# Normalize + Export — Implementation Plan (Plano 2 de 6)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn raw parsed product dicts into the versioned canonical JEM record and export them as `products.csv` and a breadcrumb-organized `wiki/`, applying the reusable dedup/reconciliation logic generalized from the two reference scrapers.

**Architecture:** Extends the `jemscrape/` package (stdlib only) with `canonical.py` (the schema), `normalize.py` (raw dict → `CanonicalRecord`, cleaning + derived fields), `dedup.py` (stock hub-collapse, price-band priority, variant collision), `export_csv.py`, `export_wiki.py`, and a template-root `build_dataset.py` that orchestrates load → normalize → dedup → export. Every function takes its inputs explicitly (records lists, config dicts) so it is unit-testable without a live scrape. Site-specific field mapping stays in the per-site `site_adapter.parse` (out of scope); the normalizer assumes the raw dict already uses canonical field names and hardens/cleans/derives from there.

**Tech Stack:** Python 3.9+ (stdlib only at runtime — `csv`, `html`, `re`, `json`, `dataclasses`). `pytest` dev-only. Reuses `jemscrape.cache.atomic_write` (Plano 1).

## Global Constraints

- Runtime code is **Python 3 stdlib only** — no third-party imports in `jemscrape/`, `build_dataset.py`. Min Python **3.9**.
- The canonical record carries `schema_version` (start `"1.0"`, matching Plano 1's manifest).
- All persisted writes use `jemscrape.cache.atomic_write` (temp + `os.replace`).
- Exports land in `exports/` (`exports/products.csv`, `exports/wiki/**.md`) — versioned, NOT git-ignored.
- Dedup logic is **parametrized**, never site-hardcoded: hub-group branch ids, Ireland branch id, and price-band priority come from config, not literals in the code.
- Text cleaning is deterministic: `html.unescape` + strip tags with a stdlib regex; no network, no third-party HTML parser.
- Functions take records/config as explicit arguments (no global state) so they test without a scrape.

---

## File Structure

```
assets/scraper-template/
├── jemscrape/
│   ├── canonical.py      # SCHEMA_VERSION, CanonicalRecord dataclass, validate, to_row
│   ├── normalize.py      # normalize(raw, ...) -> CanonicalRecord
│   ├── dedup.py          # collapse_stock, pick_price, collapse_variants
│   ├── export_csv.py     # write_csv(records, path)
│   └── export_wiki.py    # write_wiki(records, wiki_dir)
├── build_dataset.py      # orchestrator + CLI: load -> normalize -> dedup -> export
└── tests/
    ├── test_canonical.py
    ├── test_normalize.py
    ├── test_dedup.py
    ├── test_export_csv.py
    ├── test_export_wiki.py
    └── test_build_dataset.py
```

**Environment note (all tasks):** pytest is in the repo's local `.venv` (PEP 668). Run focused tests as `.venv/bin/python -m pytest <path> -v` from the repo root; run the full suite `.venv/bin/python -m pytest -q` before each commit. Every commit message ends with the trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: Canonical record schema

**Files:**
- Create: `assets/scraper-template/jemscrape/canonical.py`
- Test: `assets/scraper-template/tests/test_canonical.py`

**Interfaces:**
- Produces:
  - `SCHEMA_VERSION = "1.0"`.
  - `CanonicalRecord` dataclass with fields: `source_site, source_url, scraped_at, authorization_ref, product_id, sku, name, brand, description_raw, description_clean, breadcrumbs (list), division, category_path, images (list), specs (dict), prices (list of dict), list_price, cost_price, variants (list of dict), stock (dict), attachments (list), related (list), raw_ref`. `schema_version` defaults to `SCHEMA_VERSION`.
  - `record.validate() -> None` — raises `ValueError` if a required field (`source_site`, `source_url`, `product_id`, `name`) is missing/empty.
  - `record.to_row() -> dict` — flat dict for CSV: `schema_version, product_id, sku, name, brand, division, category_path, breadcrumb, best_price, price_band, price_source, list_price, cost_price, total_stock, image_url, source_url, description_clean`. `breadcrumb` = `" > ".join(breadcrumbs)`; `best_price`/`price_band`/`price_source` from the first entry of `prices` (or blank); `image_url` = first of `images` (or blank); `total_stock` = `stock.get("total", "")`.
  - `record.to_dict() -> dict` — the full record as a JSON-serializable dict (includes `schema_version`).

- [ ] **Step 1: Write the failing test**

`assets/scraper-template/tests/test_canonical.py`:
```python
import pytest

from jemscrape.canonical import CanonicalRecord, SCHEMA_VERSION


def _rec(**over):
    base = dict(
        source_site="ex.com", source_url="https://ex.com/p/1",
        scraped_at="2026-07-01T00:00:00+00:00", authorization_ref="auth-1",
        product_id="A1", sku="A1", name="Widget", brand="Acme",
        description_raw="<b>raw</b>", description_clean="raw",
        breadcrumbs=["Fire", "Detectors"], division="Fire", category_path="Fire > Detectors",
        images=["https://ex.com/i/1.jpg"], specs={"weight": "2kg"},
        prices=[{"value": 21.86, "currency": "GBP", "source": "jem_band", "band": "PLE-J015"}],
        list_price=19.67, cost_price=None,
        variants=[], stock={"total": 5, "by_location": {}},
        attachments=[], related=[], raw_ref="data/a1.html",
    )
    base.update(over)
    return CanonicalRecord(**base)


def test_schema_version_default():
    assert _rec().schema_version == SCHEMA_VERSION == "1.0"


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
    assert row["schema_version"] == "1.0"


def test_to_row_blank_when_no_price_or_image():
    row = _rec(prices=[], images=[]).to_row()
    assert row["best_price"] == ""
    assert row["price_band"] == ""
    assert row["image_url"] == ""


def test_to_dict_is_json_serializable():
    import json
    json.dumps(_rec().to_dict())  # no raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_canonical.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jemscrape.canonical'`

- [ ] **Step 3: Write minimal implementation**

`assets/scraper-template/jemscrape/canonical.py`:
```python
from dataclasses import dataclass, field, asdict

SCHEMA_VERSION = "1.0"

_REQUIRED = ("source_site", "source_url", "product_id", "name")


@dataclass
class CanonicalRecord:
    source_site: str
    source_url: str
    scraped_at: str
    authorization_ref: str
    product_id: str
    sku: str
    name: str
    brand: str
    description_raw: str
    description_clean: str
    breadcrumbs: list
    division: str
    category_path: str
    images: list
    specs: dict
    prices: list
    list_price: object          # float | None
    cost_price: object          # float | None
    variants: list
    stock: dict
    attachments: list
    related: list
    raw_ref: str
    schema_version: str = SCHEMA_VERSION

    def validate(self):
        missing = [f for f in _REQUIRED if not getattr(self, f)]
        if missing:
            raise ValueError(f"canonical record missing required fields: {missing}")

    def to_dict(self):
        return asdict(self)

    def to_row(self):
        price = self.prices[0] if self.prices else {}
        return {
            "schema_version": self.schema_version,
            "product_id": self.product_id,
            "sku": self.sku,
            "name": self.name,
            "brand": self.brand,
            "division": self.division,
            "category_path": self.category_path,
            "breadcrumb": " > ".join(self.breadcrumbs),
            "best_price": price.get("value", ""),
            "price_band": price.get("band", ""),
            "price_source": price.get("source", ""),
            "list_price": self.list_price if self.list_price is not None else "",
            "cost_price": self.cost_price if self.cost_price is not None else "",
            "total_stock": self.stock.get("total", ""),
            "image_url": self.images[0] if self.images else "",
            "source_url": self.source_url,
            "description_clean": self.description_clean,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_canonical.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/canonical.py assets/scraper-template/tests/test_canonical.py
git commit -m "feat: canonical JEM product record (schema_version, validate, to_row)"
```

---

### Task 2: Normalize raw dict → canonical record

**Files:**
- Create: `assets/scraper-template/jemscrape/normalize.py`
- Test: `assets/scraper-template/tests/test_normalize.py`

**Interfaces:**
- Consumes: `CanonicalRecord` (Task 1).
- Produces:
  - `clean_text(html_text: str) -> str` — `html.unescape` then strip tags via regex, collapse whitespace.
  - `normalize(raw: dict, *, source_site, source_url, scraped_at, authorization_ref, raw_ref) -> CanonicalRecord`. Maps a raw parsed dict (canonical field names, all optional) into a `CanonicalRecord`: fills defaults for missing lists/dicts, sets `description_clean = clean_text(raw.get("description") or raw.get("description_raw") or "")`, `category_path = " > ".join(breadcrumbs)`, `product_id = raw.get("product_id") or raw.get("sku") or ""`. Calls `.validate()` before returning (raises `ValueError` on incomplete input).

- [ ] **Step 1: Write the failing test**

`assets/scraper-template/tests/test_normalize.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_normalize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jemscrape.normalize'`

- [ ] **Step 3: Write minimal implementation**

`assets/scraper-template/jemscrape/normalize.py`:
```python
import html
import re

from .canonical import CanonicalRecord

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def clean_text(html_text):
    if not html_text:
        return ""
    text = html.unescape(html_text)
    text = _TAG.sub(" ", text)
    return _WS.sub(" ", text).strip()


def normalize(raw, *, source_site, source_url, scraped_at, authorization_ref, raw_ref):
    breadcrumbs = list(raw.get("breadcrumbs") or [])
    description_raw = raw.get("description") or raw.get("description_raw") or ""
    rec = CanonicalRecord(
        source_site=source_site,
        source_url=source_url,
        scraped_at=scraped_at,
        authorization_ref=authorization_ref,
        product_id=raw.get("product_id") or raw.get("sku") or "",
        sku=raw.get("sku") or "",
        name=raw.get("name") or "",
        brand=raw.get("brand") or "",
        description_raw=description_raw,
        description_clean=clean_text(description_raw),
        breadcrumbs=breadcrumbs,
        division=raw.get("division") or (breadcrumbs[0] if breadcrumbs else ""),
        category_path=" > ".join(breadcrumbs),
        images=list(raw.get("images") or []),
        specs=dict(raw.get("specs") or {}),
        prices=list(raw.get("prices") or []),
        list_price=raw.get("list_price"),
        cost_price=raw.get("cost_price"),
        variants=list(raw.get("variants") or []),
        stock=dict(raw.get("stock") or {}),
        attachments=list(raw.get("attachments") or []),
        related=list(raw.get("related") or []),
        raw_ref=raw_ref,
    )
    rec.validate()
    return rec
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_normalize.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/normalize.py assets/scraper-template/tests/test_normalize.py
git commit -m "feat: normalize raw parsed dict into canonical record with cleaning"
```

---

### Task 3: Dedup / reconciliation (stock, price, variants)

**Files:**
- Create: `assets/scraper-template/jemscrape/dedup.py`
- Test: `assets/scraper-template/tests/test_dedup.py`

**Interfaces:**
- Produces (all parametrized — no site literals):
  - `collapse_stock(by_location: dict, *, hub_group: set, ireland_branch: str) -> dict` → `{"total", "uk", "ireland"}`. `hub` = max over `hub_group` branch ids present (default 0); `uk_others` = sum of values for branches not in `hub_group` and != `ireland_branch`, each clamped `>= 0`; `uk = hub + uk_others`; `ireland = max(by_location.get(ireland_branch, 0), 0)`; `total = uk + ireland`.
  - `pick_price(prices: list, *, band_priority: list) -> dict | None` → the price dict whose `band` appears earliest in `band_priority`; if none match, the first price; if `prices` empty, `None`.
  - `collapse_variants(records: list) -> list` → group `CanonicalRecord`s by `product_id`; for a group of size > 1, set `multi_variant=True` on the kept record and return the one with the lowest `list_price` (treat `None` as `+inf`); groups of size 1 pass through unchanged. Order of first appearance preserved.

- [ ] **Step 1: Write the failing test**

`assets/scraper-template/tests/test_dedup.py`:
```python
from jemscrape.dedup import collapse_stock, pick_price, collapse_variants
from jemscrape.canonical import CanonicalRecord


def _rec(pid, list_price):
    return CanonicalRecord(
        source_site="e", source_url="u", scraped_at="t", authorization_ref="a",
        product_id=pid, sku=pid, name="n", brand="b", description_raw="", description_clean="",
        breadcrumbs=[], division="", category_path="", images=[], specs={},
        prices=[], list_price=list_price, cost_price=None, variants=[],
        stock={}, attachments=[], related=[], raw_ref="",
    )


HUB = {"hub-real", "hub-mirror-1", "hub-mirror-2"}


def test_collapse_stock_collapses_hub_to_max_and_sums_others():
    by_loc = {"hub-real": 10, "hub-mirror-1": 10, "hub-mirror-2": 8,
              "leeds": 3, "ireland": 4}
    out = collapse_stock(by_loc, hub_group=HUB, ireland_branch="ireland")
    assert out["uk"] == 13      # max(10,10,8)=10 hub + 3 leeds
    assert out["ireland"] == 4
    assert out["total"] == 17


def test_collapse_stock_clamps_negative_oversold():
    by_loc = {"leeds": -5, "ireland": 2}
    out = collapse_stock(by_loc, hub_group=HUB, ireland_branch="ireland")
    assert out["uk"] == 0       # -5 clamped to 0
    assert out["total"] == 2


def test_pick_price_prefers_contract_band():
    prices = [{"band": "universal", "value": 10}, {"band": "PLE-J015", "value": 9}]
    assert pick_price(prices, band_priority=["PLE-J015", "universal"])["value"] == 9


def test_pick_price_falls_back_to_first_when_no_band_matches():
    prices = [{"band": "x", "value": 5}, {"band": "y", "value": 6}]
    assert pick_price(prices, band_priority=["PLE-J015"])["value"] == 5


def test_pick_price_none_when_empty():
    assert pick_price([], band_priority=["PLE-J015"]) is None


def test_collapse_variants_keeps_cheapest_and_marks_multi():
    records = [_rec("M1", 20.0), _rec("M1", 15.0), _rec("M2", 8.0)]
    out = collapse_variants(records)
    by_pid = {r.product_id: r for r in out}
    assert len(out) == 2
    assert by_pid["M1"].list_price == 15.0
    assert getattr(by_pid["M1"], "multi_variant", False) is True
    assert getattr(by_pid["M2"], "multi_variant", False) is False


def test_collapse_variants_none_list_price_is_infinity():
    records = [_rec("M1", None), _rec("M1", 12.0)]
    out = collapse_variants(records)
    assert out[0].list_price == 12.0   # the priced one wins over None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_dedup.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jemscrape.dedup'`

- [ ] **Step 3: Write minimal implementation**

`assets/scraper-template/jemscrape/dedup.py`:
```python
def collapse_stock(by_location, *, hub_group, ireland_branch):
    hub = max((by_location[b] for b in hub_group if b in by_location), default=0)
    uk_others = sum(
        max(v, 0) for b, v in by_location.items()
        if b not in hub_group and b != ireland_branch
    )
    uk = max(hub, 0) + uk_others
    ireland = max(by_location.get(ireland_branch, 0), 0)
    return {"total": uk + ireland, "uk": uk, "ireland": ireland}


def pick_price(prices, *, band_priority):
    if not prices:
        return None
    ranked = []
    for p in prices:
        band = p.get("band")
        rank = band_priority.index(band) if band in band_priority else len(band_priority)
        ranked.append((rank, p))
    ranked.sort(key=lambda rp: rp[0])
    return ranked[0][1]


def collapse_variants(records):
    groups = {}
    order = []
    for r in records:
        if r.product_id not in groups:
            groups[r.product_id] = []
            order.append(r.product_id)
        groups[r.product_id].append(r)

    out = []
    for pid in order:
        group = groups[pid]
        if len(group) == 1:
            out.append(group[0])
            continue
        best = min(group, key=lambda r: r.list_price if r.list_price is not None else float("inf"))
        setattr(best, "multi_variant", True)
        out.append(best)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_dedup.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/dedup.py assets/scraper-template/tests/test_dedup.py
git commit -m "feat: dedup — hub-stock collapse, price-band priority, variant collision"
```

---

### Task 4: CSV export

**Files:**
- Create: `assets/scraper-template/jemscrape/export_csv.py`
- Test: `assets/scraper-template/tests/test_export_csv.py`

**Interfaces:**
- Consumes: `CanonicalRecord.to_row()` (Task 1); `jemscrape.cache.atomic_write` (Plano 1).
- Produces:
  - `CSV_COLUMNS` — the fixed, stable column order (the keys of `to_row()`).
  - `write_csv(records: list, path) -> int` — writes all records' `to_row()` dicts to a UTF-8 CSV at `path` (atomic), header first, columns in `CSV_COLUMNS` order; returns the number of data rows written. Empty `records` writes a header-only file and returns 0.

- [ ] **Step 1: Write the failing test**

`assets/scraper-template/tests/test_export_csv.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_export_csv.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jemscrape.export_csv'`

- [ ] **Step 3: Write minimal implementation**

`assets/scraper-template/jemscrape/export_csv.py`:
```python
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
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    count = 0
    for rec in records:
        writer.writerow(rec.to_row())
        count += 1
    atomic_write(path, buf.getvalue())
    return count
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_export_csv.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/export_csv.py assets/scraper-template/tests/test_export_csv.py
git commit -m "feat: CSV export with stable column order (atomic write)"
```

---

### Task 5: Wiki export (breadcrumb-organized markdown)

**Files:**
- Create: `assets/scraper-template/jemscrape/export_wiki.py`
- Test: `assets/scraper-template/tests/test_export_wiki.py`

**Interfaces:**
- Consumes: `CanonicalRecord` (Task 1); `jemscrape.cache.atomic_write` (Plano 1).
- Produces:
  - `safe_name(name: str) -> str` — a filesystem-safe file base (strip/replace unsafe chars; fall back to `product_id` if empty — the caller passes a fallback).
  - `render_markdown(record) -> str` — the per-product markdown (name H1, sku/brand, category, image, description, price, source link).
  - `write_wiki(records: list, wiki_dir) -> int` — writes one `.md` per record under `wiki_dir/<breadcrumb parts>/<safe name>.md` (atomic), plus a root `INDEX.md` linking every product by relative path. Returns the number of product files written. Collisions on the same path get a `-<product_id>` suffix.

- [ ] **Step 1: Write the failing test**

`assets/scraper-template/tests/test_export_wiki.py`:
```python
from jemscrape.export_wiki import write_wiki, safe_name, render_markdown
from jemscrape.canonical import CanonicalRecord


def _rec(pid, name, crumbs):
    return CanonicalRecord(
        source_site="e", source_url="https://e/p/" + pid, scraped_at="t", authorization_ref="a",
        product_id=pid, sku=pid, name=name, brand="Acme", description_raw="", description_clean="Desc.",
        breadcrumbs=crumbs, division=crumbs[0] if crumbs else "", category_path=" > ".join(crumbs),
        images=["https://e/i/" + pid + ".jpg"],
        specs={}, prices=[{"value": 9.5, "band": "PLE-J015", "source": "jem_band"}],
        list_price=None, cost_price=None, variants=[], stock={"total": 3},
        attachments=[], related=[], raw_ref="",
    )


def test_safe_name_strips_unsafe_chars():
    s = safe_name("1kg Powder / Extinguisher (APS1)")
    assert "/" not in s and s


def test_render_markdown_has_name_and_link():
    md = render_markdown(_rec("A1", "Widget", ["Fire", "Detectors"]))
    assert "# Widget" in md
    assert "https://e/p/A1" in md
    assert "PLE-J015" in md


def test_write_wiki_creates_files_under_breadcrumbs_and_index(tmp_path):
    wiki = tmp_path / "wiki"
    n = write_wiki([_rec("A1", "Widget", ["Fire", "Detectors"]),
                    _rec("A2", "Gadget", ["Fire"])], wiki)
    assert n == 2
    assert (wiki / "Fire" / "Detectors").is_dir()
    md_files = list(wiki.rglob("*.md"))
    names = {p.name for p in md_files}
    assert "INDEX.md" in names
    assert any(p.match("Fire/Detectors/*.md") for p in md_files)
    index = (wiki / "INDEX.md").read_text(encoding="utf-8")
    assert "Widget" in index and "Gadget" in index


def test_write_wiki_disambiguates_path_collision(tmp_path):
    wiki = tmp_path / "wiki"
    # same name + same breadcrumbs -> would collide; must not overwrite
    n = write_wiki([_rec("A1", "Widget", ["Fire"]), _rec("A2", "Widget", ["Fire"])], wiki)
    assert n == 2
    md_files = [p for p in wiki.rglob("*.md") if p.name != "INDEX.md"]
    assert len(md_files) == 2  # both written, not overwritten
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_export_wiki.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jemscrape.export_wiki'`

- [ ] **Step 3: Write minimal implementation**

`assets/scraper-template/jemscrape/export_wiki.py`:
```python
import re
from pathlib import Path

from .cache import atomic_write

_UNSAFE = re.compile(r"[^A-Za-z0-9 ._()\-]+")


def safe_name(name, fallback="index"):
    cleaned = _UNSAFE.sub("", name or "").strip()
    return cleaned or fallback


def render_markdown(record):
    lines = [f"# {record.name}", ""]
    meta = []
    if record.sku:
        meta.append(f"**SKU:** `{record.sku}`")
    if record.brand:
        meta.append(f"**Brand:** {record.brand}")
    if meta:
        lines += [" · ".join(meta), ""]
    if record.category_path:
        lines += [f"**Category:** {record.category_path}", ""]
    if record.images:
        lines += [f"![{safe_name(record.name)}]({record.images[0]})", ""]
    if record.description_clean:
        lines += ["## Description", record.description_clean, ""]
    if record.prices:
        p = record.prices[0]
        band = f" _(band {p.get('band')})_" if p.get("band") else ""
        lines += ["## Pricing", f"- {p.get('value')} {p.get('currency', '')}{band}".rstrip(), ""]
    lines += [f"[Source]({record.source_url})", ""]
    return "\n".join(lines)


def write_wiki(records, wiki_dir):
    wiki_dir = Path(wiki_dir)
    index = ["# Product Index", ""]
    seen = set()
    count = 0
    for rec in records:
        parts = [safe_name(c, c) for c in rec.breadcrumbs] or ["Uncategorized"]
        base = safe_name(rec.name, rec.product_id)
        rel = Path(*parts) / f"{base}.md"
        if str(rel) in seen:
            rel = Path(*parts) / f"{base}-{safe_name(rec.product_id, rec.product_id)}.md"
        seen.add(str(rel))
        atomic_write(wiki_dir / rel, render_markdown(rec))
        index.append(f"- [{rec.name}]({rel.as_posix()})")
        count += 1
    atomic_write(wiki_dir / "INDEX.md", "\n".join(index) + "\n")
    return count
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_export_wiki.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/export_wiki.py assets/scraper-template/tests/test_export_wiki.py
git commit -m "feat: wiki export — breadcrumb dirs, per-product markdown, INDEX"
```

---

### Task 6: `build_dataset.py` orchestrator + CLI

**Files:**
- Create: `assets/scraper-template/build_dataset.py`
- Test: `assets/scraper-template/tests/test_build_dataset.py`

**Interfaces:**
- Consumes: `normalize` (Task 2), `collapse_variants`/`collapse_stock`/`pick_price` (Task 3), `write_csv` (Task 4), `write_wiki` (Task 5), `CanonicalRecord` (Task 1).
- Produces:
  - `build(raw_records: list, *, source_site, authorization_ref, scraped_at, exports_dir, band_priority=(), hub_group=frozenset(), ireland_branch="") -> dict`. Each `raw_records` item is `{"url": <source_url>, "raw_ref": <path>, "raw": <parsed dict>}`. Pipeline: normalize each → apply `collapse_stock` to any record carrying `stock["by_location"]` (writing `stock["total"]/["uk"]/["ireland"]`) and `pick_price` to set `prices` to the single best price (kept as a 1-element list) when `band_priority` is given → `collapse_variants` → `write_csv(exports_dir/"products.csv")` + `write_wiki(exports_dir/"wiki")`. Returns `{"normalized": N, "exported": M, "csv": path, "wiki": path}`.
  - `main(argv=None) -> int` — CLI reading `config.json` (for `source_site`, `band_priority`, `hub_group`, `ireland_branch`) and a `--records <json>` file of raw_records; writes to `exports/`. (The scraper run produces the records file; wiring it to the live manifest is a later plan.)

- [ ] **Step 1: Write the failing test**

`assets/scraper-template/tests/test_build_dataset.py`:
```python
import csv

from build_dataset import build


def _raw(pid, name, crumbs, by_loc, list_price):
    return {
        "url": f"https://e/p/{pid}", "raw_ref": f"data/{pid}.html",
        "raw": {"sku": pid, "name": name, "breadcrumbs": crumbs,
                "list_price": list_price,
                "prices": [{"value": 9.9, "band": "universal"},
                           {"value": 9.0, "band": "PLE-J015"}],
                "stock": {"by_location": by_loc}},
    }


HUB = {"hub", "hub-mirror"}


def test_build_normalizes_dedups_and_exports(tmp_path):
    exports = tmp_path / "exports"
    raws = [
        _raw("M1", "Widget", ["Fire", "Detectors"], {"hub": 5, "hub-mirror": 5, "ie": 2}, 20.0),
        _raw("M1", "Widget v2", ["Fire", "Detectors"], {"hub": 5, "hub-mirror": 5, "ie": 2}, 15.0),
        _raw("M2", "Gadget", ["Fire"], {"leeds": 3}, 8.0),
    ]
    summary = build(
        raws, source_site="e", authorization_ref="auth-1", scraped_at="t",
        exports_dir=exports, band_priority=["PLE-J015", "universal"],
        hub_group=HUB, ireland_branch="ie",
    )
    assert summary["normalized"] == 3
    assert summary["exported"] == 2       # M1 variants collapsed to 1

    with (exports / "products.csv").open(newline="", encoding="utf-8") as f:
        rows = {r["product_id"]: r for r in csv.DictReader(f)}
    assert set(rows) == {"M1", "M2"}
    assert rows["M1"]["best_price"] == "9.0"       # PLE-J015 band chosen
    assert rows["M1"]["list_price"] == "15.0"      # cheaper variant kept
    assert rows["M1"]["total_stock"] == "7"        # hub max 5 + ie 2
    assert (exports / "wiki" / "INDEX.md").exists()


def test_build_handles_empty(tmp_path):
    summary = build([], source_site="e", authorization_ref="a", scraped_at="t",
                    exports_dir=tmp_path / "exports")
    assert summary["normalized"] == 0 and summary["exported"] == 0
    assert (tmp_path / "exports" / "products.csv").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_build_dataset.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'build_dataset'`

- [ ] **Step 3: Write minimal implementation**

`assets/scraper-template/build_dataset.py`:
```python
"""Assemble scraped raw records into the canonical dataset + exports."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from jemscrape.normalize import normalize
from jemscrape.dedup import collapse_stock, pick_price, collapse_variants
from jemscrape.export_csv import write_csv
from jemscrape.export_wiki import write_wiki

HERE = Path(__file__).resolve().parent


def build(raw_records, *, source_site, authorization_ref, scraped_at, exports_dir,
          band_priority=(), hub_group=frozenset(), ireland_branch=""):
    band_priority = list(band_priority)
    hub_group = set(hub_group)
    records = []
    for item in raw_records:
        rec = normalize(
            item["raw"], source_site=source_site, source_url=item["url"],
            scraped_at=scraped_at, authorization_ref=authorization_ref,
            raw_ref=item.get("raw_ref", ""),
        )
        by_loc = rec.stock.get("by_location")
        if by_loc:
            rec.stock.update(collapse_stock(by_loc, hub_group=hub_group,
                                            ireland_branch=ireland_branch))
        if band_priority and rec.prices:
            best = pick_price(rec.prices, band_priority=band_priority)
            rec.prices = [best] if best else []
        records.append(rec)

    normalized = len(records)
    records = collapse_variants(records)
    exports_dir = Path(exports_dir)
    csv_path = exports_dir / "products.csv"
    wiki_path = exports_dir / "wiki"
    exported = write_csv(records, csv_path)
    write_wiki(records, wiki_path)
    return {"normalized": normalized, "exported": exported,
            "csv": str(csv_path), "wiki": str(wiki_path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build canonical dataset + exports")
    parser.add_argument("--records", required=True, help="JSON file of raw_records")
    args = parser.parse_args(argv)

    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    raws = json.loads(Path(args.records).read_text(encoding="utf-8"))
    summary = build(
        raws,
        source_site=cfg["target_domain"],
        authorization_ref=cfg.get("authorization_ref", ""),
        scraped_at=datetime.now(timezone.utc).isoformat(),
        exports_dir=HERE / "exports",
        band_priority=cfg.get("band_priority", []),
        hub_group=cfg.get("hub_group", []),
        ireland_branch=cfg.get("ireland_branch", ""),
    )
    print(f"[build] {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_build_dataset.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full suite and commit**

Run: `.venv/bin/python -m pytest -q`
Expected: all tests pass (Plano 1's 54 + Plano 2's ~27).

```bash
git add assets/scraper-template/build_dataset.py assets/scraper-template/tests/test_build_dataset.py
git commit -m "feat: build_dataset orchestrator — normalize -> dedup -> csv + wiki exports"
```

---

## Self-Review

**1. Spec coverage (spec §7 canonical record + exports, §11 normalize skill patterns):**
- `schema_version` on the record (§7) → Task 1. ✓
- `variants[]`/`prices[]` multi-band, `product_id` identity key (§7 rev2 additions) → Task 1 fields + Task 3 `pick_price`/`collapse_variants`. ✓
- Stock dedup / hub collapse (fortus pattern, §7 "dedup de hub aplicado no normalize") → Task 3 `collapse_stock`. ✓
- Exports: `products.csv`, `wiki/**.md` by breadcrumb, under `exports/` (§5, §13) → Tasks 4, 5, 6. ✓
- Parametrized (no site literals) — hub_group/ireland_branch/band_priority from config → Tasks 3, 6. ✓
- Reuses `atomic_write` (§13 atomic writes) → Tasks 4, 5. ✓
- **Out of scope (correct):** per-site `parse` field mapping (site_adapter), the live manifest→records wiring (a later plan feeds `build_dataset` from the run), GMC/Shopify/Magento mapping (Camada 2). Noted in the plan intro.

**2. Placeholder scan:** No TBD/TODO; every code step has complete runnable code; every test shows assertions. `config.json` keys `band_priority`/`hub_group`/`ireland_branch`/`authorization_ref` are read with `.get(..., default)` so a Plano-1 config without them still works.

**3. Type consistency:** `CanonicalRecord` fields (Task 1) are constructed identically in `normalize` (Task 2) and the dedup/test helpers (Task 3); `to_row()` keys (Task 1) equal `CSV_COLUMNS` (Task 4) — verified column-for-column; `collapse_stock`/`pick_price`/`collapse_variants` signatures (Task 3) match their calls in `build` (Task 6); `write_csv`/`write_wiki` signatures (Tasks 4/5) match their calls in `build` (Task 6). `atomic_write` (Plano 1 `cache.py`) is imported by `export_csv`, `export_wiki`.
