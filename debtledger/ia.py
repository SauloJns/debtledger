"""Análise dos itens: Claude (API da Anthropic) ou heurística offline."""
from __future__ import annotations

import hashlib
import json
import os
import re

from .coletor import normalizar

# tipos de dívida: Alves et al. (2016)
TIPOS = ["arquitetura", "design", "codigo", "teste", "documentacao",
         "defeito", "requisito", "build", "infraestrutura", "pessoas"]

# quadrante de Fowler (2009)
QUADRANTES = ["deliberada-prudente", "deliberada-imprudente",
              "inadvertida-prudente", "inadvertida-imprudente"]

ESFORCOS = ["P", "M", "G"]
ESTRATEGIAS = ["refatorar", "adicionar_testes", "documentar", "substituir_componente",
               "corrigir_defeito", "remover_codigo", "aceitar_divida"]

SCHEMA = {
    "type": "object",
    "properties": {
        "e_divida": {"type": "boolean",
                     "description": "false se o comentário não representa dívida técnica de verdade"},
        "tipo": {"type": "string", "enum": TIPOS},
        "quadrante_fowler": {"type": "string", "enum": QUADRANTES},
        "confianca": {"type": "number", "description": "entre 0 e 1"},
        "evidencia": {"type": "string",
                      "description": "trecho COPIADO LITERALMENTE do código ou comentário que justifica a classificação"},
        "risco": {"type": "string", "description": "o que acontece se a dívida não for paga (1 a 2 frases)"},
        "esforco": {"type": "string", "enum": ESFORCOS,
                    "description": "P = até meio dia, M = 1 a 2 dias, G = uma semana ou mais"},
        "estrategia": {"type": "string", "enum": ESTRATEGIAS},
        "primeiro_passo": {"type": "string", "description": "ação concreta e pequena para começar a pagar"},
        "titulo_issue": {"type": "string", "description": "título curto para registrar no backlog"},
    },
    "required": ["e_divida", "tipo", "quadrante_fowler", "confianca", "evidencia",
                 "risco", "esforco", "estrategia", "primeiro_passo", "titulo_issue"],
    "additionalProperties": False,
}

SISTEMA = """Você é um engenheiro de software sênior ajudando a gerenciar a dívida técnica de um sistema legado.
Você recebe UM comentário encontrado no código, o trecho ao redor e métricas calculadas pela ferramenta
(complexidade, histórico do git). As métricas são fatos medidos: não as contradiga nem invente outras.

Sua tarefa:
1. Decidir se o comentário representa dívida técnica de verdade (alguns TODOs são só lembretes triviais).
2. Classificar o tipo de dívida usando a taxonomia de Alves et al. (2016).
3. Indicar o quadrante de Fowler (deliberada/inadvertida, prudente/imprudente) com base no tom do comentário.
4. Estimar o esforço para quitar (principal): P, M ou G.
5. Sugerir uma estratégia e um primeiro passo pequeno e concreto.

Regras:
- O campo "evidencia" precisa ser uma cópia literal de um pedaço do trecho recebido (sem os números de linha).
  A ferramenta confere isso automaticamente; se não bater, sua resposta vai para revisão humana.
- Seja honesto na confiança. Se o contexto for insuficiente, use confiança baixa.
- Responda em português do Brasil, de forma direta."""


def montar_prompt(item) -> str:
    m = item.metricas
    return f"""Arquivo: {item.arquivo}
Linha do comentário: {item.linha}
Comentário: {item.comentario}

Trecho (a linha marcada com >> é o comentário):
{item.trecho}

Métricas medidas pela ferramenta:
- função: {m.get('funcao')} | complexidade ciclomática: {m.get('complexidade')} | tamanho: {m.get('tamanho_funcao')} linhas
- commits no arquivo (últimos 12 meses / total): {m.get('commits_janela')} / {m.get('commits_total')}
- pessoas que já alteraram o arquivo: {m.get('autores_qtd')}
- comentário escrito em {m.get('introduzida_em')} por {m.get('introduzida_por')} ({m.get('idade_dias')} dias atrás)"""


