# Browser Render Adapter Implementation Plan (Plano 3a)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Playwright-based browser render adapter (spec §5.2) so the scraper and warm-up can process public SPA/JS sites (whose static HTML is empty), keeping the stdlib core and its TDD suite untouched by wrapping Playwright behind an injectable `render_fn`.

**Architecture:** Pure adapter factories in `jemscrape/browser.py` (stdlib, TDD) convert a `render_fn(url) -> RenderedResult` into the engine's existing contracts — the runner's `fetcher(url) -> html` and the warm-up's `probe_fn(url) -> Probe`. The only module that imports Playwright is `drivers/playwright_render.py` (guarded, kept out of the stdlib test suite). `config.json` gains `fetch_mode: "http" | "browser"`; `scrape.py` and `warmup.py` select the fetcher/probe accordingly, importing the driver lazily. Auth/token (Plano 3b, spec §5.1) is deferred.

**Tech Stack:** Python 3 stdlib for the core; Playwright (Chromium) as a NEW **optional** dependency confined to `drivers/`. Tests via `pytest` (`.venv/bin/python -m pytest`).

## Global Constraints

- **The stdlib core stays stdlib-only.** No third-party imports anywhere under `jemscrape/` or in `scrape.py`/`warmup.py`/`build_dataset.py`. Playwright is imported ONLY in `assets/scraper-template/drivers/playwright_render.py`, behind a guarded `try/except ImportError`.
- **Dependency injection.** The browser adapter takes `render_fn` as an argument; unit tests inject a fake `render_fn` and NEVER launch a real browser.
- **`fetch_mode` defaults to `"http"`.** Browser mode is opt-in via config `fetch_mode: "browser"` or the `warmup.py --render browser` flag. Existing HTTP behavior is unchanged when unset.
- **Driver is outside the stdlib suite.** `drivers/playwright_render.py`'s guard behavior IS unit-tested (raises an actionable error when Playwright is absent); the real browser render is a `pytest.importorskip("playwright")` smoke that skips where Playwright/Chromium aren't installed (they aren't in this repo's venv — the suite stays green).
- **Reuse existing contracts:** `Probe(status, headers, body, final_url)` from `jemscrape.fetch`; `FetchError` from `jemscrape.errors` (the runner catches broadly, `run_warmup` counts `FetchError` as `fetch_errors`); the runner's `fetcher(url) -> html` and `run_warmup`'s `probe_fn(url) -> Probe`.
- **Deferred (Plano 3b, spec §5.1):** session capture, token lifecycle, `gh secret`, daily refresh, VM promotion. Not in this plan.
- **Tests:** `.venv/bin/python -m pytest -q`. Baseline 134 passing; keep green + pristine.
- **Commits** end with the trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

## File Structure

- `assets/scraper-template/jemscrape/browser.py` — CREATE: `RenderedResult` dataclass, `make_browser_fetcher(render_fn)`, `make_browser_probe(render_fn)`. Stdlib only.
- `assets/scraper-template/drivers/__init__.py` — CREATE: empty (makes `drivers` an importable package on the template pythonpath).
- `assets/scraper-template/drivers/playwright_render.py` — CREATE: guarded `render(url, *, timeout=30000, proxy=None) -> RenderedResult`. The only Playwright import.
- `assets/scraper-template/jemscrape/config.py` — MODIFY: validate optional `fetch_mode`.
- `assets/scraper-template/warmup.py` — MODIFY: `--render` flag + `render_fn` injection + browser-probe selection.
- `assets/scraper-template/scrape.py` — MODIFY: `build_fetcher(cfg, *, http_fetch, render_fn=None)` helper + wire into `main()`.
- Tests: `tests/test_browser.py`, `tests/test_playwright_render.py`, `tests/test_config_fetch_mode.py`, additions to `tests/test_warmup_cli.py`, `tests/test_build_fetcher.py`.

---

### Task 1: `jemscrape/browser.py` — pure render adapters

**Files:**
- Create: `assets/scraper-template/jemscrape/browser.py`
- Test: `assets/scraper-template/tests/test_browser.py`

**Interfaces:**
- Consumes: `Probe` from `jemscrape.fetch` (fields `status, headers, body, final_url`); `FetchError` from `jemscrape.errors`.
- Produces:
  - `RenderedResult` dataclass: `status: int`, `html: str`, `final_url: str`.
  - `make_browser_fetcher(render_fn) -> fetcher` where `fetcher(url) -> str` (rendered html), matching the runner's fetcher contract. `render_fn(url) -> RenderedResult`. A render failure is wrapped in `FetchError`.
  - `make_browser_probe(render_fn) -> probe_fn` where `probe_fn(url) -> Probe` (with `headers={}`, `body=html`), matching `run_warmup`'s probe_fn contract. A render failure is wrapped in `FetchError`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_browser.py
