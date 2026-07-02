# jem-product-scrape-kit-intel

Plugin do Claude Code da JEM Systems para o time scrapear catálogos de produtos (fornecedores e concorrentes) e normalizar pra loja, com compliance em primeiro lugar. Qualquer pessoa do time usa por um wizard guiado; o motor roda local ou no GitHub Actions.

**Status:** v1 — fundação de scraping (empacotada).

## O que ele faz

- **Gate de compliance fail-closed** — antes de qualquer scrape, valida a autorização (`.scrape-authorization.json`) e a matriz de precedência do `robots.txt`. Concorrente público + robots proíbe = bloqueio duro.
- **Warm-up lap obrigatório** — antes do run cheio, amostra 10–50 produtos e detecta como o site se comporta (render server vs SPA/JS, login/paywall, anti-bot/geo, cobertura de campos). Um review de 2 agentes (Opus 4.8 `xhigh` + advisor Sonnet 5) dá o veredito; só o **verde** libera a largada.
- **Motor resiliente** — fetch 429-aware, pacing humanizado, cache atômico com cursor de retomada.
- **Normalização + export** — registro canônico versionado → `products.csv` (à prova de Excel) + wiki por breadcrumb; dedup de stock/preço/variantes.
- **Caminho browser opcional** — Playwright pra sites SPA/JS (`fetch_mode: browser`), como dependência opcional.
- **Runtime GitHub Actions** — workflow agendado que reconstrói os secrets, roda o gate, faz checkpoint e publica o export como artifact.

## Como usar

1. `/scrape-setup` — primeira vez: checa o toolchain (git, `gh`, Python, Playwright), corrige o PATH do Desktop e gera o kit pra TI se faltar algo.
2. `/scrape-init <url>` — novo projeto: o wizard guiado conduz gate → warm-up → run-plan → run → export, perguntando um passo de cada vez.
3. `/scrape-status` — progresso: cursor de retomada, log diário e (no Actions) o link do artifact.

## Estrutura

- `skills/` — as 6 skills (onboarding, wizard `scrape-product-catalog`, compliance-gate, warm-up, normalize-export, run-plan).
- `commands/` — `/scrape-setup`, `/scrape-init`, `/scrape-status`.
- `agents/scrape-run-auditor.md` — auditoria de cobertura/qualidade pós-scrape.
- `hooks/` — guarda `PreToolUse` (defesa-em-profundidade: barra credencial indo pro git).
- `assets/scraper-template/` — o motor (Python 3 stdlib), scaffoldado por projeto.
- `references/` — decisões de runtime, canonical record, anti-ban, geo-proxy, estimativa.
- `docs/superpowers/` — o design (spec) e os planos de implementação.

## Desenvolvimento

```bash
python3 -m venv .venv && .venv/bin/python -m pip install pytest
.venv/bin/python -m pytest -q     # motor: 194 passando (+1 skip: smoke Playwright)
```

O núcleo do motor é Python 3 stdlib-only; Playwright é dependência opcional, só no caminho browser.

## Escopo

**Nesta v1:** scraping público (local + Actions), warm-up, normalize/export, onboarding. **Deferido:** scraping autenticado + ciclo de token (Plano 3b), normalização assistida por LLM (Batch API), render do run-plan em PDF.

Repositório interno JEM Systems. UNLICENSED.
