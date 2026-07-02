# tests/test_browser.py
import pytest

from jemscrape.browser import RenderedResult, make_browser_fetcher, make_browser_probe
from jemscrape.fetch import Probe
from jemscrape.errors import FetchError


def test_make_browser_fetcher_returns_rendered_html():
    def fake_render(url):
        return RenderedResult(status=200, html="<h1>Rendered</h1>", final_url=url)
    fetcher = make_browser_fetcher(fake_render)
    assert fetcher("https://x/p") == "<h1>Rendered</h1>"


def test_make_browser_fetcher_wraps_failure_in_fetcherror():
    def boom(url):
        raise RuntimeError("browser crashed")
    fetcher = make_browser_fetcher(boom)
    with pytest.raises(FetchError):
        fetcher("https://x/p")


def test_make_browser_probe_builds_probe_from_rendered_result():
    def fake_render(url):
        return RenderedResult(status=200, html="<html>ok</html>", final_url="https://x/final")
    probe_fn = make_browser_probe(fake_render)
    p = probe_fn("https://x/p")
    assert isinstance(p, Probe)
    assert p.status == 200
    assert p.body == "<html>ok</html>"
    assert p.final_url == "https://x/final"
    assert p.headers == {}


def test_make_browser_probe_wraps_failure_in_fetcherror():
    def boom(url):
        raise TimeoutError("nav timeout")
    probe_fn = make_browser_probe(boom)
    with pytest.raises(FetchError):
        probe_fn("https://x/p")
