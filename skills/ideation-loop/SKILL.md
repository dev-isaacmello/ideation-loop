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

Workspace: crie `.ideation/<slug-do-problema>/` na raiz do projeto (ou no diretório atual). Tudo que for gerado vai lá, para o usuário poder auditar cada etapa. Os scripts ficam em `scripts/` desta skill; chame-os pelo caminho absoluto da skill.

## Fase 0. Enquadrar e definir o avaliador ANTES de gerar

Escreva `brief.md` com:

1. **Problema** em uma frase operacional. "Melhorar retenção" é vago; "usuários do plano mensal cancelam entre o dia 20 e 35, quero reduzir isso" é operacional. Se o pedido for vago e o usuário estiver presente, faça uma pergunta de uma linha; se não estiver, assuma a leitura mais razoável e registre no brief.
2. **Objetivo**: `novidade` (o usuário quer o que ainda não existe) ou `melhoria` (o usuário quer as mudanças de maior alavancagem, e uma ideia conhecida que funciona serve). Na dúvida entre os dois, é `melhoria`. O objetivo muda as Fases 1, 3, 4 e 8, e cada uma diz como.
3. **Sinal privado**: o que só este projeto sabe. Investigue de verdade antes de gerar: leia o schema do banco, models, rotas, logs, métricas, issues, README, docs internos. Se houver acesso a dados (Postgres, CSV, analytics), rode queries agregadas e registre os fatos com números. Esta é a parte mais importante da fase: o modelo já conhece a internet; o que produz ideia nova é a conjunção do conhecimento público com fatos que ele não viu no treino. Liste de 5 a 15 fatos numerados, cada um marcado `[verificado: como]` ou `[suposição]`.
4. **Restrições reais**: stack, tempo, orçamento, quem constrói (frequentemente uma pessoa só).
5. **Avaliador**: como uma ideia vai ser provada ou morta. Leia `references/avaliadores.md` e escolha o mais forte disponível. Se não existir avaliador melhor que opinião, diga isso no brief; o relatório final vai carregar essa limitação.

Não pule o avaliador. Sem ele o loop vira brainstorm caro.

## Fase 1. Mapear o óbvio

Gere de 15 a 20 ideias que qualquer especialista da área daria em cinco minutos, o consenso. Salve em `obvious.jsonl` (mesmo schema dos candidatos, `"lente": "obvio"`), com `mecanismo` de 2 a 4 frases como o dos candidatos: texto curto demais não se compara com nada. As lentes recebem a lista como "já pensado, não repita".

Com objetivo `novidade`, o óbvio é só régua. Com objetivo `melhoria`, o óbvio também compete: várias dessas ideias são boas, e deixá-las de fora faz o loop devolver a segunda melhor resposta.

## Fase 2. Geração divergente em paralelo

Leia `references/lentes.md`. Cada lente do modo escolhido roda num subagente independente (ferramenta Agent), que não vê a saída das outras; independência é o que garante diversidade.

Todos os subagentes de uma mesma leva recebem **o mesmo prompt, byte a byte**, e pegam a lente de um script. Faça assim:

1. Para cada lente, escreva `tarefas/<lente>.md` com tudo que o subagente precisa: caminho do `brief.md` e do `obvious.jsonl`, a instrução comum e a instrução da lente (de `lentes.md`), o número de candidatos e o caminho de saída `candidates/<lente>.jsonl`.
2. O prompt de todos é só: `Rode python3 <skill>/scripts/claim.py <workspace>/tarefas e siga o que ele imprimir.`
3. Dispare **um** subagente, e os demais na mensagem seguinte, juntos.

O motivo da largada em duas mensagens: cada subagente abre com dezenas de milhares de tokens de contexto fixo do ambiente. Com prompt idêntico, do segundo em diante esse contexto é lido do cache em vez de recriado, o que custa uma fração. Disparados no mesmo instante, nenhum aproveita o cache do outro.

