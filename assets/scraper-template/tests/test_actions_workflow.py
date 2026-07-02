from pathlib import Path

WF_TEXT = (Path(__file__).resolve().parents[2] / "github-actions" / "scrape.yml").read_text(encoding="utf-8")


def test_workflow_has_manual_and_scheduled_triggers():
    assert "workflow_dispatch" in WF_TEXT
    assert "schedule" in WF_TEXT and "cron" in WF_TEXT


def test_workflow_order_materialize_then_gate_then_scrape():
    setup_i = WF_TEXT.index("actions_setup.py")
    gate_i = WF_TEXT.index("smoke_test.py")
    scrape_i = WF_TEXT.index("scrape.py --limit")
    assert setup_i < gate_i < scrape_i


def test_workflow_wires_gate_secrets():
    assert "SCRAPE_AUTHORIZATION" in WF_TEXT
    assert "SCRAPE_WARMUP" in WF_TEXT


def test_workflow_checkpoints_uploads_and_notifies():
    assert "git commit" in WF_TEXT
    assert "upload-artifact" in WF_TEXT
    assert "notify.py" in WF_TEXT
    assert "if: failure()" in WF_TEXT


def test_workflow_has_write_permission_for_checkpoint():
    assert "contents: write" in WF_TEXT


def test_workflow_surfaces_push_failures_instead_of_swallowing():
    assert "git push || echo" not in WF_TEXT
    assert "git pull --rebase" in WF_TEXT
