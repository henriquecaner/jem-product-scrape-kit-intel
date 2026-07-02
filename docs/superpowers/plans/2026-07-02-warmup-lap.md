# Warm-Up Lap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the mandatory warm-up lap (spec §9.1): sample 10–50 product URLs, detect the four site signals (render mode, auth/paywall, anti-bot/geo, parse shape), emit a recon report + operator-prep checklist, and add a fail-closed warm-up-verdict gate so the runtime refuses a full run without a GREEN verdict.

**Architecture:** Pure detector functions in `jemscrape/signals.py` (testable in isolation), an orchestrator `jemscrape/recon.py` that fetches a sample via dependency injection and aggregates the signals into a `WarmupReport`, a runtime gate `jemscrape/warmup_gate.py` mirroring `authz.py`, and a root CLI `warmup.py`. A new `fetch.probe()` returns status+headers+body without raising on 4xx/5xx (the existing `fetch()` discards the status). The two-agent green-light review (Opus 4.8 `xhigh` reviewer + Sonnet 5 advisor) is orchestrated by the `scrape-warmup` skill and is OUT OF SCOPE for this Python plan — the plan builds and tests the artifact it consumes (`.scrape-warmup.json`) and the gate that enforces it.

**Tech Stack:** Python 3, standard library only. Tests via `pytest`. Run with `.venv/bin/python -m pytest`.

## Global Constraints

- **Runtime is Python 3 stdlib-only.** No third-party imports in `jemscrape/`, `scrape.py`, or `warmup.py`. (Playwright is the optional auth path, Plano 3 — not this plan.)
- **Dependency injection for testability.** Inject `probe_fn`, `parse_fn`, and `urlopen`; never hit the network in a unit test.
- **Fail-closed gates live in runtime code.** The warm-up-verdict gate is enforced in `scrape.py` (the full-run entry point), NOT in `preflight` (which `smoke_test.py` reuses — the smoke test must stay compliance-only, pre-warm-up).
- **Reuse existing modules:** `jemscrape.fetch`, `jemscrape.normalize.normalize`, `jemscrape.canonical.CanonicalRecord`, `jemscrape.cache.atomic_write`, and the `authz.py` load/validate pattern. Do not duplicate their logic.
- **Model policy (JEM):** never Haiku. The green-light review uses Opus 4.8 `xhigh` (reviewer) + Sonnet 5 (advisor) — that review is the skill's job, not code in this plan.
- **Sample discovery is injected (DI) and deferred to Plano 3.** `run_warmup` receives a list of sample URLs; the CLI reads them from a `--sample <json>` file.
- **Tests:** run `.venv/bin/python -m pytest -q`. New tests must keep the suite green (currently 97 passing). Test output must be pristine.
- **Commits** end with the trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

## File Structure

- `assets/scraper-template/jemscrape/fetch.py` — MODIFY: add `Probe` dataclass + `probe()` (non-raising status/headers/body/final_url).
- `assets/scraper-template/jemscrape/signals.py` — CREATE: `detect_render`, `detect_auth`, `detect_antibot`, `analyze_shape` (pure functions).
- `assets/scraper-template/jemscrape/recon.py` — CREATE: `WarmupReport`, `run_warmup`, `build_checklist`, `write_report`.
- `assets/scraper-template/jemscrape/warmup_gate.py` — CREATE: `WarmupVerdict`, `load_warmup_verdict`, `validate_warmup`.
- `assets/scraper-template/jemscrape/errors.py` — MODIFY: add `WarmupError`.
- `assets/scraper-template/scrape.py` — MODIFY: add `require_warmup()` helper + wire it into `main()` (fail-closed before the full run).
- `assets/scraper-template/warmup.py` — CREATE: root CLI (`main`), preflight compliance gate + `run_warmup` + report.
- `.gitignore` — MODIFY: ignore `.scrape-warmup.json` (per-run gate artifact, like `.scrape-authorization.json`).
- Tests: `tests/test_probe.py`, `tests/test_signals.py`, `tests/test_recon.py`, `tests/test_warmup_gate.py`, `tests/test_warmup_cli.py`.

---

### Task 1: `fetch.probe()` — non-raising status/headers/body

**Files:**
- Modify: `assets/scraper-template/jemscrape/fetch.py`
- Test: `assets/scraper-template/tests/test_probe.py`

**Interfaces:**
- Consumes: `_default_urlopen` (existing in `fetch.py`), `FetchError` (existing).
- Produces:
  - `Probe` dataclass: `status: int`, `headers: dict` (lowercased keys), `body: str`, `final_url: str`.
  - `probe(url, *, user_agent, timeout=30, urlopen=_default_urlopen) -> Probe`. Returns a `Probe` for ANY HTTP response including 4xx/5xx (captures the code); raises `FetchError` only on a network-level `URLError`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_probe.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_probe.py -q`
Expected: FAIL with `ImportError: cannot import name 'probe'`.

- [ ] **Step 3: Write minimal implementation**

Add to `assets/scraper-template/jemscrape/fetch.py` (keep the existing `fetch`/`_default_urlopen`; add the import and the new code):

```python
from dataclasses import dataclass


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


