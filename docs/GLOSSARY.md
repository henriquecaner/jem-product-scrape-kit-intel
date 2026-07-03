# Glossário e perguntas frequentes

## Glossário

Gate de compliance: a checagem de autorização que roda antes e durante o scraping. Se a autorização falta, venceu, ou o robots proíbe, ele para.

Warm-up (reconhecimento): uma volta de teste numa amostra pequena (10 a 50 produtos) antes do run cheio, pra descobrir como o site se comporta.

Veredito (verde / ajustar / pedir ajuda): o resultado da revisão do warm-up. Só verde libera o run, e o verde tem validade e vale só pro site revisado. No arquivo que o motor confere, os três aparecem em inglês: `green`, `adjust`, `ask`.

Adaptador do site (`site_adapter.py`): a parte específica de cada site, que sabe descobrir as páginas de produto e ler os campos delas. O assistente escreve esse arquivo quando cria o projeto; o resto do motor é igual pra todo site.

SPA (site renderizado por JavaScript): um site cujo conteúdo só aparece depois que o navegador executa JavaScript. O fetch simples vê a página vazia; precisa do modo navegador.

Modo navegador (`fetch_mode: browser`): usa o Playwright pra abrir a página num navegador de verdade e enxergar o conteúdo que só aparece com JavaScript.

Proxy de país: um intermediário que faz a requisição sair de um país específico, pra sites que só mostram conteúdo (ou preço) pra visitantes de certo país. Vale tanto pro fetch simples quanto pro navegador (e pra própria captura de sessão).

Sessão autenticada (`storage_state`): o login capturado uma vez na sua máquina — os cookies e o estado que provam que você está logado. Fica salvo em `.scrape-session.json` (protegido, nunca vai pro Git) e é reusado nos runs seguintes, inclusive nos agendados.

Captura de sessão (`auth_capture.py`): o comando que abre um navegador de verdade na sua máquina pra você logar no site; ao terminar, salva a sessão e mostra o comando pra subir ela como secret do Actions. A captura é sempre local; nada loga sozinho no servidor.

Token expirado: a sessão de login tem prazo (horas, não dias). Quando expira no meio de um run, o motor para na hora e avisa, em vez de coletar a página de login como se fosse produto. O conserto é recapturar a sessão.

Registro canônico: o formato padrão da JEM pra um produto, pra onde todo dado cru é convertido. É versionado, pra não quebrar as ferramentas que consomem depois.

Banda de preço: um mesmo produto pode ter vários preços marcados por banda (por exemplo, um preço de cliente específico e um universal). A config diz qual banda ganha.

Estoque de hub: quando várias localizações são o mesmo armazém espelhado, somar dobraria o estoque. O plugin pega o máximo entre elas, não a soma.

Checkpoint (cursor): o ponto até onde o run já foi. Se cair no meio, retoma daí em vez de recomeçar.

Runtime: onde o scraping roda. Local (sua máquina) ou GitHub Actions (agendado, sozinho).

Plano do run: o resumo que o assistente monta antes do run cheio, com escopo, tempo estimado, custo e riscos. Tudo vem do que o warm-up mediu no site, não de chute. Pra projetos que exigem aprovação, é esse documento que o aprovador revisa.

Relatório do run (`exports/scrape_manifest.json`): a prestação de contas de um run — quantas páginas deram certo, quantas foram puladas e quantas deram erro.

Auditoria: a conferência de cobertura e qualidade depois do run, feita pelo agente `scrape-run-auditor`. Diz se o dataset é confiável antes de ir pra loja, ou se vale re-scrapear uma parte.

## Perguntas frequentes

Por que o plugin bloqueou meu scraping? Provavelmente o site é concorrente público e o robots.txt proíbe as páginas que você quer. Nesse caso é pra parar; não tem workaround.

Preciso de login no site? Pra sites públicos, não. Pra sites que exigem conta, sim, e isso é suportado: você loga uma vez na sua máquina (o `auth_capture.py` abre uma janela de navegador), a sessão é salva e reusada nos runs seguintes. Quando o token expira, o motor para e avisa; é só recapturar. O login é sempre feito por você, localmente.

Por que está lento? De propósito. O plugin roda pausado e uma requisição por vez, pra não derrubar nem irritar o site (e não queimar a conta). O tempo é dominado por esse ritmo, não pela velocidade da internet.

Quanto tempo demora? Depende do tamanho do catálogo: no ritmo padrão, mil produtos levam algumas horas. O plano do run traz a estimativa pro seu caso, medida no warm-up.

O CSV abre no Excel? Sim, e sem os furos comuns: sem linhas em branco entre produtos, e sem transformar um texto em fórmula por acidente.

Perdi a conexão no meio. Recomeça tudo? Não. O plugin guarda um checkpoint e retoma de onde parou.

O site é SPA e o warm-up pediu ajuda. E agora? O site precisa do modo navegador. Peça pra TI instalar o Playwright; o assistente refaz o warm-up no modo navegador.

Onde fica o resultado? Em `exports/`: o `products.csv` e a pasta `wiki/`. Ficam versionados no projeto.

Isso é permitido? O plugin te ajuda a respeitar o robots.txt e a registrar a autorização, mas a decisão sobre o que é razoável scrapear é da JEM. Veja o [guia de compliance](FOR-APPROVERS.md).
