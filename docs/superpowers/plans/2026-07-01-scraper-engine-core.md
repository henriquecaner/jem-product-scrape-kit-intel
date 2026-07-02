# Scraper Engine Core — Implementation Plan (Plano 1 de 6)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the reusable, zero-runtime-dependency Python core of `assets/scraper-template/` — the resilient fetch/cache/pace/manifest engine plus the runtime authorization gate — that every generated scraper is instantiated from.

**Architecture:** A small package `jemscrape/` (stdlib only) composed of focused modules (config, authz, pacing, fetch, cache, manifest, runner) wired by a `scrape.py` CLI and validated by `smoke_test.py`. Every module takes its side-effecting collaborators (clock, rng, HTTP opener) as injected callables so it is deterministically testable without network or wall-clock sleeps. Discovery (sitemap/listing) and `parse_fn` are site-specific and are provided by later plans / adapted per site by the orchestrator; this plan builds everything around them.

**Tech Stack:** Python 3.9+ (stdlib only at runtime). `pytest` is a **dev-only** dependency of the plugin repo used to test the template; it is never shipped into a generated scraper's runtime.

## Global Constraints

- Runtime code is **Python 3 stdlib only** — no third-party imports in `jemscrape/`, `scrape.py`, or `smoke_test.py`. (Playwright, the auth/browser path, is a later plan and stays out of this core.)
- Minimum Python: **3.9** (broad Windows compatibility).
- **Compliance enforcement lives at runtime:** `scrape.py` validates `.scrape-authorization.json` before any network request and exits non-zero if invalid. The Claude Code hook is defense-in-depth, not the guarantee.
- **`rate_limit_floor_seconds` is a required field of `config.json`** (minimum seconds between requests). The pacer never emits a delay below it.
- All persisted writes use **atomic write** (temp file + `os.replace`).
- Raw cache lives in `data/` (git-ignored by the generated project). The resume checkpoint lives in `state/cursor.json` (versioned, not ignored).
- The manifest carries `schema_version` (start at `"1.0"`).
- robots precedence (spec §10.2) is enforced at runtime: `public_competitor` + `robots_status == "disallowed"` → abort; `contracted_partner` requires `robots_override_ref` to override; `own_account` may override.
- Every module receives its clock/rng/opener as parameters (default to the stdlib real ones) so tests inject fakes — no real `time.sleep` or network in tests.

---

## File Structure

```
assets/scraper-template/
├── jemscrape/
│   ├── __init__.py         # package marker + version
│   ├── errors.py           # ConfigError, AuthorizationError, FetchError
│   ├── config.py           # load_config, validate_config
│   ├── authz.py            # Authorization, load_authorization, validate
│   ├── pacing.py           # Pacer
│   ├── fetch.py            # fetch
│   ├── cache.py            # atomic_write, slug_for, cache_path, is_cached, read_cached, Cursor
│   ├── manifest.py         # Manifest
│   └── runner.py           # run
├── scrape.py               # CLI entry (wires everything; the runtime gate)
├── smoke_test.py           # pre-run validation gate
├── config.json.example     # documented config template
└── tests/
    ├── conftest.py         # shared fixtures (fake clock, rng, opener, tmp dirs)
    ├── test_config.py
    ├── test_authz.py
    ├── test_pacing.py
    ├── test_fetch.py
    ├── test_cache.py
    ├── test_manifest.py
    ├── test_runner.py
    └── test_smoke.py
```

The plugin repo root also gets a dev `pyproject.toml` (pytest config) — created in Task 0.

---

### Task 0: Repo dev setup + template package skeleton

**Files:**
- Create: `pyproject.toml` (repo root)
- Create: `assets/scraper-template/jemscrape/__init__.py`
- Create: `assets/scraper-template/jemscrape/errors.py`
- Create: `assets/scraper-template/tests/conftest.py`
- Create: `assets/scraper-template/tests/test_smoke_import.py`

**Interfaces:**
- Produces: package `jemscrape` importable; exceptions `ConfigError`, `AuthorizationError`, `FetchError`; `jemscrape.__version__`.

- [ ] **Step 1: Write the failing test**

`assets/scraper-template/tests/test_smoke_import.py`:
```python
def test_package_imports_and_exposes_errors():
    import jemscrape
    from jemscrape.errors import ConfigError, AuthorizationError, FetchError

    assert isinstance(jemscrape.__version__, str)
    for exc in (ConfigError, AuthorizationError, FetchError):
        assert issubclass(exc, Exception)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd assets/scraper-template && python -m pytest tests/test_smoke_import.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jemscrape'`

- [ ] **Step 3: Create the dev config and package files**

`pyproject.toml` (repo root):
```toml
[tool.pytest.ini_options]
testpaths = ["assets/scraper-template/tests"]
pythonpath = ["assets/scraper-template"]
addopts = "-q"
```

`assets/scraper-template/jemscrape/__init__.py`:
```python
"""jemscrape — reusable stdlib-only scraping engine core (JEM plugin)."""

__version__ = "1.0.0"
```

`assets/scraper-template/jemscrape/errors.py`:
```python
class ConfigError(Exception):
    """Raised when config.json is missing required fields or has bad values."""


class AuthorizationError(Exception):
    """Raised when .scrape-authorization.json is missing, invalid, or forbids the target."""


class FetchError(Exception):
    """Raised when an HTTP fetch exhausts its retries."""
```

