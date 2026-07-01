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


def test_distinct_urls_sharing_tail_both_fetched(tmp_path):
    from jemscrape.cache import cache_path

    url_a = "https://x/A/widget-1"
    url_b = "https://x/B/widget-1"
    fetched = []

    def fetcher(url):
        fetched.append(url)
        return f"product page for {url}"

    m = Manifest()
    summary = run(
        urls=[url_a, url_b], parse_fn=_parse, cache_dir=tmp_path / "data",
        fetcher=fetcher, pacer=_pacer(),
        cursor=Cursor(tmp_path / "state" / "cursor.json").load(), manifest=m,
    )
    assert sorted(fetched) == sorted([url_a, url_b])
    assert summary["scraped"] == 2
    path_a = cache_path(tmp_path / "data", url_a)
    path_b = cache_path(tmp_path / "data", url_b)
    assert path_a != path_b
    assert path_a.read_text(encoding="utf-8") != path_b.read_text(encoding="utf-8")


def test_errored_url_not_retried_on_resume(tmp_path):
    def failing_fetcher(url):
        raise RuntimeError("down")

    m = Manifest()
    cur = Cursor(tmp_path / "state" / "cursor.json").load()
    summary = run(urls=["https://x/1"], parse_fn=_parse, cache_dir=tmp_path / "data",
                  fetcher=failing_fetcher, pacer=_pacer(), cursor=cur, manifest=m)
    assert summary["errors"] == 1
    assert cur.done("https://x/1")

    fetched = []

    def succeeding_fetcher(url):
        fetched.append(url)
        return "product page"

    run(urls=["https://x/1"], parse_fn=_parse, cache_dir=tmp_path / "data",
        fetcher=succeeding_fetcher, pacer=_pacer(), cursor=cur, manifest=Manifest())
    assert fetched == []  # errored URL is done; not retried on resume


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
