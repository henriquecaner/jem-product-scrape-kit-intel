"""Reconstruct a gitignored secret file from an env var (Actions secret),
fail-closed. Used by actions_setup.py so gate files never live in the repo."""
import os
from pathlib import Path

from .errors import ConfigError


def materialize_secret(name, path, *, env, mode=0o600):
    value = env.get(name)
    if not value or not value.strip():
        raise ConfigError(f"missing required secret env var: {name}")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(value, encoding="utf-8")
    try:
        os.chmod(p, mode)
    except OSError:
        pass
    return p
