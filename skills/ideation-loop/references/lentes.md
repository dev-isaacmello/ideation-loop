# Lentes de geração

Cada lente roda num subagente independente. Para cada uma, escreva `tarefas/<lente>.md` com: o caminho do `brief.md` (para ler inteiro), o caminho do `obvious.jsonl` (rotulado "já pensado, não repita nem varie"), a instrução comum, o bloco "Instrução" da lente, o schema de candidato do SKILL.md, o número de candidatos e o caminho de saída. O subagente pega a tarefa com `claim.py`, como descrito na Fase 2 do SKILL.md.

Ordem de uso por modo:
- `rapido`: anomalia, analogia, cauda
- padrão: anomalia, analogia, inversao, restricao, cauda, combinacao
- `profundo`: todas as sete

Rode `cauda` e `combinacao` com o modelo menor disponível (variância barata), com as tarefas delas em `tarefas-menor/`.

Instrução comum a todas as lentes (inclua sempre):

> Você está gerando candidatos para um loop de ideação que vai filtrar depois com busca de anterioridade e testes reais, então não se autocensure por viabilidade nem por soar estranho. Ideias que repetem ou variam levemente o conteúdo de `obvious.jsonl` são desperdício. Cada candidato precisa de mecanismo concreto (o que acontece, quem faz o quê, com qual dado), não de slogan. `teste_barato` precisa ser algo executável em menos de um dia. `criterio_de_morte` precisa ser um resultado observável. O arquivo de saída só contém linhas JSON: nenhum título, comentário ou resumo dentro dele. Confira que cada linha é JSON válido antes de terminar e responda, fora do arquivo, com quantos candidatos escreveu.

---

## anomalia

Parte do sinal privado. É a lente que mais produz ideia que não existe, porque usa fatos que nenhum modelo viu no treino.

**Instrução:**
> Leia os fatos do brief marcados `[verificado]`. Para cada fato, pergunte: o que é surpreendente aqui? O que este padrão revela sobre o usuário que ele mesmo não diria? Que comportamento já existe e está sendo ignorado pelo produto? Gere candidatos que exploram diretamente um fato surpreendente, citando o fato em `dado_usado`. Se você tiver acesso ao projeto, investigue (schema, logs, código, queries agregadas somente leitura) atrás de fatos que o brief não tem ou que o contradizem. Grave cada fato novo no seu arquivo como uma linha própria, `{"fato": "o fato, com número", "como_verificou": "comando ou arquivo"}`, e cite-o em `dado_usado` nos candidatos que ele sustenta.

## analogia

Transferência estrutural de um domínio distante.

**Instrução:**
> Escolha 4 domínios estruturalmente distantes do problema (exemplos de distância: se o problema é nutrição, pense em seguros, controle de tráfego aéreo, cooperativas agrícolas, jogos competitivos; evite domínios vizinhos como fitness). Para cada domínio, descreva em uma frase como ele resolve um problema com a mesma estrutura (o mesmo tipo de incerteza, incentivo ou gargalo) e então transfira o mecanismo. Em `lente`, use `analogia:<dominio>`. Em `insight`, explicite o mapeamento estrutural: "X no domínio A corresponde a Y aqui porque ...". Analogias superficiais (gamificação genérica, "Uber de X") não contam.

## inversao

Quebra premissas tácitas.

**Instrução:**
> Liste de 6 a 10 premissas que todo mundo na área assume sem perceber (ex.: "o usuário precisa registrar o que comeu", "o cliente agenda o horário", "o produto é usado por uma pessoa"). Para cada premissa, suponha que ela é falsa ou invertida e pergunte que produto ou mecanismo faria sentido nesse mundo. Gere candidatos a partir das inversões mais férteis. Em `insight`, nomeie a premissa invertida.

## restricao

Restrições extremas forçam soluções fora do repertório.

**Instrução:**
> Gere candidatos sob cada uma destas restrições, distribuindo entre elas: (1) custo de operação 10x menor que a solução óbvia; (2) zero interface, o usuário não abre nada; (3) o usuário não faz nenhuma ação nova; (4) dá para construir em um dia com o que o projeto já tem; (5) funciona só com dados que já existem no banco; (6) a solução é remover algo em vez de adicionar. Em `lente`, use `restricao:<numero>`.

## cauda

Verbalized sampling: pedir a distribuição explícita reduz o colapso para a resposta típica.

**Instrução:**
> Para o problema do brief, gere ideias em lotes de 5. Para cada ideia, estime a probabilidade de um especialista da área sugeri-la espontaneamente (0 a 1) e grave no campo extra `p_verbalizada`. Mantenha no arquivo apenas as ideias com `p_verbalizada` abaixo de 0.10. Continue gerando lotes até atingir o número de candidatos pedido. Ideias de baixa probabilidade não precisam ser absurdas: precisam ser plausíveis e pouco prováveis de ocorrer a alguém.

## combinacao

Combinação forçada. A aleatoriedade vem de um script, porque LLM é ruim em sortear.

**Instrução:**
> Monte duas listas no seu arquivo de trabalho: A = capacidades que o projeto já tem (dados, integrações, modelos, canais, ativos) e B = dores ou momentos do usuário, ambas a partir do brief e do código. Salve cada lista como um item por linha e rode `python3 <skill>/scripts/combine.py A.txt B.txt --k <n> --seed <qualquer inteiro>`. Para cada par sorteado, gere o melhor candidato que usa aquela capacidade para aquela dor, mesmo que a conexão pareça forçada; conexões forçadas são o objetivo. Descarte só se for impossível em vez de estranho.

## extremo

Usuários na borda da distribuição mostram necessidades que a média esconde.

**Instrução:**
> Descreva 4 usuários extremos e 2 não-usuários relevantes: o que usa 10x mais que a média, o que usa de um jeito que o produto não previu, o que quase cancelou e ficou, o que nunca começou apesar de ser público-alvo. Se houver dados, encontre-os de verdade com queries agregadas. Para cada um, gere candidatos que resolvem a necessidade dele de forma que também sirva à média. Em `lente`, use `extremo:<perfil>`.
