"""Testes da classificacao de editais (LLM-first + fallback regex)."""
import pytest

import validador
from validador import _titulo_fallback, validar_edital


# ─────────────────────────────────────────────
# _titulo_fallback
# ─────────────────────────────────────────────

class TestTituloFallback:

    def test_remove_extensao_e_capitaliza(self):
        assert _titulo_fallback("edital-08-2026.pdf.md") == "Edital 08 2026"

    def test_substitui_hifens_por_espacos(self):
        assert _titulo_fallback("edital-no-07-prpgi.pdf.md") == "Edital No 07 Prpgi"


# ─────────────────────────────────────────────
# validar_edital — LLM-first com fallback regex
# ─────────────────────────────────────────────

class TestValidarEdital:

    def test_llm_retorna_valido_e_usado_diretamente(self, tmp_path, monkeypatch):
        md = tmp_path / "edital-08-2026.pdf.md"
        md.write_text("Edital PIBIC do IFBA", encoding="utf-8")

        monkeypatch.setattr(
            validador, "gerar_json",
            lambda prompt: {
                "valido": True,
                "programa": "PIBIC",
                "titulo_amigavel": "Edital 08/2026 - PIBIC",
                "motivo": "ok",
            },
        )

        r = validar_edital(md)
        assert r["valido"] is True
        assert r["programa"] == "PIBIC"
        assert r["titulo_amigavel"] == "Edital 08/2026 - PIBIC"

    def test_llm_falha_e_fallback_regex_detecta_pibic(self, tmp_path, monkeypatch):
        md = tmp_path / "edital.pdf.md"
        md.write_text("Este edital trata do PIBIC para 2026", encoding="utf-8")

        def boom(_):
            raise RuntimeError("LLM offline")
        monkeypatch.setattr(validador, "gerar_json", boom)

        r = validar_edital(md)
        assert r["valido"] is True
        assert r["programa"] == "PIBIC"
        assert "regex" in r["motivo"].lower()

    def test_llm_falha_sem_programa_no_texto(self, tmp_path, monkeypatch):
        md = tmp_path / "edital.pdf.md"
        md.write_text("Texto qualquer sem o programa de interesse", encoding="utf-8")

        monkeypatch.setattr(
            validador, "gerar_json",
            lambda _: (_ for _ in ()).throw(RuntimeError("falhou")),
        )

        r = validar_edital(md)
        assert r["valido"] is False
        assert r["programa"] == "OUTRO"

    def test_llm_retorna_dict_sem_campo_valido_dispara_fallback(self, tmp_path, monkeypatch):
        md = tmp_path / "edital.pdf.md"
        md.write_text("PIBITI 2026", encoding="utf-8")

        # LLM retorna dict mas sem a chave 'valido' — codigo cai no fallback regex
        monkeypatch.setattr(validador, "gerar_json", lambda _: {"motivo": "ok"})

        r = validar_edital(md)
        assert r["valido"] is True
        assert r["programa"] == "PIBITI"