Diversidade de modelo: rode duas das lentes com um modelo menor (`model: "haiku"` ou equivalente disponível). O AlphaEvolve observou que um modelo mais fraco injeta variância útil e evita que a busca fique presa refinando uma ideia só. O cache não passa de um modelo para outro, então ponha as tarefas do modelo menor em `tarefas-menor/` e repita a largada em duas mensagens para elas.

Sem subagentes disponíveis (ex.: claude.ai sem Agent), rode as lentes em sequência você mesmo, pegando cada uma com o `claim.py`, escrevendo cada arquivo antes de começar a próxima e sem reler as anteriores.

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

Espere muita duplicata entre lentes: lentes diferentes chegam à mesma ideia com outras palavras, e de um terço a metade dos candidatos costuma ser repetição. A similaridade do script é lexical: ela ordena bem os pares parecidos e não decide se são a mesma ideia. Quem decide é você. Leia `suspeitos.md`, marque `[x]` nos pares que são a mesma ideia e acrescente no mesmo formato as duplicatas que a fila não trouxe. Na seção "Contra o óbvio", marque o candidato que é a ideia de consenso com outra redação. Depois:

```bash
python3 <skill>/scripts/cluster.py merge --out .ideation/<slug>
```

O `merge` funde os grupos, grava em cada sobrevivente o campo `fusao` (quem ele absorveu) e `lentes_no_grupo`, e escreve `clusters.md`. Uma ideia a que várias lentes chegaram sozinhas é provavelmente menos distante do que parece: leve isso em conta antes de escrever "não óbvio" no relatório.

Corte para no máximo 15 sobreviventes (rapido: 8) apagando linhas de `survivors.jsonl`, e registre cada corte com o motivo em uma linha em `cortes.md`. Com objetivo `novidade`, descarte os `perto_do_obvio` a menos que o mecanismo seja claramente diferente. Com objetivo `melhoria`, copie para `survivors.jsonl` as ideias de `obvious.jsonl` que merecem competir. Ao cortar, prefira as ideias apoiadas em fato verificado do brief ou de `facts.jsonl`.

## Fase 4. Anterioridade com busca real

Para cada sobrevivente, faça de 2 a 3 buscas na web com termos diferentes (o nome provável do produto, o mecanismo descrito com outras palavras, o problema + "startup" ou "paper" ou "github"). Use subagentes em paralelo quando houver muitos. Registre em `prior_art.md`:

- `existe`: link do produto ou paper que faz essencialmente isso. Com objetivo `novidade`, a ideia só segue se o brief tiver uma vantagem concreta sobre o existente (dado, distribuição, custo). Com objetivo `melhoria`, existir conta a favor: registre o resultado que quem já fez mediu, com a fonte, e o que dá para reusar em vez de construir.
- `parcial`: existe algo vizinho; anote a diferença.
- `não encontrado`: liste as queries usadas.

Registre também o que a busca achar que contradiz a premissa de uma ideia: é o resultado mais útil desta fase, e costuma virar o desenho do teste da Fase 5.

Nunca escreva "inédito" ou "ninguém fez". O máximo que a evidência permite é "não encontrado nestas N buscas: ...". Benchmarks recentes mostram que LLMs julgam novidade de forma pouco confiável mesmo quando o raciocínio parece bom, então a busca é o juiz aqui, não a sua impressão.

## Fase 5. Avaliar contra a realidade

Para cada sobrevivente, execute o `teste_barato` quando ele for executável agora: query no banco, script sobre logs, protótipo descartável, spike de código, cálculo de custo com preço real. Salve cada execução em `evidence/<id>.md` com o comando e o resultado. Se o teste depende do usuário (falar com cliente, landing page), registre como pendente com o roteiro pronto.

A primeira linha de conteúdo de cada `evidence/<id>.md` é o veredito, neste vocabulário fechado:

