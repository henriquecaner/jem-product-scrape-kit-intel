# Canonical Record

The JEM canonical record is the single interface between the scraping engine
(Layer 1) and the objective skills (Layer 2, roadmap). It's implemented in
`jemscrape/canonical.py` as `CanonicalRecord`, a dataclass with `schema_version
= "1.0"`.

## Fields

```
schema_version                     "1.0" — additive by default, breaking changes bump major
source_site, source_url, scraped_at
authorization_ref                  id of the .scrape-authorization.json that authorized the capture
product_id                         identity key for dedup and resume — normalized SKU or the
                                    source's master_id; the concrete rule is per-site, decided
                                    during scaffold and documented in the project's config
sku, name, brand
description_raw, description_clean
breadcrumbs[], division, category_path
images[]                           full-res URLs
specs{}                            technical attribute key:value
variants[]                         each variant carries its own prices[]
prices[]                           [{ value, currency, source, band }] — supports multiple bands
                                    (e.g. contract price vs. universal list)
list_price, cost_price
stock{ total, by_location }        hub dedup applied at normalize time
attachments[]                      [{ label, url }]
related[]                          [{ title, url }]
raw_ref                            pointer to the cached raw file
```

`validate()` requires `source_site`, `source_url`, `product_id`, `name` to be
non-empty; missing fields raise `ValueError`. `product_id` is the identity key
used for dedup and checkpoint resume — never blank.

## CSV export (`to_row`, 17 columns)

`jemscrape/export_csv.py` writes `exports/products.csv` with a fixed column
order (`CSV_COLUMNS`), independent of dict key ordering, so downstream imports
(Excel, Shopify, GMC) don't break when fields are reordered internally:

```
schema_version, product_id, sku, name, brand, division, category_path,
breadcrumb, best_price, price_band, price_source, list_price, cost_price,
total_stock, image_url, source_url, description_clean
```

Notes on the mapping:
- `breadcrumb` is `breadcrumbs[]` joined with `" > "`.
- `best_price`, `price_band`, `price_source` come from `prices[0]` (empty
  string if no prices).
- `image_url` is `images[0]` (empty string if none) — the CSV carries one
  representative image; the full `images[]` list lives in the canonical JSON
  and the wiki export, not the CSV.
- Cells starting with `= + - @` (or tab/CR) get a leading `'` to block
  spreadsheet formula injection.
- The writer uses `\n` line endings and an atomic write (`jemscrape/cache.py`
  `atomic_write`) — no partial CSVs on crash.

## Downstream mapping (future, Layer 2)

The canonical record is designed to map to Shopify (`title` / `body_html` /
`vendor` / `variants` / `images`), Magento/NetSuite, and GMC (via the existing
`gmc-quality` skill). These mappings are **not yet built** — Layer 2 consumes
this record when each objective skill (`product-price-analysis`,
`catalog-quality-compare`, `product-create-shopify`,
`product-create-magento`) is implemented.

## Schema versioning

Policy is additive by default: new fields can be appended without bumping
`schema_version`. A breaking change (renaming/removing a field, changing a
field's type or meaning) requires a major version bump so Layer 2 skills can
detect and handle the change instead of failing silently. `schema_version`
travels in every record, in `exports/scrape_manifest.json`, and in
`exports/products.csv`.
