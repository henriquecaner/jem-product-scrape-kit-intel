# Design — acúmulo de records + LLM-normalize + run-plan PDF

**Data:** 2026-07-06
**Repo:** `jem-product-scrape-kit-intel`
**Base:** deltas do design canônico `2026-07-01-...-design.md` (rev6/rev7) — §11 (fronteira LLM por runtime) e §12 (`render_pdf`). Este doc fixa o **escopo da primeira fatia** de cada feature; a arquitetura de alto nível já foi decidida e aprovada no spec canônico.

## Escopo

Três unidades independentes, cada uma com seu plano de implementação e ciclo SDD/TDD. Ordem: Unidade 1 primeiro (desbloqueia um scrape real multi-chunk), depois 2 e 3.

Regras invioláveis herdadas do projeto: **stdlib-only no núcleo** (`jemscrape/` + CLIs raiz), Playwright só em `drivers/`, **testes sem rede** (tudo injetado), fail-closed nas cadeias de gate, prosa de usuário em pt-br.

---

## Unidade 1 — Acúmulo de records entre runs encadeados

### Problema
`scrape.py:flush_outputs` (linha 45) grava `data/raw_records.json` a partir de `manifest.records_for_build`, que só enxerga a invocação atual (`manifest.py:28-37`), com **overwrite**. Um scrape chunked (`--limit`) ou por cron entrega **só o último chunk**. O fluxo auth+cron do 3b torna isso o modo normal de operação. Latente desde o Plano 5.

### Solução
1. **Helper puro** `merge_records(existing, new)` em `jemscrape/` (módulo novo `records.py` ou dentro de `manifest.py`):
   - Dedup por `url` (chave de identidade do handoff).
   - Colisão: o registro **mais recente** (de `new`) vence — um re-scrape atualiza preço/estoque.
   - Ordem estável (registros existentes preservam posição; novos entram no fim).
   - Puro, sem I/O — testável isoladamente.
2. **`flush_outputs` mescla antes de gravar:**
   - Lê o `raw_records.json` acumulado existente, se houver.
   - **Fail-open** (deliberado, oposto dos gates): arquivo ausente/ilegível/corrompido → começa de `[]` com aviso em stderr. Nunca aborta — abortar aqui perderia o que acabou de ser scrapeado.
   - `merge_records(existente, records_for_build(...))` → grava atômico.
3. **Persistência no Actions:** mover o arquivo acumulado de `data/raw_records.json` (gitignored) para **`state/raw_records.json`** (versionado, junto do `cursor.json`), para persistir entre cron runs. Ajustar `scrape.py`, `build_dataset` (default `--records`) e `assets/scraper-template/assets/github-actions/scrape.yml` para lerem/commitarem o novo caminho.
4. **Brinde (achado do deep review do motor, mesmo arquivo):** `build_dataset.build` (`build_dataset.py:23-36`) envolve `normalize()` por-item em `try/except`, contabiliza `normalize_errors` no summary e segue — hoje um registro malformado (`ValueError` de `validate()`) mata o export inteiro. Espelha o runner (`runner.py:22`) e o recon (`recon.py:89-96`).
5. **Superfície:** reverter no wizard `scrape-product-catalog/SKILL.md` (passo 3) e onde aplicável a recomendação de "chunk auth runs" — depois do fix, chunking **acumula corretamente**; a prosa passa de implícito-perigoso para explícito-seguro.

### Testes
- `merge_records`: união por URL, colisão (novo vence), ordem estável, entradas vazias.
- `flush_outputs`: arquivo ausente → grava só o atual; arquivo existente → acumula; corrompido → fail-open + aviso; dois chunks encadeados → CSV final tem ambos.
- `build_dataset`: lote com 1 registro malformado no meio → export completa com os válidos + `normalize_errors=1`.

---

## Unidade 2 — LLM-normalize: infra genérica + categorização (runtime Local)

### Princípio de arquitetura
Runtime **Local** = a normalização por LLM roda como **subagents do Claude Code** (assinatura, §11), **não** como código Python chamando API. O código do motor **nunca importa cliente HTTP de LLM** — `stdlib-only` e `testes sem rede` ficam intactos. O "LLM" é o próprio Claude, orquestrado pela skill.

Fluxo (protocolo de intercâmbio via arquivos):
```
raw_records.json ──(CLI extrai categorias distintas)──▶ categories_to_map.json
categories_to_map.json ──(Claude, via skill scrape-normalize-export)──▶ category_map.json
category_map.json ──(build_dataset --category-map, aplica deterministicamente)──▶ dataset
```

### Componentes
1. **`normalize(raw, ..., category_map=None)`** (`normalize.py`):
   - `None` → comportamento atual (`category_path` = breadcrumbs join, `division` = `breadcrumbs[0]`). Zero mudança de comportamento default.
   - `dict` (chave = `category_path` cru; valor = categoria canônica JEM) → preenche o novo campo `category_canonical`. Categoria crua sem entrada no mapa → `category_canonical=""` (não inventa).
   - Os campos crus (`breadcrumbs`, `category_path`, `division`) são **sempre preservados**.
