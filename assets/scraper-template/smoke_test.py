"""Fail-closed pre-run gate: validate config + authorization before any full run."""
import sys
from datetime import datetime, timezone
from pathlib import Path

from scrape import preflight

HERE = Path(__file__).resolve().parent


def run_smoke(config_path, authz_path, now):
    try:
        preflight(config_path, authz_path, now)
    except Exception as exc:
        print(f"[smoke] FAIL: {exc}", file=sys.stderr)
        return 1
    print("[smoke] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(
        run_smoke(HERE / "config.json", HERE / ".scrape-authorization.json",
                  datetime.now(timezone.utc))
    )
