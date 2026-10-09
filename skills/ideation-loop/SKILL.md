---
name: ideation-loop
description: Pipeline de ideação que gera ideias realmente não óbvias e as filtra contra a realidade, em vez de brainstorm de uma passada. Use sempre que o usuário pedir ideias novas, "algo que não existe", features inéditas, o que construir a seguir, como resolver um problema de produto ou de engenharia de forma não óbvia, como diferenciar um produto, ou quando pedir para o modelo "estudar" um tema e propor algo. Use também para descoberta de algoritmo/otimização com métrica mensurável (latência, custo, acurácia, taxa de acerto de um agente), onde roda em modo evolutivo com avaliador executável. Prefira esta skill a responder com uma lista de ideias direto do modelo.
---

# Ideation Loop

Ideias de LLM numa passada saem típicas (mode collapse do pós-treino) e o modelo julga mal a própria novidade. O que funciona é sistema: **gerar muito com diversidade forçada, colapsar duplicatas, checar anterioridade com busca real e selecionar com um avaliador que não seja o próprio gerador**, de preferência um sinal do mundo real (dado, teste, benchmark). Esta skill implementa esse loop.

Princípio que guia todas as decisões abaixo: **novidade vem da distância (lentes, cauda da distribuição, dado privado); qualidade vem do avaliador.** Nunca peça ao mesmo agente para gerar e julgar.

## Quando rodar e com qual tamanho

| Modo | Lentes | Candidatos por lente | Mutação | Quando |
|---|---|---|---|---|
| `rapido` | 3 | 8 | não | dúvida pontual, quer direção em minutos |
| padrão | 6 | 12 | 1 rodada | problema real de produto ou arquitetura |
| `profundo` | 7 | 20 | 2 rodadas | aposta grande, vale gastar tokens |
| `evolutivo` | ver `references/modo-evolutivo.md` | | | existe métrica executável (código, prompt, query, heurística) |

Se o usuário não disser, use padrão. Se o problema tem uma métrica que um script consegue calcular, use `evolutivo`: é onde LLM mais gera coisa genuinamente nova, porque o avaliador é objetivo.

Workspace: crie `.ideation/<slug-do-problema>/` na raiz do projeto (ou no diretório atual; se o projeto for somente leitura, em qualquer diretório fora dele). Tudo que for gerado vai lá, para o usuário poder auditar cada etapa; scripts de medição e de teste que você escrever ficam em `eval/` dentro dele. Os scripts da skill ficam em `scripts/` desta skill. Use caminho absoluto para os scripts e para o workspace: os comandos abaixo mostram `.ideation/<slug>` só para caber na linha.

## Fase 0. Enquadrar e definir o avaliador ANTES de gerar

Escreva `brief.md` com:

1. **Problema** em uma frase operacional. "Melhorar retenção" é vago; "usuários do plano mensal cancelam entre o dia 20 e 35, quero reduzir isso" é operacional. Se o pedido for vago e o usuário estiver presente, faça uma pergunta de uma linha; se não estiver, assuma a leitura mais razoável e registre no brief.
2. **Objetivo**: `novidade` (o usuário quer o que ainda não existe) ou `melhoria` (o usuário quer as mudanças de maior alavancagem, e uma ideia conhecida que funciona serve). Na dúvida entre os dois, é `melhoria`. O objetivo muda as Fases 1, 3, 4 e 8, e cada uma diz como.
3. **Sinal privado**: o que só este projeto sabe. Investigue de verdade antes de gerar: leia o schema do banco, models, rotas, logs, métricas, issues, README, docs internos. Se houver acesso a dados (Postgres, CSV, analytics), rode queries agregadas e registre os fatos com números. Esta é a parte mais importante da fase: o modelo já conhece a internet; o que produz ideia nova é a conjunção do conhecimento público com fatos que ele não viu no treino. Liste de 5 a 15 fatos numerados, cada um marcado `[verificado: como]` ou `[suposição]`.
4. **Restrições reais**: stack, tempo, orçamento, quem constrói (frequentemente uma pessoa só).
5. **Avaliador**: como uma ideia vai ser provada ou morta. Leia `references/avaliadores.md` e escolha o mais forte disponível. Se não existir avaliador melhor que opinião, diga isso no brief; o relatório final vai carregar essa limitação.

