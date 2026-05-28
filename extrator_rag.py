"""Extrator com cache. Usa RAG (multi-query) com fallbacks por regex e full text.

Persiste o resultado em state/extracoes.json para o front ler instantaneamente
(sem precisar bater na LLM no momento da consulta do usuário).

Campos extraídos por arquivo:
- resumo: 3-4 frases descrevendo o edital
- data_de_inscricao_texto: forma legível ("06/04/2026 a 08/05/2026")
- data_inscricao_inicio / data_inscricao_fim: ISO YYYY-MM-DD para filtros
- valor_bolsa: string com valor + periodicidade
- documentos_necessarios: lista
"""
import re
import time
import logging
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from llm_client import gerar_json
from vector_store import popular_banco, recuperar_contexto_arquivo
from state import (
    carregar_extracoes,
    salvar_extracoes,
    carregar_editais,
    registrar_metodo_extracao,
)

load_dotenv(".env")
log = logging.getLogger(__name__)

INPUT_DIR = Path("editais_markdown")

PROMPT_RAG = """Você é um assistente especialista em editais de bolsas acadêmicas.
Analise os fragmentos abaixo retirados do arquivo "{arquivo}" e extraia as informações solicitadas.

Regras:
- Se não encontrar a informação, use "NAO_ENCONTRADO" (ou [] para listas, null para datas).
- Para "valor_bolsa": priorize valores com "R$" e inclua a periodicidade (mensal/anual).
- Para "data_de_inscricao_texto": formato livre legível, ex: "06/04/2026 a 08/05/2026".
- Para "data_inscricao_inicio" e "data_inscricao_fim": formato ISO YYYY-MM-DD (ou null).
- Para "documentos_necessarios": cada documento como item separado da lista.
- Para "resumo": 3-4 frases em português claro descrevendo público-alvo, programa, valor e prazo.
- Responda APENAS com JSON válido, sem texto adicional.

FRAGMENTOS:
{context}

FORMATO ESPERADO:
{{
  "resumo": "string",
  "data_de_inscricao_texto": "string",
  "data_inscricao_inicio": "YYYY-MM-DD",
  "data_inscricao_fim": "YYYY-MM-DD",
  "valor_bolsa": "string",
  "documentos_necessarios": ["doc1", "doc2"]
}}
"""


def _call_llm(prompt: str) -> dict:
    try:
        return gerar_json(prompt)
    except Exception as e:
        log.warning(f"Erro na LLM: {e}")
        return {}


def _recortes_relevantes(md_text: str, max_chars: int = 12_000) -> str:
    """Filtra linhas do markdown por padrões relevantes (datas, R$, docs, objeto)."""
    padroes = [
        r"inscri|prazo|cronograma|per[ií]odo",
        r"\bR\$\s*\d|valor\s+da\s+bolsa|reais",
        r"document(os|a[cç][aã]o)|anexos|comprovantes",
        r"processo\s+de\s+sele[cç][aã]o|crite|an[aá]lise|julg",
        r"objeto|finalidade|destinad",
    ]
    linhas = md_text.splitlines()
    hits: set[int] = set()
    for i, ln in enumerate(linhas):
        for pat in padroes:
            if re.search(pat, ln, re.IGNORECASE):
                hits.update(range(max(0, i - 6), min(len(linhas), i + 7)))
                break
    if not hits:
        return md_text[:max_chars]
    return "\n".join(linhas[i] for i in sorted(hits))[:max_chars]


def _precisa_refazer(ans: dict) -> bool:
    """Considera resposta insuficiente se faltar valor, data textual OU lista de docs."""
    if not ans:
        return True
    nao_enc = "NAO_ENCONTRADO"
    return (
        str(ans.get("valor_bolsa", nao_enc)).strip().upper() == nao_enc
        or str(ans.get("data_de_inscricao_texto", nao_enc)).strip().upper() == nao_enc
        or not ans.get("documentos_necessarios")
    )


def _montar_resultado(nome_arquivo: str, metodo: str, dados: dict) -> dict:
    dados.setdefault("resumo", "")
    dados.setdefault("data_de_inscricao_texto", "NAO_ENCONTRADO")
    dados.setdefault("data_inscricao_inicio", None)
    dados.setdefault("data_inscricao_fim", None)
    dados.setdefault("valor_bolsa", "NAO_ENCONTRADO")
    dados.setdefault("documentos_necessarios", [])
    return {
        "arquivo": nome_arquivo,
        "metodo_extracao": metodo,
        "extraido_em": datetime.now().isoformat(timespec="seconds"),
        **dados,
    }


def processar_arquivo_hibrido(file_path: Path, force: bool = False) -> dict:
    """Extrai os dados do edital. Usa cache em state/extracoes.json se disponível.
    force=True força re-extração mesmo havendo cache.
    """
    extracoes = carregar_extracoes()

    if not force and file_path.name in extracoes:
        log.info(f"[CACHE] {file_path.name}")
        return extracoes[file_path.name]

    log.info(f"Extraindo: {file_path.name}")

    # Nível 1: RAG vetorial (multi-query)
    contexto = recuperar_contexto_arquivo(file_path.name)
    if len(contexto) >= 50:
        prompt = PROMPT_RAG.format(arquivo=file_path.name, context=contexto)
        resposta = _call_llm(prompt)
        if not _precisa_refazer(resposta):
            resultado = _montar_resultado(file_path.name, "RAG_VETORIAL", resposta)
            extracoes[file_path.name] = resultado
            salvar_extracoes(extracoes)
            registrar_metodo_extracao("RAG_VETORIAL")
            return resultado

    # Nível 2: regex
    log.info("  RAG insuficiente. Fallback regex...")
    full_text = file_path.read_text(encoding="utf-8", errors="ignore")
    ctx_regex = _recortes_relevantes(full_text, max_chars=12_000)
    prompt = PROMPT_RAG.format(arquivo=file_path.name, context=ctx_regex)
    resposta = _call_llm(prompt)
    if not _precisa_refazer(resposta):
        resultado = _montar_resultado(file_path.name, "REGEX_FALLBACK", resposta)
        extracoes[file_path.name] = resultado
        salvar_extracoes(extracoes)
        registrar_metodo_extracao("REGEX_FALLBACK")
        return resultado

    # Nível 3: full text
    log.info("  Tentando texto completo...")
    ctx_full = full_text[:100_000]
    prompt = PROMPT_RAG.format(arquivo=file_path.name, context=ctx_full)
    resposta = _call_llm(prompt)
    resultado = _montar_resultado(file_path.name, "FULL_TEXT_FALLBACK", resposta)
    extracoes[file_path.name] = resultado
    salvar_extracoes(extracoes)
    registrar_metodo_extracao("FULL_TEXT_FALLBACK")
    return resultado


def extrair_todos(force: bool = False):
    """Extrai todos os editais válidos em editais_markdown/."""
    editais = carregar_editais()
    arquivos = [
        f for f in INPUT_DIR.glob("*.md")
        if editais.get(f.name, {}).get("valido", True)
    ]

    print(f"\n--- Iniciando extracao ({len(arquivos)} editais validos) ---")
    t0 = time.time()
    for arquivo in arquivos:
        processar_arquivo_hibrido(arquivo, force=force)
    print(f"\nFinalizado em {time.time() - t0:.2f}s.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if not INPUT_DIR.exists():
        print(f"Pasta {INPUT_DIR} nao encontrada.")
        raise SystemExit(1)

    popular_banco()
    extrair_todos()
