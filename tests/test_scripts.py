"""Rode com: python3 -m unittest discover tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "ideation-loop" / "scripts"


def run(script, *args):
    return subprocess.run([sys.executable, "-B", str(SCRIPTS / script), *map(str, args)],
                          capture_output=True, text=True, check=False)


def cand(i, titulo, mecanismo, lente="anomalia"):
    return json.dumps({"id": i, "titulo": titulo, "mecanismo": mecanismo, "lente": lente}, ensure_ascii=False)


class ClusterTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "a.jsonl").write_text("\n".join([
            cand("anomalia-01", "Lembrete de consulta por mensagem", "Enviar mensagem na véspera da consulta marcada."),
            cand("anomalia-02", "Relatório semanal de faturamento", "Somar o caixa da semana e mandar ao dono."),
            json.dumps({"fato": "37% das consultas marcadas não acontecem", "como_verificou": "query"}),
            "2 candidatos escritos.",
        ]), encoding="utf-8")
        (self.dir / "b.jsonl").write_text(
            cand("cauda-01", "Mensagem de lembrete da consulta", "Na véspera da consulta marcada, enviar mensagem.", "cauda"),
            encoding="utf-8")
        (self.dir / "obvious.jsonl").write_text(
            cand("obvio-01", "Relatório de faturamento", "Mandar ao dono o caixa da semana somado.", "obvio"),
            encoding="utf-8")

    def queue(self):
        return run("cluster.py", "queue", self.dir / "a.jsonl", self.dir / "b.jsonl",
                   "--obvious", self.dir / "obvious.jsonl", "--out", self.dir)

    def test_fato_e_linha_solta_nao_se_perdem(self):
        r = self.queue()
        self.assertEqual(r.returncode, 0, r.stderr)
        facts = [json.loads(l) for l in (self.dir / "facts.jsonl").read_text().splitlines()]
        self.assertEqual([f["fato"] for f in facts], ["37% das consultas marcadas não acontecem"])
        self.assertIn("linhas ignoradas 1", r.stdout)
        self.assertEqual(len((self.dir / "survivors.jsonl").read_text().splitlines()), 3)

    def test_marca_funde_duplicata_e_marca_perto_do_obvio(self):
        self.queue()
        path = self.dir / "suspeitos.md"
        text = path.read_text()
        self.assertIn("- [ ] `anomalia-01` ~ `cauda-01`", text)
        text = text.replace("- [ ] `anomalia-01` ~ `cauda-01`", "- [x] `anomalia-01` ~ `cauda-01`")
        text = text.replace("- [ ] `anomalia-02` ~ `obvio-01`", "- [x] `anomalia-02` ~ `obvio-01`")
        path.write_text(text)
        r = run("cluster.py", "merge", "--out", self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        surv = {s["id"]: s for s in map(json.loads, (self.dir / "survivors.jsonl").read_text().splitlines())}
        self.assertEqual(len(surv), 2)
        grupo = next(s for s in surv.values() if s["fusao"])
        self.assertEqual(sorted([grupo["id"]] + grupo["fusao"]), ["anomalia-01", "cauda-01"])
        self.assertEqual(grupo["lentes_no_grupo"], ["anomalia", "cauda"])
        self.assertTrue(surv["anomalia-02"]["perto_do_obvio"])


class TournamentTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        ids = ["anomalia-01", "cauda-02", "analogia-03", "inversao-04"]
        (self.dir / "survivors.jsonl").write_text(
            "\n".join(cand(i, f"Ideia {n}", f"Mecanismo {n}, variante de {ids[0]}.") for n, i in enumerate(ids)),
            encoding="utf-8")
        (self.dir / "brief.md").write_text("# Brief\n", encoding="utf-8")
        ev = self.dir / "evidence"
        ev.mkdir()
        (ev / "inversao-04.md").write_text("# inversao-04\n\nveredito: sustentada\n\nRodou e o sinal apareceu.\n")
        (ev / "cauda-02.md").write_text("# cauda-02\n\nveredito: morta\n\nBateu no critério de morte.\n")
        r = run("tournament.py", "decks", self.dir / "survivors.jsonl", "--evidence", ev,
                "--brief", self.dir / "brief.md", "--out", self.dir / "juiz")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.mapa = json.loads((self.dir / "juiz" / "mapa.json").read_text())

    def lista(self, deck, order):
        code = {v: k.split(":")[1] for k, v in self.mapa.items() if k.startswith(deck + ":")}
        (self.dir / "juiz" / f"lista_{deck}.jsonl").write_text("\n".join(
            json.dumps({"posicao": n, "id": code[i], "motivo": "m", "maior_risco": "r", "para_vencer": f"pv {i}"})
            for n, i in enumerate(order, 1)))

    def agree(self):
        return run("tournament.py", "agree", self.dir / "juiz", "--survivors", self.dir / "survivors.jsonl",
                   "--evidence", self.dir / "evidence", "--out", self.dir / "ranking.md")

    def test_baralho_e_cego(self):
        d1 = (self.dir / "juiz" / "tarefas" / "deck1.md").read_text()
        d2 = (self.dir / "juiz" / "tarefas" / "deck2.md").read_text()
        for lente in ("anomalia", "cauda", "analogia", "inversao"):
            self.assertNotIn(lente + "-", d1)
        self.assertIn("veredito: sustentada", d1)
        self.assertIn("veredito: nao_testada", d1)
        self.assertNotEqual(sorted(k for k in self.mapa if k.startswith("deck1")),
                            sorted(k.replace("deck2", "deck1") for k in self.mapa if k.startswith("deck2")))
        self.assertNotEqual(d1, d2)

    def test_ranking_respeita_veredito_e_mede_concordancia(self):
        # Os juízes põem a ideia morta no topo e a sustentada por último; o veredito inverte isso.
        self.lista("deck1", ["cauda-02", "anomalia-01", "analogia-03", "inversao-04"])
        self.lista("deck2", ["anomalia-01", "cauda-02", "analogia-03", "inversao-04"])
        r = self.agree()
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads((self.dir / "ranking.json").read_text())
        self.assertEqual([x["id"] for x in out["ranking"]],
                         ["inversao-04", "anomalia-01", "analogia-03", "cauda-02"])
        self.assertAlmostEqual(out["tau_lista_inteira"], 4 / 6)
        # Só um par está no mesmo veredito (as duas não testadas), e os juízes concordam nele.
        self.assertAlmostEqual(out["tau"], 1.0)
        self.assertEqual(out["inversoes_de_veredito"]["deck1"], 5)
        self.assertEqual([x["faixa"] for x in out["ranking"]], [1, 2, 3, 4])
        self.assertIn("pv inversao-04", (self.dir / "ranking.md").read_text())

    def test_juizes_em_desacordo_ficam_na_mesma_faixa(self):
        self.lista("deck1", ["inversao-04", "anomalia-01", "analogia-03", "cauda-02"])
        self.lista("deck2", ["inversao-04", "analogia-03", "anomalia-01", "cauda-02"])
        self.assertEqual(self.agree().returncode, 0)
        out = json.loads((self.dir / "ranking.json").read_text())
        self.assertEqual({x["id"]: x["faixa"] for x in out["ranking"]},
                         {"inversao-04": 1, "analogia-03": 2, "anomalia-01": 2, "cauda-02": 3})

    def test_lista_incompleta_ou_ausente_e_recusada(self):
        self.lista("deck1", ["cauda-02", "anomalia-01", "analogia-03"])
        r = self.agree()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("refazer a lista", r.stderr)
        self.lista("deck1", ["cauda-02", "anomalia-01", "analogia-03", "inversao-04"])
        r = self.agree()  # o juiz do deck2 não entregou
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("falta a lista de deck2", r.stderr)


class TasksTest(unittest.TestCase):
    def test_tarefas_por_modo_com_anomalia_dividida(self):
        d = Path(tempfile.mkdtemp())
        r = run("tasks.py", d, "--modo", "padrao", "--areas", "código", "dados")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(p.name for p in (d / "tarefas").iterdir()),
                         ["01-anomalia-1.md", "01-anomalia-2.md", "02-analogia.md", "03-inversao.md",
                          "04-restricao.md"])
        self.assertEqual(sorted(p.name for p in (d / "tarefas-menor").iterdir()),
                         ["05-cauda.md", "06-combinacao.md"])
        anomalia = (d / "tarefas" / "01-anomalia-2.md").read_text()
        self.assertIn("Gere 6 candidatos", anomalia)
        self.assertIn("só esta: dados", anomalia)
        self.assertIn("criterio_de_morte", anomalia)
        self.assertIn("surpreendente", anomalia)  # veio a instrução da lente, de lentes.md
        self.assertNotIn("<skill>", (d / "tarefas-menor" / "06-combinacao.md").read_text())
        # a primeira tarefa entregue é a da anomalia, que é a mais lenta
        self.assertIn("anomalia-1", run("claim.py", d / "tarefas").stdout)


class ClaimTest(unittest.TestCase):
    def test_cada_tarefa_sai_uma_vez(self):
        d = Path(tempfile.mkdtemp())
        (d / "analogia.md").write_text("lente analogia")
        (d / "inversao.md").write_text("lente inversao")
        saidas = [run("claim.py", d) for _ in range(3)]
        self.assertEqual(sorted(s.stdout.strip() for s in saidas[:2]), ["lente analogia", "lente inversao"])
        self.assertNotEqual(saidas[2].returncode, 0)
        self.assertIn("nenhuma tarefa livre", saidas[2].stderr)


if __name__ == "__main__":
    unittest.main()
