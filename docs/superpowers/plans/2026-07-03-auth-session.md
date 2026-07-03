# Auth Session + Geo on GitHub Actions Implementation Plan (Plano 3b)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bridge a locally-captured browser session to an unsupervised, geo-routed run on GitHub Actions (spec §5.1) — replay cookies/storage on the runner, fail closed the moment the token dies, and egress through the country proxy on both the HTTP and browser fetch paths.

**Architecture:** Two new stdlib modules carry the testable logic — `jemscrape/session.py` (parse the Playwright `storage_state`; emit a `Cookie` header for the HTTP path, the raw storage dict for the browser path, and the token's validity) and `jemscrape/proxy.py` (translate `HTTPS_PROXY` into the Playwright launch dict). A new `AuthExpiredError` makes a 401/403 abort the run instead of being retried or swallowed. The local capture (`drivers/auth_capture.py`, headed Chromium) stays behind the same Playwright guard as the existing render driver. Wiring threads the session/proxy through `scrape.py`, `warmup.py`, `actions_setup.py`, `deploy_actions.py`, and the `scrape.yml` template — always fail-closed, secret never on argv, gate files never in the repo.

**Tech Stack:** Python 3 stdlib for the core (`jemscrape/`) and the root CLIs; Playwright (Chromium) only in `drivers/`, guarded. Tests via `pytest` (`.venv/bin/python -m pytest`).

## Global Constraints

- **stdlib-only core.** No third-party imports anywhere under `jemscrape/` or in the root CLIs (`scrape.py`, `warmup.py`, `auth_capture.py`, `actions_setup.py`, `build_dataset.py`). Playwright is imported ONLY in `assets/scraper-template/drivers/*.py`, behind a guarded `try/except ImportError`; root CLIs import the driver lazily inside `main()`.
- **Dependency injection for tests.** `session.py`/`proxy.py` are tested with JSON fixtures and strings. Fetch/runner/CLI tests inject fakes and NEVER open a socket or launch a browser.
- **Fail-closed everywhere.** Session absent/expired aborts before any fetch (exit 2). A 401/403 mid-run raises `AuthExpiredError`, which aborts the run, persists the cursor, alerts, and returns non-zero. The secret never appears on argv and gate files are never committed.
- **Reuse existing contracts.** Runner takes `fetcher(url) -> html`; warm-up takes `probe_fn(url) -> Probe`; `Probe(status, headers, body, final_url)` from `jemscrape.fetch`; `build_fetcher`/`build_pacer` in `scrape.py`; `secrets_io.materialize_secret`; `deploy_actions.build_secret_commands`.
- **`auth_required` defaults off.** When absent or `false`, the public path is byte-for-byte unchanged. Everything auth-related is opt-in via config.
- **Baseline:** `.venv/bin/python -m pytest -q` → 204 passing + 1 skip. Keep green + pristine after every task.
- **Run pytest from the repo root** (`pyproject.toml` points `testpaths`/`pythonpath` at `assets/scraper-template`).
- **Commits** use conventional prefixes and end with the trailer `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Update `CHANGELOG.md` on relevant changes.

## File Structure

- `assets/scraper-template/jemscrape/errors.py` — MODIFY: add `SessionError`, `AuthExpiredError`.
- `assets/scraper-template/jemscrape/session.py` — CREATE: `load_session`, `Session` (cookie_header, storage_state, expires_at, is_expired).
- `assets/scraper-template/jemscrape/proxy.py` — CREATE: `proxy_dict_from_url`.
- `assets/scraper-template/jemscrape/fetch.py` — MODIFY: `fetch(..., cookie_header=None)`; raise `AuthExpiredError` on 401/403 without retry.
- `assets/scraper-template/jemscrape/runner.py` — MODIFY: let `AuthExpiredError` propagate (don't swallow as a per-URL error).
- `assets/scraper-template/jemscrape/config.py` — MODIFY: validate `auth_required` (bool) and `login_url` (required when auth_required).
- `assets/scraper-template/drivers/playwright_render.py` — MODIFY: `render(..., storage_state=None)`.
- `assets/scraper-template/drivers/auth_capture.py` — CREATE: guarded `capture_session(...)`, headed.
- `assets/scraper-template/auth_capture.py` — CREATE: root CLI (stdlib top-level, lazy driver import).
- `assets/scraper-template/scrape.py` — MODIFY: session preflight; `build_fetcher(..., session=None)`; catch `AuthExpiredError` in `main()`.
- `assets/scraper-template/warmup.py` — MODIFY: session preflight + injection for the auth path.
- `assets/scraper-template/actions_setup.py` — MODIFY: conditional `SCRAPE_STORAGE_STATE` target when `auth_required`.
- `assets/scraper-template/drivers/deploy_actions.py` — MODIFY: add `.scrape-session.json` to the secret map.
- `assets/github-actions/scrape.yml` — MODIFY: materialize `SCRAPE_STORAGE_STATE`; ensure `HTTPS_PROXY` reaches the scrape step (already present).
- `assets/project-skeleton/.gitignore` — MODIFY: add `.scrape-session.json`.
- `assets/scraper-template/config.json.example` — MODIFY: document `auth_required`/`login_url` (commented via extra keys is not valid JSON, so keep them present with safe defaults).
- `hooks/scripts/precheck.py` — MODIFY: add `.scrape-session.json` to `_SECRET_MARKERS`.
- `references/auth-session.md` — CREATE: the daily refresh ritual + VM-promotion trigger.
- Tests: `tests/test_session.py`, `tests/test_proxy.py`, `tests/test_auth_capture.py` (new); additions to `tests/test_fetch.py`, `tests/test_runner.py`, `tests/test_config.py`, `tests/test_build_fetcher.py`, `tests/test_actions_setup.py`, `tests/test_deploy_actions.py`, `tests/test_actions_workflow.py`, `tests/test_warmup_cli.py`, `tests/test_config_example.py`, `tests/test_precheck_hook.py`.

---

### Task 1: New exceptions (`SessionError`, `AuthExpiredError`)

**Files:**
- Modify: `assets/scraper-template/jemscrape/errors.py`
- Test: `tests/test_session.py` (created here; grows in Task 2)

**Interfaces:**
- Produces: `SessionError(Exception)`, `AuthExpiredError(Exception)` in `jemscrape.errors`.

- [ ] **Step 1: Write the failing test**

Create `assets/scraper-template/tests/test_session.py`:

```python
from jemscrape.errors import SessionError, AuthExpiredError


def test_session_and_auth_exceptions_exist_and_are_exceptions():
    assert issubclass(SessionError, Exception)
    assert issubclass(AuthExpiredError, Exception)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_session.py -q`
Expected: FAIL — `ImportError: cannot import name 'SessionError'`.

- [ ] **Step 3: Write minimal implementation**

Append to `assets/scraper-template/jemscrape/errors.py`:

```python
class SessionError(Exception):
    """Raised when .scrape-session.json is missing, malformed, or has no cookies."""


class AuthExpiredError(Exception):
    """Raised when the site returns 401/403 — the session token is dead.
    Fatal to the run: not retried, not swallowed as a per-URL error."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_session.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/errors.py assets/scraper-template/tests/test_session.py
git commit -m "feat(3b): add SessionError and AuthExpiredError

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `jemscrape/session.py` — parse storage_state

**Files:**
- Create: `assets/scraper-template/jemscrape/session.py`
- Test: `assets/scraper-template/tests/test_session.py`

**Interfaces:**
- Consumes: `SessionError` from `jemscrape.errors` (Task 1).
- Produces:
  - `load_session(path) -> Session`
  - `Session.cookie_header(domain: str) -> str` — `"name=value; name2=value2"` for matching, unexpired cookies; `""` if none.
  - `Session.storage_state -> dict` — the raw storage_state dict.
  - `Session.expires_at(now=None) -> datetime | None` — earliest non-session cookie expiry as an aware UTC datetime; `None` if all cookies are session cookies (`expires` in {-1, 0, missing}).
  - `Session.is_expired(now: datetime) -> bool` — `True` iff `expires_at()` exists and `<= now`.

The Playwright `storage_state` shape (fixture used by the tests):

```python
def _storage_state(expires):
    return {
        "cookies": [
            {"name": "sid", "value": "abc", "domain": "shop.example.com",
             "path": "/", "expires": expires, "httpOnly": True, "secure": True,
             "sameSite": "Lax"},
            {"name": "csrf", "value": "xyz", "domain": ".example.com",
             "path": "/", "expires": -1, "httpOnly": False, "secure": True,
             "sameSite": "Strict"},
        ],
        "origins": [{"origin": "https://shop.example.com",
                     "localStorage": [{"name": "k", "value": "v"}]}],
    }
```

- [ ] **Step 1: Write the failing tests**

Append to `assets/scraper-template/tests/test_session.py`:

```python
import json
from datetime import datetime, timezone

import pytest

from jemscrape import session as sess


def _storage_state(expires):
    return {
        "cookies": [
            {"name": "sid", "value": "abc", "domain": "shop.example.com",
             "path": "/", "expires": expires, "httpOnly": True, "secure": True,
             "sameSite": "Lax"},
            {"name": "csrf", "value": "xyz", "domain": ".example.com",
             "path": "/", "expires": -1, "httpOnly": False, "secure": True,
             "sameSite": "Strict"},
        ],
        "origins": [{"origin": "https://shop.example.com",
                     "localStorage": [{"name": "k", "value": "v"}]}],
    }


def _write(tmp_path, obj):
    p = tmp_path / ".scrape-session.json"
    p.write_text(json.dumps(obj), encoding="utf-8")
    return p


FUTURE = 4102444800  # 2100-01-01 UTC
PAST = 1000000000    # 2001-09-09 UTC


def test_load_missing_file_raises_session_error(tmp_path):
    with pytest.raises(sess.SessionError):
        sess.load_session(tmp_path / "nope.json")


def test_load_malformed_json_raises_session_error(tmp_path):
    p = tmp_path / ".scrape-session.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(sess.SessionError):
        sess.load_session(p)


def test_load_no_cookies_raises_session_error(tmp_path):
    p = _write(tmp_path, {"cookies": [], "origins": []})
    with pytest.raises(sess.SessionError):
        sess.load_session(p)


def test_cookie_header_matches_domain_and_skips_expired(tmp_path):
    s = sess.load_session(_write(tmp_path, _storage_state(FUTURE)))
    header = s.cookie_header("shop.example.com")
    # both cookies apply to shop.example.com (exact + dot-suffix), unexpired
    assert header == "sid=abc; csrf=xyz"


def test_cookie_header_expired_cookie_dropped(tmp_path):
    s = sess.load_session(_write(tmp_path, _storage_state(PAST)))
    header = s.cookie_header("shop.example.com")
    # sid expired in the past -> only the session cookie csrf remains
    assert header == "csrf=xyz"


def test_cookie_header_unrelated_domain_returns_empty(tmp_path):
    s = sess.load_session(_write(tmp_path, _storage_state(FUTURE)))
    assert s.cookie_header("other.test") == ""


def test_storage_state_is_raw_dict(tmp_path):
    obj = _storage_state(FUTURE)
    s = sess.load_session(_write(tmp_path, obj))
    assert s.storage_state == obj


def test_expires_at_is_earliest_non_session_cookie(tmp_path):
    s = sess.load_session(_write(tmp_path, _storage_state(FUTURE)))
    assert s.expires_at() == datetime.fromtimestamp(FUTURE, tz=timezone.utc)


def test_expires_at_none_when_all_session_cookies(tmp_path):
    obj = {"cookies": [{"name": "a", "value": "b", "domain": "x.com",
                        "path": "/", "expires": -1}], "origins": []}
    s = sess.load_session(_write(tmp_path, obj))
    assert s.expires_at() is None


def test_is_expired_true_for_past(tmp_path):
    s = sess.load_session(_write(tmp_path, _storage_state(PAST)))
    now = datetime.now(timezone.utc)
    assert s.is_expired(now) is True


def test_is_expired_false_when_no_expiry(tmp_path):
    obj = {"cookies": [{"name": "a", "value": "b", "domain": "x.com",
                        "path": "/", "expires": -1}], "origins": []}
    s = sess.load_session(_write(tmp_path, obj))
    assert s.is_expired(datetime.now(timezone.utc)) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_session.py -q`
Expected: FAIL — `AttributeError`/`ImportError` (`load_session` not defined; `sess.SessionError` missing).

- [ ] **Step 3: Write minimal implementation**

Create `assets/scraper-template/jemscrape/session.py`:

```python
"""Parse a Playwright storage_state (the single source of a captured session):
emit a Cookie header for the HTTP path, the raw storage dict for the browser
path, and the token's validity. Stdlib only; token validity is kept distinct
from run progress (the cursor owns progress). Spec §5.1."""
import json
from datetime import datetime, timezone
from pathlib import Path

from .errors import SessionError

# Re-export so callers can `from jemscrape import session; session.SessionError`.
SessionError = SessionError


def _domain_matches(cookie_domain, target):
    """Cookie domain rule: a leading-dot domain matches the host and any
    subdomain; a bare domain matches that exact host."""
    cd = (cookie_domain or "").lower().lstrip(".")
    target = (target or "").lower()
    return target == cd or target.endswith("." + cd)


class Session:
    def __init__(self, raw):
        self._raw = raw
        self._cookies = raw.get("cookies") or []

    @property
    def storage_state(self):
        return self._raw

    def cookie_header(self, domain):
        now = datetime.now(timezone.utc).timestamp()
        parts = []
        for c in self._cookies:
            if not _domain_matches(c.get("domain"), domain):
                continue
            expires = c.get("expires", -1)
            if isinstance(expires, (int, float)) and expires > 0 and expires <= now:
                continue  # expired
            parts.append(f"{c['name']}={c['value']}")
        return "; ".join(parts)

    def expires_at(self, now=None):
        stamps = [c.get("expires") for c in self._cookies
                  if isinstance(c.get("expires"), (int, float)) and c.get("expires") > 0]
        if not stamps:
            return None
        return datetime.fromtimestamp(min(stamps), tz=timezone.utc)

    def is_expired(self, now):
        exp = self.expires_at()
        return exp is not None and exp <= now


def load_session(path):
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SessionError(f"cannot read session at {p}: {exc}") from exc
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SessionError(f"session at {p} is not valid JSON: {exc}") from exc
    if not isinstance(obj, dict) or not obj.get("cookies"):
        raise SessionError(f"session at {p} has no cookies")
    return Session(obj)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_session.py -q`
Expected: PASS (all session tests).

- [ ] **Step 5: Full suite stays green**

Run: `.venv/bin/python -m pytest -q`
Expected: 204 passing + new session tests, 1 skip.

- [ ] **Step 6: Commit**

```bash
git add assets/scraper-template/jemscrape/session.py assets/scraper-template/tests/test_session.py
git commit -m "feat(3b): jemscrape/session.py — parse Playwright storage_state

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `jemscrape/proxy.py` — HTTPS_PROXY → Playwright launch dict

**Files:**
- Create: `assets/scraper-template/jemscrape/proxy.py`
- Test: `assets/scraper-template/tests/test_proxy.py`

**Interfaces:**
- Consumes: `ConfigError` from `jemscrape.errors`.
- Produces: `proxy_dict_from_url(url: str | None) -> dict | None` — `{"server": "http://host:port", "username": ..., "password": ...}` (username/password keys only when present); `None` for empty/None input; raises `ConfigError` for a URL with no host.

- [ ] **Step 1: Write the failing tests**

Create `assets/scraper-template/tests/test_proxy.py`:

```python
import pytest

from jemscrape.proxy import proxy_dict_from_url
from jemscrape.errors import ConfigError


def test_none_and_empty_return_none():
    assert proxy_dict_from_url(None) is None
    assert proxy_dict_from_url("") is None
    assert proxy_dict_from_url("   ") is None


def test_plain_proxy_no_credentials():
    d = proxy_dict_from_url("http://gw.proxy.uk:8080")
    assert d == {"server": "http://gw.proxy.uk:8080"}


def test_proxy_with_credentials_splits_them_out():
    d = proxy_dict_from_url("http://user:pass@gw.proxy.uk:8080")
    assert d == {"server": "http://gw.proxy.uk:8080",
                 "username": "user", "password": "pass"}


def test_https_scheme_preserved():
    d = proxy_dict_from_url("https://gw.proxy.uk:443")
    assert d["server"] == "https://gw.proxy.uk:443"


def test_invalid_url_without_host_raises():
    with pytest.raises(ConfigError):
        proxy_dict_from_url("http://:8080")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_proxy.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'jemscrape.proxy'`.

- [ ] **Step 3: Write minimal implementation**

Create `assets/scraper-template/jemscrape/proxy.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_proxy.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/proxy.py assets/scraper-template/tests/test_proxy.py
git commit -m "feat(3b): jemscrape/proxy.py — HTTPS_PROXY to Playwright launch dict

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `fetch.py` — Cookie header + fail-closed 401/403

**Files:**
- Modify: `assets/scraper-template/jemscrape/fetch.py`
- Test: `assets/scraper-template/tests/test_fetch.py`

**Interfaces:**
- Consumes: `AuthExpiredError` from `jemscrape.errors` (Task 1).
- Produces: `fetch(url, *, user_agent, cookie_header=None, timeout=30, retries=4, backoff_sleep=..., urlopen=...)` — adds a `Cookie` header when `cookie_header` is truthy; raises `AuthExpiredError` immediately (no retry, no backoff) on HTTP 401/403.

- [ ] **Step 1: Write the failing tests**

Append to `assets/scraper-template/tests/test_fetch.py`:

```python
import urllib.error

import pytest

from jemscrape.fetch import fetch
from jemscrape.errors import AuthExpiredError


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_fetch.py -q`
Expected: FAIL — `fetch()` has no `cookie_header` kwarg / 401 currently retried into `FetchError`.

- [ ] **Step 3: Write minimal implementation**

In `assets/scraper-template/jemscrape/fetch.py`, add the import and update `fetch`:

```python
from .errors import FetchError, AuthExpiredError
```

Replace the `fetch` function signature and body head:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_fetch.py -q`
Expected: PASS.

- [ ] **Step 5: Full suite green**

Run: `.venv/bin/python -m pytest -q`
Expected: green (no regressions in `test_probe.py` — `probe()` is untouched).

- [ ] **Step 6: Commit**

```bash
git add assets/scraper-template/jemscrape/fetch.py assets/scraper-template/tests/test_fetch.py
git commit -m "feat(3b): fetch() Cookie header + fail-closed AuthExpiredError on 401/403

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: `runner.py` — let `AuthExpiredError` propagate

**Files:**
- Modify: `assets/scraper-template/jemscrape/runner.py`
- Test: `assets/scraper-template/tests/test_runner.py`

**Interfaces:**
- Consumes: `AuthExpiredError` from `jemscrape.errors`.
- Produces: unchanged `run(...)` signature; behavior change — a fatal `AuthExpiredError` from the fetcher propagates out of `run()` instead of being recorded as a per-URL error. `FetchError` and other exceptions keep the current record-and-continue behavior.

- [ ] **Step 1: Write the failing tests**

Append to `assets/scraper-template/tests/test_runner.py`:

```python
from jemscrape.errors import AuthExpiredError, FetchError


def test_auth_expired_propagates_and_persists_cursor(tmp_path):
    from jemscrape.cache import Cursor
    cur = Cursor(tmp_path / "state" / "cursor.json").load()

    def fetcher(url):
        raise AuthExpiredError("token dead")

    with __import__("pytest").raises(AuthExpiredError):
        run(urls=["https://x/1"], parse_fn=_parse, cache_dir=tmp_path / "data",
            fetcher=fetcher, pacer=_pacer(), cursor=cur, manifest=Manifest())
    # x/1 was NOT marked done — it must be retried after the session is renewed
    assert not cur.done("https://x/1")


def test_fetch_error_still_recorded_and_continues(tmp_path):
    from jemscrape.cache import Cursor
    cur = Cursor(tmp_path / "state" / "cursor.json").load()
    seen = []

    def fetcher(url):
        seen.append(url)
        if url.endswith("/1"):
            raise FetchError("boom")
        return "product page"

    m = Manifest()
    summary = run(urls=["https://x/1", "https://x/2"], parse_fn=_parse,
                  cache_dir=tmp_path / "data", fetcher=fetcher, pacer=_pacer(),
                  cursor=cur, manifest=m)
    assert seen == ["https://x/1", "https://x/2"]  # kept going after the error
    assert summary["errors"] == 1
    assert summary["scraped"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_runner.py -q`
Expected: FAIL — `AuthExpiredError` is currently swallowed by `except Exception`, so it's recorded and `x/1` is marked done (no raise).

- [ ] **Step 3: Write minimal implementation**

In `assets/scraper-template/jemscrape/runner.py`, add the import at the top:

```python
from . import cache as cache_mod
from .errors import AuthExpiredError
```

Change the `except Exception as exc:` block to re-raise the fatal case first:

```python
        except AuthExpiredError:
            # Fatal to the whole run: the token is dead. Do NOT mark this URL
            # done (it must be retried after renewal) and do NOT swallow it —
            # scrape.py catches it, alerts, and exits non-zero. The cursor
            # already holds progress from prior URLs (saved each iteration).
            raise
        except Exception as exc:  # fetch/cache failure: record and move on
            manifest.record_error(url, str(exc))
            cursor.add(url)
            cursor.save()
            continue
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_runner.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/runner.py assets/scraper-template/tests/test_runner.py
git commit -m "feat(3b): runner propagates AuthExpiredError instead of swallowing it

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: `config.py` — validate `auth_required` / `login_url`

**Files:**
- Modify: `assets/scraper-template/jemscrape/config.py`
- Test: `assets/scraper-template/tests/test_config.py`

**Interfaces:**
- Produces: `validate_config` additionally requires `auth_required` (bool, optional, default treated as false) and, when `auth_required` is `true`, `login_url` (non-empty string).

- [ ] **Step 1: Write the failing tests**

Append to `assets/scraper-template/tests/test_config.py` (reuse the existing `_valid()` helper if present; otherwise inline a minimal valid config):

```python
import pytest
from jemscrape.config import validate_config
from jemscrape.errors import ConfigError


def _base():
    return {"target_domain": "x.com", "runtime": "local",
            "user_agent": "UA", "rate_limit_floor_seconds": 2.5}


def test_auth_required_must_be_bool():
    cfg = _base()
    cfg["auth_required"] = "yes"
    with pytest.raises(ConfigError):
        validate_config(cfg)


def test_auth_required_true_requires_login_url():
    cfg = _base()
    cfg["auth_required"] = True   # no login_url
    with pytest.raises(ConfigError):
        validate_config(cfg)


def test_auth_required_true_with_login_url_ok():
    cfg = _base()
    cfg["auth_required"] = True
    cfg["login_url"] = "https://x.com/login"
    validate_config(cfg)  # must not raise


def test_auth_required_absent_is_fine():
    validate_config(_base())  # unchanged public path
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_config.py -q`
Expected: FAIL — no validation for `auth_required` yet (the string "yes" is accepted).

- [ ] **Step 3: Write minimal implementation**

In `assets/scraper-template/jemscrape/config.py`, inside `validate_config`, before the final `if errors:` block, add:

```python
    auth_required = cfg.get("auth_required")
    if auth_required is not None and not isinstance(auth_required, bool):
        errors.append("auth_required: must be a boolean if set")
    if auth_required is True:
        login_url = cfg.get("login_url")
        if not isinstance(login_url, str) or not login_url.strip():
            errors.append("login_url: required non-empty string when auth_required is true")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_config.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/config.py assets/scraper-template/tests/test_config.py
git commit -m "feat(3b): config validates auth_required/login_url

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: `build_fetcher` — inject cookie (HTTP) / storage_state + proxy (browser)

**Files:**
- Modify: `assets/scraper-template/scrape.py` (`build_fetcher` only)
- Modify: `assets/scraper-template/drivers/playwright_render.py` (add `storage_state`)
- Test: `assets/scraper-template/tests/test_build_fetcher.py`

**Interfaces:**
- Consumes: `Session` (Task 2), `proxy_dict_from_url` (Task 3), `make_browser_fetcher` (existing).
- Produces:
  - `build_fetcher(cfg, *, http_fetch, render_fn=None, session=None)` — HTTP mode passes `cookie_header=session.cookie_header(cfg["target_domain"])` when `session` is set; browser mode's default `render_fn` passes `storage_state=session.storage_state` and `proxy=proxy_dict_from_url(os.environ.get("HTTPS_PROXY"))`.
  - `render(url, *, timeout=30000, proxy=None, user_agent=None, storage_state=None) -> RenderedResult`.

- [ ] **Step 1: Write the failing tests**

Append to `assets/scraper-template/tests/test_build_fetcher.py`:

```python
from jemscrape.session import Session


def test_http_mode_injects_cookie_header_from_session():
    seen = {}

    def fake_http(url, *, user_agent, cookie_header=None):
        seen["cookie"] = cookie_header
        return "<h1>ok</h1>"

    session = Session({"cookies": [
        {"name": "sid", "value": "abc", "domain": "x.com", "expires": -1}]})
    fetcher = scrape.build_fetcher(
        {"user_agent": "UA", "target_domain": "x.com"},
        http_fetch=fake_http, session=session)
    assert fetcher("https://x.com/p") == "<h1>ok</h1>"
    assert seen["cookie"] == "sid=abc"


def test_http_mode_without_session_sends_no_cookie():
    seen = {}

    def fake_http(url, *, user_agent, cookie_header=None):
        seen["cookie"] = cookie_header
        return "<h1>ok</h1>"

    fetcher = scrape.build_fetcher(
        {"user_agent": "UA", "target_domain": "x.com"}, http_fetch=fake_http)
    fetcher("https://x.com/p")
    assert seen["cookie"] is None


def test_browser_mode_render_fn_receives_storage_state():
    captured = {}

    def fake_render(url):
        captured["url"] = url
        return RenderedResult(status=200, html="<h1>r</h1>", final_url=url)

    session = Session({"cookies": [
        {"name": "sid", "value": "abc", "domain": "x.com", "expires": -1}],
        "origins": []})
    fetcher = scrape.build_fetcher(
        {"user_agent": "UA", "fetch_mode": "browser", "target_domain": "x.com"},
        http_fetch=lambda *a, **k: None, render_fn=fake_render, session=session)
    assert fetcher("https://x.com/p") == "<h1>r</h1>"
```

Also add a driver test in `assets/scraper-template/tests/test_playwright_render.py` (guard-level, no browser):

```python
def test_render_accepts_storage_state_kwarg():
    import inspect
    from drivers.playwright_render import render
    sig = inspect.signature(render)
    assert "storage_state" in sig.parameters
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_build_fetcher.py assets/scraper-template/tests/test_playwright_render.py -q`
Expected: FAIL — `build_fetcher` has no `session` kwarg; `render` has no `storage_state`.

- [ ] **Step 3: Write minimal implementation**

In `assets/scraper-template/scrape.py`, add `import os` at the top and replace `build_fetcher`:

```python
def build_fetcher(cfg, *, http_fetch, render_fn=None, session=None):
    """Select the run fetcher by fetch_mode. Browser mode wraps a render_fn
    (Playwright) into the runner's fetcher(url)->html contract; default is HTTP.
    When session is set, the HTTP path sends its Cookie header and the browser
    path replays its storage_state; the browser proxy comes from HTTPS_PROXY."""
    if cfg.get("fetch_mode") == "browser":
        from jemscrape.browser import make_browser_fetcher
        if render_fn is None:
            from drivers.playwright_render import render as _render
            from jemscrape.proxy import proxy_dict_from_url
            proxy = proxy_dict_from_url(os.environ.get("HTTPS_PROXY"))
            storage = session.storage_state if session is not None else None
            render_fn = lambda url: _render(url, user_agent=cfg["user_agent"],
                                            proxy=proxy, storage_state=storage)
        return make_browser_fetcher(render_fn)
    user_agent = cfg["user_agent"]
    cookie_header = session.cookie_header(cfg["target_domain"]) if session is not None else None
    return lambda url: http_fetch(url, user_agent=user_agent, cookie_header=cookie_header)
```

In `assets/scraper-template/drivers/playwright_render.py`, update `render` to accept and apply `storage_state`:

```python
def render(url, *, timeout=30000, proxy=None, user_agent=None, storage_state=None):
    """Render url in headless Chromium; return RenderedResult(status, html, final_url).
    timeout is in milliseconds. proxy is a Playwright proxy dict or None.
    storage_state is a Playwright storage_state dict (replays a captured session)."""
    if not _AVAILABLE:
        raise RuntimeError(_INSTALL_HINT)
    launch_kwargs = {}
    if proxy:
        launch_kwargs["proxy"] = proxy
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, **launch_kwargs)
        try:
            context_kwargs = {}
            if user_agent is not None:
                context_kwargs["user_agent"] = user_agent
            if storage_state is not None:
                context_kwargs["storage_state"] = storage_state
            if context_kwargs:
                context = browser.new_context(**context_kwargs)
                page = context.new_page()
            else:
                page = browser.new_page()
            response = page.goto(url, wait_until="networkidle", timeout=timeout)
            status = response.status if response is not None else 0
            html = page.content()
            final_url = page.url
        finally:
            browser.close()
    return RenderedResult(status=status, html=html, final_url=final_url)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_build_fetcher.py assets/scraper-template/tests/test_playwright_render.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/scrape.py assets/scraper-template/drivers/playwright_render.py assets/scraper-template/tests/test_build_fetcher.py assets/scraper-template/tests/test_playwright_render.py
git commit -m "feat(3b): build_fetcher injects session cookie/storage_state + browser proxy

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: `scrape.py` — session preflight + AuthExpired handling in `main()`

**Files:**
- Modify: `assets/scraper-template/scrape.py`
- Test: `assets/scraper-template/tests/test_scrape_session.py` (new)

**Interfaces:**
- Consumes: `load_session`/`Session` (Task 2), `SessionError`/`AuthExpiredError` (Task 1), `build_fetcher(..., session=...)` (Task 7).
- Produces:
  - `load_run_session(cfg, session_path, now) -> Session | None` — `None` when `auth_required` is falsey; otherwise loads the session and raises `SessionError` if missing or `is_expired(now)`.
  - `main()` calls it before `run()`, passes `session=` to `build_fetcher`, and wraps `run()` to catch `AuthExpiredError` → `notify` + non-zero exit.

- [ ] **Step 1: Write the failing tests**

Create `assets/scraper-template/tests/test_scrape_session.py`:

```python
import json
from datetime import datetime, timezone

import pytest

import scrape
from jemscrape.errors import SessionError

FUTURE = 4102444800
PAST = 1000000000


def _session_file(tmp_path, expires):
    p = tmp_path / ".scrape-session.json"
    p.write_text(json.dumps({"cookies": [
        {"name": "sid", "value": "abc", "domain": "x.com",
         "path": "/", "expires": expires}], "origins": []}), encoding="utf-8")
    return p


def test_no_session_when_auth_not_required(tmp_path):
    got = scrape.load_run_session({"auth_required": False},
                                  tmp_path / "nope.json", datetime.now(timezone.utc))
    assert got is None


def test_auth_required_missing_session_raises(tmp_path):
    with pytest.raises(SessionError):
        scrape.load_run_session({"auth_required": True, "target_domain": "x.com"},
                                tmp_path / "nope.json", datetime.now(timezone.utc))


def test_auth_required_expired_session_raises(tmp_path):
    p = _session_file(tmp_path, PAST)
    with pytest.raises(SessionError):
        scrape.load_run_session({"auth_required": True, "target_domain": "x.com"},
                                p, datetime.now(timezone.utc))


def test_auth_required_valid_session_returned(tmp_path):
    p = _session_file(tmp_path, FUTURE)
    s = scrape.load_run_session({"auth_required": True, "target_domain": "x.com"},
                                p, datetime.now(timezone.utc))
    assert s.cookie_header("x.com") == "sid=abc"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_scrape_session.py -q`
Expected: FAIL — `scrape.load_run_session` does not exist.

- [ ] **Step 3: Write minimal implementation**

In `assets/scraper-template/scrape.py`, add near the other imports:

```python
SESSION_PATH = HERE / ".scrape-session.json"
```

Add the helper (after `require_warmup`):

```python
def load_run_session(cfg, session_path, now):
    """Fail-closed session gate for the auth path. Returns None when auth isn't
    required; otherwise loads the session and raises SessionError if it's
    missing or expired (spec §5.1 rules 5)."""
    if not cfg.get("auth_required"):
        return None
    from jemscrape.session import load_session   # stdlib, but keep imports local to the path
    session = load_session(session_path)
    if session.is_expired(now):
        from jemscrape.errors import SessionError
        raise SessionError("session token expired — renew locally with auth_capture.py "
                           "and update the SCRAPE_STORAGE_STATE secret")
    return session
```

Wire it into `main()`. After the warm-up gate block and before building the fetcher:

```python
    try:
        session = load_run_session(cfg, SESSION_PATH, datetime.now(timezone.utc))
    except Exception as exc:   # fail-closed: no auth run without a valid session
        print(f"[gate] BLOCKED: {exc}", file=sys.stderr)
        return 2
```

Change the fetcher build to pass the session:

```python
    fetcher = build_fetcher(cfg, http_fetch=http_fetch, session=session)
```

Wrap the `run(...)` call to catch a mid-run expiry:

```python
    from jemscrape.errors import AuthExpiredError
    try:
        summary = run(urls=urls, parse_fn=parse, cache_dir=cache_dir, fetcher=fetcher,
                      pacer=pacer, cursor=cursor, manifest=manifest, reparse=args.reparse)
    except AuthExpiredError as exc:
        import notify
        notify.emit("error", f"session expired mid-run: {exc}; renew with auth_capture.py "
                             f"and update the secret")
        print(f"[gate] BLOCKED: {exc}", file=sys.stderr)
        return 2
```

(The existing lines that write the manifest and records file stay after this block.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_scrape_session.py -q`
Expected: PASS.

- [ ] **Step 5: Full suite green**

Run: `.venv/bin/python -m pytest -q`
Expected: green (public path unchanged — `session` is `None` when `auth_required` is falsey).

- [ ] **Step 6: Commit**

```bash
git add assets/scraper-template/scrape.py assets/scraper-template/tests/test_scrape_session.py
git commit -m "feat(3b): scrape.py session preflight + mid-run AuthExpired handling

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: `warmup.py` — authenticated warm-up (session preflight + injection)

**Files:**
- Modify: `assets/scraper-template/warmup.py`
- Test: `assets/scraper-template/tests/test_warmup_cli.py`

**Interfaces:**
- Consumes: `load_run_session` (Task 8), `make_browser_probe` (existing), `Session.cookie_header`/`storage_state`.
- Produces: when `auth_required`, `warmup.py` loads the session (fail-closed via exit 2) and injects it — HTTP probe gets the cookie header; browser probe's default render_fn gets `storage_state` + proxy. The `probe_fn=`/`render_fn=` injection points used by existing tests keep working unchanged.

- [ ] **Step 1: Write the failing test**

Append to `assets/scraper-template/tests/test_warmup_cli.py` (follow the file's existing style for building `config`/`authz` temp files; the assertions below are the new behavior):

```python
def test_warmup_auth_required_missing_session_returns_2(tmp_path, capsys, monkeypatch):
    # Build a minimal valid config with auth_required + a passing compliance gate.
    # (Reuse this file's existing _write_config / _write_authz helpers.)
    cfg_path, authz_path = _auth_config(tmp_path, auth_required=True)
    sample = tmp_path / "sample.json"
    sample.write_text('["https://x.com/p"]', encoding="utf-8")
    rc = __import__("warmup").main(
        ["--sample", str(sample), "--config", str(cfg_path), "--authz", str(authz_path),
         "--out", str(tmp_path / "out.json")],
        parse_fn=lambda html, url: None)
    assert rc == 2
    assert "session" in capsys.readouterr().err.lower()
```

If `test_warmup_cli.py` has no config/authz helper yet, add a small `_auth_config(tmp_path, *, auth_required)` local helper that writes a config with `target_domain`, `runtime`, `user_agent`, `rate_limit_floor_seconds`, `auth_required`, `login_url`, plus a matching `.scrape-authorization.json` that passes `validate_authz` for `https://x.com/` (mirror the existing warm-up/compliance tests' fixtures).

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_warmup_cli.py -q`
Expected: FAIL — warm-up currently ignores `auth_required` (returns 0 or proceeds).

- [ ] **Step 3: Write minimal implementation**

In `assets/scraper-template/warmup.py`, after the compliance-gate `preflight` block and before building `probe_fn`, add the session gate:

```python
    from scrape import load_run_session
    try:
        session = load_run_session(cfg, HERE / ".scrape-session.json", now)
    except Exception as exc:   # fail-closed: no authenticated warm-up without a valid session
        print(f"[warmup] BLOCKED: session gate — {exc}", file=sys.stderr)
        return 2
```

Then thread `session` into the default probe construction:

```python
    if probe_fn is None:
        mode = args.render or cfg.get("fetch_mode", "http")
        if mode == "browser":
            from jemscrape.browser import make_browser_probe
            if render_fn is None:
                from drivers.playwright_render import render as _render
                from jemscrape.proxy import proxy_dict_from_url
                proxy = proxy_dict_from_url(os.environ.get("HTTPS_PROXY"))
                storage = session.storage_state if session is not None else None
                render_fn = lambda url: _render(url, user_agent=cfg["user_agent"],
                                                proxy=proxy, storage_state=storage)
            probe_fn = make_browser_probe(render_fn)
        else:
            user_agent = cfg["user_agent"]
            cookie_header = session.cookie_header(cfg["target_domain"]) if session is not None else None

            def probe_fn(url):
                return http_probe(url, user_agent=user_agent, cookie_header=cookie_header)
```

Add `import os` at the top of `warmup.py` if not present, and extend `http_probe` to accept `cookie_header`:

In `assets/scraper-template/jemscrape/fetch.py`, update `probe` to accept and send the cookie header (mirrors `fetch`):

```python
def probe(url, *, user_agent, cookie_header=None, timeout=30, urlopen=_default_urlopen):
    headers = {"User-Agent": user_agent}
    if cookie_header:
        headers["Cookie"] = cookie_header
    request = urllib.request.Request(url, headers=headers)
    ...
```

(Keep the rest of `probe` unchanged.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_warmup_cli.py -q`
Expected: PASS.

- [ ] **Step 5: Full suite green**

Run: `.venv/bin/python -m pytest -q`
Expected: green (probe's new kwarg is optional; existing probe tests unaffected).

- [ ] **Step 6: Commit**

```bash
git add assets/scraper-template/warmup.py assets/scraper-template/jemscrape/fetch.py assets/scraper-template/tests/test_warmup_cli.py
git commit -m "feat(3b): authenticated warm-up — session gate + cookie/storage injection

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 10: `drivers/auth_capture.py` + root CLI `auth_capture.py`

**Files:**
- Create: `assets/scraper-template/drivers/auth_capture.py`
- Create: `assets/scraper-template/auth_capture.py`
- Test: `assets/scraper-template/tests/test_auth_capture.py`

**Interfaces:**
- Consumes: `proxy_dict_from_url` (Task 3), `load_config`/`validate_config` (existing), `load_session` (Task 2).
- Produces:
  - Driver: `capture_session(login_url, out_path, *, proxy=None, user_agent=None, wait_fn=None) -> Path` — guarded (raises `RuntimeError(_INSTALL_HINT)` if Playwright absent).
  - CLI: `main(argv=None)` — reads config, resolves proxy from `HTTPS_PROXY`, calls the driver lazily, prints the estimated validity + the `gh secret set` instruction. Returns 0/2.

- [ ] **Step 1: Write the failing tests**

Create `assets/scraper-template/tests/test_auth_capture.py`:

```python
import inspect


def test_driver_guard_raises_actionable_error_without_playwright(monkeypatch):
    import drivers.auth_capture as ac
    if ac._AVAILABLE:
        import pytest
        pytest.skip("Playwright installed; guard path not exercised here")
    import pytest
    with pytest.raises(RuntimeError) as ei:
        ac.capture_session("https://x/login", "/tmp/out.json")
    assert "playwright" in str(ei.value).lower()


def test_driver_signature():
    import drivers.auth_capture as ac
    sig = inspect.signature(ac.capture_session)
    for name in ("login_url", "out_path", "proxy", "user_agent", "wait_fn"):
        assert name in sig.parameters


def test_cli_requires_login_url(tmp_path, capsys):
    import auth_capture
    import json
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"target_domain": "x.com", "runtime": "local",
                               "user_agent": "UA", "rate_limit_floor_seconds": 2.5,
                               "auth_required": True}), encoding="utf-8")
    # login_url missing -> validate_config rejects -> CLI returns 2
    rc = auth_capture.main(["--config", str(cfg), "--out", str(tmp_path / "s.json")])
    assert rc == 2
    assert "login_url" in capsys.readouterr().err
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_auth_capture.py -q`
Expected: FAIL — modules don't exist.

- [ ] **Step 3: Write minimal implementation**

Create `assets/scraper-template/drivers/auth_capture.py`:

```python
"""Local session capture (spec §5.1 rule 1). Launches HEADED Chromium so the
user logs in manually (with the country proxy on launch when geo applies), then
saves context.storage_state to a file. Playwright-only, guarded — kept out of
the stdlib core and the stdlib test suite, like playwright_render.py."""
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
    _AVAILABLE = True
except ImportError:
    sync_playwright = None
    _AVAILABLE = False

_INSTALL_HINT = (
    "Playwright is not installed — required to capture an authenticated session. "
    "Ask IT to install it: pip install playwright && playwright install chromium"
)


def _default_wait():
    input("\n>>> Log in in the opened browser window, then press Enter here to save the session... ")


def capture_session(login_url, out_path, *, proxy=None, user_agent=None, wait_fn=None):
    """Open login_url in headed Chromium, wait for the user to log in, save the
    session to out_path (Playwright storage_state JSON). Returns the Path."""
    if not _AVAILABLE:
        raise RuntimeError(_INSTALL_HINT)
    wait_fn = _default_wait if wait_fn is None else wait_fn
    out_path = Path(out_path)
    launch_kwargs = {}
    if proxy:
        launch_kwargs["proxy"] = proxy
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, **launch_kwargs)
        try:
            context = browser.new_context(user_agent=user_agent) if user_agent else browser.new_context()
            page = context.new_page()
            page.goto(login_url)
            wait_fn()
            context.storage_state(path=str(out_path))
        finally:
            browser.close()
    return out_path
```

Create `assets/scraper-template/auth_capture.py` (root CLI — stdlib at top level, driver imported lazily):

```python
"""Capture an authenticated session locally and stage it for the Actions secret
(spec §5.1). Headed browser login happens on the user's machine; the run replays
the saved session on the runner. This CLI never pushes the secret automatically —
it prints the exact `gh secret set` command for a conscious step."""
import argparse
import os
import sys
from pathlib import Path

from jemscrape.config import load_config, validate_config
from jemscrape.proxy import proxy_dict_from_url

HERE = Path(__file__).resolve().parent
SESSION_PATH = HERE / ".scrape-session.json"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Capture an authenticated session (local)")
    parser.add_argument("--config", default=str(HERE / "config.json"))
    parser.add_argument("--out", default=str(SESSION_PATH))
    args = parser.parse_args(argv)

    try:
        cfg = load_config(args.config)
        validate_config(cfg)
    except Exception as exc:
        print(f"[auth-capture] BLOCKED: {exc}", file=sys.stderr)
        return 2
    login_url = cfg.get("login_url")
    if not login_url:
        print("[auth-capture] login_url required in config (set auth_required + login_url).",
              file=sys.stderr)
        return 2

    proxy = proxy_dict_from_url(os.environ.get("HTTPS_PROXY"))
    from drivers.auth_capture import capture_session   # lazy: Playwright only here
    try:
        out = capture_session(login_url, args.out, proxy=proxy, user_agent=cfg["user_agent"])
    except RuntimeError as exc:  # Playwright missing -> actionable hint
        print(f"[auth-capture] {exc}", file=sys.stderr)
        return 2

    # Report validity + the secret push instruction (never auto-push).
    from jemscrape.session import load_session
    try:
        session = load_session(out)
        exp = session.expires_at()
        when = exp.isoformat() if exp else "unknown (session cookies only)"
    except Exception:
        when = "unknown"
    print(f"[auth-capture] saved -> {out}")
    print(f"[auth-capture] token valid until: {when}")
    print(f"[auth-capture] next: gh secret set SCRAPE_STORAGE_STATE < {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_auth_capture.py -q`
Expected: PASS (driver guard test skips if Playwright is installed; otherwise exercises the actionable error).

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/drivers/auth_capture.py assets/scraper-template/auth_capture.py assets/scraper-template/tests/test_auth_capture.py
git commit -m "feat(3b): auth_capture — headed local session capture + secret staging CLI

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 11: Conditional `SCRAPE_STORAGE_STATE` in `actions_setup.py`

**Files:**
- Modify: `assets/scraper-template/actions_setup.py`
- Test: `assets/scraper-template/tests/test_actions_setup.py`

**Interfaces:**
- Consumes: `materialize_secret` (existing), `load_config` (existing).
- Produces: `main(argv=None, *, env=None, targets=None, config=None)` — when `targets` is `None`, it builds the default target list and, if the config's `auth_required` is true, appends `("SCRAPE_STORAGE_STATE", HERE/".scrape-session.json")` as a required (fail-closed) target. When `auth_required` is false, the session secret is not required.

- [ ] **Step 1: Write the failing tests**

Append to `assets/scraper-template/tests/test_actions_setup.py`:

```python
def test_session_secret_required_when_auth_required(tmp_path):
    a = tmp_path / ".scrape-authorization.json"
    w = tmp_path / ".scrape-warmup.json"
    s = tmp_path / ".scrape-session.json"
    targets = [("SCRAPE_AUTHORIZATION", a), ("SCRAPE_WARMUP", w),
               ("SCRAPE_STORAGE_STATE", s)]
    # auth_required path: session secret missing -> fail-closed
    rc = actions_setup.main(env={"SCRAPE_AUTHORIZATION": "{}", "SCRAPE_WARMUP": "{}"},
                            targets=targets)
    assert rc == 2


def test_target_builder_appends_session_when_auth_required(tmp_path):
    cfg = {"auth_required": True}
    targets = actions_setup.build_targets(cfg, base=tmp_path)
    names = [t[0] for t in targets]
    assert "SCRAPE_STORAGE_STATE" in names


def test_target_builder_omits_session_when_public(tmp_path):
    targets = actions_setup.build_targets({"auth_required": False}, base=tmp_path)
    names = [t[0] for t in targets]
    assert "SCRAPE_STORAGE_STATE" not in names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_actions_setup.py -q`
Expected: FAIL — `build_targets` doesn't exist.

- [ ] **Step 3: Write minimal implementation**

In `assets/scraper-template/actions_setup.py`, add a `build_targets` helper and use it when `targets is None`:

```python
def build_targets(cfg, *, base=HERE):
    targets = [
        ("SCRAPE_AUTHORIZATION", base / ".scrape-authorization.json"),
        ("SCRAPE_WARMUP", base / ".scrape-warmup.json"),
    ]
    if cfg.get("auth_required"):
        targets.append(("SCRAPE_STORAGE_STATE", base / ".scrape-session.json"))
    return targets


def main(argv=None, *, env=None, targets=None, config=None):
    env = os.environ if env is None else env
    if targets is None:
        if config is None:
            from jemscrape.config import load_config
            try:
                config = load_config(HERE / "config.json")
            except Exception:
                config = {}
        targets = build_targets(config)
    written = []
    for name, path in targets:
        try:
            materialize_secret(name, path, env=env)
        except ConfigError as exc:
            print(f"[actions-setup] BLOCKED: {exc}", file=sys.stderr)
            return 2
        written.append(str(path))
    for w in written:
        print(f"[actions-setup] wrote {w}")
    return 0
```

(Keep the existing `_SECRET_FILES` constant for backward reference, or remove it if now unused; the tests use `build_targets`/explicit `targets`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_actions_setup.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/actions_setup.py assets/scraper-template/tests/test_actions_setup.py
git commit -m "feat(3b): actions_setup materializes SCRAPE_STORAGE_STATE when auth_required

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 12: `deploy_actions.py` — session in the secret map

**Files:**
- Modify: `assets/scraper-template/drivers/deploy_actions.py`
- Test: `assets/scraper-template/tests/test_deploy_actions.py`

**Interfaces:**
- Produces: `build_secret_commands` includes `("SCRAPE_STORAGE_STATE", ".scrape-session.json")` in `_SECRET_MAP`; still `if f.exists()` (so a public project simply omits it) and still `stdin_file` (never argv).

- [ ] **Step 1: Write the failing test**

Append to `assets/scraper-template/tests/test_deploy_actions.py`:

```python
def test_build_secret_commands_includes_session_when_present(tmp_path):
    (tmp_path / ".scrape-authorization.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".scrape-warmup.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".scrape-session.json").write_text('{"cookies":[]}', encoding="utf-8")
    steps = da.build_secret_commands(tmp_path)
    names = [s["secret"] for s in steps]
    assert "SCRAPE_STORAGE_STATE" in names
    sess = next(s for s in steps if s["secret"] == "SCRAPE_STORAGE_STATE")
    assert sess["stdin_file"].name == ".scrape-session.json"
    assert '{"cookies":[]}' not in sess["argv"]  # secret value never on argv
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_deploy_actions.py -q`
Expected: FAIL — session not in `_SECRET_MAP`.

- [ ] **Step 3: Write minimal implementation**

In `assets/scraper-template/drivers/deploy_actions.py`, add the session entry:

```python
_SECRET_MAP = (
    ("SCRAPE_AUTHORIZATION", ".scrape-authorization.json"),
    ("SCRAPE_WARMUP", ".scrape-warmup.json"),
    ("SCRAPE_STORAGE_STATE", ".scrape-session.json"),
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_deploy_actions.py -q`
Expected: PASS (the existing "skips absent files" test still holds — a project without a session file just omits it).

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/drivers/deploy_actions.py assets/scraper-template/tests/test_deploy_actions.py
git commit -m "feat(3b): deploy_actions pushes SCRAPE_STORAGE_STATE via stdin when present

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 13: `scrape.yml` template — materialize the session secret

**Files:**
- Modify: `assets/github-actions/scrape.yml`
- Test: `assets/scraper-template/tests/test_actions_workflow.py`

**Interfaces:**
- Produces: the workflow's "Materialize gate secrets" step passes `SCRAPE_STORAGE_STATE: ${{ secrets.SCRAPE_STORAGE_STATE }}` alongside the two gate secrets; `HTTPS_PROXY` already reaches the scrape step.

- [ ] **Step 1: Write the failing test**

Append to `assets/scraper-template/tests/test_actions_workflow.py` (match the file's existing text-assertion style):

```python
def test_workflow_materializes_session_secret():
    from pathlib import Path
    text = Path(__file__).resolve().parents[3].joinpath(
        "assets/github-actions/scrape.yml").read_text(encoding="utf-8")
    assert "SCRAPE_STORAGE_STATE" in text
    assert "secrets.SCRAPE_STORAGE_STATE" in text
```

(Confirm the path depth matches how `test_actions_workflow.py` already locates `scrape.yml`; reuse that exact locator if the file has one.)

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_actions_workflow.py -q`
Expected: FAIL — the secret isn't in the template yet.

- [ ] **Step 3: Write minimal implementation**

In `assets/github-actions/scrape.yml`, add the session secret to the materialize step's env:

```yaml
      - name: Materialize gate secrets (fail-closed)
        env:
          SCRAPE_AUTHORIZATION: ${{ secrets.SCRAPE_AUTHORIZATION }}
          SCRAPE_WARMUP: ${{ secrets.SCRAPE_WARMUP }}
          SCRAPE_STORAGE_STATE: ${{ secrets.SCRAPE_STORAGE_STATE }}
        run: python actions_setup.py
```

(The scrape step already exports `HTTPS_PROXY: ${{ secrets.HTTPS_PROXY }}`; the browser path reads it via `build_fetcher`. No change needed there. Add a short comment above the scrape step noting the browser path applies the proxy on the Playwright launch.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_actions_workflow.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assets/github-actions/scrape.yml assets/scraper-template/tests/test_actions_workflow.py
git commit -m "feat(3b): scrape.yml materializes SCRAPE_STORAGE_STATE secret

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 14: Secret blindage — `.gitignore`, precheck hook, config example

**Files:**
- Modify: `assets/project-skeleton/.gitignore`
- Modify: `hooks/scripts/precheck.py`
- Modify: `assets/scraper-template/config.json.example`
- Test: `assets/scraper-template/tests/test_precheck_hook.py`, `tests/test_config_example.py`

**Interfaces:**
- Produces: `.scrape-session.json` ignored by the scaffold; `precheck.should_block` blocks a `git add`/`commit` naming it; `config.json.example` documents `auth_required`/`login_url`.

- [ ] **Step 1: Write the failing tests**

Append to `assets/scraper-template/tests/test_precheck_hook.py` (mirror the existing block-marker tests):

```python
def test_blocks_git_add_of_session_file():
    from importlib import import_module
    precheck = import_module("scripts.precheck") if False else None  # see locator note below
```

Use the same import mechanism the existing tests in `test_precheck_hook.py` already use to load `hooks/scripts/precheck.py` (reuse that fixture/helper), then:

```python
def test_blocks_git_add_of_session_file(precheck):
    reason = precheck.should_block("Bash", {"command": "git add .scrape-session.json"})
    assert reason is not None
    assert ".scrape-session.json" in reason
```

Append to `assets/scraper-template/tests/test_config_example.py`:

```python
def test_config_example_documents_auth_fields():
    import json
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / "config.json.example"
    cfg = json.loads(p.read_text(encoding="utf-8"))
    assert "auth_required" in cfg
    assert "login_url" in cfg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_precheck_hook.py assets/scraper-template/tests/test_config_example.py -q`
Expected: FAIL — marker/keys not present yet.

- [ ] **Step 3: Write minimal implementation**

In `hooks/scripts/precheck.py`, add to `_SECRET_MARKERS`:

```python
_SECRET_MARKERS = (
    ".scrape-authorization.json",
    ".scrape-warmup.json",
    ".scrape-session.json",
    ".env",
    ".token",
    ".secret",
)
```

In `assets/project-skeleton/.gitignore`, under the secrets section:

```
.scrape-authorization.json
.scrape-warmup.json
.scrape-session.json
*.token
*.secret
.env
```

In `assets/scraper-template/config.json.example`, add the two keys (valid JSON — `auth_required` defaults false, `login_url` empty):

```json
{
  "target_domain": "example.com",
  "runtime": "local",
  "fetch_mode": "http",
  "auth_required": false,
  "login_url": "",
  "user_agent": "Mozilla/5.0 (compatible; JEMScrape/1.0; +mailto:ops@jemsystems.com)",
  "rate_limit_floor_seconds": 2.5,
  "min_delay_seconds": 2.5,
  "max_delay_seconds": 5.0,
  "band_priority": [],
  "hub_group": [],
  "ireland_branch": ""
}
```

Note: `validate_config` accepts `auth_required: false` with an empty `login_url` (login_url is only required when `auth_required` is true), so this example still validates. Confirm `test_config_example.py`'s existing "example validates" test (if any) stays green.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_precheck_hook.py assets/scraper-template/tests/test_config_example.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add hooks/scripts/precheck.py assets/project-skeleton/.gitignore assets/scraper-template/config.json.example assets/scraper-template/tests/test_precheck_hook.py assets/scraper-template/tests/test_config_example.py
git commit -m "feat(3b): blindar .scrape-session.json (gitignore, precheck, config example)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 15: Reference doc — the daily refresh ritual

**Files:**
- Create: `references/auth-session.md`
- Test: none (docs); a light presence check can live in an existing docs test if the repo has one — otherwise skip.

**Interfaces:** none (documentation).

- [ ] **Step 1: Write the reference**

Create `references/auth-session.md` documenting: the local capture is intrinsic (only the user's machine logs in); the daily ritual (run `auth_capture.py` → `gh secret set SCRAPE_STORAGE_STATE`); the cron fires just after the daily refresh, inside the token's life; mid-run 401/403 is fail-closed with an alert and resumes from the cursor after renewal; the machine-offline limitation; and the VM-promotion trigger (a site that forces non-automatable interactive re-login within the token's life). Cross-reference spec §5.1 and `geo-proxy.md`.

- [ ] **Step 2: Commit**

```bash
git add references/auth-session.md
git commit -m "docs(3b): reference — authenticated session refresh ritual + VM trigger

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 16: Full suite + CHANGELOG + spec status

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `docs/superpowers/specs/2026-07-01-jem-product-scrape-kit-intel-design.md` (mark 3b built, if the plan-of-record notes deferral there — a one-line status update, not a rewrite)
- Test: full suite.

- [ ] **Step 1: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: 204 baseline + all new tests passing; 1 skip (Playwright smoke). No failures.

- [ ] **Step 2: Update CHANGELOG**

Add a `### Plano 3b — sessão autenticada + geo no Actions` entry summarizing: `session.py`, `proxy.py`, `AuthExpiredError` fail-closed, `auth_capture.py`, conditional `SCRAPE_STORAGE_STATE`, authenticated warm-up, proxy on the browser launch.

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md docs/superpowers/specs/2026-07-01-jem-product-scrape-kit-intel-design.md
git commit -m "docs(3b): CHANGELOG + spec status — 3b built

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- §4.1 session.py → Task 2 ✓; §4.2 proxy.py → Task 3 ✓; §4.3 AuthExpired fail-closed → Tasks 1/4/5/8 ✓; §4.4 session preflight → Tasks 8/9 ✓; §4.5 injection → Task 7 (+9) ✓; §4.6 auth_capture → Task 10 ✓; §4.7 conditional secret + deploy + yml → Tasks 11/12/13 ✓; §5 config fields → Task 6 ✓; §6 end-to-end flow → exercised across 7/8/9/13; §7 refresh ritual → Task 15 ✓; §8 tests → each task; §9 secret blindage → Task 14 ✓.
- HTTP-path proxy (`HTTPS_PROXY` via urllib) needs no code — noted in Tasks 7/13.

**Placeholder scan:** no TBD/TODO; every code step shows code. Two tasks (9, 14) reference reusing an existing test helper in the target test file rather than repeating fixture code — the implementer must open that file; the new assertions are given in full.

**Type consistency:** `Session.cookie_header(domain)`, `Session.storage_state`, `Session.expires_at()`, `Session.is_expired(now)` consistent across Tasks 2/7/8/9. `build_fetcher(cfg, *, http_fetch, render_fn=None, session=None)` consistent Tasks 7/8. `render(..., storage_state=None)` consistent Tasks 7/10. `proxy_dict_from_url` consistent Tasks 3/7/9/10. `load_run_session(cfg, session_path, now)` consistent Tasks 8/9. `build_targets(cfg, *, base)` Task 11.

**Note for the implementer (Tasks 9, 13, 14):** these touch test files whose exact fixtures/locators already exist in the repo (`test_warmup_cli.py` config/authz builders, `test_actions_workflow.py`'s `scrape.yml` path locator, `test_precheck_hook.py`'s precheck import helper). Reuse the existing mechanism rather than the illustrative locator shown — the assertion content is what matters, and it's given in full.
