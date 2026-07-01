import json
from pathlib import Path

from .errors import ConfigError

VALID_RUNTIMES = {"local", "github_actions", "vm"}


def load_config(path):
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read config at {p}: {exc}") from exc
    try:
        cfg = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"config at {p} is not valid JSON: {exc}") from exc
    if not isinstance(cfg, dict):
        raise ConfigError("config must be a JSON object")
    return cfg


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate_config(cfg):
    errors = []

    domain = cfg.get("target_domain")
    if not isinstance(domain, str) or not domain.strip():
        errors.append("target_domain: required non-empty string")

    runtime = cfg.get("runtime")
    if runtime not in VALID_RUNTIMES:
        errors.append(f"runtime: must be one of {sorted(VALID_RUNTIMES)}")

    ua = cfg.get("user_agent")
    if not isinstance(ua, str) or not ua.strip():
        errors.append("user_agent: required non-empty string")

    floor = cfg.get("rate_limit_floor_seconds")
    if not _is_number(floor) or floor <= 0:
        errors.append("rate_limit_floor_seconds: required number > 0")

    lo = cfg.get("min_delay_seconds")
    hi = cfg.get("max_delay_seconds")
    if lo is not None or hi is not None:
        if not _is_number(lo) or not _is_number(hi):
            errors.append("min_delay_seconds/max_delay_seconds: both must be numbers if either is set")
        else:
            if lo > hi:
                errors.append("min_delay_seconds must be <= max_delay_seconds")
            if _is_number(floor) and lo < floor:
                errors.append("min_delay_seconds must be >= rate_limit_floor_seconds")

    if errors:
        raise ConfigError("invalid config: " + "; ".join(errors))