import pytest

from jemscrape.browser import RenderedResult, make_browser_fetcher, make_browser_probe
from jemscrape.fetch import Probe
from jemscrape.errors import FetchError


def test_make_browser_fetcher_returns_rendered_html():
    def fake_render(url):
        return RenderedResult(status=200, html="<h1>Rendered</h1>", final_url=url)
    fetcher = make_browser_fetcher(fake_render)
    assert fetcher("https://x/p") == "<h1>Rendered</h1>"


def test_make_browser_fetcher_wraps_failure_in_fetcherror():
    def boom(url):
        raise RuntimeError("browser crashed")
    fetcher = make_browser_fetcher(boom)
    with pytest.raises(FetchError):
        fetcher("https://x/p")


def test_make_browser_probe_builds_probe_from_rendered_result():
    def fake_render(url):
        return RenderedResult(status=200, html="<html>ok</html>", final_url="https://x/final")
    probe_fn = make_browser_probe(fake_render)
    p = probe_fn("https://x/p")
    assert isinstance(p, Probe)
    assert p.status == 200
    assert p.body == "<html>ok</html>"
    assert p.final_url == "https://x/final"
    assert p.headers == {}


def test_make_browser_probe_wraps_failure_in_fetcherror():
    def boom(url):
        raise TimeoutError("nav timeout")
    probe_fn = make_browser_probe(boom)
    with pytest.raises(FetchError):
        probe_fn("https://x/p")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_browser.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'jemscrape.browser'`.

- [ ] **Step 3: Write minimal implementation**

```python
# assets/scraper-template/jemscrape/browser.py
"""Pure browser-render adapters (spec §5.2). Convert a render_fn(url) ->
RenderedResult into the engine's existing fetcher/probe contracts. Stdlib only —
the actual Playwright driver lives in drivers/playwright_render.py."""
from dataclasses import dataclass

from .fetch import Probe
from .errors import FetchError


@dataclass
class RenderedResult:
    status: int
    html: str
    final_url: str


def make_browser_fetcher(render_fn):
    """Return fetcher(url) -> html backed by render_fn(url) -> RenderedResult."""
    def fetcher(url):
        try:
            result = render_fn(url)
        except Exception as exc:
            raise FetchError(f"browser render failed for {url}: {exc}") from exc
        return result.html
    return fetcher


def make_browser_probe(render_fn):
    """Return probe_fn(url) -> Probe backed by render_fn(url) -> RenderedResult."""
    def probe_fn(url):
        try:
            result = render_fn(url)
        except Exception as exc:
            raise FetchError(f"browser render failed for {url}: {exc}") from exc
        return Probe(status=result.status, headers={}, body=result.html,
                     final_url=result.final_url)
    return probe_fn
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_browser.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/browser.py assets/scraper-template/tests/test_browser.py
git commit -m "feat: browser.py — pure render adapters (fetcher/probe from render_fn)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `drivers/playwright_render.py` — guarded Playwright driver

**Files:**
- Create: `assets/scraper-template/drivers/__init__.py` (empty)
- Create: `assets/scraper-template/drivers/playwright_render.py`
- Test: `assets/scraper-template/tests/test_playwright_render.py`

**Interfaces:**
- Consumes: `RenderedResult` from `jemscrape.browser` (Task 1).
- Produces: `render(url, *, timeout=30000, proxy=None) -> RenderedResult`. `timeout` is milliseconds; `proxy` is a Playwright proxy dict (e.g. `{"server": "http://host:port"}`) or `None`. Raises `RuntimeError` with an actionable install hint when Playwright is unavailable. Module-level `_AVAILABLE: bool` reflects whether the Playwright import succeeded.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_playwright_render.py
import pytest

import drivers.playwright_render as pr
from jemscrape.browser import RenderedResult


def test_render_raises_actionable_error_when_playwright_absent(monkeypatch):
    # Fail closed with a helpful message, never a bare ImportError/NameError.
    monkeypatch.setattr(pr, "_AVAILABLE", False)
    with pytest.raises(RuntimeError) as exc:
        pr.render("https://example.com/")
    assert "playwright install chromium" in str(exc.value)


