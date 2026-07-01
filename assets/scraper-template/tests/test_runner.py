from jemscrape.runner import run
from jemscrape.pacing import Pacer
from jemscrape.cache import Cursor, is_cached
from jemscrape.manifest import Manifest


def _pacer():
    return Pacer(1, 1, 1, rng=lambda a, b: 1, randint=lambda a, b: 999, sleep=lambda s: None)


def _parse(html, url):
    return {"url": url, "len": len(html)} if "product" in html else None


def test_fetches_caches_and_parses(tmp_path):
    fetched = []

    def fetcher(url):
        fetched.append(url)
        return "product page"

    m = Manifest()
    summary = run(
        urls=["https://x/1", "https://x/2"],
        parse_fn=_parse, cache_dir=tmp_path / "data",
        fetcher=fetcher, pacer=_pacer(),
        cursor=Cursor(tmp_path / "state" / "cursor.json").load(), manifest=m,
    )
    assert summary == {"scraped": 2, "skipped": 0, "errors": 0}
    assert fetched == ["https://x/1", "https://x/2"]
    assert is_cached(tmp_path / "data", "https://x/1")


def test_resume_skips_done_urls(tmp_path):
    cur = Cursor(tmp_path / "state" / "cursor.json").load()
    cur.add("https://x/1")
    cur.save()

    fetched = []

    def fetcher(url):
        fetched.append(url)
        return "product page"

    run(urls=["https://x/1", "https://x/2"], parse_fn=_parse, cache_dir=tmp_path / "data",
        fetcher=fetcher, pacer=_pacer(), cursor=cur, manifest=Manifest())
    assert fetched == ["https://x/2"]  # x/1 was already done


def test_cached_url_not_refetched(tmp_path):
    from jemscrape.cache import atomic_write, cache_path
    atomic_write(cache_path(tmp_path / "data", "https://x/1"), "product cached")

    def fetcher(url):
        raise AssertionError("should not fetch a cached url")

    m = Manifest()
    run(urls=["https://x/1"], parse_fn=_parse, cache_dir=tmp_path / "data",
        fetcher=fetcher, pacer=_pacer(),
        cursor=Cursor(tmp_path / "state" / "cursor.json").load(), manifest=m)
    assert m.summary()["scraped"] == 1


def test_fetch_error_recorded_and_continues(tmp_path):
    def fetcher(url):
        if url.endswith("1"):
            raise RuntimeError("down")
        return "product page"

    m = Manifest()
    summary = run(urls=["https://x/1", "https://x/2"], parse_fn=_parse,
                  cache_dir=tmp_path / "data", fetcher=fetcher, pacer=_pacer(),
                  cursor=Cursor(tmp_path / "state" / "cursor.json").load(), manifest=m)
    assert summary == {"scraped": 1, "skipped": 0, "errors": 1}