2. **`CanonicalRecord`** (`canonical.py`): novo campo `category_canonical: str = ""`. Adicionar a `to_dict` (via `asdict`, automático) e a `to_row` (nova coluna). Não é campo obrigatório (`_REQUIRED` inalterado).
3. **CSV** (`export_csv.py` + reference): nova coluna `category_canonical` na ordem fixa (append no fim para não quebrar consumidores posicionais — decidir posição no plano, documentar como schema bump se necessário; `SCHEMA_VERSION` 1.0 → 1.1).
4. **Extração de categorias** — helper/CLI (`extract_categories.py` raiz ou subcomando de `build_dataset`): lê um `raw_records.json`, coleta os `category_path`/breadcrumbs crus **distintos** com contagem de ocorrências, grava `categories_to_map.json` (lista ordenada por frequência). Puro + testável.
5. **`build_dataset`**: novo flag `--category-map <path>` (opcional). Ausente → pipeline determinística atual. Presente → carrega o mapa (fail-closed se o arquivo for passado mas inválido) e injeta no `normalize`.
6. **Skill `scrape-normalize-export`**: novo passo opcional documentado — depois de extrair `categories_to_map.json`, o Claude produz `category_map.json` (guiado pela taxonomia canônica JEM em prosa/reference), e então roda `build_dataset --category-map`. Deixar explícito: Local = subagents (assinatura, sem API key); o caminho Actions/Batch (§11) fica para uma fatia futura.

### stdlib-only
Nenhum novo import de terceiros. O `category_map` é um `dict` comum. Testes injetam um mapa fake — sem rede, sem Claude real no teste.

### Testes
- `normalize` com `category_map=None` → idêntico ao atual (regressão).
- `normalize` com mapa → `category_canonical` preenchido; categoria fora do mapa → `""`; crus preservados.
- `extract_categories`: distintas + contagem + ordem por frequência; entrada vazia.
- `build_dataset --category-map`: aplica o mapa; arquivo de mapa inválido → exit 2; sem flag → comportamento inalterado.
- `to_row`/CSV inclui a nova coluna.

---

## Unidade 3 — Run-plan em PDF (§12)

### Componentes
1. **Conversor markdown→HTML mínimo** (`jemscrape/` — stdlib puro): cobre só o subset que o template do run-plan usa (H1/H2, listas, tabelas, negrito, parágrafos). O template é fixo e conhecido (`scrape-run-plan/SKILL.md`), então o conversor não precisa ser um markdown completo. Gera HTML autocontido e estilizado (CSS inline, imprimível). Testável puro.
2. **`drivers/render_pdf.py`** (fora da suíte stdlib, guardado como `playwright_render`):
   - Descobre o Chrome: via Chromium do Playwright, ou binário do sistema.
   - Achou → renderiza o HTML → PDF (`page.pdf()` do Playwright headless).
   - **Não achou → fallback:** grava o HTML (e mantém o Markdown), retorna sinal de "sem PDF, HTML disponível". Aprovação nunca trava por falta de software (§12/§18).
   - Import de Playwright guardado com erro acionável (padrão de `playwright_render.py`).
3. **Skill `scrape-run-plan/SKILL.md`:** remover a nota "PDF é enhancement futuro / não diga que há PDF"; passar a descrever o output em três níveis: Markdown (sempre) → HTML estilizado (sempre, stdlib) → PDF (se Chrome disponível). A camada de aprovação (`.scrape-approval.json` com hash) passa a poder hashear o PDF/HTML gerado.

### stdlib-only
O conversor md→HTML é stdlib puro (fica em `jemscrape/`). O PDF de fato depende de Chrome/Playwright e por isso vive em `drivers/` — nunca no núcleo.

### Testes
- Conversor md→HTML: cada elemento do subset; HTML bem-formado; escape de `<`/`>`/`&` no conteúdo.
- `render_pdf`: guard de import (Playwright ausente → erro acionável); fallback quando Chrome não é descoberto (retorna HTML, não levanta); render real de PDF = skip-if-absent (como o smoke do `playwright_render`).

---

## O que NÃO está no escopo (YAGNI, explícito)
- LLM-normalize no **runtime Actions** (Batch API + `ANTHROPIC_API_KEY`) — só quando houver volume real. §11 já descreve; fica como fatia futura.
- Tiers de LLM além de categorização (extração de atributos, scoring de qualidade) — a infra genérica os suporta, mas não os habilitamos agora.
- Refresh de token automatizado + promoção a VM (deferido pré-existente, inalterado).

## Dependências entre unidades
Nenhuma. As três tocam arquivos majoritariamente disjuntos (1: `scrape.py`/`manifest`/`build_dataset`; 2: `normalize`/`canonical`/`export_csv`/novo CLI; 3: `drivers/`/novo conversor). A Unidade 2 e a 1 tocam `build_dataset` — a 1 vai primeiro, a 2 rebaseia por cima. Podem ser implementadas em sequência sem conflito estrutural.
