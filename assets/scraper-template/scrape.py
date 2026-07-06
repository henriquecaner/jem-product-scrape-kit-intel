"""Generated scraper entry point. Runtime compliance gate lives in preflight()."""
import argparse
import json
import os
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
SESSION_PATH = HERE / ".scrape-session.json"


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


def flush_outputs(manifest, cache_dir):
    """Write the manifest + the accumulated records file build_dataset consumes.
    Called on both a clean finish and an AuthExpired abort. Records accumulate by
    url across chained runs (merge_records), so a chunked/cron run doesn't drop
    every chunk but the last. The file lives under state/ (versioned, persists on
    the Actions runtime, unlike git-ignored data/). Fail-open: a missing/corrupt
    accumulator starts empty with a warning — never aborts and discards this run."""
    manifest.write(HERE / "exports" / "scrape_manifest.json")
    from jemscrape.cache import atomic_write
    from jemscrape.records import merge_records
    records_path = HERE / "state" / "raw_records.json"
    existing = []
    if records_path.exists():
        try:
            loaded = json.loads(records_path.read_text(encoding="utf-8"))
            existing = loaded if isinstance(loaded, list) else []
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[warn] could not read {records_path} ({exc}); starting fresh",
                  file=sys.stderr)
    merged = merge_records(existing, manifest.records_for_build(cache_dir))
    atomic_write(records_path, json.dumps(merged, ensure_ascii=False, indent=2))
    return records_path


def require_warmup(warmup_path, target_url, now):
    """Fail-closed: raises WarmupError unless a green, unexpired, matching verdict exists."""
    verdict = load_warmup_verdict(warmup_path)
    validate_warmup(verdict, target_url, now)


def load_run_session(cfg, session_path, now):
    """Fail-closed session gate for the auth path. Returns None when auth isn't
    required; otherwise loads the session and raises SessionError if it's
    missing or expired (spec §5.1 rules 5)."""
    if not cfg.get("auth_required"):
        return None
    from jemscrape.session import load_session   # stdlib, but keep imports local to the path
    session = load_session(session_path)
    if session.is_expired(now):
        from jemscrape.errors import SessionError
        raise SessionError("session token expired — renew locally with auth_capture.py "
                           "and update the SCRAPE_STORAGE_STATE secret")
    return session


def build_fetcher(cfg, *, http_fetch, render_fn=None, session=None):
    """Select the run fetcher by fetch_mode. Browser mode wraps a render_fn
    (Playwright) into the runner's fetcher(url)->html contract; default is HTTP.
    When session is set, the HTTP path sends its Cookie header and the browser
    path replays its storage_state; the browser proxy comes from HTTPS_PROXY."""
    if cfg.get("fetch_mode") == "browser":
        from jemscrape.browser import make_browser_fetcher
        if render_fn is None:
            from drivers.playwright_render import render as _render
            from jemscrape.proxy import proxy_dict_from_url
            proxy = proxy_dict_from_url(os.environ.get("HTTPS_PROXY"))
            storage = session.storage_state if session is not None else None
            render_fn = lambda url: _render(url, user_agent=cfg["user_agent"],
                                            proxy=proxy, storage_state=storage)
        return make_browser_fetcher(render_fn)
    user_agent = cfg["user_agent"]
    cookie_header = session.cookie_header(cfg["target_domain"]) if session is not None else None
    return lambda url: http_fetch(url, user_agent=user_agent, cookie_header=cookie_header)


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

    try:
        session = load_run_session(cfg, SESSION_PATH, datetime.now(timezone.utc))
    except Exception as exc:   # fail-closed: no auth run without a valid session
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

    try:
        fetcher = build_fetcher(cfg, http_fetch=http_fetch, session=session)
    except Exception as exc:   # fail-closed: e.g. a malformed HTTPS_PROXY secret
        print(f"[gate] BLOCKED: {exc}", file=sys.stderr)
        return 2

    from jemscrape.errors import AuthExpiredError
    try:
        summary = run(urls=urls, parse_fn=parse, cache_dir=cache_dir, fetcher=fetcher,
                      pacer=pacer, cursor=cursor, manifest=manifest, reparse=args.reparse)
    except AuthExpiredError as exc:
        import notify
        notify.emit("error", f"session expired mid-run: {exc}; renew with auth_capture.py "
                             f"and update the secret")
        print(f"[gate] BLOCKED: {exc}", file=sys.stderr)
        flush_outputs(manifest, cache_dir)
        return 2
    # Hand off to normalize/export: write the records file build_dataset consumes.
    records_path = flush_outputs(manifest, cache_dir)
    print(f"[done] {summary}; records -> {records_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
