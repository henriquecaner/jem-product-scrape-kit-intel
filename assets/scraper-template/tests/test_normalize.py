import pytest

from jemscrape.normalize import normalize, clean_text


def _norm(raw):
    return normalize(
        raw, source_site="ex.com", source_url="https://ex.com/p/1",
        scraped_at="2026-07-01T00:00:00+00:00", authorization_ref="auth-1",
        raw_ref="data/1.html",
    )


def test_clean_text_unescapes_and_strips_tags():
    assert clean_text("<p>Fire &amp; smoke</p>  ") == "Fire & smoke"


def test_normalize_maps_core_fields():
    rec = _norm({"sku": "A1", "name": "Widget", "brand": "Acme",
                 "breadcrumbs": ["Fire", "Detectors"], "description": "<b>hi</b>"})
    assert rec.product_id == "A1"
    assert rec.category_path == "Fire > Detectors"
    assert rec.description_clean == "hi"
    assert rec.source_site == "ex.com"


def test_normalize_prefers_explicit_product_id():
    rec = _norm({"product_id": "M-9", "sku": "A1", "name": "W"})
    assert rec.product_id == "M-9"


def test_normalize_defaults_missing_collections():
    rec = _norm({"sku": "A1", "name": "W"})
    assert rec.images == [] and rec.specs == {} and rec.prices == []
    assert rec.stock == {}


def test_normalize_raises_on_incomplete():
    with pytest.raises(ValueError):
        _norm({"sku": "", "name": ""})  # no product_id, no name
