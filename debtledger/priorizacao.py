"""Juros, principal e prioridade de cada item."""
from __future__ import annotations

HORAS = {"P": 4, "M": 12, "G": 40}

# pesos escolhidos por mim, dá pra ajustar
PESOS = {"frequencia": 0.45, "complexidade": 0.30, "idade": 0.15, "conhecimento": 0.10}

ORDEM_QUADRANTE = ["Pagar agora", "Planejar pagamento",
                   "Pagar quando passar por perto", "Monitorar / aceitar"]

LIMITE_JUROS_ALTO = 50
LIMITE_PRINCIPAL_ALTO = 12


def calcular_juros(m: dict, max_commits: int) -> tuple[float, dict]:
    freq = (m.get("commits_janela") or 0) / max_commits if max_commits else 0
    comp = min((m.get("complexidade") or 1) / 15, 1.0)
    idade = min((m.get("idade_dias") or 0) / (5 * 365), 1.0)
    autores = m.get("autores_qtd") or 0
    conh = 1.0 if autores == 1 else (0.5 if autores == 2 else 0.0)
    partes = {"frequencia": freq, "complexidade": comp, "idade": idade, "conhecimento": conh}
    juros = 100 * sum(PESOS[k] * v for k, v in partes.items())
    return round(juros, 1), {k: round(v, 2) for k, v in partes.items()}


def quadrante(juros: float, horas: int) -> str:
    alto_j = juros >= LIMITE_JUROS_ALTO
    alto_p = horas >= LIMITE_PRINCIPAL_ALTO
    if alto_j and not alto_p:
        return "Pagar agora"
    if alto_j and alto_p:
        return "Planejar pagamento"
    if not alto_j and not alto_p:
        return "Pagar quando passar por perto"
    return "Monitorar / aceitar"


def priorizar(itens: list) -> list:
    max_commits = max((it.metricas.get("commits_janela") or 0 for it in itens), default=0)
    for it in itens:
        juros, partes = calcular_juros(it.metricas, max_commits)
        horas = HORAS.get(it.analise.get("esforco"), 12)
        it.prioridade = {
            "juros": juros,
            "componentes_juros": partes,
            "principal_horas": horas,
            "retorno": round(juros / horas, 2),
            "quadrante": quadrante(juros, horas),
        }
    # quadrante primeiro, depois retorno por hora; descartados vão pro fim
    def chave(it):
        descartado = it.analise.get("e_divida") is False or it.decisao == "falso_positivo"
        return (descartado, ORDEM_QUADRANTE.index(it.prioridade["quadrante"]),
                -it.prioridade["retorno"], -it.prioridade["juros"])
    return sorted(itens, key=chave)