REGRAS = [  # a ordem importa
    (r"copiad|duplic|copy", "design", "refatorar", "M"),
    (r"test", "teste", "adicionar_testes", "M"),
    (r"document|layout|so (o|a) \w+ sabe|ninguem sabe|explica", "documentacao", "documentar", "P"),
    (r"timeout|conex|servidor cai|deploy|infra", "infraestrutura", "corrigir_defeito", "M"),
    (r"hard.?coded|chumbad|magic|constante", "codigo", "refatorar", "P"),
    (r"migr|api nova|sistema novo|acoplad|camada", "arquitetura", "substituir_componente", "G"),
    (r"separar|refator|monstro|gigante|god", "design", "refatorar", "G"),
    (r"fixme|bug|quebra|errad|falha|negativo", "defeito", "corrigir_defeito", "M"),
    (r"valid|regra de negocio|requisito|cliente pediu", "requisito", "corrigir_defeito", "M"),
    (r"build|dependenc|versao da lib|pip|maven", "build", "refatorar", "M"),
    (r"hack|gambi|workaround|kludge", "codigo", "refatorar", "M"),
]


class AnalistaHeuristico:
    nome = "heurística por palavras-chave (sem IA)"
    usa_ia = False

    def analisar(self, item) -> dict:
        txt = normalizar(item.comentario)
        tipo, estrategia, esforco = "codigo", "refatorar", "M"
        for padrao, t, e, s in REGRAS:
            if re.search(padrao, txt):
                tipo, estrategia, esforco = t, e, s
                break
        deliberada = bool(re.search(r"hack|gambi|workaround|temporar|provisor|depois|por enquanto", txt))
        # na heurística a evidência é o próprio gatilho
        return {
            "e_divida": True,
            "tipo": tipo,
            "quadrante_fowler": "deliberada-prudente" if deliberada else "inadvertida-prudente",
            "confianca": 0.4,
            "evidencia": item.gatilho,
            "risco": "Não avaliado no modo offline.",
            "esforco": esforco,
            "estrategia": estrategia,
            "primeiro_passo": "Revisar o trecho e confirmar a classificação.",
            "titulo_issue": f"[{tipo}] {item.comentario[:70]}",
        }


class ErroIA(Exception):
    pass


class AnalistaClaude:
    usa_ia = True

    def __init__(self, modelo: str = "claude-opus-5-5", esforco: str = "low",
                 cache_path: str | None = None, cliente=None):
        self.modelo = modelo
        self.esforco = esforco
        self.nome = f"Claude ({modelo}, via API da Anthropic)"
        self.cache_path = cache_path
        self.cache = {}
        if cache_path and os.path.exists(cache_path):
            with open(cache_path, encoding="utf-8") as f:
                self.cache = json.load(f)
        if cliente is None:
            import anthropic
            cliente = anthropic.Anthropic()
        self.cliente = cliente
        self.chamadas_api = 0
        self.acertos_cache = 0

    def _salvar_cache(self):
        if self.cache_path:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def analisar(self, item) -> dict:
        prompt = montar_prompt(item)
        chave = hashlib.sha256(f"{self.modelo}|{SISTEMA}|{prompt}".encode("utf-8")).hexdigest()
        if chave in self.cache:
            self.acertos_cache += 1
            return self.cache[chave]

        import anthropic
        pedido = dict(
            model=self.modelo,
            max_tokens=4000,
            system=SISTEMA,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": self.esforco,
                           "format": {"type": "json_schema", "schema": SCHEMA}},
        )
        try:
            try:
                # se o modelo recusar, a API tenta de novo com outro
                resp = self.cliente.beta.messages.create(
                    **pedido, betas=["server-side-fallback-2026-07-01"], fallbacks="default")
            except anthropic.BadRequestError as e:
                if "fallback" not in str(e).lower():
                    raise
                resp = self.cliente.messages.create(**pedido)
        except anthropic.AuthenticationError as e:
            raise ErroIA("credencial inválida (confira ANTHROPIC_API_KEY)") from e
        except anthropic.RateLimitError as e:
            raise ErroIA("limite de requisições atingido; tente de novo em instantes") from e
        except anthropic.APIStatusError as e:
            raise ErroIA(f"erro da API ({e.status_code}): {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise ErroIA("sem conexão com a API") from e

        self.chamadas_api += 1
        if resp.stop_reason == "refusal":
            raise ErroIA("o modelo recusou analisar este trecho")
        if resp.stop_reason == "max_tokens":
            raise ErroIA("resposta cortada (max_tokens)")
        texto = next((b.text for b in resp.content if b.type == "text"), None)
        if not texto:
            raise ErroIA("resposta sem texto")
        try:
            dados = json.loads(texto)
        except json.JSONDecodeError as e:
            raise ErroIA("a IA devolveu JSON inválido") from e
        self.cache[chave] = dados
        self._salvar_cache()
        return dados


def tem_credencial() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
