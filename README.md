# Ideation Loop

Skill de ideação para agentes de código (Claude Code, Codex e qualquer agente que leia `SKILL.md`).

Pedir ideias a um LLM numa passada devolve o consenso da área, e o modelo julga mal a novidade do que ele mesmo escreveu. Esta skill troca o brainstorm por um loop com etapas auditáveis: gera muito com diversidade forçada, colapsa duplicatas, checa anterioridade com busca real e seleciona com um avaliador que não é o gerador.

## Como funciona

| Fase | O que acontece |
|---|---|
| 0. Brief | Problema operacional, objetivo (novidade ou melhoria), fatos privados do projeto (schema, logs, métricas) e o avaliador, definido antes de gerar |
| 1. Óbvio | 15 a 20 ideias de consenso: régua de distância quando o objetivo é novidade, concorrentes quando é melhoria |
| 2. Geração | Um subagente independente por lente (anomalia, analogia, inversão, restrição, cauda, combinação, extremo); `tasks.py` monta as tarefas e `claim.py` as entrega |
| 3. Dedup | `cluster.py` monta a fila de pares suspeitos, o agente confirma e o script funde; fatos novos achados pelas lentes vão para `facts.jsonl` |
| 4. Anterioridade | 2 a 3 buscas na web por sobrevivente, com links ou queries registradas |
| 5. Realidade | Executa o teste barato de cada ideia (query, script, protótipo, cálculo de custo) e grava o veredito |
| 6. Julgamento | Dois juízes que não geraram, de modelos diferentes, ordenam baralhos cegos; `tournament.py` cruza as listas, ordena pelo veredito de evidência e declara empate onde os juízes discordam |
| 7. Mutação | Variações dos finalistas, a partir do que os juízes disseram que faria cada um subir, competem com os pais |
| 8. Relatório | Top 3 a 5 com evidência, anterioridade, próximo teste e critério de morte |

Há também um modo evolutivo para problemas com métrica executável (latência, custo, acurácia): população de candidatos, avaliador automático com holdout, seleção e mutação.

Tudo fica em `.ideation/<slug>/` no diretório do projeto, para cada etapa poder ser conferida.

## Instalação

### Claude Code (plugin)

```
/plugin marketplace add dev-isaacmello/ideation-loop
/plugin install ideation-loop@ideation-loop
```

A skill fica disponível como `/ideation-loop:ideation-loop` e também é acionada sozinha quando você pede ideias.

### Claude Code, Codex, Cursor e outros (skills CLI)

```bash
npx skills add dev-isaacmello/ideation-loop
```

Para instalar direto em um agente, no nível do usuário:

```bash
npx skills add dev-isaacmello/ideation-loop -g -a claude-code
npx skills add dev-isaacmello/ideation-loop -g -a codex
```

### Manual

```bash
git clone https://github.com/dev-isaacmello/ideation-loop
cp -r ideation-loop/skills/ideation-loop ~/.claude/skills/     # Claude Code
cp -r ideation-loop/skills/ideation-loop ~/.agents/skills/     # Codex
```

## Uso

Peça em linguagem natural:

```
use o ideation loop: usuários do plano mensal cancelam entre o dia 20 e 35, quero reduzir isso
```

```
ideation loop em modo rapido: o que construir a seguir neste projeto
```

```
ideation loop evolutivo: reduzir a latência p95 do endpoint /search sem quebrar os testes
```

Modos: `rapido` (3 lentes), padrão (6 lentes, 1 rodada de mutação), `profundo` (7 lentes, 2 rodadas) e `evolutivo`.

## Requisitos

- Python 3 para os scripts. Só biblioteca padrão, nada para instalar.
- Subagentes em paralelo e busca na web rendem o melhor resultado. Sem subagentes, as lentes rodam em sequência.

## Limites

- A skill não prova que uma ideia é inédita. O máximo que ela afirma é "não encontrado nestas N buscas".
- A fila de duplicatas é lexical e só propõe pares. Quem decide se duas ideias são a mesma é o agente, e ideias iguais escritas com palavras muito diferentes podem ficar fora da fila.
- O ranking segue o veredito de evidência, e quem escolhe o que testar é o agente. A ordem dos testes pesa no resultado.
- Sem avaliador melhor que opinião, o ranking é hipótese, e o relatório diz isso.
- Os juízes concordam bem sobre o que tem evidência e só moderadamente sobre a ordem de ideias com o mesmo nível de evidência. O `ranking.md` mostra esse número.
- Gasta tokens: o modo padrão dispara seis subagentes de geração, além de busca e juízes. Os subagentes de cada fase usam o mesmo prompt e largam em duas levas para reaproveitar o cache do contexto inicial.
- As instruções da skill estão em português.

## Testes

```bash
python3 -m unittest discover tests   # scripts
python3 evals/dedup.py                # fila de duplicatas contra as suas rodadas rotuladas
```

`evals/dedup.py` mede quantas duplicatas reais ficam ao alcance de quem revisa a fila. Os dados não vêm no repositório, porque rodadas reais carregam detalhe do projeto de quem rodou: o cabeçalho do script diz o formato para usar as suas. Dois rotuladores discordam bastante sobre o que é duplicata, então diferença pequena de score é ruído.

## Licença

MIT
