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


def test_clean_text_strips_entity_encoded_tags():
    result = clean_text("Safe &lt;script&gt;alert(1)&lt;/script&gt; end")
    assert "<" not in result and ">" not in result
    assert result == "Safe alert(1) end"


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


_BASE = dict(source_site="x", source_url="u", scraped_at="t",
             authorization_ref="r", raw_ref="")


def test_normalize_without_map_is_unchanged():
    rec = normalize({"sku": "P", "name": "N", "breadcrumbs": ["A", "B"]}, **_BASE)
    assert rec.category_path == "A > B"
    assert rec.category_canonical == ""      # default: no map


def test_normalize_applies_category_map():
    m = {"A > B": "Ferramentas/Elétricas"}
    rec = normalize({"sku": "P", "name": "N", "breadcrumbs": ["A", "B"]},
                    category_map=m, **_BASE)
    assert rec.category_canonical == "Ferramentas/Elétricas"
    assert rec.category_path == "A > B"       # raw preserved


def test_normalize_unmapped_category_stays_empty():
    rec = normalize({"sku": "P", "name": "N", "breadcrumbs": ["Z"]},
                    category_map={"A > B": "x"}, **_BASE)
    assert rec.category_canonical == ""
