#!/usr/bin/env python3
"""Sorteia pares (capacidade x dor) para a lente de combinação forçada.

Uso: combine.py A.txt B.txt --k 12 [--seed 42]
Um item por linha em cada arquivo. Linhas vazias e iniciadas por # são ignoradas.
O sorteio fica num script porque LLM é ruim em escolher ao acaso: tende a parear
os itens que já combinam, o que anula o propósito da lente.
"""
import argparse
import random
from pathlib import Path


def read_list(path):
    return [l.strip() for l in Path(path).read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.strip().startswith("#")]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--k", type=int, default=12)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()
    a, b = read_list(args.a), read_list(args.b)
    if not a or not b:
        raise SystemExit("listas vazias")
    product = [(x, y) for x in a for y in b]
    rng = random.Random(args.seed)
    for n, (x, y) in enumerate(rng.sample(product, min(args.k, len(product))), 1):
        print(f"{n}. {x}  x  {y}")


if __name__ == "__main__":
    main()