`assets/scraper-template/tests/conftest.py`:
```python
import sys
from pathlib import Path

# Make the template package importable when tests run from the repo root.
TEMPLATE_ROOT = Path(__file__).resolve().parent.parent
if str(TEMPLATE_ROOT) not in sys.path:
    sys.path.insert(0, str(TEMPLATE_ROOT))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest assets/scraper-template/tests/test_smoke_import.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml assets/scraper-template/jemscrape/__init__.py assets/scraper-template/jemscrape/errors.py assets/scraper-template/tests/conftest.py assets/scraper-template/tests/test_smoke_import.py
git commit -m "chore: scaffold scraper-template package + pytest dev setup"
```

---

### Task 1: Config loading + validation

**Files:**
- Create: `assets/scraper-template/jemscrape/config.py`
- Test: `assets/scraper-template/tests/test_config.py`

**Interfaces:**
- Consumes: `jemscrape.errors.ConfigError`.
- Produces:
  - `load_config(path: str | Path) -> dict` — reads JSON, raises `ConfigError` if unreadable/not-object.
  - `validate_config(cfg: dict) -> None` — raises `ConfigError` listing every missing/invalid field.
  - Required keys: `target_domain` (non-empty str), `runtime` (one of `"local"`, `"github_actions"`, `"vm"`), `rate_limit_floor_seconds` (number > 0), `user_agent` (non-empty str). Optional: `min_delay_seconds`, `max_delay_seconds` (numbers; if present, `min <= max` and `min >= rate_limit_floor_seconds`).

- [ ] **Step 1: Write the failing test**

`assets/scraper-template/tests/test_config.py`:
```python
import json
import pytest

from jemscrape.config import load_config, validate_config
from jemscrape.errors import ConfigError


def _valid():
    return {
        "target_domain": "example.com",
        "runtime": "local",
        "rate_limit_floor_seconds": 2.5,
        "user_agent": "Mozilla/5.0 (compatible; JEMScrape/1.0)",
    }


def test_valid_config_passes():
    validate_config(_valid())  # no raise


def test_missing_required_field_lists_it():
    cfg = _valid()
    del cfg["target_domain"]
    with pytest.raises(ConfigError) as e:
        validate_config(cfg)
    assert "target_domain" in str(e.value)


def test_bad_runtime_rejected():
    cfg = _valid()
    cfg["runtime"] = "carrier-pigeon"
    with pytest.raises(ConfigError):
        validate_config(cfg)


def test_floor_must_be_positive():
    cfg = _valid()
    cfg["rate_limit_floor_seconds"] = 0
    with pytest.raises(ConfigError):
        validate_config(cfg)


def test_min_below_floor_rejected():
    cfg = _valid()
    cfg["min_delay_seconds"] = 1.0  # below the 2.5 floor
    cfg["max_delay_seconds"] = 5.0
    with pytest.raises(ConfigError):
        validate_config(cfg)


def test_load_config_reads_json(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps(_valid()), encoding="utf-8")
    cfg = load_config(p)
    assert cfg["target_domain"] == "example.com"


def test_load_config_bad_json_raises(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(p)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest assets/scraper-template/tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jemscrape.config'`

- [ ] **Step 3: Write minimal implementation**

`assets/scraper-template/jemscrape/config.py`:
```python
import json
from pathlib import Path

from .errors import ConfigError

VALID_RUNTIMES = {"local", "github_actions", "vm"}


def load_config(path):
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read config at {p}: {exc}") from exc
    try:
        cfg = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"config at {p} is not valid JSON: {exc}") from exc
    if not isinstance(cfg, dict):
        raise ConfigError("config must be a JSON object")
    return cfg


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate_config(cfg):
    errors = []

    domain = cfg.get("target_domain")
    if not isinstance(domain, str) or not domain.strip():
        errors.append("target_domain: required non-empty string")

    runtime = cfg.get("runtime")
    if runtime not in VALID_RUNTIMES:
        errors.append(f"runtime: must be one of {sorted(VALID_RUNTIMES)}")

    ua = cfg.get("user_agent")
    if not isinstance(ua, str) or not ua.strip():
        errors.append("user_agent: required non-empty string")

    floor = cfg.get("rate_limit_floor_seconds")
    if not _is_number(floor) or floor <= 0:
        errors.append("rate_limit_floor_seconds: required number > 0")

    lo = cfg.get("min_delay_seconds")
    hi = cfg.get("max_delay_seconds")
    if lo is not None or hi is not None:
        if not _is_number(lo) or not _is_number(hi):
            errors.append("min_delay_seconds/max_delay_seconds: both must be numbers if either is set")
        else:
            if lo > hi:
                errors.append("min_delay_seconds must be <= max_delay_seconds")
            if _is_number(floor) and lo < floor:
                errors.append("min_delay_seconds must be >= rate_limit_floor_seconds")

    if errors:
        raise ConfigError("invalid config: " + "; ".join(errors))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest assets/scraper-template/tests/test_config.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/config.py assets/scraper-template/tests/test_config.py
git commit -m "feat: config loading + validation with mandatory rate-limit floor"
```

---

