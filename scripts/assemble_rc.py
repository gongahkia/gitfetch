"""Freeze reviewed working-tree files and build local, unpublished RC artifacts.

Run in a disposable environment with pinned build/setuptools/wheel installed.
The generated verification report/evidence live beside artifacts, outside the
source snapshot, to avoid self-referential hashes. No Git writes or publication.
"""
import argparse
import gzip
import hashlib
import importlib.metadata
import io
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from pathlib import Path

REPORT = 'docs/RELEASE-CANDIDATE-VERIFICATION-V3.md'
EXCLUDED_PARTS = {'.git', '.venv', 'venv', '__pycache__', '.mypy_cache', '.ruff_cache', 'build', 'dist'}
PRIVATE_NAMES = {'.env', '.pypirc', 'credentials', 'config.toml'}


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args]).decode()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected_files(root, allowed):
    tracked = set(git(root, 'ls-files', '-z').split('\0')) - {''}
    untracked = set(git(root, 'ls-files', '--others', '--exclude-standard', '-z').split('\0')) - {''}
    approved = {name for name in untracked if any(name == entry or name.startswith(entry + '/') for entry in allowed)}
    names = sorted((tracked | approved) - {REPORT})
    selected = {}
    for name in names:
        relative = Path(name)
        path = root / relative
        if not path.exists():
            continue  # Preserve tracked deletions rather than resurrecting HEAD.
        if (relative.is_absolute() or '..' in relative.parts or
                any(part in EXCLUDED_PARTS or part.endswith('.egg-info') for part in relative.parts) or
                relative.name in PRIVATE_NAMES or relative.suffix in {'.pyc', '.pem', '.key'}):
            raise ValueError(f'unsafe snapshot path: {name}')
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError(f'snapshot requires an in-tree regular file: {name}')
        selected[name] = {'sha256': digest(path), 'bytes': path.stat().st_size,
                          'mode': 0o755 if path.stat().st_mode & stat.S_IXUSR else 0o644}
    return selected


def write_archive(path, members, epoch):
    """Canonical tar/gzip headers; file contents are never rewritten."""
    with (path.open('wb') as raw,
          gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=epoch) as compressed,
          tarfile.open(fileobj=compressed, mode='w', format=tarfile.PAX_FORMAT) as archive):
        for name, content, mode in sorted(members):
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(content), mode, epoch
            info.uid = info.gid = 0
            info.uname = info.gname = ''
            archive.addfile(info, io.BytesIO(content))


def normalize_sdist(path, epoch):
    with tarfile.open(path) as archive:
        members = []
        for info in archive.getmembers():
            if info.isdir():
                continue
            if not info.isfile() or Path(info.name).is_absolute() or '..' in Path(info.name).parts:
                raise ValueError('unexpected non-regular sdist member')
            stream = archive.extractfile(info)
            assert stream is not None
            members.append((info.name, stream.read(), 0o755 if info.mode & 0o111 else 0o644))
    write_archive(path, members, epoch)
    # Repacking headers must not alter the source/content membership.
    with tarfile.open(path) as archive:
        assert {m.name: archive.extractfile(m).read() for m in archive if m.isfile()} == {n: b for n, b, _ in members}


def verify(root, manifest):
    current = selected_files(root, manifest['allowed_untracked'])
    if current != manifest['source_files']:
        changed = sorted(name for name in current.keys() | manifest['source_files'].keys()
                         if current.get(name) != manifest['source_files'].get(name))
        raise ValueError('candidate INVALID: source changed; rebuild in a new output directory: ' + ', '.join(changed))
    return True


def reproduce(root, output, manifest):
    """Rebuild an extracted snapshot without requiring its original Git repo."""
    if output.exists():
        raise ValueError('rebuild output already exists; select a fresh directory')
    with tempfile.TemporaryDirectory(prefix='gitfetch-rc-reproduce-') as temporary:
        source = Path(temporary) / 'source'
        for name, info in manifest['source_files'].items():
            relative = Path(name)
            path = root / relative
            if (relative.is_absolute() or '..' in relative.parts or path.is_symlink() or
                    not path.resolve().is_relative_to(root) or digest(path) != info['sha256']):
                raise ValueError('snapshot content mismatch: ' + name)
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            target.chmod(info['mode'])
            os.utime(target, (manifest['source_date_epoch'],) * 2)
        env = {**os.environ, 'SOURCE_DATE_EPOCH': str(manifest['source_date_epoch']), 'PYTHONHASHSEED': '0', 'TZ': 'UTC'}
        subprocess.run([sys.executable, '-m', 'build', '--no-isolation', '--outdir', str(output), str(source)],
                       env=env, check=True)
    for product in output.iterdir():
        if product.name.endswith('.tar.gz'):
            normalize_sdist(product, manifest['source_date_epoch'])
        if digest(product) != manifest['artifacts'][product.name]['sha256']:
            raise ValueError('rebuild differs from verified artifact: ' + product.name)
    print('PASS: independent snapshot rebuild matches wheel and sdist hashes')


