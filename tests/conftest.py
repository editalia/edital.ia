"""Fixtures compartilhadas pelos testes do Edital.IA."""
import pytest


@pytest.fixture
def state_tmp(tmp_path, monkeypatch):
    """Redireciona todas as constantes de state.py para uma pasta temp.

    Permite testar carregar_/salvar_ sem sujar o state/ real do projeto.
    """
    import state as s

    monkeypatch.setattr(s, "STATE_DIR", tmp_path)
    monkeypatch.setattr(s, "CRAWLER_FILE", tmp_path / "urls_visitadas.json")
    monkeypatch.setattr(s, "EDITAIS_FILE", tmp_path / "editais.json")
    monkeypatch.setattr(s, "EXTRACOES_FILE", tmp_path / "extracoes.json")
    monkeypatch.setattr(s, "PIPELINE_FILE", tmp_path / "pipeline_state.json")
    monkeypatch.setattr(s, "STATS_FILE", tmp_path / "stats.json")
    return s