Não pule o avaliador. Sem ele o loop vira brainstorm caro.

## Fase 1. Mapear o óbvio

Gere de 15 a 20 ideias que qualquer especialista da área daria em cinco minutos, o consenso. Salve em `obvious.jsonl`, um JSON por linha com `id`, `titulo`, `mecanismo` e `"lente": "obvio"`. O `mecanismo` tem de 2 a 4 frases como o dos candidatos: texto curto demais não se compara com nada. Os outros campos do schema só são necessários para as ideias óbvias que forem competir (Fase 3). As lentes recebem a lista como "já pensado, não repita".

Com objetivo `novidade`, o óbvio é só régua. Com objetivo `melhoria`, o óbvio também compete: várias dessas ideias são boas, e deixá-las de fora faz o loop devolver a segunda melhor resposta.

## Fase 2. Geração divergente em paralelo

Leia `references/lentes.md`. Cada lente do modo escolhido roda num subagente independente (ferramenta Agent), que não vê a saída das outras; independência é o que garante diversidade.

Todos os subagentes de uma mesma leva recebem **o mesmo prompt, byte a byte**, e pegam a lente de um script. Faça assim:

1. Monte as tarefas com `python3 <skill>/scripts/tasks.py <workspace> --modo <rapido|padrao|profundo>`. O script lê `lentes.md` e escreve um arquivo por lente em `tarefas/` (e em `tarefas-menor/` as lentes do modelo menor), com brief, óbvio, instruções, schema e arquivo de saída. `--areas` é opcional e divide a lente `anomalia` em um subagente por área do projeto (por exemplo "código e schema" e "dados, logs e histórico"). Use em projeto grande: dois agentes acham mais fatos do que um, mas a rodada não fica mais rápida, porque cada um investiga pelo tempo que tiver. Se o problema pedir uma instrução diferente, edite o arquivo da tarefa.
2. O prompt de todos é só o que o script imprime: `Rode python3 <skill>/scripts/claim.py <workspace>/tarefas e siga o que ele imprimir.`
3. Dispare **um** subagente, e os demais na mensagem seguinte, juntos. As tarefas saem em ordem, e a primeira é a da anomalia. Quando as tarefas acabam, o `claim.py` responde `nenhuma tarefa livre`.

O motivo da largada em duas mensagens: cada subagente abre com dezenas de milhares de tokens de contexto fixo do ambiente. Com prompt idêntico, do segundo em diante esse contexto é lido do cache em vez de recriado, o que custa uma fração. Disparados no mesmo instante, nenhum aproveita o cache do outro.

Diversidade de modelo: rode duas das lentes com um modelo menor (`model: "haiku"` ou equivalente disponível). O AlphaEvolve observou que um modelo mais fraco injeta variância útil e evita que a busca fique presa refinando uma ideia só. O cache não passa de um modelo para outro, então as tarefas do modelo menor ficam em `tarefas-menor/`, com a mesma largada em duas mensagens.

Sem subagentes disponíveis (ex.: claude.ai sem Agent), monte as tarefas com `--sem-subagentes` (uma pasta só) e rode as lentes em sequência você mesmo, pegando cada uma com o `claim.py` e escrevendo cada arquivo antes de começar a próxima. As lentes anteriores ficam no seu contexto, então a independência é menor: diga isso nas limitações do relatório.

O `claim.py` renomeia a tarefa entregue para `.tomada`. Se uma lente falhar, renomeie o arquivo de volta para `.md` e dispare de novo.

Schema de cada linha (JSON por linha, e nada além de JSON no arquivo):

```json
{"id": "analogia-07", "titulo": "...", "mecanismo": "como funciona, 2 a 4 frases concretas", "insight": "o fato não óbvio que a ideia explora", "lente": "analogia:seguros", "dado_usado": "qual fato do brief sustenta, ou null", "teste_barato": "como provar ou matar em menos de um dia", "criterio_de_morte": "resultado do teste que mata a ideia"}
```