def probe(url, *, user_agent, timeout=30, urlopen=_default_urlopen):
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
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
```

Put the `from dataclasses import dataclass` line with the other imports at the top of `fetch.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_probe.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/fetch.py assets/scraper-template/tests/test_probe.py
git commit -m "feat: fetch.probe() — non-raising status/headers/body for warm-up

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `signals.detect_render`

**Files:**
- Create: `assets/scraper-template/jemscrape/signals.py`
- Test: `assets/scraper-template/tests/test_signals.py`

**Interfaces:**
- Produces: `detect_render(body: str) -> dict` with keys `mode` (`"server"|"spa"`), `text_len` (int), `script_ratio` (float), `markers` (list[str]). Strips `<script>` blocks before measuring visible text so JSON payloads don't count as content.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_signals.py
from jemscrape.signals import detect_render


def test_detect_render_server_rendered_page():
    body = "<html><body><h1>Fire-Lite ES-200X</h1>" + ("<p>Addressable panel. </p>" * 40) + "</body></html>"
    out = detect_render(body)
    assert out["mode"] == "server"
    assert out["text_len"] > 200


def test_detect_render_spa_shell():
    body = '<html><body><div id="root"></div><script>' + ("x=1;" * 500) + "</script></body></html>"
    out = detect_render(body)
    assert out["mode"] == "spa"
    assert 'id="root"' in out["markers"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_signals.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'jemscrape.signals'`.

- [ ] **Step 3: Write minimal implementation**

```python
# assets/scraper-template/jemscrape/signals.py
import re

_TAG = re.compile(r"<[^>]+>")
_SCRIPT = re.compile(r"<script\b.*?</script>", re.I | re.S)
_WS = re.compile(r"\s+")

_SPA_MARKERS = (
    'id="root"', "id='root'", 'id="app"', "id='app'",
    "<app-root", "ng-app", "__next_data__", "window.__nuxt__",
    "data-reactroot", "window.__initial_state__",
)


def detect_render(body):
    body = body or ""
    low = body.lower()
    without_scripts = _SCRIPT.sub(" ", body)
    visible = _WS.sub(" ", _TAG.sub(" ", without_scripts)).strip()
    text_len = len(visible)
    markers = [m for m in _SPA_MARKERS if m in low]
    total = max(len(body), 1)
    script_len = sum(len(m.group(0)) for m in _SCRIPT.finditer(body))
    script_ratio = script_len / total
    spa = bool(markers) and text_len < 500
    if not spa and text_len < 200 and script_ratio > 0.5:
        spa = True
    return {
        "mode": "spa" if spa else "server",
        "text_len": text_len,
        "script_ratio": round(script_ratio, 3),
        "markers": markers,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_signals.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/signals.py assets/scraper-template/tests/test_signals.py
git commit -m "feat: signals.detect_render — server-rendered vs SPA/JS shell

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `signals.detect_auth`

**Files:**
- Modify: `assets/scraper-template/jemscrape/signals.py`
- Test: `assets/scraper-template/tests/test_signals.py`

**Interfaces:**
- Consumes: `Probe` (Task 1) — reads `.status`, `.final_url`, `.body`.
- Produces: `detect_auth(probe) -> dict` with keys `auth_required` (bool), `signals` (list[str]).

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_signals.py
from jemscrape.signals import detect_auth
from jemscrape.fetch import Probe


def _probe(status=200, final_url="https://x/product/1", body=""):
    return Probe(status=status, headers={}, body=body, final_url=final_url)


def test_detect_auth_flags_403():
    out = detect_auth(_probe(status=403))
    assert out["auth_required"] is True


def test_detect_auth_flags_login_redirect():
    out = detect_auth(_probe(final_url="https://x/account/login?next=/p"))
    assert out["auth_required"] is True


def test_detect_auth_flags_price_login_body():
    out = detect_auth(_probe(body="<div>Sign in to see price</div>"))
    assert out["auth_required"] is True


def test_detect_auth_clean_product_page():
    out = detect_auth(_probe(body="<h1>Widget</h1><span>$19.99</span>"))
    assert out["auth_required"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_signals.py -k detect_auth -q`
Expected: FAIL with `ImportError: cannot import name 'detect_auth'`.

- [ ] **Step 3: Write minimal implementation**

Add to `assets/scraper-template/jemscrape/signals.py`:

```python
_LOGIN_PATH = re.compile(r"/(login|signin|sign-in|account|myaccount|auth)(/|$|\?)", re.I)
_LOGIN_BODY = (
    "sign in to see price", "log in to view", "please sign in",
    "login required", "member price", 'type="password"',
)


def detect_auth(probe):
    signals = []
    if probe.status in (401, 403):
        signals.append(f"status {probe.status}")
    if _LOGIN_PATH.search(probe.final_url or ""):
        signals.append(f"auth URL: {probe.final_url}")
    low = (probe.body or "").lower()
    for marker in _LOGIN_BODY:
        if marker in low:
            signals.append(f"body marker: {marker!r}")
    return {"auth_required": bool(signals), "signals": signals}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_signals.py -k detect_auth -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/signals.py assets/scraper-template/tests/test_signals.py
git commit -m "feat: signals.detect_auth — login/paywall detection

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `signals.detect_antibot`

**Files:**
- Modify: `assets/scraper-template/jemscrape/signals.py`
- Test: `assets/scraper-template/tests/test_signals.py`

**Interfaces:**
- Consumes: `Probe` (Task 1) — reads `.status`, `.headers`, `.body`.
- Produces: `detect_antibot(probe) -> dict` with keys `blocked` (bool), `kind` (`"rate"|"cloudflare"|"geo"|None`), `signals` (list[str]).

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_signals.py
from jemscrape.signals import detect_antibot


def test_detect_antibot_429_rate():
    out = detect_antibot(Probe(status=429, headers={}, body="", final_url="https://x/p"))
    assert out["blocked"] is True and out["kind"] == "rate"


def test_detect_antibot_cloudflare_header():
    out = detect_antibot(Probe(status=503, headers={"cf-ray": "abc"}, body="Just a moment...", final_url="https://x/p"))
    assert out["blocked"] is True and out["kind"] == "cloudflare"


def test_detect_antibot_geo_block_body():
    out = detect_antibot(Probe(status=200, headers={}, body="This content is not available in your country.", final_url="https://x/p"))
    assert out["blocked"] is True and out["kind"] == "geo"


def test_detect_antibot_clean():
    out = detect_antibot(Probe(status=200, headers={}, body="<h1>Widget</h1>", final_url="https://x/p"))
    assert out["blocked"] is False and out["kind"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_signals.py -k detect_antibot -q`
Expected: FAIL with `ImportError: cannot import name 'detect_antibot'`.

- [ ] **Step 3: Write minimal implementation**

Add to `assets/scraper-template/jemscrape/signals.py`:

```python
_CF_BODY = (
    "just a moment", "attention required", "cf-chl",
    "checking your browser", "cf-browser-verification",
)
_GEO_BODY = (
    "not available in your country", "access denied",
    "blocked in your region", "not available in your region",
)


def detect_antibot(probe):
    signals = []
    kind = None
    if probe.status == 429:
        signals.append("status 429 (rate limited)")
        kind = "rate"
    if "cf-ray" in probe.headers or "cf-mitigated" in probe.headers:
        signals.append("cloudflare header (cf-ray)")
        kind = kind or "cloudflare"
    low = (probe.body or "").lower()
    for marker in _CF_BODY:
        if marker in low:
            signals.append(f"cloudflare body: {marker!r}")
            kind = kind or "cloudflare"
            break
    for marker in _GEO_BODY:
        if marker in low:
            signals.append(f"geo-block body: {marker!r}")
            kind = kind or "geo"
            break
    return {"blocked": bool(signals), "kind": kind, "signals": signals}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_signals.py -k detect_antibot -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/signals.py assets/scraper-template/tests/test_signals.py
git commit -m "feat: signals.detect_antibot — 429 / Cloudflare / geo-block detection

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: `signals.analyze_shape`

**Files:**
- Modify: `assets/scraper-template/jemscrape/signals.py`
- Test: `assets/scraper-template/tests/test_signals.py`

**Interfaces:**
- Consumes: a list of `CanonicalRecord` (from `jemscrape.canonical`) — reads `.name`, `.sku`, `.product_id`, `.prices`, `.images`, `.breadcrumbs`, `.stock`.
- Produces: `analyze_shape(records) -> dict` with keys `count` (int), `coverage` (dict of field -> fraction 0..1), `price_bands` (sorted list), `variant_collisions` (int, product_ids appearing >1 pre-collapse), `stock_by_location` (int).

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_signals.py
from jemscrape.signals import analyze_shape
from jemscrape.normalize import normalize


def _rec(pid, name, prices=None, images=None, breadcrumbs=None):
    return normalize(
        {"product_id": pid, "name": name, "sku": pid,
         "prices": prices or [], "images": images or [], "breadcrumbs": breadcrumbs or []},
        source_site="x", source_url="https://x/p", scraped_at="t",
        authorization_ref="a", raw_ref="r")


def test_analyze_shape_empty():
    out = analyze_shape([])
    assert out["count"] == 0


def test_analyze_shape_coverage_and_bands_and_collisions():
    records = [
        _rec("A1", "Widget", prices=[{"band": "trade", "value": 10}], images=["u"], breadcrumbs=["Fire"]),
        _rec("A1", "Widget v2", prices=[{"band": "list", "value": 12}]),   # same product_id -> collision
        _rec("B2", "Gadget"),                                              # no price/image/breadcrumb
    ]
    out = analyze_shape(records)
    assert out["count"] == 3
    assert out["coverage"]["name"] == 1.0
    assert out["coverage"]["price"] == round(2 / 3, 3)
    assert out["price_bands"] == ["list", "trade"]
    assert out["variant_collisions"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_signals.py -k analyze_shape -q`
Expected: FAIL with `ImportError: cannot import name 'analyze_shape'`.

- [ ] **Step 3: Write minimal implementation**

Add to `assets/scraper-template/jemscrape/signals.py`:

```python
def analyze_shape(records):
    n = len(records)
    if n == 0:
        return {"count": 0, "coverage": {}, "price_bands": [],
                "variant_collisions": 0, "stock_by_location": 0}

    def frac(pred):
        return round(sum(1 for r in records if pred(r)) / n, 3)

    coverage = {
        "name": frac(lambda r: bool(r.name)),
        "sku": frac(lambda r: bool(r.sku)),
        "product_id": frac(lambda r: bool(r.product_id)),
        "price": frac(lambda r: bool(r.prices)),
        "image": frac(lambda r: bool(r.images)),
        "breadcrumbs": frac(lambda r: bool(r.breadcrumbs)),
    }
    bands = sorted({p.get("band") for r in records for p in r.prices
                    if isinstance(p, dict) and p.get("band")})
    seen = {}
    for r in records:
        seen[r.product_id] = seen.get(r.product_id, 0) + 1
    collisions = sum(1 for count in seen.values() if count > 1)
    stock_by_loc = sum(1 for r in records if r.stock.get("by_location"))
    return {
        "count": n,
        "coverage": coverage,
        "price_bands": bands,
        "variant_collisions": collisions,
        "stock_by_location": stock_by_loc,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_signals.py -q`
Expected: PASS (all signals tests).

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/signals.py assets/scraper-template/tests/test_signals.py
git commit -m "feat: signals.analyze_shape — field coverage, price bands, variant collisions

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: `recon.run_warmup` + report + checklist

**Files:**
- Create: `assets/scraper-template/jemscrape/recon.py`
- Test: `assets/scraper-template/tests/test_recon.py`

**Interfaces:**
- Consumes: `detect_render`/`detect_auth`/`detect_antibot`/`analyze_shape` (Tasks 2–5), `normalize` (existing), `atomic_write` (existing), `FetchError` (existing), `Probe` (Task 1).
- Produces:
  - `WarmupReport` dataclass: `source_site, sampled, fetched, spa_count, auth_count, antibot_count, fetch_errors, shape, per_url, checklist`; method `to_dict()`.
  - `build_checklist(*, spa_count, auth_count, antibot_count, shape) -> list[str]`.
  - `run_warmup(sample_urls, *, probe_fn, parse_fn, source_site, scraped_at, authorization_ref, raw_ref="") -> WarmupReport`. For each URL: `probe_fn(url)` → run the three probe detectors; only when the page is server-rendered, unauthenticated, and unblocked does it call `parse_fn(body, url)` and `normalize(...)`. A URL whose `probe_fn` raises `FetchError` is counted in `fetch_errors` and skipped.
  - `write_report(report, path)` — atomic JSON write.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_recon.py
import json

from jemscrape.recon import run_warmup, write_report, WarmupReport
from jemscrape.fetch import Probe
from jemscrape.errors import FetchError

SPA_BODY = '<html><body><div id="root"></div><script>' + ("x=1;" * 500) + "</script></body></html>"
SERVER_BODY = "<html><body><h1>Widget</h1>" + ("<p>desc </p>" * 40) + "</body></html>"


def _fake_probe(mapping):
    def probe_fn(url):
        val = mapping[url]
        if isinstance(val, Exception):
            raise val
        return val
    return probe_fn


def _parse(body, url):
    # Minimal fake site adapter: returns a raw record only for the server page.
    if "Widget" in body:
        return {"product_id": "A1", "name": "Widget", "sku": "A1",
                "prices": [{"band": "trade", "value": 10}]}
    return None


def test_run_warmup_aggregates_signals_and_shape():
    mapping = {
        "https://x/spa": Probe(status=200, headers={}, body=SPA_BODY, final_url="https://x/spa"),
        "https://x/server": Probe(status=200, headers={}, body=SERVER_BODY, final_url="https://x/server"),
        "https://x/auth": Probe(status=403, headers={}, body="", final_url="https://x/account/login"),
        "https://x/dead": FetchError("boom"),
    }
    report = run_warmup(
        list(mapping.keys()), probe_fn=_fake_probe(mapping), parse_fn=_parse,
        source_site="x", scraped_at="t", authorization_ref="a")
    assert report.sampled == 4
    assert report.fetched == 3          # dead one raised
    assert report.fetch_errors == 1
    assert report.spa_count == 1
    assert report.auth_count == 1
    assert report.shape["count"] == 1   # only the server page parsed+normalized
    assert any("SPA" in c or "JS" in c for c in report.checklist)


def test_write_report_roundtrips(tmp_path):
    report = WarmupReport(source_site="x", sampled=0, fetched=0, spa_count=0,
                          auth_count=0, antibot_count=0, fetch_errors=0,
                          shape={"count": 0}, per_url=[], checklist=["ok"])
    out = tmp_path / ".scrape-warmup-report.json"
    write_report(report, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["source_site"] == "x" and data["checklist"] == ["ok"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_recon.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'jemscrape.recon'`.

- [ ] **Step 3: Write minimal implementation**

```python
# assets/scraper-template/jemscrape/recon.py
import json
from dataclasses import dataclass, asdict

from .signals import detect_render, detect_auth, detect_antibot, analyze_shape
from .normalize import normalize
from .cache import atomic_write
from .errors import FetchError


@dataclass
class WarmupReport:
    source_site: str
    sampled: int
    fetched: int
    spa_count: int
    auth_count: int
    antibot_count: int
    fetch_errors: int
    shape: dict
    per_url: list
    checklist: list

    def to_dict(self):
        return asdict(self)


def build_checklist(*, spa_count, auth_count, antibot_count, shape):
    items = []
    if spa_count:
        items.append("Site renderiza via JS (SPA): habilite o navegador/Playwright (Plano 3) — "
                     "o fetch HTTP puro não enxerga produto.")
    if auth_count:
        items.append("Login/paywall detectado: capture a sessão (storage_state) e logue no site antes do run.")
    if antibot_count:
        items.append("Anti-bot/geo detectado: configure proxy de país ou promova para VM (§5).")
    cov = shape.get("coverage", {})
    if cov and cov.get("price", 1) < 0.5:
        items.append("Cobertura de preço < 50%: confirme se o preço exige login ou ajuste o parser.")
    if not items:
        items.append("Nenhum bloqueio detectado no HTTP puro — pronto para o review de sinal verde.")
    return items


def run_warmup(sample_urls, *, probe_fn, parse_fn, source_site,
               scraped_at, authorization_ref, raw_ref=""):
    per_url = []
    records = []
    spa_count = auth_count = antibot_count = fetch_errors = fetched = 0
    for url in sample_urls:
        entry = {"url": url}
        try:
            pr = probe_fn(url)
        except FetchError as exc:
            fetch_errors += 1
            entry["error"] = str(exc)
            per_url.append(entry)
            continue
        fetched += 1
        render = detect_render(pr.body)
        auth = detect_auth(pr)
        antibot = detect_antibot(pr)
        entry.update(status=pr.status, render=render, auth=auth, antibot=antibot)
        if render["mode"] == "spa":
            spa_count += 1
        if auth["auth_required"]:
            auth_count += 1
        if antibot["blocked"]:
            antibot_count += 1
        if render["mode"] == "server" and not auth["auth_required"] and not antibot["blocked"]:
            raw = parse_fn(pr.body, url)
            entry["parsed"] = bool(raw)
            if raw:
                records.append(normalize(
                    raw, source_site=source_site, source_url=url,
                    scraped_at=scraped_at, authorization_ref=authorization_ref,
                    raw_ref=raw_ref))
        per_url.append(entry)
    shape = analyze_shape(records)
    checklist = build_checklist(spa_count=spa_count, auth_count=auth_count,
                                antibot_count=antibot_count, shape=shape)
    return WarmupReport(
        source_site=source_site, sampled=len(sample_urls), fetched=fetched,
        spa_count=spa_count, auth_count=auth_count, antibot_count=antibot_count,
        fetch_errors=fetch_errors, shape=shape, per_url=per_url, checklist=checklist)


def write_report(report, path):
    atomic_write(path, json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_recon.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/recon.py assets/scraper-template/tests/test_recon.py
git commit -m "feat: recon.run_warmup — aggregate 4 signals into report + operator checklist

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: root `warmup.py` CLI

**Files:**
- Create: `assets/scraper-template/warmup.py`
- Test: `assets/scraper-template/tests/test_warmup_cli.py`

**Interfaces:**
- Consumes: `load_config` (existing), `preflight` (from `scrape.py`), `probe` (Task 1), `run_warmup`/`write_report` (Task 6).
- Produces: `main(argv=None, *, probe_fn=None, parse_fn=None) -> int`. Runs the compliance gate (`preflight`) first (fail-closed → exit 2); reads a `--sample` JSON list of URLs; runs `run_warmup`; writes the recon report to `--out`; prints the checklist. `probe_fn`/`parse_fn` default to the real `fetch.probe` and a lazily-imported `site_adapter.parse`, and are injectable for tests.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_warmup_cli.py
import json
from datetime import datetime, timezone, timedelta

import warmup
from jemscrape.fetch import Probe

SERVER_BODY = "<html><body><h1>Widget</h1>" + ("<p>d </p>" * 40) + "</body></html>"


def _write_valid_gate_files(tmp_path):
    now = datetime.now(timezone.utc)
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "target_domain": "example.com", "runtime": "local",
        "user_agent": "UA", "rate_limit_floor_seconds": 8,
    }), encoding="utf-8")
    authz = tmp_path / ".scrape-authorization.json"
    authz.write_text(json.dumps({
        "target_domain": "example.com", "authorization_type": "public_competitor",
        "approver": "H", "approved_at": now.isoformat(),
        "expires_at": (now + timedelta(days=1)).isoformat(),
        "rate_limit_floor_seconds": 8, "robots_status": "allowed",
        "robots_override_ref": None, "requires_approval": False, "scope": "https://example.com/",
    }), encoding="utf-8")
    return cfg, authz


def test_warmup_cli_success_writes_report(tmp_path):
    cfg, authz = _write_valid_gate_files(tmp_path)
    sample = tmp_path / "sample.json"
    sample.write_text(json.dumps(["https://example.com/product/1"]), encoding="utf-8")
    out = tmp_path / ".scrape-warmup-report.json"

    def fake_probe(url):
        return Probe(status=200, headers={}, body=SERVER_BODY, final_url=url)

    def fake_parse(body, url):
        return {"product_id": "A1", "name": "Widget", "sku": "A1"}

    rc = warmup.main(
        ["--sample", str(sample), "--config", str(cfg), "--authz", str(authz), "--out", str(out)],
        probe_fn=fake_probe, parse_fn=fake_parse)
    assert rc == 0
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["fetched"] == 1


def test_warmup_cli_blocked_by_gate_returns_2(tmp_path, capsys):
    # No authz file -> compliance gate fails closed.
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "target_domain": "example.com", "runtime": "local",
        "user_agent": "UA", "rate_limit_floor_seconds": 8}), encoding="utf-8")
    sample = tmp_path / "sample.json"
    sample.write_text(json.dumps(["https://example.com/p"]), encoding="utf-8")
    rc = warmup.main(
        ["--sample", str(sample), "--config", str(cfg),
         "--authz", str(tmp_path / "missing.json"), "--out", str(tmp_path / "r.json")],
        probe_fn=lambda u: None, parse_fn=lambda b, u: None)
    assert rc == 2
    assert "BLOCKED" in capsys.readouterr().err


def test_warmup_cli_missing_sample_returns_2(tmp_path):
    cfg, authz = _write_valid_gate_files(tmp_path)
    rc = warmup.main(
        ["--sample", str(tmp_path / "nope.json"), "--config", str(cfg),
         "--authz", str(authz), "--out", str(tmp_path / "r.json")],
        probe_fn=lambda u: None, parse_fn=lambda b, u: None)
    assert rc == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_warmup_cli.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'warmup'`.

- [ ] **Step 3: Write minimal implementation**

```python
# assets/scraper-template/warmup.py
"""Warm-up lap (spec §9.1): sample a site and detect render/auth/anti-bot/shape
before the full run. Compliance gate runs first (fail-closed). No product scraping
beyond the sample; the two-agent green-light review is the scrape-warmup skill's job."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from jemscrape.fetch import probe as http_probe
from jemscrape.recon import run_warmup, write_report
from scrape import preflight   # compliance gate (config + authz), fail-closed

HERE = Path(__file__).resolve().parent


def main(argv=None, *, probe_fn=None, parse_fn=None):
    parser = argparse.ArgumentParser(description="Warm-up lap (recon before full run)")
    parser.add_argument("--sample", required=True, help="JSON file: list of sample URLs")
    parser.add_argument("--config", default=str(HERE / "config.json"))
    parser.add_argument("--authz", default=str(HERE / ".scrape-authorization.json"))
    parser.add_argument("--out", default=str(HERE / ".scrape-warmup-report.json"))
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc)
    try:
        cfg, _auth = preflight(args.config, args.authz, now)
    except Exception as exc:   # compliance gate is fail-closed
        print(f"[warmup] BLOCKED by compliance gate: {exc}", file=sys.stderr)
        return 2

    try:
        urls = json.loads(Path(args.sample).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"[warmup] sample file not found or invalid: {exc}.", file=sys.stderr)
        return 2
    if not isinstance(urls, list) or not urls:
        print("[warmup] sample must be a non-empty JSON list of URLs.", file=sys.stderr)
        return 2

    if probe_fn is None:
        user_agent = cfg["user_agent"]

        def probe_fn(url):
            return http_probe(url, user_agent=user_agent)
    if parse_fn is None:
        from site_adapter import parse as parse_fn   # per-site, created in scaffold

    report = run_warmup(
        urls, probe_fn=probe_fn, parse_fn=parse_fn,
        source_site=cfg["target_domain"], scraped_at=now.isoformat(),
        authorization_ref=str(args.authz))
    write_report(report, args.out)

    print(f"[warmup] sampled={report.sampled} fetched={report.fetched} "
          f"spa={report.spa_count} auth={report.auth_count} antibot={report.antibot_count} "
          f"fetch_errors={report.fetch_errors}")
    for item in report.checklist:
        print(f"  - {item}")
    print(f"[warmup] report -> {args.out}")
    print("[warmup] next: 2-agent review (Opus 4.8 xhigh + Sonnet 5 advisor) decides "
          "VERDE/AJUSTAR/PEDIR AJUDA and writes .scrape-warmup.json (gate for the full run).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_warmup_cli.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/warmup.py assets/scraper-template/tests/test_warmup_cli.py
git commit -m "feat: warmup.py CLI — compliance gate + run_warmup + recon report

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: warm-up-verdict gate (fail-closed) + wire into `scrape.py`

**Files:**
- Modify: `assets/scraper-template/jemscrape/errors.py`
- Create: `assets/scraper-template/jemscrape/warmup_gate.py`
- Modify: `assets/scraper-template/scrape.py`
- Modify: `.gitignore`
- Test: `assets/scraper-template/tests/test_warmup_gate.py`

**Interfaces:**
- Produces:
  - `WarmupError(Exception)` in `errors.py`.
  - `WarmupVerdict` dataclass: `target_domain, verdict, generated_at, expires_at, report_sha256, reviewer, advisor`.
  - `load_warmup_verdict(path) -> WarmupVerdict` (raises `WarmupError`).
  - `validate_warmup(verdict, target_url, now)` — passes only when `verdict == "green"`, `expires_at` is future and tz-aware, and the target host matches `target_domain`; otherwise raises `WarmupError` (fail-closed). `report_sha256` binds the verdict to a specific recon report (traceability; loaded but not re-hashed here, like `authz.robots_override_ref`).
  - `require_warmup(warmup_path, target_url, now)` in `scrape.py` — composes load + validate; used by `main()` before the full run.
- Consumes: `atomic_write` not needed here; mirrors `authz.py` structure.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_warmup_gate.py
import json
from datetime import datetime, timezone, timedelta

import pytest

from jemscrape.warmup_gate import load_warmup_verdict, validate_warmup, WarmupVerdict
from jemscrape.errors import WarmupError

NOW = datetime(2026, 7, 2, 12, 0, tzinfo=timezone.utc)


def _verdict(verdict="green", domain="example.com", expires=None):
    return WarmupVerdict(
        target_domain=domain, verdict=verdict,
        generated_at=NOW.isoformat(),
        expires_at=(expires or (NOW + timedelta(days=1))).isoformat(),
        report_sha256="abc", reviewer="opus-4.8", advisor="sonnet-5")


def test_validate_warmup_green_passes():
    validate_warmup(_verdict(), "https://example.com/", NOW)   # no raise


def test_validate_warmup_not_green_blocks():
    with pytest.raises(WarmupError):
        validate_warmup(_verdict(verdict="adjust"), "https://example.com/", NOW)


def test_validate_warmup_expired_blocks():
    with pytest.raises(WarmupError):
        validate_warmup(_verdict(expires=NOW - timedelta(hours=1)), "https://example.com/", NOW)


def test_validate_warmup_domain_mismatch_blocks():
    with pytest.raises(WarmupError):
        validate_warmup(_verdict(domain="other.com"), "https://example.com/", NOW)


def test_validate_warmup_naive_expiry_blocks():
    v = _verdict()
    v.expires_at = "2026-07-03T12:00:00"   # no tz offset
    with pytest.raises(WarmupError):
        validate_warmup(v, "https://example.com/", NOW)


def test_load_warmup_verdict_missing_file_raises(tmp_path):
    with pytest.raises(WarmupError):
        load_warmup_verdict(tmp_path / "nope.json")


def test_load_warmup_verdict_roundtrip(tmp_path):
    p = tmp_path / ".scrape-warmup.json"
    p.write_text(json.dumps({
        "target_domain": "example.com", "verdict": "green",
        "generated_at": NOW.isoformat(), "expires_at": (NOW + timedelta(days=1)).isoformat(),
        "report_sha256": "abc", "reviewer": "opus-4.8", "advisor": "sonnet-5"}), encoding="utf-8")
    v = load_warmup_verdict(p)
    validate_warmup(v, "https://example.com/", NOW)   # no raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_warmup_gate.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'jemscrape.warmup_gate'`.

- [ ] **Step 3: Write minimal implementation**

Add to `assets/scraper-template/jemscrape/errors.py`:

```python
class WarmupError(Exception):
    """Raised when the warm-up verdict is missing, invalid, or not green — full run blocked."""
```

Create `assets/scraper-template/jemscrape/warmup_gate.py`:

```python
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from .errors import WarmupError

VALID_VERDICTS = {"green", "adjust", "ask"}


@dataclass
class WarmupVerdict:
    target_domain: str
    verdict: str
    generated_at: str
    expires_at: str
    report_sha256: str      # binds this verdict to a specific recon report (traceability)
    reviewer: str
    advisor: str


def load_warmup_verdict(path):
    p = Path(path)
    if not p.exists():
        raise WarmupError(f"no warm-up verdict at {p} — run the warm-up lap + green-light review first")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WarmupError(f"cannot read warm-up verdict at {p}: {exc}") from exc
    if not isinstance(data, dict):
        raise WarmupError(f"warm-up verdict at {p} must be a JSON object")
    try:
        return WarmupVerdict(**{k: data.get(k) for k in WarmupVerdict.__annotations__})
    except TypeError as exc:
        raise WarmupError(f"malformed warm-up verdict: {exc}") from exc


def _parse_dt(value):
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise WarmupError(f"expires_at: not an ISO-8601 datetime ({value!r})") from exc


def validate_warmup(verdict, target_url, now):
    if verdict.verdict not in VALID_VERDICTS:
        raise WarmupError(f"verdict invalid: {verdict.verdict!r}")
    if verdict.verdict != "green":
        raise WarmupError(f"warm-up verdict is {verdict.verdict!r}, not green — full run blocked")
    host = urlsplit(target_url).hostname or ""
    if host != verdict.target_domain:
        raise WarmupError(
            f"target host {host!r} does not match warm-up domain {verdict.target_domain!r}")
    expires = _parse_dt(verdict.expires_at)
    if expires.tzinfo is None:
        raise WarmupError("expires_at must include a timezone offset")
    try:
        expired = now >= expires
    except TypeError as exc:
        raise WarmupError(f"cannot compare expiry ({exc})") from exc
    if expired:
        raise WarmupError(f"warm-up verdict expired at {verdict.expires_at}")
```

Modify `assets/scraper-template/scrape.py`:

1. Add imports near the top (with the other `from jemscrape...` imports):

```python
from jemscrape.warmup_gate import load_warmup_verdict, validate_warmup
```

2. Add the constant near `AUTHZ_PATH`:

```python
WARMUP_PATH = HERE / ".scrape-warmup.json"
```

3. Add the helper (below `preflight`):

```python
def require_warmup(warmup_path, target_url, now):
    """Fail-closed: raises WarmupError unless a green, unexpired, matching verdict exists."""
    verdict = load_warmup_verdict(warmup_path)
    validate_warmup(verdict, target_url, now)
```

4. In `main()`, right after the `preflight` gate succeeds and before `from site_adapter import discover, parse`, add:

```python
    try:
        target_url = f"https://{cfg['target_domain']}/"
        require_warmup(WARMUP_PATH, target_url, datetime.now(timezone.utc))
    except Exception as exc:   # fail-closed: no full run without a green warm-up verdict
        print(f"[gate] BLOCKED: warm-up not green — {exc}", file=sys.stderr)
        return 2
```

- [ ] **Step 2b: Add a test for the `scrape.require_warmup` seam**

```python
# add to tests/test_warmup_gate.py
import scrape


def test_scrape_require_warmup_missing_blocks(tmp_path):
    with pytest.raises(WarmupError):
        scrape.require_warmup(tmp_path / ".scrape-warmup.json", "https://example.com/", NOW)


def test_scrape_require_warmup_green_passes(tmp_path):
    p = tmp_path / ".scrape-warmup.json"
    p.write_text(json.dumps({
        "target_domain": "example.com", "verdict": "green",
        "generated_at": NOW.isoformat(), "expires_at": (NOW + timedelta(days=1)).isoformat(),
        "report_sha256": "abc", "reviewer": "opus-4.8", "advisor": "sonnet-5"}), encoding="utf-8")
    scrape.require_warmup(p, "https://example.com/", NOW)   # no raise
```

- [ ] **Step 3b: Update `.gitignore`**

Add under the secrets section (near `.scrape-authorization.json`):

```
.scrape-warmup.json
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_warmup_gate.py -q`
Expected: PASS (9 passed).

Then the full suite:

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (all previous + new).

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/errors.py assets/scraper-template/jemscrape/warmup_gate.py assets/scraper-template/scrape.py assets/scraper-template/tests/test_warmup_gate.py .gitignore
git commit -m "feat: warm-up-verdict gate — scrape.py refuses full run without green verdict

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage (§9.1):**
- "amostra 10–50 produtos ... caminho HTTP padrão" → Task 1 (`probe`) + Task 6 (`run_warmup` over injected sample). ✓
- Signal 1 render (server vs SPA) → Task 2. ✓
- Signal 2 auth/paywall → Task 3. ✓
- Signal 3 anti-bot/geo → Task 4. ✓
- Signal 4 shape de parse (normalize/dedup, cobertura) → Task 5. ✓
- Relatório de recon → Task 6 (`WarmupReport` + `write_report`). ✓
- Checklist de preparo do operador → Task 6 (`build_checklist`). ✓
- Gate fail-closed "runtime recusa run full sem verde" → Task 8 (`warmup_gate` + `scrape.require_warmup`). ✓
- Review de 2 agentes (Opus 4.8 xhigh + Sonnet 5) → explicitly OUT OF SCOPE (skill `scrape-warmup`); the plan builds the verdict artifact it writes + the enforcing gate. Noted in Global Constraints. ✓
- Sample discovery (sitemap/categoria) → injected (DI), deferred to Plano 3. Noted. ✓

**2. Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N". Every code step shows complete code. ✓

**3. Type consistency:**
- `Probe(status, headers, body, final_url)` defined in Task 1; consumed identically in Tasks 3, 4, 6. ✓
- `detect_render`/`detect_auth`/`detect_antibot`/`analyze_shape` signatures defined in Tasks 2–5; called with the same shapes in Task 6. ✓
- `run_warmup(...)` / `WarmupReport` fields defined in Task 6; consumed by the CLI in Task 7 (`report.sampled`, `.fetched`, `.spa_count`, etc.). ✓
- `WarmupVerdict` fields (Task 8) match the JSON the CLI/skill writes and the gate reads. ✓
- `preflight(config_path, authz_path, now)` reused from `scrape.py` (existing signature) in Task 7. ✓

Note for the implementer: Task 6's `recon.py` uses `from dataclasses import dataclass, asdict` — do NOT import `field` (it is unused; an unused import is a lint failure this codebase has explicitly fixed before).
