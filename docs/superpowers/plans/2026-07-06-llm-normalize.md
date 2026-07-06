# LLM-normalize (infra genérica + categorização, runtime Local) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Habilitar normalização assistida por LLM para categorização (breadcrumbs crus → taxonomia canônica JEM) sem o motor jamais chamar um LLM: o Claude (via skill, runtime Local) produz um `category_map.json` que o código aplica deterministicamente.

**Architecture:** `normalize` ganha um parâmetro opcional `category_map` (dict). Um CLI extrai as categorias cruas distintas de um `raw_records.json` para `categories_to_map.json`; o Claude preenche o mapa cru→canônico; `build_dataset --category-map` injeta e aplica. Zero import de rede — o "LLM" é o Claude do próprio Claude Code, orquestrado pela skill. Executar DEPOIS do plano de acúmulo de records (ambos tocam `build_dataset`).

**Tech Stack:** Python 3 stdlib, pytest.

## Global Constraints

- **stdlib-only no núcleo:** nenhum import de terceiros; o `category_map` é um `dict` comum, nenhuma chamada de API no código.
- **Testes sem rede:** testes injetam um `category_map` fake — nunca chamam Claude/LLM real.
- **Comportamento default inalterado:** sem `category_map`, `normalize`/`build_dataset` se comportam exatamente como hoje (regressão coberta por teste).
- **Não inventar dados:** categoria crua sem entrada no mapa → `category_canonical=""`, nunca um chute.
- Escrita atômica via `jemscrape.cache.atomic_write`; commits com prefixo convencional + trailer padrão.

---

### Task 1: Campo `category_canonical` no `CanonicalRecord` + CSV

**Files:**
- Modify: `assets/scraper-template/jemscrape/canonical.py` (dataclass, `to_row`, bump `SCHEMA_VERSION`)
- Modify: `assets/scraper-template/jemscrape/export_csv.py` (`CSV_COLUMNS`)
- Test: `assets/scraper-template/tests/test_canonical.py`, `tests/test_export_csv.py`

**Interfaces:**
- Produces: `CanonicalRecord.category_canonical: str = ""` (default vazio, não em `_REQUIRED`). `to_row()` inclui `"category_canonical"`. `CSV_COLUMNS` ganha `"category_canonical"` como **última** coluna (append — não quebra consumidores posicionais das 17 colunas atuais). `SCHEMA_VERSION` → `"1.1"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_canonical.py — adicionar
def test_category_canonical_defaults_empty_and_serializes():
    from jemscrape.canonical import CanonicalRecord, SCHEMA_VERSION
    rec = CanonicalRecord(
        source_site="x", source_url="u", scraped_at="t", authorization_ref="r",
        product_id="P", sku="P", name="N", brand="", description_raw="",
        description_clean="", breadcrumbs=["A", "B"], division="A",
        category_path="A > B", images=[], specs={}, prices=[], list_price=None,
        cost_price=None, variants=[], stock={}, attachments=[], related=[], raw_ref="",
    )
    assert rec.category_canonical == ""
    assert rec.to_row()["category_canonical"] == ""
    assert SCHEMA_VERSION == "1.1"
    rec.category_canonical = "Ferramentas"
    assert rec.to_row()["category_canonical"] == "Ferramentas"
```

```python
# tests/test_export_csv.py — adicionar
def test_csv_has_category_canonical_column():
    from jemscrape.export_csv import CSV_COLUMNS
    assert CSV_COLUMNS[-1] == "category_canonical"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_canonical.py::test_category_canonical_defaults_empty_and_serializes assets/scraper-template/tests/test_export_csv.py::test_csv_has_category_canonical_column -v`
Expected: FAIL (campo/coluna inexistentes; `SCHEMA_VERSION` ainda `"1.0"`).

- [ ] **Step 3: Implement**

Em `canonical.py`: `SCHEMA_VERSION = "1.1"`; adicionar campo ao dataclass (após `category_path`, antes de `images` — mas como há campos sem default depois, colocar `category_canonical` junto dos demais SEM default para não violar a ordem de dataclass; posicioná-lo imediatamente após `category_path`):

```python
    category_path: str
    category_canonical: str
    images: list
```

Em `to_row()`, adicionar dentro do dict retornado:

