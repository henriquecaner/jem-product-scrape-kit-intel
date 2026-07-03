# HANDOFF — jem-product-scrape-kit-intel

Estado do trabalho para retomar em outro terminal/sessão sem perder contexto.

**Repo:** `github.com/henriquecaner/jem-product-scrape-kit-intel` (privado). Branch de trabalho: `main` (tudo mergeado e pushado).
**Data do handoff:** 2026-07-01.

## Onde estamos

Plugin do Claude Code para scraping de catálogos JEM. **PROJETO v1 COMPLETO — Planos 1, 2, 4, 3a, 5, 6 e 7 na `main`, pushados. Plugin instalável + documentado. 197 testes passando (+1 skip: smoke Playwright).** Único item deferido: **Plano 3b — auth/token** (usuário sem login; ver §5.1). Design em rev7.

## Pré-distribuição (2026-07-02)
Preparado pra distribuir amanhã. Feito: **C — handoff scrape→export fiado** (`Manifest.records_for_build` + `scrape.py` grava `data/raw_records.json`, commit `0d2c98e`); **B — distribuição** (`.claude-plugin/marketplace.json` + `scripts/build-plugin-zip.sh` → `dist/*.zip`; SETUP.md com os 2 métodos; commit `7d77f6f`). Docs de usuário: OVERVIEW, SETUP, GETTING-STARTED, GLOSSARY, FOR-APPROVERS, DEVELOPING.
**Pendente (do usuário, precisa de máquina real):** **A — smoke de instalação**: instalar o plugin num Claude Code de verdade e confirmar que as 6 skills + 3 commands carregam e um `/scrape-setup` roda (o plugin-validator valida estrutura, não runtime). **Caveat:** nenhum scrape rodou ponta-a-ponta de verdade (tudo testado com fakes) — vale um run real numa fixture/site público permitido, que precisa de um `site_adapter` (o wizard cria).

- **Plano 1 — Motor de scraping** ✅ (mergeado). `assets/scraper-template/jemscrape/`: `config.py` (validação + piso de rate-limit), `authz.py` (gate de autorização em runtime, fail-closed, matriz robots §10.2), `pacing.py` (anti-ban + coffee breaks), `fetch.py` (resiliente, 429-aware, opener injetável), `cache.py` (escrita atômica + `Cursor` de resume, slug injetivo com hash), `manifest.py` (schema_version), `runner.py` (resumível). Template-root: `scrape.py` (CLI + preflight gate), `smoke_test.py`, `config.json.example`.
- **Plano 2 — Normalize + export** ✅ (mergeado). `jemscrape/`: `canonical.py` (`CanonicalRecord`, `SCHEMA_VERSION`, `to_row`), `normalize.py` (`clean_text` unescape-antes-de-strip, mapeamento), `dedup.py` (`collapse_stock` hub-max, `pick_price` por banda, `collapse_variants`), `export_csv.py` (colunas estáveis, `lineterminator="\n"`), `export_wiki.py` (dirs por breadcrumb + INDEX, **endurecido contra path-traversal**). Template-root: `build_dataset.py` (orquestrador + CLI).
- **Plano 4 — Warm-Up Lap** ✅ (mergeado, head `3477421`). `jemscrape/`: `fetch.py` `probe()` (status/headers/body sem levantar em 4xx/5xx), `signals.py` (4 detectores: `detect_render` server-vs-SPA, `detect_auth` login/paywall, `detect_antibot` 429/Cloudflare/geo — **corrigido: cf-ray não é sinal de block; markers de body só em não-200**, `analyze_shape` cobertura/bandas/colisões), `recon.py` (`run_warmup` DI + `WarmupReport` + checklist, parse resiliente com `parse_errors`), `warmup_gate.py` (veredito fail-closed, espelha authz). Template-root: `warmup.py` (CLI: gate de compliance → sample → recon). `scrape.py` recusa run full sem veredito VERDE (`require_warmup`). Review de 2 agentes (Opus 4.8 xhigh + Sonnet 5) que produz `.scrape-warmup.json` = job da skill `scrape-warmup` (Plano 6/empacotamento).

