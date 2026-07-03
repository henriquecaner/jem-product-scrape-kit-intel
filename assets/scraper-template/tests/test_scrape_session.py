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
