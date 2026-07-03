from jemscrape.manifest import Manifest


def test_records_for_build_shapes_scraped_entries():
    m = Manifest()
    m.record_scraped("https://x/p1", {"product_id": "A1", "name": "Widget"})
    m.record_skipped("https://x/p2", "no record")
    m.record_error("https://x/p3", "boom")
    recs = m.records_for_build()
    assert len(recs) == 1  # only scraped entries, not skipped/errored
    assert recs[0]["url"] == "https://x/p1"
    assert recs[0]["raw"] == {"product_id": "A1", "name": "Widget"}
    assert recs[0]["raw_ref"] == ""  # no cache_dir given


def test_records_for_build_includes_cache_ref(tmp_path):
    m = Manifest()
    m.record_scraped("https://x/p1", {"name": "W"})
    recs = m.records_for_build(cache_dir=tmp_path)
    assert recs[0]["raw_ref"]                     # non-empty path
    assert str(tmp_path) in recs[0]["raw_ref"]    # points inside the cache dir


def test_records_for_build_matches_build_dataset_input_keys():
    # build_dataset reads item["url"], item["raw"], item.get("raw_ref", "")
    m = Manifest()
    m.record_scraped("https://x/p", {"product_id": "A1", "name": "W", "sku": "A1"})
    rec = m.records_for_build()[0]
    assert set(rec) == {"url", "raw", "raw_ref"}
