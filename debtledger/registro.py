"""Ledger: acompanha os itens entre uma análise e outra."""
from __future__ import annotations

import json
import os

DECISOES_VALIDAS = {"", "aceita", "falso_positivo", "em_andamento", "agendada"}


def carregar(caminho: str) -> dict:
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    return {"execucoes": [], "itens": {}}


def salvar(caminho: str, ledger: dict) -> None:
    os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=2)


def atualizar(ledger: dict, itens: list, data_ref: str, modo: str) -> dict:
    registros = ledger.setdefault("itens", {})
    primeira_execucao = not ledger.get("execucoes")
    atuais = {it.id: it for it in itens}
    novas, reabertas, quitadas = [], [], []

    for id_, it in atuais.items():
        reg = registros.get(id_)
        if reg is None:
            registros[id_] = {"arquivo": it.arquivo, "comentario": it.comentario,
                              "primeira_vez": data_ref, "ultima_vez": data_ref,
                              "status": "aberta", "decisao": "", "nota": ""}
            if not primeira_execucao:
                novas.append(id_)
        else:
            if reg["status"] == "quitada":
                reabertas.append(id_)
            reg.update({"status": "aberta", "ultima_vez": data_ref, "arquivo": it.arquivo})
            reg.pop("quitada_em", None)
        decisao = registros[id_].get("decisao", "")
        it.decisao = decisao if decisao in DECISOES_VALIDAS else ""

    for id_, reg in registros.items():
        if reg["status"] == "aberta" and id_ not in atuais:
            reg["status"] = "quitada"
            reg["quitada_em"] = data_ref
            quitadas.append(id_)

    ledger.setdefault("execucoes", []).append({
        "data_referencia": data_ref, "modo": modo, "itens_abertos": len(atuais),
        "novas": len(novas), "quitadas": len(quitadas), "reabertas": len(reabertas),
    })
    return {"novas": novas, "quitadas": quitadas, "reabertas": reabertas,
            "primeira_execucao": primeira_execucao}
