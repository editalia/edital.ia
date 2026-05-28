"""Validador de editais via LLM.

Marca cada arquivo .md como valido=true/false em state/editais.json,
extrai o programa (PIBIC/PIBITI/PIBID) e gera um título amigável.
NÃO deleta arquivos — só persiste o veredito. Subsequentes (vector_store,
extrator_rag, app) filtram por valido=true.
"""
import re
import logging
from datetime import datetime
from pathlib import Path

from llm_client import gerar_json
from state import carregar_editais, salvar_editais

log = logging.getLogger(__name__)

PROGRAMAS_ALVO = re.compile(r"\bPIBIC\b|\bPIBITI\b|\bPIBID\b", re.IGNORECASE)

PROMPT_VALIDACAO = """Você é um especialista em editais acadêmicos brasileiros do IFBA.
Analise o trecho abaixo e determine se é um edital de seleção de bolsistas para os programas PIBIC, PIBITI ou PIBID.

Responda APENAS com JSON válido, sem texto adicional:
{{
  "valido": true,
  "programa": "PIBIC",
  "titulo_amigavel": "Edital nº 08/2026 — PIBIC-EM",
  "motivo": "string"
}}

Campos:
- "valido": true se for edital de bolsas PIBIC/PIBITI/PIBID, false caso contrário
- "programa": "PIBIC", "PIBITI", "PIBID" ou "OUTRO"
- "titulo_amigavel": título curto e legível, ex: "Edital nº 08/2026 — PIBIC-EM"
- "motivo": breve justificativa

TEXTO:
{texto}
"""


def _titulo_fallback(nome_arquivo: str) -> str:
    return nome_arquivo.replace(".pdf.md", "").replace("-", " ").title()


def validar_edital(md_path: Path) -> dict:
    """Chama a LLM e retorna {valido, programa, titulo_amigavel, motivo}.
    Em caso de falha da LLM, cai num fallback por regex.
    """
    texto = md_path.read_text(encoding="utf-8", errors="ignore")[:5000]

    try:
        resultado = gerar_json(PROMPT_VALIDACAO.format(texto=texto))
        if "valido" in resultado:
            return resultado
    except Exception as e:
        log.warning(f"LLM falhou ao validar {md_path.name}: {e}. Fallback regex.")

    m = PROGRAMAS_ALVO.search(texto)
    return {
        "valido": bool(m),
        "programa": m.group(0).upper() if m else "OUTRO",
        "titulo_amigavel": _titulo_fallback(md_path.name),
        "motivo": "validação por regex (fallback)",
    }


def filtrar_invalidos(md_dir: Path) -> tuple[list[Path], list[Path]]:
    """Valida cada MD em md_dir, persistindo o resultado em state/editais.json.
    Pula arquivos que já têm campo `valido` registrado. Retorna (validos, invalidos).
    """
    editais = carregar_editais()
    validos, invalidos = [], []

    for md_path in md_dir.glob("*.md"):
        info = editais.get(md_path.name, {})

        # Skip se já validado em execução anterior
        if "valido" in info:
            if info["valido"]:
                log.info(f"[CACHE] {md_path.name} | {info.get('programa', '?')}")
                validos.append(md_path)
            else:
                invalidos.append(md_path)
            continue

        resultado = validar_edital(md_path)
        info.update({
            "arquivo_md": md_path.name,
            "valido": bool(resultado.get("valido")),
            "programa": resultado.get("programa", "OUTRO").upper(),
            "titulo_amigavel": resultado.get("titulo_amigavel") or _titulo_fallback(md_path.name),
            "motivo_validacao": resultado.get("motivo", ""),
            "data_validacao": datetime.now().isoformat(timespec="seconds"),
        })
        editais[md_path.name] = info

        if info["valido"]:
            log.info(f"[VALIDO]   {md_path.name} | {info['programa']} | {info['titulo_amigavel']}")
            validos.append(md_path)
        else:
            log.warning(f"[INVALIDO] {md_path.name} | {info['motivo_validacao']}")
            invalidos.append(md_path)

    salvar_editais(editais)
    return validos, invalidos


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    md_dir = Path("editais_markdown")
    if not md_dir.exists():
        print("Pasta editais_markdown nao encontrada.")
    else:
        validos, invalidos = filtrar_invalidos(md_dir)
        print(f"\nValidos: {len(validos)} | Invalidos: {len(invalidos)}")
