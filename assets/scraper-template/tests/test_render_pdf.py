import importlib


def test_fallback_writes_html_when_no_chrome(tmp_path, monkeypatch):
    render_pdf = importlib.import_module("drivers.render_pdf")
    monkeypatch.setattr(render_pdf, "_chrome_available", lambda: False)
    md = tmp_path / "run-plan.md"
    md.write_text("# Run Plan\n\n- item", encoding="utf-8")
    result = render_pdf.render_pdf(str(md), str(tmp_path))
    assert result["pdf"] is None
    assert (tmp_path / "run-plan.html").exists()
    assert "<h1>Run Plan</h1>" in (tmp_path / "run-plan.html").read_text(encoding="utf-8")


def test_pdf_render_when_chrome_present(tmp_path):
    import pytest
    pytest.importorskip("playwright")
    render_pdf = importlib.import_module("drivers.render_pdf")
    if not render_pdf._chrome_available():
        pytest.skip("chromium not installed")
    md = tmp_path / "run-plan.md"
    md.write_text("# Run Plan", encoding="utf-8")
    result = render_pdf.render_pdf(str(md), str(tmp_path))
    assert result["pdf"] is not None
    assert (tmp_path / "run-plan.pdf").exists()
