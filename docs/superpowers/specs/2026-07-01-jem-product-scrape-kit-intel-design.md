# Design — `jem-product-scrape-kit-intel`

**Data:** 2026-07-01
**Autor:** Henrique Caner (JEM Systems) + Claude Code
**Status:** Aprovado para plano de implementação
**Revisão:** rev6 — §6.1 especifica a **implementação do onboarding (Plano 6)**: núcleo testável (green-check + kit-TI + fix de PATH + CLI `scrape_setup`) + assets (`.gitignore` do scaffold, kit-TI) + driver `deploy_actions`; skill markdown + commands deferidos ao Plano 7 (achado #46). rev5 §5.3 runtime Actions (#45). rev4 dividiu o Plano 3 em 3a (§5.2) + 3b deferido (#44). rev3 Warm-Up Lap + review de sinal verde (§9.1, #43). rev2 deep review multi-agente (49 achados). Rastreabilidade no §21.

---

## 1. Contexto e objetivo

A JEM Systems precisa scrapear produtos de fornecedores e concorrentes para subir no catálogo com qualidade e gerar vendas. Isso já foi feito duas vezes no repo Fast-Alarm, com processos diferentes:

- **firechiefglobal** — scrape local via Claude Code, site Magento server-rendered, sem autenticação.
- **fortuslive** — exigia login e IP do Reino Unido; rodou numa VM GCP com IP UK, autenticada, em horário comercial para não derrubar a conta.

O objetivo é empacotar esse conhecimento num plugin que qualquer pessoa do time JEM use sozinha, com segurança e — o que mais importa — com dados de qualidade. Cada projeto tem um objetivo próprio (análise de preços, comparação de qualidade de dados, criação de produtos em Shopify ou Magento via NetSuite), mas todos partem da mesma fundação de scraping.

O nome canônico do plugin é **`jem-product-scrape-kit-intel`** (definido no `plugin.json`). Mora num repositório standalone e é publicado no marketplace interno da JEM. O diretório atual do repo (`jem-aget-product-scap-plugin`) tem typos e será renomeado para o nome canônico como primeira tarefa do plano (ver §19).

## 2. Decisões travadas (resumo do brainstorming)

| Decisão | Escolha |
|---|---|
| Foco da v1 | Fundação de scraping reutilizável (motor compartilhado + skills por objetivo em cima) |
| Perfil de uso | Majoritariamente não-técnicos → skills como wizard guiado, máxima automação |
| Estratégia de fetch | Híbrida: HTTP stdlib como padrão (núcleo zero-dep); Playwright sob demanda para JS/auth |
| Contrato de saída | Registro canônico normalizado **e** cache cru + manifest (o cru é subproduto, o canônico é a entrega) |
| Compliance | Enforcement em runtime (`scrape.py`/workflow) + hook de defesa-em-profundidade + checklist guiado |
| Packaging | Templates + scaffolding (o motor vive como templates que as skills instanciam e adaptam) |
| Ambiente do usuário | Notebooks Windows corporativos (90%); usuário cria/loga contas sozinho, mas depende da TI para instalar software |
| Superfícies | Terminal CLI e Desktop (modo local); web fora de escopo |
| Runtime pesado | GitHub Actions + proxy de país como padrão para público/geo/agendado; auth+multi-dias tem ritual de token; GCP VM e Cloudflare como fallbacks |
| Política de modelo | Nunca usar Haiku; tier econômico é Sonnet 5 `medium` (thinking off para extração simples, on para julgamento) |

## 3. Arquitetura — duas camadas

**Camada 1 — O Motor (v1).** Núcleo HTTP/parse **zero-dependência em Python 3 stdlib**, templates de infra, e as skills que os instanciam e adaptam por site. Leva qualquer pessoa do time do zero até um catálogo scrapeado e normalizado, com auditoria de qualidade no fim. **O caminho browser/autenticação usa Playwright** como dependência declarada e opcional (login, captura de sessão via `storage_state`, fetch de páginas com JS) — só entra quando o site exige, e é instalado pela TI para quem precisa (§6, §12).

**Camada 2 — Skills por objetivo (roadmap, interface definida agora).** Análise de preços, comparação de qualidade de dados, criação de produto em Shopify e Magento/NetSuite. Consomem o registro canônico produzido pela Camada 1.

O princípio central: **o motor não conhece o objetivo.** Ele entrega um registro de produto padronizado; as skills de objetivo trabalham em cima dele. As camadas ficam isoladas e testáveis de forma independente.

## 4. Superfícies suportadas

O plugin roda o mesmo motor do Claude Code contra a máquina local real em **duas superfícies**, e ambas carregam skills, agents, hooks, commands e MCP de forma idêntica:

- **Terminal CLI** — suporte completo.
- **App Desktop (modo local)** — suporte completo. Ressalva: ao abrir pelo Dock/Finder o app nem sempre herda o `PATH` do shell, então `python3`/`playwright`/`gcloud` podem "não ser encontrados" mesmo instalados. O `/scrape-setup` **escreve** o `env`/`PATH` correto em `~/.claude/settings.json` (não é passo manual do usuário) e valida no check verde.

**Fora de escopo: Claude Code na web (e sessões "remote").** A web roda em VM na nuvem da Anthropic, sem acesso à máquina local — plugins não carregam, hooks não rodam, e não há Chrome/scheduler locais. Documentado no README.

## 5. Runtimes de execução

O plugin suporta três runtimes. A orquestradora escolhe a partir de: *precisa logar? precisa de IP de um país específico? precisa rodar agendado sem supervisão? qual o volume/duração estimados?*

```
Precisa logar?  país?  agendado sem supervisão?
  └─ Nada disso (público, avulso) ─────────────► LOCAL (roda na máquina Win/mac)
  └─ Só país e/ou agendado, SEM auth ──────────► GITHUB ACTIONS  (sweet spot)
        país → HTTPS_PROXY com saída no país (proxy provisionado pela TI, §19)
        agendado → cron em pedaços + checkpoint versionado (state/cursor.json)
        browser → Playwright dentro do Actions + proxy no launch
  └─ Autenticado ──────────────────────────────► depende da duração:
        cabe numa janela (~1 dia útil, token ~10h) → GITHUB ACTIONS (1 run)
        multi-dias → GITHUB ACTIONS + ritual diário de token (§5.1), OU
        re-login interativo não-automatizável / volume muito alto → VM (fallback, §19)
```

**Recuperação das saídas (todos os runtimes cloud).** O run gera o entregável em `exports/` (products.csv, wiki/, scrape_manifest.json). No Actions, além de versionar `exports/` no repo, o workflow publica via `actions/upload-artifact`. O `/scrape-status` devolve o link do artifact/commit; `pull.py` baixa localmente. **Só o cache cru (`data/`) e segredos ficam gitignored** — `exports/`, `wiki/` e `state/` são versionados (markdown/CSV são leves; o peso de 355MB do firechief era cache HTML, que fica em `data/`).

**Fallbacks documentados (não-v1):**
- **Cloudflare Workers** — para sites que exigem login mas **não** têm geo-block; Workflows/Durable Objects dão execução durável e pausada melhor que o Actions (`step.sleep` até 365 dias, não bilhado enquanto dorme). **Não resolve geo** (o egress do Worker não sai por país específico nem usa proxy externo de forma suportada). Requer conta Cloudflare (self-serve) + plano Workers Paid.
- **GCP VM** — para o caso auth+re-login-interativo ou volume muito alto; ou se o ToS do Actions virar bloqueio. **Requer a org/TI provisionar projeto GCP + billing + IAM** (§19); o usuário não tem conta GCP, então este caminho é dirigido pela TI, não self-serve.

**Por que Actions + proxy é o padrão para público/geo/agendado:** desacopla os problemas que a VM resolvia. Geo vira config de proxy (qualquer runtime honra `HTTP_PROXY`); o agendamento vira cron; o deploy inteiro é feito via API REST do GitHub (o Claude Code escreve o workflow com escopo `workflow` e seta secrets via `gh secret set`). Zero instalação de VM, sem GCP no caminho padrão.

**Risco de ToS do GitHub Actions (aceito).** Scraping autenticado/geo-restrito/cron contra concorrentes é um perfil que o GitHub pode tratar como uso abusivo (cláusula de "atividade não relacionada / carga desproporcional"). A mitigação "o scraper é o projeto de software do repo" é **parcial**. Decisão: registrar como **risco aceito** (posição da org/jurídico) e **roteamento sensível a volume/continuidade** — cargas pesadas e contínuas vão para VM/Cloudflare por padrão, não como reação a um bloqueio (ver §18).

**Cuidados do runtime Actions:** runs agendados atrasam e às vezes caem → cada run é idempotente e retoma do `state/cursor.json`; auto-disable após 60 dias de inatividade → os commits de checkpoint contam como atividade; repo **privado** para dado sensível (2.000 min/mês grátis, suficiente para scrape pausado); repo público só para dado genuinamente público. Proxy é serviço pago (residencial UK ~US$1,75+/GB), mas scrape pausado usa pouca banda.

### 5.1 Ciclo de vida da sessão autenticada

Ponto crítico do caminho auth: o token/sessão (JWT no Chrome, ~10h) expira, e a captura é **intrinsecamente local** (só a máquina do usuário loga no Chrome). Distinguir duas coisas:

- **Sessão recuperável (progresso):** o `state/cursor.json` deixa qualquer run retomar de onde parou. Isso é independente do token.
- **Renovação de token:** processo separado, com dono e mecanismo explícitos.

Regras:
1. **Captura local** — `auth_capture.py` (Playwright): o usuário loga no Chrome (com proxy no launch quando há geo), a sessão é salva via `storage_state`, e o token é extraído dela. Nada de ler leveldb cru.
2. **Push do token** — o driver empurra a sessão como **secret do Actions via `gh secret set`** (por isso `gh` está no toolchain do caminho auth; a criptografia libsodium fica com o `gh`).
3. **Janela** — runs autenticados no Actions são fatiados para caber logo após o refresh diário, dentro da vida do token.
4. **Expiro mid-run → fail-closed + alerta** — o `scrape.py` detecta 401/403, para (não crasheia), grava o cursor, e abre uma issue/dispara `notify.py`. Nada de continuar cego.
5. **Máquina offline** — se o run agendado precisa de token novo e a máquina do usuário está desligada, o run pausa e alerta; retoma no próximo refresh. Documentado como limitação honesta.
6. **Gatilho de promoção** — se o site exige re-login interativo que não dá pra automatizar dentro da vida do token, promove para VM (fortus-style, dirigido pela TI).

### 5.2 Adapter de render por browser (Plano 3a)

Muitos sites são SPAs: o HTML estático vem vazio e só um browser que executa JS enxerga o produto. Esse é o bloqueio real que o warm-up (§9.1) já sinaliza ("PEDIR AJUDA: precisa browser") — independente de login.

**Escopo dividido.** **3a (construído agora):** render de páginas públicas. **3b (deferido, YAGNI):** captura de sessão, ciclo de token (§5.1), `gh secret`, refresh diário, promoção a VM — só quando existir alvo logado.

**Arquitetura** (espelha a DI do motor — o `runner` já recebe `fetcher`, o warm-up recebe `probe_fn`):
- `jemscrape/browser.py` (stdlib, TDD): `RenderedResult(status, html, final_url)`; `browser_fetch(url, *, render_fn) -> str`; `browser_probe(url, *, render_fn) -> Probe`. Adapters puros que convertem um resultado renderizado nos contratos que o motor já usa. Testados com `render_fn` fake — Playwright não entra na suíte.
- `assets/drivers/playwright_render.py` (Playwright, **única** importação da dep): `render(url, *, timeout, proxy=None) -> RenderedResult`. Import guardado, erro acionável se a dep faltar (instalada pela TI, §19). Fora da suíte stdlib — verificado por integração / smoke skip-if-absent.
- Wiring: `config.json` ganha `fetch_mode: "http" | "browser"` (default `http`). `scrape.py` e `warmup.py` selecionam o fetcher/probe_fn; no modo browser injetam `render_fn=render` do driver. O core (runner/warm-up) não muda.

**Compliance intacto:** os dois gates (§10 compliance + §9.1 veredito) e o `Pacer` (rate-limit entre renders) continuam valendo; robots idem. O modo browser fecha o loop do warm-up: `warmup.py --render browser` re-mede o shape depois que a TI instala o Playwright.

Playwright passa a ser **dependência opcional declarada** (não entra no núcleo zero-dep, §3), só no caminho browser.

### 5.3 Implementação do runtime Actions (Plano 5)

O workflow roda o pipeline **determinístico** atual (fetch → parse → normalize → dedup → export) sem supervisão, no cron, com o gate de compliance no runtime (§10).

**Secrets → arquivos (mecanismo-chave).** Os arquivos de gate são gitignored (segredos): `.scrape-authorization.json` e `.scrape-warmup.json` não vão pro repo. No Actions, o passo de setup os **materializa a partir de secrets** (`SCRAPE_AUTHORIZATION`, `SCRAPE_WARMUP`) via `actions_setup.py` — fail-closed: secret ausente → aborta non-zero antes de qualquer fetch; perms restritas (0600).

**Passos do workflow** (`assets/github-actions/scrape.yml`, template): `workflow_dispatch` + `schedule` (cron); checkout; setup Python; `actions_setup.py` (materializa os gates); `smoke_test.py` (gate de compliance, fail-closed); `scrape.py --limit <chunk>` (cron em pedaços, retoma do `state/cursor.json`); `build_dataset.py` (monta exports); commit do checkpoint (`state/cursor.json` + `exports/`, conta como atividade e evita auto-disable); `actions/upload-artifact` de `exports/`; em falha, `notify.py` (`if: failure()`).

**Testável (stdlib, TDD):** `jemscrape/secrets_io.py` (`materialize_secret`, fail-closed), `actions_setup.py` (CLI que materializa os dois gates), `notify.py` (formata/emite anotação GitHub `::error::`/`::warning::`). O `.yml` é template (asset) validado por teste de asserção textual dos passos/guards.

**Determinístico agora, Batch depois.** O pipeline v1 é determinístico → o Actions não precisa da Anthropic API. O passo de normalização por LLM com **Batch (−50%)** + `ANTHROPIC_API_KEY` (§11) entra quando a normalização assistida por LLM existir (Camada 2); fica como secret opcional + hook documentado, não no caminho atual.

**Fora do Plano 5 (deferido):** deploy automatizado (`gh secret set` + push do workflow via API do GitHub) — é a skill/driver de onboarding (Plano 6). O Plano 5 entrega o template + os helpers testáveis + o gate no runtime.

## 6. Onboarding em duas fases

Como o usuário cria contas sozinho mas depende da TI para instalar software, o onboarding (skill `scrape-onboarding`, comando `/scrape-setup`) se divide em duas fases:

**Fase A — uma vez por máquina, precisa da TI.** Detecta o que falta e gera um "kit para a TI": documento + comandos silenciosos (winget IDs + flags) para instalar de uma vez só. Toolchain:
- Git + GitHub Desktop + **`gh` CLI** (o `gh` é o que permite `gh secret set` no caminho auth)
- Python 3
- **Playwright + Chromium** (`pip install playwright` + `playwright install chromium`) — só para o caminho browser/auth; pode exigir a TI se o download do browser for bloqueado
- Chrome (normalmente já presente)
- `gcloud` **apenas** se o usuário for usar o fallback VM (fora do pedido padrão)

**Fase B — o usuário faz sozinho, re-executável.**
- Criar/logar conta GitHub e autenticar o `gh`
- Fix de PATH/`env` do Desktop (o `/scrape-setup` escreve em `settings.json`; não é manual)
- Criar o repo do projeto
- **Check verde final** que só libera o `/scrape-init` quando tudo (incl. `gh auth status`, Playwright, PATH) está OK

Pré-requisitos que **não** são do usuário e sim da org/TI (ver §19): a conta de proxy compartilhada, a `ANTHROPIC_API_KEY` (para normalização via LLM no Actions), e — se for usar VM — o projeto GCP. Se tudo já estiver instalado/provisionado, pula direto para a Fase B.

### 6.1 Implementação do onboarding (Plano 6)

O núcleo testável do onboarding é detecção + configuração; a orquestração (skill `scrape-onboarding`) é markdown que o `plugin.json` carrega — authorada no Plano 7 junto do empacotamento, pra não shipar markdown inerte.

**Testável (stdlib, TDD):**
- `jemscrape/toolchain.py` — registry de ferramentas (git, `gh`, python3, Playwright, Chrome; winget ID + porquê + opcional?), `check_tools(*, which)` → relatório present/missing, `render_it_kit(report)` → o "kit para a TI" (§6 Fase A: doc + comandos winget silenciosos das ferramentas que faltam).
- `jemscrape/settings_patch.py` — `patch_claude_settings(path, *, env)` mescla PATH/env no `~/.claude/settings.json` sem clobber (fix de PATH do Desktop, §6 Fase B; escrita atômica).
- `scrape_setup.py` (root CLI, backing do `/scrape-setup`) — roda o check verde, aplica o fix de PATH, imprime relatório + kit-TI se faltar algo, retorna non-zero se não estiver pronto (o check verde que trava o `/scrape-init`, §6 Fase B).

**Assets:**
- `assets/project-skeleton/.gitignore` — bloqueia `data/` + gate files (`.scrape-authorization.json`, `.scrape-warmup.json`) + tokens/secrets; **NÃO** bloqueia `exports/`/`state/`/`wiki/` (versionados, §5/§13). Resolve o blocker herdado do review do Plano 5 (o `.gitignore` do repo-do-plugin não vai no scaffold).
- `assets/it-request/README.md` — template do pedido pra TI (toolchain + proxy + `ANTHROPIC_API_KEY`; nota de admin no Windows, §19).

**Driver (guardado):**
- `drivers/deploy_actions.py` — fecha o deploy adiado do Plano 5: `build_secret_commands(gate_files)` → sequência `gh secret set <NAME>` (segredo via stdin do arquivo de gate, **nunca** no argv) pros dois gates; + snippet de colocar o workflow em `.github/workflows/` e commitar. Builder testável (constrói comandos como dado); execução fina.

**Deferido:** drivers de auth (daily_refresh/pull/watch — caminho 3b) e de run-plan (render_pdf — §8, não construído); a skill `scrape-onboarding` (markdown) + `/scrape-setup`/`/scrape-init` (commands) entram no Plano 7 (empacotamento) junto do `plugin.json`.

## 7. Registro Canônico JEM

Interface única entre o motor e as skills de objetivo. Versionado (`schema_version`) para não quebrar silenciosamente as skills da Camada 2 quando evoluir.

```
schema_version                     (ex.: "1.0"; política aditiva por default, breaking bump major)
source_site, source_url, scraped_at (ISO 8601)
authorization_ref                  (id do .scrape-authorization.json que autorizou esta captura)
product_id                         (CHAVE DE IDENTIDADE canônica p/ dedup e retomada — sku normalizado
                                    ou master_id da fonte; documentada por site em canonical-record.md)
sku, name, brand, description_raw, description_clean
breadcrumbs[], division, category_path
images[]                           (URLs full-res)
specs{}                            (atributos técnicos chave:valor)
variants[]                         (cada variante com seus prices[])
prices[]                           ({ value, currency, source, band } — múltiplas bandas, ex. PLE-J015 vs universal)
list_price, cost_price
stock{ total, by_location }        (dedup de hub aplicado no normalize)
attachments[]                      ({ label, url }), related[] ({ title, url })
raw_ref                            (ponteiro para o arquivo cru em cache)
```

Formatos de campo (`authorization_ref`, `related[]`, `attachments[]`) definidos em `references/canonical-record.md`. **Exports:** `exports/products.csv`, `exports/wiki/**.md` (por breadcrumb), `exports/scrape_manifest.json` (carrega `schema_version`). O `canonical-record.md` documenta o mapeamento para Shopify (title / body_html / vendor / variants / images), Magento/NetSuite e GMC (reusa a skill `gmc-quality` que já existe no ambiente JEM), a política de evolução do schema, e a chave de identidade por site.

## 8. Componentes do plugin

**Skills:**
| Skill | Papel |
|---|---|
| `scrape-onboarding` | Onboarding de primeira vez (via `/scrape-setup`): toolchain, GitHub/`gh`, Playwright, fix de PATH (escreve settings.json), pré-requisitos de org, check verde |
| `scrape-product-catalog` | Orquestrador-wizard (via `/scrape-init`): entende o alvo, roda o gate, escolhe runtime, faz scaffold, dirige warm-up → review → run-plan → run → normalize |
| `scrape-compliance-gate` | Segurança em camadas; grava/valida o `.scrape-authorization.json` (schema em §10.1) |
| `scrape-warmup` | Warm-up lap **obrigatório** (§9.1): amostra 10–50 produtos, detecta render/auth/anti-bot/shape, emite recon + checklist de preparo, e roda o review de sinal verde (Opus 4.8 `xhigh` + advisor Sonnet 5) que trava a largada |
| `scrape-normalize-export` | Cru → registro canônico + CSV/wiki/manifest; dedup/reconciliação (multi-band, hub-stock, multi-pass) |
| `scrape-run-plan` | Gera o briefing pré-run (escopo, ETA, custo, riscos, aprovação); render em PDF com fallback — alimentado pelo warm-up (§9.1) |

**Commands:** `/scrape-setup` (1ª vez) · `/scrape-init` (novo projeto) · `/scrape-status` (lê `state/cursor.json` + `docs/DAILY.md`; no Actions entrega link do artifact/commit).

**References:** `runtime-local.md` · `runtime-github-actions.md` (estrela — inclui contrato de token, checkpoint, monitoramento) · `runtime-cloudflare-optional.md` · `runtime-vm-fallback.md` · `canonical-record.md` · `anti-ban-playbook.md` · `geo-proxy.md` · `execution-strategy.md` · `windows-toolchain.md` · `estimation.md`.

**Assets / templates (o motor):**
- `assets/scraper-template/` — `scrape.py` (núcleo HTTP zero-dep + adaptador Playwright opcional; **valida a autorização em runtime e aborta non-zero — ver §10**), `smoke_test.py`, `warmup.py` (warm-up lap §9.1: amostra + detecção de render/auth/anti-bot/shape; **runtime recusa run full sem warm-up verde**), `notify.py`, `build_dataset.py` (o passo que chama a API com Batch quando roda no Actions), `config.json.example` (declara `rate_limit_floor` como campo)
- `assets/drivers/` — `auth_capture.py` (Playwright `storage_state` + push via `gh`), `daily_refresh.py`, `pull.py`, `watch.py`, `render_pdf.py` (descobre o binário do Chrome; fallback HTML/Markdown se não achar) — Python cross-platform
- `assets/vm/` — `startup-script.sh`, `deploy_vm.sh`, `push_token.sh` (bash, roda no Linux da VM; só no fallback)
- `assets/github-actions/` — template de workflow `.yml` (cron em pedaços, secrets, checkpoint, `upload-artifact`, gate de autorização em runtime)
- `assets/project-skeleton/` — README, `.gitignore` (bloqueia só `data/`, tokens, credenciais), `docs/DAILY.md`, `docs/AUDIT.md`
- `assets/run-plan-template/` — HTML/CSS do briefing
- `assets/it-request/` — template do pedido para a TI (toolchain + proxy + GCP + API key)

**Agent:** `scrape-run-auditor` — revisa cobertura/qualidade pós-scrape (drift de paginação, dedup, price sourcing, % de cobertura, validade de imagem). Roda em Opus com effort `xhigh`; escala para workflow multi-agente quando há riscos detectados.

**Hooks (defesa-em-profundidade, não a garantia primária):** `PreToolUse` em Python que, na autoria dentro do Claude Code, bloqueia se falta autorização/aprovação ou se há credencial prestes a ir pro git. **A garantia de compliance vive no runtime (§10)**, porque o run real (cron/Actions) não passa por hook. O hook resolve o interpretador com shim `py -3`→`python3`→`python` e **falha FECHADO** se nenhum existir; depende do fix de PATH já aplicado.

## 9. Fluxo end-to-end

```
/scrape-init
  → entender alvo (URL, objetivo, precisa auth?, precisa país?, precisa agendar?, volume?)
  → gate de compliance (robots.txt + declaração de autorização + piso de rate-limit
                        → grava .scrape-authorization.json válido, §10.1)
  → escolhe runtime (Local / Actions / promoção a VM), ver §5
  → scaffold do projeto a partir dos templates (Claude inspeciona uma página e adapta
                        selectors/endpoints; para geo/auth configura proxy e captura de sessão)
  → WARM-UP LAP (OBRIGATÓRIO, §9.1) — amostra 10–50 produtos; absorve o canary (parse + paginação)
                        e detecta render (server vs SPA/JS), auth/paywall, anti-bot/geo, shape de parse
                        → relatório de recon + checklist de preparo do operador
  → REVIEW OBRIGATÓRIO (§9.1) — Opus 4.8 @ xhigh (revisor) + Sonnet 5 (advisor):
                        veredito VERDE | AJUSTAR/REFATORAR | PEDIR AJUDA — só VERDE segue
  → RUN-PLAN (escopo, ETA, custo, riscos → mitigações, autorização, assinatura; PDF com fallback)
    → aprovação (se o projeto exigir, §10.1)
  → run completo (Local na hora; Actions faz deploy do workflow + secret + cron + upload-artifact
                  + smoke_test por chunk que para se a taxa de parse cair — drift de selector)
  → normalize (registro canônico + exports/)
  → auditor (Opus xhigh; workflow multi-agente quando há riscos)
  → handoff para skill de objetivo (Camada 2)
```

### 9.1 Warm-Up Lap (obrigatório) + review de sinal verde

**Regra dura:** nenhum run full roda sem um warm-up lap com veredito verde. O orquestrador e o runtime recusam pular a etapa — é fail-closed, igual ao gate de compliance (§10).

**O que é.** Uma volta de reconhecimento antes da largada. Uma amostra de **10–50 produtos** (aleatória dentro do `scope`, descoberta por sitemap ou categorias permitidas) passa pelo caminho de fetch padrão (HTTP stdlib) primeiro. Absorve o antigo canary — valida parse e paginação — e vai além: aprende o site antes de gastar o run inteiro.

**Os quatro sinais que ele mede:**
1. **Render** — server-rendered ou SPA/JS-only. HTML vazio (shell de SPA) significa que o site exige Playwright/browser, não HTTP cru.
2. **Auth / paywall** — redirect de login, campos ou preço escondidos, 401/403 → precisa de `storage_state`/login (§5.1).
3. **Anti-bot / geo** — challenge de Cloudflare, 429 recorrente, geo-block → precisa de proxy/país ou promoção a VM (§5).
4. **Shape de parse** — roda `normalize`/`dedup` na amostra e mede cobertura de campos (% com nome/SKU/preço/imagem/breadcrumb), padrão de price-band, formato de stock, colisão de variantes.

**O que o warm-up entrega:**
- **Relatório de recon** — as métricas dos quatro sinais, com amostras concretas.
- **Checklist de preparo do operador** — o que a pessoa faz antes da largada, derivado dos sinais (não genérico): logar no site, habilitar a extensão Chrome ou instalar o Playwright (via TI), configurar o proxy.
- **Insumo do run-plan** — ETA, custo e riscos saem de evidência, não de premissa.

**Review obrigatório (o gate de decisão).** Depois do warm-up, um review obrigatório roda com **Opus 4.8 effort `xhigh` como revisor** e **Sonnet 5 como advisor** — workflow de dois agentes: o advisor levanta hipóteses e riscos, o revisor decide. O veredito é um de três:

| Veredito | Quando | O que acontece |
|---|---|---|
| **VERDE** | Padrões consistentes, cobertura suficiente, sem bloqueio | Libera o run-plan → run full |
| **AJUSTAR / REFATORAR** | Parser/selectors/config precisam mudar (drift, cobertura baixa, campo-chave faltando) | Volta pro scaffold, corrige, re-warm-up |
| **PEDIR AJUDA** | Ação do operador obrigatória (login, extensão, Playwright/TI, proxy) ou decisão humana (robots ambíguo, ToS) | Pausa e pede — não roda cego; **re-warm-up depois do preparo** (num site SPA o 1º warm-up via HTTP não mede o shape até o browser estar pronto) |

**Gate final:** o run full libera só com veredito **VERDE** e, quando o projeto exigir, a aprovação do run-plan (§10.1). Reusa o padrão adversarial do `scrape-run-auditor` (§8), mas antes do run — não depois, quando o custo já foi gasto.

## 10. Segurança e compliance

**Enforcement em runtime (a garantia real).** `scrape.py` e o workflow do Actions validam o `.scrape-authorization.json` **no início e por chunk**: existência, `expires_at` não vencido, `target_domain` bate com a URL, `rate_limit_floor` presente e respeitado, e `robots_status` compatível com a matriz abaixo. Falha → aborta non-zero. Reusa o `smoke_test.py` para não duplicar lógica. O hook do Claude Code é camada extra.

### 10.1 Schema do `.scrape-authorization.json`
```
target_domain          (match exato do host; runtime rejeita divergência)
authorization_type     (public_competitor | contracted_partner | own_account)
approver, approved_at, expires_at
rate_limit_floor       (req/s mínimo respeitado; validado como campo, não parseando o script)
robots_status          (allowed | disallowed)
robots_override_ref    (obrigatório se robots_status=disallowed E type=contracted_partner)
requires_approval      (bool; se true, exige .scrape-approval.json com hash do run-plan)
scope                  (o que pode ser capturado; base de consentimento)
```
"Válido" = todos os campos presentes, `expires_at` futuro, `target_domain` batendo. O gate é **auto-declaração por design** (threat model interno); a camada de aprovação (`.scrape-approval.json`, com hash do PDF do run-plan) endurece projetos sensíveis.

### 10.2 Precedência robots.txt × autorização
| authorization_type | robots.txt `Disallow` no alvo |
|---|---|
| `public_competitor` | **bloqueio duro** (runtime aborta) |
| `contracted_partner` | override permitido **se** `robots_override_ref` referencia o contrato |
| `own_account` | override permitido (é a própria conta) |
robots.txt é condição verificada no runtime **e** no hook.

### 10.3 Camadas
1. **Baseline sempre-ligado** — piso de rate-limit, UA realista, `.gitignore` que bloqueia só `data/`/tokens/credenciais, segredos via secret do Actions (ou metadata GCP **no caminho VM**), repo privado para dado sensível, scanner tipo `gitleaks` no diff staged (detecção de credencial não depende de adivinhação do hook).
2. **Checklist guiado** — a skill explica riscos de ToS e ban, pergunta o `authorization_type`.
3. **Enforcement em runtime + hook** — descrito acima.

### 10.4 Ciclo de vida do secret de sessão
TTL com alerta no `daily_refresh.py`; revogação no offboarding; **GitHub Actions Environments com required reviewers** para os secrets sensíveis; conta de scraping **dedicada e de baixo privilégio** no site-alvo; `scope`/consentimento registrados na autorização.

### 10.5 Dados pessoais e retenção
Se o alvo for site UK/EU ou expuser PII: minimização de PII no `normalize` (não persistir campos pessoais desnecessários), base legal registrada na autorização, e política de retenção/acesso/descarte dos `exports/` versionados (definida em `references/canonical-record.md` + README do projeto). LGPD/GDPR é responsabilidade da org; o plugin dá o hook para cumprir.

## 11. Estratégia de execução (models / efforts / workflows)

Documentada em `references/execution-strategy.md`. **Nunca usar Haiku** (política JEM); o tier econômico é **Sonnet 5 `medium`**.

**Fronteira de infra por runtime (importante):**
- **Local runtime** — a normalização via LLM roda como **subagents/workflows do Claude Code** (assinatura; prompt caching aplica; **sem Batch**).
- **Actions runtime (desassistido)** — não há Claude Code rodando; a normalização é um **passo Python (`build_dataset.py`) que chama a Anthropic API com `ANTHROPIC_API_KEY`** (secret). Aqui **Batch API (−50%) + caching aplicam**. A API key é pré-requisito de org (§19).

| Tarefa | Model | Effort | Thinking | Orquestração |
|---|---|---|---|---|
| Parsing puramente mecânico | **Código determinístico (sem LLM)** — Opus infere o parser 1× | — | — | — |
| Extração semântica simples em massa | **Sonnet 5** | medium | off | Local: subagents · Actions: script + **Batch** + caching |
| Normalização com julgamento (categoria, match, qualidade) | **Sonnet 5** | medium | **on** | Local: subagents (pipeline) · Actions: script + **Batch** + caching |
| Inferência de parser / auditoria | **Opus** | **xhigh** | on | workflow quando há riscos (dimensões em paralelo + verificação adversarial) |
| Review do warm-up lap (§9.1): verde / ajustar / pedir ajuda | **Opus 4.8** (revisor) + **Sonnet 5** (advisor) | **xhigh** / medium | on | workflow de 2 agentes: advisor levanta riscos, revisor decide — **antes** do run; obrigatório, trava a largada |
| Comparar nossos × concorrentes (Camada 2) | **Sonnet 5 / Opus** | medium/high | on | workflow (fan-out por produto) |

**Levers de custo:** **Batch API (−50%) só no runtime Actions** (script + API key); prompt caching em qualquer runtime; thinking off no mecânico/extração simples (on no julgamento). Nota de billing: Batch exige API key + billing de API; a assinatura do Claude Code (runtime Local) não roteia por Batch. Controláveis: model/effort/thinking por skill/command/subagent/workflow-agent; na sessão principal o orquestrador recomenda/anuncia; escala para workflow multi-agente quando há riscos, respeitando o opt-in.

## 12. Estratégia cross-platform

Helpers OS-específicos são **drivers Python stdlib cross-platform** (mais Playwright no caminho auth) que o Claude executa igual em Windows e mac:

| Peça | Antes (mac) | Agora (cross-platform) |
|---|---|---|
| Captura de sessão de auth | `strings`+bash lendo leveldb | **Playwright `storage_state`** (login via browser controlado; NÃO lê leveldb — inviável no Windows por App-Bound Encryption v127+) |
| daily_refresh / pull / watch / render_pdf | `.sh` | drivers Python |
| Hooks | bash | Python invocado por comando com shim de interpretador (`py -3`→`python3`→`python`), fail-closed |
| Agendamento local | launchd | Task Scheduler no Win / launchd no mac — minimizado, pois o agendamento do run fica no Actions/GCP |
| Render do run-plan | Chrome headless (path fixo) | `render_pdf.py` descobre o binário do Chrome; fallback HTML/Markdown se não achar (aprovação nunca trava) |

## 13. Estrutura de projeto gerada (scaffold padrão)

```
scrape-<site>/
├── README.md · .gitignore · .scrape-authorization.json · config.json
├── scripts/  (scrape.py, smoke_test.py, notify.py, build_dataset.py)
├── .github/workflows/  (só no runtime Actions)
├── vm/         (só no fallback VM)
├── state/cursor.json     (checkpoint de retomada — versionado, NÃO gitignored)
├── exports/    (products.csv, wiki/**.md, scrape_manifest.json — entregável, versionado)
├── data/       (cache cru HTML/JSON — gitignored)
└── docs/  (DAILY.md, AUDIT.md, run-plan.pdf)
```
`.gitignore` bloqueia **apenas** `data/`, tokens e credenciais. `exports/`, `state/` e `wiki/` são versionados (leves; resolve a contradição "entregável vs gitignored").

## 14. Estrutura do repo do plugin

```
jem-product-scrape-kit-intel/
├── .claude-plugin/plugin.json   (name, version, description, author, keywords — espelha ahrefs-intel)
├── skills/{scrape-onboarding,scrape-product-catalog,scrape-compliance-gate,
│           scrape-normalize-export,scrape-run-plan}/SKILL.md
├── references/*.md
├── assets/{scraper-template,drivers,vm,github-actions,project-skeleton,
│           run-plan-template,it-request}/
├── agents/scrape-run-auditor.md
├── hooks/{hooks.json,scripts/*.py}
├── commands/{scrape-setup.md,scrape-init.md,scrape-status.md}
└── README.md · CHANGELOG.md
```
Segue a convenção do plugin `ahrefs-intel` (descrições ricas com triggers e exemplos, `when_to_use`, `allowed-tools`, `model`). O `plugin.json` é especificado no plano espelhando o `ahrefs-intel`.

## 15. Testes e qualidade

Escada de validação em cada scrape: **warm-up lap (§9.1: recon dos 4 sinais + review de sinal verde, obrigatório, absorve o canary de parse + paginação) → `smoke_test.py` por chunk (fail-close abaixo de um piso de taxa de parse — pega drift de selector) → `scrape-run-auditor`**. O run-plan documenta cobertura esperada; o auditor confere a real e o `notify.py` alerta em falha/travamento/token-expirado/cobertura-baixa (canal default = issue no repo). Terminologia unificada: o "smoke-gate" É o `smoke_test.py`. Para o plugin em si: os agentes `plugin-validator` e `skill-reviewer` (do toolchain `plugin-dev`) antes de publicar.

## 16. Roadmap Camada 2 (interface pronta, build depois)

`product-price-analysis` (usa `variants[]/prices[]` + snapshots datados por `scraped_at` para histórico) · `catalog-quality-compare` (integra `gmc-quality`) · `product-create-shopify` / `product-create-magento` (integram os agentes shopify e o NetSuite ERP). Cada uma consome o registro canônico (respeitando `schema_version`) e vira seu próprio ciclo spec → plano → implementação.

## 17. Fora de escopo (YAGNI)

- Claude Code na web / sessões remote.
- Build das skills da Camada 2 nesta v1 (só a interface).
- Cloudflare Workers como runtime de primeira classe (fica como referência/roadmap).
- Suporte a Linux desktop além do necessário (foco Windows + mac).
- Login automatizado com credenciais cruas armazenadas (preferimos captura de sessão local; credencial crua só se a org aceitar o risco, fora de v1).

## 18. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Usuário não-técnico trava no setup Windows | Onboarding em 2 fases + kit pra TI + check verde antes de liberar; PATH escrito pelo setup |
| Ban da conta em site autenticado | Pacing humanizado, horário comercial, single-thread, checkpoint, gate de autorização, conta dedicada de baixo privilégio |
| Token de sessão expira em run auth+agendado | Ritual diário de refresh (§5.1); fail-closed no expiro; promoção a VM quando re-login é interativo |
| Custo de LLM em volume | Código determinístico onde dá + Batch (só Actions) + caching + thinking off no mecânico |
| Dados sensíveis expostos no GitHub | Repo privado obrigatório; `.gitignore` bloqueia cru/segredos; scanner de secrets no diff |
| Runs de Actions atrasando/caindo | Idempotência + retomada do `state/cursor.json` |
| **ToS do GitHub Actions (risco aceito)** | Posição da org/jurídico; roteamento sensível a volume → cargas pesadas em VM/Cloudflare por padrão |
| Drift de selector em run desassistido | `smoke_test.py` por chunk fail-close + `notify.py` + re-scaffold assistido |
| Aquisição de proxy sem dono | TI provisiona conta JEM compartilhada 1× (§19); credenciais como secret gerenciado |
| Interpretador Python ausente vira fail-open no hook | Shim de interpretador + fail-closed explícito |
| Fundação GCP ausente no fallback VM | Pré-requisito de org/TI declarado (§19) |
| LGPD/GDPR (site UK/EU, dado de concorrente) | Minimização de PII + base legal na autorização + política de retenção |

## 19. Pré-requisitos de org/TI (não são do usuário)

- **Renomear o repo** `jem-aget-product-scap-plugin` → `jem-product-scrape-kit-intel` (ou fixar o nome canônico no `plugin.json` e manter o dir) — 1ª tarefa do plano.
- **Conta de proxy JEM compartilhada** (residencial UK e outros países conforme a demanda), provisionada 1× pela TI; credenciais entregues como secret gerenciado (não cada usuário contrata).
- **`ANTHROPIC_API_KEY` + billing de API** — necessária para normalização via LLM no **runtime Actions** (Batch). Runtime Local usa a assinatura, não precisa.
- **Projeto GCP + billing + IAM** — só se/quando o fallback VM for usado; provisionado pela TI (usuário não tem GCP).
- **Toolchain via TI** — Git, GitHub Desktop, `gh`, Python 3, Playwright+Chromium (caminho auth), `gcloud` (só VM).

## 20. Critérios de sucesso

- Uma pessoa não-técnica, num Windows corporativo, roda `/scrape-setup` uma vez e depois `/scrape-init` para criar e executar um scrape completo, sem escrever código.
- O scrape produz o registro canônico + exports recuperáveis (link do artifact/commit ou `pull.py`), com relatório de cobertura do auditor.
- Nenhuma credencial vai para o git; nenhum scrape começa sem autorização declarada; o enforcement vive no runtime, não só no hook.
- O motor atende: público local; público/geo/agendado na nuvem via Actions; autenticado dentro de uma janela via Actions; e escala para VM/Cloudflare nos casos duros — com o custo e os pré-requisitos de cada caminho explícitos.

## 21. Rastreabilidade do review (achado → resolução)

| # | Achado | Resolvido em |
|---|---|---|
| 1 | Gate não cobre a execução real | §8, §10 (enforcement em runtime; hook = defesa-em-profundidade) |
| 2/5/37b | Refresh de token auth+agendado sem mecanismo | §5.1 (ciclo de vida da sessão) + §6 (`gh` no toolchain) |
| 3 | Recuperação de saídas no Actions + contradição `wiki/` gitignored | §5 (upload-artifact/exports), §13 (`exports/`/`wiki/` versionados) |
| 4 | Captura de token via leveldb inviável no Windows | §3, §12 (Playwright `storage_state`), §8 (`auth_capture.py`) |
| 6 | Batch API vs subagents; API key/billing | §11 (fronteira por runtime), §19 (API key) |
| 7 | ToS do Actions como padrão | §5 (risco aceito + roteamento por volume), §18 |
| 8 | Proxy sem dono | §19 (TI provisiona), §18 |
| 9/22 | GCP não provisionado | §5, §19 (pré-requisito de TI) |
| 10 | Precedência robots.txt × autorização | §10.2 (matriz) |
| 11 | "Válido" indefinido; gate auto-servido | §10.1 (schema) |
| 12 | Ciclo de vida do secret | §10.4 |
| 13 | Interpretador dos hooks | §8, §12 (shim + fail-closed) |
| 14 | Detecção rate-limit/credencial | §10.1 (campo no config), §10.3 (gitleaks) |
| 15 | Drift de selector | §9, §15, §18 (`smoke_test` por chunk) |
| 16 | Monitoramento de runs | §15 (canal issue + gatilhos) |
| 17 | Versionamento de schema | §7 (`schema_version`) |
| 18 | Render de PDF cross-platform | §8, §12 (`render_pdf.py` + fallback) |
| 19/21 | `gcloud`/`metadata GCP` incondicionais | §6, §10.3 (marcados como só-VM) |
| 20 | Tier `low` vs `medium` | §2, §11 (reconciliado para `medium`) |
| 23/24 | Retenção de dados; LGPD/GDPR | §10.5 |
| 25/26/41 | `price{}` único; chave de identidade; formatos | §7 (`variants[]/prices[]`, `product_id`, formatos) |
| 27/28/38 | Local do estado; fonte do `/scrape-status` | §13 (`state/cursor.json`), §8 |
| 29 | `plugin.json` não especificado | §14, §19 |
| 30 | Nome vs diretório | §1, §19 (renomear) |
| 31 | Fix de PATH manual | §4, §6 (escrito pelo setup) |
| 32 | Typo `scrap-` | §13 (`scrape-<site>`) |
| 33 | Canary não valida paginação | §9, §9.1 (absorvido pelo warm-up lap — valida parse + paginação) |
| 34 | Limites do Cloudflare | §5 (nota + plano pago) |
| 35 | `HTTPS_PROXY` não cobre o browser | §12 (proxy no launch do Playwright), `geo-proxy.md` |
| 36/37 | Marcador de aprovação | §10.1 (`.scrape-approval.json` + hash) |
| 39 | `smoke-gate` vs `smoke_test.py` | §15 (unificado) |
| 40 | Origem de `plugin-validator`/`skill-reviewer` | §15 (toolchain plugin-dev) |
| 42 | Playwright vs zero-dep | §3 (zero-dep = núcleo HTTP; Playwright declarado) |
| 43 | Warm-up lap obrigatório + review de sinal verde antes do run full (sessão 2026-07-02: ADI = SPA/JS descoberto só na tentativa) | §9.1, §8 (skill `scrape-warmup` + asset `warmup.py`), §11 (Opus 4.8 `xhigh` revisor + advisor Sonnet 5) |
| 44 | Plano 3 dividido: render por browser (3a, o bloqueio real = SPA/JS) construído; auth/token (3b) deferido YAGNI (usuário sem login) | §5.2 (`jemscrape/browser.py` + `drivers/playwright_render.py` + `fetch_mode`), §5.1 (3b deferido), §3 (Playwright = dep opcional) |
| 45 | Runtime Actions (Plano 5): workflow determinístico no cron + gate no runtime + secrets→arquivos pros gates gitignored; Batch/API = hook futuro (normalize v1 é determinística) | §5.3 (`actions_setup.py` + `jemscrape/secrets_io.py` + `notify.py` + `assets/github-actions/scrape.yml`), §10 (gate no workflow), §11 (Batch adiado) |
| 46 | Onboarding (Plano 6): núcleo testável (green-check + kit-TI + fix de PATH + CLI) + assets (scaffold `.gitignore`, kit-TI) + driver deploy_actions; skill/commands → Plano 7 | §6.1 (`jemscrape/toolchain.py` + `jemscrape/settings_patch.py` + `scrape_setup.py` + `assets/project-skeleton/.gitignore` + `assets/it-request/` + `drivers/deploy_actions.py`), §6 (2 fases) |
