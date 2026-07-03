"""Parse a Playwright storage_state (the single source of a captured session):
emit a Cookie header for the HTTP path, the raw storage dict for the browser
path, and the token's validity. Stdlib only; token validity is kept distinct
from run progress (the cursor owns progress). Spec §5.1."""
import json
from datetime import datetime, timezone
from pathlib import Path

from .errors import SessionError


def _domain_matches(cookie_domain, target):
    """Cookie domain rule: a leading-dot domain matches the host and any
    subdomain; a bare (host-only) domain matches that exact host only."""
    raw = cookie_domain or ""
    target = (target or "").lower()
    if raw.startswith("."):
        cd = raw[1:].lower()
        return target == cd or target.endswith("." + cd)
    return target == raw.lower()


class Session:
    def __init__(self, raw):
        self._raw = raw
        self._cookies = raw.get("cookies") or []

    @property
    def storage_state(self):
        return self._raw

    def cookie_header(self, domain, now=None):
        if now is None:
            now = datetime.now(timezone.utc)
        now_ts = now.timestamp()
        by_name = {}  # name -> (path_len, cookie), first-seen order preserved
        order = []
        for c in self._cookies:
            if not _domain_matches(c.get("domain"), domain):
                continue
            expires = c.get("expires", -1)
            if isinstance(expires, (int, float)) and expires > 0 and expires <= now_ts:
                continue  # expired
            name = c["name"]
            path_len = len(c.get("path") or "")
            if name not in by_name:
                order.append(name)
                by_name[name] = (path_len, c)
            elif path_len > by_name[name][0]:
                by_name[name] = (path_len, c)
        parts = [f"{by_name[name][1]['name']}={by_name[name][1]['value']}" for name in order]
        return "; ".join(parts)

    def expires_at(self):
        stamps = [c.get("expires") for c in self._cookies
                  if isinstance(c.get("expires"), (int, float)) and c.get("expires") > 0]
        if not stamps:
            return None
        return datetime.fromtimestamp(min(stamps), tz=timezone.utc)

    def is_expired(self, now):
        """Dead only if there is at least one persistent (time-based) cookie and
        ALL persistent cookies have expired. A session-scoped cookie (expires<=0/
        -1/missing) carries no expiry signal either way — it neither proves the
        session alive nor dead. So one still-future persistent cookie (a
        long-lived auth cookie) keeps the session alive even though a short-TTL
        persistent cookie (consent/CSRF) already expired — the runtime 401/403
        (AuthExpiredError) is the real backstop. Mirrors expires_at()'s
        persistent-cookie filter, but requires ALL (not just the earliest) to
        have expired."""
        now_ts = now.timestamp()
        persistent = [c.get("expires") for c in self._cookies
                      if isinstance(c.get("expires"), (int, float)) and c.get("expires") > 0]
        if not persistent:
            return False  # no persistent cookie present -> can't prove expiry
        return all(exp <= now_ts for exp in persistent)


def load_session(path):
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SessionError(f"cannot read session at {p}: {exc}") from exc
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SessionError(f"session at {p} is not valid JSON: {exc}") from exc
    if not isinstance(obj, dict) or not obj.get("cookies"):
        raise SessionError(f"session at {p} has no cookies")
    return Session(obj)
