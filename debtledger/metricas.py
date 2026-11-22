"""Métricas sem IA: complexidade e histórico do git."""
from __future__ import annotations

import ast
import os
import re
import subprocess
from datetime import datetime, timezone

RAMIFICACOES = re.compile(r"\b(if|for|while|case|catch|elif|except)\b|&&|\|\|")


def _complexidade_ciclomatica(no: ast.AST) -> int:
    cc = 1
    for n in ast.walk(no):
        if isinstance(n, (ast.If, ast.For, ast.While, ast.IfExp, ast.ExceptHandler,
                          ast.With, ast.Assert, ast.AsyncFor)):
            cc += 1
        elif isinstance(n, ast.BoolOp):
            cc += len(n.values) - 1
        elif isinstance(n, ast.comprehension):
            cc += 1 + len(n.ifs)
        elif hasattr(ast, "match_case") and isinstance(n, ast.match_case):
            cc += 1
    return cc


def complexidade_python(codigo: str, linha: int) -> dict:
    try:
        arvore = ast.parse(codigo)
    except SyntaxError:
        return {"funcao": None, "complexidade": None, "tamanho_funcao": None}
    funcoes = [n for n in ast.walk(arvore)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    dentro = [f for f in funcoes if f.lineno <= linha <= (f.end_lineno or f.lineno)]
    if dentro:
        alvo = max(dentro, key=lambda f: f.lineno)  # a mais interna
    else:
        abaixo = [f for f in funcoes if 0 < f.lineno - linha <= 3]
        alvo = min(abaixo, key=lambda f: f.lineno) if abaixo else None
    if alvo is None:
        return {"funcao": "(nível de módulo)", "complexidade": 1, "tamanho_funcao": 0}
    return {
        "funcao": alvo.name,
        "complexidade": _complexidade_ciclomatica(alvo),
        "tamanho_funcao": (alvo.end_lineno or alvo.lineno) - alvo.lineno + 1,
    }


def complexidade_generica(codigo: str, linha: int) -> dict:
    linhas = codigo.splitlines()
    janela = linhas[max(0, linha - 10): linha + 30]
    cc = 1 + sum(len(RAMIFICACOES.findall(l)) for l in janela)
    return {"funcao": "(janela de 40 linhas)", "complexidade": cc, "tamanho_funcao": len(janela)}


def complexidade(raiz: str, arquivo: str, linha: int) -> dict:
    with open(os.path.join(raiz, arquivo), encoding="utf-8", errors="replace") as f:
        codigo = f.read()
    if arquivo.endswith(".py"):
        return complexidade_python(codigo, linha)
    return complexidade_generica(codigo, linha)


def _git(raiz: str, *args: str) -> str:
    r = subprocess.run(["git", "-C", raiz, *args], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return r.stdout


def eh_repositorio_git(raiz: str) -> bool:
    try:
        return _git(raiz, "rev-parse", "--is-inside-work-tree").strip() == "true"
    except (RuntimeError, FileNotFoundError):
        return False


def data_referencia(raiz: str) -> datetime:
    try:
        ts = int(_git(raiz, "log", "-1", "--format=%at").strip())
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (RuntimeError, ValueError, FileNotFoundError):
        return datetime.now(tz=timezone.utc)


def historico_arquivo(raiz: str, arquivo: str, ref: datetime, janela_dias: int = 365) -> dict:
    try:
        saida = _git(raiz, "log", "--follow", "--format=%at%x09%an", "--", arquivo)
    except (RuntimeError, FileNotFoundError):
        return {"commits_total": 0, "commits_janela": 0, "autores": [], "autores_qtd": 0}
    commits = []
    for l in saida.splitlines():
        if "\t" in l:
            ts, autor = l.split("\t", 1)
            commits.append((int(ts), autor))
    limite = ref.timestamp() - janela_dias * 86400
    autores = sorted({a for _, a in commits})
    return {
        "commits_total": len(commits),
        "commits_janela": sum(1 for ts, _ in commits if ts >= limite),
        "autores": autores,
        "autores_qtd": len(autores),
    }


def idade_linha(raiz: str, arquivo: str, linha: int, ref: datetime) -> dict:
    try:
        saida = _git(raiz, "blame", "--porcelain", "-L", f"{linha},{linha}", "--", arquivo)
    except (RuntimeError, FileNotFoundError):
        return {"introduzida_em": None, "introduzida_por": None, "idade_dias": None}
    ts, autor = None, None
    for l in saida.splitlines():
        if l.startswith("author-time "):
            ts = int(l.split()[1])
        elif l.startswith("author "):
            autor = l[len("author "):]
    if ts is None:  # linha ainda não commitada
        return {"introduzida_em": None, "introduzida_por": "(não commitado)", "idade_dias": 0}
    quando = datetime.fromtimestamp(ts, tz=timezone.utc)
    return {
        "introduzida_em": quando.date().isoformat(),
        "introduzida_por": autor,
        "idade_dias": max(0, (ref - quando).days),
    }


def medir(raiz: str, itens: list, janela_dias: int = 365) -> datetime:
    usar_git = eh_repositorio_git(raiz)
    ref = data_referencia(raiz) if usar_git else datetime.now(tz=timezone.utc)
    cache_hist: dict[str, dict] = {}
    for it in itens:
        m = complexidade(raiz, it.arquivo, it.linha)
        if usar_git:
            if it.arquivo not in cache_hist:
                cache_hist[it.arquivo] = historico_arquivo(raiz, it.arquivo, ref, janela_dias)
            m.update(cache_hist[it.arquivo])
            m.update(idade_linha(raiz, it.arquivo, it.linha, ref))
        else:
            m.update({"commits_total": 0, "commits_janela": 0, "autores": [],
                      "autores_qtd": 0, "introduzida_em": None,
                      "introduzida_por": None, "idade_dias": None})
        m["git_disponivel"] = usar_git
        it.metricas = m
    return ref
