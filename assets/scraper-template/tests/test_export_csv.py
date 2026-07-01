import csv

from jemscrape.export_csv import write_csv, CSV_COLUMNS
from jemscrape.canonical import CanonicalRecord


def _rec(pid, name, price):
    return CanonicalRecord(
        source_site="e", source_url="https://e/p", scraped_at="t", authorization_ref="a",
        product_id=pid, sku=pid, name=name, brand="b", description_raw="", description_clean="d",
        breadcrumbs=["Fire"], division="Fire", category_path="Fire", images=[],
        specs={}, prices=[{"value": price, "band": "PLE-J015", "source": "jem_band"}],
        list_price=None, cost_price=None, variants=[], stock={"total": 3},
        attachments=[], related=[], raw_ref="",
    )


def test_write_csv_writes_rows_and_returns_count(tmp_path):
    out = tmp_path / "exports" / "products.csv"
    n = write_csv([_rec("A1", "Widget", 9.5), _rec("A2", "Gadget", 12.0)], out)
    assert n == 2
    with out.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [r["product_id"] for r in rows] == ["A1", "A2"]
    assert rows[0]["best_price"] == "9.5"
    assert list(rows[0].keys()) == CSV_COLUMNS


def test_write_csv_empty_writes_header_only(tmp_path):
    out = tmp_path / "products.csv"
    n = write_csv([], out)
    assert n == 0
    text = out.read_text(encoding="utf-8")
    assert text.strip() == ",".join(CSV_COLUMNS)
