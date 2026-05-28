"""Testes do modulo state.py — helpers de persistencia e calculo de status."""
from datetime import date, timedelta

import pytest

from state import calcular_status_edital


# ─────────────────────────────────────────────
# calcular_status_edital
# ─────────────────────────────────────────────

class TestCalcularStatusEdital:

    def test_data_none_retorna_indefinido(self):
        r = calcular_status_edital(None)
        assert r["status"] == "indefinido"
        assert r["dias_restantes"] is None
        assert r["semaforo"] == "⚫"

    def test_string_nao_encontrado_retorna_indefinido(self):
        r = calcular_status_edital("NAO_ENCONTRADO")
        assert r["status"] == "indefinido"

    def test_string_null_retorna_indefinido(self):
        r = calcular_status_edital("null")
        assert r["status"] == "indefinido"

    def test_formato_invalido_retorna_indefinido(self):
        r = calcular_status_edital("nao-eh-data")
        assert r["status"] == "indefinido"

    def test_data_passada_retorna_encerrado(self):
        ontem = (date.today() - timedelta(days=1)).isoformat()
        r = calcular_status_edital(ontem)
        assert r["status"] == "encerrado"
        assert r["dias_restantes"] == -1
        assert r["semaforo"] == "⚫"

    def test_data_hoje_retorna_aberto_vermelho(self):
        hoje = date.today().isoformat()
        r = calcular_status_edital(hoje)
        assert r["status"] == "aberto"
        assert r["dias_restantes"] == 0
        assert r["semaforo"] == "🔴"

    def test_data_5_dias_retorna_amarelo(self):
        d = (date.today() + timedelta(days=5)).isoformat()
        r = calcular_status_edital(d)
        assert r["status"] == "aberto"
        assert r["dias_restantes"] == 5
        assert r["semaforo"] == "🟡"

    def test_data_7_dias_retorna_amarelo(self):
        d = (date.today() + timedelta(days=7)).isoformat()
        r = calcular_status_edital(d)
        assert r["semaforo"] == "🟡"

    def test_data_8_dias_retorna_verde(self):
        d = (date.today() + timedelta(days=8)).isoformat()
        r = calcular_status_edital(d)
        assert r["status"] == "aberto"
        assert r["semaforo"] == "🟢"

    def test_data_longe_retorna_verde(self):
        d = (date.today() + timedelta(days=60)).isoformat()
        r = calcular_status_edital(d)
        assert r["semaforo"] == "🟢"


# ─────────────────────────────────────────────
# Persistencia (carregar / salvar)
# ─────────────────────────────────────────────

class TestPersistencia:

    def test_carregar_editais_vazio_retorna_dict_vazio(self, state_tmp):
        assert state_tmp.carregar_editais() == {}

    def test_carregar_extracoes_vazio_retorna_dict_vazio(self, state_tmp):
        assert state_tmp.carregar_extracoes() == {}

    def test_salvar_e_carregar_editais_round_trip(self, state_tmp):
        dados = {"x.md": {"valido": True, "programa": "PIBIC"}}
        state_tmp.salvar_editais(dados)
        assert state_tmp.carregar_editais() == dados

    def test_carregar_json_corrompido_retorna_default(self, state_tmp):
        state_tmp.EDITAIS_FILE.write_text("{nao eh json valido", encoding="utf-8")
        assert state_tmp.carregar_editais() == {}

    def test_salvar_pipeline_state_adiciona_timestamp(self, state_tmp):
        state_tmp.salvar_pipeline_state({"status": "sucesso"})
        carregado = state_tmp.carregar_pipeline_state()
        assert carregado["status"] == "sucesso"
        assert "ultima_execucao" in carregado
        assert carregado["ultima_execucao"] is not None


# ─────────────────────────────────────────────
# registrar_metodo_extracao
# ─────────────────────────────────────────────

class TestRegistrarMetodoExtracao:

    def test_primeiro_registro_cria_stats(self, state_tmp):
        state_tmp.registrar_metodo_extracao("RAG_VETORIAL")
        stats = state_tmp.carregar_stats()
        assert stats["por_metodo"]["RAG_VETORIAL"] == 1
        assert stats["total"] == 1

    def test_registros_consecutivos_acumulam(self, state_tmp):
        state_tmp.registrar_metodo_extracao("RAG_VETORIAL")
        state_tmp.registrar_metodo_extracao("RAG_VETORIAL")
        state_tmp.registrar_metodo_extracao("FULL_TEXT_FALLBACK")
        stats = state_tmp.carregar_stats()
        assert stats["por_metodo"]["RAG_VETORIAL"] == 2
        assert stats["por_metodo"]["FULL_TEXT_FALLBACK"] == 1
        assert stats["total"] == 3
