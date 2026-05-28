# Edital.IA

> Monitoramento inteligente de editais de bolsas de incentivo do IFBA.

Edital.IA é um sistema que **coleta automaticamente** os editais de bolsas
(PIBIC, PIBITI, PIBID) publicados no portal do IFBA, **extrai os dados
relevantes** de cada um (valor da bolsa, período de inscrição, documentos
necessários, etc.) usando uma arquitetura **RAG (Retrieval-Augmented
Generation)** e apresenta tudo numa **interface web** simples, com semáforo
de urgência por prazo.

Este projeto é o **TCC** de Khian Gabriel — IFBA Vitória da Conquista.

---

## ✨ Funcionalidades

- 🕷️ **Crawler automático** do portal IFBA (`/prpgi/editais/`) — baixa só editais novos
- 📄 **Conversão PDF → Markdown** via PyMuPDF4LLM
- 🤖 **Classificação por LLM** — separa editais PIBIC/PIBITI/PIBID dos demais
- 🧠 **RAG vetorial** com multi-query — recupera os trechos relevantes de cada edital
- ⛑️ **Fallback em 3 níveis** — se o RAG falhar, tenta regex e então texto completo
- 🚦 **Semáforo de urgência** — 🟢 (>7 dias) / 🟡 (≤7 dias) / 🔴 (último dia) / ⚫ (encerrado)
- 🌐 **Interface Streamlit** — read-only, sem latência de LLM em runtime
- ⏰ **Agendador diário** — pipeline roda 1×/dia (Task Scheduler / cron / launchd)

---

## 🏛️ Arquitetura

Pipeline sequencial de 5 etapas, orquestrado por `pipeline.py`:

```
┌─────────────┐   PDFs    ┌──────────────────────────┐   .md     ┌──────────────┐
│  crawler.py │──────────▶│ pymu_conversor_markdown  │──────────▶│ validador.py │
└─────────────┘           └──────────────────────────┘           └──────┬───────┘
                                                                        │ valido=true
                                                                        ▼
┌─────────────────────┐   contexto   ┌────────────────────────┐   chunks
│   app.py (front)    │◀─────────────│   extrator_rag.py      │◀───┐
│   read-only         │  extracoes   │   (RAG multi-query)    │    │
└─────────────────────┘  .json       └────────────────────────┘    │
                                                                    │
                                                          ┌────────────────┐
                                                          │ vector_store.py│
                                                          │   ChromaDB     │
                                                          └────────────────┘
```

**Princípio CQRS-light:** o pipeline **escreve** os JSONs em `state/`, o
frontend **só lê**. Zero chamada de LLM em runtime — o front é sempre rápido.

---

## 📁 Estrutura de arquivos

