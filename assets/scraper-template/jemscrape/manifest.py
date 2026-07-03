import json

from .cache import atomic_write, cache_path


class Manifest:
    def __init__(self, schema_version="1.0"):
        self.schema_version = schema_version
        self.scraped = []
        self.skipped = []
        self.errors = []

    def record_scraped(self, url, record):
        # record is always a dict here (parse_fn returns dict|None and None is
        # skipped, not scraped); copy it so later caller-side mutation of the
        # original dict can't leak into the stored manifest entry.
        self.scraped.append({"url": url, "record": dict(record)})

    def record_skipped(self, url, reason):
        self.skipped.append({"url": url, "reason": reason})

    def record_error(self, url, message):
        self.errors.append({"url": url, "message": message})

    def summary(self):
        return {"scraped": len(self.scraped), "skipped": len(self.skipped), "errors": len(self.errors)}

    def records_for_build(self, cache_dir=None):
        """Shape the scraped entries into the list build_dataset consumes:
        [{"url", "raw", "raw_ref"}]. This is the handoff from a scrape run to
        the normalize/export step. `raw_ref` is the cached HTML path when
        cache_dir is given, else "" ."""
        out = []
        for entry in self.scraped:
            raw_ref = str(cache_path(cache_dir, entry["url"])) if cache_dir is not None else ""
            out.append({"url": entry["url"], "raw": entry["record"], "raw_ref": raw_ref})
        return out

    def write(self, path):
        payload = {
            "schema_version": self.schema_version,
            "counts": self.summary(),
            "scraped": self.scraped,
            "skipped": self.skipped,
            "errors": self.errors,
        }
        atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2))
