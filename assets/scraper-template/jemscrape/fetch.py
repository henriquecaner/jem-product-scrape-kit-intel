import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from .errors import FetchError, AuthExpiredError


def _default_urlopen(request, timeout=None):
    return urllib.request.urlopen(request, timeout=timeout)


def fetch(url, *, user_agent, cookie_header=None, timeout=30, retries=4,
          backoff_sleep=time.sleep, urlopen=_default_urlopen):
    headers = {"User-Agent": user_agent}
    if cookie_header:
        headers["Cookie"] = cookie_header
    request = urllib.request.Request(url, headers=headers)
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
            if exc.code in (401, 403):
                # Token is dead — retrying won't fix it and can burn the session.
                raise AuthExpiredError(
                    f"auth failed ({exc.code}) fetching {url}: session token expired") from exc
            if exc.code == 429:
                backoff_sleep(90 * attempt)  # long backoff for rate limiting
            else:
                backoff_sleep(10 * attempt)
        except urllib.error.URLError as exc:
            last_exc = exc
            backoff_sleep(10 * attempt)
    raise FetchError(f"failed to fetch {url} after {retries} attempts: {last_exc}")


@dataclass
class Probe:
    status: int
    headers: dict          # header name (lowercased) -> value
    body: str
    final_url: str


def _headers_to_dict(headers):
    out = {}
    if headers:
        for k, v in headers.items():
            out[k.lower()] = v
    return out


def probe(url, *, user_agent, cookie_header=None, timeout=30, urlopen=_default_urlopen):
    headers = {"User-Agent": user_agent}
    if cookie_header:
        headers["Cookie"] = cookie_header
    request = urllib.request.Request(url, headers=headers)
    try:
        resp = urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read()
        except Exception:
            raw = b""
        return Probe(
            status=exc.code,
            headers=_headers_to_dict(getattr(exc, "headers", None)),
            body=raw.decode("utf-8", errors="replace"),
            final_url=getattr(exc, "url", url) or url,
        )
    except urllib.error.URLError as exc:
        raise FetchError(f"network error probing {url}: {exc}") from exc
    try:
        raw = resp.read()
    finally:
        close = getattr(resp, "close", None)
        if close:
            close()
    status = getattr(resp, "status", None)
    if status is None:
        getcode = getattr(resp, "getcode", None)
        status = getcode() if getcode else 200
    geturl = getattr(resp, "geturl", None)
    final_url = geturl() if geturl else url
    return Probe(
        status=status,
        headers=_headers_to_dict(getattr(resp, "headers", None)),
        body=raw.decode("utf-8", errors="replace"),
        final_url=final_url,
    )
