import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from .errors import AuthorizationError

VALID_TYPES = {"public_competitor", "contracted_partner", "own_account"}
VALID_ROBOTS = {"allowed", "disallowed"}


@dataclass
class Authorization:
    # NOTE: `scope` and `requires_approval` are loaded and validated-for-presence
    # here, but not yet ENFORCED — enforcement (run-plan approval gate, and
    # discovery/URL scoping against `scope`) lands in later plans (Plan 2+).
    # This loaded-but-not-enforced gap is intentional and tracked, not an oversight.
    target_domain: str
    authorization_type: str
    approver: str
    approved_at: str
    expires_at: str
    rate_limit_floor_seconds: float
    robots_status: str
    robots_override_ref: object  # str | None
    requires_approval: bool
    scope: str


def load_authorization(path):
    p = Path(path)
    if not p.exists():
        raise AuthorizationError(f"no authorization record at {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuthorizationError(f"cannot read authorization at {p}: {exc}") from exc
    if not isinstance(data, dict):
        raise AuthorizationError(f"authorization record at {p} must be a JSON object")
    try:
        return Authorization(**{k: data.get(k) for k in Authorization.__annotations__})
    except TypeError as exc:
        raise AuthorizationError(f"malformed authorization record: {exc}") from exc


def _parse_dt(value, field):
    # datetime.fromisoformat only accepts the trailing "Z" UTC suffix on
    # Python 3.11+; the template targets 3.9+, so normalize it ourselves.
    if isinstance(value, str) and value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise AuthorizationError(f"{field}: not an ISO-8601 datetime ({value!r})") from exc


def validate(auth, target_url, now):
    if not isinstance(auth.authorization_type, str) or auth.authorization_type not in VALID_TYPES:
        raise AuthorizationError(f"authorization_type invalid: {auth.authorization_type!r}")
    if auth.robots_status not in VALID_ROBOTS:
        raise AuthorizationError(f"robots_status invalid: {auth.robots_status!r}")
    if not auth.approver:
        raise AuthorizationError("approver is required")

    host = urlsplit(target_url).hostname or ""
    if host != auth.target_domain:
        raise AuthorizationError(
            f"target host {host!r} does not match authorized domain {auth.target_domain!r}"
        )

    expires = _parse_dt(auth.expires_at, "expires_at")
    if expires.tzinfo is None:
        raise AuthorizationError("expires_at must include a timezone offset")
    try:
        is_expired = now >= expires
    except TypeError as exc:
        raise AuthorizationError(f"cannot compare expiry ({exc})") from exc
    if is_expired:
        raise AuthorizationError(f"authorization expired at {auth.expires_at}")

    override_ref = auth.robots_override_ref
    has_override = bool(override_ref) and bool(str(override_ref).strip())
    if auth.robots_status == "disallowed":
        if auth.authorization_type == "public_competitor":
            raise AuthorizationError("robots.txt disallows and target is a public competitor — hard block")
        if auth.authorization_type == "contracted_partner" and not has_override:
            raise AuthorizationError("robots.txt disallows; contracted_partner requires robots_override_ref")
