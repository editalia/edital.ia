"""Testes das funcoes puras do extrator_rag (criterio de fallback + recortes)."""
from extrator_rag import _precisa_refazer, _recortes_relevantes, _montar_resultado


# ─────────────────────────────────────────────
# _precisa_refazer
# ─────────────────────────────────────────────

class TestPrecisaRefazer:

    def test_dict_vazio_precisa_refazer(self):
        assert _precisa_refazer({}) is True

    def test_valor_nao_encontrado_precisa_refazer(self):
        ans = {
            "valor_bolsa": "NAO_ENCONTRADO",
            "data_de_inscricao_texto": "01/01/2026 a 10/01/2026",
            "documentos_necessarios": ["RG"],
        }
        assert _precisa_refazer(ans) is True

    def test_data_nao_encontrada_precisa_refazer(self):
        ans = {
            "valor_bolsa": "R$ 700",
            "data_de_inscricao_texto": "NAO_ENCONTRADO",
            "documentos_necessarios": ["RG"],
        }
        assert _precisa_refazer(ans) is True

    def test_docs_vazia_precisa_refazer(self):
        ans = {
            "valor_bolsa": "R$ 700",
            "data_de_inscricao_texto": "01/01/2026 a 10/01/2026",
            "documentos_necessarios": [],
        }
        assert _precisa_refazer(ans) is True

    def test_todos_campos_preenchidos_nao_precisa_refazer(self):
        ans = {
            "valor_bolsa": "R$ 700",
            "data_de_inscricao_texto": "01/01/2026 a 10/01/2026",
            "documentos_necessarios": ["RG", "CPF"],
        }
        assert _precisa_refazer(ans) is False

    def test_case_insensitive_nao_encontrado(self):
        # str.upper() é aplicado, então qualquer case funciona
        ans = {
            "valor_bolsa": "nao_encontrado",
            "data_de_inscricao_texto": "ok",
            "documentos_necessarios": ["x"],
        }
        assert _precisa_refazer(ans) is True


# ─────────────────────────────────────────────
# _recortes_relevantes
# ─────────────────────────────────────────────

class TestRecortesRelevantes:

    def test_texto_sem_padroes_retorna_inicio(self):
        texto = "Lorem ipsum dolor sit amet." * 100
        resultado = _recortes_relevantes(texto, max_chars=500)
        assert len(resultado) <= 500
        assert resultado == texto[:500]

    def test_recorta_em_torno_de_palavra_chave(self):
        texto = "\n".join([
            "linha 1 fora",
            "linha 2 fora",
            "linha 3 fora",
            "linha 4 fora",
            "linha 5 fora",
            "linha 6 fora",
            "esta tem inscricao aqui",
            "linha 8 fora",
            "linha 9 fora",
        ])
        resultado = _recortes_relevantes(texto, max_chars=5000)
        # Janela inclui as 6 anteriores + a linha + 6 posteriores
        assert "inscricao" in resultado
        assert "linha 1 fora" in resultado  # ±6 alcanca

    def test_respeita_max_chars(self):
        texto = "linha com R$ 100\n" * 200
        resultado = _recortes_relevantes(texto, max_chars=300)
        assert len(resultado) <= 300


# ─────────────────────────────────────────────
# _montar_resultado
# ─────────────────────────────────────────────

class TestMontarResultado:

    def test_preenche_defaults_quando_dados_vazios(self):
        r = _montar_resultado("ex.md", "RAG_VETORIAL", {})
        assert r["arquivo"] == "ex.md"
        assert r["metodo_extracao"] == "RAG_VETORIAL"
        assert r["resumo"] == ""
        assert r["valor_bolsa"] == "NAO_ENCONTRADO"
        assert r["documentos_necessarios"] == []
        assert "extraido_em" in r

    def test_preserva_dados_fornecidos(self):
        dados = {
            "resumo": "Edital PIBIC 2026",
            "valor_bolsa": "R$ 700",
            "documentos_necessarios": ["RG"],
        }
        r = _montar_resultado("ex.md", "RAG_VETORIAL", dados)
        assert r["resumo"] == "Edital PIBIC 2026"
        assert r["valor_bolsa"] == "R$ 700"
        assert r["documentos_necessarios"] == ["RG"]
