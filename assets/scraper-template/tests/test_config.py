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