### Task 2: Runtime authorization gate

**Files:**
- Create: `assets/scraper-template/jemscrape/authz.py`
- Test: `assets/scraper-template/tests/test_authz.py`

**Interfaces:**
- Consumes: `jemscrape.errors.AuthorizationError`.
- Produces:
  - `Authorization` dataclass: `target_domain, authorization_type, approver, approved_at, expires_at, rate_limit_floor_seconds, robots_status, robots_override_ref, requires_approval, scope`.
  - `load_authorization(path) -> Authorization` — raises `AuthorizationError` if missing/malformed.
  - `validate(auth: Authorization, target_url: str, now: datetime) -> None` — raises `AuthorizationError` on: domain mismatch, expired, robots precedence violation (§10.2), missing required fields. `now` is injected for deterministic tests. Timestamps are ISO-8601 (`datetime.fromisoformat`).

- [ ] **Step 1: Write the failing test**

`assets/scraper-template/tests/test_authz.py`:
```python
import json
from datetime import datetime, timezone

import pytest

from jemscrape.authz import Authorization, load_authorization, validate
from jemscrape.errors import AuthorizationError

NOW = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)


def _auth(**over):
    base = dict(
        target_domain="example.com",
        authorization_type="public_competitor",
        approver="henrique",
        approved_at="2026-07-01T09:00:00+00:00",
        expires_at="2026-07-08T09:00:00+00:00",
        rate_limit_floor_seconds=2.5,
        robots_status="allowed",
        robots_override_ref=None,
        requires_approval=False,
        scope="catalog",
    )
    base.update(over)
    return Authorization(**base)


def test_valid_authorization_passes():
    validate(_auth(), "https://example.com/p/1", NOW)


def test_domain_mismatch_rejected():
    with pytest.raises(AuthorizationError):
        validate(_auth(), "https://other.com/p/1", NOW)


def test_expired_rejected():
    with pytest.raises(AuthorizationError):
        validate(_auth(expires_at="2026-06-30T09:00:00+00:00"), "https://example.com/", NOW)


def test_public_competitor_disallowed_is_hard_block():
    with pytest.raises(AuthorizationError):
        validate(_auth(robots_status="disallowed"), "https://example.com/", NOW)


def test_partner_disallowed_without_override_rejected():
    with pytest.raises(AuthorizationError):
        validate(
            _auth(authorization_type="contracted_partner", robots_status="disallowed"),
            "https://example.com/",
            NOW,
        )


def test_partner_disallowed_with_override_ok():
    validate(
        _auth(
            authorization_type="contracted_partner",
            robots_status="disallowed",
            robots_override_ref="MSA-2026-014",
        ),
        "https://example.com/",
        NOW,
    )


def test_own_account_disallowed_ok():
    validate(_auth(authorization_type="own_account", robots_status="disallowed"),
             "https://example.com/", NOW)


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(AuthorizationError):
        load_authorization(tmp_path / "nope.json")


def test_load_reads_record(tmp_path):
    p = tmp_path / ".scrape-authorization.json"
    p.write_text(json.dumps(_auth().__dict__), encoding="utf-8")
    auth = load_authorization(p)
    assert auth.target_domain == "example.com"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest assets/scraper-template/tests/test_authz.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jemscrape.authz'`

- [ ] **Step 3: Write minimal implementation**

`assets/scraper-template/jemscrape/authz.py`:
```python
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from .errors import AuthorizationError

VALID_TYPES = {"public_competitor", "contracted_partner", "own_account"}
VALID_ROBOTS = {"allowed", "disallowed"}


@dataclass
class Authorization:
    target_domain: str
    authorization_type: str
    approver: str
    approved_at: str
    expires_at: str
    rate_limit_floor_seconds: float
    robots_status: str
    robots_override_ref: object  # str | None
    requires_approval: bool
    scope: str


def load_authorization(path):
    p = Path(path)
    if not p.exists():
        raise AuthorizationError(f"no authorization record at {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthorizationError(f"cannot read authorization at {p}: {exc}") from exc
    try:
        return Authorization(**{k: data.get(k) for k in Authorization.__annotations__})
    except TypeError as exc:
        raise AuthorizationError(f"malformed authorization record: {exc}") from exc


def _parse_dt(value, field):
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise AuthorizationError(f"{field}: not an ISO-8601 datetime ({value!r})") from exc


def validate(auth, target_url, now):
    if auth.authorization_type not in VALID_TYPES:
        raise AuthorizationError(f"authorization_type invalid: {auth.authorization_type!r}")
    if auth.robots_status not in VALID_ROBOTS:
        raise AuthorizationError(f"robots_status invalid: {auth.robots_status!r}")
    if not auth.approver:
        raise AuthorizationError("approver is required")

    host = urlsplit(target_url).hostname or ""
    if host != auth.target_domain:
        raise AuthorizationError(
            f"target host {host!r} does not match authorized domain {auth.target_domain!r}"
        )

    if now >= _parse_dt(auth.expires_at, "expires_at"):
        raise AuthorizationError(f"authorization expired at {auth.expires_at}")

    if auth.robots_status == "disallowed":
        if auth.authorization_type == "public_competitor":
            raise AuthorizationError("robots.txt disallows and target is a public competitor — hard block")
        if auth.authorization_type == "contracted_partner" and not auth.robots_override_ref:
            raise AuthorizationError("robots.txt disallows; contracted_partner requires robots_override_ref")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest assets/scraper-template/tests/test_authz.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/authz.py assets/scraper-template/tests/test_authz.py
git commit -m "feat: runtime authorization gate (domain, expiry, robots precedence)"
```

