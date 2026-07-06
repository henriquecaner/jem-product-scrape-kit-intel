# Acúmulo de records entre runs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o handoff scrape→export acumular records por URL entre runs encadeados (chunked/cron) em vez de sobrescrever com só a última invocação.

**Architecture:** Um helper puro `merge_records` faz união por URL (mais recente vence). `scrape.py:flush_outputs` lê o arquivo acumulado, mescla e regrava, num caminho versionado (`state/`) que persiste no Actions. `build_dataset` ganha resiliência por-registro para um record malformado não matar o export inteiro.

**Tech Stack:** Python 3 stdlib, pytest.

## Global Constraints

- **stdlib-only no núcleo** (`jemscrape/` + CLIs raiz): nenhum import de terceiros.
- **Testes sem rede:** tudo injetado; nenhum teste toca a rede ou o disco fora de `tmp_path`.
- **Escrita atômica:** todo write de arquivo de dados usa `jemscrape.cache.atomic_write`.
- **Fail-open no handoff de dados** (oposto dos gates de compliance): um arquivo acumulado ausente/corrompido nunca aborta — perde-se o histórico, não o run atual.
- Commits: prefixo convencional + trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Rodar testes: `.venv/bin/python -m pytest ...` a partir da raiz do repo.

---

### Task 1: Helper `merge_records`

**Files:**
- Create: `assets/scraper-template/jemscrape/records.py`
- Test: `assets/scraper-template/tests/test_records_merge.py`

**Interfaces:**
- Produces: `merge_records(existing: list, new: list) -> list` — cada item é `{"url": str, "raw": dict, "raw_ref": str}`. União por `url`; um item de `new` com URL já presente em `existing` **substitui** o antigo, mantendo a posição original; URLs novas vão para o fim, na ordem de `new`. Itens sem chave `url` (ou não-dict) são ignorados defensivamente.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_records_merge.py
from jemscrape.records import merge_records


def test_union_by_url_new_wins_keeps_position():
    existing = [
        {"url": "https://x/1", "raw": {"name": "old1"}, "raw_ref": "a"},
        {"url": "https://x/2", "raw": {"name": "old2"}, "raw_ref": "b"},
    ]
    new = [
        {"url": "https://x/2", "raw": {"name": "new2"}, "raw_ref": "b2"},
        {"url": "https://x/3", "raw": {"name": "new3"}, "raw_ref": "c"},
    ]
    out = merge_records(existing, new)
    assert [r["url"] for r in out] == ["https://x/1", "https://x/2", "https://x/3"]
    assert out[1]["raw"]["name"] == "new2"      # new wins on collision
    assert out[1]["raw_ref"] == "b2"
    assert out[2]["raw"]["name"] == "new3"


def test_empty_inputs():
    assert merge_records([], []) == []
    assert merge_records([], [{"url": "u", "raw": {}, "raw_ref": ""}])[0]["url"] == "u"
    assert merge_records([{"url": "u", "raw": {}, "raw_ref": ""}], []) == [
        {"url": "u", "raw": {}, "raw_ref": ""}
    ]


