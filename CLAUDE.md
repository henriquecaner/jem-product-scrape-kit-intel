# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## O que é este repositório

Plugin do Claude Code (`jem-product-scrape-kit-intel`) da JEM Systems: kit compliance-first para scraping de catálogos de produtos. O repositório É o plugin — não há aplicação rodando aqui. O motor de scraping vive em `assets/scraper-template/` e é scaffoldado nos projetos dos usuários pelo wizard; `skills/`, `commands/`, `agents/` e `hooks/` são a superfície que o Claude Code carrega.

Estado canônico do projeto: `docs/superpowers/HANDOFF.md` (v1 completa + Plano 3b — auth/token + geo — mergeado 2026-07-03; sem itens do roadmap deferidos). Design em `docs/superpowers/specs/`, planos de implementação em `docs/superpowers/plans/`. Deferidos abertos: normalização assistida por LLM, run-plan em PDF, refresh automático de token + promoção a VM, e o follow-up de acúmulo de records entre runs encadeados (ver HANDOFF).

## Comandos

```bash
# Setup (uma vez; .venv é gitignored — PEP 668 na system Python)
python3 -m venv .venv && .venv/bin/python -m pip install pytest

# Suíte completa (326 passando + 2 skip: smokes Playwright quando ausente)
.venv/bin/python -m pytest -q

# Um arquivo ou um teste específico
.venv/bin/python -m pytest assets/scraper-template/tests/test_fetch.py -q
.venv/bin/python -m pytest -k nome_do_teste -q

# Build do zip distribuível (→ dist/, gitignored; lê a versão de .claude-plugin/plugin.json)
scripts/build-plugin-zip.sh
```

Rode o pytest da raiz do repo: `pyproject.toml` aponta `testpaths`/`pythonpath` para `assets/scraper-template`. Para validar a estrutura do plugin, use o agente `plugin-dev:plugin-validator`.

## Arquitetura

Duas camadas:

**1. Superfície do plugin** (carregada pelo Claude Code):
- `skills/` — 6 skills; `scrape-product-catalog` é o wizard que orquestra gate → warm-up → run-plan → run → export.
- `commands/` — `/scrape-setup` (toolchain), `/scrape-init <url>` (novo projeto), `/scrape-status` (progresso).
- `agents/scrape-run-auditor.md` — auditoria de cobertura/qualidade pós-scrape.
- `hooks/` — guarda `PreToolUse` (`hooks/scripts/precheck.py`): bloqueia `git add`/`git commit` que nomeie arquivo de segredo. É defesa-em-profundidade; a garantia real é o gate de runtime.
- `references/` — decisões técnicas (anti-ban, canonical record, geo-proxy, estimativa, runtime Actions, toolchain Windows).
- `.claude-plugin/plugin.json` (manifest) e `marketplace.json` (rota marketplace; excluído do zip).

**2. Motor** (`assets/scraper-template/`, scaffoldado por projeto):
- `jemscrape/` — núcleo Python 3 stdlib-only: `config`, `authz` (gate de autorização), `pacing` (anti-ban), `fetch` (+`probe`), `cache` (+cursor de resume), `runner`, `canonical`/`normalize`/`dedup`/`export_csv`/`export_wiki` (dataset), `signals`/`recon`/`warmup_gate` (warm-up), `browser` (adapters de render), `session`/`proxy` (auth + geo), `toolchain`/`settings_patch`/`secrets_io` (onboarding/Actions).
- Raiz do template — os CLIs: `scrape.py`, `smoke_test.py`, `warmup.py`, `build_dataset.py`, `auth_capture.py`, `scrape_setup.py`, `actions_setup.py`, `notify.py`.
- `drivers/` — o único lugar com dependência de terceiros: `playwright_render.py` e `auth_capture.py` (as duas importações de Playwright, guardadas) e `deploy_actions.py`.
- `assets/github-actions/scrape.yml`, `assets/project-skeleton/`, `assets/it-request/` — templates scaffoldados junto.

**Site adapters:** o motor é genérico; cada site fornece `discover(cfg) -> list[str]` e `parse(html, url) -> dict | None`, injetados no runner e no warm-up. O resto (fetch, normalize, dedup, export, gates) é reaproveitado.

**Cadeia fail-closed (não afrouxar):** compliance gate (`.scrape-authorization.json` + matriz de precedência do robots, preflight do `scrape.py` reusando `smoke_test.py`) → warm-up com veredito VERDE (`.scrape-warmup.json`, checado por `require_warmup`) → preflight de sessão quando `auth_required` (`load_run_session`, fail-closed se `.scrape-session.json` falta/expirou; e 401/403 vira `AuthExpiredError` que aborta em runtime) → run cheio. Os arquivos de gate (incluindo a sessão) são gitignored e reconstruídos de secrets no Actions (`actions_setup.py`/`secrets_io.py`). A garantia vive no runtime, não no hook nem no .gitignore.

## Regras do projeto

- **stdlib-only no núcleo:** nada em `jemscrape/` nem nos scripts raiz do template importa biblioteca de terceiros. Playwright entra só em `drivers/` (`playwright_render.py` e `auth_capture.py`), como dependência opcional. É o que mantém o motor leve e testável.
- **Testes sem rede:** tudo é injetado (fetcher, clock, urlopen, render_fn). Novos testes seguem o mesmo padrão.
- **TDD:** o projeto foi construído por SDD (subagent-driven development) com TDD por task; mudanças no motor começam pelo teste.
- **Política de modelos:** nunca Haiku. Tier econômico: Sonnet 5 medium. Opus xhigh para auditoria e para o review de sinal verde do warm-up (revisor Opus + advisor Sonnet 5).
- **Idioma:** documentação de usuário e prosa em pt-br; identificadores de código em inglês.
- **Commits:** prefixo convencional (`feat:`, `fix:`, `docs:`) e trailer `Co-Authored-By: Claude ... <noreply@anthropic.com>`; atualizar `CHANGELOG.md` em mudanças relevantes.
