from jemscrape.cache import atomic_write, slug_for, cache_path, is_cached, read_cached, Cursor


def test_atomic_write_and_read(tmp_path):
    p = tmp_path / "sub" / "file.txt"
    atomic_write(p, "hello")
    assert p.read_text(encoding="utf-8") == "hello"
    # no leftover temp files
    assert list(p.parent.glob("*.tmp")) == []


def test_slug_is_filesystem_safe():
    slug = slug_for("https://example.com/a/b/c-fire%20extinguisher?x=1")
    assert "/" not in slug and "?" not in slug and " " not in slug
    assert slug


def test_cache_roundtrip(tmp_path):
    url = "https://example.com/p/widget-1"
    assert not is_cached(tmp_path, url)
    atomic_write(cache_path(tmp_path, url), "<html>1</html>")
    assert is_cached(tmp_path, url)
    assert read_cached(tmp_path, url) == "<html>1</html>"


def test_cursor_persists_and_reloads(tmp_path):
    cpath = tmp_path / "state" / "cursor.json"
    cur = Cursor(cpath)
    cur.load()
    assert not cur.done("https://x/1")
    cur.add("https://x/1")
    cur.save()

    reloaded = Cursor(cpath)
    reloaded.load()
    assert reloaded.done("https://x/1")
    assert not reloaded.done("https://x/2")
