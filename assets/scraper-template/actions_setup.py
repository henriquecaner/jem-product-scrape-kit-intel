"""Reconstruct the gitignored gate files from Actions secrets before a run.
Fail-closed: a missing secret aborts (exit 2) before any scrape step."""
import os
import sys
from pathlib import Path

from jemscrape.secrets_io import materialize_secret
from jemscrape.errors import ConfigError

HERE = Path(__file__).resolve().parent

_SECRET_FILES = [
    ("SCRAPE_AUTHORIZATION", HERE / ".scrape-authorization.json"),
    ("SCRAPE_WARMUP", HERE / ".scrape-warmup.json"),
]


def main(argv=None, *, env=None, targets=None):
    env = os.environ if env is None else env
    targets = _SECRET_FILES if targets is None else targets
    written = []
    for name, path in targets:
        try:
            materialize_secret(name, path, env=env)
        except ConfigError as exc:
            print(f"[actions-setup] BLOCKED: {exc}", file=sys.stderr)
            return 2
        written.append(str(path))
    for w in written:
        print(f"[actions-setup] wrote {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
