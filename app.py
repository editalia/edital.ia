"""Front read-only do Edital.IA.

Lê dos JSONs em state/ — não dispara LLM, não roda pipeline.
A atualização da base é feita pelo pipeline.py (manual ou via cron).
"""
from datetime import datetime

import streamlit as st

from state import (
    carregar_editais,
    carregar_extracoes,
    carregar_pipeline_state,
    calcular_status_edital,
)

st.set_page_config(
    page_title="Edital.IA",
    page_icon="🎓",
    layout="wide",
)

# ─────────────────────────────────────────────
# Logo / cabeçalho — "Edital" verde + ".IA" vermelho
# ─────────────────────────────────────────────
st.markdown(
    """
    <div style="text-align:center; padding:24px 0 8px 0;">
        <h1 style="font-size:3.6em; margin:0; font-weight:800; letter-spacing:-1px;">
            <span style="color:#22c55e;">Edital</span><span style="color:#ef4444;">.IA</span>
        </h1>
        <p style="font-size:1.05em; color:#6b7280; margin:6px 0 0 0;">
            Monitoramento inteligente de editais de bolsas de incentivo do IFBA
        </p>
    </div>
    <hr style="margin:18px 0 28px 0; border:none; border-top:1px solid #e5e7eb;">
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────
# Carrega dados pré-processados
# ─────────────────────────────────────────────
editais = carregar_editais()
extracoes = carregar_extracoes()
pipeline_state = carregar_pipeline_state()

# Apenas válidos com extração feita
editais_validos: dict = {}
for k, v in editais.items():
    if not v.get("valido"):
        continue
    if k not in extracoes:
        continue
    extr = extracoes[k]
    editais_validos[k] = {
        **v,
        "_extracao": extr,
        "_status": calcular_status_edital(extr.get("data_inscricao_fim")),
    }

# ─────────────────────────────────────────────
# Sidebar — filtros + lista agrupada por programa
# ─────────────────────────────────────────────
st.sidebar.markdown("### 🔍 Filtros")
mostrar_encerrados = st.sidebar.toggle(
    "Mostrar editais encerrados",
    value=False,
    help="Por padrão, exibe apenas editais com inscrições abertas ou sem data definida.",
)


def _visivel(info: dict) -> bool:
    s = info["_status"]["status"]
    if mostrar_encerrados:
        return True
    return s in ("aberto", "indefinido")


editais_filtrados = {k: v for k, v in editais_validos.items() if _visivel(v)}


def _grupos(editais_dict):
    grupos = {"PIBIC": [], "PIBITI": [], "PIBID": [], "OUTRO": []}
    for k, v in editais_dict.items():
        prog = (v.get("programa") or "OUTRO").upper()
        if prog not in grupos:
            grupos[prog] = []
        grupos[prog].append((k, v))
    return grupos


def _chave_ordem(item):
    """Mais urgente primeiro: ordena por data_inscricao_fim ascendente."""
    _, info = item
    return info["_extracao"].get("data_inscricao_fim") or "9999-99-99"


grupos = _grupos(editais_filtrados)

ICONES = {"PIBIC": "📚", "PIBITI": "🔬", "PIBID": "🎓", "OUTRO": "📋"}

st.sidebar.markdown("### 📂 Editais Disponíveis")

algum_visivel = any(items for items in grupos.values())
if not algum_visivel:
    if not editais_validos:
        st.sidebar.info("Base ainda vazia. Rode `python pipeline.py` para popular.")
    else:
        st.sidebar.info(
            "Nenhum edital com inscrições abertas. "
            "Ative o toggle 'Mostrar encerrados' para ver o histórico."
        )

for prog, items in grupos.items():
    if not items:
        continue
    items.sort(key=_chave_ordem)
    with st.sidebar.expander(f"{ICONES[prog]} {prog} ({len(items)})", expanded=True):
        for k, info in items:
            label = info.get("titulo_amigavel", k)
            semaforo = info["_status"]["semaforo"]
            if st.button(
                f"{semaforo} {label}",
                key=f"btn_{k}",
                use_container_width=True,
            ):
                st.session_state["selected"] = k

arquivo_selecionado = st.session_state.get("selected")

# Última atualização do pipeline
ultima = pipeline_state.get("ultima_execucao")
if ultima:
    try:
        dt = datetime.fromisoformat(ultima)
        st.sidebar.markdown(
            f"""
            <div style='font-size:0.85em; color:#9ca3af; margin-top:24px;
                        padding-top:12px; border-top:1px solid #e5e7eb;'>
                Atualizado em<br>
                <strong style='color:#6b7280;'>{dt.strftime('%d/%m/%Y às %H:%M')}</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        pass

# ─────────────────────────────────────────────
# Área principal
# ─────────────────────────────────────────────
if not arquivo_selecionado or arquivo_selecionado not in editais_validos:
    st.markdown(
        """
        <div style="background:#f8fafc; padding:32px; border-radius:8px;
                    text-align:center; color:#6b7280;">
            <h4 style="color:#1f2937; margin:0 0 8px 0;">
                👈 Selecione um edital na barra lateral
            </h4>
            <p style="margin:0;">
                Você verá <strong>resumo</strong>, <strong>período de inscrição</strong>,
                <strong>valor da bolsa</strong>, <strong>documentos necessários</strong>
                e <strong>link para o edital oficial</strong>.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    info = editais_validos[arquivo_selecionado]
    extr = info["_extracao"]
    status = info["_status"]
    cor_prog = {
        "PIBIC": "#22c55e",
        "PIBITI": "#3b82f6",
        "PIBID": "#8b5cf6",
    }.get(info.get("programa"), "#6b7280")

    # Cabeçalho com badge do programa
    st.markdown(
        f"""
        <div style="margin-bottom:24px;">
            <div style="display:inline-block; background:{cor_prog}; color:white;
                        padding:4px 14px; border-radius:20px;
                        font-size:0.85em; font-weight:600; margin-bottom:10px;">
                {info.get('programa', 'EDITAL')}
            </div>
            <h2 style="margin:0; color:#1f2937; font-weight:700;">
                {info.get('titulo_amigavel', arquivo_selecionado)}
            </h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Resumo
    resumo = extr.get("resumo", "")
    if resumo and resumo != "NAO_ENCONTRADO":
        st.markdown(
            f"""
            <div style="background:#f8fafc; border-left:4px solid {cor_prog};
                        padding:18px 20px; border-radius:6px; margin-bottom:24px;">
                <div style="font-size:0.85em; color:#6b7280;
                            margin-bottom:8px; font-weight:600;">
                    📋 RESUMO
                </div>
                <div style="color:#1f2937; line-height:1.65;">
                    {resumo}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Cards: período, valor, semáforo
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        st.markdown(
            f"""
            <div style="background:white; border:1px solid #e5e7eb;
                        padding:18px 20px; border-radius:6px; height:100px;">
                <div style="font-size:0.85em; color:#6b7280; margin-bottom:6px;">
                    📅 Período de Inscrição
                </div>
                <div style="font-size:1.15em; color:#1f2937; font-weight:600;">
                    {extr.get('data_de_inscricao_texto', 'Não informado')}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
            <div style="background:white; border:1px solid #e5e7eb;
                        padding:18px 20px; border-radius:6px; height:100px;">
                <div style="font-size:0.85em; color:#6b7280; margin-bottom:6px;">
                    💰 Valor da Bolsa
                </div>
                <div style="font-size:1.15em; color:#1f2937; font-weight:600;">
                    {extr.get('valor_bolsa', 'Não informado')}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        dias = status.get("dias_restantes")
        sem = status.get("semaforo", "⚫")
        if status["status"] == "aberto" and dias is not None:
            txt = f"{dias} dias<br>restantes" if dias > 0 else "Último dia!"
            cor_fundo = {
                "🟢": "#dcfce7",
                "🟡": "#fef3c7",
                "🔴": "#fee2e2",
            }.get(sem, "#f3f4f6")
        elif status["status"] == "encerrado":
            txt = "Encerrado"
            cor_fundo = "#f3f4f6"
        else:
            txt = "Sem data"
            cor_fundo = "#f3f4f6"

        st.markdown(
            f"""
            <div style="background:{cor_fundo}; padding:14px;
                        border-radius:6px; text-align:center; height:100px;">
                <div style="font-size:1.8em; line-height:1;">{sem}</div>
                <div style="font-size:0.9em; color:#1f2937; font-weight:600;
                            margin-top:6px;">
                    {txt}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Documentos
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 📄 Documentos Necessários")
    docs = extr.get("documentos_necessarios", [])
    if docs and isinstance(docs, list):
        for d in docs:
            st.markdown(f"- {d}")
    else:
        st.info("Nenhum documento listado para este edital.")

    # Link oficial
    url_oficial = info.get("url_original") or info.get("url_pdf")
    if url_oficial:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <a href="{url_oficial}" target="_blank" style="text-decoration:none;">
                <div style="background:linear-gradient(135deg, #22c55e, #16a34a);
                            color:white; padding:16px; border-radius:6px;
                            text-align:center; font-weight:600; font-size:1.05em;
                            box-shadow:0 2px 8px rgba(34,197,94,0.3);">
                    🔗 Abrir edital oficial no portal IFBA
                </div>
            </a>
            """,
            unsafe_allow_html=True,
        )
