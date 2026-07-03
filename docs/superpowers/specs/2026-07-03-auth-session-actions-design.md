# Design — Plano 3b: sessão autenticada + geo no GitHub Actions

**Data:** 2026-07-03
**Autor:** Henrique Caner (JEM Systems) + Claude Code
**Status:** Aprovado para plano de implementação (pré-aprovação do autor)
**Base:** design canônico `2026-07-01-jem-product-scrape-kit-intel-design.md` §5.1, §5.2, §5.3; references `geo-proxy.md`, `runtime-github-actions.md`.

---

## 1. Contexto e objetivo

O 3b foi deferido na v1 como YAGNI: nenhum alvo exigia login. Ele existe para o caso
concreto que motivou o kit — o **fortuslive**: um site que exige sessão autenticada
**e** egress pelo IP do país (Reino Unido), rodando sem supervisão no GitHub Actions.

A dificuldade é que a captura de sessão é local por natureza: só a máquina do usuário
abre o Chrome e faz login. O run roda headless num runner do GitHub, longe dessa
máquina. O 3b liga os dois lados — captura local, secret, replay no runner — sem
afrouxar nenhum dos gates existentes e sem quebrar a regra stdlib-only do núcleo.

Duas capacidades entram juntas porque o alvo real precisa das duas de uma vez:
1. **Autenticação** — replay de uma sessão capturada localmente (cookies + storage).
2. **Geo** — egress pelo IP do país via proxy provisionado pela TI, tanto no path HTTP
   quanto no path browser.

## 2. Escopo

**Dentro:**
- Módulo stdlib de sessão (`jemscrape/session.py`): parse do `storage_state` do
  Playwright, header `Cookie` para o path HTTP, storage raw para o path browser,
  cálculo de validade.
- Módulo stdlib de proxy (`jemscrape/proxy.py`): tradução de `HTTPS_PROXY` para o dict
  de launch do Playwright.
- Detecção de expiração de token fail-closed: `AuthExpiredError`, aborta o run em
  401/403 (não retenta, não segue).
- Preflight de sessão: aborta antes de qualquer fetch se `auth_required` e a sessão
  está ausente ou expirada.
- Captura local: `drivers/auth_capture.py` (Playwright headed) + CLI raiz
  `auth_capture.py`.
- Wiring: campos `auth_required` e `login_url` no config; injeção de sessão em
  `scrape.py` e `warmup.py`; secret condicional `SCRAPE_STORAGE_STATE` em
  `actions_setup.py` e `deploy_actions.py`; passos do `scrape.yml`.
- Blindagem do segredo: `.scrape-session.json` no `.gitignore` do skeleton e como
  marcador no hook `precheck.py`.
- Ritual de refresh diário documentado em reference.

**Fora (deferido, YAGNI até haver caso):**
- Refresh de token automatizado sem interação humana (impossível quando o site exige
  captcha/2FA no login — é o gatilho de promoção a VM da §5.1 regra 6).
- Promoção a VM propriamente dita (já documentada como fallback dirigido pela TI, §19
  do design canônico).
- Rotação de múltiplas sessões / múltiplas contas.

## 3. Princípios herdados (não afrouxar)

- **stdlib-only no núcleo.** Nada em `jemscrape/` nem nos scripts raiz importa
  terceiros no topo. Playwright entra só em `drivers/` (headed capture) e no já
  existente `drivers/playwright_render.py` (render). Os scripts raiz importam o driver
  de forma lazy dentro de `main()`, como `scrape.py` já faz.
- **Testes sem rede, por injeção.** `session.py` e `proxy.py` são testados com
  fixtures JSON e strings. A captura headed é um driver fora da suíte stdlib
  (smoke skip-if-absent).
- **Fail-closed em toda a cadeia.** Sessão ausente/expirada aborta antes do fetch;
  401/403 mid-run aborta e alerta. O segredo nunca vai para argv nem para o repo.
- **Reuso dos contratos existentes.** O runner já recebe `fetcher(url) -> html`; o
  warm-up recebe `probe_fn(url) -> Probe`; `build_fetcher`/`build_pacer` já existem em
  `scrape.py`; `secrets_io.materialize_secret` e `deploy_actions.build_secret_commands`
  já existem. O 3b liga nesses pontos, não os reescreve.

