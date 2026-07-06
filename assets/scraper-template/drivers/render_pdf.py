"""Run-plan PDF driver (spec §12). Discovers Chrome via Playwright and prints
the run-plan HTML to PDF. If Chrome isn't available, falls back to writing the
HTML only — an approval step never blocks on missing software. Playwright is a
guarded optional dependency; this module lives in drivers/, never in the core."""
import sys
from pathlib import Path

from jemscrape.md_to_html import md_to_html

try:
    from playwright.sync_api import sync_playwright
    _AVAILABLE = True
except ImportError:
    sync_playwright = None
    _AVAILABLE = False


def _chrome_available():
    """True when Playwright + a launchable Chromium are present."""
    if not _AVAILABLE:
        return False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception:
        return False


def render_pdf(markdown_path, out_dir):
    """Render the run-plan markdown to HTML (always) and PDF (if Chrome is
    available). Returns {"html": path, "pdf": path|None}. Never raises on a
    missing Chrome — writes HTML and returns pdf=None."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    markdown = Path(markdown_path).read_text(encoding="utf-8")
    html = md_to_html(markdown)
    html_path = out / "run-plan.html"
    html_path.write_text(html, encoding="utf-8")

    if not _chrome_available():
        return {"html": str(html_path), "pdf": None}

    pdf_path = out / "run-plan.pdf"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_content(html, wait_until="load")
                page.pdf(path=str(pdf_path), format="A4", print_background=True)
            finally:
                browser.close()
    except Exception as exc:
        print(f"[render_pdf] PDF render failed, falling back to HTML: {exc}",
              file=sys.stderr)
        return {"html": str(html_path), "pdf": None}
    return {"html": str(html_path), "pdf": str(pdf_path)}
