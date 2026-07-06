from jemscrape.categories import extract_categories


def test_extract_distinct_with_counts_sorted():
    raws = [
        {"url": "1", "raw": {"breadcrumbs": ["A", "B"]}},
        {"url": "2", "raw": {"breadcrumbs": ["A", "B"]}},
        {"url": "3", "raw": {"breadcrumbs": ["C"]}},
        {"url": "4", "raw": {"breadcrumbs": []}},        # sem categoria → ignorado
    ]
    out = extract_categories(raws)
    assert out == [
        {"category_path": "A > B", "count": 2},
        {"category_path": "C", "count": 1},
    ]


def test_empty():
    assert extract_categories([]) == []
