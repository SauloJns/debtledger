"""Gera extrato.html, backlog.md e itens.json."""
from __future__ import annotations

import html
import json
import os

from .priorizacao import LIMITE_JUROS_ALTO, LIMITE_PRINCIPAL_ALTO

ROTULO_STATUS = {"consistente": "Consistente", "revisar": "Revisar", "suspeita": "Suspeita"}
COR_QUADRANTE = {"Pagar agora": "q1", "Planejar pagamento": "q2",
                 "Pagar quando passar por perto": "q3", "Monitorar / aceitar": "q4"}


def _e(x) -> str:
    return html.escape(str(x if x is not None else "—"))


def para_dict(it) -> dict:
    return {"id": it.id, "arquivo": it.arquivo, "linha": it.linha, "comentario": it.comentario,
            "gatilho": it.gatilho, "metricas": it.metricas, "analise": it.analise,
            "verificacao": it.verificacao, "prioridade": it.prioridade, "decisao": it.decisao}


def _grafico(itens: list) -> str:
    L, A, m = 640, 360, 48
    max_h = 44
    def x(h): return m + (h / max_h) * (L - 2 * m)
    def y(j): return A - m - (j / 100) * (A - 2 * m)
    xl, yl = x(LIMITE_PRINCIPAL_ALTO - 0.5), y(LIMITE_JUROS_ALTO)
    partes = [f'<svg viewBox="0 0 {L} {A}" role="img" aria-label="Juros por principal">',
              f'<rect x="{m}" y="{m}" width="{xl - m}" height="{yl - m}" class="z1"/>',
              f'<rect x="{xl}" y="{m}" width="{L - m - xl}" height="{yl - m}" class="z2"/>',
              f'<rect x="{m}" y="{yl}" width="{xl - m}" height="{A - m - yl}" class="z3"/>',
              f'<rect x="{xl}" y="{yl}" width="{L - m - xl}" height="{A - m - yl}" class="z4"/>',
              f'<text x="{m + 8}" y="{m + 18}" class="zl">PAGAR AGORA</text>',
              f'<text x="{L - m - 8}" y="{m + 18}" class="zl" text-anchor="end">PLANEJAR</text>',
              f'<text x="{m + 8}" y="{A - m - 8}" class="zl">QUANDO PASSAR POR PERTO</text>',
              f'<text x="{L - m - 8}" y="{A - m - 8}" class="zl" text-anchor="end">MONITORAR</text>',
              f'<line x1="{m}" y1="{A - m}" x2="{L - m}" y2="{A - m}" class="eixo"/>',
              f'<line x1="{m}" y1="{m}" x2="{m}" y2="{A - m}" class="eixo"/>',
              f'<text x="{L / 2}" y="{A - 12}" class="rot" text-anchor="middle">principal (horas para quitar)</text>',
              f'<text x="14" y="{A / 2}" class="rot" text-anchor="middle" transform="rotate(-90 14 {A / 2})">juros (0–100)</text>']
    for h in (4, 12, 40):
        partes.append(f'<text x="{x(h)}" y="{A - m + 16}" class="tick" text-anchor="middle">{h}h</text>')
    for j in (0, 50, 100):
        partes.append(f'<text x="{m - 6}" y="{y(j) + 4}" class="tick" text-anchor="end">{j}</text>')
    vistos: dict = {}
    for n, it in enumerate(itens, 1):
        h, j = it.prioridade["principal_horas"], it.prioridade["juros"]
        k = (h, round(j / 4))
        desloc = vistos.get(k, 0); vistos[k] = desloc + 1
        cx, cy = x(h) + desloc * 13, y(j)
        cls = "pt sus" if it.verificacao.get("status") == "suspeita" else "pt"
        partes.append(f'<g><title>#{n} {_e(it.arquivo)}:{it.linha} — juros {j}, {h}h</title>'
                      f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="9" class="{cls}"/>'
                      f'<text x="{cx:.1f}" y="{cy + 3.5:.1f}" class="ptn" text-anchor="middle">{n}</text></g>')
    partes.append("</svg>")
    return "".join(partes)


