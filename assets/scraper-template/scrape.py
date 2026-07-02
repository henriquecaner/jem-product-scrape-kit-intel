"""Generated scraper entry point. Runtime compliance gate lives in preflight()."""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from jemscrape.config import load_config, validate_config
from jemscrape.authz import load_authorization, validate as validate_authz
from jemscrape.warmup_gate import load_warmup_verdict, validate_warmup
from jemscrape.pacing import Pacer

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"
AUTHZ_PATH = HERE / ".scrape-authorization.json"
WARMUP_PATH = HERE / ".scrape-warmup.json"


def build_pacer(cfg):
    """Build a Pacer from raw config, normalizing an inverted min/max range (assumes cfg may not have passed validate_config)."""
    floor = cfg["rate_limit_floor_seconds"]
    lo = cfg.get("min_delay_seconds", floor)
    hi = cfg.get("max_delay_seconds", max(floor, lo))
    hi = max(lo, hi)
    return Pacer(min_delay=lo, max_delay=hi, floor=floor)


def preflight(config_path, authz_path, now):
    cfg = load_config(config_path)
    validate_config(cfg)
    auth = load_authorization(authz_path)
    target_url = f"https://{cfg['target_domain']}/"
    validate_authz(auth, target_url, now)
    return cfg, auth


def require_warmup(warmup_path, target_url, now):
    """Fail-closed: raises WarmupError unless a green, unexpired, matching verdict exists."""
    verdict = load_warmup_verdict(warmup_path)
    validate_warmup(verdict, target_url, now)


def build_fetcher(cfg, *, http_fetch, render_fn=None):
    """Select the run fetcher by fetch_mode. Browser mode wraps a render_fn
    (Playwright) into the runner's fetcher(url)->html contract; default is HTTP."""
    if cfg.get("fetch_mode") == "browser":
        from jemscrape.browser import make_browser_fetcher
        if render_fn is None:
            from drivers.playwright_render import render as _render
            render_fn = lambda url: _render(url, user_agent=cfg["user_agent"])
        return make_browser_fetcher(render_fn)
    user_agent = cfg["user_agent"]
    return lambda url: http_fetch(url, user_agent=user_agent)


def main(argv=None):
    parser = argparse.ArgumentParser(description="JEM scraper")
    parser.add_argument("--limit", type=int, default=0, help="max URLs (0 = all)")
    parser.add_argument("--reparse", action="store_true", help="reparse cache without fetching")
    args = parser.parse_args(argv)

    try:
        cfg, _auth = preflight(CONFIG_PATH, AUTHZ_PATH, datetime.now(timezone.utc))
    except Exception as exc:  # fail-closed: no run without a valid gate
        print(f"[gate] BLOCKED: {exc}", file=sys.stderr)
        return 2

    try:
        target_url = f"https://{cfg['target_domain']}/"
        require_warmup(WARMUP_PATH, target_url, datetime.now(timezone.utc))
    except Exception as exc:   # fail-closed: no full run without a green warm-up verdict
        print(f"[gate] BLOCKED: warm-up not green — {exc}", file=sys.stderr)
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

    fetcher = build_fetcher(cfg, http_fetch=http_fetch)

    summary = run(urls=urls, parse_fn=parse, cache_dir=cache_dir, fetcher=fetcher,
                  pacer=pacer, cursor=cursor, manifest=manifest, reparse=args.reparse)
    manifest.write(HERE / "exports" / "scrape_manifest.json")
    print(f"[done] {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
