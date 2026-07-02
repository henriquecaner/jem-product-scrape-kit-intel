import pytest

from jemscrape.config import validate_config
from jemscrape.errors import ConfigError


def _base():
    return {"target_domain": "x.com", "runtime": "local",
            "user_agent": "UA", "rate_limit_floor_seconds": 5}


def test_fetch_mode_browser_ok():
    cfg = _base(); cfg["fetch_mode"] = "browser"
    validate_config(cfg)   # no raise


def test_fetch_mode_http_ok():
    cfg = _base(); cfg["fetch_mode"] = "http"
    validate_config(cfg)   # no raise


def test_fetch_mode_absent_ok():
    validate_config(_base())   # no raise


def test_fetch_mode_invalid_raises():
    cfg = _base(); cfg["fetch_mode"] = "spa"
    with pytest.raises(ConfigError):
        validate_config(cfg)
