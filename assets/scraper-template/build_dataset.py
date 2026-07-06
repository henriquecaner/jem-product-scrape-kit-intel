"""Assemble scraped raw records into the canonical dataset + exports."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from jemscrape.config import load_config
from jemscrape.errors import ConfigError
from jemscrape.normalize import normalize
from jemscrape.dedup import collapse_stock, pick_price, collapse_variants
from jemscrape.export_csv import write_csv
from jemscrape.export_wiki import write_wiki

HERE = Path(__file__).resolve().parent


def build(raw_records, *, source_site, authorization_ref, scraped_at, exports_dir,
          band_priority=(), hub_group=frozenset(), ireland_branch="", category_map=None):
    band_priority = list(band_priority)
    hub_group = set(hub_group)
    records = []
    normalize_errors = 0
    for item in raw_records:
        try:
            rec = normalize(
                item["raw"], source_site=source_site, source_url=item["url"],
                scraped_at=scraped_at, authorization_ref=authorization_ref,
                raw_ref=item.get("raw_ref", ""), category_map=category_map,
            )
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            normalize_errors += 1
            url = item.get("url", "?") if isinstance(item, dict) else "?"
            print(f"[warn] skipping record {url}: {exc}", file=sys.stderr)
            continue
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
            "csv": str(csv_path), "wiki": str(wiki_path),
            "normalize_errors": normalize_errors}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build canonical dataset + exports")
    parser.add_argument("--records", required=True, help="JSON file of raw_records")
    parser.add_argument("--config", default=str(HERE / "config.json"),
                         help="Path to config.json")
    parser.add_argument("--exports", default=str(HERE / "exports"),
                         help="Directory to write exports into")
    parser.add_argument("--category-map", default=None,
                         help="JSON dict {raw category_path: canonical} for LLM-assisted categorization")
    parser.add_argument("--extract-categories", default=None,
                         help="Write distinct raw category paths to this path and exit (no export)")
    args = parser.parse_args(argv)

    try:
        raws = json.loads(Path(args.records).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"records file not found or invalid: {exc}.", file=sys.stderr)
        return 2

    if not isinstance(raws, list):
        print(
            f"records file at {args.records} must be a JSON list of records.",
            file=sys.stderr,
        )
        return 2

    if args.extract_categories:
        from jemscrape.categories import extract_categories
        from jemscrape.cache import atomic_write
        atomic_write(args.extract_categories,
                     json.dumps(extract_categories(raws), ensure_ascii=False, indent=2))
        print(f"[categories] wrote {args.extract_categories}")
        return 0

    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(
            f"config not found or invalid: {exc}. "
            "Copy config.json.example to config.json and set target_domain.",
            file=sys.stderr,
        )
        return 2

    source_site = cfg.get("target_domain")
    if not isinstance(source_site, str) or not source_site.strip():
        print(
            "config is missing required key 'target_domain': "
            "set target_domain in config.json.",
            file=sys.stderr,
        )
        return 2

    category_map = None
    if args.category_map:
        try:
            category_map = json.loads(Path(args.category_map).read_text(encoding="utf-8"))
            if not isinstance(category_map, dict):
                raise ValueError("category map must be a JSON object")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            print(f"category map not found or invalid: {exc}.", file=sys.stderr)
            return 2

    summary = build(
        raws,
        source_site=source_site,
        authorization_ref=cfg.get("authorization_ref", ""),
        scraped_at=datetime.now(timezone.utc).isoformat(),
        exports_dir=args.exports,
        band_priority=cfg.get("band_priority", []),
        hub_group=cfg.get("hub_group", []),
        ireland_branch=cfg.get("ireland_branch", ""),
        category_map=category_map,
    )
    print(f"[build] {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
