# GitHub Actions Runtime Implementation Plan (Plano 5)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the unattended GitHub Actions runtime (spec §5.3): a workflow template that runs the deterministic scrape pipeline on a schedule with the compliance gate enforced in-runtime, reconstructing the gitignored gate files from Actions secrets (fail-closed), checkpointing to the repo, and uploading exports as an artifact.

**Architecture:** The security-critical seam is stdlib + TDD: `jemscrape/secrets_io.py` materializes a secret env var into a file fail-closed; `actions_setup.py` uses it to reconstruct `.scrape-authorization.json` + `.scrape-warmup.json` from secrets before any fetch; `notify.py` emits GitHub annotations on failure. The workflow itself is a YAML **template** under `assets/github-actions/` (never an active workflow in this repo) validated by a text-assertion test that pins the step order (materialize → gate → scrape) and the fail-closed guards.

**Tech Stack:** Python 3 stdlib only. Tests via `pytest` (`.venv/bin/python -m pytest`). The workflow YAML is a template asset (not executed by tests).

## Global Constraints

- **Python 3 stdlib-only** — no third-party imports anywhere in `jemscrape/`, `actions_setup.py`, `notify.py`.
- **Secrets never committed.** `.scrape-authorization.json` and `.scrape-warmup.json` are gitignored; in Actions they are reconstructed from secrets (`SCRAPE_AUTHORIZATION`, `SCRAPE_WARMUP`) at runtime, written with restrictive perms (0600).
- **Fail-closed.** A missing/blank required secret aborts with a non-zero exit BEFORE any scrape step. The compliance gate (`smoke_test.py`) runs after materialization and before `scrape.py`.
- **The workflow is a TEMPLATE.** It lives under `assets/github-actions/scrape.yml` (scaffolded into a generated project's `.github/workflows/`), so it never triggers in this plugin repo. Tests assert on its text, never execute it.
- **Deterministic now, Batch later.** The v1 pipeline is deterministic; the Actions run needs no Anthropic API. The Batch/API normalize step (§11) is a documented future hook (optional `ANTHROPIC_API_KEY` secret), not built here.
- **Out of scope (Plano 6):** automated deploy (`gh secret set`, pushing the workflow via the GitHub API). This plan ships the template + testable helpers + the runtime gate.
- **Reuse:** `ConfigError` from `jemscrape.errors`; existing `smoke_test.py`/`scrape.py`/`build_dataset.py` are invoked by the workflow, unchanged.
- **Tests:** `.venv/bin/python -m pytest -q`. Baseline 147 passed, 1 skipped; keep green + pristine.
- **Commits** end with the trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

## File Structure

- `assets/scraper-template/jemscrape/secrets_io.py` — CREATE: `materialize_secret(name, path, *, env, mode=0o600)`.
- `assets/scraper-template/actions_setup.py` — CREATE: CLI that materializes both gate files from secrets, fail-closed.
- `assets/scraper-template/notify.py` — CREATE: `format_notification` / `emit` / `main` (GitHub annotations).
- `assets/github-actions/scrape.yml` — CREATE: workflow template.
- Tests: `tests/test_secrets_io.py`, `tests/test_actions_setup.py`, `tests/test_notify.py`, `tests/test_actions_workflow.py`.

---

### Task 1: `jemscrape/secrets_io.py` — materialize a secret to a file (fail-closed)

**Files:**
- Create: `assets/scraper-template/jemscrape/secrets_io.py`
- Test: `assets/scraper-template/tests/test_secrets_io.py`

**Interfaces:**
- Consumes: `ConfigError` from `jemscrape.errors`.
- Produces: `materialize_secret(name, path, *, env, mode=0o600) -> Path`. Reads `env[name]`; raises `ConfigError` if missing or blank; writes the value to `path` (creating parent dirs) with perms `mode`; returns the `Path`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_secrets_io.py
import stat

import pytest

from jemscrape.secrets_io import materialize_secret
from jemscrape.errors import ConfigError


def test_materialize_secret_writes_value_and_returns_path(tmp_path):
    dest = tmp_path / "sub" / ".scrape-authorization.json"
    out = materialize_secret("SEC", dest, env={"SEC": '{"target_domain":"x.com"}'})
    assert out == dest
    assert dest.read_text(encoding="utf-8") == '{"target_domain":"x.com"}'


def test_materialize_secret_sets_restrictive_perms(tmp_path):
    dest = tmp_path / "s.json"
    materialize_secret("SEC", dest, env={"SEC": "data"})
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600


def test_materialize_secret_missing_raises(tmp_path):
    with pytest.raises(ConfigError):
        materialize_secret("SEC", tmp_path / "s.json", env={})


def test_materialize_secret_blank_raises(tmp_path):
    with pytest.raises(ConfigError):
        materialize_secret("SEC", tmp_path / "s.json", env={"SEC": "   "})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_secrets_io.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'jemscrape.secrets_io'`.

- [ ] **Step 3: Write minimal implementation**

```python
# assets/scraper-template/jemscrape/secrets_io.py
"""Reconstruct a gitignored secret file from an env var (Actions secret),
fail-closed. Used by actions_setup.py so gate files never live in the repo."""
import os
from pathlib import Path

from .errors import ConfigError


def materialize_secret(name, path, *, env, mode=0o600):
    value = env.get(name)
    if not value or not value.strip():
        raise ConfigError(f"missing required secret env var: {name}")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    # Create with restrictive perms FROM CREATION — no world-readable window.
    # (0o600 has no group/other bits, so umask cannot loosen it.) The chmod
    # after covers a pre-existing file, and its failure is surfaced, not swallowed.
    fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(value)
    os.chmod(p, mode)
    return p
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_secrets_io.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/secrets_io.py assets/scraper-template/tests/test_secrets_io.py
git commit -m "feat: secrets_io.materialize_secret — reconstruct gate file from env (fail-closed)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `actions_setup.py` — materialize both gate files (fail-closed CLI)

**Files:**
- Create: `assets/scraper-template/actions_setup.py`
- Test: `assets/scraper-template/tests/test_actions_setup.py`

**Interfaces:**
- Consumes: `materialize_secret` (Task 1); `ConfigError` from `jemscrape.errors`.
- Produces: `main(argv=None, *, env=None, targets=None) -> int`. Materializes each `(secret_name, path)` in `targets` (default: `SCRAPE_AUTHORIZATION` → `.scrape-authorization.json`, `SCRAPE_WARMUP` → `.scrape-warmup.json`, relative to the script dir). On any missing secret, prints `[actions-setup] BLOCKED: ...` to stderr and returns `2` (before writing an incomplete set is acceptable; the gate re-checks). On success prints what it wrote and returns `0`. `env`/`targets` are injectable for tests.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_actions_setup.py
import json

import actions_setup


def test_actions_setup_materializes_both_gate_files(tmp_path):
    a = tmp_path / ".scrape-authorization.json"
    w = tmp_path / ".scrape-warmup.json"
    env = {"SCRAPE_AUTHORIZATION": json.dumps({"target_domain": "x.com"}),
           "SCRAPE_WARMUP": json.dumps({"verdict": "green"})}
    rc = actions_setup.main(env=env, targets=[("SCRAPE_AUTHORIZATION", a), ("SCRAPE_WARMUP", w)])
    assert rc == 0
    assert json.loads(a.read_text(encoding="utf-8"))["target_domain"] == "x.com"
    assert json.loads(w.read_text(encoding="utf-8"))["verdict"] == "green"


def test_actions_setup_missing_secret_returns_2(tmp_path, capsys):
    a = tmp_path / ".scrape-authorization.json"
    w = tmp_path / ".scrape-warmup.json"
    rc = actions_setup.main(env={"SCRAPE_AUTHORIZATION": "{}"},  # SCRAPE_WARMUP missing
                            targets=[("SCRAPE_AUTHORIZATION", a), ("SCRAPE_WARMUP", w)])
    assert rc == 2
    assert "BLOCKED" in capsys.readouterr().err
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_actions_setup.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'actions_setup'`.

- [ ] **Step 3: Write minimal implementation**

```python
# assets/scraper-template/actions_setup.py
"""Reconstruct the gitignored gate files from Actions secrets before a run.
Fail-closed: a missing secret aborts (exit 2) before any scrape step."""
import os
import sys
from pathlib import Path

from jemscrape.secrets_io import materialize_secret
from jemscrape.errors import ConfigError

HERE = Path(__file__).resolve().parent

_SECRET_FILES = [
    ("SCRAPE_AUTHORIZATION", HERE / ".scrape-authorization.json"),
    ("SCRAPE_WARMUP", HERE / ".scrape-warmup.json"),
]


def main(argv=None, *, env=None, targets=None):
    env = os.environ if env is None else env
    targets = _SECRET_FILES if targets is None else targets
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


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_actions_setup.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/actions_setup.py assets/scraper-template/tests/test_actions_setup.py
git commit -m "feat: actions_setup — materialize gate files from secrets (fail-closed)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `notify.py` — GitHub Actions failure annotation

**Files:**
- Create: `assets/scraper-template/notify.py`
- Test: `assets/scraper-template/tests/test_notify.py`

**Interfaces:**
- Produces:
  - `format_notification(kind, message) -> str` — returns a GitHub annotation line: `"::error::[scrape] {message}"` for `kind="error"`, `"::warning::..."` for `"warning"`, `"::notice::..."` for `"notice"` or any unknown kind.
  - `emit(kind, message, *, stream=None) -> None` — prints the formatted line to `stream` (default `sys.stdout`).
  - `main(argv=None) -> int` — CLI: `--kind {error,warning,notice}` (default error), `--message` (required); emits and returns 0.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_notify.py
import notify


def test_format_notification_error():
    assert notify.format_notification("error", "boom") == "::error::[scrape] boom"


def test_format_notification_warning():
    assert notify.format_notification("warning", "slow") == "::warning::[scrape] slow"


def test_format_notification_unknown_kind_defaults_to_notice():
    assert notify.format_notification("bogus", "hi") == "::notice::[scrape] hi"


def test_emit_writes_to_stream(capsys):
    notify.emit("error", "down")
    assert "::error::[scrape] down" in capsys.readouterr().out


def test_main_returns_zero_and_emits(capsys):
    rc = notify.main(["--kind", "warning", "--message", "heads up"])
    assert rc == 0
    assert "::warning::[scrape] heads up" in capsys.readouterr().out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_notify.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'notify'`.

- [ ] **Step 3: Write minimal implementation**

```python
# assets/scraper-template/notify.py
"""Emit a GitHub Actions annotation on scrape failure/warning. Pure formatting
plus a thin emit; opening a repo issue via gh is an onboarding/driver concern."""
import argparse
import sys

_LEVELS = {"error": "::error::", "warning": "::warning::", "notice": "::notice::"}


def format_notification(kind, message):
    prefix = _LEVELS.get(kind, "::notice::")
    return f"{prefix}[scrape] {message}"


def emit(kind, message, *, stream=None):
    stream = sys.stdout if stream is None else stream
    print(format_notification(kind, message), file=stream)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Emit a GitHub Actions annotation")
    parser.add_argument("--kind", choices=sorted(_LEVELS), default="error")
    parser.add_argument("--message", required=True)
    args = parser.parse_args(argv)
    emit(args.kind, args.message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_notify.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/notify.py assets/scraper-template/tests/test_notify.py
git commit -m "feat: notify.py — GitHub Actions failure/warning annotation

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: workflow template + text-assertion test

**Files:**
- Create: `assets/github-actions/scrape.yml`
- Test: `assets/scraper-template/tests/test_actions_workflow.py`

**Interfaces:**
- Consumes (referenced by the workflow, already present): `actions_setup.py`, `smoke_test.py`, `scrape.py`, `build_dataset.py`, `notify.py`.
- Produces: a scaffold-ready workflow template. The test reads it as text (from `parents[2]/"github-actions"/"scrape.yml"` relative to the test file) and asserts the fail-closed step order and required guards — it does NOT execute the workflow.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_actions_workflow.py
from pathlib import Path

WF_TEXT = (Path(__file__).resolve().parents[2] / "github-actions" / "scrape.yml").read_text(encoding="utf-8")


def test_workflow_has_manual_and_scheduled_triggers():
    assert "workflow_dispatch" in WF_TEXT
    assert "schedule" in WF_TEXT and "cron" in WF_TEXT


def test_workflow_order_materialize_then_gate_then_scrape():
    setup_i = WF_TEXT.index("actions_setup.py")
    gate_i = WF_TEXT.index("smoke_test.py")
    scrape_i = WF_TEXT.index("scrape.py --limit")
    assert setup_i < gate_i < scrape_i


def test_workflow_wires_gate_secrets():
    assert "SCRAPE_AUTHORIZATION" in WF_TEXT
    assert "SCRAPE_WARMUP" in WF_TEXT


def test_workflow_checkpoints_uploads_and_notifies():
    assert "git commit" in WF_TEXT
    assert "upload-artifact" in WF_TEXT
    assert "notify.py" in WF_TEXT
    assert "if: failure()" in WF_TEXT


def test_workflow_has_write_permission_for_checkpoint():
    assert "contents: write" in WF_TEXT
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_actions_workflow.py -q`
Expected: FAIL with `FileNotFoundError` (the workflow template does not exist yet).

- [ ] **Step 3: Write minimal implementation**

Create `assets/github-actions/scrape.yml`:

```yaml
# Template — scaffolded into a generated project's .github/workflows/.
# Not an active workflow in the plugin repo. See spec §5.3.
name: scrape
on:
  workflow_dispatch:
  schedule:
    - cron: "17 9 * * *"   # daily ~09:17 UTC; adjust per project

permissions:
  contents: write          # commit the resume checkpoint

concurrency:
  group: scrape
  cancel-in-progress: false

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Materialize gate secrets (fail-closed)
        env:
          SCRAPE_AUTHORIZATION: ${{ secrets.SCRAPE_AUTHORIZATION }}
          SCRAPE_WARMUP: ${{ secrets.SCRAPE_WARMUP }}
        run: python actions_setup.py

      - name: Compliance gate
        run: python smoke_test.py

      - name: Scrape (resumable chunk)
        env:
          HTTPS_PROXY: ${{ secrets.HTTPS_PROXY }}
        run: python scrape.py --limit 200

      - name: Build dataset (exports)
        # Records-file wiring (scrape -> build_dataset) is per-project via site_adapter; kept non-fatal.
        run: python build_dataset.py --records data/raw_records.json || echo "build_dataset skipped"

      - name: Commit checkpoint
        run: |
          git config user.name "scrape-bot"
          git config user.email "scrape-bot@users.noreply.github.com"
          mkdir -p state exports
          git add state exports
          git commit -m "checkpoint: scrape run ${{ github.run_id }}" || echo "no changes to checkpoint"
          git pull --rebase --autostash || echo "rebase skipped"
          git push || { python notify.py --kind error --message "checkpoint push FAILED for run ${{ github.run_id }} - cursor may re-scrape"; exit 1; }

      - uses: actions/upload-artifact@v4
        with:
          name: exports
          path: exports/

      - name: Notify on failure
        if: failure()
        run: python notify.py --kind error --message "scrape run ${{ github.run_id }} failed"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_actions_workflow.py -q`
Expected: PASS (5 passed).

Then the full suite:

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (all previous + new; the Playwright smoke still skipped).

- [ ] **Step 5: Commit**

```bash
git add assets/github-actions/scrape.yml assets/scraper-template/tests/test_actions_workflow.py
git commit -m "feat: Actions workflow template — materialize->gate->scrape->checkpoint->artifact

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage (§5.3):**
- Workflow runs deterministic pipeline on cron + manual → Task 4 (`workflow_dispatch` + `schedule`). ✓
- Secrets → gitignored gate files, fail-closed, 0600 → Tasks 1 & 2. ✓
- Compliance gate in-runtime, after materialization, before scrape → Task 4 order assertion + `smoke_test.py` step. ✓
- Chunked resumable scrape (`--limit`, `state/cursor.json`) → Task 4 `scrape.py --limit 200`. ✓
- Checkpoint commit (state + exports, counts as activity) + `upload-artifact` → Task 4. ✓
- `notify.py` on failure → Tasks 3 & 4 (`if: failure()`). ✓
- Testable stdlib helpers (`secrets_io`, `actions_setup`, `notify`) + template asserted by text → Tasks 1-4. ✓
- Deterministic now / Batch later (no API key required) → build_dataset step is deterministic + non-fatal; no ANTHROPIC_API_KEY in the required path. ✓
- Deploy automation (`gh secret set`) deferred to Plano 6 → not in this plan. ✓

**2. Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N". Every code step is complete. ✓

**3. Type consistency:**
- `materialize_secret(name, path, *, env, mode=0o600)` defined in Task 1; consumed by Task 2 with matching kwargs. ✓
- `actions_setup.main(argv=None, *, env=None, targets=None)` — tests inject `env`/`targets`; the workflow calls it with no args (uses `_SECRET_FILES` + `os.environ`). ✓
- `notify.format_notification/emit/main` defined in Task 3; the workflow calls `python notify.py --kind error --message ...` matching `main`'s argparse. ✓
- The workflow's script references (`actions_setup.py`, `smoke_test.py`, `scrape.py --limit`, `build_dataset.py`, `notify.py`) all match real files at the template root. ✓

Note for the implementer: `assets/github-actions/` is NOT gitignored and is NOT on the pytest pythonpath — Task 4's test locates the YAML by relative path (`parents[2]/"github-actions"/"scrape.yml"`), it is not imported. The workflow is a template and must never be copied into this repo's own `.github/workflows/`.
