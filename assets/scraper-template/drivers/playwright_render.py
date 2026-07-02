"""Playwright render driver (spec §5.2, Plano 3a). The ONLY module that imports
Playwright — kept out of the stdlib jemscrape/ core and out of the stdlib test
suite. Guarded so its absence produces an actionable error, not an ImportError."""
from jemscrape.browser import RenderedResult

try:
    from playwright.sync_api import sync_playwright
    _AVAILABLE = True
except ImportError:
    sync_playwright = None
    _AVAILABLE = False

_INSTALL_HINT = (
    "Playwright is not installed — required for the browser render path "
    "(fetch_mode=browser / --render browser). Ask IT to install it: "
    "pip install playwright && playwright install chromium"
)


def render(url, *, timeout=30000, proxy=None, user_agent=None):
    """Render url in headless Chromium; return RenderedResult(status, html, final_url).
    timeout is in milliseconds. proxy is a Playwright proxy dict or None."""
    if not _AVAILABLE:
        raise RuntimeError(_INSTALL_HINT)
    launch_kwargs = {}
    if proxy:
        launch_kwargs["proxy"] = proxy
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, **launch_kwargs)
        try:
            # Browser mode now honors the configured user_agent (Plano 3a Fix A):
            # a context is created only when a UA override is supplied.
            if user_agent is not None:
                context = browser.new_context(user_agent=user_agent)
                page = context.new_page()
            else:
                page = browser.new_page()
            response = page.goto(url, wait_until="networkidle", timeout=timeout)
            status = response.status if response is not None else 0
            html = page.content()
            final_url = page.url
        finally:
            browser.close()
    return RenderedResult(status=status, html=html, final_url=final_url)
