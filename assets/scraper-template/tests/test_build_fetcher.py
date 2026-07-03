import pytest

import scrape
from jemscrape.browser import RenderedResult
from jemscrape.errors import ConfigError
from jemscrape.session import Session


def test_build_fetcher_http_mode_uses_http_fetch():
    calls = {}

    def fake_http(url, *, user_agent, cookie_header=None):
        calls["ua"] = user_agent
        return "<h1>http</h1>"

    fetcher = scrape.build_fetcher({"user_agent": "UA"}, http_fetch=fake_http)
    assert fetcher("https://x/p") == "<h1>http</h1>"
    assert calls["ua"] == "UA"


def test_build_fetcher_browser_mode_uses_render_fn():
    def fake_render(url):
        return RenderedResult(status=200, html="<h1>rendered</h1>", final_url=url)

    def unused_http(url, *, user_agent, cookie_header=None):
        raise AssertionError("http_fetch must not be called in browser mode")

    fetcher = scrape.build_fetcher(
        {"user_agent": "UA", "fetch_mode": "browser"},
        http_fetch=unused_http, render_fn=fake_render)
    assert fetcher("https://x/p") == "<h1>rendered</h1>"


def test_http_mode_injects_cookie_header_from_session():
    seen = {}

    def fake_http(url, *, user_agent, cookie_header=None):
        seen["cookie"] = cookie_header
        return "<h1>ok</h1>"

    session = Session({"cookies": [
        {"name": "sid", "value": "abc", "domain": "x.com", "expires": -1}]})
    fetcher = scrape.build_fetcher(
        {"user_agent": "UA", "target_domain": "x.com"},
        http_fetch=fake_http, session=session)
    assert fetcher("https://x.com/p") == "<h1>ok</h1>"
    assert seen["cookie"] == "sid=abc"


def test_http_mode_without_session_sends_no_cookie():
    seen = {}

    def fake_http(url, *, user_agent, cookie_header=None):
        seen["cookie"] = cookie_header
        return "<h1>ok</h1>"

    fetcher = scrape.build_fetcher(
        {"user_agent": "UA", "target_domain": "x.com"}, http_fetch=fake_http)
    fetcher("https://x.com/p")
    assert seen["cookie"] is None


def test_browser_mode_render_fn_receives_storage_state():
    captured = {}

    def fake_render(url):
        captured["url"] = url
        return RenderedResult(status=200, html="<h1>r</h1>", final_url=url)

    session = Session({"cookies": [
        {"name": "sid", "value": "abc", "domain": "x.com", "expires": -1}],
        "origins": []})
    fetcher = scrape.build_fetcher(
        {"user_agent": "UA", "fetch_mode": "browser", "target_domain": "x.com"},
        http_fetch=lambda *a, **k: None, render_fn=fake_render, session=session)
    assert fetcher("https://x.com/p") == "<h1>r</h1>"


def test_build_fetcher_browser_mode_malformed_proxy_raises_configerror(monkeypatch):
    # A host-less HTTPS_PROXY (e.g. a broken Actions secret) must fail closed
    # with a clean ConfigError, not an uncaught traceback from urlsplit.
    monkeypatch.setenv("HTTPS_PROXY", "http://:8080")
    with pytest.raises(ConfigError):
        scrape.build_fetcher(
            {"user_agent": "UA", "fetch_mode": "browser", "target_domain": "x.com"},
            http_fetch=lambda *a, **k: None)
