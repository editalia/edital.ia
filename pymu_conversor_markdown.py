"""Conversor PDF → Markdown via pymupdf4llm. Idempotente."""
import logging
from pathlib import Path

import pymupdf4llm

log = logging.getLogger(__name__)

INDIR = Path("editais_baixados")
OUTDIR = Path("editais_markdown")


def converter_pdfs() -> list[Path]:
    """Converte todos os PDFs novos em INDIR para Markdown em OUTDIR.
    Pula PDFs cujo .md correspondente já existe. Retorna lista de todos os MDs.
    """
    OUTDIR.mkdir(exist_ok=True)
    if not INDIR.exists():
        log.warning(f"Pasta {INDIR} nao existe — nada a converter.")
        return []

    pdfs = list(INDIR.glob("*.pdf"))
    novos = 0
    todos_mds: list[Path] = []

    for src in pdfs:
        destino = OUTDIR / (src.name + ".md")
        todos_mds.append(destino)
        if destino.exists():
            continue
        try:
            doc = pymupdf4llm.to_markdown(str(src))
            destino.write_text(doc, encoding="utf-8")
            log.info(f"Convertido: {src.name}")
            novos += 1
        except Exception as e:
            log.error(f"Erro ao converter {src}: {e}")

    log.info(f"Conversor: {novos} novos, {len(todos_mds)} totais.")
    return todos_mds


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    converter_pdfs()
