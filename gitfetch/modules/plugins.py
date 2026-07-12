from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from gitfetch.config import ConfigError
from gitfetch.github_api import GitHubClient, GitHubContext
from gitfetch.modules.builtin import MODULE_HANDLERS, ModuleResult


PLUGIN_METADATA: dict[str, dict[str, Any]] = {}
_PLUGIN_NAMES: set[str] = set()
_BUILTIN_MODULE_NAMES = frozenset(MODULE_HANDLERS)


PluginHandler = Callable[[dict[str, Any], GitHubContext, GitHubClient], ModuleResult | dict[str, Any] | list[str]]


def reset_plugin_modules() -> None:
    """Remove handlers registered for a previous in-process invocation."""
    for name in _PLUGIN_NAMES:
        MODULE_HANDLERS.pop(name, None)
    _PLUGIN_NAMES.clear()
    PLUGIN_METADATA.clear()


def load_plugin_modules(config: dict[str, Any]) -> None:
    # CLI tests and SDK-style callers can invoke gitfetch more than once in
    # one process.  Plugins are config-scoped, not process-scoped.
    reset_plugin_modules()
    plugins = config.get("plugins", {}) or {}
    paths = plugins.get("paths", []) or []
    if paths and not plugins.get("allow_unsafe", False):
        raise ConfigError("local plugins execute arbitrary code; set plugins.allow_unsafe=true to enable them")
    loaded_paths: set[Path] = set()
    for raw_path in paths:
        path = Path(str(raw_path)).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        path = path.resolve()
        if path in loaded_paths:
            continue
        if not path.exists():
            raise ConfigError(f"plugin path does not exist: {path}")
        module = _load_module_from_path(path)
        _register_from_module(module, path)
        loaded_paths.add(path)


def _load_module_from_path(path: Path) -> ModuleType:
    module_name = f"gitfetch_plugin_{abs(hash(path))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ConfigError(f"unable to load plugin: {path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # pragma: no cover - plugin code is user supplied
        raise ConfigError(f"plugin {path} failed to load: {exc}") from exc
    return module


def _register_from_module(module: ModuleType, path: Path) -> None:
    if hasattr(module, "register"):
        registry = module.register()
    else:
        registry = getattr(module, "MODULES", None)
    if not isinstance(registry, dict):
        raise ConfigError(f"plugin {path} must expose register() or MODULES")
    for name, payload in registry.items():
        if not isinstance(name, str) or not name:
            raise ConfigError(f"plugin {path} registered an invalid module name")
        if name in _BUILTIN_MODULE_NAMES:
            raise ConfigError(f"plugin {path} cannot replace built-in module '{name}'")
        if name in _PLUGIN_NAMES:
            raise ConfigError(f"plugin {path} registered duplicate module '{name}'")
        handler: PluginHandler
        description = f"Plugin module from {path.name}."
        token_required = False
        title = name.replace("_", " ").title()
        if isinstance(payload, dict):
            raw_handler = payload.get("handler")
            description = str(payload.get("description") or description)
            token_required = bool(payload.get("token_required", False))
            title = str(payload.get("title") or title)
        else:
            raw_handler = payload
        if not callable(raw_handler):
            raise ConfigError(f"plugin {path} module '{name}' has no callable handler")
        handler = raw_handler
        MODULE_HANDLERS[name] = _wrap_handler(name, title, handler)
        _PLUGIN_NAMES.add(name)
        PLUGIN_METADATA[name] = {
            "token_required": token_required,
            "description": description,
        }


def _wrap_handler(name: str, title: str, handler: PluginHandler):
    def wrapped(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
        try:
            result = handler(config, context, client)
        except Exception as exc:
            return ModuleResult(name, title, [f"plugin failed: {exc}"], {"error": str(exc)})
        if isinstance(result, ModuleResult):
            return result
        if isinstance(result, list):
            return ModuleResult(name, title, [str(line) for line in result], result, hidden=not bool(result))
        if isinstance(result, dict):
            lines = result.get("lines", [])
            if isinstance(lines, str):
                lines = [lines]
            return ModuleResult(
                name,
                str(result.get("title") or title),
                [str(line) for line in lines],
                result.get("data", result),
                hidden=bool(result.get("hidden", False)),
                requires_token=bool(result.get("requires_token", False)),
            )
        return ModuleResult(name, title, [str(result)], result, hidden=result is None)

    return wrapped


def available_module_metadata() -> dict[str, dict[str, Any]]:
    from gitfetch.config import MODULE_METADATA

    metadata = dict(MODULE_METADATA)
    metadata.update(PLUGIN_METADATA)
    return metadata
