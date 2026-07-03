"""Merge PATH/env into ~/.claude/settings.json without clobbering existing keys
(Desktop-app PATH fix, onboarding §6 Fase B). Atomic write."""
import json
from pathlib import Path

from .cache import atomic_write


def patch_claude_settings(path, *, env):
    p = Path(path)
    settings = {}
    if p.exists():
        try:
            settings = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            settings = {}
        if not isinstance(settings, dict):
            settings = {}
    current_env = settings.get("env")
    if not isinstance(current_env, dict):
        current_env = {}
    for key, value in env.items():
        # Don't let an empty/blank incoming value (e.g. a PATH read as "" in a
        # broken shell) clobber a previously-good existing value.
        if not value and current_env.get(key):
            continue
        current_env[key] = value
    settings["env"] = current_env
    atomic_write(p, json.dumps(settings, indent=2) + "\n")
    return settings
