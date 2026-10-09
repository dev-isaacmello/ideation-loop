#!/usr/bin/env python3
"""Valida os candidatos, monta a fila de duplicatas suspeitas e aplica as fusões confirmadas.

Uso:
  cluster.py queue candidates/*.jsonl --obvious obvious.jsonl --out <dir> [--k 3]
  cluster.py merge --out <dir>

`queue` escreve em <dir>: survivors.jsonl (todos os candidatos válidos, com a distância ao
óbvio), suspeitos.md (pares para confirmar) e facts.jsonl (fatos novos achados pelas lentes).
`merge` lê as marcas `[x]` de suspeitos.md, funde os grupos e reescreve survivors.jsonl e
clusters.md.

A similaridade é lexical (TF-IDF). Ela ordena bem os pares parecidos e decide mal se são a
mesma ideia, por isso o script só propõe a fila e a decisão fica com quem lê.
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
SAME_LENS = 0.5
MECH = 220  # caracteres do mecanismo mostrados na fila: basta para decidir e não incha o arquivo
MARK = re.compile(r"^- \[(x|X| )\] `([^`]+)` ~ `([^`]+)`")

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
    """Devolve (itens válidos, fatos, número de linhas ilegíveis)."""
    items, facts, seen, bad = [], [], Counter(), 0
    for path in paths:
        for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                item = None
            if not isinstance(item, dict):
                bad += 1
                print(f"[aviso] {path}:{n} não é um objeto JSON, ignorado: {line[:60]!r}", file=sys.stderr)
                continue
            # A lente que investiga o projeto devolve fatos novos junto dos candidatos.
            if item.get("fato") and not item.get("titulo"):
                item.setdefault("origem", Path(path).stem)
                facts.append(item)
                continue
            missing = [k for k in REQUIRED if not item.get(k)]
            if missing:
                bad += 1
                print(f"[aviso] {path}:{n} sem {missing}, ignorado", file=sys.stderr)
                continue
            base = str(item.get("id") or f"{Path(path).stem}-{n}")
            seen[base] += 1
            item["id"] = base if seen[base] == 1 else f"{base}~{seen[base]}"
            item.setdefault("lente", Path(path).stem if label == "candidato" else "obvio")
            items.append(item)
    return items, facts, bad


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


def neighbor_pairs(cands, vecs, k):
    """Fila de suspeitos: os k vizinhos de cada candidato, {(id_a, id_b): similaridade}.

    Por candidato, e não os pares mais parecidos da rodada: um teto global concentra a fila
    nos grupos grandes e deixa as duplicatas dos pequenos sem par.
    """
    lentes = [c.get("lente", "").split(":")[0] for c in cands]
    pairs = {}
    for i, v in enumerate(vecs):
        # Duplicata quase sempre vem de lentes diferentes: uma lente roda num agente só, que
        # não se repete. Par da mesma lente vale metade para não ocupar a vaga de um vizinho.
        sims = sorted(((cosine(v, w) * (SAME_LENS if lentes[i] == lentes[j] else 1.0), j)
                       for j, w in enumerate(vecs) if j != i), reverse=True)
        for s, j in sims[:k]:
            pairs[tuple(sorted((cands[i]["id"], cands[j]["id"])))] = s
    return pairs


def write_jsonl(path, items):
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(item, ensure_ascii=False) + "\n" for item in items)


def read_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def cmd_queue(args):
    cands, facts, bad = load_jsonl(args.candidates, "candidato")
    obvious = load_jsonl([args.obvious], "obvio")[0] if args.obvious and Path(args.obvious).exists() else []
    if not cands:
        sys.exit("nenhum candidato válido")

    vecs = tfidf([normalize(text_of(x)) for x in cands + obvious])
    cvecs, ovecs = vecs[: len(cands)], vecs[len(cands):]
    by_id = {x["id"]: x for x in cands + obvious}

    for item, v in zip(cands, cvecs):
        best = max(((cosine(v, o), ob["id"]) for o, ob in zip(ovecs, obvious)), default=(0.0, None))
        item["sim_obvio"] = round(best[0], 3)
        item["obvio_mais_proximo"] = best[1]
        item["perto_do_obvio"] = False

    pairs = neighbor_pairs(cands, cvecs, args.k)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / "survivors.jsonl", cands)
    if facts:
        for n, f in enumerate(facts, 1):
            f.setdefault("id", f"fato-novo-{n:02d}")
        write_jsonl(out / "facts.jsonl", facts)

    lines = [
        "# Duplicatas suspeitas",
        "",
        (f"Candidatos válidos: {len(cands)} | Pares na fila: {len(pairs)} | Fatos novos: {len(facts)} | "
         f"Linhas ignoradas: {bad}"),
        "",
        "Marque `[x]` nos pares que são a mesma ideia e rode `cluster.py merge`. A ordem é por",
        "similaridade lexical, que deixa escapar ideias iguais com palavras diferentes: se achar",
        "uma duplicata fora da fila, acrescente uma linha `- [x] `id-a` ~ `id-b`` (o número entre",
        "parênteses é só informativo e pode faltar).",
        "",
        "## Entre candidatos",
        "",
    ]
    for (a, b), s in sorted(pairs.items(), key=lambda kv: -kv[1]):
        lines.append(f"- [ ] `{a}` ~ `{b}` ({s:.2f})")
        lines.append(f"  - {by_id[a]['titulo']}: {by_id[a]['mecanismo'][:MECH]}")
        lines.append(f"  - {by_id[b]['titulo']}: {by_id[b]['mecanismo'][:MECH]}")
    if obvious:
        lines += ["", "## Contra o óbvio", "",
                  "Marque `[x]` quando o candidato for a ideia de consenso com outra redação.", ""]
        for c in sorted(cands, key=lambda c: -c["sim_obvio"]):
            ob = c["obvio_mais_proximo"]
            lines.append(f"- [ ] `{c['id']}` ~ `{ob}` ({c['sim_obvio']:.2f})")
            lines.append(f"  - {c['titulo']}")
            lines.append(f"  - {by_id[ob]['titulo']}")
    (out / "suspeitos.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    lentes = Counter(x["lente"].split(":")[0] for x in cands)
    print(f"candidatos {len(cands)} | pares na fila {len(pairs)} | fatos novos {len(facts)} | "
          f"linhas ignoradas {bad}")
    print("por lente: " + ", ".join(f"{k}={v}" for k, v in sorted(lentes.items())))
    print(f"escrito: {out / 'survivors.jsonl'}, {out / 'suspeitos.md'}"
          + (f", {out / 'facts.jsonl'}" if facts else ""))


def cmd_merge(args):
    out = Path(args.out)
    cands = read_jsonl(out / "survivors.jsonl")
    by_id = {x["id"]: x for x in cands}
    parent = {i: i for i in by_id}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    confirmed = 0
    for line in (out / "suspeitos.md").read_text(encoding="utf-8").splitlines():
        m = MARK.match(line)
        if not m or m.group(1) == " ":
            continue
        a, b = m.group(2), m.group(3)
        if a not in by_id:
            print(f"[aviso] id desconhecido em suspeitos.md: {a}", file=sys.stderr)
            continue
        confirmed += 1
        if b in by_id:
            parent[find(a)] = find(b)
        else:
            by_id[a]["perto_do_obvio"] = True

    groups = {}
    for i in by_id:
        groups.setdefault(find(i), []).append(i)

    survivors = []
    for cid, members in enumerate(groups.values(), 1):
        # Representante: o mais distante do óbvio; empate favorece o mecanismo mais detalhado.
        rep_id = min(members, key=lambda i: (by_id[i]["sim_obvio"], -len(by_id[i].get("mecanismo", ""))))
        rep = dict(by_id[rep_id])
        rep["cluster_id"] = cid
        rep["fusao"] = sorted(set(members + rep.get("fusao", [])) - {rep_id})
        rep["lentes_no_grupo"] = sorted({by_id[i]["lente"].split(":")[0] for i in members})
        rep["perto_do_obvio"] = any(by_id[i]["perto_do_obvio"] for i in members)
        survivors.append(rep)
    survivors.sort(key=lambda s: (s["perto_do_obvio"], s["sim_obvio"]))
    write_jsonl(out / "survivors.jsonl", survivors)

    fused = sum(len(s["fusao"]) for s in survivors)
    lines = ["# Grupos", "",
             (f"Candidatos: {len(cands)} | Ideias distintas: {len(survivors)} | Fundidos em outro: {fused} | "
              f"Perto do óbvio: {sum(s['perto_do_obvio'] for s in survivors)}"), ""]
    for s in survivors:
        flag = " [PERTO DO ÓBVIO]" if s["perto_do_obvio"] else ""
        lines.append(f"## G{s['cluster_id']}: {s['titulo']}{flag}")
        lines.append(f"representante `{s['id']}` | sim_obvio {s['sim_obvio']} | "
                     f"lentes: {', '.join(s['lentes_no_grupo'])}")
        lines += [f"- funde `{i}`: {by_id[i]['titulo']}" for i in s["fusao"] if i in by_id]
        lines.append("")
    (out / "clusters.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"marcas lidas {confirmed} | candidatos {len(cands)} -> ideias distintas {len(survivors)} "
          f"(perto do óbvio: {sum(s['perto_do_obvio'] for s in survivors)})")
    print(f"escrito: {out / 'survivors.jsonl'}, {out / 'clusters.md'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("queue")
    q.add_argument("candidates", nargs="+")
    q.add_argument("--obvious", default=None)
    q.add_argument("--out", required=True)
    q.add_argument("--k", type=int, default=3, help="vizinhos de cada candidato que entram na fila")
    m = sub.add_parser("merge")
    m.add_argument("--out", required=True)
    args = ap.parse_args()
    cmd_queue(args) if args.cmd == "queue" else cmd_merge(args)


if __name__ == "__main__":
    main()