def assemble(root, output, allowed):
    if output.exists():
        raise ValueError('output already exists; use a new directory to preserve previous candidates')
    metadata = tomllib.loads((root / 'pyproject.toml').read_text())
    version = metadata['project']['version']
    if version != '3.0.0rc1':
        raise ValueError('this assembly procedure is for 3.0.0rc1')
    files = selected_files(root, allowed)
    epoch = int(git(root, 'show', '-s', '--format=%ct', 'HEAD').strip())
    status = git(root, 'status', '--porcelain=v1', '--untracked-files=all')
    manifest = {
        'candidate_version': version, 'source_head': git(root, 'rev-parse', 'HEAD').strip(),
        'branch': git(root, 'branch', '--show-current').strip(), 'worktree_status': status,
        'source_date_epoch': epoch, 'allowed_untracked': allowed, 'source_files': files,
        'excluded_generated_report': REPORT,
        'dependencies': metadata['project']['dependencies'], 'requires_python': metadata['project']['requires-python'],
        'build_environment': {'python': sys.version, 'platform': platform.platform(),
                              'tools': {n: importlib.metadata.version(n) for n in ('build', 'setuptools', 'wheel', 'packaging')}},
        'build_commands': [['python', '-m', 'build', '--no-isolation', '--outdir', '<artifacts>', '<frozen-source>']],
        'normalization': 'SOURCE_DATE_EPOCH; canonical source and sdist tar/gzip headers; source bytes preserved',
        'publication': 'local candidate only; not an official GitHub tag archive',
    }
    output.mkdir(parents=True)
    artifact_dir = output / 'artifacts'
    artifact_dir.mkdir()
    source_archive = artifact_dir / f'gitfetch-{version}-source.tar.gz'
    prefix = f'gitfetch-{version}'
    members = [(f'{prefix}/{name}', (root / name).read_bytes(), info['mode']) for name, info in files.items()]
    write_archive(source_archive, members, epoch)
    verify(root, manifest)  # Detect a concurrent edit during capture.
    env = {**os.environ, 'SOURCE_DATE_EPOCH': str(epoch), 'PYTHONHASHSEED': '0', 'TZ': 'UTC'}
    build_hashes = []
    for attempt in range(2):
        with tempfile.TemporaryDirectory(prefix='gitfetch-rc-build-') as temporary:
            source = Path(temporary) / prefix
            source.mkdir()
            for name, content, mode in members:
                path = Path(temporary) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
                path.chmod(mode)
                os.utime(path, (epoch, epoch))
            target = Path(temporary) / 'artifacts'
            with (output / f'build-{attempt + 1}.log').open('w') as log:
                subprocess.run([sys.executable, '-m', 'build', '--no-isolation', '--outdir', str(target), str(source)],
                               env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
            products = sorted(target.iterdir())
            for product in products:
                if product.name.endswith('.tar.gz'):
                    normalize_sdist(product, epoch)
            build_hashes.append({product.name: digest(product) for product in products})
            if attempt == 0:
                for product in products:
                    shutil.copyfile(product, artifact_dir / product.name)
    if build_hashes[0] != build_hashes[1]:
        raise ValueError(f'candidate INVALID: repeat builds differ: {build_hashes}')
    manifest['reproducible_builds'] = build_hashes
    manifest['artifacts'] = {p.name: {'sha256': digest(p), 'bytes': p.stat().st_size} for p in sorted(artifact_dir.iterdir())}
    verify(root, manifest)
    (output / 'source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (output / 'SHA256SUMS').write_text(''.join(f'{value["sha256"]}  artifacts/{name}\n' for name, value in manifest['artifacts'].items()))
    print(f'Assembled {version}: {len(files)} source files; two matching builds; {output}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--allow-untracked', action='append', default=[])
    parser.add_argument('--verify', type=Path, help='Verify a previously generated source manifest against the checkout')
    parser.add_argument('--rebuild', type=Path, help='Rebuild an extracted --root using this manifest, without Git')
    args = parser.parse_args()
    root = args.root.resolve()
    if args.rebuild and args.output:
        reproduce(root, args.output.resolve(), json.loads(args.rebuild.read_text()))
    elif args.verify:
        manifest = json.loads(args.verify.read_text())
        verify(root, manifest)
        for name, info in manifest['artifacts'].items():
            if digest(args.verify.parent / 'artifacts' / name) != info['sha256']:
                raise ValueError('candidate INVALID: artifact hash mismatch: ' + name)
        print('PASS: frozen source and every candidate artifact match the manifest')
    elif args.output:
        assemble(root, args.output.resolve(), args.allow_untracked)
    else:
        parser.error('--output or --verify is required')


if __name__ == '__main__':
    main()