---

### Task 3: Humanized pacing with floor enforcement

**Files:**
- Create: `assets/scraper-template/jemscrape/pacing.py`
- Test: `assets/scraper-template/tests/test_pacing.py`

**Interfaces:**
- Produces:
  - `Pacer(min_delay, max_delay, floor, rng=random.uniform, randint=random.randint, sleep=time.sleep)`.
  - `pacer.wait(heavy=False) -> float` — computes a delay, calls `sleep(delay)`, returns the delay. Delay is `rng(min, max)` (×1.4 if `heavy`), clamped up to `floor`; every 20–30 calls a "coffee break" of `rng(90, 240)` extra seconds is added. `rng`/`randint`/`sleep` are injected for deterministic tests.

- [ ] **Step 1: Write the failing test**

`assets/scraper-template/tests/test_pacing.py`:
```python
from jemscrape.pacing import Pacer


class Recorder:
    def __init__(self):
        self.slept = []

    def __call__(self, seconds):
        self.slept.append(seconds)


def test_delay_never_below_floor():
    rec = Recorder()
    # rng always returns 0.1 (below floor); floor must win
    pacer = Pacer(min_delay=0.1, max_delay=0.1, floor=2.5,
                  rng=lambda a, b: 0.1, randint=lambda a, b: 999, sleep=rec)
    delay = pacer.wait()
    assert delay == 2.5
    assert rec.slept == [2.5]


def test_heavy_multiplies():
    pacer = Pacer(min_delay=10, max_delay=10, floor=1,
                  rng=lambda a, b: 10, randint=lambda a, b: 999, sleep=lambda s: None)
    assert pacer.wait(heavy=True) == 14.0


def test_coffee_break_adds_time_on_interval():
    # randint returns 1 → coffee break triggers on the 1st call; rng returns lo each call.
    seq = iter([5.0, 120.0])  # first rng() = base delay, second rng() = coffee break add

    def rng(a, b):
        return next(seq)

    pacer = Pacer(min_delay=5, max_delay=5, floor=1,
                  rng=rng, randint=lambda a, b: 1, sleep=lambda s: None)
    delay = pacer.wait()
    assert delay == 125.0  # 5 base + 120 coffee break
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest assets/scraper-template/tests/test_pacing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jemscrape.pacing'`

- [ ] **Step 3: Write minimal implementation**

`assets/scraper-template/jemscrape/pacing.py`:
```python
import random
import time


class Pacer:
    def __init__(self, min_delay, max_delay, floor,
                 rng=random.uniform, randint=random.randint, sleep=time.sleep):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.floor = floor
        self._rng = rng
        self._randint = randint
        self._sleep = sleep
        self._count = 0
        self._next_break_at = self._randint(20, 30)

    def wait(self, heavy=False):
        self._count += 1
        delay = self._rng(self.min_delay, self.max_delay)
        if heavy:
            delay *= 1.4
        if delay < self.floor:
            delay = self.floor
        if self._count >= self._next_break_at:
            delay += self._rng(90, 240)
            self._count = 0
            self._next_break_at = self._randint(20, 30)
        self._sleep(delay)
        return delay
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest assets/scraper-template/tests/test_pacing.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/pacing.py assets/scraper-template/tests/test_pacing.py
git commit -m "feat: humanized pacer with rate-limit floor and coffee breaks"
```

---

### Task 4: Resilient HTTP fetch

**Files:**
- Create: `assets/scraper-template/jemscrape/fetch.py`
- Test: `assets/scraper-template/tests/test_fetch.py`

**Interfaces:**
- Consumes: `jemscrape.errors.FetchError`.
- Produces:
  - `fetch(url, *, user_agent, timeout=30, retries=4, backoff_sleep=time.sleep, urlopen=<stdlib>) -> str`.
  - Retries on transient errors and HTTP 429 (longer backoff for 429), raising `FetchError` after `retries` attempts. `urlopen` and `backoff_sleep` are injected. `urlopen(request, timeout=...)` returns an object with `.read()` (bytes) and `.status` (int); a `urllib.error.HTTPError` with `.code == 429` triggers the 429 path.

- [ ] **Step 1: Write the failing test**

`assets/scraper-template/tests/test_fetch.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest assets/scraper-template/tests/test_fetch.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jemscrape.fetch'`

- [ ] **Step 3: Write minimal implementation**

`assets/scraper-template/jemscrape/fetch.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest assets/scraper-template/tests/test_fetch.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/fetch.py assets/scraper-template/tests/test_fetch.py
git commit -m "feat: resilient HTTP fetch with 429-aware backoff and injected opener"
```

---

### Task 5: Atomic cache + resume cursor

**Files:**
- Create: `assets/scraper-template/jemscrape/cache.py`
- Test: `assets/scraper-template/tests/test_cache.py`