- **Plano 3a — Browser render adapter** ✅ (mergeado, head `d796b8f`). `jemscrape/browser.py` (`RenderedResult` + `make_browser_fetcher`/`make_browser_probe`, adapters puros stdlib que convertem `render_fn(url)->RenderedResult` nos contratos do motor; falha de render vira `FetchError`). `drivers/playwright_render.py` (**única** importação de Playwright, guardada + erro acionável; fora da suíte stdlib — guard testado, render real skip-if-absent; `render()` honra `user_agent`). `config.py` valida `fetch_mode` {http,browser}. `warmup.py --render` e `scrape.build_fetcher` selecionam browser vs http (import lazy do driver). **Fix do review:** `detect_antibot` agora pega desafio Cloudflare renderizado em 200 (markers CF challenge-specific, gate de status removido) + modo browser honra `user_agent`. Playwright = 1ª dep opcional (só no driver). **3b (auth/token, §5.1) deferido** — usuário sem login.

- **Plano 5 — Runtime GitHub Actions** ✅ (mergeado, head `87e71ad`). `jemscrape/secrets_io.py` (`materialize_secret` — reconstrói arquivo de gate a partir de env/secret, fail-closed, criado já 0600 via `os.open`, chmod propaga). Template-root: `actions_setup.py` (materializa `.scrape-authorization.json` + `.scrape-warmup.json` dos secrets antes de qualquer scrape — fail-closed exit 2), `notify.py` (anotação GitHub `::error::`/`::warning::`, escapa newline anti-spoof). `assets/github-actions/scrape.yml` (template: `workflow_dispatch`+cron → materialize → gate `smoke_test.py` → `scrape.py --limit` → `build_dataset.py` → checkpoint commit `state/`+`exports/` (rebase antes de push; push falho → notify + `exit 1`) → `upload-artifact` → `notify.py` on failure). Cadeia fail-closed intacta ponta-a-ponta (materialize → smoke gate → `require_warmup` do scrape.py). Batch/API = hook futuro (normalize v1 é determinística). Deploy automatizado (`gh secret set`) = Plano 6.

- **Plano 6 — Onboarding** ✅ (mergeado, head `564055b`). `jemscrape/toolchain.py` (`check_tools` green-check: git/gh/python3 required, playwright optional; `render_it_kit` → comandos winget das ferramentas que faltam). `jemscrape/settings_patch.py` (`patch_claude_settings` — mescla PATH/env no `~/.claude/settings.json` sem clobber, tolera corrupto/non-dict, atômico). Template-root: `scrape_setup.py` (CLI `/scrape-setup`: green-check + fix de PATH + gate de readiness, exit 0 pronto / 1 falta required). Assets: `assets/project-skeleton/.gitignore` (bloqueia cache **`/data/` ancorado** + gate files + secrets; NÃO ignora exports/state/wiki — **fix do review: `/data/` ancorado evita dropar `exports/wiki/data/...`**), `assets/it-request/README.md` (kit pra TI: winget + proxy + API key). `drivers/deploy_actions.py` (`build_secret_commands` → `gh secret set` com segredo via stdin, nunca argv — fecha o deploy adiado do Plano 5). **Skill markdown + commands → Plano 7.**

Design de referência: `docs/superpowers/specs/2026-07-01-jem-product-scrape-kit-intel-design.md` (rev6; §9.1 warm-up, §5.2 browser, §5.3 Actions, §6.1 onboarding).
Planos: `.../scraper-engine-core.md` (1), `...normalize-export.md` (2), `...warmup-lap.md` (4), `...browser-render-adapter.md` (3a), `...actions-runtime.md` (5), `2026-07-02-onboarding.md` (6).

## Rodar os testes

```bash
cd <repo>
.venv/bin/python -m pytest -q     # 187 passando (+1 skip: smoke Playwright)
```
O `.venv/` é gitignored (PEP 668 na system Python). Num clone novo: `python3 -m venv .venv && .venv/bin/python -m pip install pytest`.

## Pendências (loose ends)

**Todas as 3 do Plano 2 fechadas em `78bfa1a` (2026-07-02). Suíte: 97 testes passando.**

1. ~~Review de branch inteira do Plano 2~~ ✅ rodado (Opus): sem Critical; 3 Important corrigidos com TDD (main() robusto + testado; coerção em `collapse_stock`/`pick_price`; anti-CSV-injection no `write_csv`) + 2 F401.
2. ~~Review por-task da Task 6~~ ✅ coberto pelo review de branch inteira; `cfg["target_domain"]` e `main()` sem teste resolvidos.
3. ~~Doc divergente do `export_wiki`~~ ✅ `plans/...-normalize-export.md` Task 5 sincronizado com o código endurecido (`safe_name` `_DOTS_ONLY` + `write_wiki` containment).

