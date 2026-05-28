"""Testes de integracao do orquestrador (pipeline.py).

Cada etapa eh mockada — testamos que:
- Todas as 5 etapas sao chamadas em ordem
- Estatisticas sao agregadas em `stats`
- Falhas em qualquer etapa nao impedem o salvamento do state final
"""
from unittest.mock import call

import pytest

import pipeline


@pytest.fixture
def mocks_etapas(monkeypatch):
    """Substitui as 5 etapas e o salvar_pipeline_state por mocks rastreaveis."""
    calls = []

    def make(nome, retorno=None):
        def _f(*args, **kwargs):
            calls.append(nome)
            return retorno
        return _f

    monkeypatch.setattr(pipeline, "executar_crawler", make("crawler", {"novos": 2, "total_visitados": 5}))
    monkeypatch.setattr(pipeline, "converter_pdfs", make("conversor", ["a.md", "b.md"]))
    monkeypatch.setattr(pipeline, "filtrar_invalidos", make("validador", (["a.md"], ["b.md"])))
    monkeypatch.setattr(pipeline, "popular_banco", make("vector_store"))
    monkeypatch.setattr(pipeline, "extrair_todos", make("extrator"))

    salvas = []
    monkeypatch.setattr(pipeline, "salvar_pipeline_state", lambda s: salvas.append(s))

    return {"calls": calls, "salvas": salvas}


class TestExecutarPipeline:

    def test_chama_todas_as_etapas_em_ordem(self, mocks_etapas):
        pipeline.executar_pipeline(anos_limite=1)
        assert mocks_etapas["calls"] == [
            "crawler", "conversor", "validador", "vector_store", "extrator"
        ]

    def test_status_sucesso_quando_tudo_passa(self, mocks_etapas):
        pipeline.executar_pipeline(anos_limite=1)
        salvas = mocks_etapas["salvas"]
        assert len(salvas) == 1
        stats = salvas[0]
        assert stats["status"] == "sucesso"
        assert stats["erro"] is None
        assert stats["anos_limite"] == 1

    def test_stats_agrega_dados_das_etapas(self, mocks_etapas):
        pipeline.executar_pipeline(anos_limite=1)
        stats = mocks_etapas["salvas"][0]
        assert stats["crawler"]["novos"] == 2
        assert stats["conversor"]["total_mds"] == 2
        assert stats["validador"]["validos"] == 1
        assert stats["validador"]["invalidos"] == 1

    def test_falha_em_etapa_resulta_em_status_falha(self, monkeypatch, mocks_etapas):
        def explode(*a, **kw):
            raise RuntimeError("crawler caiu")
        monkeypatch.setattr(pipeline, "executar_crawler", explode)

        pipeline.executar_pipeline(anos_limite=1)
        stats = mocks_etapas["salvas"][0]
        assert stats["status"] == "falha"
        assert "crawler caiu" in stats["erro"]

    def test_state_sempre_salvo_mesmo_em_erro(self, monkeypatch, mocks_etapas):
        monkeypatch.setattr(
            pipeline, "popular_banco",
            lambda: (_ for _ in ()).throw(RuntimeError("chroma down")),
        )

        pipeline.executar_pipeline(anos_limite=1)
        assert len(mocks_etapas["salvas"]) == 1  # finally garante salvamento

    def test_duracao_segundos_e_registrada(self, mocks_etapas):
        pipeline.executar_pipeline(anos_limite=1)
        stats = mocks_etapas["salvas"][0]
        assert "duracao_segundos" in stats
        assert isinstance(stats["duracao_segundos"], (int, float))
        assert stats["duracao_segundos"] >= 0
