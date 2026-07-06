import importlib


class _ExplodingPlaywright:
    """Stub for sync_playwright() that raises on launch, simulating a
    transient Chrome launch/render failure after _chrome_available()
    already returned True."""

    def __enter__(self):
        raise RuntimeError("simulated transient Chrome launch failure")

    def __exit__(self, exc_type, exc, tb):
        return False


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


def test_transient_launch_failure_falls_back_to_html_without_raising(tmp_path, monkeypatch):
    """§12 invariant: approval step never blocks/crashes. If Chrome is
    reported available but the actual launch/render blows up, render_pdf
    must swallow the error and return the HTML-only fallback."""
    render_pdf = importlib.import_module("drivers.render_pdf")
    monkeypatch.setattr(render_pdf, "_chrome_available", lambda: True)
    monkeypatch.setattr(render_pdf, "sync_playwright", lambda: _ExplodingPlaywright())
    md = tmp_path / "run-plan.md"
    md.write_text("# Run Plan\n\n- item", encoding="utf-8")

    result = render_pdf.render_pdf(str(md), str(tmp_path))

    assert result["pdf"] is None
    assert (tmp_path / "run-plan.html").exists()
    assert result["html"] == str(tmp_path / "run-plan.html")


def test_render_run_plan_missing_markdown_exits_cleanly(tmp_path, capsys):
    """§12 invariant: a missing/unreadable markdown file must produce a
    clean stderr message and exit(2), never a traceback."""
    render_run_plan = importlib.import_module("render_run_plan")
    missing = tmp_path / "does-not-exist.md"

    exit_code = render_run_plan.main(["--markdown", str(missing), "--out", str(tmp_path)])

    assert exit_code == 2
    captured = capsys.readouterr()
    assert captured.err.strip() != ""
