# Primeiro scrape

Este guia vai do zero ao primeiro catálogo, ponta a ponta. Antes, faça o [setup da máquina](SETUP.md) até o green check dar "READY".

## 1. Comece o projeto

No Claude Code, rode:

```
/scrape-init https://www.exemplo.com
```

O assistente assume daqui. Ele pergunta uma coisa de cada vez, explica cada passo e confirma antes de cada trava. Não precisa saber de código.

## 2. Responda o assistente

Ele pergunta, um de cada vez:

- Qual o site e o que você quer (categorias, marcas).
- Qual a sua relação com o site: concorrente público, fornecedor com contrato, ou conta própria. Isso define o que o gate de compliance permite.
- Se precisa de IP de um país específico.
- Se precisa rodar agendado, sozinho.

Responda com o que você sabe. Se não souber algo, diga.

## 3. O gate de compliance

Com as respostas, ele lê o robots.txt do site e registra a autorização num arquivo (`.scrape-authorization.json`, que nunca vai pro Git). Se for concorrente público e o robots proibir as páginas que você quer, ele para aqui e explica. É proposital: melhor parar do que arriscar a conta ou um problema legal.

## 4. O warm-up

Antes do site inteiro, ele testa uma amostra de 10 a 50 produtos e te mostra o que achou: o site é normal ou precisa de navegador? tem login? tem anti-bot? os campos vêm completos?

Dois modelos revisam o resultado e dão um de três vereditos:

- Verde: pode seguir.
- Ajustar: o parser precisa de conserto. Ele arruma e roda o warm-up de novo.
- Pedir ajuda: precisa de você. Por exemplo, o site é SPA e precisa habilitar o navegador (a TI instala o Playwright), ou tem login, ou precisa de proxy. Ele pausa, diz o que fazer, e depois refaz o warm-up.

O run de verdade só começa no verde. Mesmo que alguém pule o assistente, o motor recusa rodar sem o verde.

## 5. O plano do run

Ele monta um resumo: escopo, tempo estimado, custo e riscos, tudo baseado no que o warm-up encontrou, não em chute. Se o projeto exigir aprovação, é a hora de aprovar.

## 6. O scrape

Aí ele roda. Devagar de propósito, uma requisição por vez, com pausas, pra não derrubar nem irritar o site. Guarda um checkpoint, então se cair no meio, retoma de onde parou.

## 7. O resultado

Sai em `exports/`:

- `products.csv`: uma linha por produto, colunas fixas, pronto pra abrir no Excel.
- `wiki/`: uma página markdown por produto, organizada por categoria, com um `INDEX.md`.

Esses arquivos ficam versionados no projeto (não são descartáveis). O cache cru fica em `data/`, que o Git ignora.

## Acompanhar e retomar

A qualquer momento:

```
/scrape-status
```

Mostra quanto já foi feito, o log do dia, e (no Actions) o link pra baixar o resultado. Se o run pausou (token expirado, warm-up não-verde, gate bloqueado), ele diz o motivo e o próximo passo.

## Quando algo dá errado

- "NOT READY" no `/scrape-setup`: falta uma ferramenta. Rode o comando que ele mostrou (ou entregue pra TI) e rode de novo.
- Gate bloqueou: o robots do site proíbe pra concorrente público. Não tem workaround; é pra parar.
- Warm-up voltou "pedir ajuda: SPA": o site precisa de navegador. Peça pra TI instalar o Playwright, e o assistente refaz o warm-up no modo navegador.
- CSV com estoque dobrado ou preço errado: geralmente é config (`hub_group` ou `band_priority`). O assistente ajusta.
