import drivers.deploy_actions as da


def test_build_secret_commands_for_existing_gate_files(tmp_path):
    (tmp_path / ".scrape-authorization.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".scrape-warmup.json").write_text("{}", encoding="utf-8")
    steps = da.build_secret_commands(tmp_path)
    assert [s["secret"] for s in steps] == ["SCRAPE_AUTHORIZATION", "SCRAPE_WARMUP"]
    for s in steps:
        assert s["argv"][:3] == ["gh", "secret", "set"]
        assert s["argv"][-1] == s["secret"]
        assert s["stdin_file"].exists()
        # the secret value must NOT appear on argv (it comes from stdin_file)
        assert "{}" not in s["argv"]


def test_build_secret_commands_skips_absent_files(tmp_path):
    (tmp_path / ".scrape-authorization.json").write_text("{}", encoding="utf-8")
    steps = da.build_secret_commands(tmp_path)   # warmup file absent
    assert [s["secret"] for s in steps] == ["SCRAPE_AUTHORIZATION"]


def test_build_secret_commands_includes_session_when_present(tmp_path):
    (tmp_path / ".scrape-authorization.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".scrape-warmup.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".scrape-session.json").write_text('{"cookies":[]}', encoding="utf-8")
    steps = da.build_secret_commands(tmp_path)
    names = [s["secret"] for s in steps]
    assert "SCRAPE_STORAGE_STATE" in names
    sess = next(s for s in steps if s["secret"] == "SCRAPE_STORAGE_STATE")
    assert sess["stdin_file"].name == ".scrape-session.json"
    assert '{"cookies":[]}' not in sess["argv"]  # secret value never on argv
