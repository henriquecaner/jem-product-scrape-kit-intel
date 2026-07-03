# Guia do desenvolvedor

Pra quem for estender ou manter o plugin.

## Como o projeto é organizado

- `assets/scraper-template/jemscrape/` — o motor, Python 3 stdlib-only: `config`, `authz` (gate), `pacing` (anti-ban), `fetch` (+`probe`), `cache` (+cursor), `runner`, `canonical`, `normalize`, `dedup`, `export_csv`, `export_wiki`, `signals` (warm-up), `recon`, `warmup_gate`, `browser` (adapters de render), `session`/`proxy` (auth + geo), `toolchain`, `settings_patch`, `secrets_io`.
- `assets/scraper-template/` (raiz) — os scripts CLI: `scrape.py`, `smoke_test.py`, `warmup.py`, `build_dataset.py`, `auth_capture.py`, `scrape_setup.py`, `actions_setup.py`, `notify.py`.
- `assets/scraper-template/drivers/` — o que depende de terceiros: `playwright_render.py` e `auth_capture.py` (as duas importações guardadas do Playwright) e `deploy_actions.py`.
- `assets/github-actions/`, `assets/project-skeleton/`, `assets/it-request/` — templates scaffoldados por projeto.
- `skills/`, `commands/`, `agents/`, `hooks/`, `references/` — a superfície do plugin.
- `docs/superpowers/` — o design (spec) e os planos de implementação.

## Rodar os testes

```
python3 -m venv .venv && .venv/bin/python -m pip install pytest
.venv/bin/python -m pytest -q
```

São 263 passando e 1 skip (o smoke do Playwright, que pula quando o Playwright não está instalado). O núcleo é stdlib-only, então os testes não fazem rede: tudo é injetado (fetcher, clock, urlopen, render_fn).

## A regra que segura o projeto: stdlib-only no núcleo

Nada em `jemscrape/` (nem nos scripts raiz) importa biblioteca de terceiros. O Playwright entra só em `drivers/` (`playwright_render.py` pro render e `auth_capture.py` pra captura de sessão), guardado, e é dependência opcional. É isso que mantém o motor leve e testável.

## Adicionar um site (site adapter)

O motor é genérico; cada site tem um adaptador. Um `site_adapter.py` expõe duas funções:

- `discover(cfg) -> list[str]`: as URLs de produto a scrapear.
- `parse(html, url) -> dict | None`: extrai o dict cru de uma página.

Comece pelo stub: copie `site_adapter.py.example` (na raiz do template) para `site_adapter.py` no projeto e implemente as duas funções. Copiado sem implementar, ele falha alto com `NotImplementedError` em vez de devolver um catálogo vazio.

O runner e o warm-up recebem essas funções por injeção. O resto (fetch, normalize, dedup, export, gates) é reaproveitado.

## Política de modelos

Nunca Haiku. Tier econômico: Sonnet 5 medium. Opus xhigh pra auditoria e pro review de sinal verde do warm-up (revisor Opus 4.8, advisor Sonnet 5). Batch API (−50%) só no runtime Actions, com API key.

## Os gates são fail-closed

Os gates travam o run, e a garantia vive no runtime, não só no hook: o gate de compliance (`scrape.py` preflight, que reusa `smoke_test.py`) e o veredito do warm-up (`scrape.py` `require_warmup`). Em projetos com `auth_required`, um terceiro gate entra: o preflight de sessão (`load_run_session`, fail-closed se `.scrape-session.json` falta ou expirou), que trava tanto `warmup.py` quanto `scrape.py`; e no runtime, um 401/403 vira `AuthExpiredError` que aborta o run em vez de coletar página de login. Os arquivos de gate (incluindo a sessão) são gitignored e reconstruídos de secrets no Actions. Não afrouxe isso.

## Lançar uma versão

1. Suba a versão em `.claude-plugin/plugin.json` **e** em `.claude-plugin/marketplace.json` — as duas precisam bater.
2. Atualize o `CHANGELOG.md`.
3. Rode `scripts/build-plugin-zip.sh` (gera `dist/jem-product-scrape-kit-intel-<versão>.zip`; o `dist/` é gitignored).
4. Tag e release com o zip anexado:

```bash
git tag vX.Y.Z && git push origin vX.Y.Z
gh release create vX.Y.Z dist/jem-product-scrape-kit-intel-X.Y.Z.zip --title "vX.Y.Z" --notes "..."
```

Quem instala pelo marketplace pega a versão da `main`; quem instala pelo zip pega o release. Por isso o release sai sempre depois do push.

## Processo

O projeto foi construído por SDD (subagent-driven development): cada plano vira tasks TDD, com review por-task e um review de branch inteira no fim. Specs em `docs/superpowers/specs/`, planos em `docs/superpowers/plans/`. Commits terminam com o trailer `Co-Authored-By`.
