"""Cria o SIGAFIN, um sistema legado fictício de faturamento, com histórico git
de 2019 a 2026 e quatro pessoas diferentes mexendo nele.

  python exemplo/criar_sigafin.py            -> cria demo/sigafin
  python exemplo/criar_sigafin.py --etapa 2  -> a equipe paga duas dívidas e cria uma nova
"""
from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess

AUTORES = {
    "carlos": ("Carlos Mendes", "carlos@sigafin.example"),
    "ana": ("Ana Souza", "ana@sigafin.example"),
    "rafael": ("Rafael Lima", "rafael@sigafin.example"),
    "julia": ("Julia Rocha", "julia@sigafin.example"),
}

ARQUIVOS_INICIAIS = {
"README.txt": """SIGAFIN - Sistema de Faturamento (distribuidora)
Versao 2.3 - em producao desde 2019.
Contato: Carlos (TI)
""",

"faturamento/__init__.py": "",

"faturamento/calculo_nota.py": '''"""Calculo da nota fiscal de venda.

Modulo original de 2019. Boa parte das regras veio da planilha do financeiro.
"""
from faturamento.impostos import aliquota_icms, calcula_st
from integracao.banco_legado import busca_cliente, busca_produto

FRETE_MINIMO = 12.0
DESCONTO_MAX = 0.30
UFS_ZONA_FRANCA = ("AM",)


# HACK: arredondamento manual porque o Decimal quebrava o relatorio antigo do financeiro
def arredonda(valor):
    return int(valor * 100 + 0.5) / 100.0


# TODO: separar as regras de imposto por estado, essa funcao virou um monstro
def calcular_nota(pedido, cliente_id, uf_destino, cupom=None, vendedor=None):
    cliente = busca_cliente(cliente_id)
    total = 0
    itens = []
    for item in pedido["itens"]:
        produto = busca_produto(item["codigo"])
        if produto is None:
            continue
        preco = produto["preco"]
        if cliente["tipo"] == "atacado":
            if item["qtd"] >= 100:
                preco = preco * 0.85
            elif item["qtd"] >= 50:
                preco = preco * 0.90
            else:
                preco = preco * 0.95
        elif cliente["tipo"] == "varejo" and cupom:
            if cupom.startswith("PROMO"):
                preco = preco * 0.9
            elif cupom == "FUNCIONARIO":
                preco = preco * 0.8
        icms = aliquota_icms(uf_destino)
        if produto.get("st") and uf_destino != "SP":
            icms = icms + calcula_st(produto, uf_destino)
        if uf_destino in UFS_ZONA_FRANCA and produto.get("zona_franca"):
            icms = 0
        valor = arredonda(preco * item["qtd"] * (1 + icms))
        itens.append({"codigo": item["codigo"], "valor": valor})
        total += valor
    desconto = 0
    if vendedor and vendedor.get("pode_dar_desconto"):
        desconto = min(pedido.get("desconto", 0), DESCONTO_MAX)
    frete = pedido.get("frete", 0)
    if frete < FRETE_MINIMO and uf_destino != "SP":
        frete = FRETE_MINIMO
    total = arredonda(total * (1 - desconto) + frete)
    return {"cliente": cliente["nome"], "itens": itens, "total": total}
''',

"faturamento/impostos.py": '''"""Aliquotas e substituicao tributaria."""

ALIQUOTAS_ICMS = {"SP": 0.18, "RJ": 0.20}


def aliquota_icms(uf):
    # FIXME: aliquota padrao chumbada em 0.17, mudou em 2023 e ninguem atualizou
    return ALIQUOTAS_ICMS.get(uf, 0.17)


def calcula_st(produto, uf):
    # TODO: revisar MVA por estado, hoje usa o mesmo para todos
    mva = 0.4
    return produto.get("aliquota_st", 0.0) * mva
''',

"integracao/__init__.py": "",

"integracao/banco_legado.py": '''"""Acesso ao banco do sistema antigo (Firebird via gateway proprio).

Nao mexa sem falar com o Carlos.
"""
import json
import socket

HOST = "10.0.0.12"
PORTA = 3050


def _conectar():
    s = socket.socket()
    # XXX: conexao sem timeout; se o servidor cair, o lote noturno inteiro trava
    s.connect((HOST, PORTA))
    return s


def _consulta(comando):
    con = _conectar()
    con.sendall(comando.encode("latin-1"))
    resposta = con.recv(65536).decode("latin-1")
    con.close()
    return json.loads(resposta) if resposta else None


# workaround temporario ate migrarmos para a API nova de clientes (combinado em 2019)
def busca_cliente(cliente_id):
    return _consulta("CLI " + str(cliente_id))


def busca_produto(codigo):
    return _consulta("PRD " + str(codigo))
''',

"relatorios/__init__.py": "",

"relatorios/exporta_csv.py": '''"""Exporta o fechamento mensal para o sistema do contador."""
import os


# TODO: documentar o layout deste arquivo. So o Carlos sabe o que e cada coluna
def exporta_fechamento(notas, caminho):
    with open(caminho, "w") as f:
        for n in notas:
            colunas = [n["cliente"][:30].ljust(30), "%012.2f" % n["total"],
                       "S" if n["total"] > 0 else "N", "01", ""]
            f.write(";".join(colunas) + "\\n")


def total_por_cliente(notas):
    totais = {}
    for n in notas:
        totais[n["cliente"]] = totais.get(n["cliente"], 0) + n["total"]
    return totais


def gera_pdf_resumo(notas, destino):
    # O arquivo temporario do relatorio e apagado no final da funcao
    tmp = destino + ".tmp"
    with open(tmp, "w") as f:
        f.write(str(total_por_cliente(notas)))
    os.replace(tmp, destino)
''',

"clientes/__init__.py": "",

"clientes/cadastro.py": '''"""Cadastro de clientes."""


def cadastra_cliente(dados):
    if not dados.get("nome"):
        raise ValueError("nome obrigatorio")
    return {"nome": dados["nome"].upper(), "documento": dados.get("documento", "")}
''',

"utils/__init__.py": "",

"utils/datas.py": '''"""Funcoes de data usadas em todo o sistema."""
from datetime import datetime


# TODO: tratar fuso horario; hoje assume que o servidor esta em Brasilia
def agora():
    return datetime.now()


def competencia(data):
    return data.strftime("%m/%Y")
''',

"tests/test_impostos.py": '''from faturamento.impostos import aliquota_icms


def test_aliquota_sp():
    assert aliquota_icms("SP") == 0.18
''',
}


