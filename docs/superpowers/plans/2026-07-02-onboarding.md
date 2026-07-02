# Onboarding Implementation Plan (Plano 6)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the testable onboarding core (spec §6.1): a toolchain green-check that renders an "IT kit", a Desktop PATH fix that merges into `~/.claude/settings.json`, a `/scrape-setup`-backing CLI that gates readiness, the scaffold `.gitignore` + IT-request assets, and a `deploy_actions` driver that builds the `gh` secret-set commands (closing Plano 5's deferred deploy).

**Architecture:** Detection/config logic is pure stdlib + TDD (`jemscrape/toolchain.py`, `jemscrape/settings_patch.py`), driven by a `scrape_setup.py` CLI with injectable `which`/settings-path for tests. The IT kit and scaffold `.gitignore` are assets validated by text-assertion tests. `drivers/deploy_actions.py` builds `gh secret set` commands as data (secret piped via stdin, never argv). The `scrape-onboarding` skill markdown and `/scrape-setup` command wrapper are deferred to Plano 7 (packaging) so no inert markdown ships here.

**Tech Stack:** Python 3 stdlib only. Tests via `pytest` (`.venv/bin/python -m pytest`).

## Global Constraints

- **Python 3 stdlib-only** — no third-party imports.
- **Dependency injection for testability** — inject `which` (tool detection) and settings/env paths; never touch the real `~/.claude/settings.json` or run real `gh`/`winget` in a unit test.
- **Deliverables stay versioned** — the scaffold `.gitignore` must block `data/` + gate files + secrets but MUST NOT ignore `exports/`, `state/`, or `wiki/` (spec §5/§13).
- **Secrets never on argv** — `deploy_actions` pipes secret values from files via stdin; the command argv carries only the secret NAME.
- **Reuse** `atomic_write` from `jemscrape.cache`. `drivers/` already exists (has `__init__.py` from Plano 3a).
- **Deferred:** auth/run-plan drivers (daily_refresh/pull/watch/render_pdf); the `scrape-onboarding` skill + `/scrape-setup`/`/scrape-init` commands (Plano 7).
- **Tests:** `.venv/bin/python -m pytest -q`. Baseline 168 passed, 1 skipped; keep green + pristine.
- **Commits** end with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

## File Structure

- `assets/scraper-template/jemscrape/toolchain.py` — CREATE: `Tool`, `TOOLS`, `check_tools`, `render_it_kit`.
- `assets/scraper-template/jemscrape/settings_patch.py` — CREATE: `patch_claude_settings`.
- `assets/scraper-template/scrape_setup.py` — CREATE: `/scrape-setup`-backing CLI.
- `assets/project-skeleton/.gitignore` — CREATE.
- `assets/it-request/README.md` — CREATE.
- `assets/scraper-template/drivers/deploy_actions.py` — CREATE: `build_secret_commands`.
- Tests: `tests/test_toolchain.py`, `tests/test_settings_patch.py`, `tests/test_scrape_setup.py`, `tests/test_project_skeleton.py`, `tests/test_it_request.py`, `tests/test_deploy_actions.py`.

---

### Task 1: `jemscrape/toolchain.py` — green check + IT kit

**Files:**
- Create: `assets/scraper-template/jemscrape/toolchain.py`
- Test: `assets/scraper-template/tests/test_toolchain.py`

**Interfaces:**
- Produces:
  - `Tool` dataclass: `name, label, winget_id, why, required`.
  - `TOOLS` tuple (git, gh, python3 required; playwright optional).
  - `check_tools(*, which, tools=TOOLS) -> dict` with `ready` (all required present), `present` (list[Tool]), `missing` (list[Tool]). `which(name) -> path|None` injected.
  - `render_it_kit(report) -> str` — markdown with `winget install` lines for missing tools that have a `winget_id`, plus manual notes for missing ones without (e.g. Playwright); `""` when nothing installable is missing.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_toolchain.py
from jemscrape.toolchain import check_tools, render_it_kit


def _which(present):
    return lambda name: ("/usr/bin/" + name) if name in present else None


def test_check_tools_all_present_ready():
    rep = check_tools(which=_which({"git", "gh", "python3", "playwright"}))
    assert rep["ready"] is True
    assert rep["missing"] == []


def test_check_tools_missing_required_not_ready():
    rep = check_tools(which=_which({"git", "python3"}))   # gh (required) missing
    assert rep["ready"] is False
    assert any(t.name == "gh" for t in rep["missing"])


