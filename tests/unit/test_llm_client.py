"""Testes do wrapper sobre Ollama — focam no parse tolerante de JSON."""
import json

import pytest

import llm_client


def _mock_generate(monkeypatch, resposta_str):
    """Helper: faz ollama.generate (re-exportado em llm_client) devolver `resposta_str`."""
    monkeypatch.setattr(
        llm_client, "generate",
        lambda **kwargs: {"response": resposta_str},
    )


class TestGerarJson:

    def test_json_limpo_e_parseado(self, monkeypatch):
        _mock_generate(monkeypatch, '{"valor": "R$400", "valido": true}')
        result = llm_client.gerar_json("qualquer prompt")
        assert result == {"valor": "R$400", "valido": True}

    def test_texto_antes_e_depois_do_json_ainda_parseia(self, monkeypatch):
        _mock_generate(monkeypatch, 'Aqui esta a resposta: {"a": 1} fim.')
        result = llm_client.gerar_json("p")
        assert result == {"a": 1}

    def test_resposta_sem_chaves_retorna_dict_vazio(self, monkeypatch):
        _mock_generate(monkeypatch, "sem json nenhum")
        assert llm_client.gerar_json("p") == {}

    def test_resposta_string_vazia_retorna_dict_vazio(self, monkeypatch):
        _mock_generate(monkeypatch, "")
        assert llm_client.gerar_json("p") == {}

    def test_json_malformado_entre_braces_levanta(self, monkeypatch):
        _mock_generate(monkeypatch, '{"a": ,}')
        with pytest.raises(json.JSONDecodeError):
            llm_client.gerar_json("p")

    def test_json_aninhado_e_parseado(self, monkeypatch):
        _mock_generate(
            monkeypatch,
            '{"docs": ["a", "b"], "meta": {"k": 1}}',
        )
        result = llm_client.gerar_json("p")
        assert result["docs"] == ["a", "b"]
        assert result["meta"] == {"k": 1}
