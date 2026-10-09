#!/usr/bin/env python3
"""Entrega a próxima tarefa livre de um diretório e imprime o conteúdo dela.

Uso: claim.py <dir-de-tarefas>
Cada tarefa é um arquivo .md. Quem chama recebe uma tarefa que ninguém mais recebeu.

Existe para que todos os subagentes de uma fase tenham o mesmo prompt, byte a byte ("rode
claim.py e siga o que ele imprimir"). Com prompt idêntico, o segundo subagente em diante lê
do cache o contexto inicial inteiro em vez de pagar para criá-lo de novo.
"""
import os
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    for task in sorted(Path(sys.argv[1]).glob("*.md")):
        taken = task.with_suffix(".tomada")
        try:
            os.rename(task, taken)  # atômico: dois subagentes nunca levam a mesma tarefa
        except FileNotFoundError:
            continue
        print(taken.read_text(encoding="utf-8"))
        return
    sys.exit("nenhuma tarefa livre")


if __name__ == "__main__":
    main()
