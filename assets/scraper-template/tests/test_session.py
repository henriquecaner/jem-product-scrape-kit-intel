import json
from datetime import datetime, timezone

import pytest

from jemscrape.errors import SessionError, AuthExpiredError
from jemscrape import session as sess


def test_session_and_auth_exceptions_exist_and_are_exceptions():
    assert issubclass(SessionError, Exception)
    assert issubclass(AuthExpiredError, Exception)


def _storage_state(expires):
    return {
        "cookies": [
            {"name": "sid", "value": "abc", "domain": "shop.example.com",
             "path": "/", "expires": expires, "httpOnly": True, "secure": True,
             "sameSite": "Lax"},
            {"name": "csrf", "value": "xyz", "domain": ".example.com",
             "path": "/", "expires": -1, "httpOnly": False, "secure": True,
             "sameSite": "Strict"},
        ],
        "origins": [{"origin": "https://shop.example.com",
                     "localStorage": [{"name": "k", "value": "v"}]}],
    }


def _write(tmp_path, obj):
    p = tmp_path / ".scrape-session.json"
    p.write_text(json.dumps(obj), encoding="utf-8")
    return p


FUTURE = 4102444800  # 2100-01-01 UTC
PAST = 1000000000    # 2001-09-09 UTC


def test_load_missing_file_raises_session_error(tmp_path):
    with pytest.raises(sess.SessionError):
        sess.load_session(tmp_path / "nope.json")


def test_load_malformed_json_raises_session_error(tmp_path):
    p = tmp_path / ".scrape-session.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(sess.SessionError):
        sess.load_session(p)


def test_load_no_cookies_raises_session_error(tmp_path):
    p = _write(tmp_path, {"cookies": [], "origins": []})
    with pytest.raises(sess.SessionError):
        sess.load_session(p)


def test_cookie_header_matches_domain_and_skips_expired(tmp_path):
    s = sess.load_session(_write(tmp_path, _storage_state(FUTURE)))
    header = s.cookie_header("shop.example.com")
    # both cookies apply to shop.example.com (exact + dot-suffix), unexpired
    assert header == "sid=abc; csrf=xyz"


def test_cookie_header_expired_cookie_dropped(tmp_path):
    s = sess.load_session(_write(tmp_path, _storage_state(PAST)))
    header = s.cookie_header("shop.example.com")
    # sid expired in the past -> only the session cookie csrf remains
    assert header == "csrf=xyz"


def test_cookie_header_unrelated_domain_returns_empty(tmp_path):
    s = sess.load_session(_write(tmp_path, _storage_state(FUTURE)))
    assert s.cookie_header("other.test") == ""


def test_storage_state_is_raw_dict(tmp_path):
    obj = _storage_state(FUTURE)
    s = sess.load_session(_write(tmp_path, obj))
    assert s.storage_state == obj


def test_expires_at_is_earliest_non_session_cookie(tmp_path):
    s = sess.load_session(_write(tmp_path, _storage_state(FUTURE)))
    assert s.expires_at() == datetime.fromtimestamp(FUTURE, tz=timezone.utc)


def test_expires_at_none_when_all_session_cookies(tmp_path):
    obj = {"cookies": [{"name": "a", "value": "b", "domain": "x.com",
                        "path": "/", "expires": -1}], "origins": []}
    s = sess.load_session(_write(tmp_path, obj))
    assert s.expires_at() is None


def test_is_expired_true_for_past(tmp_path):
    s = sess.load_session(_write(tmp_path, _storage_state(PAST)))
    now = datetime.now(timezone.utc)
    assert s.is_expired(now) is True


def test_is_expired_false_when_no_expiry(tmp_path):
    obj = {"cookies": [{"name": "a", "value": "b", "domain": "x.com",
                        "path": "/", "expires": -1}], "origins": []}
    s = sess.load_session(_write(tmp_path, obj))
    assert s.is_expired(datetime.now(timezone.utc)) is False


def test_bare_domain_cookie_does_not_match_subdomain(tmp_path):
    # A host-only cookie for shop.example.com must NOT be sent to a narrower/other host.
    obj = {"cookies": [{"name": "sid", "value": "abc", "domain": "example.com",
                        "path": "/", "expires": -1}], "origins": []}
    s = sess.load_session(_write(tmp_path, obj))
    assert s.cookie_header("shop.example.com") == ""   # bare domain != subdomain
    assert s.cookie_header("example.com") == "sid=abc"  # exact host matches


def test_dot_domain_cookie_matches_subdomain(tmp_path):
    obj = {"cookies": [{"name": "csrf", "value": "xyz", "domain": ".example.com",
                        "path": "/", "expires": -1}], "origins": []}
    s = sess.load_session(_write(tmp_path, obj))
    assert s.cookie_header("shop.example.com") == "csrf=xyz"  # dot domain -> subdomain
    assert s.cookie_header("example.com") == "csrf=xyz"       # and the apex


def test_cookie_header_accepts_injected_clock(tmp_path):
    from datetime import datetime, timezone
    s = sess.load_session(_write(tmp_path, _storage_state(FUTURE)))
    # A clock after the FUTURE expiry drops the sid cookie; only the session cookie remains.
    later = datetime.fromtimestamp(FUTURE + 1, tz=timezone.utc)
    assert s.cookie_header("shop.example.com", now=later) == "csrf=xyz"