## Roadmap restante (não começados)

3a. ✅ **Browser render adapter** — FEITO (mergeado, head `d796b8f`). Playwright renderiza SPA/JS público; fecha o caminho browser do warm-up (`warmup.py --render browser`) e do scrape (`fetch_mode: browser`).
3b. **Auth + token (deferido, YAGNI)** — captura de sessão via Playwright `storage_state`, ciclo de token, `gh secret`, refresh diário, promoção a VM (spec §5.1). Só quando houver alvo logado — usuário não tem login hoje.
4. ✅ **Warm-Up Lap** — FEITO (mergeado, head `3477421`). Código Python + gate no runtime. Falta só a skill `scrape-warmup` que orquestra o review de 2 agentes e escreve `.scrape-warmup.json` (vai junto do empacotamento, #7).
5. ✅ **Runtime GitHub Actions** — FEITO (mergeado, head `87e71ad`). Workflow template + `secrets_io`/`actions_setup`/`notify` + gate no runtime + secrets→arquivos. Falta o **deploy automatizado** (`gh secret set` + push do workflow via API) que é da skill/driver de onboarding (#6).
6. ✅ **Onboarding** — FEITO (mergeado, head `564055b`). Núcleo testável (green-check + kit-TI + fix de PATH + CLI `scrape_setup`) + assets (scaffold `.gitignore` **com `/data/` ancorado**, kit-TI) + `deploy_actions` (gh-secret builder). Blocker do Plano 5 (scaffold `.gitignore`) FECHADO. Skill markdown + commands → Plano 7.
7. ✅ **Empacotamento do plugin** — FEITO (mergeado, head `7102681`). `.claude-plugin/plugin.json` + 6 skills (wizard guiado) + 3 commands + agent `scrape-run-auditor` + `hooks/` (guarda credencial-pro-git, 7 testes) + 7 references + README/CHANGELOG. Validado: `plugin-dev:plugin-validator` PASS (0 crítico); `plugin-dev:skill-reviewer` — 2 must-fix de grounding corrigidos (regra own_account+robots; overclaim do deploy_actions/cron) + references linkadas. **Plugin instalável.**

## Deferido (único item aberto)
- **Plano 3b — Auth + token** (§5.1): captura de sessão Playwright `storage_state`, ciclo de token, `gh secret`, refresh diário, promoção a VM. Só quando existir alvo logado (o usuário não tem login hoje). Ao construir, fiar o executor do `deploy_actions` mantendo o segredo no stdin do subprocess (ler `stdin_file`), nunca no argv.

> Numeração: warm-up = Plano 4 (Actions→5, Onboarding→6, Packaging→7; traceability do Plano 1 já bate). Plano 3 dividido em 3a (feito) e 3b (deferido), spec rev4 §5.2.

**Motivação do #4 (warm-up):** na sessão 2026-07-02, testando ADI (`adiglobaldistribution.us`), descobrimos SPA/JS-only + muro de login **só na tentativa** — o gate de compliance passou (robots permite `/Catalog/`+`/Product/`), mas fetch estático volta vazio. O warm-up teria cuspido isso antes de gastar o run.

## Processo e convenções

- **SDD (subagent-driven-development):** por task → implementer (TDD) → review spec+qualidade → fix loop → ledger. Ledger em `.superpowers/sdd/progress.md` (**scratch gitignored — só sobrevive na mesma máquina**; `git log` é a fonte durável).
- **Política de modelo (memória):** nunca Haiku; tier econômico Sonnet 5 medium; Opus xhigh para auditoria. Ver `~/.claude/.../memory/no-haiku-use-sonnet5.md`.
- Commits terminam com o trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Runtime = Python 3 stdlib only (Playwright é dep opcional do caminho auth, Plano 3).

## Como retomar

- **Mesma máquina, outro terminal:** `cd <repo>` e resuma a conversa do Claude Code (ver comando confirmado na resposta do chat).
- **Outra máquina:** clone o repo; este HANDOFF + `git log` + os planos reconstroem o estado. O ledger `.superpowers/sdd/` não vem no clone (gitignored).
