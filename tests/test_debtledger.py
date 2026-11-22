import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from debtledger import coletor, metricas, priorizacao, registro, verificador  # noqa: E402
from debtledger.cli import main  # noqa: E402
from debtledger.ia import AnalistaClaude, AnalistaHeuristico  # noqa: E402

GERADOR = os.path.join(RAIZ, "exemplo", "criar_sigafin.py")


def criar_repo(destino, etapa=1):
    subprocess.run([sys.executable, GERADOR, "--destino", destino, "--etapa", str(etapa)],
                   check=True, capture_output=True)


def _rm(func, caminho, _):
    os.chmod(caminho, stat.S_IWRITE)
    func(caminho)


class ClienteFalso:
    """Imita client.beta.messages.create devolvendo respostas prontas."""

    def __init__(self, resposta):
        self.resposta = resposta
        self.chamadas = 0
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.chamadas += 1
        self.ultimo_pedido = kwargs
        bloco = SimpleNamespace(type="text", text=json.dumps(self.resposta))
        return SimpleNamespace(stop_reason="end_turn", content=[bloco])


RESPOSTA_BOA = {
    "e_divida": True, "tipo": "infraestrutura", "quadrante_fowler": "inadvertida-imprudente",
    "confianca": 0.9, "evidencia": "s.connect((HOST, PORTA))",
    "risco": "O lote noturno trava se o banco cair.", "esforco": "P",
    "estrategia": "corrigir_defeito", "primeiro_passo": "Adicionar s.settimeout(10).",
    "titulo_issue": "Timeout na conexão com o banco legado",
}


class TestDebtLedger(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.repo = os.path.join(cls.tmp, "sigafin")
        criar_repo(cls.repo)
        cls.itens = coletor.coletar(cls.repo)
        metricas.medir(cls.repo, cls.itens)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, onerror=_rm)

    def item(self, arquivo, texto):
        return next(i for i in self.itens if i.arquivo == arquivo and texto in i.comentario)

    def test_coleta_acha_todos_os_comentarios(self):
        self.assertEqual(len(self.itens), 12)
        gatilhos = {i.gatilho.upper() for i in self.itens}
        self.assertTrue({"TODO", "FIXME", "HACK", "XXX"} <= gatilhos)

    def test_metricas_da_funcao_gigante(self):
        it = self.item("faturamento/calculo_nota.py", "separar as regras")
        self.assertEqual(it.metricas["funcao"], "calcular_nota")
        self.assertGreaterEqual(it.metricas["complexidade"], 15)
        self.assertGreaterEqual(it.metricas["commits_janela"], 8)

    def test_conhecimento_concentrado(self):
        it = self.item("integracao/banco_legado.py", "sem timeout")
        self.assertEqual(it.metricas["autores"], ["Carlos Mendes"])
        self.assertEqual(it.metricas["introduzida_em"], "2019-03-11")

    def test_juros_maior_onde_mais_se_mexe(self):
        priorizacao.priorizar(self.itens)
        quente = self.item("faturamento/calculo_nota.py", "separar as regras").prioridade["juros"]
        frio = self.item("utils/datas.py", "fuso").prioridade["juros"]
        self.assertGreater(quente, frio)

    def test_ia_com_evidencia_real_fica_consistente(self):
        it = self.item("integracao/banco_legado.py", "sem timeout")
        cliente = ClienteFalso(RESPOSTA_BOA)
        analise = AnalistaClaude(cliente=cliente).analisar(it)
        v = verificador.verificar(it, analise, AnalistaHeuristico().analisar(it), True)
        self.assertEqual(v["status"], "consistente", v)
        pedido = cliente.ultimo_pedido
        self.assertEqual(pedido["output_config"]["format"]["type"], "json_schema")
        self.assertIn("banco_legado.py", pedido["messages"][0]["content"])

    def test_ia_inventando_evidencia_vira_suspeita(self):
        it = self.item("integracao/banco_legado.py", "sem timeout")
        inventada = dict(RESPOSTA_BOA, evidencia="pool.max_connections = 5")
        analise = AnalistaClaude(cliente=ClienteFalso(inventada)).analisar(it)
        v = verificador.verificar(it, analise, None, True)
        self.assertEqual(v["status"], "suspeita")

    def test_estimativa_otimista_e_sinalizada(self):
        it = self.item("faturamento/calculo_nota.py", "separar as regras")
        otimista = dict(RESPOSTA_BOA, tipo="design", estrategia="refatorar", esforco="P",
                        evidencia="essa funcao virou um monstro")
        v = verificador.verificar(it, otimista, None, True)
        coerencia = next(c for c in v["checagens"] if c["nome"] == "coerência com métricas")
        self.assertFalse(coerencia["ok"])

    def test_cache_evita_chamada_repetida(self):
        it = self.item("integracao/banco_legado.py", "sem timeout")
        cache = os.path.join(self.tmp, "cache.json")
        cliente = ClienteFalso(RESPOSTA_BOA)
        AnalistaClaude(cliente=cliente, cache_path=cache).analisar(it)
        AnalistaClaude(cliente=cliente, cache_path=cache).analisar(it)
        self.assertEqual(cliente.chamadas, 1)

    def test_id_nao_muda_quando_a_linha_muda(self):
        a = coletor.ItemSATD("x.py", 10, "TODO: arrumar", "", "TODO")
        b = coletor.ItemSATD("x.py", 42, "TODO:  arrumar", "", "TODO")
        self.assertEqual(a.id, b.id)


class TestEvolucao(unittest.TestCase):
    def test_ledger_detecta_quitadas_e_novas(self):
        tmp = tempfile.mkdtemp()
        try:
            repo = os.path.join(tmp, "sigafin")
            criar_repo(repo)
            saida = os.path.join(tmp, "saida")
            with open(os.devnull, "w", encoding="utf-8") as nulo:
                antigo, sys.stdout = sys.stdout, nulo
                try:
                    self.assertEqual(main([repo, "--modo", "offline", "--saida", saida]), 0)
                    criar_repo(repo, etapa=2)
                    self.assertEqual(main([repo, "--modo", "offline", "--saida", saida]), 0)
                finally:
                    sys.stdout = antigo
            ledger = registro.carregar(os.path.join(saida, "ledger.json"))
            ultima = ledger["execucoes"][-1]
            self.assertEqual((ultima["novas"], ultima["quitadas"]), (1, 2))
            self.assertTrue(os.path.exists(os.path.join(saida, "extrato.html")))
        finally:
            shutil.rmtree(tmp, onerror=_rm)


if __name__ == "__main__":
    unittest.main()
