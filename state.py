"""Helpers para ler/escrever os JSONs de estado em state/.

Centraliza toda persistência fora do ChromaDB:
- urls_visitadas.json  → URLs já visitadas pelo crawler
- editais.json         → registro mestre (programa, título amigável, link, valido)
- extracoes.json       → cache das extrações (resumo, datas, valor, docs)
- pipeline_state.json  → última execução do pipeline e estatísticas
- stats.json           → contagem de qual método (RAG/regex/full) foi usado
"""
import json
from pathlib import Path
from datetime import datetime, date

STATE_DIR = Path("state")
STATE_DIR.mkdir(exist_ok=True)

CRAWLER_FILE = STATE_DIR / "urls_visitadas.json"
EDITAIS_FILE = STATE_DIR / "editais.json"
EXTRACOES_FILE = STATE_DIR / "extracoes.json"
PIPELINE_FILE = STATE_DIR / "pipeline_state.json"
STATS_FILE = STATE_DIR / "stats.json"


def _ler_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _escrever_json(path: Path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ───── Crawler state ─────
def carregar_crawler_state() -> dict:
    return _ler_json(CRAWLER_FILE, {"urls_visitadas": [], "ultima_execucao": None})


def salvar_crawler_state(state: dict):
    state["ultima_execucao"] = datetime.now().isoformat(timespec="seconds")
    _escrever_json(CRAWLER_FILE, state)


# ───── Editais (registro mestre) ─────
def carregar_editais() -> dict:
    return _ler_json(EDITAIS_FILE, {})


def salvar_editais(editais: dict):
    _escrever_json(EDITAIS_FILE, editais)


# ───── Extracoes (cache da LLM) ─────
def carregar_extracoes() -> dict:
    return _ler_json(EXTRACOES_FILE, {})


def salvar_extracoes(extracoes: dict):
    _escrever_json(EXTRACOES_FILE, extracoes)


# ───── Pipeline state (última execução) ─────
def carregar_pipeline_state() -> dict:
    return _ler_json(PIPELINE_FILE, {"ultima_execucao": None})


def salvar_pipeline_state(state: dict):
    state["ultima_execucao"] = datetime.now().isoformat(timespec="seconds")
    _escrever_json(PIPELINE_FILE, state)


# ───── Stats de RAG ─────
def carregar_stats() -> dict:
    return _ler_json(STATS_FILE, {"por_metodo": {}, "total": 0})


def salvar_stats(stats: dict):
    _escrever_json(STATS_FILE, stats)


def registrar_metodo_extracao(metodo: str):
    stats = carregar_stats()
    stats["por_metodo"][metodo] = stats["por_metodo"].get(metodo, 0) + 1
    stats["total"] = stats.get("total", 0) + 1
    salvar_stats(stats)


# ───── Helpers de domínio ─────
def calcular_status_edital(data_fim_iso) -> dict:
    """Recebe data ISO (YYYY-MM-DD) e devolve status visual.

    Retorna dict com:
      - status: 'aberto' | 'encerrado' | 'indefinido'
      - dias_restantes: int ou None
      - semaforo: emoji
    """
    hoje = date.today()
    if not data_fim_iso or str(data_fim_iso).upper() in ("NAO_ENCONTRADO", "NULL", "NONE"):
        return {"status": "indefinido", "dias_restantes": None, "semaforo": "⚫"}

    try:
        fim = date.fromisoformat(str(data_fim_iso))
    except (ValueError, TypeError):
        return {"status": "indefinido", "dias_restantes": None, "semaforo": "⚫"}

    dias = (fim - hoje).days

    if dias < 0:
        return {"status": "encerrado", "dias_restantes": dias, "semaforo": "⚫"}
    if dias == 0:
        return {"status": "aberto", "dias_restantes": 0, "semaforo": "🔴"}
    if dias <= 7:
        return {"status": "aberto", "dias_restantes": dias, "semaforo": "🟡"}
    return {"status": "aberto", "dias_restantes": dias, "semaforo": "🟢"}
