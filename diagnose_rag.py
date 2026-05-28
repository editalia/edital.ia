"""Script de diagnóstico do RAG.

Roda o RAG num único edital com top_k configurável e mostra:
1. Os chunks recuperados por cada query (com distâncias)
2. O contexto montado
3. A resposta crua da LLM
4. O que disparou (ou não) o _precisa_refazer

Uso: python diagnose_rag.py
"""
import json
import sys

from vector_store import collection, QUERIES_PADRAO
from llm_client import gerar_json
from extrator_rag import PROMPT_RAG, _precisa_refazer

ARQUIVO_TESTE = "edital-ndeg-02-2026-prpgi-ifba-retificado-em-22-04-2026.pdf.md"
TOP_K = 15


def main():
    print(f"\n{'=' * 70}")
    print(f"DIAGNÓSTICO RAG")
    print(f"  Arquivo: {ARQUIVO_TESTE}")
    print(f"  top_k por query: {TOP_K}")
    print(f"{'=' * 70}\n")

    todos_trechos: list[str] = []
    chunks_vistos: set[str] = set()

    for idx, query in enumerate(QUERIES_PADRAO, 1):
        print(f"\n--- QUERY {idx}: '{query}' ---")
        try:
            results = collection.query(
                query_texts=[query],
                n_results=TOP_K,
                where={"source": ARQUIVO_TESTE},
                include=["documents", "distances"],
            )
        except Exception as e:
            print(f"  ERRO: {e}")
            continue

        docs = (results.get("documents") or [[]])[0]
        dists = (results.get("distances") or [[]])[0]

        print(f"  {len(docs)} chunks retornados")
        for i, (doc, dist) in enumerate(zip(docs, dists), 1):
            preview = doc[:140].replace("\n", " ").strip()
            novo = doc not in chunks_vistos
            marker = "[NEW]" if novo else "[DUP]"
            print(f"  {marker} [{i:2d}] dist={dist:.3f} | {preview}")
            if novo:
                chunks_vistos.add(doc)
                todos_trechos.append(doc)

    contexto = "\n---\n".join(todos_trechos)
    print(f"\n{'=' * 70}")
    print("CONTEXTO MONTADO")
    print(f"  Chunks únicos: {len(todos_trechos)}")
    print(f"  Tamanho total: {len(contexto)} chars")
    print(f"{'=' * 70}")

    prompt = PROMPT_RAG.format(arquivo=ARQUIVO_TESTE, context=contexto)
    print(f"\nPrompt final: {len(prompt)} chars")
    print("\nChamando LLM... (5-15s)")

    try:
        resposta = gerar_json(prompt)
    except Exception as e:
        print(f"ERRO na LLM: {e}")
        sys.exit(1)

    print(f"\n{'=' * 70}")
    print("RESPOSTA DA LLM (JSON parseado):")
    print(f"{'=' * 70}")
    print(json.dumps(resposta, ensure_ascii=False, indent=2))

    print(f"\n{'=' * 70}")
    print("ANÁLISE DO _precisa_refazer:")
    print(f"{'=' * 70}")
    nao_enc = "NAO_ENCONTRADO"

    valor_raw = resposta.get("valor_bolsa", "<MISSING_KEY>")
    data_raw = resposta.get("data_de_inscricao_texto", "<MISSING_KEY>")
    docs = resposta.get("documentos_necessarios", [])

    valor_check = str(valor_raw).strip().upper() == nao_enc
    data_check = str(data_raw).strip().upper() == nao_enc
    docs_check = not docs

    print(f"  valor_bolsa raw           : {valor_raw!r}")
    print(f"  ↳ é NAO_ENCONTRADO?       : {valor_check}")
    print(f"  data_de_inscricao_texto   : {data_raw!r}")
    print(f"  ↳ é NAO_ENCONTRADO?       : {data_check}")
    print(f"  documentos count          : {len(docs) if isinstance(docs, list) else 'NOT_LIST'}")
    print(f"  ↳ vazio?                  : {docs_check}")

    precisa = _precisa_refazer(resposta)
    print(f"\n  _precisa_refazer = {precisa}")
    if precisa:
        print(f"  -> CAI NO FALLBACK [X]")
        if valor_check:
            print("    (motivo: valor_bolsa veio NAO_ENCONTRADO)")
        if data_check:
            print("    (motivo: data_de_inscricao_texto veio NAO_ENCONTRADO)")
        if docs_check:
            print("    (motivo: documentos_necessarios está vazio)")
    else:
        print(f"  -> ACEITA O RAG [OK]")


if __name__ == "__main__":
    main()
