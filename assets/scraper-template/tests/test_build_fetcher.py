import scrape
from jemscrape.browser import RenderedResult


def test_build_fetcher_http_mode_uses_http_fetch():
    calls = {}

    def fake_http(url, *, user_agent):
        calls["ua"] = user_agent
        return "<h1>http</h1>"

    fetcher = scrape.build_fetcher({"user_agent": "UA"}, http_fetch=fake_http)
    assert fetcher("https://x/p") == "<h1>http</h1>"
    assert calls["ua"] == "UA"


def test_build_fetcher_browser_mode_uses_render_fn():
    def fake_render(url):
        return RenderedResult(status=200, html="<h1>rendered</h1>", final_url=url)

    def unused_http(url, *, user_agent):
        raise AssertionError("http_fetch must not be called in browser mode")

    fetcher = scrape.build_fetcher(
        {"user_agent": "UA", "fetch_mode": "browser"},
        http_fetch=unused_http, render_fn=fake_render)
    assert fetcher("https://x/p") == "<h1>rendered</h1>"