CSS = """
:root{--bg:#f7f6f2;--card:#fff;--ink:#1d1d1b;--mute:#6b6a64;--line:#e3e1d9;--acc:#2f5d50;
--q1:#fde2d8;--q2:#fdf0cf;--q3:#e2efe6;--q4:#ebebeb;--ok:#2e7d4f;--warn:#a86b00;--bad:#b3261e;--code:#f1efe8}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#171716;--card:#21211f;--ink:#ecebe6;
--mute:#a3a29b;--line:#34332f;--acc:#8fc7b2;--q1:#4a2a22;--q2:#463b1d;--q3:#213a2b;--q4:#2c2c2a;
--ok:#7fd3a0;--warn:#f0c060;--bad:#ff8a80;--code:#1b1b1a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1040px;margin:0 auto;padding:32px 16px 80px}
h1{font-size:28px;margin:0 0 4px;letter-spacing:-.01em}h2{font-size:19px;margin:40px 0 12px}
.sub{color:var(--mute);margin:0 0 20px}.banner{padding:10px 14px;border-radius:8px;border:1px solid var(--line);
background:var(--card);margin:16px 0}.banner b{color:var(--acc)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.kpi .v{font-size:26px;font-weight:650}.kpi .l{color:var(--mute);font-size:13px}
svg{width:100%;height:auto;background:var(--card);border:1px solid var(--line);border-radius:10px}
.z1{fill:var(--q1)}.z2{fill:var(--q2)}.z3{fill:var(--q3)}.z4{fill:var(--q4)}
.zl{font-size:11px;fill:var(--mute);font-weight:600;letter-spacing:.05em}.eixo{stroke:var(--mute)}
.rot{font-size:12px;fill:var(--mute)}.tick{font-size:11px;fill:var(--mute)}
.pt{fill:var(--acc)}.pt.sus{fill:var(--bad)}.ptn{font-size:10px;fill:var(--card);font-weight:700}
.tab{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.tab th,.tab td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;font-size:14px}
.tab th{font-size:12px;color:var(--mute);text-transform:uppercase;letter-spacing:.04em}
.wrap{overflow-x:auto}.tag{display:inline-block;padding:1px 8px;border-radius:99px;font-size:12px;white-space:nowrap}
.q1{background:var(--q1)}.q2{background:var(--q2)}.q3{background:var(--q3)}.q4{background:var(--q4)}
.s-consistente{color:var(--ok)}.s-revisar{color:var(--warn)}.s-suspeita{color:var(--bad)}
details{background:var(--card);border:1px solid var(--line);border-radius:10px;margin:10px 0;padding:0 14px}
summary{cursor:pointer;padding:12px 0;font-weight:600}summary span{font-weight:400;color:var(--mute)}
pre{background:var(--code);padding:10px;border-radius:8px;overflow-x:auto;font-size:12.5px;line-height:1.45}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}@media(max-width:720px){.grid2{grid-template-columns:1fr}}
dl{margin:0;display:grid;grid-template-columns:max-content 1fr;gap:4px 12px;font-size:14px}dt{color:var(--mute)}dd{margin:0}
ul.chk{list-style:none;padding:0;margin:0;font-size:14px}ul.chk li{padding:3px 0}
.mono{font-family:ui-monospace,Consolas,monospace;font-size:13px}.nota{color:var(--mute);font-size:13px}
"""


