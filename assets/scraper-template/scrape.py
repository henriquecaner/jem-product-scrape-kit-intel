"""Generated scraper entry point. Runtime compliance gate lives in preflight()."""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from jemscrape.config import load_config, validate_config
from jemscrape.authz import load_authorization, validate as validate_authz
from jemscrape.pacing import Pacer

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"
AUTHZ_PATH = HERE / ".scrape-authorization.json"


def build_pacer(cfg):
    floor = cfg["rate_limit_floor_seconds"]
    lo = cfg.get("min_delay_seconds", floor)
    hi = cfg.get("max_delay_seconds", max(floor, lo))
    return Pacer(min_delay=lo, max_delay=hi, floor=floor)


def preflight(config_path, authz_path, target_url, now):
    cfg = load_config(config_path)
    validate_config(cfg)
    auth = load_authorization(authz_path)
    validate_authz(auth, target_url, now)
    return cfg, auth


def main(argv=None):
    parser = argparse.ArgumentParser(description="JEM scraper")
    parser.add_argument("--limit", type=int, default=0, help="max URLs (0 = all)")
    parser.add_argument("--reparse", action="store_true", help="reparse cache without fetching")
    args = parser.parse_args(argv)

    cfg = load_config(CONFIG_PATH)
    validate_config(cfg)
    target_url = f"https://{cfg['target_domain']}/"
    try:
        preflight(CONFIG_PATH, AUTHZ_PATH, target_url, datetime.now(timezone.utc))
    except Exception as exc:  # fail-closed: no run without a valid gate
        print(f"[gate] BLOCKED: {exc}", file=sys.stderr)
        return 2

    # Site adaptation supplies discover() -> list[str] and parse(html, url) -> dict | None.
    from site_adapter import discover, parse  # created per site (not in this plan)
    from jemscrape.cache import Cursor
    from jemscrape.manifest import Manifest
    from jemscrape.fetch import fetch as http_fetch
    from jemscrape.runner import run

    urls = discover(cfg)
    if args.limit:
        urls = urls[: args.limit]

    cache_dir = HERE / "data"
    cursor = Cursor(HERE / "state" / "cursor.json").load()
    manifest = Manifest()
    pacer = build_pacer(cfg)

    def fetcher(url):
        return http_fetch(url, user_agent=cfg["user_agent"])

    summary = run(urls=urls, parse_fn=parse, cache_dir=cache_dir, fetcher=fetcher,
                  pacer=pacer, cursor=cursor, manifest=manifest, reparse=args.reparse)
    manifest.write(HERE / "exports" / "scrape_manifest.json")
    print(f"[done] {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
