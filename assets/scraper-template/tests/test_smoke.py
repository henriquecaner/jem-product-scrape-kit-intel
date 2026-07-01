import json
from datetime import datetime, timezone

from scrape import preflight, build_pacer
from smoke_test import run_smoke
from jemscrape.errors import AuthorizationError, ConfigError

import pytest

NOW = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)


def _write(tmp_path):
    cfg = {
        "target_domain": "example.com", "runtime": "local",
        "rate_limit_floor_seconds": 2.5, "user_agent": "UA/1",
        "min_delay_seconds": 2.5, "max_delay_seconds": 5.0,
    }
    authz = {
        "target_domain": "example.com", "authorization_type": "public_competitor",
        "approver": "henrique", "approved_at": "2026-07-01T09:00:00+00:00",
        "expires_at": "2026-07-08T09:00:00+00:00", "rate_limit_floor_seconds": 2.5,
        "robots_status": "allowed", "robots_override_ref": None,
        "requires_approval": False, "scope": "catalog",
    }
    cp = tmp_path / "config.json"
    ap = tmp_path / ".scrape-authorization.json"
    cp.write_text(json.dumps(cfg), encoding="utf-8")
    ap.write_text(json.dumps(authz), encoding="utf-8")
    return cp, ap


def test_preflight_ok_returns_cfg_and_auth(tmp_path):
    cp, ap = _write(tmp_path)
    cfg, auth = preflight(cp, ap, NOW)
    assert cfg["target_domain"] == "example.com"
    assert auth.approver == "henrique"


def test_preflight_blocks_expired_authorization(tmp_path):
    cp, ap = _write(tmp_path)
    data = json.loads(ap.read_text())
    data["expires_at"] = "2026-06-01T00:00:00+00:00"
    ap.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(AuthorizationError):
        preflight(cp, ap, NOW)


def test_preflight_blocks_missing_authorization(tmp_path):
    cp, _ = _write(tmp_path)
    with pytest.raises(AuthorizationError):
        preflight(cp, tmp_path / "nope.json", NOW)


def test_preflight_blocks_bad_config(tmp_path):
    cp, ap = _write(tmp_path)
    cp.write_text("{bad json", encoding="utf-8")
    with pytest.raises(ConfigError):
        preflight(cp, ap, NOW)


def test_build_pacer_uses_floor(tmp_path):
    cp, _ = _write(tmp_path)
    cfg = json.loads(cp.read_text())
    pacer = build_pacer(cfg)
    assert pacer.floor == 2.5


def test_build_pacer_clamps_inverted_range(tmp_path):
    cp, _ = _write(tmp_path)
    cfg = json.loads(cp.read_text())
    cfg["min_delay_seconds"] = 5
    cfg["max_delay_seconds"] = 3
    cfg["rate_limit_floor_seconds"] = 2.5
    pacer = build_pacer(cfg)
    assert pacer.max_delay >= pacer.min_delay


def test_run_smoke_returns_zero_on_valid(tmp_path):
    cp, ap = _write(tmp_path)
    assert run_smoke(cp, ap, NOW) == 0


def test_run_smoke_nonzero_on_bad_config(tmp_path):
    cp, ap = _write(tmp_path)
    cp.write_text("{bad json", encoding="utf-8")
    assert run_smoke(cp, ap, NOW) != 0