def test_render_smoke_renders_inline_html():
    # Integration: only runs where Playwright + Chromium are actually installed.
    pytest.importorskip("playwright")
    try:
        result = pr.render("data:text/html,<h1>Hello Warmup</h1>", timeout=15000)
    except Exception as exc:  # playwright present but browser binary/launch unavailable
        pytest.skip(f"browser render unavailable: {exc}")
    assert isinstance(result, RenderedResult)
    assert "Hello Warmup" in result.html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_playwright_render.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'drivers'` (or `drivers.playwright_render`).

- [ ] **Step 3: Write minimal implementation**

Create empty `assets/scraper-template/drivers/__init__.py`:

```python
```

Create `assets/scraper-template/drivers/playwright_render.py`:

```python
"""Playwright render driver (spec §5.2, Plano 3a). The ONLY module that imports
Playwright — kept out of the stdlib jemscrape/ core and out of the stdlib test
suite. Guarded so its absence produces an actionable error, not an ImportError."""
from jemscrape.browser import RenderedResult

try:
    from playwright.sync_api import sync_playwright
    _AVAILABLE = True
except ImportError:
    sync_playwright = None
    _AVAILABLE = False

_INSTALL_HINT = (
    "Playwright is not installed — required for the browser render path "
    "(fetch_mode=browser / --render browser). Ask IT to install it: "
    "pip install playwright && playwright install chromium"
)


def render(url, *, timeout=30000, proxy=None):
    """Render url in headless Chromium; return RenderedResult(status, html, final_url).
    timeout is in milliseconds. proxy is a Playwright proxy dict or None."""
    if not _AVAILABLE:
        raise RuntimeError(_INSTALL_HINT)
    launch_kwargs = {}
    if proxy:
        launch_kwargs["proxy"] = proxy
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, **launch_kwargs)
        try:
            page = browser.new_page()
            response = page.goto(url, wait_until="networkidle", timeout=timeout)
            status = response.status if response is not None else 0
            html = page.content()
            final_url = page.url
        finally:
            browser.close()
    return RenderedResult(status=status, html=html, final_url=final_url)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_playwright_render.py -q`
Expected: PASS — the guard test passes; the smoke test is skipped where Playwright is absent (`1 passed, 1 skipped`).

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/drivers/__init__.py assets/scraper-template/drivers/playwright_render.py assets/scraper-template/tests/test_playwright_render.py
git commit -m "feat: playwright_render driver — guarded Chromium render (opt dep)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `config.py` — validate optional `fetch_mode`

**Files:**
- Modify: `assets/scraper-template/jemscrape/config.py`
- Test: `assets/scraper-template/tests/test_config_fetch_mode.py`

**Interfaces:**
- Consumes: existing `validate_config(cfg)` (raises `ConfigError` on invalid config) and `ConfigError`.
- Produces: `validate_config` additionally rejects `fetch_mode` when present and not in `{"http", "browser"}`. Absent `fetch_mode` is valid (defaults to HTTP behavior).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config_fetch_mode.py
import pytest

from jemscrape.config import validate_config
from jemscrape.errors import ConfigError


def _base():
    return {"target_domain": "x.com", "runtime": "local",
            "user_agent": "UA", "rate_limit_floor_seconds": 5}


def test_fetch_mode_browser_ok():
    cfg = _base(); cfg["fetch_mode"] = "browser"
    validate_config(cfg)   # no raise


def test_fetch_mode_http_ok():
    cfg = _base(); cfg["fetch_mode"] = "http"
    validate_config(cfg)   # no raise


def test_fetch_mode_absent_ok():
    validate_config(_base())   # no raise


def test_fetch_mode_invalid_raises():
    cfg = _base(); cfg["fetch_mode"] = "spa"
    with pytest.raises(ConfigError):
        validate_config(cfg)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_config_fetch_mode.py -q`
