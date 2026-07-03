"""Translate an HTTPS_PROXY URL into the dict Playwright expects on launch.
The HTTP path honors HTTPS_PROXY via urllib on its own; the browser path does
NOT — headless Chromium ignores the env var, so the proxy must go on
chromium.launch(proxy=...). This helper exists only for the browser path
(spec §5, references/geo-proxy.md)."""
from urllib.parse import urlsplit, unquote

from .errors import ConfigError


def proxy_dict_from_url(url):
    if not url or not url.strip():
        return None
    parts = urlsplit(url.strip())
    if not parts.hostname:
        # Never echo the raw URL or its netloc -- HTTPS_PROXY can carry
        # user:pass, and callers (scrape.py/warmup.py) print this to the
        # Actions log. Report only that it's malformed; scheme is not secret.
        raise ConfigError(
            f"HTTPS_PROXY is malformed: no host (scheme={parts.scheme!r}; "
            "credentials redacted)"
        )
    host = parts.hostname
    if ":" in host:  # IPv6 literal -- urlsplit strips the brackets
        host = f"[{host}]"
    netloc = host
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    d = {"server": f"{parts.scheme}://{netloc}"}
    if parts.username:
        d["username"] = unquote(parts.username)
    if parts.password is not None:
        d["password"] = unquote(parts.password)
    return d
