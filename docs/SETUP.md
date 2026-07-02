# Setup da máquina (antes de começar)

Este guia prepara a máquina pra rodar o plugin. Faça uma vez por máquina. Pode rodar de novo sem problema.

O plugin roda dentro do Claude Code. Você precisa de quatro coisas instaladas: Git, GitHub CLI (`gh`), Python 3 e, só pra sites que precisam de navegador, o Playwright. Em notebook Windows corporativo da JEM, a instalação normalmente depende da TI, porque exige senha de administrador.

## O que é da TI e o que é seu

Você mesmo faz: criar ou entrar na conta do GitHub, autenticar o `gh`, rodar o plugin.

A TI provisiona (não é por usuário): a conta de proxy compartilhada (só pra sites geo-restritos) e a `ANTHROPIC_API_KEY` (só quando a normalização por IA entrar). Nada disso é necessário pro scraping público local.

Se tudo já estiver instalado, pule pra "Instalar o plugin".

## Windows

A maioria dos notebooks da JEM é Windows travado. Peça pra TI rodar, no PowerShell como administrador:

```powershell
winget install --id Git.Git -e --silent
winget install --id GitHub.cli -e --silent
winget install --id Python.Python.3.12 -e --silent
```

Só pro caminho de navegador (sites SPA/JS ou com login), também:

```powershell
pip install playwright
playwright install chromium
```

O Chrome normalmente já está na máquina.

Não sabe o que falta? O plugin te diz. O `/scrape-setup` (mais abaixo) lista o que está instalado e o que falta, com os comandos `winget` prontos pra entregar pra TI. O arquivo `assets/it-request/README.md` traz esse pedido pronto.

## Mac

Com o Homebrew:

```bash
brew install git gh python
```

Só pro caminho de navegador:

```bash
pip3 install playwright
playwright install chromium
```

## Entrar no GitHub

Crie ou entre na sua conta do GitHub e autentique o `gh`:

```bash
gh auth login
```

Siga as perguntas (GitHub.com, HTTPS, autenticar pelo navegador). Pra conferir depois: `gh auth status`.

## Instalar o plugin

Peça acesso ao repositório privado do plugin (`jem-product-scrape-kit-intel`). Com o repo em mãos, adicione ele como plugin no Claude Code. A forma exata depende de como a JEM distribui (marketplace interno ou repositório clonado localmente); em dúvida, pergunte a quem cuida do plugin. Depois de instalar, reinicie o Claude Code pra ele carregar as skills e os comandos.

## Rodar o green check

Abra o Claude Code e rode:

```
/scrape-setup
```

Ele checa o toolchain, corrige o PATH do app Desktop (escreve em `~/.claude/settings.json` por você, não é passo manual) e diz se está tudo pronto. Se faltar algo obrigatório, ele mostra o que instalar e não deixa seguir. Quando aparecer "READY", a máquina está pronta.

Sobre o app Desktop: quando você abre o Claude Code pelo Dock ou pelo Finder (em vez do terminal), às vezes ele não enxerga o `python`/`gh` mesmo instalados, porque não herda o PATH do shell. O `/scrape-setup` resolve isso escrevendo o PATH certo no `settings.json`. É por isso que o green check é o portão antes do `/scrape-init`.

## Pronto

Máquina configurada. Vá pro [primeiro scrape](GETTING-STARTED.md).
