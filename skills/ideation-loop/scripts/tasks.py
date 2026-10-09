#!/usr/bin/env python3
"""Monta as tarefas das lentes de uma rodada, uma por subagente, para entregar com claim.py.

Uso:
  tasks.py <workspace> [--modo rapido|padrao|profundo] [--n N] [--sem-subagentes]
           [--areas "área 1" "área 2"]

Lê references/lentes.md e escreve <workspace>/tarefas/ (modelo principal) e
<workspace>/tarefas-menor/ (lentes que rodam no modelo menor). Cada arquivo traz tudo que o
subagente precisa: brief, óbvio, instrução comum, instrução da lente, schema e arquivo de saída.

A lente anomalia é a única que investiga o projeto. Com --areas ela vira uma tarefa por área,
cada uma com uma fração dos candidatos. Serve para cobrir projeto grande (mais fatos achados),
não para ganhar tempo: cada agente investiga pelo tempo que tiver.
"""
import argparse
import re
import sys
from pathlib import Path

LENTES_MD = Path(__file__).resolve().parent.parent / "references" / "lentes.md"
MODOS = {
    "rapido": (["anomalia", "analogia", "inversao"], 8),
    "padrao": (["anomalia", "analogia", "inversao", "restricao", "cauda", "combinacao"], 12),
    "profundo": (["anomalia", "analogia", "inversao", "restricao", "cauda", "combinacao", "extremo"], 20),
}
MENOR = {"cauda", "combinacao"}
SCHEMA = ('{"id": "<lente>-01", "titulo": "...", "mecanismo": "como funciona, 2 a 4 frases concretas", '
          '"insight": "o fato não óbvio que a ideia explora", "lente": "<lente>", '
          '"dado_usado": "qual fato do brief sustenta, ou null", '
          '"teste_barato": "como provar ou matar em menos de um dia", '
          '"criterio_de_morte": "resultado do teste que mata a ideia"}')


def quote(text, start):
    """Texto do primeiro bloco de citação (linhas iniciadas por '>') depois de `start`."""
    lines = []
    for line in text[start:].splitlines():
        if line.startswith(">"):
            lines.append(line[1:].strip())
        elif lines:
            break
    return " ".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspace")
    ap.add_argument("--modo", choices=sorted(MODOS), default="padrao")
    ap.add_argument("--n", type=int, default=None, help="candidatos por lente (padrão: o do modo)")
    ap.add_argument("--sem-subagentes", action="store_true", help="uma pasta só, para rodar as lentes em sequência")
    ap.add_argument("--areas", nargs="+", default=None, help="divide a anomalia em uma tarefa por área")
    args = ap.parse_args()

    md = LENTES_MD.read_text(encoding="utf-8")
    comum = quote(md, md.index("Instrução comum"))
    ws = Path(args.workspace).resolve()
    lentes, n_modo = MODOS[args.modo]
    n = args.n or n_modo

    tarefas = []  # (pasta, nome do arquivo, lente, instrução, n, arquivo de saída)
    for pos, lente in enumerate(lentes, 1):
        m = re.search(rf"^## {lente}\s*$", md, re.MULTILINE)
        if not m:
            sys.exit(f"lente {lente} não encontrada em {LENTES_MD}")
        instr = quote(md, md.index("**Instrução:**", m.end())).replace("<skill>", str(LENTES_MD.parent.parent))
        pasta = "tarefas" if args.sem_subagentes or lente not in MENOR else "tarefas-menor"
        if lente == "anomalia" and args.areas:
            parte = -(-n // len(args.areas))
            for k, area in enumerate(args.areas, 1):
                nome = f"anomalia-{k}"
                extra = f" Sua área de investigação é só esta: {area}. Outro agente cobre o resto."
                tarefas.append((pasta, f"{pos:02d}-{nome}.md", nome, instr + extra, parte, f"candidates/{nome}.jsonl"))
        else:
            tarefas.append((pasta, f"{pos:02d}-{lente}.md", lente, instr, n, f"candidates/{lente}.jsonl"))

    (ws / "candidates").mkdir(parents=True, exist_ok=True)
    for pasta, arquivo, lente, instr, qtd, saida in tarefas:
        (ws / pasta).mkdir(exist_ok=True)
        (ws / pasta / arquivo).write_text(
            f"Você é um gerador de candidatos num loop de ideação.\n\n"
            f"Leia inteiros: {ws / 'brief.md'} (problema, fatos, restrições, avaliador) e "
            f"{ws / 'obvious.jsonl'} (JÁ PENSADO: não repita nem varie)."
            f"{'' if args.sem_subagentes else ' Não leia a saída de outras lentes.'}\n\n"
            f"Instrução comum: {comum}\n\n"
            f"Sua lente: {lente}. {instr}\n\n"
            f"Gere {qtd} candidatos. Escreva SOMENTE {ws / saida}, um JSON por linha, neste schema "
            f"(troque <lente> pelo nome da sua):\n{SCHEMA}\n\n"
            + ("" if args.sem_subagentes else "Responda no fim só com quantos candidatos escreveu.\n"),
            encoding="utf-8")

    claim = Path(__file__).resolve().parent / "claim.py"
    for pasta in sorted({t[0] for t in tarefas}):
        nomes = [t[2] for t in tarefas if t[0] == pasta]
        print(f"{ws / pasta}: {len(nomes)} tarefas ({', '.join(nomes)})")
        if args.sem_subagentes:
            print(f"  para cada lente, em sequência: python3 {claim} {ws / pasta}")
        else:
            print(f"  prompt de cada subagente: Rode python3 {claim} {ws / pasta} e siga o que ele imprimir.")


if __name__ == "__main__":
    main()