# Cada commit: (data, autor, mensagem, [(arquivo, texto_antigo, texto_novo), ...])
# texto_antigo=None significa "criar/sobrescrever o arquivo com texto_novo".
HISTORICO_ETAPA_1 = [
    ("2019-03-11T10:00:00", "carlos", "Versao inicial do SIGAFIN", "INICIAL"),
    ("2019-08-02T15:20:00", "carlos", "Inclui aliquota de MG", [
        ("faturamento/impostos.py", '"RJ": 0.20}', '"RJ": 0.20, "MG": 0.18}')]),
    ("2020-02-14T09:10:00", "carlos", "Ajusta frete minimo", [
        ("faturamento/calculo_nota.py", "FRETE_MINIMO = 12.0", "FRETE_MINIMO = 13.5")]),
    ("2020-06-30T18:45:00", "carlos", "Separador do fechamento passa a ser ponto e virgula", [
        ("relatorios/exporta_csv.py", '"01", ""]', '"01", "", ""]')]),
    ("2021-04-19T11:00:00", "ana", "Cadastro de cliente aceita documento", [
        ("clientes/cadastro.py", '    if not dados.get("nome"):',
         '    # TODO: validar CPF/CNPJ (o cliente pediu em 2021 e ainda nao fizemos)\n    if not dados.get("nome"):')]),
    ("2021-09-08T14:30:00", "ana", "Arredondamento no cadastro de limite de credito", [
        ("clientes/cadastro.py", '"""Cadastro de clientes."""\n',
         '"""Cadastro de clientes."""\n\n\n# copiado de calculo_nota.arredonda, refatorar depois\n'
         'def arredonda(valor):\n    return int(valor * 100 + 0.5) / 100.0\n')]),
    ("2022-11-03T16:00:00", "carlos", "Permite nota de devolucao", [
        ("faturamento/calculo_nota.py", "    total = arredonda(total * (1 - desconto) + frete)",
         "    # XXX: se o total vier negativo (devolucao) a nota sai assim mesmo, ninguem confirmou com o fiscal\n"
         "    total = arredonda(total * (1 - desconto) + frete)")]),
    ("2023-07-21T10:15:00", "rafael", "Inclui aliquota do PR", [
        ("faturamento/impostos.py", '"MG": 0.18}', '"MG": 0.18, "PR": 0.195}')]),
    ("2025-12-04T09:00:00", "rafael", "Zona franca inclui RR e AP", [
        ("faturamento/calculo_nota.py", 'UFS_ZONA_FRANCA = ("AM",)', 'UFS_ZONA_FRANCA = ("AM", "RR", "AP")')]),
    ("2026-01-15T13:40:00", "julia", "Novo desconto de atacado acima de 100 unidades", [
        ("faturamento/calculo_nota.py", "preco = preco * 0.85", "preco = preco * 0.83")]),
    ("2026-02-20T17:05:00", "rafael", "Aliquota RJ atualizada", [
        ("faturamento/impostos.py", '"RJ": 0.20', '"RJ": 0.22')]),
    ("2026-03-10T10:30:00", "ana", "Frete minimo reajustado", [
        ("faturamento/calculo_nota.py", "FRETE_MINIMO = 13.5", "FRETE_MINIMO = 15.0")]),
    ("2026-04-28T15:00:00", "julia", "Cupom FUNCIONARIO limitado a 20%", [
        ("faturamento/calculo_nota.py", 'elif cupom == "FUNCIONARIO":', 'elif cupom == "FUNCIONARIO" and vendedor is None:')]),
    ("2026-05-19T11:20:00", "rafael", "Inclui aliquota de SC", [
        ("faturamento/impostos.py", '"PR": 0.195}', '"PR": 0.195, "SC": 0.17}')]),
    ("2026-06-22T09:45:00", "julia", "Desconto maximo do vendedor cai para 25%", [
        ("faturamento/calculo_nota.py", "DESCONTO_MAX = 0.30", "DESCONTO_MAX = 0.25")]),
    ("2026-07-30T16:10:00", "rafael", "Corrige desconto de atacado 50+", [
        ("faturamento/calculo_nota.py", "preco = preco * 0.90\n", "preco = preco * 0.89\n")]),
    ("2026-08-25T14:00:00", "ana", "Aliquota MG atualizada", [
        ("faturamento/impostos.py", '"MG": 0.18', '"MG": 0.185')]),
    ("2026-09-17T10:00:00", "julia", "Cupom PROMO10 e PROMO15", [
        ("faturamento/calculo_nota.py", 'if cupom.startswith("PROMO"):\n                preco = preco * 0.9',
         'if cupom.startswith("PROMO"):\n                preco = preco * (0.85 if cupom == "PROMO15" else 0.9)')]),
    ("2026-10-08T11:30:00", "rafael", "Cadastro grava nome sem espacos extras", [
        ("clientes/cadastro.py", 'dados["nome"].upper()', 'dados["nome"].strip().upper()')]),
    ("2026-10-29T15:50:00", "ana", "Frete gratis para SP acima de 500", [
        ("faturamento/calculo_nota.py", 'if frete < FRETE_MINIMO and uf_destino != "SP":',
         'if total > 500 and uf_destino == "SP":\n        frete = 0\n    elif frete < FRETE_MINIMO and uf_destino != "SP":')]),
    ("2026-11-10T09:15:00", "julia", "Aliquota padrao do ES", [
        ("faturamento/impostos.py", '"SC": 0.17}', '"SC": 0.17, "ES": 0.17}')]),
]

