import urllib.error

import pytest

from jemscrape.fetch import fetch
from jemscrape.errors import FetchError, AuthExpiredError


class FakeResp:
    def __init__(self, body, status=200):
        self._body = body.encode("utf-8")
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_success_returns_text():
    def urlopen(req, timeout=None):
        return FakeResp("<html>ok</html>")

    out = fetch("https://x/1", user_agent="UA", urlopen=urlopen, backoff_sleep=lambda s: None)
    assert out == "<html>ok</html>"


def test_retries_then_succeeds():
    calls = {"n": 0}

    def urlopen(req, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib.error.URLError("boom")
        return FakeResp("done")

    out = fetch("https://x/1", user_agent="UA", retries=4,
                urlopen=urlopen, backoff_sleep=lambda s: None)
    assert out == "done"
    assert calls["n"] == 3


def test_429_uses_longer_backoff_then_gives_up():
    slept = []

    def urlopen(req, timeout=None):
        raise urllib.error.HTTPError("https://x", 429, "Too Many Requests", {}, None)

    with pytest.raises(FetchError):
        fetch("https://x/1", user_agent="UA", retries=2,
              urlopen=urlopen, backoff_sleep=slept.append)
    # 429 backoff is the long schedule (90s * attempt), not the short one
    assert slept and min(slept) >= 90


def test_exhausts_retries_raises():
    def urlopen(req, timeout=None):
        raise urllib.error.URLError("always down")

    with pytest.raises(FetchError):
        fetch("https://x/1", user_agent="UA", retries=3,
              urlopen=urlopen, backoff_sleep=lambda s: None)


def test_sets_user_agent_header():
    seen = {}

    def urlopen(req, timeout=None):
        seen["ua"] = req.get_header("User-agent")
        return FakeResp("ok")

    fetch("https://x/1", user_agent="MyUA/9", urlopen=urlopen, backoff_sleep=lambda s: None)
    assert seen["ua"] == "MyUA/9"


class _Resp:
    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def close(self):
        pass


def test_cookie_header_added_to_request():
    seen = {}

    def fake_urlopen(request, timeout=None):
        seen["cookie"] = request.get_header("Cookie")
        return _Resp(b"<h1>ok</h1>")

    html = fetch("https://x/p", user_agent="UA", cookie_header="sid=abc; csrf=xyz",
                 urlopen=fake_urlopen)
    assert html == "<h1>ok</h1>"
    assert seen["cookie"] == "sid=abc; csrf=xyz"


def test_no_cookie_header_when_absent():
    seen = {}

    def fake_urlopen(request, timeout=None):
        seen["cookie"] = request.get_header("Cookie")
        return _Resp(b"<h1>ok</h1>")

    fetch("https://x/p", user_agent="UA", urlopen=fake_urlopen)
    assert seen["cookie"] is None


@pytest.mark.parametrize("code", [401, 403])
def test_401_403_raise_auth_expired_without_retry(code):
    calls = {"n": 0}

    def fake_urlopen(request, timeout=None):
        calls["n"] += 1
        raise urllib.error.HTTPError("https://x/p", code, "denied", {}, None)

    with pytest.raises(AuthExpiredError):
        fetch("https://x/p", user_agent="UA", urlopen=fake_urlopen,
              backoff_sleep=lambda s: None)
    assert calls["n"] == 1  # no retry