def gerar_html(itens: list, ctx: dict) -> str:
    total_h = sum(it.prioridade["principal_horas"] for it in itens if it.analise.get("e_divida", True))
    n_rev = sum(1 for it in itens if it.verificacao.get("status") != "consistente")
    agora = sum(1 for it in itens if it.prioridade["quadrante"] == "Pagar agora")
    dif = ctx["diferenca"]
    ev = ("primeira análise deste repositório" if dif["primeira_execucao"] else
          f'{len(dif["novas"])} nova(s), {len(dif["quitadas"])} quitada(s), {len(dif["reabertas"])} reaberta(s) desde a última análise')

    linhas_tab = []
    for n, it in enumerate(itens, 1):
        p, a, v = it.prioridade, it.analise, it.verificacao
        nova = " 🆕" if it.id in dif["novas"] else ""
        decisao = f'<br><span class="nota">decisão: {_e(it.decisao)}</span>' if it.decisao else ""
        linhas_tab.append(
            f'<tr><td>{n}</td><td class="mono">{_e(it.arquivo)}:{it.linha}{nova}</td>'
            f'<td>{_e(a.get("tipo"))}</td><td>{p["juros"]}</td><td>{p["principal_horas"]}h</td>'
            f'<td>{p["retorno"]}</td><td><span class="tag {COR_QUADRANTE[p["quadrante"]]}">{_e(p["quadrante"])}</span></td>'
            f'<td class="s-{v["status"]}">{ROTULO_STATUS[v["status"]]}{decisao}</td></tr>')

    cards = []
    for n, it in enumerate(itens, 1):
        p, a, v, m = it.prioridade, it.analise, it.verificacao, it.metricas
        chk = "".join(f'<li>{"✅" if c["ok"] else ("❌" if c["grave"] else "⚠️")} <b>{_e(c["nome"])}</b>: {_e(c["detalhe"])}</li>'
                      for c in v["checagens"])
        comp = " · ".join(f"{k} {val}" for k, val in p["componentes_juros"].items())
        cards.append(f"""<details{" open" if n <= 2 else ""}><summary>#{n} {_e(a.get("titulo_issue"))}
<span>— {_e(it.arquivo)}:{it.linha}</span></summary>
<p class="mono">“{_e(it.comentario)}”</p><pre>{_e(it.trecho)}</pre>
<div class="grid2"><div><h3>Análise ({_e(ctx["analista"])})</h3><dl>
<dt>É dívida?</dt><dd>{"sim" if a.get("e_divida") else "não"}</dd>
<dt>Tipo</dt><dd>{_e(a.get("tipo"))}</dd><dt>Quadrante de Fowler</dt><dd>{_e(a.get("quadrante_fowler"))}</dd>
<dt>Risco</dt><dd>{_e(a.get("risco"))}</dd><dt>Estratégia</dt><dd>{_e(a.get("estrategia"))}</dd>
<dt>Primeiro passo</dt><dd>{_e(a.get("primeiro_passo"))}</dd><dt>Evidência citada</dt><dd class="mono">{_e(a.get("evidencia"))}</dd>
<dt>Confiança</dt><dd>{_e(a.get("confianca"))}</dd></dl></div>
<div><h3>Métricas medidas (sem IA)</h3><dl>
<dt>Função</dt><dd class="mono">{_e(m.get("funcao"))}</dd><dt>Complexidade</dt><dd>{_e(m.get("complexidade"))}</dd>
<dt>Commits (12 meses / total)</dt><dd>{_e(m.get("commits_janela"))} / {_e(m.get("commits_total"))}</dd>
<dt>Pessoas no arquivo</dt><dd>{_e(m.get("autores_qtd"))} {_e(", ".join(m.get("autores") or []))}</dd>
<dt>Escrito em</dt><dd>{_e(m.get("introduzida_em"))} por {_e(m.get("introduzida_por"))} ({_e(m.get("idade_dias"))} dias)</dd>
<dt>Juros</dt><dd>{p["juros"]} <span class="nota">({comp})</span></dd>
<dt>Principal</dt><dd>{p["principal_horas"]}h (esforço {_e(a.get("esforco"))})</dd></dl></div></div>
<h3>Verificação automática — <span class="s-{v["status"]}">{ROTULO_STATUS[v["status"]]}</span></h3><ul class="chk">{chk}</ul>
<p class="nota">id no registro: <span class="mono">{it.id}</span> · para registrar sua decisão, edite o campo "decisao" deste id em ledger.json</p>
</details>""")

    quitadas = "".join(f'<li class="mono">{_e(ctx["ledger"]["itens"][i]["arquivo"])} — “{_e(ctx["ledger"]["itens"][i]["comentario"])}”</li>'
                       for i in dif["quitadas"]) or "<li>nenhuma</li>"
    hist = "".join(f'<tr><td>{_e(e["data_referencia"])}</td><td>{_e(e["modo"])}</td><td>{e["itens_abertos"]}</td>'
                   f'<td>{e["novas"]}</td><td>{e["quitadas"]}</td></tr>' for e in ctx["ledger"]["execucoes"])

    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Extrato da Dívida</title>