## 4. Arquitetura

### 4.1 `jemscrape/session.py` (stdlib, TDD)

Fonte única da sessão é o `storage_state` do Playwright — um JSON com `cookies` (lista
de dicts com `name`, `value`, `domain`, `path`, `expires`, `httpOnly`, `secure`,
`sameSite`) e `origins` (localStorage por origem). O módulo não inventa formato próprio;
lê o que o Playwright grava.

API:
- `load_session(path) -> Session` — lê e valida o JSON; `SessionError` (nova exceção)
  se ausente, malformado, ou sem cookies.
- `Session.cookie_header(domain) -> str` — monta `name=value; name2=value2` com os
  cookies cujo `domain` casa (suffix match, respeitando o ponto-prefixo do padrão de
  cookies) e que não expiraram. Vazio se nenhum aplica.
- `Session.storage_state -> dict` — o dict raw, para o path browser passar a
  `new_context(storage_state=...)`.
- `Session.expires_at -> datetime | None` — menor `expires` entre os cookies não-sessão
  (epoch → UTC). `None` quando só há cookies de sessão (`expires == -1`), tratado como
  "validade desconhecida, confie no run" mas alertável.
- `Session.is_expired(now) -> bool` — `True` se `expires_at` existe e é `<= now`.

Separação explícita (§5.1): validade de token é distinta de progresso. O `cursor.json`
continua sendo o dono do progresso; `session.py` só cuida do token.

### 4.2 `jemscrape/proxy.py` (stdlib, TDD)

- `proxy_dict_from_url(url) -> dict | None` — traduz uma URL de proxy
  (`http://user:pass@host:port`) no dict que o Playwright espera no launch:
  `{"server": "http://host:port", "username": ..., "password": ...}`. `None` para
  entrada vazia. Credenciais saem do `server` e vão para os campos próprios (o
  Playwright rejeita user:pass embutido no server). URL inválida → `ConfigError`.
- Motivação (de `geo-proxy.md`): o path HTTP honra `HTTPS_PROXY` via urllib sem
  ajuda; o path browser **não** — o Chromium headless ignora o env var e o proxy tem
  que ir no `chromium.launch(proxy=...)`. Este helper existe só para o path browser.

### 4.3 Expiração fail-closed em `fetch.py` e no runner

Nova exceção `AuthExpiredError(Exception)` em `errors.py`.

`fetch.py`: ao ver `HTTPError` 401 ou 403, levanta `AuthExpiredError` **imediatamente**
— sem retry, sem backoff. Um token expirado não melhora com repetição, e insistir
queima a sessão e pode disparar anti-bot. Os demais códigos e o 429 mantêm o
comportamento atual.

`runner.py`: hoje o `except Exception` marca a URL como errored e segue. Isso está
certo para uma falha de uma URL, errado para um token morto. O runner passa a
**re-levantar** exceções fatais (`AuthExpiredError`) em vez de engoli-las; falhas
comuns (`FetchError`) seguem o caminho atual (registra, marca done, continua). O
`cursor.save()` a cada URL já garante que o progresso está persistido no momento do
abort.