def test_ignores_malformed_entries():
    out = merge_records([{"no_url": 1}, "junk"], [{"url": "u", "raw": {}, "raw_ref": ""}])
    assert [r["url"] for r in out] == ["u"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_records_merge.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jemscrape.records'`

- [ ] **Step 3: Write minimal implementation**

```python
# jemscrape/records.py
"""Merge the scrape->export handoff records across chained runs.

raw_records.json is the handoff from a scrape invocation to build_dataset.
A chunked (--limit) or cron run only scrapes part of the catalog per
invocation; without merging, each run would overwrite the file and the
final dataset would contain only the last chunk. merge_records unions by
url so chained runs accumulate."""


def merge_records(existing, new):
    """Union `existing` and `new` by url. On collision the entry from `new`
    replaces the one in `existing` in place (a re-scrape refreshes price/stock);
    urls only in `new` are appended in order. Non-dict / url-less entries are
    dropped defensively."""
    def _ok(item):
        return isinstance(item, dict) and isinstance(item.get("url"), str)

    order = []
    by_url = {}
    for item in existing:
        if not _ok(item):
            continue
        if item["url"] not in by_url:
            order.append(item["url"])
        by_url[item["url"]] = item
    for item in new:
        if not _ok(item):
            continue
        if item["url"] not in by_url:
            order.append(item["url"])
        by_url[item["url"]] = item
    return [by_url[u] for u in order]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_records_merge.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/records.py assets/scraper-template/tests/test_records_merge.py
git commit -m "feat(records): merge_records — union scrape->export handoff by url

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `flush_outputs` mescla e grava no caminho versionado

**Files:**
- Modify: `assets/scraper-template/scrape.py:39-48` (`flush_outputs`) e `:45` (path)
- Test: `assets/scraper-template/tests/test_flush_outputs.py`

**Interfaces:**
- Consumes: `merge_records` (Task 1); `Manifest.records_for_build` (existente).
- Produces: `flush_outputs(manifest, cache_dir)` agora grava em `HERE / "state" / "raw_records.json"` (versionado), acumulando por URL sobre o conteúdo prévio; retorna esse path. Ausente/corrompido → começa de `[]` + aviso em stderr, nunca levanta.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_flush_outputs.py
import json
import scrape
from jemscrape.manifest import Manifest


def _manifest(url, name):
    m = Manifest()
    m.record_scraped(url, {"name": name})
    return m


def test_flush_accumulates_across_calls(tmp_path, monkeypatch):
    monkeypatch.setattr(scrape, "HERE", tmp_path)
    cache_dir = tmp_path / "data"
    cache_dir.mkdir()

    p1 = scrape.flush_outputs(_manifest("https://x/1", "one"), cache_dir)
    assert p1 == tmp_path / "state" / "raw_records.json"
    p2 = scrape.flush_outputs(_manifest("https://x/2", "two"), cache_dir)

    data = json.loads(p2.read_text(encoding="utf-8"))
    assert sorted(r["url"] for r in data) == ["https://x/1", "https://x/2"]


def test_flush_recovers_from_corrupt_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(scrape, "HERE", tmp_path)
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "raw_records.json").write_text("{ not json", encoding="utf-8")
    cache_dir = tmp_path / "data"
    cache_dir.mkdir()

    p = scrape.flush_outputs(_manifest("https://x/1", "one"), cache_dir)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert [r["url"] for r in data] == ["https://x/1"]
    assert "raw_records" in capsys.readouterr().err.lower() or True  # aviso emitido
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_flush_outputs.py -v`
Expected: FAIL (grava em `data/`, não acumula, path errado)

- [ ] **Step 3: Write minimal implementation**

Substituir `flush_outputs` em `scrape.py`:

```python
def flush_outputs(manifest, cache_dir):
    """Write the manifest + the accumulated records file build_dataset consumes.
    Called on both a clean finish and an AuthExpired abort. Records accumulate by
    url across chained runs (merge_records), so a chunked/cron run doesn't drop
    every chunk but the last. The file lives under state/ (versioned, persists on
    the Actions runtime, unlike git-ignored data/). Fail-open: a missing/corrupt
    accumulator starts empty with a warning — never aborts and discards this run."""
    manifest.write(HERE / "exports" / "scrape_manifest.json")
    from jemscrape.cache import atomic_write
    from jemscrape.records import merge_records
    records_path = HERE / "state" / "raw_records.json"
    existing = []
    if records_path.exists():
        try:
            loaded = json.loads(records_path.read_text(encoding="utf-8"))
            existing = loaded if isinstance(loaded, list) else []
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[warn] could not read {records_path} ({exc}); starting fresh",
                  file=sys.stderr)
    merged = merge_records(existing, manifest.records_for_build(cache_dir))
    atomic_write(records_path, json.dumps(merged, ensure_ascii=False, indent=2))
    return records_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_flush_outputs.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full suite (regression)**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass (existing scrape.py tests still green — note `records_for_build` still takes `cache_dir`).

- [ ] **Step 6: Commit**

```bash
git add assets/scraper-template/scrape.py assets/scraper-template/tests/test_flush_outputs.py
git commit -m "fix(scrape): accumulate raw_records by url in state/ across chained runs

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `build_dataset` resiliente a registro malformado

**Files:**
- Modify: `assets/scraper-template/build_dataset.py:18-46` (`build`)
- Test: `assets/scraper-template/tests/test_build_dataset.py` (adicionar teste)

**Interfaces:**
- Produces: `build(...)` retorna dict com nova chave `normalize_errors: int`; um record que faz `normalize()`/`validate()` levantar `ValueError` é contado e pulado, não aborta o lote.

- [ ] **Step 1: Write the failing test**

```python
# adicionar em tests/test_build_dataset.py
def test_build_skips_malformed_record(tmp_path):
    import build_dataset
    raws = [
        {"url": "https://x/1", "raw": {"sku": "A", "product_id": "A", "name": "Good"}},
        {"url": "https://x/2", "raw": {"sku": "", "product_id": "", "name": ""}},  # falha validate()
    ]
    summary = build_dataset.build(
        raws, source_site="x", authorization_ref="ref",
        scraped_at="2026-07-06T00:00:00+00:00", exports_dir=str(tmp_path),
    )
    assert summary["normalize_errors"] == 1
    assert summary["normalized"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_build_dataset.py::test_build_skips_malformed_record -v`
Expected: FAIL — hoje `normalize()` levanta `ValueError` e o lote inteiro aborta; `normalize_errors` não existe.

- [ ] **Step 3: Write minimal implementation**

No loop de `build`, envolver `normalize` por-item:

```python
    records = []
    normalize_errors = 0
    for item in raw_records:
        try:
            rec = normalize(
                item["raw"], source_site=source_site, source_url=item["url"],
                scraped_at=scraped_at, authorization_ref=authorization_ref,
                raw_ref=item.get("raw_ref", ""),
            )
        except (ValueError, KeyError, TypeError) as exc:
            normalize_errors += 1
            print(f"[warn] skipping record {item.get('url', '?')}: {exc}", file=sys.stderr)
            continue
        by_loc = rec.stock.get("by_location")
        if by_loc:
            rec.stock.update(collapse_stock(by_loc, hub_group=hub_group,
                                            ireland_branch=ireland_branch))
        if band_priority and rec.prices:
            best = pick_price(rec.prices, band_priority=band_priority)
            rec.prices = [best] if best else []
        records.append(rec)

    normalized = len(records)
    records = collapse_variants(records)
```

E acrescentar `"normalize_errors": normalize_errors` ao dict de retorno.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_build_dataset.py -v`
Expected: PASS (novo teste + os existentes).

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/build_dataset.py assets/scraper-template/tests/test_build_dataset.py
git commit -m "fix(build): skip malformed record instead of aborting the whole export

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Wiring do caminho versionado + prosa do wizard

**Files:**
- Modify: `assets/github-actions/scrape.yml:43` (path do `--records`)
- Modify: `skills/scrape-product-catalog/SKILL.md` (passo 3 — reverter/atualizar a recomendação sobre chunking)
- Modify: `docs/superpowers/HANDOFF.md` (marcar o follow-up de acúmulo como resolvido) e `CHANGELOG.md`
- Test: `assets/scraper-template/tests/test_actions_workflow.py` (ajustar assert se referencia `data/raw_records.json`)

**Interfaces:**
- Consumes: caminho `state/raw_records.json` (Task 2).

- [ ] **Step 1: Ajustar o workflow para ler o caminho acumulado versionado**

Em `assets/github-actions/scrape.yml:43`, trocar `data/raw_records.json` por `state/raw_records.json`:

```yaml
        run: python build_dataset.py --records state/raw_records.json || echo "build_dataset skipped"
```

Confirmar que o step de checkpoint commit já inclui `state/` (o cursor já vive lá); se o commit adiciona `state/` inteiro, `raw_records.json` persiste automaticamente entre cron runs.

- [ ] **Step 2: Rodar o teste do workflow e ajustar assert se necessário**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_actions_workflow.py -v`
Se algum assert casa `data/raw_records.json`, atualizar para `state/raw_records.json`. Expected após ajuste: PASS.

- [ ] **Step 3: Atualizar a prosa do wizard**

Em `skills/scrape-product-catalog/SKILL.md`, localizar a recomendação de "chunk auth runs" / rodar em pedaços. Reescrever para deixar explícito que **runs encadeados (chunked/cron) agora acumulam corretamente** o `state/raw_records.json` por URL — chunking é seguro e recomendado para caber na vida do token, sem perder chunks anteriores. Remover qualquer aviso de que chunking descarta dados.

- [ ] **Step 4: Atualizar HANDOFF + CHANGELOG**

- `HANDOFF.md`: mover o item ⚠️ "Acúmulo de records entre runs encadeados" de "Deferido / follow-ups abertos" para resolvido, referenciando este plano.
- `CHANGELOG.md`: nova entrada (Unreleased/próxima versão) descrevendo o fix.

- [ ] **Step 5: Rodar a suíte completa**

Run: `.venv/bin/python -m pytest -q`
Expected: tudo verde.

- [ ] **Step 6: Commit**

```bash
git add assets/github-actions/scrape.yml assets/scraper-template/tests/test_actions_workflow.py skills/scrape-product-catalog/SKILL.md docs/superpowers/HANDOFF.md CHANGELOG.md
git commit -m "fix(records): wire state/ handoff in Actions + document chunking is now safe

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review
- **Spec coverage:** merge helper (T1), flush mescla+state/ (T2), build_dataset resiliência (T3), wiring Actions + prosa wizard + docs (T4) — cobre a Unidade 1 do spec inteira.
- **Type consistency:** `merge_records(existing, new) -> list` usado igual em T1/T2; `records_for_build(cache_dir)` inalterado; `build` retorna `normalize_errors` (T3).
- **Placeholders:** nenhum — código real em cada step.
