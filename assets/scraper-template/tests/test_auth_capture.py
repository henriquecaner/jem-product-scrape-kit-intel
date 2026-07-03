import inspect
from pathlib import Path

import pytest


def test_driver_guard_raises_actionable_error_without_playwright(monkeypatch):
    import drivers.auth_capture as ac
    monkeypatch.setattr(ac, "_AVAILABLE", False)
    with pytest.raises(RuntimeError) as ei:
        ac.capture_session("https://x/login", "/tmp/out.json")
    assert "playwright" in str(ei.value).lower()


def test_driver_signature():
    import drivers.auth_capture as ac
    sig = inspect.signature(ac.capture_session)
    for name in ("login_url", "out_path", "proxy", "user_agent", "wait_fn"):
        assert name in sig.parameters


def test_cli_requires_login_url(tmp_path, capsys):
    import auth_capture
    import json
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"target_domain": "x.com", "runtime": "local",
                               "user_agent": "UA", "rate_limit_floor_seconds": 2.5,
                               "auth_required": True}), encoding="utf-8")
    # login_url missing -> validate_config rejects -> CLI returns 2
    rc = auth_capture.main(["--config", str(cfg), "--out", str(tmp_path / "s.json")])
    assert rc == 2
    assert "login_url" in capsys.readouterr().err


def test_cli_requires_login_url_when_auth_not_required(tmp_path, capsys):
    # auth_required absent -> validate_config does not require login_url, so it
    # passes the gate; main()'s own `if not login_url` branch must still catch it.
    import auth_capture
    import json
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"target_domain": "x.com", "runtime": "local",
                               "user_agent": "UA", "rate_limit_floor_seconds": 2.5}),
                   encoding="utf-8")
    rc = auth_capture.main(["--config", str(cfg), "--out", str(tmp_path / "s.json")])
    assert rc == 2
    assert "login_url" in capsys.readouterr().err


def test_cli_writes_session_with_0600_perms(tmp_path, capsys, monkeypatch):
    # Live auth cookies -> the saved session file must be 0600 (spec §4.6, §9),
    # regardless of the process umask. capture_session itself needs Playwright,
    # which is not guaranteed present, so fake the lazy import target the CLI
    # actually uses: drivers.auth_capture.capture_session.
    import json
    import drivers.auth_capture as driver_module

    out_path = tmp_path / "s.json"

    def fake_capture_session(login_url, out, *, proxy=None, user_agent=None, wait_fn=None):
        dummy = {"cookies": [{"name": "a", "value": "b", "domain": "x.com", "expires": -1}],
                 "origins": []}
        Path(out).write_text(json.dumps(dummy), encoding="utf-8")
        return Path(out)

    monkeypatch.setattr(driver_module, "capture_session", fake_capture_session)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)

    import auth_capture
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"target_domain": "x.com", "runtime": "local",
                               "user_agent": "UA", "rate_limit_floor_seconds": 2.5,
                               "auth_required": True, "login_url": "https://x.com/login"}),
                   encoding="utf-8")

    rc = auth_capture.main(["--config", str(cfg), "--out", str(out_path)])
    assert rc == 0
    assert oct(out_path.stat().st_mode & 0o777) == "0o600"


def test_cli_handles_generic_exception_from_capture_session(tmp_path, capsys, monkeypatch):
    # A Playwright timeout / user-closed-browser is not a RuntimeError; main()
    # must still catch it and return an actionable BLOCKED message, not a
    # traceback.
    import json
    import drivers.auth_capture as driver_module

    def fake_capture_session(login_url, out, *, proxy=None, user_agent=None, wait_fn=None):
        raise Exception("boom")

    monkeypatch.setattr(driver_module, "capture_session", fake_capture_session)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)

    import auth_capture
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"target_domain": "x.com", "runtime": "local",
                               "user_agent": "UA", "rate_limit_floor_seconds": 2.5,
                               "auth_required": True, "login_url": "https://x.com/login"}),
                   encoding="utf-8")

    rc = auth_capture.main(["--config", str(cfg), "--out", str(tmp_path / "s.json")])
    assert rc == 2
    assert "boom" in capsys.readouterr().err
