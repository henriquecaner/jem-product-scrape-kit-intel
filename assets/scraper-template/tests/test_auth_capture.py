import inspect


def test_driver_guard_raises_actionable_error_without_playwright(monkeypatch):
    import drivers.auth_capture as ac
    if ac._AVAILABLE:
        import pytest
        pytest.skip("Playwright installed; guard path not exercised here")
    import pytest
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
