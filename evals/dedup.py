#!/usr/bin/env python3
"""Mede a fila de duplicatas do cluster.py contra rodadas rotuladas.

Uso: python3 evals/dedup.py [--min 0.70]

Os dados não vêm no repositório: rodadas reais carregam detalhe do projeto de quem rodou.
Ponha as suas em evals/data/dedup_<nome>.json, neste formato:
  {"candidatos": [{"id": "...", "lente": "...", "titulo": "...", "mecanismo": "...", "insight": "..."}],
   "rotulos": {"original": [["id-a", "id-b"], ["id-c", "id-d", "id-e"]]}}
Cada rótulo é uma lista de grupos de ids que são a mesma ideia (o campo `fusao` de
survivors.jsonl depois do merge já dá isso).

Para k = 1, 2, 3, monta a fila como o cluster.py monta e supõe que quem revisa confirma certo
todo par dela. Recall = pares duplicados que ficam no mesmo grupo depois do fecho transitivo,
dividido pelos pares duplicados do rótulo. Um conjunto pode ter mais de um rótulo: o de quem conduziu
a rodada e, quando houver, o de um rotulador que não viu o primeiro. Nas rodadas em que medi,
os dois discordaram bastante (F1 entre 0,46 e 0,86), então diferença pequena de score é ruído.

Sai com erro se a média ficar abaixo de --min, para servir de trava contra regressão.
"""
import argparse
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT.parent / "skills" / "ideation-loop" / "scripts"))
import cluster


def closure_recall(queue, groups):
    gold = {frozenset(p) for g in groups for p in itertools.combinations(g, 2)}
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            x = parent[x]
        return x

    for pair in {frozenset(p) for p in queue} & gold:
        a, b = tuple(pair)
        parent[find(a)] = find(b)
    return sum(1 for p in gold if len({find(x) for x in p}) == 1) / len(gold)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min", type=float, default=0.70)
    args = ap.parse_args()
    paths = sorted((ROOT / "data").glob("dedup_*.json"))
    if not paths:
        sys.exit(f"sem dados em {ROOT / 'data'}: veja o formato no cabeçalho deste arquivo")
    scores = []
    print(f"{'conjunto':8s} {'rótulo':9s} {'k=1':>5s} {'k=2':>5s} {'k=3':>5s}  fila(k=3)")
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        cands = data["candidatos"]
        vecs = cluster.tfidf([cluster.normalize(cluster.text_of(c)) for c in cands])
        queues = {k: cluster.neighbor_pairs(cands, vecs, k) for k in (1, 2, 3)}
        for name, groups in data["rotulos"].items():
            r = [closure_recall(queues[k], groups) for k in (1, 2, 3)]
            scores.append(sum(r) / 3)
            print(f"{path.stem[6:]:8s} {name:9s} {r[0]:5.2f} {r[1]:5.2f} {r[2]:5.2f}  {len(queues[3])}")
    mean = sum(scores) / len(scores)
    print(f"média {mean:.3f} (mínimo {args.min})")
    sys.exit(0 if mean >= args.min else 1)


if __name__ == "__main__":
    main()