HISTORICO_ETAPA_2 = [
    ("2026-11-18T10:00:00", "ana", "Documenta o layout do fechamento (conversa com o Carlos)", [
        ("relatorios/exporta_csv.py",
         "# TODO: documentar o layout deste arquivo. So o Carlos sabe o que e cada coluna\n",
         "# Layout documentado em docs/LAYOUT_FECHAMENTO.md\n"),
        ("docs/LAYOUT_FECHAMENTO.md", None,
         "# Layout do fechamento mensal\n\n| Coluna | Conteudo | Tamanho |\n|---|---|---|\n"
         "| 1 | Nome do cliente | 30 |\n| 2 | Total da nota | 12 |\n| 3 | Nota positiva (S/N) | 1 |\n"
         "| 4 | Filial (sempre 01) | 2 |\n| 5-6 | Reservado | - |\n")]),
    ("2026-11-19T14:30:00", "rafael", "Timeout na conexao com o banco legado", [
        ("integracao/banco_legado.py",
         "    # XXX: conexao sem timeout; se o servidor cair, o lote noturno inteiro trava\n",
         "    s.settimeout(10)\n")]),
    ("2026-11-20T16:00:00", "julia", "Cashback do app (primeira versao)", [
        ("faturamento/calculo_nota.py", "    desconto = 0\n",
         "    desconto = 0\n    # TODO: cashback do app entra como desconto por enquanto, depois precisa virar credito\n"
         "    if pedido.get(\"cashback\"):\n        desconto = pedido[\"cashback\"]\n")]),
]


