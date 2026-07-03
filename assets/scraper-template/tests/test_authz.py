import json
from datetime import datetime, timezone

import pytest

import jemscrape.authz as authz_mod
from jemscrape.authz import Authorization, load_authorization, validate
from jemscrape.errors import AuthorizationError

NOW = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)


def _auth(**over):
    base = dict(
        target_domain="example.com",
        authorization_type="public_competitor",
        approver="henrique",
        approved_at="2026-07-01T09:00:00+00:00",
        expires_at="2026-07-08T09:00:00+00:00",
        rate_limit_floor_seconds=2.5,
        robots_status="allowed",
        robots_override_ref=None,
        requires_approval=False,
        scope="catalog",
    )
    base.update(over)
    return Authorization(**base)


def test_valid_authorization_passes():
    validate(_auth(), "https://example.com/p/1", NOW)


def test_domain_mismatch_rejected():
    with pytest.raises(AuthorizationError):
        validate(_auth(), "https://other.com/p/1", NOW)


def test_expired_rejected():
    with pytest.raises(AuthorizationError):
        validate(_auth(expires_at="2026-06-30T09:00:00+00:00"), "https://example.com/", NOW)


def test_public_competitor_disallowed_is_hard_block():
    with pytest.raises(AuthorizationError):
        validate(_auth(robots_status="disallowed"), "https://example.com/", NOW)


def test_partner_disallowed_without_override_rejected():
    with pytest.raises(AuthorizationError):
        validate(
            _auth(authorization_type="contracted_partner", robots_status="disallowed"),
            "https://example.com/",
            NOW,
        )


def test_partner_disallowed_with_override_ok():
    validate(
        _auth(
            authorization_type="contracted_partner",
            robots_status="disallowed",
            robots_override_ref="MSA-2026-014",
        ),
        "https://example.com/",
        NOW,
    )


def test_own_account_disallowed_ok():
    validate(_auth(authorization_type="own_account", robots_status="disallowed"),
             "https://example.com/", NOW)


def test_naive_expires_at_rejected_not_typeerror():
    with pytest.raises(AuthorizationError):
        validate(
            _auth(expires_at="2026-07-08T09:00:00"),
            "https://example.com/",
            NOW,
        )


def test_partner_disallowed_with_whitespace_override_rejected():
    with pytest.raises(AuthorizationError):
        validate(
            _auth(
                authorization_type="contracted_partner",
                robots_status="disallowed",
                robots_override_ref="   ",
            ),
            "https://example.com/",
            NOW,
        )


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(AuthorizationError):
        load_authorization(tmp_path / "nope.json")


def test_load_reads_record(tmp_path):
    p = tmp_path / ".scrape-authorization.json"
    p.write_text(json.dumps(_auth().__dict__), encoding="utf-8")
    auth = load_authorization(p)
    assert auth.target_domain == "example.com"


def test_load_non_utf8_file_raises_authorization_error(tmp_path):
    p = tmp_path / ".scrape-authorization.json"
    p.write_bytes(b"\xff\xfe not utf8")
    with pytest.raises(AuthorizationError):
        load_authorization(p)


def test_load_non_object_json_raises_authorization_error(tmp_path):
    p = tmp_path / ".scrape-authorization.json"
    p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(AuthorizationError):
        load_authorization(p)


def test_unhashable_authorization_type_raises_domain_error():
    # A JSON list value for authorization_type must not leak a raw
    # TypeError ("unhashable type") out of `not in VALID_TYPES` -- it must
    # fail closed with the domain error like any other invalid value.
    with pytest.raises(AuthorizationError):
        validate(_auth(authorization_type=["x"]), "https://example.com/", NOW)


def test_expires_at_with_z_suffix_accepted():
    # Python 3.11+ already accepts a trailing "Z" in fromisoformat, which
    # would mask a regression on the 3.9/3.10 floor this template targets.
    # This is a straightforward regression check on top of the mechanism
    # test below.
    validate(_auth(expires_at="2026-07-08T09:00:00Z"), "https://example.com/", NOW)


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

    monkeypatch.setattr(authz_mod, "datetime", NoNativeZSupport)
    validate(_auth(expires_at="2026-07-08T09:00:00Z"), "https://example.com/", NOW)
