from jemscrape.records import merge_records


def test_union_by_url_new_wins_keeps_position():
    existing = [
        {"url": "https://x/1", "raw": {"name": "old1"}, "raw_ref": "a"},
        {"url": "https://x/2", "raw": {"name": "old2"}, "raw_ref": "b"},
    ]
    new = [
        {"url": "https://x/2", "raw": {"name": "new2"}, "raw_ref": "b2"},
        {"url": "https://x/3", "raw": {"name": "new3"}, "raw_ref": "c"},
    ]
    out = merge_records(existing, new)
    assert [r["url"] for r in out] == ["https://x/1", "https://x/2", "https://x/3"]
    assert out[1]["raw"]["name"] == "new2"      # new wins on collision
    assert out[1]["raw_ref"] == "b2"
    assert out[2]["raw"]["name"] == "new3"


def test_empty_inputs():
    assert merge_records([], []) == []
    assert merge_records([], [{"url": "u", "raw": {}, "raw_ref": ""}])[0]["url"] == "u"
    assert merge_records([{"url": "u", "raw": {}, "raw_ref": ""}], []) == [
        {"url": "u", "raw": {}, "raw_ref": ""}
    ]


def test_ignores_malformed_entries():
    out = merge_records([{"no_url": 1}, "junk"], [{"url": "u", "raw": {}, "raw_ref": ""}])
    assert [r["url"] for r in out] == ["u"]