```python
            "category_canonical": self.category_canonical,
```

Em `export_csv.py`, acrescentar `"category_canonical"` ao fim de `CSV_COLUMNS`.

Nota: como `category_canonical` passa a ser campo posicional sem default, todos os call-sites que constroem `CanonicalRecord` posicionalmente/por-kwarg precisam passá-lo. O único construtor de produção é `normalize()` (Task 2). Os testes que instanciam `CanonicalRecord` diretamente devem passar `category_canonical` — ajustar os existentes em Step 4.

- [ ] **Step 4: Ajustar instanciações existentes + rodar**

Rodar a suíte; onde um teste instanciar `CanonicalRecord` sem `category_canonical`, adicionar o kwarg. `normalize()` será corrigido na Task 2 — se `test_normalize.py` quebrar aqui por falta do campo, é esperado até a Task 2 (pode-se adicionar `category_canonical=""` temporariamente em `normalize` neste step para manter verde, e a Task 2 troca por `_map_category(...)`).

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_canonical.py assets/scraper-template/tests/test_export_csv.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/canonical.py assets/scraper-template/jemscrape/export_csv.py assets/scraper-template/tests/test_canonical.py assets/scraper-template/tests/test_export_csv.py
git commit -m "feat(canonical): add category_canonical field + CSV column, bump schema 1.1

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `normalize` aplica o `category_map`

**Files:**
- Modify: `assets/scraper-template/jemscrape/normalize.py`
- Test: `assets/scraper-template/tests/test_normalize.py`

**Interfaces:**
- Consumes: `CanonicalRecord.category_canonical` (Task 1).
- Produces: `normalize(raw, *, source_site, source_url, scraped_at, authorization_ref, raw_ref, category_map=None)`. `category_map` é `dict[str, str]` com chave = `category_path` cru (o `" > ".join(breadcrumbs)`). `None` ou chave ausente → `category_canonical=""`. Crus (`breadcrumbs`, `category_path`, `division`) sempre preservados.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_normalize.py — adicionar
from jemscrape.normalize import normalize

_BASE = dict(source_site="x", source_url="u", scraped_at="t",
             authorization_ref="r", raw_ref="")


def test_normalize_without_map_is_unchanged():
    rec = normalize({"sku": "P", "name": "N", "breadcrumbs": ["A", "B"]}, **_BASE)
    assert rec.category_path == "A > B"
    assert rec.category_canonical == ""      # default: no map


def test_normalize_applies_category_map():
    m = {"A > B": "Ferramentas/Elétricas"}
    rec = normalize({"sku": "P", "name": "N", "breadcrumbs": ["A", "B"]},
                    category_map=m, **_BASE)
    assert rec.category_canonical == "Ferramentas/Elétricas"
    assert rec.category_path == "A > B"       # raw preserved


def test_normalize_unmapped_category_stays_empty():
    rec = normalize({"sku": "P", "name": "N", "breadcrumbs": ["Z"]},
                    category_map={"A > B": "x"}, **_BASE)
    assert rec.category_canonical == ""
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_normalize.py -k category -v`
Expected: FAIL (`normalize` não aceita `category_map`).

- [ ] **Step 3: Implement**

Em `normalize.py`, adicionar o parâmetro e a lógica:

```python
def normalize(raw, *, source_site, source_url, scraped_at, authorization_ref,
              raw_ref, category_map=None):
    breadcrumbs = list(raw.get("breadcrumbs") or [])
    category_path = " > ".join(breadcrumbs)
    category_canonical = ""
    if category_map:
        category_canonical = category_map.get(category_path, "")
    description_raw = raw.get("description") or raw.get("description_raw") or ""
    rec = CanonicalRecord(
        source_site=source_site,
        source_url=source_url,
        scraped_at=scraped_at,
        authorization_ref=authorization_ref,
        product_id=raw.get("product_id") or raw.get("sku") or "",
        sku=raw.get("sku") or "",
        name=raw.get("name") or "",
        brand=raw.get("brand") or "",
        description_raw=description_raw,
        description_clean=clean_text(description_raw),
        breadcrumbs=breadcrumbs,
        division=raw.get("division") or (breadcrumbs[0] if breadcrumbs else ""),
        category_path=category_path,
        category_canonical=category_canonical,
        images=list(raw.get("images") or []),
        specs=dict(raw.get("specs") or {}),
        prices=list(raw.get("prices") or []),
        list_price=raw.get("list_price"),
        cost_price=raw.get("cost_price"),
        variants=list(raw.get("variants") or []),
        stock=dict(raw.get("stock") or {}),
        attachments=list(raw.get("attachments") or []),
        related=list(raw.get("related") or []),
        raw_ref=raw_ref,
    )
    rec.validate()
    return rec
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_normalize.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/normalize.py assets/scraper-template/tests/test_normalize.py
git commit -m "feat(normalize): optional category_map maps raw breadcrumbs -> canonical category

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Extração de categorias distintas → `categories_to_map.json`

