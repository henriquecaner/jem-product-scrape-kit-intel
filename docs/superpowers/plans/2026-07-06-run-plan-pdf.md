# Run-plan em PDF (§12) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Renderizar o run-plan (Markdown) em PDF via Chrome headless, com fallback para HTML/Markdown quando o Chrome não existe — para que a etapa de aprovação nunca trave por falta de software.

**Architecture:** Um conversor Markdown→HTML mínimo em `jemscrape/` (stdlib puro, cobre só o subset do template do run-plan) gera HTML autocontido estilizado. Um driver `drivers/render_pdf.py` (fora da suíte stdlib, guardado como `playwright_render.py`) descobre o Chrome via Playwright e imprime o HTML em PDF; sem Chrome, retorna o caminho do HTML como fallback.

**Tech Stack:** Python 3 stdlib (conversor); Playwright/Chromium (driver, dep opcional).

## Global Constraints

- **stdlib-only no núcleo:** o conversor md→HTML fica em `jemscrape/`, stdlib puro. O PDF real depende de Chrome/Playwright e por isso vive **só** em `drivers/`.
- **Import de Playwright guardado:** ausência produz erro acionável (padrão de `drivers/playwright_render.py`), não `ImportError`.
- **Fallback nunca levanta:** Chrome ausente → retorna HTML, não erro. Aprovação nunca trava (spec §12/§18).
- **Escape de HTML:** conteúdo textual do Markdown é escapado (`<`, `>`, `&`) para não injetar tags.
- Testes sem rede; render real de PDF = skip-if-absent. Commits com prefixo convencional + trailer padrão.

---

### Task 1: Conversor Markdown→HTML mínimo

**Files:**
- Create: `assets/scraper-template/jemscrape/md_to_html.py`
- Test: `assets/scraper-template/tests/test_md_to_html.py`

**Interfaces:**
- Produces: `md_to_html(markdown: str, *, title: str = "Run Plan") -> str` — HTML autocontido (`<!doctype html>` + `<style>` inline) cobrindo o subset do template do run-plan: `#`/`##` (H1/H2), listas `- ` (UL), tabelas GFM (`| a | b |` + linha separadora), `**negrito**`, e parágrafos. Escapa `<`/`>`/`&` no texto antes de aplicar a formatação inline.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_md_to_html.py
from jemscrape.md_to_html import md_to_html


def test_headers_and_paragraph():
    html = md_to_html("# Title\n\nHello world")
    assert "<h1>Title</h1>" in html
    assert "<p>Hello world</p>" in html
    assert html.lstrip().lower().startswith("<!doctype html>")


def test_list_and_bold():
    html = md_to_html("- one\n- **two**")
    assert "<li>one</li>" in html
    assert "<li>one</li>" in html and "<strong>two</strong>" in html
    assert "<ul>" in html


def test_table():
    md = "| A | B |\n|---|---|\n| 1 | 2 |"
    html = md_to_html(md)
    assert "<table>" in html
    assert "<th>A</th>" in html and "<td>1</td>" in html


def test_escapes_html_in_content():
    html = md_to_html("A <script> & B")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html and "&amp;" in html
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_md_to_html.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