Expected: FAIL on `test_fetch_mode_invalid_raises` (no `ConfigError` raised — `fetch_mode` isn't validated yet).

- [ ] **Step 3: Write minimal implementation**

In `assets/scraper-template/jemscrape/config.py`, inside `validate_config`, add this check alongside the other field checks (e.g. right after the `runtime` check), using the existing `errors` list:

```python
    fetch_mode = cfg.get("fetch_mode")
    if fetch_mode is not None and fetch_mode not in ("http", "browser"):
        errors.append('fetch_mode: must be "http" or "browser" if set')
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_config_fetch_mode.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/config.py assets/scraper-template/tests/test_config_fetch_mode.py
git commit -m "feat: config validates optional fetch_mode (http|browser)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `warmup.py` — `--render` flag + browser probe selection

**Files:**
- Modify: `assets/scraper-template/warmup.py`
- Test: `assets/scraper-template/tests/test_warmup_cli.py` (append)

**Interfaces:**
- Consumes: `make_browser_probe` (Task 1); `render` from `drivers.playwright_render` (Task 2, imported lazily); existing `run_warmup`/`write_report`, `preflight`, `http_probe`.
- Produces: `main(argv=None, *, probe_fn=None, parse_fn=None, render_fn=None) -> int`. New `--render {http,browser}` arg (default `None`). Effective mode = `args.render or cfg.get("fetch_mode", "http")`. When `probe_fn is None` and mode is `"browser"`, the probe is `make_browser_probe(render_fn or <lazy driver render>)`; otherwise the existing HTTP probe. `render_fn` is injectable for tests (never launches a real browser).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_warmup_cli.py
from jemscrape.browser import RenderedResult


def test_warmup_cli_browser_mode_uses_render_fn(tmp_path):
    cfg, authz = _write_valid_gate_files(tmp_path)
    sample = tmp_path / "sample.json"
    sample.write_text(json.dumps(["https://example.com/product/1"]), encoding="utf-8")
    out = tmp_path / "r.json"
    rendered = "<html><body><h1>Widget</h1>" + ("<p>d </p>" * 40) + "</body></html>"

    def fake_render(url):
        return RenderedResult(status=200, html=rendered, final_url=url)

    def fake_parse(body, url):
        assert "Widget" in body      # proves the browser-rendered html reached parse
        return {"product_id": "A1", "name": "Widget", "sku": "A1"}

    rc = warmup.main(
        ["--sample", str(sample), "--config", str(cfg), "--authz", str(authz),
         "--out", str(out), "--render", "browser"],
        render_fn=fake_render, parse_fn=fake_parse)

    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["fetched"] == 1
    assert data["shape"]["count"] == 1
```

(This test reuses the module-level `import warmup`, `import json`, and the `_write_valid_gate_files` helper already present in `test_warmup_cli.py` from Plano 4.)

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_warmup_cli.py::test_warmup_cli_browser_mode_uses_render_fn -q`
Expected: FAIL with `TypeError: main() got an unexpected keyword argument 'render_fn'`.

- [ ] **Step 3: Write minimal implementation**

In `assets/scraper-template/warmup.py`:

Change the signature:

```python
def main(argv=None, *, probe_fn=None, parse_fn=None, render_fn=None):
```

Add the `--render` argument alongside the others:

```python
    parser.add_argument("--render", choices=["http", "browser"], default=None,
                        help="fetch mode override (default: config fetch_mode or http)")
```

Replace the existing `if probe_fn is None:` block with mode-aware selection:

```python
    if probe_fn is None:
        mode = args.render or cfg.get("fetch_mode", "http")
        if mode == "browser":
            from jemscrape.browser import make_browser_probe
            if render_fn is None:
                from drivers.playwright_render import render as render_fn
            probe_fn = make_browser_probe(render_fn)
        else:
            user_agent = cfg["user_agent"]

            def probe_fn(url):
                return http_probe(url, user_agent=user_agent)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_warmup_cli.py -q`
Expected: PASS (all existing warmup CLI tests + the new browser-mode test).

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/warmup.py assets/scraper-template/tests/test_warmup_cli.py
git commit -m "feat: warmup.py --render browser — probe via render adapter

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: `scrape.py` — `build_fetcher` (fetch_mode → browser/http)

**Files:**
- Modify: `assets/scraper-template/scrape.py`
- Test: `assets/scraper-template/tests/test_build_fetcher.py`

**Interfaces:**
- Consumes: `make_browser_fetcher` (Task 1); `render` from `drivers.playwright_render` (Task 2, lazy); existing `fetch as http_fetch`.
- Produces: `build_fetcher(cfg, *, http_fetch, render_fn=None) -> fetcher` where `fetcher(url) -> html`. Browser mode (`cfg["fetch_mode"] == "browser"`) returns `make_browser_fetcher(render_fn or <lazy driver render>)`; otherwise a closure calling `http_fetch(url, user_agent=cfg["user_agent"])`. Wired into `main()` in place of the inline HTTP fetcher.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_build_fetcher.py
import scrape
from jemscrape.browser import RenderedResult


def test_build_fetcher_http_mode_uses_http_fetch():
    calls = {}

    def fake_http(url, *, user_agent):
        calls["ua"] = user_agent
        return "<h1>http</h1>"

    fetcher = scrape.build_fetcher({"user_agent": "UA"}, http_fetch=fake_http)
    assert fetcher("https://x/p") == "<h1>http</h1>"
    assert calls["ua"] == "UA"


def test_build_fetcher_browser_mode_uses_render_fn():
    def fake_render(url):
        return RenderedResult(status=200, html="<h1>rendered</h1>", final_url=url)

    def unused_http(url, *, user_agent):
        raise AssertionError("http_fetch must not be called in browser mode")

    fetcher = scrape.build_fetcher(
        {"user_agent": "UA", "fetch_mode": "browser"},
        http_fetch=unused_http, render_fn=fake_render)
    assert fetcher("https://x/p") == "<h1>rendered</h1>"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_build_fetcher.py -q`
Expected: FAIL with `AttributeError: module 'scrape' has no attribute 'build_fetcher'`.

- [ ] **Step 3: Write minimal implementation**

In `assets/scraper-template/scrape.py`, add the helper (below `require_warmup`):

```python
def build_fetcher(cfg, *, http_fetch, render_fn=None):
    """Select the run fetcher by fetch_mode. Browser mode wraps a render_fn
    (Playwright) into the runner's fetcher(url)->html contract; default is HTTP."""
    if cfg.get("fetch_mode") == "browser":
        from jemscrape.browser import make_browser_fetcher
        if render_fn is None:
            from drivers.playwright_render import render as render_fn
        return make_browser_fetcher(render_fn)
    user_agent = cfg["user_agent"]
    return lambda url: http_fetch(url, user_agent=user_agent)
```

Then in `main()`, replace the inline fetcher definition:

```python
    def fetcher(url):
        return http_fetch(url, user_agent=cfg["user_agent"])
```

with:

```python
    fetcher = build_fetcher(cfg, http_fetch=http_fetch)
```

(`http_fetch` is already imported inside `main()` as `from jemscrape.fetch import fetch as http_fetch`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_build_fetcher.py -q`
Expected: PASS (2 passed).

Then the full suite:

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (all previous + new; the Playwright smoke skipped).

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/scrape.py assets/scraper-template/tests/test_build_fetcher.py
git commit -m "feat: scrape.build_fetcher — browser render fetcher when fetch_mode=browser

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage (§5.2):**
- Render adapter converting a browser result into engine contracts → Task 1 (`make_browser_fetcher`/`make_browser_probe`). ✓
- `jemscrape/browser.py` stdlib, TDD with fake render_fn → Task 1. ✓
- `drivers/playwright_render.py` sole Playwright import, guarded, out of stdlib suite → Task 2 (guard unit-tested; real render skip-if-absent). ✓
- `config.json` `fetch_mode: "http" | "browser"` → Task 3. ✓
- `scrape.py` + `warmup.py` select fetcher/probe, lazy driver import, core unchanged → Tasks 4 & 5. ✓
- Closes the warm-up "needs browser" loop (`warmup.py --render browser`) → Task 4. ✓
- Playwright = optional declared dep, not in the zero-dep core → Global Constraints + Task 2 guard. ✓
- Deferred 3b (auth/token) → explicitly out of scope. ✓

**2. Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N". Every code step is complete. ✓

**3. Type consistency:**
- `RenderedResult(status, html, final_url)` defined in Task 1; produced by `render` in Task 2; consumed by the factories in Task 1 and by tests in Tasks 4/5. ✓
- `make_browser_fetcher`/`make_browser_probe` defined in Task 1; consumed by Task 4 (`make_browser_probe`) and Task 5 (`make_browser_fetcher`). ✓
- `render(url, *, timeout=30000, proxy=None)` defined in Task 2; imported lazily in Tasks 4 & 5. ✓
- `Probe(status, headers, body, final_url)` reused from `jemscrape.fetch` (unchanged). ✓
- `build_fetcher(cfg, *, http_fetch, render_fn=None)` (Task 5) and `main(..., render_fn=None)` (Task 4) both expose `render_fn` injection with identical semantics. ✓

Note for the implementer: `drivers/` must be a package on the template pythonpath (`pyproject.toml` sets `pythonpath = ["assets/scraper-template"]`), hence the empty `drivers/__init__.py` in Task 2 — without it `from drivers.playwright_render import render` may not resolve on all setups.
