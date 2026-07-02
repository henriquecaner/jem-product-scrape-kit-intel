# HANDOFF — jem-product-scrape-kit-intel

Estado do trabalho para retomar em outro terminal/sessão sem perder contexto.

**Repo:** `github.com/henriquecaner/jem-product-scrape-kit-intel` (privado). Branch de trabalho: `main` (tudo mergeado e pushado).
**Data do handoff:** 2026-07-01.

## Onde estamos

Plugin do Claude Code para scraping de catálogos JEM. **Planos 1, 2 e 4 completos, na `main`, pushados. 134 testes passando.** (Plano 3 — auth/browser — ainda não.)

- **Plano 1 — Motor de scraping** ✅ (mergeado). `assets/scraper-template/jemscrape/`: `config.py` (validação + piso de rate-limit), `authz.py` (gate de autorização em runtime, fail-closed, matriz robots §10.2), `pacing.py` (anti-ban + coffee breaks), `fetch.py` (resiliente, 429-aware, opener injetável), `cache.py` (escrita atômica + `Cursor` de resume, slug injetivo com hash), `manifest.py` (schema_version), `runner.py` (resumível). Template-root: `scrape.py` (CLI + preflight gate), `smoke_test.py`, `config.json.example`.
- **Plano 2 — Normalize + export** ✅ (mergeado). `jemscrape/`: `canonical.py` (`CanonicalRecord`, `SCHEMA_VERSION`, `to_row`), `normalize.py` (`clean_text` unescape-antes-de-strip, mapeamento), `dedup.py` (`collapse_stock` hub-max, `pick_price` por banda, `collapse_variants`), `export_csv.py` (colunas estáveis, `lineterminator="\n"`), `export_wiki.py` (dirs por breadcrumb + INDEX, **endurecido contra path-traversal**). Template-root: `build_dataset.py` (orquestrador + CLI).
- **Plano 4 — Warm-Up Lap** ✅ (mergeado, head `3477421`). `jemscrape/`: `fetch.py` `probe()` (status/headers/body sem levantar em 4xx/5xx), `signals.py` (4 detectores: `detect_render` server-vs-SPA, `detect_auth` login/paywall, `detect_antibot` 429/Cloudflare/geo — **corrigido: cf-ray não é sinal de block; markers de body só em não-200**, `analyze_shape` cobertura/bandas/colisões), `recon.py` (`run_warmup` DI + `WarmupReport` + checklist, parse resiliente com `parse_errors`), `warmup_gate.py` (veredito fail-closed, espelha authz). Template-root: `warmup.py` (CLI: gate de compliance → sample → recon). `scrape.py` recusa run full sem veredito VERDE (`require_warmup`). Review de 2 agentes (Opus 4.8 xhigh + Sonnet 5) que produz `.scrape-warmup.json` = job da skill `scrape-warmup` (Plano 6/empacotamento).

Design de referência: `docs/superpowers/specs/2026-07-01-jem-product-scrape-kit-intel-design.md` (rev3, §9.1).
Planos: `.../2026-07-01-scraper-engine-core.md` (1), `...-normalize-export.md` (2), `2026-07-02-warmup-lap.md` (4).

## Rodar os testes

```bash
cd <repo>
.venv/bin/python -m pytest -q     # 134 passando
```
O `.venv/` é gitignored (PEP 668 na system Python). Num clone novo: `python3 -m venv .venv && .venv/bin/python -m pip install pytest`.

## Pendências (loose ends)

**Todas as 3 do Plano 2 fechadas em `78bfa1a` (2026-07-02). Suíte: 97 testes passando.**

1. ~~Review de branch inteira do Plano 2~~ ✅ rodado (Opus): sem Critical; 3 Important corrigidos com TDD (main() robusto + testado; coerção em `collapse_stock`/`pick_price`; anti-CSV-injection no `write_csv`) + 2 F401.
2. ~~Review por-task da Task 6~~ ✅ coberto pelo review de branch inteira; `cfg["target_domain"]` e `main()` sem teste resolvidos.
3. ~~Doc divergente do `export_wiki`~~ ✅ `plans/...-normalize-export.md` Task 5 sincronizado com o código endurecido (`safe_name` `_DOTS_ONLY` + `write_wiki` containment).

## Roadmap restante (não começados)

3. **Auth + browser adapter** — Playwright `storage_state`, ciclo de token (spec §5.1). **Desbloqueia sites SPA/JS (ADI) + o caminho browser do warm-up.**
4. ✅ **Warm-Up Lap** — FEITO (mergeado, head `3477421`). Código Python + gate no runtime. Falta só a skill `scrape-warmup` que orquestra o review de 2 agentes e escreve `.scrape-warmup.json` (vai junto do empacotamento, #7).
5. **Runtime GitHub Actions** — workflow + `gh` + secret + checkpoint + artifact.
6. **Onboarding** — skill `scrape-onboarding` + toolchain + kit pra TI + drivers.
7. **Empacotamento do plugin** — `plugin.json`, SKILL.md, commands, references, agents (incl. `scrape-warmup`), hooks.json.

> Renumeração: o warm-up entrou como Plano 4, empurrando Actions→5, Onboarding→6, Packaging→7. A nota de traceability do doc do Plano 1 foi atualizada pra bater (sem drift).

**Motivação do #4 (warm-up):** na sessão 2026-07-02, testando ADI (`adiglobaldistribution.us`), descobrimos SPA/JS-only + muro de login **só na tentativa** — o gate de compliance passou (robots permite `/Catalog/`+`/Product/`), mas fetch estático volta vazio. O warm-up teria cuspido isso antes de gastar o run.

## Processo e convenções

- **SDD (subagent-driven-development):** por task → implementer (TDD) → review spec+qualidade → fix loop → ledger. Ledger em `.superpowers/sdd/progress.md` (**scratch gitignored — só sobrevive na mesma máquina**; `git log` é a fonte durável).
- **Política de modelo (memória):** nunca Haiku; tier econômico Sonnet 5 medium; Opus xhigh para auditoria. Ver `~/.claude/.../memory/no-haiku-use-sonnet5.md`.
- Commits terminam com o trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Runtime = Python 3 stdlib only (Playwright é dep opcional do caminho auth, Plano 3).

## Como retomar

- **Mesma máquina, outro terminal:** `cd <repo>` e resuma a conversa do Claude Code (ver comando confirmado na resposta do chat).
- **Outra máquina:** clone o repo; este HANDOFF + `git log` + os planos reconstroem o estado. O ledger `.superpowers/sdd/` não vem no clone (gitignored).
