"""Uso: python -m debtledger <repositorio> [--modo auto|ia|offline]"""
from __future__ import annotations

import argparse
import os
import sys

from . import coletor, metricas, priorizacao, registro, relatorio, verificador
from .ia import AnalistaClaude, AnalistaHeuristico, ErroIA, tem_credencial


def _uma_linha(texto: str, n: int) -> str:
    texto = " ".join(texto.split())
    return texto if len(texto) <= n else texto[: n - 1] + "…"


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    ap = argparse.ArgumentParser(prog="debtledger",
                                 description="Extrato da dívida técnica: juros medidos no git, análise por IA, verificação automática.")
    ap.add_argument("repositorio", help="pasta do projeto a analisar (de preferência um repositório git)")
    ap.add_argument("--saida", default=None, help="pasta dos relatórios (padrão: <repositorio>/.debtledger)")
    ap.add_argument("--modo", choices=["auto", "ia", "offline"], default="auto",
                    help="auto = usa IA se houver credencial; ia = exige IA; offline = só heurística")
    ap.add_argument("--modelo", default="claude-opus-5-5", help="modelo Claude usado no modo ia")
    ap.add_argument("--esforco", default="low", choices=["low", "medium", "high"],
                    help="nível de esforço (effort) do modelo; low basta para classificação")
    ap.add_argument("--limite", type=int, default=40, help="máximo de itens enviados para a IA")
    ap.add_argument("--janela", type=int, default=365, help="janela em dias para contar commits recentes")
    args = ap.parse_args(argv)

    raiz = os.path.abspath(args.repositorio)
    if not os.path.isdir(raiz):
        print(f"Pasta não encontrada: {raiz}")
        return 2
    saida = os.path.abspath(args.saida or os.path.join(raiz, ".debtledger"))

    print(f"[1/5] Procurando comentários de dívida em {raiz}")
    itens = coletor.coletar(raiz)
    print(f"      {len(itens)} candidato(s) encontrados")
    if not itens:
        print("Nada encontrado. Repositório limpo ou linguagem não suportada.")
        return 0

    print("[2/5] Medindo complexidade e histórico do git")
    ref = metricas.medir(raiz, itens, args.janela)
    if not itens[0].metricas["git_disponivel"]:
        print("      aviso: não é um repositório git; juros vão considerar só complexidade")

    heur = AnalistaHeuristico()
    analista, aviso = heur, ""
    if args.modo == "ia" or (args.modo == "auto" and tem_credencial()):
        try:
            analista = AnalistaClaude(args.modelo, args.esforco, os.path.join(saida, "cache_ia.json"))
        except Exception as e:
            if args.modo == "ia":
                print(f"Não consegui iniciar a IA: {e}")
                return 1
            aviso = f"IA indisponível ({e}); usando heurística."
    elif args.modo == "auto":
        aviso = "Nenhuma credencial da Anthropic encontrada; rodando em modo offline (sem IA)."
    print(f"[3/5] Analisando com: {analista.nome}")
    if aviso:
        print(f"      {aviso}")

    falhas_ia = 0
    for n, it in enumerate(itens, 1):
        segunda = heur.analisar(it)
        usou_ia = analista.usa_ia and n <= args.limite
        if usou_ia:
            try:
                it.analise = analista.analisar(it)
            except ErroIA as e:
                falhas_ia += 1
                print(f"      item {n}: IA falhou ({e}); usando heurística")
                it.analise, usou_ia = segunda, False
        else:
            it.analise = segunda
        it.verificacao = verificador.verificar(it, it.analise, segunda, usou_ia)
        print(f"      {n:>2}/{len(itens)} {it.arquivo}:{it.linha} -> {it.analise['tipo']} ({it.verificacao['status']})")
    if analista.usa_ia:
        print(f"      chamadas à API: {analista.chamadas_api} · respostas do cache: {analista.acertos_cache}"
              + (f" · falhas: {falhas_ia}" if falhas_ia else ""))

    print("[4/5] Calculando juros e atualizando o registro (ledger)")
    caminho_ledger = os.path.join(saida, "ledger.json")
    ledger = registro.carregar(caminho_ledger)
    data_ref = ref.date().isoformat()
    dif = registro.atualizar(ledger, itens, data_ref, "ia" if analista.usa_ia else "offline")
    registro.salvar(caminho_ledger, ledger)
    itens = priorizacao.priorizar(itens)

    print("[5/5] Gerando relatórios")
    ctx = {"repo": os.path.basename(raiz), "data_ref": data_ref, "analista": analista.nome,
           "usa_ia": analista.usa_ia, "aviso": aviso, "diferenca": dif, "ledger": ledger,
           "pesos": ", ".join(f"{int(v * 100)}% {k}" for k, v in priorizacao.PESOS.items())}
    caminhos = relatorio.escrever(saida, itens, ctx)

    print()
    print(f"{'#':>2}  {'juros':>5}  {'horas':>5}  {'quadrante':<30} {'verif.':<11} local")
    for n, it in enumerate(itens[:15], 1):
        p = it.prioridade
        print(f"{n:>2}  {p['juros']:>5}  {p['principal_horas']:>4}h  {p['quadrante']:<30} "
              f"{(it.decisao or it.verificacao['status']):<11} {it.arquivo}:{it.linha}  {_uma_linha(it.comentario, 45)}")
    if not dif["primeira_execucao"]:
        print(f"\nDesde a última análise: {len(dif['novas'])} nova(s), {len(dif['quitadas'])} quitada(s), "
              f"{len(dif['reabertas'])} reaberta(s)")
    print(f"\nRelatório: {caminhos['html']}\nBacklog:   {caminhos['backlog']}\nRegistro:  {caminho_ledger}")
    return 0
