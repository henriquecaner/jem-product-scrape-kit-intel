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
    # Create with restrictive perms from the start — no world-readable window.
    # (0o600 has no group/other bits, so umask cannot loosen it.) chmod after
    # covers the pre-existing-file case, and its failure is surfaced, not swallowed.
    fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(value)
    os.chmod(p, mode)
    return p
