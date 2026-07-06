# Changelog

## Unreleased

### Fix — acúmulo de records entre runs encadeados (Plano 2c / Unidade 1)

Resolve o follow-up de alta prioridade registrado na 0.2.0: `raw_records.json`/`products.csv` eram sobrescritos a cada run, então um scrape encadeado por chunks (`--limit`) ou cron acumulava só o último chunk.

- `jemscrape/records.py` (novo) — `merge_records(existing, new)`: união por `url`, o mais recente vence, mantendo posição; entradas malformadas são ignoradas.
- `scrape.py:flush_outputs` — passa a ler/mesclar/gravar em `state/raw_records.json` (versionado, persiste no Actions) em vez de sobrescrever em `data/`; fail-open (arquivo acumulado ausente/corrompido começa vazio + aviso, nunca aborta).
- `build_dataset.build` — resiliente por-registro: um record que falha `normalize()`/`validate()` é contado em `normalize_errors` e pulado, sem abortar o lote inteiro.
- `assets/github-actions/scrape.yml` — `build_dataset.py --records state/raw_records.json` (era `data/raw_records.json`).
- Wizard (`scrape-product-catalog/SKILL.md`): documenta que chunking de runs autenticados agora é seguro e recomendado, sem perder chunks anteriores.

### Feat — categorização assistida por LLM (Plano 2c / Unidade 2, runtime Local)

Normalização determinística ganha um passo opcional de categorização: o motor nunca chama um LLM, mas passa a aplicar um mapa cru→canônico que o Claude (via skill, runtime Local) produz fora do código.

- `jemscrape/canonical.py` — novo campo `CanonicalRecord.category_canonical: str` (default `""`, sem chute quando a categoria crua não está no mapa); `SCHEMA_VERSION` 1.0 → 1.1.
- `jemscrape/export_csv.py` — `CSV_COLUMNS` ganha `category_canonical` como 18ª coluna (append no fim; não quebra consumidores posicionais das 17 colunas do schema 1.0).
- `jemscrape/normalize.py` — parâmetro opcional `normalize(..., category_map=None)`: aplica `category_map.get(category_path, "")`; sem mapa, comportamento idêntico ao anterior (coberto por teste de regressão).
- `jemscrape/categories.py` (novo) — `extract_categories(raw_records)`: categorias cruas distintas com contagem, ordenadas por frequência, para o Claude mapear.
- `build_dataset.py` — `--extract-categories <out.json>` escreve as categorias distintas e sai sem exportar (não exige `--config`); `--category-map <path>` aplica o mapa no build; caminho inválido/ilegível quando explicitamente pedido → exit 2 (fail-closed).
- `skills/scrape-normalize-export/SKILL.md` + `references/canonical-record.md` documentam o fluxo extract → mapear (Claude, runtime Local) → aplicar, e o schema 1.1.

### Feat — run-plan em PDF (Plano 2c / Unidade 3)

O run-plan (Markdown) agora também renderiza em HTML e PDF, para a etapa de aprovação nunca travar por falta de software.

- `jemscrape/md_to_html.py` (novo) — conversor Markdown→HTML mínimo, stdlib puro, cobrindo o subset do template do run-plan (H1/H2, listas, tabelas GFM, negrito, parágrafos); escapa `<`/`>`/`&` do conteúdo.
- `drivers/render_pdf.py` (novo) — descobre o Chrome via Playwright e imprime o HTML em PDF; sem Chrome, grava só o HTML e retorna `pdf: None` (nunca levanta).
- `render_run_plan.py` (novo, CLI raiz) — `python3 render_run_plan.py --markdown docs/run-plan.md --out docs`.
- `skills/scrape-run-plan/SKILL.md` documenta os três níveis de output (Markdown sempre, HTML sempre, PDF quando o Chrome está disponível).

## 0.2.0

### Plano 3b — sessão autenticada + geo no GitHub Actions

Ponte entre a captura de sessão local e um run autenticado, geo-roteado e não supervisionado no Actions (spec §5.1). Ativado por `auth_required: true` no `config.json`.