```
versao_0.1/
├── app.py                          # Frontend Streamlit (read-only)
├── pipeline.py                     # Orquestrador das 5 etapas
│
├── crawler.py                      # Etapa 1 — baixa PDFs do portal IFBA
├── pymu_conversor_markdown.py      # Etapa 2 — converte PDF → Markdown
├── validador.py                    # Etapa 3 — classifica via LLM (PIBIC/PIBITI/PIBID/OUTRO)
├── vector_store.py                 # Etapa 4 — chunking + embedding no ChromaDB
├── extrator_rag.py                 # Etapa 5 — RAG multi-query + extração estruturada
│
├── llm_client.py                   # Wrapper sobre Ollama (Cloud ou local)
├── state.py                        # Helpers para ler/escrever os JSONs de state/
├── diagnose_rag.py                 # Script de debug do RAG (não faz parte do pipeline)
│
├── editais_baixados/               # PDFs baixados pelo crawler        (gerado, no .gitignore)
├── editais_markdown/               # Markdowns gerados pelo conversor  (gerado, no .gitignore)
├── chroma_db/                      # Banco vetorial local              (gerado, no .gitignore)
│
├── state/                          # Persistência fora do ChromaDB
│   ├── urls_visitadas.json         # URLs já visitadas pelo crawler
│   ├── editais.json                # Registro mestre dos editais
│   ├── extracoes.json              # Cache das extrações (resumo, datas, valor, docs)
│   ├── pipeline_state.json         # Última execução do pipeline
│   ├── stats.json                  # Contagem por método de extração (RAG/regex/full)
│   └── pipeline_logs/              # Logs por execução (gerado pelo cron)
│
├── scripts/                        # Cron multi-OS (ver EXECUCAO.md)
│   ├── run_pipeline.ps1            # Windows (Task Scheduler)
│   ├── install_cron.ps1
│   ├── uninstall_cron.ps1
│   ├── run_pipeline.sh             # Linux / macOS
│   ├── install_cron_linux.sh
│   ├── uninstall_cron_linux.sh
│   ├── install_cron_macos.sh
│   ├── uninstall_cron_macos.sh
│   └── com.editalia.pipeline.plist # launchd (macOS)
│
├── tests/                          # Testes unitarios + integracao
│   ├── conftest.py
│   ├── unit/
│   └── integration/
│
├── .streamlit/config.toml          # Tema da interface
├── requirements.txt                # Dependencias de producao
├── requirements-dev.txt            # Dependencias de teste
├── pytest.ini                      # Config do pytest
├── .env                            # MODEL=... (no .gitignore)
├── README.md                       # Este arquivo
└── EXECUCAO.md                     # Guia operacional (instalacao, cron, testes)
```

---

## 🔄 Pipeline — etapa por etapa

### 1. Crawler (`crawler.py`)

Acessa `https://portal.ifba.edu.br/prpgi/editais/`, navega até os anos
configurados (`anos_limite=1` por padrão = só o ano corrente) e baixa os
PDFs cuja descrição ou título contenha `PIBIC`, `PIBITI` ou `PIBID`.

- **Idempotência**: URLs já visitadas ficam em `state/urls_visitadas.json` e são puladas
- **Robustez**: 3 tentativas de URL por PDF (path direto, `/at_download/file`, `/download`)
- **Validação de Content-Type**: só salva se a resposta for `application/pdf`
- **Cortesia**: `time.sleep(1)` entre downloads

### 2. Conversor (`pymu_conversor_markdown.py`)

Converte cada PDF de `editais_baixados/` em Markdown na pasta
`editais_markdown/` via `pymupdf4llm`. **Idempotente** — pula MDs que já
existem.

### 3. Validador (`validador.py`)

Lê os 5000 primeiros caracteres de cada `.md` e chama a LLM com um prompt
estruturado pedindo: `{ valido, programa, titulo_amigavel, motivo }`.

- Persiste o veredito em `state/editais.json` — **não deleta** os
  inválidos (apenas marca `valido=false` para etapas seguintes filtrarem)
- **Cache**: pula arquivos que já têm campo `valido` registrado
- **Fallback**: se a LLM falhar, classifica por regex (`PIBIC|PIBITI|PIBID`)

### 4. Vector Store (`vector_store.py`)

Chunking dos MDs válidos e indexação no ChromaDB local.

- **Chunking**: split por parágrafo (`\n\n`); chunks > 2000 chars são
  fatiados em pedaços de 1500
- **Normalização** (`_limpar_para_embedding`): remove ruído de Markdown
  (`**`, `<br>`, espaços múltiplos) e **strikethrough** (`~~...~~`) —
  fundamental para retificações (datas/valores cancelados não poluem o embedding)
- **Embedding**: `paraphrase-multilingual-MiniLM-L12-v2` (384d, PT-BR, roda
  local via sentence-transformers)
- **IDs determinísticos**: `{nome_arquivo}_chunk_{i}` → permite reindexação
  idempotente

### 5. Extrator RAG (`extrator_rag.py`)

