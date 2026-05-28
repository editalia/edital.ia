import os
import json
import logging
from ollama import generate
from dotenv import load_dotenv

load_dotenv(".env")
log = logging.getLogger(__name__)

MODEL = os.getenv("MODEL", "qwen3.5")


def gerar(prompt: str) -> str:
    """Envia um prompt ao modelo via Ollama local e retorna a resposta como string."""
    resp = generate(model=MODEL, prompt=prompt, format="json", options={"temperature": 0})
    return resp.get("response", "")


def gerar_json(prompt: str) -> dict:
    """Envia prompt e já faz parse do JSON retornado."""
    raw = gerar(prompt)
    s = raw.strip()
    ini, fim = s.find("{"), s.rfind("}")
    if ini != -1 and fim != -1:
        return json.loads(s[ini:fim + 1])
    return {}
