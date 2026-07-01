import csv
import io

from .cache import atomic_write

CSV_COLUMNS = [
    "schema_version", "product_id", "sku", "name", "brand", "division",
    "category_path", "breadcrumb", "best_price", "price_band", "price_source",
    "list_price", "cost_price", "total_stock", "image_url", "source_url",
    "description_clean",
]


def write_csv(records, path):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    count = 0
    for rec in records:
        writer.writerow(rec.to_row())
        count += 1
    atomic_write(path, buf.getvalue())
    return count