```python
# jemscrape/md_to_html.py
"""Minimal Markdown->HTML for the run-plan template (spec §12). NOT a general
Markdown engine — it covers exactly the subset the scrape-run-plan skill emits:
H1/H2, unordered lists, GFM tables, bold, paragraphs. Pure stdlib so it stays
in the core; the PDF step (Chrome) lives in drivers/render_pdf.py."""
import html as _html
import re

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_STYLE = """
body{font-family:-apple-system,Segoe UI,Arial,sans-serif;max-width:46rem;
margin:2rem auto;padding:0 1rem;color:#111;line-height:1.5}
h1{font-size:1.7rem;border-bottom:2px solid #333;padding-bottom:.3rem}
h2{font-size:1.25rem;margin-top:1.6rem}
table{border-collapse:collapse;width:100%;margin:1rem 0}
th,td{border:1px solid #bbb;padding:.4rem .6rem;text-align:left;vertical-align:top}
th{background:#f2f2f2}
"""


def _inline(text):
    escaped = _html.escape(text, quote=False)
    return _BOLD.sub(r"<strong>\1</strong>", escaped)


def _split_row(line):
    cells = line.strip().strip("|").split("|")
    return [c.strip() for c in cells]


def md_to_html(markdown, *, title="Run Plan"):
    lines = markdown.splitlines()
    out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("## "):
            out.append(f"<h2>{_inline(stripped[3:])}</h2>")
            i += 1
        elif stripped.startswith("# "):
            out.append(f"<h1>{_inline(stripped[2:])}</h1>")
            i += 1
        elif stripped.startswith("- "):
            items = []
            while i < n and lines[i].strip().startswith("- "):
                items.append(f"<li>{_inline(lines[i].strip()[2:])}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
        elif stripped.startswith("|") and i + 1 < n and set(lines[i + 1].strip()) <= set("|-: "):
            header = _split_row(stripped)
            i += 2  # skip header + separator
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(_split_row(lines[i].strip()))
                i += 1
            thead = "".join(f"<th>{_inline(c)}</th>" for c in header)
            body = "".join(
                "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>"
                for r in rows
            )
            out.append(f"<table><thead><tr>{thead}</tr></thead><tbody>{body}</tbody></table>")
        else:
            out.append(f"<p>{_inline(stripped)}</p>")
            i += 1
    body = "\n".join(out)
    return (f"<!doctype html>\n<html><head><meta charset=\"utf-8\">"
            f"<title>{_html.escape(title)}</title><style>{_STYLE}</style></head>"
            f"<body>\n{body}\n</body></html>\n")
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_md_to_html.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/md_to_html.py assets/scraper-template/tests/test_md_to_html.py
git commit -m "feat(run-plan): minimal stdlib Markdown->HTML for the run-plan template

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Driver `render_pdf` (Chrome + fallback)

**Files:**
- Create: `assets/scraper-template/drivers/render_pdf.py`
- Create: `assets/scraper-template/render_run_plan.py` (CLI raiz fino)
- Test: `assets/scraper-template/tests/test_render_pdf.py`

**Interfaces:**
- Consumes: `jemscrape.md_to_html.md_to_html` (Task 1).
- Produces:
  - `render_pdf(markdown_path, out_dir) -> dict` — sempre grava `<out_dir>/run-plan.html` (via `md_to_html`). Se o Chrome estiver disponível, também grava `<out_dir>/run-plan.pdf` e retorna `{"html": <path>, "pdf": <path>}`; senão `{"html": <path>, "pdf": None}`. Nunca levanta por Chrome ausente.
  - `_chrome_available() -> bool` — separado para os testes fazerem monkeypatch.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_render_pdf.py
import importlib


def test_fallback_writes_html_when_no_chrome(tmp_path, monkeypatch):
    render_pdf = importlib.import_module("drivers.render_pdf")
    monkeypatch.setattr(render_pdf, "_chrome_available", lambda: False)
    md = tmp_path / "run-plan.md"
    md.write_text("# Run Plan\n\n- item", encoding="utf-8")
    result = render_pdf.render_pdf(str(md), str(tmp_path))
    assert result["pdf"] is None
    assert (tmp_path / "run-plan.html").exists()
    assert "<h1>Run Plan</h1>" in (tmp_path / "run-plan.html").read_text(encoding="utf-8")


def test_pdf_render_when_chrome_present(tmp_path):
    import pytest
    pytest.importorskip("playwright")
    render_pdf = importlib.import_module("drivers.render_pdf")
    if not render_pdf._chrome_available():
        pytest.skip("chromium not installed")
    md = tmp_path / "run-plan.md"
    md.write_text("# Run Plan", encoding="utf-8")
    result = render_pdf.render_pdf(str(md), str(tmp_path))
    assert result["pdf"] is not None
    assert (tmp_path / "run-plan.pdf").exists()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_render_pdf.py::test_fallback_writes_html_when_no_chrome -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'drivers.render_pdf'`).

- [ ] **Step 3: Implement**

