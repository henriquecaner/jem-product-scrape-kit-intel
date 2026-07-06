"""Extract the distinct raw category paths from a scrape's raw_records so the
Claude Code operator (runtime Local, spec §11) can map them to the canonical
JEM taxonomy. Pure stdlib — the mapping itself is done by Claude via the
scrape-normalize-export skill, not by this code."""
from collections import Counter


def extract_categories(raw_records):
    counts = Counter()
    for item in raw_records:
        raw = item.get("raw") if isinstance(item, dict) else None
        if not isinstance(raw, dict):
            continue
        path = " > ".join(raw.get("breadcrumbs") or [])
        if path:
            counts[path] += 1
    return [{"category_path": p, "count": c}
            for p, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
