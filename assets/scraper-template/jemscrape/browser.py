"""Pure browser-render adapters (spec §5.2). Convert a render_fn(url) ->
RenderedResult into the engine's existing fetcher/probe contracts. Stdlib only —
the actual Playwright driver lives in drivers/playwright_render.py."""
from dataclasses import dataclass

from .fetch import Probe
from .errors import FetchError, AuthExpiredError


@dataclass
class RenderedResult:
    status: int
    html: str
    final_url: str


def make_browser_fetcher(render_fn):
    """Return fetcher(url) -> html backed by render_fn(url) -> RenderedResult."""
    def fetcher(url):
        try:
            result = render_fn(url)
        except Exception as exc:
            raise FetchError(f"browser render failed for {url}: {exc}") from exc
        if result.status in (401, 403):
            # Match the HTTP path: a dead token aborts the run (runner propagates
            # AuthExpiredError), rather than caching a login page as if it were product HTML.
            raise AuthExpiredError(
                f"auth failed ({result.status}) rendering {url}: session token expired")
        return result.html
    return fetcher


def make_browser_probe(render_fn):
    """Return probe_fn(url) -> Probe backed by render_fn(url) -> RenderedResult."""
    def probe_fn(url):
        try:
            result = render_fn(url)
        except Exception as exc:
            raise FetchError(f"browser render failed for {url}: {exc}") from exc
        return Probe(status=result.status, headers={}, body=result.html,
                     final_url=result.final_url)
    return probe_fn