**Interfaces:**
- Produces:
  - `atomic_write(path, text) -> None` — writes via temp file + `os.replace`.
  - `slug_for(url) -> str` — filesystem-safe slug from a URL's last path segment.
  - `cache_path(cache_dir, url) -> Path` — `<cache_dir>/<slug>.html`.
  - `is_cached(cache_dir, url) -> bool`; `read_cached(cache_dir, url) -> str`.
  - `Cursor(path)` with `.load()`, `.add(url)`, `.done(url) -> bool`, `.save()` — persists the set of completed URLs to `state/cursor.json` atomically for resume.

- [ ] **Step 1: Write the failing test**

`assets/scraper-template/tests/test_cache.py`:
```python
from jemscrape.cache import atomic_write, slug_for, cache_path, is_cached, read_cached, Cursor


def test_atomic_write_and_read(tmp_path):
    p = tmp_path / "sub" / "file.txt"
    atomic_write(p, "hello")
    assert p.read_text(encoding="utf-8") == "hello"
    # no leftover temp files
    assert list(p.parent.glob("*.tmp")) == []


def test_slug_is_filesystem_safe():
    slug = slug_for("https://example.com/a/b/c-fire%20extinguisher?x=1")
    assert "/" not in slug and "?" not in slug and " " not in slug
    assert slug


def test_cache_roundtrip(tmp_path):
    url = "https://example.com/p/widget-1"
    assert not is_cached(tmp_path, url)
    atomic_write(cache_path(tmp_path, url), "<html>1</html>")
    assert is_cached(tmp_path, url)
    assert read_cached(tmp_path, url) == "<html>1</html>"


def test_cursor_persists_and_reloads(tmp_path):
    cpath = tmp_path / "state" / "cursor.json"
    cur = Cursor(cpath)
    cur.load()
    assert not cur.done("https://x/1")
    cur.add("https://x/1")
    cur.save()

    reloaded = Cursor(cpath)
    reloaded.load()
    assert reloaded.done("https://x/1")
    assert not reloaded.done("https://x/2")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest assets/scraper-template/tests/test_cache.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jemscrape.cache'`

- [ ] **Step 3: Write minimal implementation**

`assets/scraper-template/jemscrape/cache.py`:
```python
import json
import os
import re
from pathlib import Path

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def atomic_write(path, text):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, p)


def slug_for(url):
    tail = url.rstrip("/").rsplit("/", 1)[-1] or url
    tail = tail.split("?", 1)[0].split("#", 1)[0]
    slug = _SAFE.sub("-", tail).strip("-")
    return slug or "index"


def cache_path(cache_dir, url):
    return Path(cache_dir) / f"{slug_for(url)}.html"


def is_cached(cache_dir, url):
    return cache_path(cache_dir, url).exists()


def read_cached(cache_dir, url):
    return cache_path(cache_dir, url).read_text(encoding="utf-8")


class Cursor:
    def __init__(self, path):
        self.path = Path(path)
        self._done = set()

    def load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self._done = set(data.get("done", []))
            except (OSError, json.JSONDecodeError):
                self._done = set()
        return self

    def done(self, url):
        return url in self._done

    def add(self, url):
        self._done.add(url)

    def save(self):
        atomic_write(self.path, json.dumps({"done": sorted(self._done)}, ensure_ascii=False, indent=2))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest assets/scraper-template/tests/test_cache.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/cache.py assets/scraper-template/tests/test_cache.py
git commit -m "feat: atomic cache writes + resume cursor (state/cursor.json)"
```

---

### Task 6: Run manifest

**Files:**
- Create: `assets/scraper-template/jemscrape/manifest.py`
- Test: `assets/scraper-template/tests/test_manifest.py`

**Interfaces:**
- Produces:
  - `Manifest(schema_version="1.0")` with `.record_scraped(url, record)`, `.record_error(url, message)`, `.record_skipped(url, reason)`, `.summary() -> dict` (counts), and `.write(path)` (atomic; includes `schema_version`, the three lists, and counts).

- [ ] **Step 1: Write the failing test**

`assets/scraper-template/tests/test_manifest.py`:
```python
import json

from jemscrape.manifest import Manifest


def test_records_and_summary():
    m = Manifest()
    m.record_scraped("https://x/1", {"sku": "A1"})
    m.record_skipped("https://x/2", "no sku")
    m.record_error("https://x/3", "timeout")
    s = m.summary()
    assert s == {"scraped": 1, "skipped": 1, "errors": 1}


def test_write_includes_schema_version(tmp_path):
    m = Manifest(schema_version="1.0")
    m.record_scraped("https://x/1", {"sku": "A1"})
    out = tmp_path / "manifest.json"
    m.write(out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0"
    assert data["counts"]["scraped"] == 1
    assert data["scraped"][0]["url"] == "https://x/1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest assets/scraper-template/tests/test_manifest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jemscrape.manifest'`

- [ ] **Step 3: Write minimal implementation**

