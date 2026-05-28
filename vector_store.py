import re

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from pathlib import Path

from state import carregar_editais

# --- CONFIGURAÇÕES ---
MD_DIR = Path("editais_markdown")
COLLECTION_NAME = "editais_bolsa"
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# Inicializa cliente persistente
client = chromadb.PersistentClient(path="./chroma_db")

# Embedding multilingual (PT-BR) via sentence-transformers.
collection = client.get_or_create_collection(
    name=COLLECTION_NAME,
    embedding_function=SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    ),
)


def _limpar_para_embedding(texto: str) -> str:
    """Remove ruído de Markdown que degrada o embedding semântico.
    O texto limpo é o que vai pro Chroma (e pra LLM); o ganho de retrieval
    compensa a perda de formatação visual.
    """
    t = re.sub(r"~~[^~]*~~", "", texto)                 # strikethrough: remove conteudo riscado (datas/valores cancelados em retificacoes)
    t = re.sub(r"\*+", "", t)                           # bold/italic
    t = re.sub(r"<br\s*/?>", " ", t, flags=re.IGNORECASE)  # quebras HTML
    t = re.sub(r"^\s*\d+\.\s{2,}", "", t, flags=re.MULTILINE)  # "0.     " espúrio
    t = re.sub(r"[ \t]+", " ", t)                       # espaços múltiplos (mantém \n)
    return t.strip()


def popular_banco():
    """Indexa MDs em editais_markdown/ no ChromaDB. Pula arquivos:
    - já indexados (mesmo chunk_id)
    - marcados como inválidos em state/editais.json
    """
    print("--- Iniciando Vetorização (Ingestão) ---")
    if not MD_DIR.exists():
        print(f"ERRO: A pasta {MD_DIR} não existe. Rode o conversor primeiro.")
        return

    editais = carregar_editais()
    files = list(MD_DIR.glob("*.md"))
    existing_ids = set(collection.get()["ids"])
    count_novos = 0

    for file_path in files:
        info = editais.get(file_path.name, {})
        if info.get("valido") is False:
            print(f"Pulando inválido: {file_path.name}")
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Erro ao ler {file_path}: {e}")
            continue

        # Chunking: split por parágrafo, fatia chunks gigantes em pedaços de 1500
        raw_chunks = content.split("\n\n")
        chunks = []
        for c in raw_chunks:
            limpo = _limpar_para_embedding(c)
            if len(limpo) > 2000:
                pedacos = [limpo[i:i + 1500] for i in range(0, len(limpo), 1500)]
                chunks.extend(pedacos)
            elif len(limpo) > 30:
                chunks.append(limpo)
        if not chunks:
            continue

        safe_name = file_path.name.replace(" ", "_").replace(",", "")
        ids, docs_to_add, metadatas = [], [], []

        for i, chunk in enumerate(chunks):
            chunk_id = f"{safe_name}_chunk_{i}"
            if chunk_id not in existing_ids:
                ids.append(chunk_id)
                docs_to_add.append(chunk)
                metadatas.append({"source": file_path.name})

        if not ids:
            print(f"Já indexado: {file_path.name}")
            continue

        print(f"Indexando: {file_path.name} ({len(ids)} novos trechos)...")
        batch_size = 10
        for i in range(0, len(ids), batch_size):
            end = i + batch_size
            collection.add(
                documents=docs_to_add[i:end],
                metadatas=metadatas[i:end],
                ids=ids[i:end],
            )
        count_novos += 1

    print(f"Concluído! {count_novos} arquivos processados.")


# --- BUSCA POR ARQUIVO (multi-query RAG) ---
QUERIES_PADRAO = [
    "valor da bolsa remuneração mensal em reais",
    "período de inscrição prazo cronograma datas",
    "cronograma do edital recebimento de propostas data início encerramento submissão",
    "data de abertura e encerramento das inscrições do edital",
    "documentos necessários anexos comprovantes para inscrição",
    "objeto seleção bolsistas público-alvo programa",
]


def recuperar_contexto_arquivo(nome_arquivo, queries=None, n_results=15):
    """Multi-query RAG: dispara N queries semânticas, dedupe os trechos."""
    queries = queries or QUERIES_PADRAO
    vistos = set()
    trechos = []
    for q in queries:
        try:
            results = collection.query(
                query_texts=[q],
                n_results=n_results,
                where={"source": nome_arquivo},
            )
            docs = (results.get("documents") or [[]])[0]
            for chunk in docs:
                if chunk and chunk not in vistos:
                    vistos.add(chunk)
                    trechos.append(chunk)
        except Exception as e:
            print(f"Erro na consulta (query='{q}'): {e}")
    return "\n---\n".join(trechos)


if __name__ == "__main__":
    popular_banco()
