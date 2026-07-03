import json
import pytest

from jemscrape.config import load_config, validate_config
from jemscrape.errors import ConfigError


def _valid():
    return {
        "target_domain": "example.com",
        "runtime": "local",
        "rate_limit_floor_seconds": 2.5,
        "user_agent": "Mozilla/5.0 (compatible; JEMScrape/1.0)",
    }


def test_valid_config_passes():
    validate_config(_valid())  # no raise


def test_missing_required_field_lists_it():
    cfg = _valid()
    del cfg["target_domain"]
    with pytest.raises(ConfigError) as e:
        validate_config(cfg)
    assert "target_domain" in str(e.value)


def test_bad_runtime_rejected():
    cfg = _valid()
    cfg["runtime"] = "carrier-pigeon"
    with pytest.raises(ConfigError):
        validate_config(cfg)


def test_floor_must_be_positive():
    cfg = _valid()
    cfg["rate_limit_floor_seconds"] = 0
    with pytest.raises(ConfigError):
        validate_config(cfg)


def test_min_below_floor_rejected():
    cfg = _valid()
    cfg["min_delay_seconds"] = 1.0  # below the 2.5 floor
    cfg["max_delay_seconds"] = 5.0
    with pytest.raises(ConfigError):
        validate_config(cfg)


def test_load_config_reads_json(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps(_valid()), encoding="utf-8")
    cfg = load_config(p)
    assert cfg["target_domain"] == "example.com"


def test_load_config_bad_json_raises(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(p)


def test_non_string_runtime_rejected():
    cfg = _valid()
    cfg["runtime"] = ["local"]
    with pytest.raises(ConfigError):
        validate_config(cfg)


def test_non_utf8_file_raises_config_error(tmp_path):
    p = tmp_path / "config.json"
    p.write_bytes(b"\xff\xfe not utf8")
    with pytest.raises(ConfigError):
        load_config(p)


def _base():
    return {"target_domain": "x.com", "runtime": "local",
            "user_agent": "UA", "rate_limit_floor_seconds": 2.5}


def test_auth_required_must_be_bool():
    cfg = _base()
    cfg["auth_required"] = "yes"
    with pytest.raises(ConfigError):
        validate_config(cfg)


def test_auth_required_true_requires_login_url():
    cfg = _base()
    cfg["auth_required"] = True   # no login_url
    with pytest.raises(ConfigError):
        validate_config(cfg)


def test_auth_required_true_with_login_url_ok():
    cfg = _base()
    cfg["auth_required"] = True
    cfg["login_url"] = "https://x.com/login"
    validate_config(cfg)  # must not raise


def test_auth_required_absent_is_fine():
    validate_config(_base())  # unchanged public path


def test_band_priority_wrong_type_rejected():
    cfg = _base()
    cfg["band_priority"] = "PLE-J015"   # must be a list, not a bare string
    with pytest.raises(ConfigError):
        validate_config(cfg)


def test_hub_group_wrong_type_rejected():
    cfg = _base()
    cfg["hub_group"] = "hub"   # must be a list
    with pytest.raises(ConfigError):
        validate_config(cfg)


def test_ireland_branch_wrong_type_rejected():
    cfg = _base()
    cfg["ireland_branch"] = ["ie"]   # must be a str
    with pytest.raises(ConfigError):
        validate_config(cfg)


def test_band_priority_hub_group_ireland_branch_valid_types_ok():
    cfg = _base()
    cfg["band_priority"] = ["PLE-J015", "universal"]
    cfg["hub_group"] = ["hub", "hub-mirror"]
    cfg["ireland_branch"] = "ie"
    validate_config(cfg)  # must not raise
