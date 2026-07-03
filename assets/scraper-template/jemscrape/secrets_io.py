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
    # Create with restrictive perms from the start (0o600 has no group/other
    # bits, so umask cannot loosen it), and reject a symlink at the path via
    # O_NOFOLLOW so a pre-planted symlink can't redirect the write+chmod onto
    # another file. For a pre-existing regular file, fchmod happens on the
    # open fd BEFORE any bytes are written, so it never sits at the file's old
    # (possibly loose) perms during the write; the trailing chmod(path) below
    # is belt-and-suspenders and its failure is surfaced, not swallowed.
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(str(p), flags, mode)
    except OSError as exc:
        raise ConfigError(f"cannot open secret target {p}: {exc}") from exc
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        os.fchmod(f.fileno(), mode)
        f.write(value)
    os.chmod(p, mode)
    return p
