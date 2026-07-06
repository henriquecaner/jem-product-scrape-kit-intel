import csv
import io

from .cache import atomic_write

CSV_COLUMNS = [
    "schema_version", "product_id", "sku", "name", "brand", "division",
    "category_path", "breadcrumb", "best_price", "price_band", "price_source",
    "list_price", "cost_price", "total_stock", "image_url", "source_url",
    "description_clean", "category_canonical",
]

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _sanitize_cell(value):
    if isinstance(value, str) and value and value[0] in _FORMULA_PREFIXES:
        return "'" + value
    return value


def write_csv(records, path):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    count = 0
    for rec in records:
        row = {k: _sanitize_cell(v) for k, v in rec.to_row().items()}
        writer.writerow(row)
        count += 1
    atomic_write(path, buf.getvalue())
    return count
