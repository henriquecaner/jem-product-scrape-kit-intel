# HANDOFF — jem-product-scrape-kit-intel

Estado do trabalho para retomar em outro terminal/sessão sem perder contexto.

**Repo:** `github.com/henriquecaner/jem-product-scrape-kit-intel` (privado). Branch de trabalho: `main` (tudo mergeado e pushado).
**Data do handoff:** 2026-07-01.

## Onde estamos

Plugin do Claude Code para scraping de catálogos JEM. Plano geral em 6 planos; **Planos 1 e 2 completos, na `main`, pushados. 88 testes passando.**

- **Plano 1 — Motor de scraping** ✅ (mergeado). `assets/scraper-template/jemscrape/`: `config.py` (validação + piso de rate-limit), `authz.py` (gate de autorização em runtime, fail-closed, matriz robots §10.2), `pacing.py` (anti-ban + coffee breaks), `fetch.py` (resiliente, 429-aware, opener injetável), `cache.py` (escrita atômica + `Cursor` de resume, slug injetivo com hash), `manifest.py` (schema_version), `runner.py` (resumível). Template-root: `scrape.py` (CLI + preflight gate), `smoke_test.py`, `config.json.example`.
- **Plano 2 — Normalize + export** ✅ (mergeado). `jemscrape/`: `canonical.py` (`CanonicalRecord`, `SCHEMA_VERSION`, `to_row`), `normalize.py` (`clean_text` unescape-antes-de-strip, mapeamento), `dedup.py` (`collapse_stock` hub-max, `pick_price` por banda, `collapse_variants`), `export_csv.py` (colunas estáveis, `lineterminator="\n"`), `export_wiki.py` (dirs por breadcrumb + INDEX, **endurecido contra path-traversal**). Template-root: `build_dataset.py` (orquestrador + CLI).

Design de referência: `docs/superpowers/specs/2026-07-01-jem-product-scrape-kit-intel-design.md` (rev2).
Planos: `docs/superpowers/plans/2026-07-01-scraper-engine-core.md` (1) e `...-normalize-export.md` (2).

## Rodar os testes

```bash
cd <repo>
.venv/bin/python -m pytest -q     # 88 passando
```
O `.venv/` é gitignored (PEP 668 na system Python). Num clone novo: `python3 -m venv .venv && .venv/bin/python -m pip install pytest`.

## Pendências (loose ends)

1. **Review de branch inteira do Plano 2** — foi PULADO num push direto. No Plano 1 esse review holístico pegou um Critical (colisão de slug) que os reviews por-task não viram, então vale rodar sobre a `main`.
2. **Review por-task da Task 6** (`build_dataset`) — pulado. Concerns leves: `cfg["target_domain"]` é subscript direto; `main()` CLI sem teste (per brief).
3. **Doc divergente:** `plans/...-normalize-export.md` Task 5 (`export_wiki`) ainda mostra o código-exemplo pré-endurecimento (vulnerável a traversal). O **código shipado está correto/endurecido** — só o exemplo do doc diverge; sincronizar.

## Roadmap restante (Planos 3–6, não começados)

3. **Auth + browser adapter** — Playwright `storage_state`, ciclo de token (spec §5.1).
4. **Runtime GitHub Actions** — workflow + `gh` + secret + checkpoint + artifact.
5. **Onboarding** — skill `scrape-onboarding` + toolchain + kit pra TI + drivers.
6. **Empacotamento do plugin** — `plugin.json`, SKILL.md, commands, references, agent, hooks.json.

## Processo e convenções

- **SDD (subagent-driven-development):** por task → implementer (TDD) → review spec+qualidade → fix loop → ledger. Ledger em `.superpowers/sdd/progress.md` (**scratch gitignored — só sobrevive na mesma máquina**; `git log` é a fonte durável).
- **Política de modelo (memória):** nunca Haiku; tier econômico Sonnet 5 medium; Opus xhigh para auditoria. Ver `~/.claude/.../memory/no-haiku-use-sonnet5.md`.
- Commits terminam com o trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Runtime = Python 3 stdlib only (Playwright é dep opcional do caminho auth, Plano 3).

## Como retomar

- **Mesma máquina, outro terminal:** `cd <repo>` e resuma a conversa do Claude Code (ver comando confirmado na resposta do chat).
- **Outra máquina:** clone o repo; este HANDOFF + `git log` + os planos reconstroem o estado. O ledger `.superpowers/sdd/` não vem no clone (gitignored).
