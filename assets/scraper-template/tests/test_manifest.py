import json

from jemscrape.manifest import Manifest


def test_records_and_summary():
    m = Manifest()
    m.record_scraped("https://x/1", {"sku": "A1"})
    m.record_skipped("https://x/2", "no sku")
    m.record_error("https://x/3", "timeout")
    s = m.summary()
    assert s == {"scraped": 1, "skipped": 1, "errors": 1}


def test_write_includes_schema_version(tmp_path):
    m = Manifest(schema_version="1.0")
    m.record_scraped("https://x/1", {"sku": "A1"})
    out = tmp_path / "manifest.json"
    m.write(out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0"
    assert data["counts"]["scraped"] == 1
    assert data["scraped"][0]["url"] == "https://x/1"