`assets/scraper-template/jemscrape/manifest.py`:
```python
import json

from .cache import atomic_write


class Manifest:
    def __init__(self, schema_version="1.0"):
        self.schema_version = schema_version
        self.scraped = []
        self.skipped = []
        self.errors = []

    def record_scraped(self, url, record):
        self.scraped.append({"url": url, "record": record})

    def record_skipped(self, url, reason):
        self.skipped.append({"url": url, "reason": reason})

    def record_error(self, url, message):
        self.errors.append({"url": url, "message": message})

    def summary(self):
        return {"scraped": len(self.scraped), "skipped": len(self.skipped), "errors": len(self.errors)}

    def write(self, path):
        payload = {
            "schema_version": self.schema_version,
            "counts": self.summary(),
            "scraped": self.scraped,
            "skipped": self.skipped,
            "errors": self.errors,
        }
        atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest assets/scraper-template/tests/test_manifest.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/manifest.py assets/scraper-template/tests/test_manifest.py
git commit -m "feat: run manifest with schema_version and counts"
```

---

### Task 7: Runner (compose fetch + cache + pace + parse + manifest, resumable)

**Files:**
- Create: `assets/scraper-template/jemscrape/runner.py`
- Test: `assets/scraper-template/tests/test_runner.py`

**Interfaces:**
- Consumes: `Pacer` (Task 3), `cache` functions + `Cursor` (Task 5), `Manifest` (Task 6).
- Produces:
  - `run(*, urls, parse_fn, cache_dir, fetcher, pacer, cursor, manifest, reparse=False) -> dict`.
  - For each URL: if `cursor.done(url)` → skip entirely; elif cached and not `reparse` → read from cache (no fetch, no pacing); else → `fetcher(url)` then cache it and `pacer.wait()`. Then `parse_fn(html, url)` → a dict records "scraped", `None` records "skipped". A `fetcher` exception records "error" and continues. `cursor.add(url)` + `cursor.save()` after each URL. Returns `manifest.summary()`.
  - `fetcher(url) -> str` and `parse_fn(html, url) -> dict | None` are injected.

- [ ] **Step 1: Write the failing test**

`assets/scraper-template/tests/test_runner.py`:
```python
from jemscrape.runner import run
from jemscrape.pacing import Pacer
from jemscrape.cache import Cursor, is_cached
from jemscrape.manifest import Manifest


def _pacer():
    return Pacer(1, 1, 1, rng=lambda a, b: 1, randint=lambda a, b: 999, sleep=lambda s: None)


def _parse(html, url):
    return {"url": url, "len": len(html)} if "product" in html else None


def test_fetches_caches_and_parses(tmp_path):
    fetched = []

    def fetcher(url):
        fetched.append(url)
        return "product page"

    m = Manifest()
    summary = run(
        urls=["https://x/1", "https://x/2"],
        parse_fn=_parse, cache_dir=tmp_path / "data",
        fetcher=fetcher, pacer=_pacer(),
        cursor=Cursor(tmp_path / "state" / "cursor.json").load(), manifest=m,
    )
    assert summary == {"scraped": 2, "skipped": 0, "errors": 0}
    assert fetched == ["https://x/1", "https://x/2"]
    assert is_cached(tmp_path / "data", "https://x/1")


def test_resume_skips_done_urls(tmp_path):
    cur = Cursor(tmp_path / "state" / "cursor.json").load()
    cur.add("https://x/1")
    cur.save()

    fetched = []

    def fetcher(url):
        fetched.append(url)
        return "product page"

    run(urls=["https://x/1", "https://x/2"], parse_fn=_parse, cache_dir=tmp_path / "data",
        fetcher=fetcher, pacer=_pacer(), cursor=cur, manifest=Manifest())
    assert fetched == ["https://x/2"]  # x/1 was already done


def test_cached_url_not_refetched(tmp_path):
    from jemscrape.cache import atomic_write, cache_path
    atomic_write(cache_path(tmp_path / "data", "https://x/1"), "product cached")

    def fetcher(url):
        raise AssertionError("should not fetch a cached url")

    m = Manifest()
    run(urls=["https://x/1"], parse_fn=_parse, cache_dir=tmp_path / "data",
        fetcher=fetcher, pacer=_pacer(),
        cursor=Cursor(tmp_path / "state" / "cursor.json").load(), manifest=m)
    assert m.summary()["scraped"] == 1


def test_fetch_error_recorded_and_continues(tmp_path):
    def fetcher(url):
        if url.endswith("1"):
            raise RuntimeError("down")
        return "product page"

    m = Manifest()
    summary = run(urls=["https://x/1", "https://x/2"], parse_fn=_parse,
                  cache_dir=tmp_path / "data", fetcher=fetcher, pacer=_pacer(),
                  cursor=Cursor(tmp_path / "state" / "cursor.json").load(), manifest=m)
    assert summary == {"scraped": 1, "skipped": 0, "errors": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest assets/scraper-template/tests/test_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jemscrape.runner'`

- [ ] **Step 3: Write minimal implementation**

`assets/scraper-template/jemscrape/runner.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest assets/scraper-template/tests/test_runner.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/runner.py assets/scraper-template/tests/test_runner.py
git commit -m "feat: resumable runner composing fetch/cache/pace/parse/manifest"
```

---

### Task 8: CLI entry (`scrape.py`) + smoke gate + config example

