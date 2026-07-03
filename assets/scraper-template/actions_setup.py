"""Reconstruct the gitignored gate files from Actions secrets before a run.
Fail-closed: a missing secret aborts (exit 2) before any scrape step."""
import os
import sys
from pathlib import Path

from jemscrape.secrets_io import materialize_secret
from jemscrape.errors import ConfigError

HERE = Path(__file__).resolve().parent


def build_targets(cfg, *, base=HERE):
    targets = [
        ("SCRAPE_AUTHORIZATION", base / ".scrape-authorization.json"),
        ("SCRAPE_WARMUP", base / ".scrape-warmup.json"),
    ]
    if cfg.get("auth_required"):
        targets.append(("SCRAPE_STORAGE_STATE", base / ".scrape-session.json"))
    return targets


def main(argv=None, *, env=None, targets=None, config=None):
    env = os.environ if env is None else env
    if targets is None:
        if config is None:
            from jemscrape.config import load_config
            try:
                config = load_config(HERE / "config.json")
            except Exception as exc:
                print(f"[actions-setup] BLOCKED: cannot read config: {exc}", file=sys.stderr)
                return 2
        targets = build_targets(config, base=HERE)
    written = []
    for name, path in targets:
        try:
            materialize_secret(name, path, env=env)
        except (ConfigError, OSError) as exc:
            print(f"[actions-setup] BLOCKED: {exc}", file=sys.stderr)
            return 2
        written.append(str(path))
    for w in written:
        print(f"[actions-setup] wrote {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
