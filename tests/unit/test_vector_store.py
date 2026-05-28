"""Testes da normalizacao de Markdown para embedding.

Nao testa o chunking nem a indexacao em ChromaDB — isso pertence aos
testes de integracao (e e' lento por causa do modelo de embedding).
"""
from vector_store import _limpar_para_embedding


class TestLimparParaEmbedding:

    def test_remove_strikethrough_com_conteudo(self):
        texto = "Inscricoes ate ~~15/04/2026~~ 30/04/2026"
        assert "15/04/2026" not in _limpar_para_embedding(texto)
        assert "30/04/2026" in _limpar_para_embedding(texto)

    def test_remove_asteriscos_de_bold(self):
        assert _limpar_para_embedding("**Edital**") == "Edital"

    def test_remove_asteriscos_de_italico(self):
        assert _limpar_para_embedding("*importante*") == "importante"

    def test_br_html_vira_espaco(self):
        assert "<br>" not in _limpar_para_embedding("linha1<br>linha2")
        assert _limpar_para_embedding("linha1<br>linha2") == "linha1 linha2"

    def test_br_self_closing_vira_espaco(self):
        assert _limpar_para_embedding("a<br/>b") == "a b"

    def test_br_case_insensitive(self):
        assert _limpar_para_embedding("a<BR>b") == "a b"

    def test_remove_numero_ponto_com_muitos_espacos(self):
        # padrao "0.    texto" que aparece em listas mal formatadas
        assert _limpar_para_embedding("0.    Item da lista") == "Item da lista"

    def test_normaliza_espacos_multiplos(self):
        assert _limpar_para_embedding("oi      mundo") == "oi mundo"

    def test_preserva_quebras_de_linha(self):
        resultado = _limpar_para_embedding("linha1\nlinha2")
        assert "\n" in resultado

    def test_texto_limpo_e_preservado(self):
        texto = "Bolsa de R$ 700 mensais"
        assert _limpar_para_embedding(texto) == texto

    def test_strip_no_resultado_final(self):
        assert _limpar_para_embedding("   texto   ") == "texto"