**Files:**
- Create: `assets/scraper-template/scrape.py`
- Create: `assets/scraper-template/smoke_test.py`
- Create: `assets/scraper-template/config.json.example`
- Test: `assets/scraper-template/tests/test_smoke.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `scrape.py`: `build_pacer(cfg) -> Pacer`; `preflight(config_path, authz_path, target_url, now) -> tuple[dict, Authorization]` (loads+validates config AND authorization, raising on any failure — this is the runtime gate); `main(argv=None) -> int` (argparse `--limit`, `--reparse`; exits non-zero on gate failure). Discovery + `parse_fn` are provided by the site adaptation; `main` imports them from a local `site_adapter.py` (documented stub, created per site — not in this plan).
  - `smoke_test.py`: `run_smoke(config_path, authz_path, now) -> int` — validates config + authorization and returns 0/non-zero; used as the fail-closed pre-run gate.

- [ ] **Step 1: Write the failing test**

`assets/scraper-template/tests/test_smoke.py`:
```python
import json
from datetime import datetime, timezone

from scrape import preflight, build_pacer
from smoke_test import run_smoke
from jemscrape.errors import AuthorizationError, ConfigError

import pytest

NOW = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)


def _write(tmp_path):
    cfg = {
        "target_domain": "example.com", "runtime": "local",
        "rate_limit_floor_seconds": 2.5, "user_agent": "UA/1",
        "min_delay_seconds": 2.5, "max_delay_seconds": 5.0,
    }
    authz = {
        "target_domain": "example.com", "authorization_type": "public_competitor",
        "approver": "henrique", "approved_at": "2026-07-01T09:00:00+00:00",
        "expires_at": "2026-07-08T09:00:00+00:00", "rate_limit_floor_seconds": 2.5,
        "robots_status": "allowed", "robots_override_ref": None,
        "requires_approval": False, "scope": "catalog",
    }
    cp = tmp_path / "config.json"
    ap = tmp_path / ".scrape-authorization.json"
    cp.write_text(json.dumps(cfg), encoding="utf-8")
    ap.write_text(json.dumps(authz), encoding="utf-8")
    return cp, ap


def test_preflight_ok_returns_cfg_and_auth(tmp_path):
    cp, ap = _write(tmp_path)
    cfg, auth = preflight(cp, ap, "https://example.com/", NOW)
    assert cfg["target_domain"] == "example.com"
    assert auth.approver == "henrique"


def test_preflight_blocks_expired_authorization(tmp_path):
    cp, ap = _write(tmp_path)
    data = json.loads(ap.read_text())
    data["expires_at"] = "2026-06-01T00:00:00+00:00"
    ap.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(AuthorizationError):
        preflight(cp, ap, "https://example.com/", NOW)


def test_preflight_blocks_missing_authorization(tmp_path):
    cp, _ = _write(tmp_path)
    with pytest.raises(AuthorizationError):
        preflight(cp, tmp_path / "nope.json", "https://example.com/", NOW)


def test_build_pacer_uses_floor(tmp_path):
    cp, _ = _write(tmp_path)
    cfg = json.loads(cp.read_text())
    pacer = build_pacer(cfg)
    assert pacer.floor == 2.5


def test_run_smoke_returns_zero_on_valid(tmp_path):
    cp, ap = _write(tmp_path)
    assert run_smoke(cp, ap, NOW) == 0


def test_run_smoke_nonzero_on_bad_config(tmp_path):
    cp, ap = _write(tmp_path)
    cp.write_text("{bad json", encoding="utf-8")
    assert run_smoke(cp, ap, NOW) != 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest assets/scraper-template/tests/test_smoke.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrape'`

- [ ] **Step 3: Write minimal implementation**

`assets/scraper-template/scrape.py`:
```python
"""Generated scraper entry point. Runtime compliance gate lives in preflight()."""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from jemscrape.config import load_config, validate_config
from jemscrape.authz import load_authorization, validate as validate_authz
from jemscrape.pacing import Pacer

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"
AUTHZ_PATH = HERE / ".scrape-authorization.json"


def build_pacer(cfg):
    floor = cfg["rate_limit_floor_seconds"]
    lo = cfg.get("min_delay_seconds", floor)
    hi = cfg.get("max_delay_seconds", max(floor, lo))
    return Pacer(min_delay=lo, max_delay=hi, floor=floor)


def preflight(config_path, authz_path, target_url, now):
    cfg = load_config(config_path)
    validate_config(cfg)
    auth = load_authorization(authz_path)
    validate_authz(auth, target_url, now)
    return cfg, auth


def main(argv=None):
    parser = argparse.ArgumentParser(description="JEM scraper")
    parser.add_argument("--limit", type=int, default=0, help="max URLs (0 = all)")
    parser.add_argument("--reparse", action="store_true", help="reparse cache without fetching")
    args = parser.parse_args(argv)

    cfg = load_config(CONFIG_PATH)
    validate_config(cfg)
    target_url = f"https://{cfg['target_domain']}/"
    try:
        preflight(CONFIG_PATH, AUTHZ_PATH, target_url, datetime.now(timezone.utc))
    except Exception as exc:  # fail-closed: no run without a valid gate
        print(f"[gate] BLOCKED: {exc}", file=sys.stderr)
        return 2

    # Site adaptation supplies discover() -> list[str] and parse(html, url) -> dict | None.
    from site_adapter import discover, parse  # created per site (not in this plan)
    from jemscrape.cache import Cursor
    from jemscrape.manifest import Manifest
    from jemscrape.fetch import fetch as http_fetch
    from jemscrape.runner import run

    urls = discover(cfg)
    if args.limit:
        urls = urls[: args.limit]

    cache_dir = HERE / "data"
    cursor = Cursor(HERE / "state" / "cursor.json").load()
    manifest = Manifest()
    pacer = build_pacer(cfg)

    def fetcher(url):
        return http_fetch(url, user_agent=cfg["user_agent"])

    summary = run(urls=urls, parse_fn=parse, cache_dir=cache_dir, fetcher=fetcher,
                  pacer=pacer, cursor=cursor, manifest=manifest, reparse=args.reparse)
    manifest.write(HERE / "exports" / "scrape_manifest.json")
    print(f"[done] {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

`assets/scraper-template/smoke_test.py`:
```python
"""Fail-closed pre-run gate: validate config + authorization before any full run."""
import sys
from datetime import datetime, timezone
from pathlib import Path