- `jemscrape/session.py` — parse do `storage_state` do Playwright: header `Cookie` para o caminho HTTP (domain-match RFC 6265), `storage_state` cru para o caminho browser, e validade do token (distinta do progresso, que segue no cursor).
- `jemscrape/proxy.py` — traduz `HTTPS_PROXY` no dict de launch do Playwright (o caminho HTTP honra o env var via urllib; o browser exige o proxy no launch).
- Fail-closed em token morto — `AuthExpiredError` em 401/403 no caminho HTTP (`fetch`) e no browser (`make_browser_fetcher`), sem retry; o runner propaga (não marca a URL como done), e o `scrape.py` faz flush dos records já coletados, alerta via `notify.py` e sai non-zero.
- Preflight de sessão fail-closed em `scrape.py` e `warmup.py` (sessão ausente/expirada → exit 2, antes de qualquer fetch); warm-up autenticado valida a sessão antes do run cheio.
- `drivers/auth_capture.py` + CLI `auth_capture.py` — captura headed local (proxy do país no launch), grava `.scrape-session.json` em 0600, imprime a validade e o comando `gh secret set`; nunca faz push automático.
- Secret `SCRAPE_STORAGE_STATE` condicional (só quando `auth_required`) em `actions_setup.py`/`deploy_actions.py`/`scrape.yml`; empurrado por stdin, nunca argv.
- Blindagem do segredo: `.scrape-session.json` no `.gitignore` do skeleton e no hook `precheck.py`.
- `config.json` valida `auth_required`/`login_url`; `references/auth-session.md` documenta o ritual de refresh e o gatilho de promoção a VM.

**Follow-up conhecido (fora do escopo 3b, pré-existente do Plano 5):** o `raw_records.json` e o `products.csv` são sobrescritos a cada run (manifest só da invocação atual), então um scrape encadeado por chunks/cron acumula só o último chunk. Latente desde o `--limit`+cron; o fluxo auth+cron do 3b torna isso o modo normal. Precisa ser resolvido (merge/append em `build_dataset`) antes de rodar auth contra um catálogo maior que um chunk.

### Endurecimento (deep review)

Varredura de review (4 revisores) sobre o 3b e o motor, com correções TDD (suíte 204 → 263 → 300 passando, +1 skip):

- **Segurança:** `proxy.py` não ecoa mais a URL do proxy num erro (vazava `user:pass` no log do Actions); credenciais percent-decoded; host IPv6 corrigido. `auth_capture.py` grava a sessão com umask 0600 (sem janela legível). `secrets_io.py` ganha `O_NOFOLLOW` + `fchmod` antes do write (fecha symlink e a janela de perms). `precheck.py` fecha bypasses do hook (`git -C/-c add`, remoção de aspas, caixa).
- **Correção:** `session.is_expired` só considera a sessão morta quando todos os cookies persistentes expiraram (antes um cookie incidental bloqueava um login válido). `authz`/`warmup_gate` aceitam o sufixo `Z` em datas (rejeitavam gate legítimo em Python <3.11). O warm-up avisa quando extrai 0 produtos (evita falso "verde"). `detect_auth` não falso-positiva com form de login no header; `detect_antibot` pega a redação atual do Cloudflare. `scrape.yml` distingue "nada a commitar" de falha real no checkpoint.
- **Robustez:** guards contra `prices[0]` não-dict, `records` não-lista, config com tipos errados, PATH vazio, slug de cache longo demais; dedup de cookies same-name.

## 0.1.0

First packaged release of `jem-product-scrape-kit-intel` — a compliance-first product-scraping kit for the JEM team.

**Engine (Python 3, stdlib-only core):**
- Compliance gate — fail-closed runtime authorization (`.scrape-authorization.json`) with the robots.txt precedence matrix.
- Resilient fetch (429-aware), humanized pacing, atomic cache with a resumable cursor.
- Normalize → canonical record → CSV + wiki exports; dedup (hub-stock, price-band, variants).
- Warm-up lap (mandatory) — samples a site and detects render mode (server vs SPA/JS), auth/paywall, anti-bot/geo, and parse-shape; a fail-closed verdict gate refuses the full run without a green light.
- Browser render adapter — optional Playwright path for SPA/JS sites (`fetch_mode: browser`); Playwright stays an optional dependency in `drivers/`.
- GitHub Actions runtime — workflow template that reconstructs gate secrets, enforces the gate, checkpoints, and uploads the exports artifact.
- Onboarding — toolchain green check, IT install kit, Desktop PATH fix, and the Actions deploy helper.
- Site adapter template — `site_adapter.py.example` documents the per-site contract (`discover`/`parse`) and fails loud if copied unimplemented; `config.json.example` ships every key the pipeline reads (`fetch_mode`, `band_priority`, `hub_group`, `ireland_branch`).
- Warm-up checklist points the anti-bot/geo mitigation at the country proxy on the Actions runtime (VM promotion is deferred with Plano 3b).

**Plugin:**
- Skills: `scrape-onboarding`, `scrape-product-catalog` (guided wizard), `scrape-compliance-gate`, `scrape-warmup`, `scrape-normalize-export`, `scrape-run-plan`.
- Commands: `/scrape-setup`, `/scrape-init`, `/scrape-status`.
- Agent: `scrape-run-auditor`. Hooks: `PreToolUse` credential-to-git guard (defense-in-depth).

**Deferred:** authenticated scraping + token lifecycle (Plano 3b); LLM-assisted normalization via Batch API; PDF rendering of the run-plan.
