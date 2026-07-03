"""Warm-up lap (spec §9.1): sample a site and detect render/auth/anti-bot/shape
before the full run. Compliance gate runs first (fail-closed). No product scraping
beyond the sample; the two-agent green-light review is the scrape-warmup skill's job."""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from jemscrape.fetch import probe as http_probe
from jemscrape.recon import run_warmup, write_report
from scrape import preflight   # compliance gate (config + authz), fail-closed

HERE = Path(__file__).resolve().parent


def main(argv=None, *, probe_fn=None, parse_fn=None, render_fn=None):
    parser = argparse.ArgumentParser(description="Warm-up lap (recon before full run)")
    parser.add_argument("--sample", required=True, help="JSON file: list of sample URLs")
    parser.add_argument("--config", default=str(HERE / "config.json"))
    parser.add_argument("--authz", default=str(HERE / ".scrape-authorization.json"))
    parser.add_argument("--out", default=str(HERE / ".scrape-warmup-report.json"))
    parser.add_argument("--render", choices=["http", "browser"], default=None,
                        help="fetch mode override (default: config fetch_mode or http)")
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc)
    try:
        cfg, _auth = preflight(args.config, args.authz, now)
    except Exception as exc:   # compliance gate is fail-closed
        print(f"[warmup] BLOCKED by compliance gate: {exc}", file=sys.stderr)
        return 2

    from scrape import load_run_session
    try:
        session = load_run_session(cfg, HERE / ".scrape-session.json", now)
    except Exception as exc:   # fail-closed: no authenticated warm-up without a valid session
        print(f"[warmup] BLOCKED: session gate — {exc}", file=sys.stderr)
        return 2

    try:
        urls = json.loads(Path(args.sample).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"[warmup] sample file not found or invalid: {exc}.", file=sys.stderr)
        return 2
    if not isinstance(urls, list) or not urls:
        print("[warmup] sample must be a non-empty JSON list of URLs.", file=sys.stderr)
        return 2

    if probe_fn is None:
        mode = args.render or cfg.get("fetch_mode", "http")
        if mode == "browser":
            from jemscrape.browser import make_browser_probe
            if render_fn is None:
                from drivers.playwright_render import render as _render
                from jemscrape.proxy import proxy_dict_from_url
                proxy = proxy_dict_from_url(os.environ.get("HTTPS_PROXY"))
                storage = session.storage_state if session is not None else None
                render_fn = lambda url: _render(url, user_agent=cfg["user_agent"],
                                                proxy=proxy, storage_state=storage)
            probe_fn = make_browser_probe(render_fn)
        else:
            user_agent = cfg["user_agent"]
            cookie_header = session.cookie_header(cfg["target_domain"]) if session is not None else None

            def probe_fn(url):
                return http_probe(url, user_agent=user_agent, cookie_header=cookie_header)
    if parse_fn is None:
        from site_adapter import parse as parse_fn   # per-site, created in scaffold

    report = run_warmup(
        urls, probe_fn=probe_fn, parse_fn=parse_fn,
        source_site=cfg["target_domain"], scraped_at=now.isoformat(),
        authorization_ref=str(args.authz))
    write_report(report, args.out)

    print(f"[warmup] sampled={report.sampled} fetched={report.fetched} "
          f"spa={report.spa_count} auth={report.auth_count} antibot={report.antibot_count} "
          f"parse_errors={report.parse_errors} fetch_errors={report.fetch_errors}")
    for item in report.checklist:
        print(f"  - {item}")
    print(f"[warmup] report -> {args.out}")
    print("[warmup] next: 2-agent review (Opus 4.8 xhigh + Sonnet 5 advisor) decides "
          "VERDE/AJUSTAR/PEDIR AJUDA and writes .scrape-warmup.json (gate for the full run).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