O coração do sistema. Para cada edital válido, extrai os campos
estruturados (resumo, valor, datas, documentos) em **3 níveis de fallback**:

1. **RAG vetorial (multi-query)** — dispara 6 queries semânticas
   (valor, datas, cronograma, docs, objeto) com `n_results=15` cada,
   dedupe os chunks, monta o contexto e chama a LLM
2. **Regex fallback** — se o RAG não trouxer todos os campos, filtra o
   texto completo por janelas de ±6 linhas em torno de palavras-chave
   (R$, inscrição, prazo, documentos) e tenta de novo
3. **Full-text fallback** — último recurso: manda os primeiros 100k
   caracteres do texto inteiro pra LLM

Cada extração é salva em `state/extracoes.json` com o método usado
(`metodo_extracao`), e o contador é atualizado em `state/stats.json`.

> **Resultado atual**: 8/9 editais resolvidos via RAG_VETORIAL (88.9%), 1/9 via FULL_TEXT_FALLBACK.

---

## 🧰 Stack

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.11+ |
| Crawler | `requests` + `BeautifulSoup4` |
| PDF → Markdown | `pymupdf4llm` |
| Embeddings | `sentence-transformers` (multilíngue, local) |
| Vector store | `ChromaDB` (persistente, local) |
| LLM | **Ollama Cloud** (`qwen3-coder:480b-cloud`, free tier) via SDK `ollama` |
| Frontend | `Streamlit` |
| Agendador | Task Scheduler (Win) / crontab (Linux) / launchd (macOS) |
| Testes | `pytest` + `pytest-mock` |

---

## 🔍 Como o RAG funciona

O RAG resolve o problema clássico de prompts longos: em vez de mandar o
edital inteiro pra LLM (que custaria muito e perderia precisão), nós:

1. **Indexamos** cada edital em chunks (parágrafos) no ChromaDB
2. Para cada consulta de extração, **disparamos 6 queries semânticas**
   diferentes ("valor da bolsa em reais", "período de inscrição", etc.)
3. Pegamos os top-15 chunks de cada query, **deduplicamos** e montamos
   um contexto enxuto
4. Mandamos só esse contexto pra LLM com um prompt estruturado pedindo
   JSON

Isso é **multi-query RAG**, e foi a chave pra subir a taxa de acerto de
~40% (single-query) pra ~90% (multi-query com normalização de markdown).

---

## 🌐 Frontend

`app.py` é um **Streamlit read-only**. Ele lê 3 JSONs de `state/`:

- `editais.json` — registro mestre (programa, título, URL, valido)
- `extracoes.json` — cache das extrações (resumo, datas, valor, docs)
- `pipeline_state.json` — timestamp da última execução do pipeline

E renderiza:

- **Sidebar** com filtros (toggle "mostrar encerrados") e lista agrupada
  por programa (PIBIC / PIBITI / PIBID / OUTRO), ordenada por urgência
- **Área principal** com card do edital selecionado (resumo, período,
  valor, semáforo, documentos, link oficial)

Como não dispara LLM em runtime, a interface é instantânea — todo o
trabalho pesado é feito offline pelo pipeline.

---

## 🧪 Testes

```bash
pip install -r requirements-dev.txt
pytest
```

Estrutura:

- `tests/unit/` — testes isolados de funções puras (sem rede, sem LLM)
- `tests/integration/` — pipeline end-to-end com mocks

Cobre: `_limpar_para_embedding`, `_precisa_refazer`,
`calcular_status_edital`, parse tolerante de JSON, fallback regex do
validador, e a orquestração completa do `pipeline.py`.

---

## 📖 Veja também

- **[EXECUCAO.md](EXECUCAO.md)** — instalação, configuração, comandos,
  agendamento (cron Windows / Linux / macOS), logs, troubleshooting

---

## 📜 Licença e contexto

Projeto acadêmico — TCC de Khian Gabriel, IFBA Vitória da Conquista.
Uso educacional.