```python
# drivers/render_pdf.py
"""Run-plan PDF driver (spec §12). Discovers Chrome via Playwright and prints
the run-plan HTML to PDF. If Chrome isn't available, falls back to writing the
HTML only — an approval step never blocks on missing software. Playwright is a
guarded optional dependency; this module lives in drivers/, never in the core."""
from pathlib import Path

from jemscrape.md_to_html import md_to_html

try:
    from playwright.sync_api import sync_playwright
    _AVAILABLE = True
except ImportError:
    sync_playwright = None
    _AVAILABLE = False


def _chrome_available():
    """True when Playwright + a launchable Chromium are present."""
    if not _AVAILABLE:
        return False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception:
        return False


def render_pdf(markdown_path, out_dir):
    """Render the run-plan markdown to HTML (always) and PDF (if Chrome is
    available). Returns {"html": path, "pdf": path|None}. Never raises on a
    missing Chrome — writes HTML and returns pdf=None."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    markdown = Path(markdown_path).read_text(encoding="utf-8")
    html = md_to_html(markdown)
    html_path = out / "run-plan.html"
    html_path.write_text(html, encoding="utf-8")

    if not _chrome_available():
        return {"html": str(html_path), "pdf": None}

    pdf_path = out / "run-plan.pdf"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content(html, wait_until="load")
            page.pdf(path=str(pdf_path), format="A4", print_background=True)
        finally:
            browser.close()
    return {"html": str(html_path), "pdf": str(pdf_path)}
```

```python
# render_run_plan.py (CLI raiz)
"""CLI: render docs/run-plan.md to HTML + PDF (PDF when Chrome is available)."""
import argparse
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render the run-plan to HTML/PDF")
    parser.add_argument("--markdown", default="docs/run-plan.md")
    parser.add_argument("--out", default="docs")
    args = parser.parse_args(argv)
    from drivers.render_pdf import render_pdf
    result = render_pdf(args.markdown, args.out)
    if result["pdf"]:
        print(f"[run-plan] PDF -> {result['pdf']}")
    else:
        print(f"[run-plan] Chrome not found — HTML fallback -> {result['html']}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_render_pdf.py -v`
Expected: PASS (fallback passa; render real skip-if-absent).

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/drivers/render_pdf.py assets/scraper-template/render_run_plan.py assets/scraper-template/tests/test_render_pdf.py
git commit -m "feat(run-plan): render_pdf driver — Chrome PDF with HTML fallback

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Atualizar a skill `scrape-run-plan` + docs

**Files:**
- Modify: `skills/scrape-run-plan/SKILL.md` (seção "Output")
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: `render_run_plan.py` / `render_pdf` (Task 2).

- [ ] **Step 1: Reescrever a seção Output da skill**

Em `skills/scrape-run-plan/SKILL.md`, substituir a seção "Output" (linhas ~62-66) que hoje diz "PDF é enhancement futuro / não diga que há PDF". Nova redação: o output tem três níveis — Markdown (sempre, `docs/run-plan.md`), HTML estilizado (sempre, stdlib), e PDF (`python3 render_run_plan.py`, quando o Chrome está disponível; senão cai para o HTML sem travar). A camada de aprovação (`.scrape-approval.json`) pode hashear o artefato gerado. Referenciar `drivers/render_pdf.py` (§12).

- [ ] **Step 2: CHANGELOG**

Nova entrada descrevendo o render de run-plan em PDF com fallback.

- [ ] **Step 3: Rodar a suíte completa**

Run: `.venv/bin/python -m pytest -q`
Expected: tudo verde (+1 skip do Playwright já esperado; render real de PDF também skip-if-absent).

- [ ] **Step 4: Commit**

```bash
git add skills/scrape-run-plan/SKILL.md CHANGELOG.md
git commit -m "docs(run-plan): document PDF output with HTML fallback (render_run_plan.py)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review
- **Spec coverage:** conversor md→HTML (T1), driver Chrome+fallback (T2), skill+docs (T3) — cobre a Unidade 3.
- **Type consistency:** `md_to_html(markdown, *, title)` usado em T1/T2; `render_pdf(markdown_path, out_dir) -> {"html","pdf"}` em T2/T3; `_chrome_available()` monkeypatchável em T2.
- **stdlib boundary:** conversor em `jemscrape/` (stdlib), Playwright só em `drivers/render_pdf.py` — regra respeitada.
- **Placeholders:** nenhum.
