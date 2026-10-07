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
2. **Sinal privado**: o que só este projeto sabe. Investigue de verdade antes de gerar: leia o schema do banco, models, rotas, logs, métricas, issues, README, docs internos. Se houver acesso a dados (Postgres, CSV, analytics), rode queries agregadas e registre os fatos com números. Esta é a parte mais importante da fase: o modelo já conhece a internet; o que produz ideia nova é a conjunção do conhecimento público com fatos que ele não viu no treino. Liste de 5 a 15 fatos, cada um marcado `[verificado: como]` ou `[suposição]`.
3. **Restrições reais**: stack, tempo, orçamento, quem constrói (frequentemente uma pessoa só).
4. **Avaliador**: como uma ideia vai ser provada ou morta. Leia `references/avaliadores.md` e escolha o mais forte disponível. Se não existir avaliador melhor que opinião, diga isso no brief; o relatório final vai carregar essa limitação.

Não pule o avaliador. Sem ele o loop vira brainstorm caro.

## Fase 1. Mapear o óbvio

Gere de 15 a 20 ideias que qualquer especialista da área daria em cinco minutos, o consenso. Salve em `obvious.jsonl` (mesmo schema dos candidatos, `"lente": "obvio"`). Elas não são descartadas por serem ruins (várias são boas), mas servem de régua: o script de dedup mede a distância de cada candidato até esse conjunto, e as lentes recebem a lista como "já pensado, não repita".

## Fase 2. Geração divergente em paralelo

Leia `references/lentes.md`. Para cada lente do modo escolhido, dispare **um subagente independente na mesma mensagem** (ferramenta Agent, chamadas em paralelo). Cada subagente recebe: o `brief.md` completo, o `obvious.jsonl`, o texto da sua lente, o número de candidatos e o caminho do arquivo de saída `candidates/<lente>.jsonl`. Ele não vê a saída das outras lentes; independência é o que garante diversidade.

Diversidade de modelo: rode duas das lentes com um modelo menor (`model: "haiku"` ou equivalente disponível). O AlphaEvolve observou que um modelo mais fraco injeta variância útil e evita que a busca fique presa refinando uma ideia só. O filtro de qualidade vem depois, então variância barata aqui é ganho.

Sem subagentes disponíveis (ex.: claude.ai sem Agent), rode as lentes em sequência você mesmo, escrevendo cada arquivo antes de começar a próxima e sem reler as anteriores.

Schema de cada linha (JSON por linha):

```json
{"id": "analogia-07", "titulo": "...", "mecanismo": "como funciona, 2 a 4 frases concretas", "insight": "o fato não óbvio que a ideia explora", "lente": "analogia:seguros", "dado_usado": "qual fato do brief sustenta, ou null", "teste_barato": "como provar ou matar em menos de um dia", "criterio_de_morte": "resultado do teste que mata a ideia", "p_verbalizada": 0.06}
```

Depois que todos terminarem, valide e junte:

```bash
python3 <skill>/scripts/cluster.py .ideation/<slug>/candidates/*.jsonl --obvious .ideation/<slug>/obvious.jsonl --out .ideation/<slug>
```

## Fase 3. Colapsar duplicatas e medir distância

O `cluster.py` agrupa candidatos lexicalmente parecidos (TF-IDF, cosseno), escolhe como representante o membro mais distante do óbvio e marca `perto_do_obvio` quando a similaridade com alguma ideia de consenso passa do limiar. Saídas: `survivors.jsonl` e `clusters.md`.

O agrupamento é lexical, então duas ideias iguais com palavras diferentes podem escapar. Leia `clusters.md` e faça uma passada semântica rápida: funda manualmente sobreviventes que são a mesma ideia e registre a fusão. Descarte os `perto_do_obvio` a menos que o mecanismo seja claramente diferente.

Corte para no máximo 15 sobreviventes (rapido: 8). Se precisar cortar mais, priorize os que usam `dado_usado` não nulo: ideia ancorada em sinal privado tem mais chance de ser nova de fato.

## Fase 4. Anterioridade com busca real

Para cada sobrevivente, faça de 2 a 3 buscas na web com termos diferentes (o nome provável do produto, o mecanismo descrito com outras palavras, o problema + "startup" ou "paper" ou "github"). Use subagentes em paralelo quando houver muitos. Registre em `prior_art.md`:

