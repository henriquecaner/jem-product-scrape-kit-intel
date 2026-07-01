import json
import os
import re
from pathlib import Path

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def atomic_write(path, text):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, p)


def slug_for(url):
    tail = url.rstrip("/").rsplit("/", 1)[-1] or url
    tail = tail.split("?", 1)[0].split("#", 1)[0]
    slug = _SAFE.sub("-", tail).strip("-")
    return slug or "index"


def cache_path(cache_dir, url):
    return Path(cache_dir) / f"{slug_for(url)}.html"


def is_cached(cache_dir, url):
    return cache_path(cache_dir, url).exists()


def read_cached(cache_dir, url):
    return cache_path(cache_dir, url).read_text(encoding="utf-8")


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
