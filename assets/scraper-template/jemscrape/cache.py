import hashlib
import json
import os
import re
from pathlib import Path

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")
_READABLE_MAX = 80


def atomic_write(path, text):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, p)


def slug_for(url):
    # Readable prefix (last path segment) is NOT unique on its own — different
    # URLs can share a tail (e.g. /A/widget-1 vs /B/widget-1, or ?id=1 vs ?id=2).
    # A short hash of the full URL is appended to keep the mapping injective and
    # avoid silent cache collisions between distinct URLs.
    tail = url.rstrip("/").rsplit("/", 1)[-1] or url
    tail = tail.split("?", 1)[0].split("#", 1)[0]
    readable = _SAFE.sub("-", tail).strip("-") or "index"
    # Cap the human-readable portion so a pathologically long path segment
    # doesn't blow past OS filename limits (~255 bytes) -- the sha below
    # keeps the result unique regardless of how much of the tail survives.
    readable = readable[:_READABLE_MAX].strip("-") or "index"
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    return f"{readable}-{digest}"


def cache_path(cache_dir, url):
    return Path(cache_dir) / f"{slug_for(url)}.html"


def is_cached(cache_dir, url):
    return cache_path(cache_dir, url).exists()


def read_cached(cache_dir, url):
    return cache_path(cache_dir, url).read_text(encoding="utf-8", errors="replace")


class Cursor:
    def __init__(self, path):
        self.path = Path(path)
        self._done = set()

    def load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                done = data.get("done", []) if isinstance(data, dict) else []
                self._done = set(done) if isinstance(done, list) else set()
            except (OSError, json.JSONDecodeError):
                self._done = set()
        return self

    def done(self, url):
        return url in self._done

    def add(self, url):
        self._done.add(url)

    def save(self):
        atomic_write(self.path, json.dumps({"done": sorted(self._done)}, ensure_ascii=False, indent=2))
