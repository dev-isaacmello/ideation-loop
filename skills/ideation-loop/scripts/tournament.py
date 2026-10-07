#!/usr/bin/env python3
"""Torneio par a par para ranquear ideias.

Gerar pareamentos:
  tournament.py pairs survivors.jsonl --rounds 4 --out pairs.jsonl [--seed 7]

Ranquear a partir dos resultados do juiz (matches.jsonl com a, b, vencedor, motivo):
  tournament.py rank matches.jsonl --survivors survivors.jsonl --out ranking.md

O ranking usa Bradley-Terry em vez de Elo porque não depende da ordem das partidas.
"""
import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path


def read_jsonl(path):
    out = []
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[aviso] {path}:{n} JSON inválido ({e.msg}), ignorado", file=sys.stderr)
    return out


def cmd_pairs(args):
    items = read_jsonl(args.survivors)
    if args.skip_obvious:
        items = [x for x in items if not x.get("perto_do_obvio")]
    ids = [x["id"] for x in items]
    titles = {x["id"]: x.get("titulo", "") for x in items}
    if len(ids) < 2:
        sys.exit("menos de 2 ideias, nada a comparar")
    rng = random.Random(args.seed)
    played, pairs = set(), []
    for _ in range(args.rounds):
        # Tenta algumas permutações para evitar repetir confrontos já jogados.
        best = None
        for _ in range(50):
            order = ids[:]
            rng.shuffle(order)
            if len(order) % 2:
                order.append(rng.choice(order[:-1]))
            cand = [tuple(sorted(order[i:i + 2])) for i in range(0, len(order), 2)]
            repeats = sum(p in played for p in cand)
            if best is None or repeats < best[0]:
                best = (repeats, cand)
            if repeats == 0:
                break
        for p in best[1]:
            played.add(p)
            a, b = list(p)
            if rng.random() < 0.5:  # ordem aleatória reduz viés de posição do juiz
                a, b = b, a
            pairs.append({"a": a, "b": b, "a_titulo": titles[a], "b_titulo": titles[b]})
    with open(args.out, "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"{len(pairs)} confrontos para {len(ids)} ideias em {args.rounds} rodadas -> {args.out}")


def bradley_terry(matches, ids, iters=500):
    wins = defaultdict(float)
    games = defaultdict(float)
    for m in matches:
        a, b, w = m["a"], m["b"], m["vencedor"]
        wins[w] += 1
        games[tuple(sorted((a, b)))] += 1
    # Prior: cada ideia empata uma partida virtual contra um oponente fixo de força 1.
    # Sem isso, quem vence tudo tem força infinita e quem perde tudo, zero.
    strength = {i: 1.0 for i in ids}
    for _ in range(iters):
        new = {}
        for i in ids:
            denom = 1.0 / (strength[i] + 1.0)
            for (x, y), n in games.items():
                if i in (x, y):
                    j = y if i == x else x
                    denom += n / (strength[i] + strength[j])
            new[i] = (wins[i] + 0.5) / denom
        mean = sum(new.values()) / len(new)
        strength = {i: v / mean for i, v in new.items()}
    return strength


def cmd_rank(args):
    matches = read_jsonl(args.matches)
    surv = {x["id"]: x for x in read_jsonl(args.survivors)} if args.survivors else {}
    valid = []
    for m in matches:
        if m.get("vencedor") not in (m.get("a"), m.get("b")):
            print(f"[aviso] vencedor inválido em {m}, ignorado", file=sys.stderr)
            continue
        valid.append(m)
    if not valid:
        sys.exit("nenhuma partida válida")
    ids = sorted({m["a"] for m in valid} | {m["b"] for m in valid})
    strength = bradley_terry(valid, ids)
    record = {i: [0, 0] for i in ids}
    reasons = defaultdict(list)
    for m in valid:
        loser = m["b"] if m["vencedor"] == m["a"] else m["a"]
        record[m["vencedor"]][0] += 1
        record[loser][1] += 1
        if m.get("motivo"):
            reasons[m["vencedor"]].append(m["motivo"])
    ranked = sorted(ids, key=lambda i: -strength[i])

    lines = ["# Ranking", "", f"Partidas válidas: {len(valid)} | Ideias: {len(ids)}", "",
             "| # | id | título | V-D | força |", "|---|---|---|---|---|"]
    for pos, i in enumerate(ranked, 1):
        t = surv.get(i, {}).get("titulo", "")
        lines.append(f"| {pos} | `{i}` | {t} | {record[i][0]}-{record[i][1]} | {strength[i]:.2f} |")
    lines += ["", "## Motivos das vitórias (top 5)", ""]
    for i in ranked[:5]:
        lines.append(f"**{i}**")
        lines += [f"- {r}" for r in reasons[i]] or ["- (sem motivo registrado)"]
        lines.append("")
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    json_out = Path(args.out).with_suffix(".json")
    json_out.write_text(json.dumps(
        [{"id": i, "forca": round(strength[i], 4), "vitorias": record[i][0], "derrotas": record[i][1]} for i in ranked],
        ensure_ascii=False, indent=2), encoding="utf-8")
    for pos, i in enumerate(ranked[:5], 1):
        print(f"{pos}. {i} ({record[i][0]}-{record[i][1]}, força {strength[i]:.2f})")
    print(f"escrito: {args.out}, {json_out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pairs")
    p.add_argument("survivors")
    p.add_argument("--rounds", type=int, default=4)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--skip-obvious", action="store_true", help="exclui itens marcados perto_do_obvio")
    p.add_argument("--out", required=True)
    r = sub.add_parser("rank")
    r.add_argument("matches")
    r.add_argument("--survivors")
    r.add_argument("--out", required=True)
    args = ap.parse_args()
    cmd_pairs(args) if args.cmd == "pairs" else cmd_rank(args)


if __name__ == "__main__":
    main()