def test_check_tools_missing_only_optional_still_ready():
    rep = check_tools(which=_which({"git", "gh", "python3"}))   # playwright optional
    assert rep["ready"] is True
    assert any(t.name == "playwright" for t in rep["missing"])


def test_render_it_kit_lists_winget_for_missing():
    rep = check_tools(which=_which({"python3"}))   # git, gh missing (winget) + playwright (manual)
    kit = render_it_kit(rep)
    assert "Git.Git" in kit and "GitHub.cli" in kit
    assert "winget install" in kit
    assert "Playwright" in kit    # manual note for the no-winget tool


def test_render_it_kit_empty_when_ready():
    rep = check_tools(which=_which({"git", "gh", "python3", "playwright"}))
    assert render_it_kit(rep) == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_toolchain.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'jemscrape.toolchain'`.

- [ ] **Step 3: Write minimal implementation**

```python
# assets/scraper-template/jemscrape/toolchain.py
"""Toolchain green check + 'kit for IT' rendering (onboarding §6 Fase A)."""
from dataclasses import dataclass


@dataclass
class Tool:
    name: str          # executable to look up
    label: str         # human label
    winget_id: str     # winget package id for the IT kit ("" = no winget install)
    why: str
    required: bool     # blocks readiness vs optional (browser path)


TOOLS = (
    Tool("git", "Git", "Git.Git", "version control + resume checkpoints", True),
    Tool("gh", "GitHub CLI", "GitHub.cli", "gh secret set / repo ops (Actions runtime)", True),
    Tool("python3", "Python 3", "Python.Python.3.12", "runs the scraper engine", True),
    Tool("playwright", "Playwright", "",
         "browser render path for SPA/JS sites — pip install playwright && playwright install chromium",
         False),
)


def check_tools(*, which, tools=TOOLS):
    found = {t.name: bool(which(t.name)) for t in tools}
    present = [t for t in tools if found[t.name]]
    missing = [t for t in tools if not found[t.name]]
    ready = all(found[t.name] for t in tools if t.required)
    return {"ready": ready, "present": present, "missing": missing}


def render_it_kit(report):
    missing = report.get("missing", [])
    winget = [t for t in missing if t.winget_id]
    manual = [t for t in missing if not t.winget_id]
    if not winget and not manual:
        return ""
    lines = ["# Kit para a TI — instalar de uma vez", ""]
    if winget:
        lines += ["Rode como administrador (PowerShell):", "", "```powershell"]
        for t in winget:
            lines.append(f"winget install --id {t.winget_id} -e --silent   # {t.label}: {t.why}")
        lines += ["```", ""]
    if manual:
        lines.append("Passos manuais:")
        for t in manual:
            lines.append(f"- {t.label}: {t.why}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_toolchain.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/toolchain.py assets/scraper-template/tests/test_toolchain.py
git commit -m "feat: toolchain green check + IT-kit rendering (onboarding)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `jemscrape/settings_patch.py` — Desktop PATH fix

**Files:**
- Create: `assets/scraper-template/jemscrape/settings_patch.py`
- Test: `assets/scraper-template/tests/test_settings_patch.py`

**Interfaces:**
- Consumes: `atomic_write` from `jemscrape.cache`.
- Produces: `patch_claude_settings(path, *, env) -> dict` — merges `env` (dict VAR→value) into the `env` object of the JSON settings at `path`, preserving all other keys; creates the file if absent; tolerates a corrupt/non-dict existing file by starting fresh; returns the merged settings dict.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_settings_patch.py
import json

from jemscrape.settings_patch import patch_claude_settings


def test_patch_creates_file_with_env(tmp_path):
    p = tmp_path / "settings.json"
    out = patch_claude_settings(p, env={"PATH": "/opt/bin"})
    assert out["env"]["PATH"] == "/opt/bin"
    assert json.loads(p.read_text(encoding="utf-8"))["env"]["PATH"] == "/opt/bin"


def test_patch_preserves_existing_keys_and_env(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"model": "opus", "env": {"FOO": "bar"}}), encoding="utf-8")
    out = patch_claude_settings(p, env={"PATH": "/opt/bin"})
    assert out["model"] == "opus"
    assert out["env"]["FOO"] == "bar"
    assert out["env"]["PATH"] == "/opt/bin"


