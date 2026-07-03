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

## Scraping autenticado

Alguns sites só mostram o catálogo, ou o preço real, pra quem está logado. O plugin cobre esse caso, e ele muda a conversa de compliance de um jeito que vale conhecer antes de aprovar.

Num scrape autenticado, o motor não faz um acesso anônimo: ele reusa uma sessão de login capturada na máquina de quem opera. Três pontos pesam na decisão:

- O tipo de relação importa mais aqui. Usar um login num site de concorrente público é um sinal bem mais forte do que scraping público, e pede escrutínio extra. Login costuma fazer sentido em fornecedor contratado ou conta própria, não em concorrente.
- A sessão é uma credencial de verdade, não um acesso anônimo. O arquivo capturado (`.scrape-session.json`) carrega o login ativo: fica com permissão restrita (0600), fora do Git, e o hook de segurança barra commit acidental. Ele tem prazo próprio (horas), separado da validade da autorização.
- A captura é local e feita por uma pessoa. Só a máquina de quem opera loga; o servidor nunca loga sozinho. Quando o token expira no meio do run, o motor para e avisa, em vez de seguir cego coletando a página de login.

## O plano do run (o que você aprova)

Antes do run cheio, o plugin gera um plano com escopo, tempo estimado, custo e riscos, tudo baseado no que o warm-up encontrou no site, não em chute. Pra projetos que exigem aprovação, esse plano é o documento que você revisa e assina.

A autorização tem um campo `requires_approval`. Quando ele é verdadeiro, o assistente só segue depois de registrar a aprovação (um marcador com o hash do plano e quem aprovou). Assim a aprovação fica amarrada a um plano específico, não a "um plano qualquer".

Um limite pra deixar claro: hoje essa trava é do processo, não do motor. O assistente exige o registro antes de rodar, mas os gates que o motor verifica sozinho, em runtime, são dois: a autorização e o veredito do warm-up. O arquivo de aprovação ainda não é verificado pelo motor.

## O que fica registrado

- A autorização (`.scrape-authorization.json`): tipo, quem autorizou, quando, validade, escopo, status do robots. Fica fora do Git, por ser sensível.
- O veredito do warm-up (`.scrape-warmup.json`): o sinal verde que libera o run, com validade e domínio.
- O plano do run e, se exigido, a aprovação com hash.

## O que conferir antes de aprovar

- O tipo de relação declarado bate com a realidade? Se diz "fornecedor contratado", o contrato existe; se diz "conta própria", a conta é mesmo da JEM.
- O escopo do plano cobre só o que foi pedido (categorias, marcas), sem sobra?
- O status do robots.txt está registrado? Se for override de fornecedor, a referência do contrato (`robots_override_ref`) está preenchida?
- A validade (`expires_at`) é curta o bastante pro caso? Autorização não é pra sempre; quando vence, o motor volta a bloquear.

## Limites honestos

O gate é auto-declaração por design: ele confia no que a pessoa registra. É um controle interno, não uma barreira contra a própria JEM. A aprovação com hash existe pra endurecer projetos sensíveis. O rate-limit e o ritmo humano reduzem o risco de derrubar ou irritar o site, mas não substituem o bom senso sobre o que é razoável scrapear.
