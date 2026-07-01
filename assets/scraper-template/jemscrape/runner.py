from . import cache as cache_mod


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
        except Exception as exc:  # fetch/cache failure: record and move on
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
