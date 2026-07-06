import json
from datetime import datetime, timezone

import pytest

import scrape
from jemscrape.errors import SessionError

FUTURE = 4102444800
PAST = 1000000000


def _session_file(tmp_path, expires):
    p = tmp_path / ".scrape-session.json"
    p.write_text(json.dumps({"cookies": [
        {"name": "sid", "value": "abc", "domain": "x.com",
         "path": "/", "expires": expires}], "origins": []}), encoding="utf-8")
    return p


def test_no_session_when_auth_not_required(tmp_path):
    got = scrape.load_run_session({"auth_required": False},
                                  tmp_path / "nope.json", datetime.now(timezone.utc))
    assert got is None


def test_auth_required_missing_session_raises(tmp_path):
    with pytest.raises(SessionError):
        scrape.load_run_session({"auth_required": True, "target_domain": "x.com"},
                                tmp_path / "nope.json", datetime.now(timezone.utc))


def test_auth_required_expired_session_raises(tmp_path):
    p = _session_file(tmp_path, PAST)
    with pytest.raises(SessionError):
        scrape.load_run_session({"auth_required": True, "target_domain": "x.com"},
                                p, datetime.now(timezone.utc))


def test_auth_required_valid_session_returned(tmp_path):
    p = _session_file(tmp_path, FUTURE)
    s = scrape.load_run_session({"auth_required": True, "target_domain": "x.com"},
                                p, datetime.now(timezone.utc))
    assert s.cookie_header("x.com") == "sid=abc"


def test_flush_outputs_writes_manifest_and_records(tmp_path, monkeypatch):
    # Regression for the AuthExpired abort silently dropping already-scraped
    # records: flush_outputs must write both the manifest and raw_records.json
    # from whatever the manifest holds at call time, independent of how main()
    # got there (clean finish or a mid-run AuthExpiredError).
    monkeypatch.setattr(scrape, "HERE", tmp_path)
    from jemscrape.manifest import Manifest

    manifest = Manifest()
    manifest.record_scraped("https://x/1", {"sku": "A1"})
    cache_dir = tmp_path / "data"

    records_path = scrape.flush_outputs(manifest, cache_dir)

    manifest_path = tmp_path / "exports" / "scrape_manifest.json"
    assert manifest_path.exists()
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_data["counts"]["scraped"] == 1

    assert records_path == tmp_path / "state" / "raw_records.json"
    records = json.loads(records_path.read_text(encoding="utf-8"))
    assert len(records) == 1
    assert records[0]["url"] == "https://x/1"
    assert records[0]["raw"] == {"sku": "A1"}
