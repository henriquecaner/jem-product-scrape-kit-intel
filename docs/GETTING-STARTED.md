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
- Quantos produtos, mais ou menos. Serve pra estimar o tempo do run.
- Se o site exige login (conta) pra ver os produtos ou os preços.
- Se precisa de IP de um país específico.
- Se precisa rodar agendado, sozinho.

Responda com o que você sabe. Se não souber algo, diga.

## 3. O gate de compliance

Com as respostas, ele lê o robots.txt do site e registra a autorização num arquivo (`.scrape-authorization.json`, que nunca vai pro Git). Se for concorrente público e o robots proibir as páginas que você quer, ele para aqui e explica. É proposital: melhor parar do que arriscar a conta ou um problema legal.

A autorização tem validade. Quando vence, o motor volta a bloquear até alguém renová-la.

## 4. Onde vai rodar

Com o gate passado, o assistente decide com você onde o scrape roda:

- Na sua máquina: site público, run avulso. O caso comum.
- No GitHub Actions: quando precisa rodar agendado, sozinho, ou sair de outro país (proxy). O assistente configura o repositório e os secrets por você.

Site que exige login também roda. Você loga uma vez na sua máquina: o assistente abre uma janela de navegador (`auth_capture.py`), você entra na conta, e a sessão é salva num arquivo protegido (`.scrape-session.json`, permissão 0600, nunca vai pro Git). Pra runs agendados no Actions, essa sessão vira um secret (`SCRAPE_STORAGE_STATE`). O motor reusa a sessão nos runs seguintes e, quando o token expira no meio, ele para e avisa em vez de coletar a página de login — aí é só recapturar. A captura é sempre local: só a sua máquina faz login, o Actions nunca loga sozinho.

## 5. A pasta do projeto

O assistente cria uma pasta nova pro projeto (`scrape-<site>/`) com o motor dentro, o `config.json` e o adaptador do site (`site_adapter.py`): a parte que sabe achar e ler as páginas de produto daquele site. Ele escreve o adaptador olhando uma página de exemplo; você não precisa mexer nele.

## 6. O warm-up

Antes do site inteiro, ele testa uma amostra de 10 a 50 produtos e te mostra o que achou: o site é normal ou precisa de navegador? tem login? tem anti-bot? os campos vêm completos?

Dois modelos revisam o resultado e dão um de três vereditos:

- Verde: pode seguir.
- Ajustar: o parser precisa de conserto. Ele arruma e roda o warm-up de novo.
- Pedir ajuda: precisa de você. Por exemplo, o site é SPA e precisa habilitar o navegador (a TI instala o Playwright), ou tem login (você roda a captura de sessão com `auth_capture.py`), ou precisa de proxy. Ele pausa, diz o que fazer, e depois refaz o warm-up.

O run de verdade só começa no verde. Mesmo que alguém pule o assistente, o motor recusa rodar sem o verde. O sinal verde tem validade e vale só pra aquele site; vencido, é refazer o warm-up.

## 7. O plano do run

Ele monta um resumo: escopo, tempo estimado, custo e riscos, tudo baseado no que o warm-up encontrou, não em chute. Se o projeto exigir aprovação, é a hora: a aprovação fica registrada junto com o plano (ver o [guia de compliance](FOR-APPROVERS.md)).

## 8. O scrape

Aí ele roda. Devagar de propósito: uma requisição por vez, com pausas curtas entre elas e pausas longas de vez em quando, pra não derrubar nem irritar o site. Na configuração padrão, mil produtos levam algumas horas. É esperado; deixe rodando.

Ele guarda um checkpoint a cada produto, então se cair no meio (conexão, máquina desligada), retoma de onde parou. Páginas que deram erro não são tentadas de novo na retomada: ficam anotadas no relatório do run (`exports/scrape_manifest.json`), e a auditoria decide se vale re-scrapear.

## 9. O resultado

Sai em `exports/`:

- `products.csv`: uma linha por produto, colunas fixas, pronto pra abrir no Excel.
- `wiki/`: uma página markdown por produto, organizada por categoria, com um `INDEX.md`.
- `scrape_manifest.json`: o relatório do run (quantos ok, quantos pulados, quantos com erro).

Esses arquivos ficam versionados no projeto (não são descartáveis). O cache cru fica em `data/`, que o Git ignora.

Antes de usar o dado na loja, peça a auditoria: o agente `scrape-run-auditor` confere cobertura, dedup e preços contra o plano do run e diz se o dataset é confiável ou se vale re-scrapear uma parte.

## Acompanhar e retomar

A qualquer momento:

```
/scrape-status
```

Mostra quanto já foi feito, o log do dia, e (no Actions) o link pra baixar o resultado. Se o run pausou (warm-up não-verde ou vencido, autorização vencida, gate bloqueado, ou sessão de login expirada), ele diz o motivo e o próximo passo.

## Quando algo dá errado

- "NOT READY" no `/scrape-setup`: falta uma ferramenta. Rode o comando que ele mostrou (ou entregue pra TI) e rode de novo.
- Gate bloqueou: o robots do site proíbe pra concorrente público. Não tem workaround; é pra parar.
- Warm-up voltou "pedir ajuda: SPA": o site precisa de navegador. Peça pra TI instalar o Playwright, e o assistente refaz o warm-up no modo navegador.
- Autorização ou sinal verde venceram: nada quebrou; o motor só recusa rodar. Renove a autorização (com quem aprova) ou refaça o warm-up.
- Sessão de login expirou: o run para e avisa em vez de coletar página de login. Rode `auth_capture.py` de novo pra recapturar a sessão (e, no Actions, atualize o secret `SCRAPE_STORAGE_STATE`). O progresso não se perde: retoma de onde parou.
- CSV com estoque dobrado ou preço errado: geralmente é config (`hub_group` ou `band_priority`). O assistente ajusta e reprocessa a partir do que já foi baixado; não precisa scrapear de novo.
