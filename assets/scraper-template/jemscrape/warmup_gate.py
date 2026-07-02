import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from .errors import WarmupError

VALID_VERDICTS = {"green", "adjust", "ask"}


@dataclass
class WarmupVerdict:
    target_domain: str
    verdict: str
    generated_at: str
    expires_at: str
    report_sha256: str      # binds this verdict to a specific recon report (traceability)
    reviewer: str
    advisor: str


def load_warmup_verdict(path):
    p = Path(path)
    if not p.exists():
        raise WarmupError(f"no warm-up verdict at {p} — run the warm-up lap + green-light review first")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WarmupError(f"cannot read warm-up verdict at {p}: {exc}") from exc
    if not isinstance(data, dict):
        raise WarmupError(f"warm-up verdict at {p} must be a JSON object")
    try:
        return WarmupVerdict(**{k: data.get(k) for k in WarmupVerdict.__annotations__})
    except TypeError as exc:
        raise WarmupError(f"malformed warm-up verdict: {exc}") from exc


def _parse_dt(value):
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise WarmupError(f"expires_at: not an ISO-8601 datetime ({value!r})") from exc


def validate_warmup(verdict, target_url, now):
    if verdict.verdict not in VALID_VERDICTS:
        raise WarmupError(f"verdict invalid: {verdict.verdict!r}")
    if verdict.verdict != "green":
        raise WarmupError(f"warm-up verdict is {verdict.verdict!r}, not green — full run blocked")
    host = urlsplit(target_url).hostname or ""
    if host != verdict.target_domain:
        raise WarmupError(
            f"target host {host!r} does not match warm-up domain {verdict.target_domain!r}")
    expires = _parse_dt(verdict.expires_at)
    if expires.tzinfo is None:
        raise WarmupError("expires_at must include a timezone offset")
    try:
        expired = now >= expires
    except TypeError as exc:
        raise WarmupError(f"cannot compare expiry ({exc})") from exc
    if expired:
        raise WarmupError(f"warm-up verdict expired at {verdict.expires_at}")
