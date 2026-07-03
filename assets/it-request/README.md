# Pedido para a TI — kit de scraping JEM

Instalar/provisionar de uma vez (a maioria exige senha de admin no Windows).

## Toolchain (por máquina do usuário)

winget (PowerShell como administrador):

    winget install --id Git.Git -e --silent
    winget install --id GitHub.cli -e --silent
    winget install --id Python.Python.3.12 -e --silent

Caminho browser e captura de sessão (só para sites SPA/JS ou com login):

    pip install playwright
    playwright install chromium

Chrome normalmente já está presente.

## Provisionamento da org (não é por usuário)

- **Conta de proxy compartilhada** (residencial, saída no país-alvo) — apenas para alvos geo-restritos.
- **`ANTHROPIC_API_KEY`** — secret do repositório, para normalização via LLM no runtime GitHub Actions (Batch API). Apenas quando a normalização assistida por LLM estiver em uso.
- **Projeto GCP + billing + IAM** — apenas para o fallback VM (fora do caminho padrão).

## Notas

- O repositório do projeto deve ser **privado** (dado sensível).
- Os secrets do Actions (`SCRAPE_AUTHORIZATION`, `SCRAPE_WARMUP`, e opcionalmente `HTTPS_PROXY`/`ANTHROPIC_API_KEY`/`SCRAPE_STORAGE_STATE` — este último quando `auth_required`) são setados via `gh secret set` (requer `gh` autenticado).