def test_patch_survives_corrupt_settings(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{not json", encoding="utf-8")
    out = patch_claude_settings(p, env={"PATH": "/opt/bin"})
    assert out["env"]["PATH"] == "/opt/bin"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_settings_patch.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'jemscrape.settings_patch'`.

- [ ] **Step 3: Write minimal implementation**

```python
# assets/scraper-template/jemscrape/settings_patch.py
"""Merge PATH/env into ~/.claude/settings.json without clobbering existing keys
(Desktop-app PATH fix, onboarding §6 Fase B). Atomic write."""
import json
from pathlib import Path

from .cache import atomic_write


def patch_claude_settings(path, *, env):
    p = Path(path)
    settings = {}
    if p.exists():
        try:
            settings = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            settings = {}
        if not isinstance(settings, dict):
            settings = {}
    current_env = settings.get("env")
    if not isinstance(current_env, dict):
        current_env = {}
    current_env.update(env)
    settings["env"] = current_env
    atomic_write(p, json.dumps(settings, indent=2) + "\n")
    return settings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_settings_patch.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/settings_patch.py assets/scraper-template/tests/test_settings_patch.py
git commit -m "feat: settings_patch — merge PATH env into settings.json (Desktop fix)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `scrape_setup.py` — /scrape-setup backing CLI

**Files:**
- Create: `assets/scraper-template/scrape_setup.py`
- Test: `assets/scraper-template/tests/test_scrape_setup.py`

**Interfaces:**
- Consumes: `check_tools`/`render_it_kit` (Task 1); `patch_claude_settings` (Task 2).
- Produces: `main(argv=None, *, which=None, settings_path=None, path_env=None) -> int`. Runs the green check and prints per-tool OK/MISS; if a `--settings` path (or injected `settings_path`) is given, applies the PATH fix (env = injected `path_env` or `{"PATH": os.environ["PATH"]}`); returns `0` when ready, `1` when a required tool is missing (printing the IT kit + "NOT READY" to stderr). `which`/`settings_path`/`path_env` injectable for tests.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scrape_setup.py
import json

import scrape_setup


def _which(present):
    return lambda n: ("/usr/bin/" + n) if n in present else None


def test_setup_ready_returns_0(capsys):
    rc = scrape_setup.main([], which=_which({"git", "gh", "python3", "playwright"}))
    assert rc == 0
    assert "READY" in capsys.readouterr().out


def test_setup_missing_required_returns_1_with_kit(capsys):
    rc = scrape_setup.main([], which=_which({"python3"}))   # git, gh missing
    assert rc == 1
    err = capsys.readouterr().err
    assert "winget install" in err and "NOT READY" in err


def test_setup_applies_path_fix(tmp_path):
    settings = tmp_path / "settings.json"
    rc = scrape_setup.main(
        ["--settings", str(settings)],
        which=_which({"git", "gh", "python3", "playwright"}),
        path_env={"PATH": "/opt/bin"})
    assert rc == 0
    assert json.loads(settings.read_text(encoding="utf-8"))["env"]["PATH"] == "/opt/bin"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_scrape_setup.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrape_setup'`.

- [ ] **Step 3: Write minimal implementation**

```python
# assets/scraper-template/scrape_setup.py
"""Backing for /scrape-setup (onboarding §6 Fase B): green check + Desktop PATH
fix + readiness gate. Exit 0 when ready, 1 when a required tool is missing."""
import argparse
import os
import shutil
import sys

from jemscrape.toolchain import check_tools, render_it_kit
from jemscrape.settings_patch import patch_claude_settings


def main(argv=None, *, which=None, settings_path=None, path_env=None):
    parser = argparse.ArgumentParser(description="Scraper onboarding: green check + PATH fix")
    parser.add_argument("--settings", default=None, help="path to ~/.claude/settings.json")
    args = parser.parse_args(argv)

    which = shutil.which if which is None else which
    report = check_tools(which=which)

    print("[setup] toolchain:")
    for t in report["present"]:
        print(f"  OK   {t.label}")
    for t in report["missing"]:
        print(f"  MISS {t.label} ({'REQUIRED' if t.required else 'optional'})")

    settings = args.settings or settings_path
    if settings:
        env = path_env if path_env is not None else {"PATH": os.environ.get("PATH", "")}
        patch_claude_settings(settings, env=env)
        print(f"[setup] wrote PATH env to {settings}")

    if not report["ready"]:
        kit = render_it_kit(report)
        if kit:
            print("\n" + kit, file=sys.stderr)
        print("[setup] NOT READY - install the required tools above, then re-run.", file=sys.stderr)
        return 1
    print("[setup] READY - you can run /scrape-init.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_scrape_setup.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/scrape_setup.py assets/scraper-template/tests/test_scrape_setup.py
git commit -m "feat: scrape_setup CLI — green check + PATH fix + readiness gate

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: scaffold `.gitignore` + IT-request assets

**Files:**
- Create: `assets/project-skeleton/.gitignore`
- Create: `assets/it-request/README.md`
- Test: `assets/scraper-template/tests/test_project_skeleton.py`
- Test: `assets/scraper-template/tests/test_it_request.py`

**Interfaces:**
- Produces two assets validated by text-assertion tests (located via `Path(__file__).resolve().parents[2]` = the `assets/` dir).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_project_skeleton.py
from pathlib import Path

GI = (Path(__file__).resolve().parents[2] / "project-skeleton" / ".gitignore").read_text(encoding="utf-8")


def test_gitignore_blocks_cache_and_secrets():
    for pat in ["data/", ".scrape-authorization.json", ".scrape-warmup.json", "*.token", ".env"]:
        assert pat in GI


def test_gitignore_does_not_block_deliverables():
    ignore_lines = [l.strip() for l in GI.splitlines() if l.strip() and not l.strip().startswith("#")]
    for pat in ["exports/", "state/", "wiki/", "exports", "state", "wiki"]:
        assert pat not in ignore_lines
```

```python
# tests/test_it_request.py
from pathlib import Path

DOC = (Path(__file__).resolve().parents[2] / "it-request" / "README.md").read_text(encoding="utf-8")


def test_it_request_lists_toolchain():
    assert "Git.Git" in DOC and "GitHub.cli" in DOC and "Python.Python" in DOC
    assert "playwright" in DOC.lower()


def test_it_request_lists_org_provisioning():
    assert "proxy" in DOC.lower()
    assert "ANTHROPIC_API_KEY" in DOC
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_project_skeleton.py assets/scraper-template/tests/test_it_request.py -q`
Expected: FAIL with `FileNotFoundError` (the assets don't exist yet).

- [ ] **Step 3: Write the assets**

Create `assets/project-skeleton/.gitignore`:

```
# Raw scrape cache — heavy + may hold scraped third-party content. Never commit.
data/

# Secrets / gate files — reconstructed from Actions secrets at runtime, never committed.
.scrape-authorization.json
.scrape-warmup.json
*.token
*.secret
.env

# Python
__pycache__/
*.py[cod]
.venv/

# OS
.DS_Store

# NOTE: exports/, state/, and wiki/ are intentionally VERSIONED — the deliverable
# (products.csv, wiki/) and the resume checkpoint (state/cursor.json). Do NOT ignore them.
```

Create `assets/it-request/README.md`:

```markdown
# Pedido para a TI — kit de scraping JEM

Instalar/provisionar de uma vez (a maioria exige senha de admin no Windows).

## Toolchain (por máquina do usuário)

winget (PowerShell como administrador):

    winget install --id Git.Git -e --silent
    winget install --id GitHub.cli -e --silent
    winget install --id Python.Python.3.12 -e --silent

Caminho browser (só para sites SPA/JS ou com login):

    pip install playwright
    playwright install chromium

Chrome normalmente já está presente.

## Provisionamento da org (não é por usuário)

- **Conta de proxy compartilhada** (residencial, saída no país-alvo) — apenas para alvos geo-restritos.
- **`ANTHROPIC_API_KEY`** — secret do repositório, para normalização via LLM no runtime GitHub Actions (Batch API). Apenas quando a normalização assistida por LLM estiver em uso.
- **Projeto GCP + billing + IAM** — apenas para o fallback VM (fora do caminho padrão).

## Notas

- O repositório do projeto deve ser **privado** (dado sensível).
- Os secrets do Actions (`SCRAPE_AUTHORIZATION`, `SCRAPE_WARMUP`, e opcionalmente `HTTPS_PROXY`/`ANTHROPIC_API_KEY`) são setados via `gh secret set` (requer `gh` autenticado).
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_project_skeleton.py assets/scraper-template/tests/test_it_request.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add assets/project-skeleton/.gitignore assets/it-request/README.md assets/scraper-template/tests/test_project_skeleton.py assets/scraper-template/tests/test_it_request.py
git commit -m "feat: scaffold .gitignore (Plano 5 blocker) + IT-request kit

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: `drivers/deploy_actions.py` — build `gh secret set` commands

**Files:**
- Create: `assets/scraper-template/drivers/deploy_actions.py`
- Test: `assets/scraper-template/tests/test_deploy_actions.py`

**Interfaces:**
- Produces: `build_secret_commands(project_dir, *, secret_map=_SECRET_MAP) -> list[dict]`. For each `(NAME, filename)` in `secret_map` whose file exists in `project_dir`, returns a step `{"secret": NAME, "argv": ["gh", "secret", "set", NAME], "stdin_file": Path}`. The secret VALUE is never on argv — it is piped from `stdin_file`. Absent files are skipped. Default `_SECRET_MAP` covers `SCRAPE_AUTHORIZATION`→`.scrape-authorization.json` and `SCRAPE_WARMUP`→`.scrape-warmup.json`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_deploy_actions.py
import drivers.deploy_actions as da


def test_build_secret_commands_for_existing_gate_files(tmp_path):
    (tmp_path / ".scrape-authorization.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".scrape-warmup.json").write_text("{}", encoding="utf-8")
    steps = da.build_secret_commands(tmp_path)
    assert [s["secret"] for s in steps] == ["SCRAPE_AUTHORIZATION", "SCRAPE_WARMUP"]
    for s in steps:
        assert s["argv"][:3] == ["gh", "secret", "set"]
        assert s["argv"][-1] == s["secret"]
        assert s["stdin_file"].exists()
        # the secret value must NOT appear on argv (it comes from stdin_file)
        assert "{}" not in s["argv"]


def test_build_secret_commands_skips_absent_files(tmp_path):
    (tmp_path / ".scrape-authorization.json").write_text("{}", encoding="utf-8")
    steps = da.build_secret_commands(tmp_path)   # warmup file absent
    assert [s["secret"] for s in steps] == ["SCRAPE_AUTHORIZATION"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_deploy_actions.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'drivers.deploy_actions'`.

- [ ] **Step 3: Write minimal implementation**

```python
# assets/scraper-template/drivers/deploy_actions.py
"""Deploy the Actions workflow for a scraped project (onboarding §6.1). Builds the
gh commands that set the gate secrets from local files — the secret value is piped
via stdin, NEVER placed on argv (which would leak it into process listings)."""
from pathlib import Path

_SECRET_MAP = (
    ("SCRAPE_AUTHORIZATION", ".scrape-authorization.json"),
    ("SCRAPE_WARMUP", ".scrape-warmup.json"),
)


def build_secret_commands(project_dir, *, secret_map=_SECRET_MAP):
    project_dir = Path(project_dir)
    steps = []
    for name, filename in secret_map:
        f = project_dir / filename
        if f.exists():
            steps.append({
                "secret": name,
                "argv": ["gh", "secret", "set", name],
                "stdin_file": f,
            })
    return steps
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_deploy_actions.py -q`
Expected: PASS (2 passed).

Then the full suite:

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (all previous + new; Playwright smoke still skipped).

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/drivers/deploy_actions.py assets/scraper-template/tests/test_deploy_actions.py
git commit -m "feat: deploy_actions — build gh secret-set commands (secret via stdin)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage (§6.1):**
- Green check (detect tools + report) → Task 1. ✓
- IT kit (winget for missing) → Task 1 (`render_it_kit`). ✓
- Desktop PATH fix into settings.json (no clobber) → Task 2. ✓
- `/scrape-setup`-backing CLI, readiness gate → Task 3. ✓
- Scaffold `.gitignore` (blocks cache/secrets, keeps exports/state/wiki) → Task 4 (Plano 5 blocker). ✓
- IT-request asset (toolchain + proxy + API key) → Task 4. ✓
- `deploy_actions` gh-secret builder (secret via stdin) → Task 5. ✓
- Skill markdown + commands deferred to Plano 7 → not in this plan. ✓

**2. Placeholder scan:** No TBD/TODO/"handle edge cases". Every code step is complete. ✓

**3. Type consistency:**
- `check_tools(*, which, tools=TOOLS) -> {"ready","present","missing"}` (Task 1) consumed by `render_it_kit` (Task 1) and `scrape_setup.main` (Task 3). ✓
- `patch_claude_settings(path, *, env)` (Task 2) consumed by `scrape_setup.main` (Task 3) with matching kwargs. ✓
- `build_secret_commands(project_dir, *, secret_map)` (Task 5) — step dict shape matches its tests. ✓
- `atomic_write(path, text)` reused from `jemscrape.cache` (existing signature). ✓

Note for the implementer: the asset tests in Task 4 locate files via `parents[2]` (the `assets/` dir) — `assets/project-skeleton/.gitignore` and `assets/it-request/README.md` are NOT on the pytest pythonpath and are read as text, never imported. `drivers/` already has `__init__.py` (from Plano 3a), so `drivers.deploy_actions` imports without adding one.
