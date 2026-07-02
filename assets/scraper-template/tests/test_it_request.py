from pathlib import Path

DOC = (Path(__file__).resolve().parents[2] / "it-request" / "README.md").read_text(encoding="utf-8")


def test_it_request_lists_toolchain():
    assert "Git.Git" in DOC and "GitHub.cli" in DOC and "Python.Python" in DOC
    assert "playwright" in DOC.lower()


def test_it_request_lists_org_provisioning():
    assert "proxy" in DOC.lower()
    assert "ANTHROPIC_API_KEY" in DOC
