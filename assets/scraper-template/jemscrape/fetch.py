import time
import urllib.error
import urllib.request

from .errors import FetchError


def _default_urlopen(request, timeout=None):
    return urllib.request.urlopen(request, timeout=timeout)


def fetch(url, *, user_agent, timeout=30, retries=4,
          backoff_sleep=time.sleep, urlopen=_default_urlopen):
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            resp = urlopen(request, timeout=timeout)
            try:
                body = resp.read()
            finally:
                close = getattr(resp, "close", None)
                if close:
                    close()
            return body.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code == 429:
                backoff_sleep(90 * attempt)  # long backoff for rate limiting
            else:
                backoff_sleep(10 * attempt)
        except urllib.error.URLError as exc:
            last_exc = exc
            backoff_sleep(10 * attempt)
    raise FetchError(f"failed to fetch {url} after {retries} attempts: {last_exc}")