**Files:**
- Create: `assets/scraper-template/jemscrape/categories.py`
- Test: `assets/scraper-template/tests/test_categories.py`

**Interfaces:**
- Produces: `extract_categories(raw_records: list) -> list[dict]` — retorna `[{"category_path": str, "count": int}, ...]`, categorias cruas distintas (o `" > ".join(breadcrumbs)` de cada raw), ordenadas por `count` desc e depois por `category_path` asc. Ignora raws sem breadcrumbs (category_path vazio não entra).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_categories.py
from jemscrape.categories import extract_categories


def test_extract_distinct_with_counts_sorted():
    raws = [
        {"url": "1", "raw": {"breadcrumbs": ["A", "B"]}},
        {"url": "2", "raw": {"breadcrumbs": ["A", "B"]}},
        {"url": "3", "raw": {"breadcrumbs": ["C"]}},
        {"url": "4", "raw": {"breadcrumbs": []}},        # sem categoria → ignorado
    ]
    out = extract_categories(raws)
    assert out == [
        {"category_path": "A > B", "count": 2},
        {"category_path": "C", "count": 1},
    ]


def test_empty():
    assert extract_categories([]) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_categories.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

```python
# jemscrape/categories.py
"""Extract the distinct raw category paths from a scrape's raw_records so the
Claude Code operator (runtime Local, spec §11) can map them to the canonical
JEM taxonomy. Pure stdlib — the mapping itself is done by Claude via the
scrape-normalize-export skill, not by this code."""
from collections import Counter


def extract_categories(raw_records):
    counts = Counter()
    for item in raw_records:
        raw = item.get("raw") if isinstance(item, dict) else None
        if not isinstance(raw, dict):
            continue
        path = " > ".join(raw.get("breadcrumbs") or [])
        if path:
            counts[path] += 1
    return [{"category_path": p, "count": c}
            for p, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_categories.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/jemscrape/categories.py assets/scraper-template/tests/test_categories.py
git commit -m "feat(categories): extract distinct raw category paths for LLM mapping

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `build_dataset --category-map` + subcomando de extração

**Files:**
- Modify: `assets/scraper-template/build_dataset.py`
- Test: `assets/scraper-template/tests/test_build_dataset.py`

**Interfaces:**
- Consumes: `normalize(..., category_map=...)` (Task 2); `extract_categories` (Task 3).
- Produces: `build(..., category_map=None)` propaga o mapa a `normalize`. CLI: novo `--category-map <path>` (opcional; inválido/ilegível quando passado → exit 2, fail-closed pois foi explicitamente pedido). Novo `--extract-categories <out.json>`: lê `--records`, escreve `categories_to_map.json` e retorna 0 sem exportar.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_build_dataset.py — adicionar
import json


def test_build_propagates_category_map(tmp_path):
    import build_dataset
    raws = [{"url": "u", "raw": {"sku": "P", "product_id": "P", "name": "N",
                                 "breadcrumbs": ["A", "B"]}}]
    summary = build_dataset.build(
        raws, source_site="x", authorization_ref="r",
        scraped_at="t", exports_dir=str(tmp_path),
        category_map={"A > B": "Canon/Cat"},
    )
    csv_text = (tmp_path / "products.csv").read_text(encoding="utf-8")
    assert "Canon/Cat" in csv_text


def test_extract_categories_cli(tmp_path):
    import build_dataset
    records = tmp_path / "raw.json"
    records.write_text(json.dumps(
        [{"url": "u", "raw": {"breadcrumbs": ["A", "B"]}}]), encoding="utf-8")
    out = tmp_path / "cats.json"
    rc = build_dataset.main([
        "--records", str(records), "--extract-categories", str(out),
    ])
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data[0]["category_path"] == "A > B"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_build_dataset.py -k "category_map or extract_categories" -v`
Expected: FAIL (`build` não aceita `category_map`; sem `--extract-categories`).

