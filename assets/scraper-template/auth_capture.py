"""Capture an authenticated session locally and stage it for the Actions secret
(spec §5.1). Headed browser login happens on the user's machine; the run replays
the saved session on the runner. This CLI never pushes the secret automatically —
it prints the exact `gh secret set` command for a conscious step."""
import argparse
import os
import sys
from pathlib import Path

from jemscrape.config import load_config, validate_config
from jemscrape.proxy import proxy_dict_from_url

HERE = Path(__file__).resolve().parent
SESSION_PATH = HERE / ".scrape-session.json"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Capture an authenticated session (local)")
    parser.add_argument("--config", default=str(HERE / "config.json"))
    parser.add_argument("--out", default=str(SESSION_PATH))
    args = parser.parse_args(argv)

    try:
        cfg = load_config(args.config)
        validate_config(cfg)
    except Exception as exc:
        print(f"[auth-capture] BLOCKED: {exc}", file=sys.stderr)
        return 2
    login_url = cfg.get("login_url")
    if not login_url:
        print("[auth-capture] login_url required in config (set auth_required + login_url).",
              file=sys.stderr)
        return 2

    proxy = proxy_dict_from_url(os.environ.get("HTTPS_PROXY"))
    from drivers.auth_capture import capture_session   # lazy: Playwright only here
    try:
        out = capture_session(login_url, args.out, proxy=proxy, user_agent=cfg["user_agent"])
    except RuntimeError as exc:  # Playwright missing -> actionable hint
        print(f"[auth-capture] {exc}", file=sys.stderr)
        return 2

    # Report validity + the secret push instruction (never auto-push).
    from jemscrape.session import load_session
    try:
        session = load_session(out)
        exp = session.expires_at()
        when = exp.isoformat() if exp else "unknown (session cookies only)"
    except Exception:
        when = "unknown"
    print(f"[auth-capture] saved -> {out}")
    print(f"[auth-capture] token valid until: {when}")
    print(f"[auth-capture] next: gh secret set SCRAPE_STORAGE_STATE < {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
