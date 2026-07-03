# tests/test_playwright_render.py
import pytest

import drivers.playwright_render as pr
from jemscrape.browser import RenderedResult


def test_render_raises_actionable_error_when_playwright_absent(monkeypatch):
    # Fail closed with a helpful message, never a bare ImportError/NameError.
    monkeypatch.setattr(pr, "_AVAILABLE", False)
    with pytest.raises(RuntimeError) as exc:
        pr.render("https://example.com/")
    assert "playwright install chromium" in str(exc.value)


def test_render_smoke_renders_inline_html():
    # Integration: only runs where Playwright + Chromium are actually installed.
    pytest.importorskip("playwright")
    try:
        result = pr.render("data:text/html,<h1>Hello Warmup</h1>", timeout=15000)
    except Exception as exc:  # playwright present but browser binary/launch unavailable
        pytest.skip(f"browser render unavailable: {exc}")
    assert isinstance(result, RenderedResult)
    assert "Hello Warmup" in result.html


def test_render_accepts_storage_state_kwarg():
    import inspect
    from drivers.playwright_render import render
    sig = inspect.signature(render)
    assert "storage_state" in sig.parameters