<style>{CSS}</style></head><body><main>
<h1>Extrato da dívida técnica</h1>
<p class="sub">Repositório <span class="mono">{_e(ctx["repo"])}</span> · referência: último commit em {_e(ctx["data_ref"])}</p>
<div class="banner">Análise feita por: <b>{_e(ctx["analista"])}</b>. {_e(ctx.get("aviso", ""))}<br>
<span class="nota">Tudo aqui é sugestão. Juros vêm de métricas medidas; tipo, esforço e estratégia vêm da {"IA" if ctx["usa_ia"] else "heurística"} e precisam de revisão humana.</span></div>
<div class="kpis"><div class="kpi"><div class="v">{len(itens)}</div><div class="l">itens de dívida abertos</div></div>
<div class="kpi"><div class="v">{total_h}h</div><div class="l">principal estimado</div></div>
<div class="kpi"><div class="v">{agora}</div><div class="l">para pagar agora</div></div>
<div class="kpi"><div class="v">{n_rev}</div><div class="l">precisam de revisão</div></div></div>
<p class="nota">Evolução: {_e(ev)}.</p>
<h2>Onde está o juro mais caro</h2>{_grafico(itens)}
<p class="nota">Cada ponto é um item (número = posição no ranking). Vermelho = a verificação achou problema grave na resposta.</p>
<h2>Ranking (quadrante primeiro, depois retorno por hora)</h2><div class="wrap"><table class="tab"><thead><tr><th>#</th><th>Local</th>
<th>Tipo</th><th>Juros</th><th>Principal</th><th>Retorno</th><th>Quadrante</th><th>Verificação</th></tr></thead>
<tbody>{"".join(linhas_tab)}</tbody></table></div>
<h2>Detalhes de cada item</h2>{"".join(cards)}
<h2>Dívidas quitadas desde a última análise</h2><ul>{quitadas}</ul>
<h2>Histórico de execuções</h2><div class="wrap"><table class="tab"><thead><tr><th>Referência</th><th>Modo</th>
<th>Abertos</th><th>Novas</th><th>Quitadas</th></tr></thead><tbody>{hist}</tbody></table></div>
<p class="nota">Gerado pelo DebtLedger. Juros = {ctx["pesos"]} (normalizados de 0 a 1, ×100).</p>
</main></body></html>"""


def gerar_backlog(itens: list, ctx: dict) -> str:
    out = [f"# Backlog de dívida técnica — {ctx['repo']}", "",
           f"Gerado em {ctx['data_ref']} por {ctx['analista']}. "
           "Revise cada item antes de abrir a issue; a classificação é uma sugestão.", ""]
    for n, it in enumerate(itens, 1):
        a, p, v = it.analise, it.prioridade, it.verificacao
        if a.get("e_divida") is False or it.decisao == "falso_positivo":
            continue
        alertas = [c["detalhe"] for c in v["checagens"] if not c["ok"]]
        out += [f"## {n}. {a.get('titulo_issue')}", "",
                f"- **Onde:** `{it.arquivo}:{it.linha}` — “{it.comentario}”",
                f"- **Tipo:** {a.get('tipo')} · **Quadrante de Fowler:** {a.get('quadrante_fowler')}",
                f"- **Prioridade:** {p['quadrante']} (juros {p['juros']}, principal ~{p['principal_horas']}h)",
                f"- **Risco se não pagar:** {a.get('risco')}",
                f"- **Estratégia:** {a.get('estrategia')} — primeiro passo: {a.get('primeiro_passo')}",
                f"- **Verificação:** {ROTULO_STATUS[v['status']]}" + (f" — {'; '.join(alertas)}" if alertas else ""),
                f"- **Rótulos sugeridos:** `divida-tecnica`, `td:{a.get('tipo')}`", ""]
    return "\n".join(out)


def escrever(saida: str, itens: list, ctx: dict) -> dict:
    os.makedirs(saida, exist_ok=True)
    caminhos = {"html": os.path.join(saida, "extrato.html"),
                "backlog": os.path.join(saida, "backlog.md"),
                "json": os.path.join(saida, "itens.json")}
    with open(caminhos["html"], "w", encoding="utf-8") as f:
        f.write(gerar_html(itens, ctx))
    with open(caminhos["backlog"], "w", encoding="utf-8") as f:
        f.write(gerar_backlog(itens, ctx))
    with open(caminhos["json"], "w", encoding="utf-8") as f:
        json.dump([para_dict(it) for it in itens], f, ensure_ascii=False, indent=2)
    return caminhos
