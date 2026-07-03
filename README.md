# jem-product-scrape-kit-intel

Plugin do Claude Code que ajuda o time da JEM a trazer catálogos de produtos de outros sites (fornecedores e concorrentes) pra loja, sem precisar saber programar e sem passar por cima das regras dos sites.

Você conversa com um assistente que pergunta o que precisa, confere se o scraping é permitido, testa o site antes e só então roda. No fim, sai uma planilha pronta pro Excel e uma wiki com uma página por produto.

**Versão atual:** v0.1.0 ([release com o instalador](https://github.com/henriquecaner/jem-product-scrape-kit-intel/releases/tag/v0.1.0)). Recém-publicada; estamos validando a instalação nas primeiras máquinas.

## Como começar

1. Prepare a máquina: [setup passo a passo](docs/SETUP.md), Windows e Mac. Diz o que instalar e o que pedir pra TI.
2. No Claude Code, rode `/scrape-setup` e espere aparecer "READY".
3. Rode `/scrape-init <endereço do site>` e siga o assistente: [guia do primeiro scrape](docs/GETTING-STARTED.md).

Pra acompanhar um scrape em andamento: `/scrape-status`.

## O que ele garante

- **Não scrapeia o que não pode.** Antes de qualquer coisa, ele lê as regras do site (o robots.txt) e registra quem autorizou. Se não pode, ele para e explica. Não tem jeitinho, e é de propósito.
- **Testa antes de gastar.** Um warm-up com 10 a 50 produtos descobre se o site precisa de navegador, se tem login ou se bloqueia robôs, antes do run de verdade.
- **Não derruba o site.** O ritmo é devagar de propósito: uma página por vez, com pausas.
- **Entra em sites com login.** Quando o site exige conta, você loga uma vez na sua máquina e o motor reusa essa sessão nos runs seguintes, inclusive nos agendados. Se o token expira no meio, ele para e avisa em vez de coletar página de login como se fosse produto.
- **Sai por um IP do país certo.** Pra sites que só respondem de um país, o run sai por um proxy daquele país (o mesmo tanto no fetch simples quanto no navegador).
- **Se cair, retoma.** O progresso fica salvo. Queda de conexão não faz recomeçar do zero.
- **Sai pronto pra usar.** Um `products.csv` que abre no Excel sem sustos e uma wiki organizada por categoria.
- **Pode rodar sozinho.** Pra scrapes agendados, ele roda no GitHub Actions, sem depender do seu computador ficar ligado.

## Guias

- [O que é o plugin](docs/OVERVIEW.md) — a visão geral, pra quem chegou agora.
- [Setup da máquina](docs/SETUP.md) — o que instalar e o que é da TI.
- [Primeiro scrape](docs/GETTING-STARTED.md) — do zero ao primeiro catálogo.
- [Glossário e FAQ](docs/GLOSSARY.md) — os termos em linguagem simples.
- [Compliance pra quem aprova](docs/FOR-APPROVERS.md) — pra gestor ou jurídico decidir com segurança.

## Pra quem é do código

O motor é Python 3 só com a biblioteca padrão (Playwright é dependência opcional, do caminho de navegador e da captura de sessão autenticada) e roda local ou agendado no GitHub Actions. Arquitetura, testes, como adicionar um site e como lançar versão estão no [guia do desenvolvedor](docs/DEVELOPING.md). O design e os planos de implementação estão em [`docs/superpowers/`](docs/superpowers/).

```bash
python3 -m venv .venv && .venv/bin/python -m pip install pytest
.venv/bin/python -m pytest -q     # motor: 263 passando (+1 skip: smoke Playwright)
```

Repositório interno JEM Systems. UNLICENSED.
