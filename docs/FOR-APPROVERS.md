# Guia de compliance (pra quem aprova)

Pra gestor ou jurídico que precisa autorizar um scraping antes dele rodar. O foco aqui é risco e decisão, não código.

## O princípio

O plugin não scrapeia nada sem uma autorização registrada. A autorização passa por uma matriz que combina o tipo de relação com o site e o que o robots.txt do site diz. A checagem roda no início e de novo durante o run. É fail-closed: na dúvida, para.

## Os três tipos de relação

Toda autorização declara um tipo:

- Concorrente público: um site sem contrato com a JEM.
- Fornecedor contratado: um parceiro com quem a JEM tem relação.
- Conta própria: uma loja ou conta da própria JEM.

## A matriz de robots

O robots.txt é um arquivo público onde o site diz o que aceita ou não que robôs acessem. O plugin lê e cruza com o tipo:

| Tipo | robots.txt permite | robots.txt proíbe |
|---|---|---|
| Concorrente público | pode | bloqueio duro (para) |
| Fornecedor contratado | pode | só com referência ao contrato (`robots_override_ref`) |
| Conta própria | pode | pode (é a própria conta) |

O caso mais restrito é concorrente público com robots proibindo: aí o plugin para, e não tem workaround. É de propósito.

## O plano do run (o que você aprova)

Antes do run cheio, o plugin gera um plano com escopo, tempo estimado, custo e riscos, tudo baseado no que o warm-up encontrou no site, não em chute. Pra projetos que exigem aprovação, esse plano é o documento que você revisa e assina.

A autorização tem um campo `requires_approval`. Quando ele é verdadeiro, o assistente só segue depois de registrar a aprovação (um marcador com o hash do plano e quem aprovou). Assim a aprovação fica amarrada a um plano específico, não a "um plano qualquer".

Um limite pra deixar claro: hoje essa trava é do processo, não do motor. O assistente exige o registro antes de rodar, mas os gates que o motor verifica sozinho, em runtime, são dois: a autorização e o veredito do warm-up. O arquivo de aprovação ainda não é verificado pelo motor.

## O que fica registrado

- A autorização (`.scrape-authorization.json`): tipo, quem autorizou, quando, validade, escopo, status do robots. Fica fora do Git, por ser sensível.
- O veredito do warm-up (`.scrape-warmup.json`): o sinal verde que libera o run, com validade e domínio.
- O plano do run e, se exigido, a aprovação com hash.

## Limites honestos

O gate é auto-declaração por design: ele confia no que a pessoa registra. É um controle interno, não uma barreira contra a própria JEM. A aprovação com hash existe pra endurecer projetos sensíveis. O rate-limit e o ritmo humano reduzem o risco de derrubar ou irritar o site, mas não substituem o bom senso sobre o que é razoável scrapear.
