"""Local session capture (spec §5.1 rule 1). Launches HEADED Chromium so the
user logs in manually (with the country proxy on launch when geo applies), then
saves context.storage_state to a file. Playwright-only, guarded — kept out of
the stdlib core and the stdlib test suite, like playwright_render.py."""
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
    _AVAILABLE = True
except ImportError:
    sync_playwright = None
    _AVAILABLE = False

_INSTALL_HINT = (
    "Playwright is not installed — required to capture an authenticated session. "
    "Ask IT to install it: pip install playwright && playwright install chromium"
)


def _default_wait():
    input("\n>>> Log in in the opened browser window, then press Enter here to save the session... ")


def capture_session(login_url, out_path, *, proxy=None, user_agent=None, wait_fn=None):
    """Open login_url in headed Chromium, wait for the user to log in, save the
    session to out_path (Playwright storage_state JSON). Returns the Path."""
    if not _AVAILABLE:
        raise RuntimeError(_INSTALL_HINT)
    wait_fn = _default_wait if wait_fn is None else wait_fn
    out_path = Path(out_path)
    launch_kwargs = {}
    if proxy:
        launch_kwargs["proxy"] = proxy
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, **launch_kwargs)
        try:
            context = browser.new_context(user_agent=user_agent) if user_agent else browser.new_context()
            page = context.new_page()
            page.goto(login_url)
            wait_fn()
            context.storage_state(path=str(out_path))
        finally:
            browser.close()
    return out_path