from jemscrape.config import load_config, validate_config
from jemscrape.authz import load_authorization, validate as validate_authz

HERE = Path(__file__).resolve().parent


def run_smoke(config_path, authz_path, now):
    try:
        cfg = load_config(config_path)
        validate_config(cfg)
        auth = load_authorization(authz_path)
        validate_authz(auth, f"https://{cfg['target_domain']}/", now)
    except Exception as exc:
        print(f"[smoke] FAIL: {exc}", file=sys.stderr)
        return 1
    print("[smoke] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(
        run_smoke(HERE / "config.json", HERE / ".scrape-authorization.json",
                  datetime.now(timezone.utc))
    )
```

`assets/scraper-template/config.json.example`:
```json
{
  "target_domain": "example.com",
  "runtime": "local",
  "user_agent": "Mozilla/5.0 (compatible; JEMScrape/1.0; +mailto:ops@jemsystems.com)",
  "rate_limit_floor_seconds": 2.5,
  "min_delay_seconds": 2.5,
  "max_delay_seconds": 5.0
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest assets/scraper-template/tests/test_smoke.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Run the full suite and commit**

Run: `python -m pytest -q`
Expected: all tests pass.

```bash
git add assets/scraper-template/scrape.py assets/scraper-template/smoke_test.py assets/scraper-template/config.json.example assets/scraper-template/tests/test_smoke.py
git commit -m "feat: scrape.py CLI with runtime gate + fail-closed smoke test + config example"
```

---

## Self-Review

**1. Spec coverage (this plan's slice — spec §3, §5.1 gate, §8 scraper-template, §10 runtime enforcement, §13 data/state/exports layout):**
- Zero-dep stdlib core (§3) → all `jemscrape/` modules import only stdlib. ✓
- Runtime authorization gate (§10) → Task 2 (`authz.validate`) + Task 8 (`preflight`/`main` fail-closed, returns 2). ✓
- `rate_limit_floor_seconds` mandatory (§10.1) → Task 1 validation + Task 3 enforcement. ✓
- robots precedence matrix (§10.2) → Task 2 tests all three `authorization_type` × disallowed cases. ✓
- Atomic writes (§13) → Task 5 `atomic_write` used by cache, cursor, manifest. ✓
- Resume via `state/cursor.json` versioned, `data/` raw cache (§13) → Task 5 `Cursor`, Task 7 resume; `scrape.py` writes cache to `data/`, manifest to `exports/`. ✓
- `schema_version` in manifest (§7) → Task 6. ✓
- Humanized pacing + coffee breaks + floor (§5, anti-ban) → Task 3. ✓
- 429-aware backoff (anti-ban) → Task 4. ✓
- Canary `--limit` (§9) → Task 8 argparse. ✓ (o canary foi absorvido pelo warm-up lap, §9.1 — o flag `--limit` continua valendo)
- Smoke gate = `smoke_test.py`, terminology unified (§15) → Task 8. ✓
- **Deferred to later plans (correctly out of scope):** discovery/sitemap + `parse_fn` (site-specific, referenced as `site_adapter.py`), normalize→canonical/exports CSV+wiki (Plan 2), Playwright auth path (Plan 3), warm-up lap + review de sinal verde (Plan 4, §9.1), Actions workflow (Plan 5), onboarding (Plan 6), plugin packaging (Plan 7). Noted in the plan intro.

**2. Placeholder scan:** No TBD/TODO; every code step contains complete runnable code; every test step shows the assertions. The only external reference is `site_adapter.py` (`discover`/`parse`), which is explicitly a per-site file produced by a later plan, not a placeholder within this plan's deliverable — `main` is untested for that path here by design (tested modules are the injected core).

**3. Type consistency:** Names verified across tasks — `atomic_write`/`cache_path`/`is_cached`/`read_cached`/`Cursor(.load/.done/.add/.save)` (Task 5) used verbatim in Tasks 6/7/8; `Pacer(min_delay,max_delay,floor,rng,randint,sleep).wait(heavy)` (Task 3) used in Task 7/8; `fetch(url, user_agent=…, urlopen=…, backoff_sleep=…)` (Task 4) wrapped by `fetcher` in Task 8; `Manifest.record_scraped/record_skipped/record_error/summary/write` (Task 6) used in Task 7; `validate(auth, target_url, now)` and `Authorization` fields (Task 2) used in Task 8 `preflight`. Consistent.