Uma lente que investiga o projeto e descobre um fato que não está no brief grava também uma linha de fato no mesmo arquivo: `{"fato": "...", "como_verificou": "comando ou arquivo"}`.

## Fase 3. Colapsar duplicatas e medir distância

```bash
python3 <skill>/scripts/cluster.py queue .ideation/<slug>/candidates/*.jsonl --obvious .ideation/<slug>/obvious.jsonl --out .ideation/<slug>
```

O script valida os arquivos e escreve:

- `suspeitos.md`: a fila de pares que podem ser a mesma ideia (os 3 vizinhos mais parecidos de cada candidato) e o item do óbvio mais próximo de cada candidato.
- `facts.jsonl`: os fatos novos que as lentes acharam. Leia todos. Fato novo é sinal privado que o brief não tinha; acrescente ao brief os que importam e use-os no corte e na Fase 5.
- `survivors.jsonl`: todos os candidatos válidos, com `sim_obvio`.

Espere muita duplicata entre lentes: lentes diferentes chegam à mesma ideia com outras palavras, e de um terço a metade dos candidatos costuma ser repetição. A similaridade do script é lexical: ela ordena bem os pares parecidos e não decide se são a mesma ideia. Quem decide é você. Leia `suspeitos.md`, marque `[x]` nos pares que são a mesma ideia e acrescente no mesmo formato as duplicatas que a fila não trouxe. A fila vem ordenada da maior similaridade para a menor, e as duplicatas se concentram no começo. Na seção "Contra o óbvio", marque o candidato que é a ideia de consenso com outra redação: `perto_do_obvio` só fica verdadeiro por essa marca, porque a similaridade lexical contra o óbvio só pega paráfrase quase literal. Depois:

```bash
python3 <skill>/scripts/cluster.py merge --out .ideation/<slug>
```

O `merge` funde os grupos, grava em cada sobrevivente o campo `fusao` (quem ele absorveu) e `lentes_no_grupo`, e escreve `clusters.md`. O representante de cada grupo é o membro mais distante do óbvio, que nem sempre tem a melhor redação: se o título e o mecanismo de outro membro descrevem melhor a ideia, copie-os para a linha do representante em `survivors.jsonl`. É esse texto que o juiz vai ler. Uma ideia a que várias lentes chegaram sozinhas é provavelmente menos distante do que parece: leve isso em conta antes de escrever "não óbvio" no relatório.

Corte para no máximo 15 sobreviventes (rapido: 8) apagando linhas de `survivors.jsonl`, e registre em `cortes.md` uma linha por corte, `- <id>: <motivo>`. Com objetivo `novidade`, descarte os `perto_do_obvio` a menos que o mecanismo seja claramente diferente. Com objetivo `melhoria`, copie para `survivors.jsonl` as ideias de `obvious.jsonl` que merecem competir, completando `teste_barato` e `criterio_de_morte` (essas linhas ficam sem os campos do cluster, e tudo bem). Ao cortar, prefira as ideias apoiadas em fato verificado do brief ou de `facts.jsonl`.

## Fase 4. Anterioridade com busca real

Para cada sobrevivente, faça de 2 a 3 buscas na web com termos diferentes (o nome provável do produto, o mecanismo descrito com outras palavras, o problema + "startup" ou "paper" ou "github"). Dispare a busca num subagente em segundo plano e comece a Fase 5 enquanto ele trabalha: as duas fases não dependem uma da outra, e esperar a busca parado é o maior tempo morto da rodada. Registre em `prior_art.md`:

- `existe`: link do produto ou paper que faz essencialmente isso. Com objetivo `novidade`, a ideia só segue se o brief tiver uma vantagem concreta sobre o existente (dado, distribuição, custo). Com objetivo `melhoria`, existir conta a favor: registre o resultado que quem já fez mediu, com a fonte, e o que dá para reusar em vez de construir.
- `parcial`: existe algo vizinho; anote a diferença.
- `não encontrado`: liste as queries usadas.