- `existe`: link do produto ou paper que faz essencialmente isso. A ideia só segue se o brief tiver uma vantagem concreta sobre o existente (dado, distribuição, custo).
- `parcial`: existe algo vizinho; anote a diferença.
- `não encontrado`: liste as queries usadas.

Nunca escreva "inédito" ou "ninguém fez". O máximo que a evidência permite é "não encontrado nestas N buscas: ...". Benchmarks recentes mostram que LLMs julgam novidade de forma pouco confiável mesmo quando o raciocínio parece bom, então a busca é o juiz aqui, não a sua impressão.

## Fase 5. Avaliar contra a realidade

Para cada sobrevivente, execute o `teste_barato` quando ele for executável agora: query no banco, script sobre logs, protótipo descartável, spike de código, cálculo de custo com preço real. Salve cada execução em `evidence/<id>.md` com o comando e o resultado. Se o teste depende do usuário (falar com cliente, landing page), registre como pendente com o roteiro pronto.

Classifique cada sobrevivente:
- `sustentada`: o teste rodou e o sinal apareceu.
- `morta`: o teste rodou e bateu no critério de morte. Mantenha no relatório com o motivo; ideias mortas com motivo claro também são resultado.
- `não testada`: não havia como testar agora.

## Fase 6. Torneio cego

Comparação par a par é mais confiável do que nota absoluta. Gere os pareamentos:

```bash
python3 <skill>/scripts/tournament.py pairs .ideation/<slug>/survivors.jsonl --rounds 4 --out .ideation/<slug>/pairs.jsonl
```

Dispare um subagente **juiz que não participou da geração** (se possível, outro modelo). Ele recebe o brief, as evidências e os pares, sem a lente de origem nem `p_verbalizada`, e escreve `matches.jsonl` com `{"a": id, "b": id, "vencedor": id, "motivo": "..."}`. Critérios do juiz, nesta ordem: força da evidência da Fase 5, alavancagem sobre o sinal privado, custo para testar de verdade, tamanho do ganho se der certo. Novidade não é critério do juiz; ela já foi garantida por distância e busca. Os pares já vêm com ordem aleatória para reduzir viés de posição.

```bash
python3 <skill>/scripts/tournament.py rank .ideation/<slug>/matches.jsonl --survivors .ideation/<slug>/survivors.jsonl --out .ideation/<slug>/ranking.md
```

## Fase 7. Mutação (padrão: 1 rodada, profundo: 2)

Pegue os 4 primeiros do ranking e gere variações com um subagente: combinar dois finalistas, remover o componente mais caro, empurrar a restrição que o juiz apontou como fraqueza, trocar o público-alvo. Cada mutação referencia os pais em `"pais": [ids]`. Mutações passam de novo pelas Fases 4 a 6, competindo com os pais. Pare quando a rodada não produzir nenhum novo top 3.

## Fase 8. Relatório

Escreva `report.md` e mostre ao usuário apenas o essencial na conversa. Estrutura:

```markdown
# <problema>

Avaliador usado: <qual> | Candidatos gerados: N | Sobreviventes: M | Modo: <modo>

## Top 3 a 5
### 1. <título>
- Mecanismo: ...
- Por que não é óbvio: <insight + distância do óbvio>
- Evidência: [sustentada | não testada] <o que rodou e o que deu>
- Anterioridade: <existe/parcial/não encontrado + links ou queries>
- Próximo teste: <o que fazer amanhã, em quanto tempo>
- Mata se: <critério>

## Mortas que valem registro
<título: motivo em uma linha>

## Limitações desta rodada
<o que não foi verificado, onde o avaliador foi fraco>
```

Honestidade no relatório: separe o que foi verificado do que é hipótese, use números só quando vierem de uma consulta real, e se nenhuma ideia ficou de pé, diga isso. Um "nada sobreviveu, e o motivo é X" vale mais do que três ideias infladas.

## Regras que valem para todas as fases

- Quem gera não julga. Gerador, juiz e mutador são agentes diferentes.
- Ideias ancoradas em dado privado verificado pesam mais do que ideias genéricas brilhantes.
- Não invente fatos, números, APIs ou produtos concorrentes. Se não verificou, marque como suposição.
- Ações caras ou irreversíveis (escrever em banco de produção, gastar dinheiro, enviar algo a cliente) ficam fora do loop: prepare e peça confirmação.
