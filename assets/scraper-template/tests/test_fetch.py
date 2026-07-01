import urllib.error

import pytest

from jemscrape.fetch import fetch
from jemscrape.errors import FetchError


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
