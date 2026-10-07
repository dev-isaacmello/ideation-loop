#!/usr/bin/env python3
"""Valida, agrupa e mede a distância ao óbvio dos candidatos de ideação.

Uso:
  cluster.py candidates/*.jsonl --obvious obvious.jsonl --out <dir>
            [--threshold 0.35] [--obvious-threshold 0.45]

Saídas em <dir>: survivors.jsonl (um representante por grupo) e clusters.md.
Só usa a biblioteca padrão, para rodar em qualquer ambiente sem instalar nada.
"""
import argparse
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

REQUIRED = ("titulo", "mecanismo")

STOPWORDS = set("""
a o e as os um uma uns umas de do da dos das em no na nos nas por pelo pela pelos pelas
para pra com sem sobre entre ate apos ante sob que se nao sim mais menos muito muita muitos
muitas ja ainda tambem so apenas como quando onde porque pois mas ou ser estar ter ha foi
sao seu sua seus suas ele ela eles elas isso isto esse essa este esta aquele aquela cada
todo toda todos todas outro outra outros outras mesmo mesma qual quais quem cujo pode podem
fazer faz feito vai vao via usuario usuarios produto
the a an of to in on for with by from and or not is are be it this that as at
""".split())


def normalize(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    tokens = [t for t in re.findall(r"[a-z0-9]+", text) if len(t) > 2 and t not in STOPWORDS]
    # Bigramas pegam expressões ("plano alimentar") que unigramas diluem.
    return tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]


def text_of(item):
    return " ".join(str(item.get(k) or "") for k in ("titulo", "mecanismo", "insight"))


def load_jsonl(paths, label):
    items, seen = [], Counter()
    for path in paths:
        for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[aviso] {path}:{n} JSON inválido ({e.msg}), ignorado", file=sys.stderr)
                continue
            missing = [k for k in REQUIRED if not item.get(k)]
            if missing:
                print(f"[aviso] {path}:{n} sem {missing}, ignorado", file=sys.stderr)
                continue
            base = str(item.get("id") or f"{Path(path).stem}-{n}")
            seen[base] += 1
            item["id"] = base if seen[base] == 1 else f"{base}~{seen[base]}"
            item.setdefault("lente", Path(path).stem if label == "candidato" else "obvio")
            items.append(item)
    return items


def tfidf(docs):
    df = Counter()
    for d in docs:
        df.update(set(d))
    n = len(docs)
    vecs = []
    for d in docs:
        tf = Counter(d)
        v = {t: (1 + math.log(c)) * (math.log((1 + n) / (1 + df[t])) + 1) for t, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({t: x / norm for t, x in v.items()})
    return vecs


def cosine(u, v):
    if len(u) > len(v):
        u, v = v, u
    return sum(x * v.get(t, 0.0) for t, x in u.items())


def unit(v):
    norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
    return {t: x / norm for t, x in v.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("candidates", nargs="+")
    ap.add_argument("--obvious", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--threshold", type=float, default=0.35, help="similaridade mínima para cair no mesmo grupo")
    ap.add_argument("--obvious-threshold", type=float, default=0.45, help="acima disso, marca perto_do_obvio")
    args = ap.parse_args()

    cands = load_jsonl(args.candidates, "candidato")
    obvious = load_jsonl([args.obvious], "obvio") if args.obvious and Path(args.obvious).exists() else []
    if not cands:
        sys.exit("nenhum candidato válido")

    vecs = tfidf([normalize(text_of(x)) for x in cands + obvious])
    cvecs, ovecs = vecs[: len(cands)], vecs[len(cands):]

    for item, v in zip(cands, cvecs):
        sims = [(cosine(v, o), ob["id"]) for o, ob in zip(ovecs, obvious)]
        best = max(sims, default=(0.0, None))
        item["sim_obvio"] = round(best[0], 3)
        item["obvio_mais_proximo"] = best[1]
        item["perto_do_obvio"] = best[0] >= args.obvious_threshold

    # Agrupamento guloso por centroide: evita o encadeamento do single-linkage,
    # em que A~B e B~C juntam A e C mesmo sendo ideias diferentes.
    clusters = []  # cada um: {"soma": vetor, "membros": [idx]}
    for i, v in enumerate(cvecs):
        best_c, best_s = None, 0.0
        for c in clusters:
            s = cosine(v, unit(c["soma"]))
            if s > best_s:
                best_c, best_s = c, s
        if best_c is not None and best_s >= args.threshold:
            best_c["membros"].append(i)
            for t, x in v.items():
                best_c["soma"][t] = best_c["soma"].get(t, 0.0) + x
        else:
            clusters.append({"soma": dict(v), "membros": [i]})

    def rep_key(i):
        it = cands[i]
        # Representante: o mais distante do óbvio; empate favorece dado privado e mecanismo mais detalhado.
        return (it["sim_obvio"], it.get("dado_usado") in (None, "", "null"), -len(it.get("mecanismo", "")))

    survivors = []
    for cid, c in enumerate(clusters, 1):
        rep = dict(cands[min(c["membros"], key=rep_key)])
        rep["cluster_id"] = cid
        rep["cluster_size"] = len(c["membros"])
        rep["membros"] = [cands[i]["id"] for i in c["membros"]]
        rep["lentes_no_grupo"] = sorted({cands[i]["lente"] for i in c["membros"]})
        survivors.append(rep)

    survivors.sort(key=lambda s: (s["perto_do_obvio"], s.get("dado_usado") in (None, "", "null"), s["sim_obvio"]))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "survivors.jsonl", "w", encoding="utf-8") as f:
        for s in survivors:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    by_id = {x["id"]: x for x in cands}
    lines = [
        "# Grupos",
        "",
        f"Candidatos válidos: {len(cands)} | Grupos: {len(clusters)} | "
        f"Perto do óbvio: {sum(s['perto_do_obvio'] for s in survivors)} | "
        f"Limiares: grupo {args.threshold}, óbvio {args.obvious_threshold}",
        "",
        "Agrupamento lexical. Revise: ideias iguais com palavras diferentes podem estar em grupos separados.",
        "",
    ]
    for s in survivors:
        flag = " [PERTO DO ÓBVIO]" if s["perto_do_obvio"] else ""
        lines.append(f"## G{s['cluster_id']}: {s['titulo']}{flag}")
        lines.append(f"representante `{s['id']}` | sim_obvio {s['sim_obvio']} | lentes: {', '.join(s['lentes_no_grupo'])}")
        for mid in s["membros"]:
            m = by_id[mid]
            mark = "*" if mid == s["id"] else "-"
            lines.append(f"{mark} `{mid}` ({m['lente']}, sim_obvio {m['sim_obvio']}): {m['titulo']}")
        lines.append("")
    (out / "clusters.md").write_text("\n".join(lines), encoding="utf-8")

    lentes = Counter(x["lente"].split(":")[0] for x in cands)
    print(f"candidatos {len(cands)} -> grupos {len(clusters)} "
          f"(perto do óbvio: {sum(s['perto_do_obvio'] for s in survivors)})")
    print("por lente: " + ", ".join(f"{k}={v}" for k, v in sorted(lentes.items())))
    print(f"escrito: {out / 'survivors.jsonl'}, {out / 'clusters.md'}")


if __name__ == "__main__":
    main()
