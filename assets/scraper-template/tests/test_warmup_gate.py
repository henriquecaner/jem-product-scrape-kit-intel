import json
from datetime import datetime, timezone, timedelta

import pytest

import jemscrape.warmup_gate as warmup_gate_mod
from jemscrape.warmup_gate import load_warmup_verdict, validate_warmup, WarmupVerdict
from jemscrape.errors import WarmupError

NOW = datetime(2026, 7, 2, 12, 0, tzinfo=timezone.utc)


def _verdict(verdict="green", domain="example.com", expires=None):
    return WarmupVerdict(
        target_domain=domain, verdict=verdict,
        generated_at=NOW.isoformat(),
        expires_at=(expires or (NOW + timedelta(days=1))).isoformat(),
        report_sha256="abc", reviewer="opus-4.8", advisor="sonnet-5")


def test_validate_warmup_green_passes():
    validate_warmup(_verdict(), "https://example.com/", NOW)   # no raise


def test_validate_warmup_not_green_blocks():
    with pytest.raises(WarmupError):
        validate_warmup(_verdict(verdict="adjust"), "https://example.com/", NOW)


def test_validate_warmup_expired_blocks():
    with pytest.raises(WarmupError):
        validate_warmup(_verdict(expires=NOW - timedelta(hours=1)), "https://example.com/", NOW)


def test_validate_warmup_domain_mismatch_blocks():
    with pytest.raises(WarmupError):
        validate_warmup(_verdict(domain="other.com"), "https://example.com/", NOW)


def test_validate_warmup_naive_expiry_blocks():
    v = _verdict()
    v.expires_at = "2026-07-03T12:00:00"   # no tz offset
    with pytest.raises(WarmupError):
        validate_warmup(v, "https://example.com/", NOW)


def test_unhashable_verdict_raises_domain_error():
    # A JSON list value for verdict must not leak a raw TypeError
    # ("unhashable type") out of `not in VALID_VERDICTS` -- it must fail
    # closed with the domain error like any other invalid value.
    with pytest.raises(WarmupError):
        validate_warmup(_verdict(verdict=["green"]), "https://example.com/", NOW)


def test_expires_at_with_z_suffix_accepted():
    # Python 3.11+ already accepts a trailing "Z" in fromisoformat, which
    # would mask a regression on the 3.9/3.10 floor this template targets.
    # This is a straightforward regression check on top of the mechanism
    # test below.
    v = _verdict()
    v.expires_at = "2026-07-08T09:00:00Z"
    validate_warmup(v, "https://example.com/", NOW)


def test_expires_at_with_z_suffix_accepted_on_pre_311_fromisoformat(monkeypatch):
    # Simulate Python <3.11, where datetime.fromisoformat rejects a trailing
    # "Z" -- the CI matrix runs 3.14 (which accepts it natively), so without
    # this simulation the bug never shows up locally. _parse_dt must
    # normalize "Z" to "+00:00" itself before calling fromisoformat.
    class NoNativeZSupport:
        @staticmethod
        def fromisoformat(value):
            if isinstance(value, str) and value.endswith("Z"):
                raise ValueError("simulated pre-3.11: no Z support")
            return datetime.fromisoformat(value)

    monkeypatch.setattr(warmup_gate_mod, "datetime", NoNativeZSupport)
    v = _verdict()
    v.expires_at = "2026-07-08T09:00:00Z"
    validate_warmup(v, "https://example.com/", NOW)


def test_load_warmup_verdict_missing_file_raises(tmp_path):
    with pytest.raises(WarmupError):
        load_warmup_verdict(tmp_path / "nope.json")


def test_load_warmup_verdict_roundtrip(tmp_path):
    p = tmp_path / ".scrape-warmup.json"
    p.write_text(json.dumps({
        "target_domain": "example.com", "verdict": "green",
        "generated_at": NOW.isoformat(), "expires_at": (NOW + timedelta(days=1)).isoformat(),
        "report_sha256": "abc", "reviewer": "opus-4.8", "advisor": "sonnet-5"}), encoding="utf-8")
    v = load_warmup_verdict(p)
    validate_warmup(v, "https://example.com/", NOW)   # no raise


import scrape


def test_scrape_require_warmup_missing_blocks(tmp_path):
    with pytest.raises(WarmupError):
        scrape.require_warmup(tmp_path / ".scrape-warmup.json", "https://example.com/", NOW)


def test_scrape_require_warmup_green_passes(tmp_path):
    p = tmp_path / ".scrape-warmup.json"
    p.write_text(json.dumps({
        "target_domain": "example.com", "verdict": "green",
        "generated_at": NOW.isoformat(), "expires_at": (NOW + timedelta(days=1)).isoformat(),
        "report_sha256": "abc", "reviewer": "opus-4.8", "advisor": "sonnet-5"}), encoding="utf-8")
    scrape.require_warmup(p, "https://example.com/", NOW)   # no raise