- [ ] **Step 3: Implement**

Em `build`, adicionar `category_map=None` à assinatura e passá-lo a `normalize(..., category_map=category_map)`.

No `main`, adicionar os argumentos e os caminhos:

```python
    parser.add_argument("--category-map", default=None,
                         help="JSON dict {raw category_path: canonical} for LLM-assisted categorization")
    parser.add_argument("--extract-categories", default=None,
                         help="Write distinct raw category paths to this path and exit (no export)")
```

Após ler `raws` (a lista já validada), antes de `build(...)`:

```python
    if args.extract_categories:
        from jemscrape.categories import extract_categories
        from jemscrape.cache import atomic_write
        atomic_write(args.extract_categories,
                     json.dumps(extract_categories(raws), ensure_ascii=False, indent=2))
        print(f"[categories] wrote {args.extract_categories}")
        return 0

    category_map = None
    if args.category_map:
        try:
            category_map = json.loads(Path(args.category_map).read_text(encoding="utf-8"))
            if not isinstance(category_map, dict):
                raise ValueError("category map must be a JSON object")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            print(f"category map not found or invalid: {exc}.", file=sys.stderr)
            return 2
```

E passar `category_map=category_map` na chamada `build(...)`.

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest assets/scraper-template/tests/test_build_dataset.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assets/scraper-template/build_dataset.py assets/scraper-template/tests/test_build_dataset.py
git commit -m "feat(build): --category-map applies LLM map; --extract-categories emits mapping input

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Skill + reference (o passo LLM Local)

**Files:**
- Modify: `skills/scrape-normalize-export/SKILL.md`
- Modify: `references/canonical-record.md` (nova coluna + schema 1.1)
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: os CLIs das Tasks 3-4.

- [ ] **Step 1: Documentar o passo de categorização LLM na skill**

Em `skills/scrape-normalize-export/SKILL.md`, adicionar uma seção "Categorização assistida por LLM (opcional, runtime Local)" descrevendo o fluxo:
1. `python3 build_dataset.py --records state/raw_records.json --extract-categories categories_to_map.json`
2. O Claude (este agente, runtime Local — assinatura, §11) lê `categories_to_map.json` e produz `category_map.json` mapeando cada `category_path` cru para a taxonomia canônica JEM. Categorias sem correspondência confiável ficam de fora (o motor deixa `category_canonical=""`, não inventa).
3. `python3 build_dataset.py --records state/raw_records.json --category-map category_map.json`
Deixar explícito: sem o mapa, a pipeline é 100% determinística; o caminho Actions/Batch (§11) fica para uma fatia futura.

- [ ] **Step 2: Atualizar a reference + schema bump**

Em `references/canonical-record.md`: documentar a coluna `category_canonical` (18ª coluna) e o bump `SCHEMA_VERSION` 1.0 → 1.1, com nota de que consumidores Camada-2 leem esse campo.

- [ ] **Step 3: CHANGELOG**

Nova entrada descrevendo LLM-normalize (infra + categorização, runtime Local).

- [ ] **Step 4: Rodar a suíte completa**

Run: `.venv/bin/python -m pytest -q`
Expected: tudo verde.

- [ ] **Step 5: Commit**

```bash
git add skills/scrape-normalize-export/SKILL.md references/canonical-record.md CHANGELOG.md
git commit -m "docs(normalize): document LLM-assisted categorization (Local) + schema 1.1

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review
- **Spec coverage:** campo+CSV (T1), normalize aplica mapa (T2), extração (T3), CLI wiring (T4), skill+reference (T5) — cobre a Unidade 2.
- **Type consistency:** `category_map: dict[str,str]` chaveado por `category_path` cru em T2/T4; `extract_categories -> [{"category_path","count"}]` em T3/T4; `category_canonical` idêntico em T1/T2.
- **Regressão:** `test_normalize_without_map_is_unchanged` + suíte completa garantem comportamento default preservado.
- **Placeholders:** nenhum.
