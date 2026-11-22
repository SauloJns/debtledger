"""Confere a resposta da IA antes de alguém confiar nela."""
from __future__ import annotations

import re

from .coletor import normalizar
from .ia import ESFORCOS, ESTRATEGIAS, QUADRANTES, TIPOS

VIZINHOS = [{"design", "codigo", "arquitetura"}, {"defeito", "requisito"},
            {"build", "infraestrutura"}, {"documentacao", "pessoas"}]


def _codigo_sem_numeros(trecho: str) -> str:
    return "\n".join(re.sub(r"^(>>|  )\s*\d+ \| ", "", l) for l in trecho.splitlines())


def verificar(item, analise: dict, segunda_opiniao: dict | None, usa_ia: bool) -> dict:
    checagens = []

    def checar(nome, ok, detalhe, grave=True):
        checagens.append({"nome": nome, "ok": bool(ok), "detalhe": detalhe, "grave": grave})

    fora = [c for c, v in (("tipo", TIPOS), ("quadrante_fowler", QUADRANTES),
                           ("esforco", ESFORCOS), ("estrategia", ESTRATEGIAS))
            if analise.get(c) not in v]
    checar("formato", not fora,
           "todos os campos dentro da taxonomia" if not fora else f"valores fora da taxonomia: {', '.join(fora)}")

    if usa_ia:
        # a citação da IA tem que existir no código (pega alucinação)
        ev = normalizar(analise.get("evidencia", ""))
        codigo = normalizar(_codigo_sem_numeros(item.trecho))
        achou = len(ev) >= 4 and ev in codigo
        checar("evidência no código", achou,
               "a citação da IA foi encontrada no trecho" if achou
               else f"a citação \"{analise.get('evidencia', '')[:60]}\" NÃO existe no trecho (possível alucinação)")

        conf = float(analise.get("confianca", 0) or 0)
        checar("confiança", conf >= 0.6, f"confiança declarada: {conf:.2f}", grave=False)

        if segunda_opiniao:
            a, b = analise.get("tipo"), segunda_opiniao.get("tipo")
            vizinho = any(a in g and b in g for g in VIZINHOS)
            checar("concordância", a == b or vizinho,
                   f"IA: {a} | heurística: {b}" + (" (tipos próximos)" if vizinho and a != b else ""),
                   grave=False)

        # função muito complexa dificilmente se refatora em meio dia
        cc = item.metricas.get("complexidade") or 0
        incoerente = cc >= 15 and analise.get("esforco") == "P" and analise.get("estrategia") == "refatorar"
        checar("coerência com métricas", not incoerente,
               "estimativa compatível com a complexidade medida" if not incoerente
               else f"refatorar função com complexidade {cc} em esforço P parece otimista", grave=False)

        if analise.get("e_divida") is False:
            checar("é dívida?", False, "a IA acha que não é dívida técnica; confirme antes de descartar", grave=False)
    else:
        checar("origem", False, "classificação feita por palavras-chave, sem IA", grave=False)

    graves = [c for c in checagens if not c["ok"] and c["grave"]]
    leves = [c for c in checagens if not c["ok"] and not c["grave"]]
    if graves:
        status = "suspeita"
    elif leves:
        status = "revisar"
    else:
        status = "consistente"
    return {"status": status, "checagens": checagens}