Formato de `prior_art.md`: uma seção curta por sobrevivente (`## <id>`), com a classificação, os links com uma linha cada, a diferença em uma linha e as queries. O juiz não lê esse arquivo: o que a busca achou de relevante entra em `evidence/<id>.md` numa linha `anterioridade: <classificação>, <o que existe e o que mediu>`, logo depois da linha do veredito (Fase 5).

Com objetivo `novidade`, a ideia classificada como `existe` sem vantagem concreta sai antes do julgamento: apague a linha de `survivors.jsonl` e registre em `cortes.md` com o link. O ranking não olha anterioridade, então quem não for cortada aqui compete normalmente.

Sem subagentes disponíveis, faça as buscas você mesmo antes dos testes.

Registre também o que a busca achar que contradiz a premissa de uma ideia: é o resultado mais útil desta fase, e costuma virar o desenho do teste da Fase 5.

Nunca escreva "inédito" ou "ninguém fez". O máximo que a evidência permite é "não encontrado nestas N buscas: ...". Benchmarks recentes mostram que LLMs julgam novidade de forma pouco confiável mesmo quando o raciocínio parece bom, então a busca é o juiz aqui, não a sua impressão.

## Fase 5. Avaliar contra a realidade

Para cada sobrevivente, execute o `teste_barato` quando ele for executável agora: query no banco, script sobre logs, protótipo descartável, spike de código, cálculo de custo com preço real. O teste que a lente escreveu é uma proposta feita sem olhar os dados: você pode trocá-lo por um melhor. Se o teste novo pede outro critério de morte, escreva o critério novo em `evidence/<id>.md` antes de rodar; depois de ver o resultado, o critério não muda. Salve cada execução em `evidence/<id>.md` com o comando e o resultado. Se o teste depende do usuário (falar com cliente, landing page), registre como pendente com o roteiro pronto.

A primeira linha de conteúdo de cada `evidence/<id>.md` é o veredito, neste vocabulário fechado:

- `veredito: sustentada`: o teste rodou e o sinal apareceu.
- `veredito: parcial`: uma parte da ideia foi verificada e outra não.
- `veredito: fraca`: o teste rodou e o sinal é ambíguo ou a amostra é pequena demais.
- `veredito: nao_testada`: não havia como testar agora.
- `veredito: morta`: o teste rodou e bateu no critério de morte. Mantenha no relatório com o motivo; ideias mortas com motivo claro também são resultado.

Ao citar outra ideia na evidência, use o id dela: o script troca ids de sobreviventes por "(outra ideia)" no baralho do juiz. Id de outra rodada precisa de prefixo (`R1:anomalia-04`) para não ser confundido com um desta.

O veredito ordena o ranking final, e quem escolhe quais ideias recebem teste é você. Então a ordem em que você testa decide boa parte do resultado: dê a toda sobrevivente ao menos um teste rápido antes de aprofundar o de qualquer uma, e não comece a implementar a sua favorita antes do julgamento.

## Fase 6. Julgamento em lista cega

```bash
python3 <skill>/scripts/tournament.py decks .ideation/<slug>/survivors.jsonl --evidence .ideation/<slug>/evidence --brief .ideation/<slug>/brief.md --out .ideation/<slug>/juiz-1
```

O script gera um baralho por juiz (2 por padrão) em `juiz-1/tarefas/deck<k>.md`: as mesmas ideias com códigos neutros e ordem diferentes em cada baralho, sem lente de origem, com a evidência embutida. Dispare um subagente **juiz que não participou da geração** por baralho, todos com o prompt que o script imprime. Use modelos diferentes para os dois juízes quando houver (por exemplo, um do modelo principal e um do menor): juízes do mesmo modelo concordam entre si mais do que com um juiz de outro modelo, então dois iguais escondem discordância que existe. Com modelos diferentes não há cache a aproveitar e os dois podem largar juntos; com o mesmo modelo, um primeiro e o outro na mensagem seguinte. Cada juiz devolve uma lista ordenada com motivo, maior risco e o que faria a ideia subir. Novidade não é critério do juiz; ela já foi tratada por distância e busca.

