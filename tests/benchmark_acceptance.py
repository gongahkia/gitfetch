"""Release CPU/cache benchmarks: deterministic transport, no public API latency."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from statistics import median
from unittest import mock
from urllib.parse import urlsplit

import requests
from avatar_fixtures import image_bytes
from modern_fixtures import REFERENCE, fixture
from test_terminal_graphics import decision

from gitfetch.cli import main
from gitfetch.config import preset_config, write_config
from gitfetch.design import resolve_colors
from gitfetch.export_design import plan_profile_card
from gitfetch.export_paint import scene_png, scene_svg
from gitfetch.images import AvatarLoader, AvatarResult, prepare_avatar
from gitfetch.kitty_graphics import encode_avatar
from gitfetch.layout import AvatarGeometry, Preferences, Viewport, plan_profile
from gitfetch.render import _render_avatar_image
from gitfetch.terminal_output import build_terminal_frame


def measure(name, function, loops=10):
    samples=[]
    for _ in range(5):
        start=time.perf_counter()
        for _ in range(loops):
            function()
        samples.append((time.perf_counter()-start)*1000/loops)
    print(f'{name}: median {median(samples):.3f} ms; range {min(samples):.3f}–{max(samples):.3f}')


def main_benchmark():
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory); cache=root/'cache'; path=root/'config.toml'
        config=preset_config('minimal'); config['profile']['username']='fixture'
        config['display'].update(presentation='modern',avatar=False)
        write_config(path,config)
        calls=[]
        def response(_session, method, url, **kwargs):
            calls.append(urlsplit(url).path)
            data=({'login':'fixture','name':'Synthetic','public_repos':0,'followers':0,'following':0,'public_gists':0,
                   'created_at':'2024-01-01T00:00:00Z'} if urlsplit(url).path=='/users/fixture' else [])
            result=requests.Response(); result.status_code=200; result.url=url
            result._content=json.dumps(data).encode(); return result
        def run(*flags):
            with contextlib.redirect_stdout(io.StringIO()):
                assert main(['--config',str(path),'--format','plain','--no-avatar',*flags])==0
        with (mock.patch('requests.Session.request',autospec=True,side_effect=response),
              mock.patch('gitfetch.cli.cache_dir',return_value=cache),
              mock.patch('gitfetch.cli.get_token',return_value=''),
              mock.patch('shutil.get_terminal_size',return_value=os.terminal_size((80,24)))):
            run(); initial=len(calls)
            measure('CLI warm fixture cache',run,5)
            assert len(calls)==initial
            measure('CLI offline fixture lookup',lambda:run('--offline','--user','fixture'),5)
            assert len(calls)==initial
            child_code = ("from pathlib import Path; from unittest.mock import patch; from gitfetch.cli import main; "
                          + "cache_patch=patch('gitfetch.cli.cache_dir',return_value=Path("+repr(str(cache))+")); cache_patch.start(); "
                          + "token_patch=patch('gitfetch.cli.get_token',return_value=''); token_patch.start(); "
                          + "raise SystemExit(main("+repr(['--config',str(path),'--offline','--no-avatar','--format','plain'])+"))")
            def process_cli():
                result=subprocess.run([sys.executable,'-c',child_code],capture_output=True,timeout=20,check=False)
                assert result.returncode==0, result.stderr.decode()
            measure('Whole-process CLI with offline cached fixtures (startup included)',process_cli,1)
            cold=[]; counts=[]
            for _ in range(5):
                for entry in cache.glob('*.json'): entry.unlink()
                before=len(calls); start=time.perf_counter();run()
                cold.append((time.perf_counter()-start)*1000); counts.append(len(calls)-before)
            print(f'CLI cold fixture cache: median {median(cold):.3f} ms; range {min(cold):.3f}–{max(cold):.3f}; mocked GET counts {counts}')
    _,_,document=fixture(plugin=True,partial=True)
    asset=prepare_avatar(image_bytes('transparent'))
    config=preset_config('minimal');config['display'].update(avatar=True,presentation='modern')
    config['_color_force']='on'; loader=mock.Mock(spec=AvatarLoader);loader.load.return_value=AvatarResult(asset)
    config['_avatar_loader']=loader
    measure('Theme resolution',lambda:resolve_colors('catppuccin-mocha'),100)
    measure('Layout 100x30',lambda:plan_profile(document,Viewport(100,30),Preferences(),AvatarGeometry(*asset.effective_size),reference_date=REFERENCE))
    measure('Half-block 28 cols',lambda:_render_avatar_image(asset.image,28,'halfblock','truecolor','BS#&@$%*!:.'))
    measure('Kitty PNG encoding',lambda:encode_avatar(asset,number=23,columns=28,rows=14))
    measure('Terminal frame with Kitty encoding',lambda:build_terminal_frame(config,document,decision(),Viewport(100,30),reference_date=REFERENCE))
    display={**config['display'],'card_width':960,'card_height':540}
    plan=lambda:plan_profile_card(document,display,asset.image,reference_date=REFERENCE)
    prepared=plan();scene_svg(prepared)
    measure('Export shared plan',plan)
    measure('SVG serialization',lambda:scene_svg(prepared))
    def png():
        with io.BytesIO() as output: scene_png(prepared,output)
    measure('PNG rendering',png)


if __name__=='__main__': main_benchmark()
