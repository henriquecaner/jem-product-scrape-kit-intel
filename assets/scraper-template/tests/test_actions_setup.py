import json

import actions_setup


def test_actions_setup_materializes_both_gate_files(tmp_path):
    a = tmp_path / ".scrape-authorization.json"
    w = tmp_path / ".scrape-warmup.json"
    env = {"SCRAPE_AUTHORIZATION": json.dumps({"target_domain": "x.com"}),
           "SCRAPE_WARMUP": json.dumps({"verdict": "green"})}
    rc = actions_setup.main(env=env, targets=[("SCRAPE_AUTHORIZATION", a), ("SCRAPE_WARMUP", w)])
    assert rc == 0
    assert json.loads(a.read_text(encoding="utf-8"))["target_domain"] == "x.com"
    assert json.loads(w.read_text(encoding="utf-8"))["verdict"] == "green"


def test_actions_setup_missing_secret_returns_2(tmp_path, capsys):
    a = tmp_path / ".scrape-authorization.json"
    w = tmp_path / ".scrape-warmup.json"
    rc = actions_setup.main(env={"SCRAPE_AUTHORIZATION": "{}"},  # SCRAPE_WARMUP missing
                            targets=[("SCRAPE_AUTHORIZATION", a), ("SCRAPE_WARMUP", w)])
    assert rc == 2
    assert "BLOCKED" in capsys.readouterr().err


def test_session_secret_required_when_auth_required(tmp_path):
    a = tmp_path / ".scrape-authorization.json"
    w = tmp_path / ".scrape-warmup.json"
    s = tmp_path / ".scrape-session.json"
    targets = [("SCRAPE_AUTHORIZATION", a), ("SCRAPE_WARMUP", w),
               ("SCRAPE_STORAGE_STATE", s)]
    # auth_required path: session secret missing -> fail-closed
    rc = actions_setup.main(env={"SCRAPE_AUTHORIZATION": "{}", "SCRAPE_WARMUP": "{}"},
                            targets=targets)
    assert rc == 2


def test_target_builder_appends_session_when_auth_required(tmp_path):
    cfg = {"auth_required": True}
    targets = actions_setup.build_targets(cfg, base=tmp_path)
    names = [t[0] for t in targets]
    assert "SCRAPE_STORAGE_STATE" in names


def test_target_builder_omits_session_when_public(tmp_path):
    targets = actions_setup.build_targets({"auth_required": False}, base=tmp_path)
    names = [t[0] for t in targets]
    assert "SCRAPE_STORAGE_STATE" not in names
