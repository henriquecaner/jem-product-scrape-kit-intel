import json

from .cache import atomic_write


class Manifest:
    def __init__(self, schema_version="1.0"):
        self.schema_version = schema_version
        self.scraped = []
        self.skipped = []
        self.errors = []

    def record_scraped(self, url, record):
        self.scraped.append({"url": url, "record": record})

    def record_skipped(self, url, reason):
        self.skipped.append({"url": url, "reason": reason})

    def record_error(self, url, message):
        self.errors.append({"url": url, "message": message})

    def summary(self):
        return {"scraped": len(self.scraped), "skipped": len(self.skipped), "errors": len(self.errors)}

    def write(self, path):
        payload = {
            "schema_version": self.schema_version,
            "counts": self.summary(),
            "scraped": self.scraped,
            "skipped": self.skipped,
            "errors": self.errors,
        }
        atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2))
