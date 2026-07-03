# O que é o jem-product-scrape-kit-intel

Um plugin do Claude Code que ajuda o time da JEM a trazer produtos de fornecedores e concorrentes pra loja, sem virar um projeto de engenharia e sem passar por cima de compliance.

## O problema que ele resolve

A JEM precisa de catálogos de produtos de outros sites: preço, descrição, especificações, imagens, estoque. Copiar na mão não escala, e scraping feito errado tem dois riscos. Um é pisar nas regras do site (robots.txt, termos de uso, conta banida). O outro é gerar dado ruim que polui a loja.

Antes, cada scraping era um script solto, feito do zero. Este plugin transforma isso numa base reutilizável: qualquer pessoa do time roda por um assistente que pergunta o que precisa e conduz o resto.

## Como funciona, por cima

Você aponta o plugin pra um site e ele conduz seis etapas, nessa ordem:

1. Gate de compliance. Lê o robots.txt do site e registra a autorização. Se for concorrente público e o robots proíbe, ele bloqueia e para. Isso não é opcional.
2. Warm-up (reconhecimento). Antes de gastar esforço no site inteiro, pega uma amostra de 10 a 50 produtos e descobre como o site se comporta: é uma página normal ou precisa de navegador? tem login? tem anti-bot? os campos vêm completos? Dois modelos revisam o resultado e dão o veredito. Só o "verde" libera o run de verdade.
3. Plano do run. Escopo, tempo estimado, custo e riscos, pra você (ou quem aprova) olhar antes.
4. Scrape. Roda num ritmo humano (pausado, uma requisição por vez) pra não derrubar nem irritar o site. Guarda um checkpoint, então dá pra retomar de onde parou.
5. Normalização. Transforma o dado cru no formato canônico da JEM: resolve estoque de vários armazéns, escolhe o preço certo por banda e junta variantes do mesmo produto.
6. Export. Sai um `products.csv` (pronto pra Excel, sem os furos clássicos) e uma wiki em markdown, organizada por categoria.

No fim, um auditor confere cobertura e qualidade antes do dado ir pra loja.

## O que faz dele diferente

Compliance é a primeira porta, não um aviso no rodapé. O gate roda no início e de novo durante o run, e é fail-closed: na dúvida, ele para, não continua.

O warm-up existe porque a gente aprendeu na prática. Testando um distribuidor, só descobrimos que o site era todo renderizado por JavaScript (e portanto invisível pro fetch simples) depois de já estar tentando. O warm-up mostra isso logo de cara, antes de gastar o run.

## Onde ele roda

- Local, na sua máquina, pra sites públicos e avulsos.
- No GitHub Actions, agendado, pra runs que precisam rodar sozinhos — com proxy de país quando o site é geo-restrito, e com login quando o site exige conta.

Você não precisa decidir isso sozinho: o assistente escolhe com você no começo do projeto, a partir do que você respondeu.

## O que está pronto e o que não está

Pronto: scraping de sites públicos (local e Actions), o warm-up, normalização e export, o onboarding de máquina, e scraping de sites com login com saída por IP do país. Pra sites com conta, você loga uma vez na sua máquina (uma janela de navegador abre), a sessão é reusada nos runs seguintes, e o run para e avisa quando o token expira.

Ainda não, e documentado pra depois: normalização assistida por IA e o plano do run em PDF (hoje o plano sai em markdown). A renovação do token continua sendo uma etapa manual sua (recapturar a sessão de tempos em tempos), e a promoção pra VM em casos de re-login interativo é dirigida pela TI.

## Próximo passo

Pra usar: [guia de setup da máquina](SETUP.md), depois o [primeiro scrape](GETTING-STARTED.md).