- `veredito: sustentada`: o teste rodou e o sinal apareceu.
- `veredito: parcial`: uma parte da ideia foi verificada e outra não.
- `veredito: fraca`: o teste rodou e o sinal é ambíguo ou a amostra é pequena demais.
- `veredito: nao_testada`: não havia como testar agora.
- `veredito: morta`: o teste rodou e bateu no critério de morte. Mantenha no relatório com o motivo; ideias mortas com motivo claro também são resultado.

O veredito ordena o ranking final, e quem escolhe quais ideias recebem teste é você. Então a ordem em que você testa decide boa parte do resultado: dê a toda sobrevivente ao menos um teste rápido antes de aprofundar o de qualquer uma, e não comece a implementar a sua favorita antes do julgamento.

## Fase 6. Julgamento em lista cega

```bash
python3 <skill>/scripts/tournament.py decks .ideation/<slug>/survivors.jsonl --evidence .ideation/<slug>/evidence --brief .ideation/<slug>/brief.md --out .ideation/<slug>/juiz-1
```

O script gera um baralho por juiz (2 por padrão): as mesmas ideias com códigos neutros e ordem diferentes em cada baralho, sem lente de origem, com a evidência embutida. Dispare um subagente **juiz que não participou da geração** por baralho (se possível, um deles de outro modelo), todos com o prompt que o script imprime, da mesma forma que as lentes: um primeiro, os demais na mensagem seguinte. Cada juiz devolve uma lista ordenada com motivo, maior risco e o que faria a ideia subir. Novidade não é critério do juiz; ela já foi tratada por distância e busca.

Não peça comparações par a par. O juiz ordena todas as ideias de uma vez e deriva os pares dessa ordem, então o par a par só acrescenta o ruído de quem enfrentou quem.

```bash
python3 <skill>/scripts/tournament.py agree .ideation/<slug>/juiz-1 --survivors .ideation/<slug>/survivors.jsonl --evidence .ideation/<slug>/evidence --out .ideation/<slug>/ranking.md
```

O `agree` monta o `ranking.md`: a ordem segue o veredito de evidência e, dentro do mesmo veredito, a posição média dos juízes. Ele também mede a concordância entre os juízes. Com concordância baixa, a ordem dentro de cada veredito é hipótese, e o relatório precisa dizer isso. Se uma lista vier incompleta, o script recusa: peça ao juiz para refazer.

Se a evidência de uma ideia mudar depois do julgamento, o ranking ficou velho: rode `agree` de novo (o veredito é relido) antes de escrever o relatório.

Sem subagentes disponíveis, gere os baralhos e ordene cada um você mesmo, em momentos separados, e declare no relatório que o juiz foi o próprio gerador.

## Fase 7. Mutação (padrão: 1 rodada, profundo: 2)

O `ranking.md` termina com as fichas das 4 primeiras, incluindo o `para_vencer` de cada juiz. Gere as variações a partir delas: aplicar o `para_vencer`, combinar dois finalistas, remover o componente mais caro, separar a parte já provada da parte não provada. Cada mutação entra em `survivors.jsonl` com `"pais": [ids]` e passa pelas Fases 4 a 6 competindo com os pais (use `--out .ideation/<slug>/juiz-2` para os novos baralhos). Pare quando a rodada não produzir nenhum novo top 3.

## Fase 8. Relatório

Escreva `report.md` e mostre ao usuário apenas o essencial na conversa. Estrutura:

```markdown
# <problema>

Avaliador usado: <qual> | Objetivo: <novidade ou melhoria> | Candidatos gerados: N | Sobreviventes: M | Modo: <modo>

## Top 3 a 5
### 1. <título>
- Mecanismo: ...
- Por que não é óbvio: <insight + distância do óbvio> (com objetivo melhoria: "Por que esta e não outra", com a alavancagem)
- Evidência: [sustentada | parcial | fraca | não testada] <o que rodou e o que deu>
- Anterioridade: <existe/parcial/não encontrado + links ou queries>
- Próximo teste: <o que fazer amanhã, em quanto tempo>
- Mata se: <critério>

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
