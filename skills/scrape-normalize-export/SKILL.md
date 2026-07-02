---
name: scrape-normalize-export
description: Turns raw scraped records into the canonical JEM dataset plus CSV and wiki exports, with dedup/reconciliation for hub stock, price bands, and variant collisions. Trigger after a scrape finishes, or on "normalize", "export the catalog", "build the CSV", "build the dataset".
allowed-tools: Bash, Read
model: sonnet
---

# Scrape normalize + export

This turns raw scraped records into the canonical JEM dataset and its exports. It wraps one CLI: `assets/scraper-template/build_dataset.py`.

## What this actually does

Run it against the raw records a scrape produced:

```
python3 build_dataset.py --records raw_records.json --config config.json --exports exports
```

Flags:
- `--records` (required) — path to a JSON file: a list of raw record entries (each with `url`, `raw`, and optionally `raw_ref`).
- `--config` — path to `config.json` (defaults to the one next to the script). Must have `target_domain` set.
- `--exports` — output directory (defaults to `exports/` next to the script).

The orchestrator (`build_dataset.build`) does three things in order:

1. **Normalize.** Each raw record goes through `jemscrape/normalize.py` -> `normalize()`, which builds a `CanonicalRecord` (`jemscrape/canonical.py`). `description_clean` comes from `clean_text`: it unescapes HTML entities *before* stripping tags and collapsing whitespace, so an entity-encoded tag can't sneak an unescaped `<script>` past the stripper. `validate()` runs on every record and requires `source_site`, `source_url`, `product_id`, `name`.
2. **Dedup / reconcile.** See rules below (`jemscrape/dedup.py`).
3. **Export.** Writes `exports/products.csv` (`jemscrape/export_csv.py`) and `exports/wiki/` (`jemscrape/export_wiki.py`).

It prints a one-line summary: `{"normalized": N, "exported": M, "csv": "...", "wiki": "..."}`. `normalized` is the record count before variant collapse; `exported` is the row count after.

## The canonical record is versioned

`CanonicalRecord.schema_version` (currently `"1.0"`) travels with every record and every CSV row. Downstream skills (Camada 2 — the ones that consume the catalog for a specific target like Shopify, GMC, NetSuite) read this field to know what shape to expect. If the schema changes, it bumps here first. Don't hand a Camada-2 skill a dataset without checking this field matches what it expects.

## Reconciliation rules

Three rules run before export, in this order:

1. **Hub stock collapse** (`collapse_stock`). Locations in `hub_group` are mirrors of the same warehouse — take the max across them, not the sum (summing would double-count the same physical stock). Every other UK location sums normally. The Ireland branch (`ireland_branch`) is kept separate and reported on its own (`stock.ireland`), authoritative for its own number — it does not fold into the UK total. Final shape: `{"total": uk + ireland, "uk": ..., "ireland": ...}`.
2. **Price by band priority** (`pick_price`). A product can carry several prices tagged with a `band` (e.g. a customer-specific band like `PLE-J015` vs. `universal`). `band_priority` in config is an ordered list — the first band in that list that the product has wins. Bands not listed rank last. Only one price survives per record.
3. **Variant collapse** (`collapse_variants`). Records sharing the same `product_id` are variants of one product. Only one survives: whichever has the cheapest `list_price` (`None` sorts last, never wins). The survivor gets `multi_variant = True` so exports can flag it.

All three are driven by config keys: `band_priority`, `hub_group`, `ireland_branch` (see `config.json.example`). Without a `band_priority` list, no price-band reduction happens and all prices from the raw record are kept as-is.

## The 17-column CSV

`exports/products.csv` (`export_csv.write_csv`) has a fixed column order — same 17 columns every run, extra fields from `to_row()` are ignored, missing ones write empty:

```
schema_version, product_id, sku, name, brand, division, category_path, breadcrumb,
best_price, price_band, price_source, list_price, cost_price, total_stock,
image_url, source_url, description_clean
```

Two things make it Excel-safe:
- Line terminator is `\n`, not the csv module default `\r\n`. This avoids the classic Windows/Excel bug where you get `\r\r\n` and rows come out with a blank line between them.
- Formula-injection sanitization: any string cell starting with `=`, `+`, `-`, `@`, tab, or `\r` gets a leading `'` prepended, so a supplier-controlled field (e.g. product name) can't turn into a live formula when opened in Excel.

The file is written atomically (`cache.atomic_write`) — no reader ever sees a half-written CSV.

## The wiki export

`exports/wiki/` (`export_wiki.write_wiki`) writes one markdown file per product, filed under a directory per breadcrumb level, plus a top-level `INDEX.md` linking every product. Filenames and directory names go through `safe_name`, which strips anything outside `[A-Za-z0-9 ._()-]` and refuses an all-dots result (so a breadcrumb of `".."` can't become a path segment). After assembling the full path, `write_wiki` double-checks it still resolves inside the wiki root before writing — belt and suspenders against path traversal from a malicious breadcrumb or product name.

## exports/ is a versioned deliverable

Unlike `data/` (the raw scrape cache, git-ignored — see `assets/project-skeleton/.gitignore`), `exports/` is **not** ignored. `products.csv` and `wiki/` are the deliverable and get committed. Don't add `exports/` to `.gitignore` and don't treat it as disposable output.

## When something looks wrong

- Missing `target_domain` in config, or a records file that isn't valid JSON — `build_dataset.py` exits 2 with a message on stderr, nothing is written.
- A record failing `validate()` (missing `source_site`, `source_url`, `product_id`, or `name`) raises before export — fix the raw record or the scraper, not the exporter.
- If stock totals look doubled, check whether a location was put in `hub_group` by mistake — hub members are max-collapsed, everything else sums.
- If the wrong price band won, check the order of `band_priority` in config — first match wins, not "most specific."