def git(repo, *args, env=None):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, env=env)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr}")
    return r.stdout


def escrever(repo, rel, conteudo):
    caminho = os.path.join(repo, rel)
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as f:
        f.write(conteudo)


def aplicar(repo, edicoes):
    for rel, antigo, novo in edicoes:
        if antigo is None and novo is None:
            continue
        if antigo is None:
            escrever(repo, rel, novo)
            continue
        caminho = os.path.join(repo, rel)
        with open(caminho, encoding="utf-8") as f:
            texto = f.read()
        if antigo not in texto:
            raise RuntimeError(f"trecho não encontrado em {rel}: {antigo!r}")
        escrever(repo, rel, texto.replace(antigo, novo, 1))


def commitar(repo, data, autor, msg):
    nome, email = AUTORES[autor]
    env = dict(os.environ, GIT_AUTHOR_NAME=nome, GIT_AUTHOR_EMAIL=email,
               GIT_COMMITTER_NAME=nome, GIT_COMMITTER_EMAIL=email,
               GIT_AUTHOR_DATE=data + " -0300", GIT_COMMITTER_DATE=data + " -0300")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg, env=env)


def _remover(func, caminho, _):
    os.chmod(caminho, stat.S_IWRITE)  # o Windows marca objetos do git como somente leitura
    func(caminho)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--destino", default=os.path.join(os.path.dirname(__file__), "..", "demo", "sigafin"))
    ap.add_argument("--etapa", type=int, choices=[1, 2], default=1)
    args = ap.parse_args()
    repo = os.path.abspath(args.destino)

    if args.etapa == 1:
        if os.path.exists(repo):
            shutil.rmtree(repo, onerror=_remover)
        os.makedirs(repo)
        git(repo, "init", "-q", "-b", "main")
        git(repo, "config", "core.autocrlf", "false")
        for data, autor, msg, edicoes in HISTORICO_ETAPA_1:
            if edicoes == "INICIAL":
                for rel, conteudo in ARQUIVOS_INICIAIS.items():
                    escrever(repo, rel, conteudo)
            else:
                aplicar(repo, edicoes)
            commitar(repo, data, autor, msg)
        print(f"SIGAFIN criado em {repo} ({len(HISTORICO_ETAPA_1)} commits, 2019-2026)")
    else:
        if not os.path.isdir(os.path.join(repo, ".git")):
            raise SystemExit("Rode a etapa 1 antes.")
        for data, autor, msg, edicoes in HISTORICO_ETAPA_2:
            aplicar(repo, edicoes)
            commitar(repo, data, autor, msg)
        print(f"Etapa 2 aplicada: {len(HISTORICO_ETAPA_2)} commits novos (duas dívidas pagas, uma nova)")


if __name__ == "__main__":
    main()
