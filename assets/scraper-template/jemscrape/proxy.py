"""Translate an HTTPS_PROXY URL into the dict Playwright expects on launch.
The HTTP path honors HTTPS_PROXY via urllib on its own; the browser path does
NOT — headless Chromium ignores the env var, so the proxy must go on
chromium.launch(proxy=...). This helper exists only for the browser path
(spec §5, references/geo-proxy.md)."""
from urllib.parse import urlsplit

from .errors import ConfigError


def proxy_dict_from_url(url):
    if not url or not url.strip():
        return None
    parts = urlsplit(url.strip())
    if not parts.hostname:
        raise ConfigError(f"proxy URL has no host: {url!r}")
    netloc = parts.hostname
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    d = {"server": f"{parts.scheme}://{netloc}"}
    if parts.username:
        d["username"] = parts.username
    if parts.password is not None:
        d["password"] = parts.password
    return d
