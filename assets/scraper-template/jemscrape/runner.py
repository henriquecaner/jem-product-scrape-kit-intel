from . import cache as cache_mod
from .errors import AuthExpiredError


def run(*, urls, parse_fn, cache_dir, fetcher, pacer, cursor, manifest, reparse=False):
    for url in urls:
        if cursor.done(url):
            continue
        try:
            if cache_mod.is_cached(cache_dir, url) and not reparse:
                html = cache_mod.read_cached(cache_dir, url)
            else:
                html = fetcher(url)
                cache_mod.atomic_write(cache_mod.cache_path(cache_dir, url), html)
                pacer.wait()
        except AuthExpiredError:
            # Fatal to the whole run: the token is dead. Do NOT mark this URL
            # done (it must be retried after renewal) and do NOT swallow it —
            # scrape.py catches it, alerts, and exits non-zero. The cursor
            # already holds progress from prior URLs (saved each iteration).
            raise
        except Exception as exc:  # fetch/cache failure: record and move on
            # Intentional design: an errored URL is marked done in the cursor
            # and is NOT retried on a later resume run — fetch() already
            # retries internally, so a persisted error is treated as final.
            manifest.record_error(url, str(exc))
            cursor.add(url)
            cursor.save()
            continue

        record = parse_fn(html, url)
        if record is None:
            manifest.record_skipped(url, "parse returned no record")
        else:
            manifest.record_scraped(url, record)
        cursor.add(url)
        cursor.save()
    return manifest.summary()
