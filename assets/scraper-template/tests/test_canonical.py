import pytest

from jemscrape.canonical import CanonicalRecord, SCHEMA_VERSION


def _rec(**over):
    base = dict(
        source_site="ex.com", source_url="https://ex.com/p/1",
        scraped_at="2026-07-01T00:00:00+00:00", authorization_ref="auth-1",
        product_id="A1", sku="A1", name="Widget", brand="Acme",
        description_raw="<b>raw</b>", description_clean="raw",
        breadcrumbs=["Fire", "Detectors"], division="Fire", category_path="Fire > Detectors",
        category_canonical="",
        images=["https://ex.com/i/1.jpg"], specs={"weight": "2kg"},
        prices=[{"value": 21.86, "currency": "GBP", "source": "jem_band", "band": "PLE-J015"}],
        list_price=19.67, cost_price=None,
        variants=[], stock={"total": 5, "by_location": {}},
        attachments=[], related=[], raw_ref="data/a1.html",
    )
    base.update(over)
    return CanonicalRecord(**base)


def test_schema_version_default():
    assert _rec().schema_version == SCHEMA_VERSION == "1.1"


def test_validate_passes_on_complete_record():
    _rec().validate()  # no raise


def test_validate_requires_product_id():
    with pytest.raises(ValueError):
        _rec(product_id="").validate()


def test_validate_requires_name():
    with pytest.raises(ValueError):
        _rec(name="").validate()


def test_to_row_flattens_expected_columns():
    row = _rec().to_row()
    assert row["product_id"] == "A1"
    assert row["breadcrumb"] == "Fire > Detectors"
    assert row["best_price"] == 21.86
    assert row["price_band"] == "PLE-J015"
    assert row["price_source"] == "jem_band"
    assert row["image_url"] == "https://ex.com/i/1.jpg"
    assert row["total_stock"] == 5
    assert row["schema_version"] == "1.1"


def test_to_row_blank_when_no_price_or_image():
    row = _rec(prices=[], images=[]).to_row()
    assert row["best_price"] == ""
    assert row["price_band"] == ""
    assert row["image_url"] == ""


def test_to_row_non_dict_first_price_does_not_crash():
    # In the default (empty band_priority) path, pick_price never runs, so
    # an adapter returning a bare scalar (e.g. "10.00" or None) as the first
    # price element must not crash the whole export with an AttributeError.
    row = _rec(prices=["10.00"]).to_row()
    assert row["best_price"] == ""
    assert row["price_band"] == ""
    assert row["price_source"] == ""

    row2 = _rec(prices=[None]).to_row()
    assert row2["best_price"] == ""


def test_to_dict_is_json_serializable():
    import json
    json.dumps(_rec().to_dict())  # no raise


def test_category_canonical_defaults_empty_and_serializes():
    from jemscrape.canonical import CanonicalRecord, SCHEMA_VERSION
    rec = CanonicalRecord(
        source_site="x", source_url="u", scraped_at="t", authorization_ref="r",
        product_id="P", sku="P", name="N", brand="", description_raw="",
        description_clean="", breadcrumbs=["A", "B"], division="A",
        category_path="A > B", category_canonical="", images=[], specs={}, prices=[], list_price=None,
        cost_price=None, variants=[], stock={}, attachments=[], related=[], raw_ref="",
    )
    assert rec.category_canonical == ""
    assert rec.to_row()["category_canonical"] == ""
    assert SCHEMA_VERSION == "1.1"
    rec.category_canonical = "Ferramentas"
    assert rec.to_row()["category_canonical"] == "Ferramentas"