Não peça comparações par a par. O juiz ordena todas as ideias de uma vez e deriva os pares dessa ordem, então o par a par só acrescenta o ruído de quem enfrentou quem.

```bash
python3 <skill>/scripts/tournament.py agree .ideation/<slug>/juiz-1 --survivors .ideation/<slug>/survivors.jsonl --evidence .ideation/<slug>/evidence --out .ideation/<slug>/ranking.md
```

O `agree` monta o `ranking.md` (e o mesmo conteúdo em `ranking.json`): a ordem segue o veredito de evidência e, dentro do mesmo veredito, a posição média dos juízes. Ele também mede a concordância entre os juízes dentro do mesmo veredito, que é onde o juiz decide de fato (na lista inteira o número sai inflado, porque todos seguem a evidência). Ideias vizinhas com o mesmo veredito sobre as quais os juízes discordam saem na mesma faixa: estão empatadas, e o relatório as apresenta como empate, sem inventar ordem. Com concordância baixa, a ordem inteira dentro de cada veredito é hipótese, e o relatório precisa dizer isso. Se uma lista vier incompleta ou um juiz não entregar, o script recusa: peça ao juiz para refazer.

Se a evidência de uma ideia mudar depois do julgamento, o ranking ficou velho: rode `agree` de novo (o veredito é relido) antes de escrever o relatório.

Sem subagentes disponíveis, gere um baralho só (`--n 1`), ordene você mesmo e declare no relatório que o juiz foi o próprio gerador. Dois baralhos ordenados pelo mesmo agente concordam sempre e não medem nada.

## Fase 7. Mutação (padrão: 1 rodada, profundo: 2)

O `ranking.md` termina com as fichas das 4 primeiras, incluindo o `para_vencer` de cada juiz. Gere as variações a partir delas: aplicar o `para_vencer`, combinar dois finalistas, remover o componente mais caro, separar a parte já provada da parte não provada. Cada mutação entra em `survivors.jsonl` com `"pais": [ids]` e passa pelas Fases 4 a 6 competindo com os pais (use `--out .ideation/<slug>/juiz-2` para os novos baralhos). Pare quando a rodada não produzir nenhum novo top 3.

## Fase 8. Relatório

Escreva `report.md` e mostre ao usuário apenas o essencial na conversa. Estrutura:

```markdown
# <problema>

Avaliador usado: <qual> | Objetivo: <novidade ou melhoria> | Candidatos gerados: N | Sobreviventes: M | Modo: <modo> | Juízes: <quantos, quais modelos, independentes do gerador: sim ou não>

## Top 3 a 5
### 1. <título>
- Mecanismo: ...
- Por que não é óbvio: <insight + distância do óbvio> (com objetivo melhoria: "Por que esta e não outra", com a alavancagem)
- Evidência: [sustentada | parcial | fraca | nao_testada] <o que rodou e o que deu>
- Anterioridade: <existe/parcial/não encontrado + links ou queries>
- Próximo teste: <o que fazer amanhã, em quanto tempo>
- Mata se: <critério>

## Interações entre as ideias
<quais atacam o mesmo ponto e não somam, quais dependem de outra>

## Fracas e não testadas
<título: o que falta para testar, em uma linha>

## Mortas que valem registro
<título: motivo em uma linha>

## Limitações desta rodada
<o que não foi verificado, onde o avaliador foi fraco, concordância entre os juízes>
```

Honestidade no relatório: separe o que foi verificado do que é hipótese, use números só quando vierem de uma consulta real, e se nenhuma ideia ficou de pé, diga isso. Um "nada sobreviveu, e o motivo é X" vale mais do que três ideias infladas.

## Regras que valem para todas as fases

- Quem gera não julga. Gerador e juiz são agentes diferentes.
- Ideias ancoradas em dado privado verificado pesam mais do que ideias genéricas brilhantes.
- Não invente fatos, números, APIs ou produtos concorrentes. Se não verificou, marque como suposição.
- Ações caras ou irreversíveis (escrever em banco de produção, gastar dinheiro, enviar algo a cliente) ficam fora do loop: prepare e peça confirmação.
