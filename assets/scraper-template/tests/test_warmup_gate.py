import json
from datetime import datetime, timezone, timedelta

import pytest

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
