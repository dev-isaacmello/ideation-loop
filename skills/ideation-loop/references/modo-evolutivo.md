# Modo evolutivo

Para problemas com métrica executável: otimizar uma função, um prompt de agente, uma heurística de agendamento, uma query, uma política de cache, um classificador. É a versão de bolso do padrão AlphaEvolve: população de candidatos, avaliador automático, seleção, mutação com feedback.

## 1. Construa o avaliador primeiro

Crie `.ideation/<slug>/eval/` com um comando que recebe o caminho de um candidato e imprime **um JSON numa linha** no stdout:

```json
{"score": 0.0, "ok": true, "detalhes": {"latencia_ms": 0, "testes": "12/12"}}
```

Requisitos:
- Determinístico ou com seed fixa. Se houver ruído (latência, rede), rode N vezes e use mediana.
- Inclui checagem de correção. Um candidato rápido e errado tem `ok: false` e score irrelevante. Sem isso, a evolução aprende a trapacear o avaliador (pular trabalho, hardcode de resposta, apagar teste).
- Conjunto de avaliação separado de um conjunto de validação final (holdout) que os geradores nunca veem. O vencedor é confirmado no holdout antes de ir para o relatório.
- Roda em segundos ou poucos minutos. Avaliador lento mata o número de gerações.

Rode o avaliador na solução atual (baseline) e registre o score. Todo ganho é relativo a ele.

## 2. Geração 0

Dispare subagentes em paralelo, cada um com uma lente diferente de `lentes.md` adaptada a código (analogia com algoritmos de outra área, inversão de premissa da implementação atual, restrição extrema de memória ou de dependências, etc.). Em Claude Code com git, use `isolation: "worktree"` para cada subagente trabalhar numa cópia isolada; sem git, cada candidato em `candidates/<id>/`. Cada subagente roda o avaliador no próprio candidato antes de entregar e reporta o JSON.

Registre todos em `population.jsonl`: `{"id", "pais": [], "lente", "descricao", "score", "ok", "caminho"}`.

## 3. Loop

A cada geração:
1. Selecione os k melhores com `ok: true` (k=4) mais 1 aleatório de fora do top, para manter diversidade.
2. Para cada selecionado, um subagente recebe: o código do candidato, o JSON do avaliador, os 3 melhores da geração anterior como contexto e uma instrução de mutação (melhorar o gargalo apontado em `detalhes`, combinar com outro finalista, simplificar mantendo o score, tentar uma abordagem estruturalmente diferente).
3. Avalie, registre, repita.

Pare quando: duas gerações seguidas sem ganho acima do ruído medido, orçamento atingido, ou o usuário mandar parar. Padrão: no máximo 5 gerações.

## 4. Fechamento

- Rode o melhor no holdout. Se cair muito em relação ao conjunto de avaliação, houve overfitting ao avaliador; diga isso.
- Revise o diff do vencedor como faria num PR: legibilidade, segurança, efeitos colaterais. Score alto não aprova código ruim.
- Relatório com: baseline, melhor score, curva por geração, o que o vencedor faz de diferente (o insight, não só o diff), e o que não foi verificado.
- Não faça merge nem deploy. Entregue o diff ou o worktree para o usuário decidir.
