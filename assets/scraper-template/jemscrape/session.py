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
    subdomain; a bare domain matches that exact host."""
    cd = (cookie_domain or "").lower().lstrip(".")
    target = (target or "").lower()
    return target == cd or target.endswith("." + cd)


class Session:
    def __init__(self, raw):
        self._raw = raw
        self._cookies = raw.get("cookies") or []

    @property
    def storage_state(self):
        return self._raw

    def cookie_header(self, domain):
        now = datetime.now(timezone.utc).timestamp()
        parts = []
        for c in self._cookies:
            if not _domain_matches(c.get("domain"), domain):
                continue
            expires = c.get("expires", -1)
            if isinstance(expires, (int, float)) and expires > 0 and expires <= now:
                continue  # expired
            parts.append(f"{c['name']}={c['value']}")
        return "; ".join(parts)

    def expires_at(self, now=None):
        stamps = [c.get("expires") for c in self._cookies
                  if isinstance(c.get("expires"), (int, float)) and c.get("expires") > 0]
        if not stamps:
            return None
        return datetime.fromtimestamp(min(stamps), tz=timezone.utc)

    def is_expired(self, now):
        exp = self.expires_at()
        return exp is not None and exp <= now


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
