"""Acha comentários de dívida técnica autoadmitida (TODO, FIXME, gambiarra...)."""
from __future__ import annotations

import hashlib
import os
import re
import unicodedata
from dataclasses import dataclass, field

LINGUAGENS = {
    ".py": "#", ".rb": "#", ".sh": "#",
    ".js": "//", ".ts": "//", ".java": "//", ".cs": "//",
    ".c": "//", ".cpp": "//", ".h": "//", ".go": "//", ".php": "//", ".kt": "//",
}

PASTAS_IGNORADAS = {".git", "node_modules", "venv", ".venv", "__pycache__",
                    "dist", "build", ".idea", ".vscode", "target", ".debtledger"}

PADROES = [
    r"\bTODO\b", r"\bFIXME\b", r"\bHACK\b", r"\bXXX\b", r"\bKLUDGE\b",
    r"\bworkaround\b", r"\bgambiarra\b", r"\bgambi\b", r"\bpaliativ",
    r"\btempor[aá]ri", r"\bprovis[oó]ri", r"\bremover depois\b",
    r"\brefatorar\b", r"\brefactor\b", r"\bcopiad[oa] de\b", r"\bcopy.?paste",
    r"\bhard.?coded\b", r"\bchumbad", r"\bn[aã]o sei (por ?qu|como)",
    r"\bnão mexa\b", r"\bnao mexa\b", r"\bdon'?t touch\b", r"\bugly\b",
    r"\bfeio\b", r"\bd[ií]vida t[eé]cnica\b", r"\bsó (o|a) \w+ sabe\b",
]
REGEX_SATD = re.compile("|".join(PADROES), re.IGNORECASE)


@dataclass
class ItemSATD:
    arquivo: str
    linha: int
    comentario: str
    trecho: str
    gatilho: str
    metricas: dict = field(default_factory=dict)
    analise: dict = field(default_factory=dict)
    verificacao: dict = field(default_factory=dict)
    prioridade: dict = field(default_factory=dict)
    decisao: str = ""  # vem do ledger.json

    @property
    def id(self) -> str:
        base = self.arquivo.replace("\\", "/") + "|" + normalizar(self.comentario)
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:10]


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().lower()


def extrair_comentario(linha: str, marcador: str) -> str | None:
    s = linha.strip()
    if marcador == "#":
        pos = linha.find("#")
        return linha[pos + 1:].strip() if pos >= 0 else None
    for m in ("//", "/*", "*"):
        if s.startswith(m):
            return s[len(m):].rstrip("*/ ").strip()
    pos = linha.find("//")
    return linha[pos + 2:].strip() if pos >= 0 else None


def montar_trecho(linhas: list[str], idx: int, antes: int = 6, depois: int = 14) -> str:
    ini, fim = max(0, idx - antes), min(len(linhas), idx + depois + 1)
    largura = len(str(fim))
    out = []
    for i in range(ini, fim):
        seta = ">>" if i == idx else "  "
        out.append(f"{seta} {str(i + 1).rjust(largura)} | {linhas[i].rstrip()}")
    return "\n".join(out)


def coletar(raiz: str) -> list[ItemSATD]:
    itens: list[ItemSATD] = []
    for pasta, subpastas, arquivos in os.walk(raiz):
        subpastas[:] = sorted(d for d in subpastas if d not in PASTAS_IGNORADAS)
        for nome in sorted(arquivos):
            ext = os.path.splitext(nome)[1].lower()
            if ext not in LINGUAGENS:
                continue
            caminho = os.path.join(pasta, nome)
            try:
                with open(caminho, encoding="utf-8", errors="replace") as f:
                    linhas = f.read().splitlines()
            except OSError:
                continue
            rel = os.path.relpath(caminho, raiz).replace("\\", "/")
            for i, linha in enumerate(linhas):
                comentario = extrair_comentario(linha, LINGUAGENS[ext])
                if not comentario:
                    continue
                achou = REGEX_SATD.search(comentario)
                if achou:
                    itens.append(ItemSATD(
                        arquivo=rel, linha=i + 1, comentario=comentario,
                        trecho=montar_trecho(linhas, i), gatilho=achou.group(0),
                    ))
    return itens