`scrape.py`: envolve o `run()` e captura `AuthExpiredError` → grava o estado (já
gravado pelo cursor), chama `notify.py --kind error` com mensagem acionável ("sessão
expirou mid-run; renove com auth_capture.py e atualize o secret"), e retorna non-zero.
É a regra 4 da §5.1 implementada de ponta a ponta.

### 4.4 Preflight de sessão em `scrape.py` e `warmup.py`

Quando `config.auth_required` é `true`:
- Carrega `.scrape-session.json`. Ausente → aborta (exit 2, mensagem acionável).
- `session.is_expired(now)` → aborta (exit 2): "sessão expirada; renove localmente".
  É a regra 5 da §5.1 (máquina offline / token velho → pausa e alerta, não roda cego).
- Injeta a sessão no fetcher/probe (ver 4.5).

Quando `auth_required` é `false` ou ausente, nada muda — o caminho público atual segue
intacto.

### 4.5 Injeção da sessão no fetcher/probe

`build_fetcher(cfg, *, http_fetch, render_fn=None, session=None)`:
- Path HTTP (`fetch_mode` != browser): injeta o header `Cookie` derivado da sessão.
  `fetch()` ganha o parâmetro opcional `cookie_header=None`; quando presente, adiciona
  o header `Cookie` ao `Request` junto do `User-Agent`.
- Path browser (`fetch_mode == browser`): o `render_fn` passa `storage_state` e `proxy`
  ao driver. `drivers/playwright_render.render(...)` ganha o parâmetro
  `storage_state=None`; quando presente, cria o contexto com
  `new_context(storage_state=..., user_agent=...)`. O `proxy` já é suportado.

O proxy do path browser vem de `HTTPS_PROXY` no ambiente, traduzido por
`proxy_dict_from_url`. No path HTTP o urllib já honra `HTTPS_PROXY` diretamente.

`warmup.py` recebe a mesma injeção, para que o warm-up autenticado valide a sessão
antes do run cheio (fecha o loop do warm-up para alvos logados).

### 4.6 Captura local: `drivers/auth_capture.py` + CLI raiz

`drivers/auth_capture.py` (importa Playwright, fora da suíte stdlib):
- `capture_session(login_url, out_path, *, proxy=None, user_agent=None, wait_fn=None) -> Path`
  — lança Chromium **headed** (`headless=False`) com o proxy no launch (mesmo país que
  o run usará, para não disparar re-verificação por geo mismatch), abre `login_url`,
  bloqueia até `wait_fn()` sinalizar que o login terminou (default: prompt no terminal
  esperando Enter), grava `context.storage_state(path=out_path)`.
- Import guardado com hint acionável se o Playwright faltar, igual ao
  `playwright_render.py`.

CLI raiz `auth_capture.py` (stdlib no topo, import lazy do driver em `main()`):
- Lê `login_url` do config, resolve `proxy` de `HTTPS_PROXY`, chama o driver, grava
  `.scrape-session.json` (0600, gitignored).
- Imprime a validade estimada (`session.expires_at`) e a instrução de push do secret —
  `gh secret set SCRAPE_STORAGE_STATE < .scrape-session.json` — sem executar o push
  automaticamente (o push é passo consciente do usuário; o `deploy_actions` também o
  cobre).

A parte testável (parse, validade, cookie header, tradução de proxy) mora no núcleo
stdlib e é coberta por testes; o driver headed é smoke skip-if-absent.

### 4.7 Secret condicional no Actions

`actions_setup.py`: `SCRAPE_STORAGE_STATE` → `.scrape-session.json` entra como target
**condicional**. Os dois gates atuais (`SCRAPE_AUTHORIZATION`, `SCRAPE_WARMUP`)
continuam obrigatórios (fail-closed). A sessão só é obrigatória quando o run é
autenticado. Mecanismo: o setup lê o config; se `auth_required`, adiciona a sessão à
lista de targets obrigatórios; senão, ignora. `materialize_secret` já grava com 0600.

`deploy_actions.build_secret_commands`: adiciona `.scrape-session.json` ao secret_map.
A função já faz `if f.exists()` e já empurra o valor por `stdin_file`, nunca por argv —
o segredo não vaza em listagem de processos. Sem mudança de mecanismo, só mais uma
entrada.

`scrape.yml` (template): novo secret `SCRAPE_STORAGE_STATE` no step de materialização;
`HTTPS_PROXY` já está no step de scrape; para o path browser, o proxy é lido do env e
aplicado no launch pelo próprio driver via o wiring de 4.5. O commit de checkpoint, o
upload de artifact e o `notify.py` em falha permanecem.

## 5. Config: campos novos

```jsonc
{
  "auth_required": false,          // opcional, default false; true liga o caminho auth
  "login_url": "https://site/login" // usado só por auth_capture.py; exigido se auth_required
}
```

Validação em `config.py`: `auth_required` deve ser bool se presente; se `true`,
`login_url` é exigido (string não-vazia). Sem `auth_required`, o schema atual não muda.

## 6. Fluxo ponta a ponta (alvo autenticado + geo)

1. **Local, uma vez por ciclo de token:** `python auth_capture.py` → Chrome headed com
   proxy UK → usuário loga → `.scrape-session.json` gravado → imprime "válido até X" e
   o comando do secret.
2. **Push do secret:** `gh secret set SCRAPE_STORAGE_STATE < .scrape-session.json` (ou
   via `deploy_actions`). Idem `HTTPS_PROXY` (proxy da TI) uma vez.
3. **Actions (cron ou dispatch):** materializa os gates + a sessão → gate de compliance
   → warm-up autenticado valida a sessão → `scrape.py --limit <chunk>` com cookie/
   storage_state injetados e egress pelo proxy → checkpoint → artifact.
4. **Token expira mid-run:** 401/403 → `AuthExpiredError` → cursor gravado → `notify`
   abre anotação de erro → run retorna non-zero. Próximo ciclo retoma do cursor após o
   usuário renovar a sessão.
5. **Máquina offline no horário do run:** sessão expirada detectada no preflight → run
   aborta e alerta, sem rodar cego. Retoma quando o secret for atualizado.

## 7. Ritual de refresh diário (documentação)

O run agendado é fatiado para caber logo após o horário em que o usuário tipicamente
renova o token (o cron dispara depois do refresh diário, dentro da vida do token). Não
há refresh automatizado — a captura é local por natureza. Documentado em
`references/auth-session.md`: o dono do ritual é o usuário, o mecanismo é o
`auth_capture.py` + `gh secret set`, e o gatilho de promoção a VM é o site que exige
re-login interativo não-automatizável dentro da vida do token.

## 8. Testes (stdlib, TDD)

- `test_session.py` — parse, cookie header (domain match, expirados filtrados), storage
  raw, `expires_at`/`is_expired`, `SessionError` em ausente/malformado.
- `test_proxy.py` — tradução com/sem credenciais, entrada vazia → None, URL inválida →
  erro.
- `test_fetch.py` (adição) — 401/403 levanta `AuthExpiredError` sem retry; `cookie_header`
  vira header `Cookie`.
- `test_runner.py` (adição) — `AuthExpiredError` propaga (não é engolida); `FetchError`
  segue o caminho atual.
- `test_build_fetcher.py` (adição) — injeção de cookie no path HTTP; storage_state +
  proxy no path browser.
- `test_config.py` (adição) — validação de `auth_required`/`login_url`.
- `test_actions_setup.py` (adição) — sessão obrigatória quando `auth_required`, ignorada
  quando não.
- `test_deploy_actions.py` (adição) — `.scrape-session.json` entra no secret_map por
  stdin.
- `test_actions_workflow.py` (adição) — o `scrape.yml` referencia `SCRAPE_STORAGE_STATE`.
- `test_scrape_cli` / `test_warmup_cli` (adição) — preflight de sessão fail-closed
  (ausente e expirada).
- `drivers/auth_capture.py` — guard testado (erro acionável sem Playwright); captura
  real skip-if-absent.

## 9. Riscos e decisões

- **Refresh manual é uma limitação honesta, não um bug.** A captura é local; a spec §5.1
  já assume isso. Documentado, alertado, com gatilho de promoção a VM.
- **ToS do GitHub Actions.** Scraping autenticado + geo + cron é o perfil mais sensível
  (§5.3 do design canônico). Risco aceito pela org; roteamento sensível a volume manda
  cargas pesadas para VM por padrão.
- **Cookies de sessão sem `expires`.** `expires_at` retorna `None`; o preflight não
  bloqueia (não há como saber a validade), mas o 401/403 mid-run continua sendo a rede
  de segurança fail-closed.
- **Segurança do secret.** `.scrape-session.json` é gitignored (`*.token`/`.env` já
  cobrem; adicionar `.scrape-session.json` explicitamente ao `.gitignore` do skeleton),
  materializado com 0600, empurrado por stdin, e o hook `precheck.py` ganha
  `.scrape-session.json` como marcador de segredo.
