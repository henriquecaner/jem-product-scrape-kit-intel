"""Merge the scrape->export handoff records across chained runs.

raw_records.json is the handoff from a scrape invocation to build_dataset.
A chunked (--limit) or cron run only scrapes part of the catalog per
invocation; without merging, each run would overwrite the file and the
final dataset would contain only the last chunk. merge_records unions by
url so chained runs accumulate."""


def merge_records(existing, new):
    """Union `existing` and `new` by url. On collision the entry from `new`
    replaces the one in `existing` in place (a re-scrape refreshes price/stock);
    urls only in `new` are appended in order. Non-dict / url-less entries are
    dropped defensively."""
    def _ok(item):
        return isinstance(item, dict) and isinstance(item.get("url"), str)

    order = []
    by_url = {}
    for item in existing:
        if not _ok(item):
            continue
        if item["url"] not in by_url:
            order.append(item["url"])
        by_url[item["url"]] = item
    for item in new:
        if not _ok(item):
            continue
        if item["url"] not in by_url:
            order.append(item["url"])
        by_url[item["url"]] = item
    return [by_url[u] for u in order]
