import io
import urllib.error

import pytest

from jemscrape.fetch import probe, Probe
from jemscrape.errors import FetchError


class _Resp:
    def __init__(self, body, status=200, headers=None, url="https://x/p"):
        self._body = body.encode("utf-8")
        self.status = status
        self.headers = headers or {"Content-Type": "text/html"}
        self._url = url

    def read(self):
        return self._body

    def geturl(self):
        return self._url

    def close(self):
        pass


def test_probe_returns_status_headers_body_final_url():
    def fake_urlopen(request, timeout=None):
        return _Resp("<html>ok</html>", status=200,
                     headers={"CF-Ray": "abc", "Content-Type": "text/html"},
                     url="https://x/final")
    p = probe("https://x/p", user_agent="UA", urlopen=fake_urlopen)
    assert isinstance(p, Probe)
    assert p.status == 200
    assert p.body == "<html>ok</html>"
    assert p.final_url == "https://x/final"
    assert p.headers["cf-ray"] == "abc"          # keys lowercased


def test_probe_captures_http_error_status_without_raising():
    def fake_urlopen(request, timeout=None):
        raise urllib.error.HTTPError(
            "https://x/login", 403, "Forbidden",
            {"Content-Type": "text/html"}, io.BytesIO(b"denied"))
    p = probe("https://x/p", user_agent="UA", urlopen=fake_urlopen)
    assert p.status == 403
    assert "denied" in p.body


def test_probe_raises_fetcherror_on_network_error():
    def fake_urlopen(request, timeout=None):
        raise urllib.error.URLError("connection refused")
    with pytest.raises(FetchError):
        probe("https://x/p", user_agent="UA", urlopen=fake_urlopen)


def test_cookie_header_added_to_request():
    seen = {}

    def fake_urlopen(request, timeout=None):
        seen["cookie"] = request.get_header("Cookie")
        return _Resp("<h1>ok</h1>")

    p = probe("https://x/p", user_agent="UA", cookie_header="sid=abc; csrf=xyz",
             urlopen=fake_urlopen)
    assert p.status == 200
    assert seen["cookie"] == "sid=abc; csrf=xyz"


def test_no_cookie_header_when_absent():
    seen = {}

    def fake_urlopen(request, timeout=None):
        seen["cookie"] = request.get_header("Cookie")
        return _Resp("<h1>ok</h1>")

    probe("https://x/p", user_agent="UA", urlopen=fake_urlopen)
    assert seen["cookie"] is None
