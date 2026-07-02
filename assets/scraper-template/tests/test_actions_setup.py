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
