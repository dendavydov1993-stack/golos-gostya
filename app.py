"""
app.py — UI-слой аналитической системы «Голос Гостя».

Основные обязанности:
  • Вёрстка интерфейса Streamlit с тёмной glassmorphism-темой
  • Отображение KPI-метрик, графиков Plotly и таблиц
  • Вызов функций backend.py для обработки данных
  • Экспорт PDF-отчётов через сайдбар
"""

from __future__ import annotations

import base64
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import backend as be

# ---------------------------------------------------------------------------
# Конфигурация страницы Streamlit
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Голос Гостя — Аналитика",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Пользовательские стили CSS (Dark Glassmorphism Theme)
# ---------------------------------------------------------------------------

_CUSTOM_CSS = """
<style>
/* ============================================================
   Глобальные стили — глубокая тёмная тема
   ============================================================ */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* Фон всего приложения — глубокий slate */
.stApp {
    background: linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F172A 100%) !important;
    background-attachment: fixed !important;
}

/* Убираем стандартные отступы контейнера */
.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 2rem !important;
    max-width: 1400px !important;
}

/* ============================================================
   Градиентный заголовок
   ============================================================ */
.gradient-title {
    font-size: 2.4rem;
    font-weight: 800;
    background: linear-gradient(135deg, #38BDF8 0%, #34D399 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    text-align: center;
    margin-bottom: 0.3rem;
    letter-spacing: -0.5px;
}

.subtitle {
    font-size: 1rem;
    color: #94A3B8;
    text-align: center;
    margin-bottom: 1.5rem;
}

/* ============================================================
   KPI-карточки с glassmorphism
   ============================================================ */
.kpi-container {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1rem;
    margin-bottom: 1.5rem;
}

.kpi-card {
    background: rgba(30, 41, 59, 0.5) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    border: 1px solid rgba(56, 189, 248, 0.15) !important;
    border-radius: 16px !important;
    padding: 1.2rem 1rem !important;
    text-align: center !important;
    transition: all 0.3s ease !important;
    position: relative;
    overflow: hidden;
}

.kpi-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, #38BDF8, #34D399);
    border-radius: 16px 16px 0 0;
}

.kpi-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 40px rgba(56, 189, 248, 0.15);
    border-color: rgba(56, 189, 248, 0.3) !important;
}

.kpi-label {
    font-size: 0.75rem;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 0.4rem;
    font-weight: 600;
}

.kpi-value {
    font-size: 2rem;
    font-weight: 800;
    color: #F8FAFC;
    line-height: 1.2;
}

.kpi-delta {
    font-size: 0.8rem;
    margin-top: 0.3rem;
    font-weight: 500;
}

.kpi-positive { color: #34D399; }
.kpi-negative { color: #E11D48; }
.kpi-neutral { color: #F59E0B; }

/* ============================================================
   Вкладки (Tabs) — кастомный стиль
   ============================================================ */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background: rgba(30, 41, 59, 0.4);
    border-radius: 12px;
    padding: 6px;
    backdrop-filter: blur(8px);
}

.stTabs [data-baseweb="tab"] {
    height: 44px;
    background: transparent;
    border-radius: 10px;
    color: #94A3B8;
    font-weight: 600;
    font-size: 0.9rem;
    border: none !important;
    padding: 0 1.5rem;
    transition: all 0.2s ease;
}

.stTabs [data-baseweb="tab"]:hover {
    color: #38BDF8;
    background: rgba(56, 189, 248, 0.08);
}

.stTabs [aria-selected="true"] {
    background: rgba(56, 189, 248, 0.15) !important;
    color: #38BDF8 !important;
    border: 1px solid rgba(56, 189, 248, 0.2) !important;
}

.stTabs [data-baseweb="tab-panel"] {
    padding-top: 1.5rem;
}

/* ============================================================
   Сайдбар — glassmorphism
   ============================================================ */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0F172A 0%, #1E293B 100%) !important;
    border-right: 1px solid rgba(56, 189, 248, 0.1);
}

[data-testid="stSidebar"] .block-container {
    padding-top: 2rem !important;
}

.sidebar-title {
    font-size: 1.1rem;
    font-weight: 700;
    color: #38BDF8;
    margin-bottom: 1rem;
    text-align: center;
    letter-spacing: 0.5px;
}

/* ============================================================
   Кнопки
   ============================================================ */
.stButton > button {
    background: linear-gradient(135deg, #38BDF8 0%, #34D399 100%) !important;
    color: #0F172A !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 0.6rem 1.5rem !important;
    transition: all 0.3s ease !important;
    width: 100%;
}

.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(56, 189, 248, 0.3) !important;
    filter: brightness(1.1);
}

.stDownloadButton > button {
    background: rgba(30, 41, 59, 0.6) !important;
    color: #38BDF8 !important;
    border: 1px solid rgba(56, 189, 248, 0.25) !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    padding: 0.6rem 1.5rem !important;
    transition: all 0.3s ease !important;
    width: 100%;
}

.stDownloadButton > button:hover {
    background: rgba(56, 189, 248, 0.15) !important;
    border-color: rgba(56, 189, 248, 0.4) !important;
    box-shadow: 0 4px 15px rgba(56, 189, 248, 0.15) !important;
}

/* ============================================================
   File uploader
   ============================================================ */
.stFileUploader > div > div {
    background: rgba(30, 41, 59, 0.4) !important;
    border: 2px dashed rgba(56, 189, 248, 0.25) !important;
    border-radius: 16px !important;
    padding: 2rem !important;
    transition: all 0.3s ease !important;
}

.stFileUploader > div > div:hover {
    border-color: rgba(56, 189, 248, 0.5) !important;
    background: rgba(30, 41, 59, 0.6) !important;
}

/* ============================================================
   Selectbox / Multiselect
   ============================================================ */
.stSelectbox > div > div {
    background: rgba(30, 41, 59, 0.5) !important;
    border: 1px solid rgba(56, 189, 248, 0.15) !important;
    border-radius: 12px !important;
    color: #F8FAFC !important;
}

.stSelectbox > div > div:focus {
    border-color: #38BDF8 !important;
    box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.2) !important;
}

/* ============================================================
   DataFrame / Таблицы
   ============================================================ */
[data-testid="stDataFrame"] {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid rgba(56, 189, 248, 0.1);
}

/* ============================================================
   Разделители
   ============================================================ */
hr {
    border: none;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(56, 189, 248, 0.3), transparent);
    margin: 1.5rem 0;
}

/* ============================================================
   Expander
   ============================================================ */
.stExpander {
    background: rgba(30, 41, 59, 0.3) !important;
    border: 1px solid rgba(56, 189, 248, 0.1) !important;
    border-radius: 12px !important;
    backdrop-filter: blur(8px);
}

/* ============================================================
    Spinner / Прогресс
   ============================================================ */
.stSpinner > div > div {
    border-color: #38BDF8 transparent transparent transparent !important;
}

/* ============================================================
   Уведомления (toast)
   ============================================================ */
.stAlert {
    border-radius: 12px !important;
    border: none !important;
}

.stAlert [data-testid="stAlertContentSuccess"] {
    background: rgba(52, 211, 153, 0.1) !important;
    border: 1px solid rgba(52, 211, 153, 0.2) !important;
    color: #34D399 !important;
}

.stAlert [data-testid="stAlertContentError"] {
    background: rgba(225, 29, 72, 0.1) !important;
    border: 1px solid rgba(225, 29, 72, 0.2) !important;
    color: #E11D48 !important;
}

/* ============================================================
   Подвал
   ============================================================ */
.footer-text {
    text-align: center;
    color: #475569;
    font-size: 0.75rem;
    margin-top: 3rem;
    padding-top: 1.5rem;
    border-top: 1px solid rgba(56, 189, 248, 0.1);
}

/* ============================================================
   Адаптивность
   ============================================================ */
@media (max-width: 768px) {
    .kpi-container {
        grid-template-columns: repeat(2, 1fr) !important;
    }
    .gradient-title {
        font-size: 1.8rem !important;
    }
}
</style>
"""

st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Инициализация session_state
# ---------------------------------------------------------------------------

if "data" not in st.session_state:
    st.session_state.data = None
if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None
if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None


# ---------------------------------------------------------------------------
# Сбор всех графиков для PDF-экспорта
# ---------------------------------------------------------------------------

def _build_all_charts(data: dict[str, Any]) -> dict[str, go.Figure]:
    """Собирает все графики для включения в PDF-отчёт."""
    charts = {}

    # NPS chart
    nps_df = data.get("nps", pd.DataFrame())
    if not nps_df.empty:
        fig = px.area(nps_df, x="Месяц", y="NPS", template="plotly_dark")
        fig.update_traces(fill='tozeroy', line=dict(color='#38BDF8', width=2))
        fig.add_hline(y=80, line_dash="dash", line_color="#34D399")
        fig.update_layout(height=400, margin=dict(l=20, r=20, t=30, b=20))
        charts["nps"] = fig

    # Radar chart
    months = be.get_available_months(data)
    if months:
        radar_df = be.get_radar_data(data, months[-1])
        if not radar_df.empty:
            categories = radar_df["Отдел"].tolist()
            values = radar_df["Средняя оценка"].tolist()
            categories_closed = categories + [categories[0]]
            values_closed = values + [values[0]]

            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(
                r=values_closed,
                theta=categories_closed,
                fill='toself',
                fillcolor='rgba(52, 211, 153, 0.25)',
                line=dict(color='#34D399', width=2),
            ))
            fig.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 5.5])),
                height=400, margin=dict(l=60, r=60, t=30, b=30),
            )
            charts["radar"] = fig

    # Heatmap
    heatmap_df = be.get_heatmap_data(data)
    if not heatmap_df.empty:
        fig = px.imshow(
            heatmap_df.values,
            x=heatmap_df.columns.tolist(),
            y=heatmap_df.index.tolist(),
            color_continuous_scale=[
                [0.0, "#E55B4B"],  # Красный
                [0.2, "#F29D4B"],  # Оранжевый
                [0.4, "#D1BA70"],  # Желто-оливковый
                [0.6, "#98C895"],  # Бледно-зелёный
                [0.8, "#5BA780"],  # Бирюзовый
                [1.0, "#428B6B"],  # Тёмно-бирюзовый
            ],
            aspect="auto",
        )
        fig.update_traces(
            text=heatmap_df.values, 
            texttemplate="%{text:.2f}", 
            xgap=1, 
            ygap=1,
            textfont=dict(color="white", size=10)
        )
        fig.update_layout(height=500, margin=dict(l=20, r=20, t=30, b=20))
        charts["heatmap"] = fig

    return charts


# ---------------------------------------------------------------------------
# Сайдбар
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("<div class='sidebar-title'>📁 ИСТОЧНИК ДАННЫХ</div>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "Загрузите отчёт (.xlsx или .csv)",
        type=["xlsx", "xls", "csv"],
        help="Файл должен содержать листы: NPS, СПИР, Горничные, Питание, Мед.часть, Столовая"
    )

    if st.button("🔄 Сбросить кэш (ОБЯЗАТЕЛЬНО)", use_container_width=True):
        st.cache_data.clear()
        st.session_state.data = None
        st.session_state.pdf_bytes = None
        st.rerun()

    if uploaded_file is not None:
        st.session_state.uploaded_file = uploaded_file
        # Читаем и парсим данные
        with st.spinner("Обработка данных..."):
            sheets = be.read_file(uploaded_file)
            if sheets:
                st.session_state.data = be.parse_all_sheets(sheets)
                st.success(f"Загружено листов: {len(sheets)}")

    st.markdown("<hr>", unsafe_allow_html=True)

    # Кнопка PDF-отчёта
    st.markdown("<div class='sidebar-title'>📄 ЭКСПОРТ</div>", unsafe_allow_html=True)

    if st.button("Подготовить PDF-отчёт", key="pdf_btn"):
        if st.session_state.data is not None:
            with st.spinner("Генерация PDF..."):
                try:
                    charts = _build_all_charts(st.session_state.data)
                    pdf_bytes = be.generate_pdf_report(st.session_state.data, charts)
                    st.session_state.pdf_bytes = pdf_bytes
                    st.success("PDF-отчёт готов!")
                except Exception as e:
                    st.error(f"Ошибка генерации PDF: {e}")
        else:
            st.warning("Сначала загрузите файл с данными")

    if st.session_state.pdf_bytes is not None:
        st.download_button(
            label="⬇ Скачать PDF-отчёт",
            data=st.session_state.pdf_bytes,
            file_name=f"Golos_Gostya_Report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            key="download_pdf"
        )

    # Кнопка Excel-экспорта
    if st.session_state.data is not None:
        if st.button("📥 Скачать Excel", key="xlsx_btn"):
            with st.spinner("Формирование Excel..."):
                xlsx_bytes = be.export_to_excel(st.session_state.data)
                st.session_state.xlsx_bytes = xlsx_bytes

    if "xlsx_bytes" in st.session_state and st.session_state.get("xlsx_bytes") is not None:
        st.download_button(
            label="⬇ Скачать XLSX",
            data=st.session_state.xlsx_bytes,
            file_name=f"Golos_Gostya_Data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_xlsx"
        )

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size: 0.75rem; color: #475569; text-align: center;'>"
        "Голос Гостя v3.0<br>© 2025</div>",
        unsafe_allow_html=True
    )




# ---------------------------------------------------------------------------
# Вспомогательные функции отображения
# ---------------------------------------------------------------------------

def _show_welcome():
    """Отображает приветственный экран при отсутствии данных."""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style="
            background: rgba(30, 41, 59, 0.4);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(56, 189, 248, 0.15);
            border-radius: 20px;
            padding: 3rem 2rem;
            text-align: center;
            margin-top: 3rem;
        ">
            <div style="font-size: 4rem; margin-bottom: 1rem;">📊</div>
            <h2 style="color: #F8FAFC; font-weight: 700; margin-bottom: 0.5rem;">Добро пожаловать</h2>
            <p style="color: #94A3B8; font-size: 1rem; line-height: 1.6;">
                Загрузите Excel-отчёт в сайдбаре, чтобы начать анализ.<br>
                Система автоматически распознает все листы и построит визуализации.
            </p>
            <div style="margin-top: 1.5rem; display: flex; justify-content: center; gap: 1rem; flex-wrap: wrap;">
                <span style="background: rgba(56, 189, 248, 0.1); color: #38BDF8; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.8rem;">NPS</span>
                <span style="background: rgba(52, 211, 153, 0.1); color: #34D399; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.8rem;">СПИР</span>
                <span style="background: rgba(245, 158, 11, 0.1); color: #F59E0B; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.8rem;">Горничные</span>
                <span style="background: rgba(225, 29, 72, 0.1); color: #E11D48; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.8rem;">Питание</span>
                <span style="background: rgba(167, 139, 250, 0.1); color: #A78BFA; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.8rem;">Мед.часть</span>
                <span style="background: rgba(244, 114, 182, 0.1); color: #F472B6; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.8rem;">Столовая</span>
            </div>
        </div>
        """, unsafe_allow_html=True)


def _render_dashboard(data: dict[str, Any]):
    """Основная функция отрисовки дашборда с данными."""

    # Получаем список всех отделов для фильтра
    all_depts = []
    if not data.get("combined", pd.DataFrame()).empty:
        all_depts = sorted(data["combined"]["Отдел"].dropna().unique().tolist())

    # Красивый фильтр "таблетками" над всем дашбордом
    selected_dept = st.pills(
        "🎯 Фильтр по направлению:", 
        options=["Все"] + all_depts, 
        default="Все",
        key="global_dept_filter"
    )

    # Создаем отфильтрованные данные
    filtered_data = data.copy()
    if selected_dept and selected_dept != "Все" and not data.get("combined", pd.DataFrame()).empty:
        comb = data["combined"]
        filtered_data["combined"] = comb[comb["Отдел"] == selected_dept].copy()

    # --- KPI-карточки с дельтами ---
    metrics = be.compute_kpi_with_delta(filtered_data)
    _render_kpi_cards(metrics)

    # --- Панель инсайтов ---
    _render_insights(filtered_data)

    st.markdown("<hr>", unsafe_allow_html=True)

    # --- Вкладки с графиками ---
    tab_nps, tab_radar, tab_heatmap, tab_compare, tab_rank, tab_drill = st.tabs([
        "📈 NPS",
        "🕸️ Радар",
        "🔥 Тепловая",
        "⚖️ Сравнение",
        "🏅 Рейтинг",
        "🔍 Детализация"
    ])

    with tab_nps:
        _render_nps_tab(filtered_data)

    with tab_radar:
        # Радару всегда передаем полные (неотфильтрованные) данные,
        # иначе на нём останется только одна точка после клика.
        _render_radar_tab(data)

    with tab_heatmap:
        _render_heatmap_tab(filtered_data)

    with tab_compare:
        _render_compare_tab(filtered_data)

    with tab_rank:
        _render_ranking_tab(filtered_data)

    with tab_drill:
        _render_drilldown_tab(filtered_data)

    # --- Подвал ---
    st.markdown(
        "<div class='footer-text'>"
        "Голос Гостя — Аналитическая система мониторинга качества сервиса | "
        f"Обновлено: {pd.Timestamp.now().strftime('%d.%m.%Y %H:%M')}"
        "</div>",
        unsafe_allow_html=True
    )


def _render_kpi_cards(metrics: dict[str, Any]):
    """Отрисовывает 4 KPI-карточки с дельтами в стеклянном стиле."""
    cols = st.columns(4)

    def _delta_badge(delta, suffix=""):
        if delta is None:
            return ""
        color = "#34D399" if delta > 0 else "#E11D48" if delta < 0 else "#94A3B8"
        arrow = "▲" if delta > 0 else "▼" if delta < 0 else "●"
        return f"<span style='font-size:0.75rem;color:{color};'>{arrow} {abs(delta)}{suffix}</span>"

    # Карточка 1: NPS
    with cols[0]:
        nps_val = metrics.get("nps_last") or metrics.get("avg_nps")
        nps_display = f"{nps_val}%" if nps_val is not None else "—"
        nps_delta = _delta_badge(metrics.get("nps_delta"), "%")
        nps_color = "kpi-positive" if (nps_val and nps_val >= 80) else "kpi-negative"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">📊 NPS</div>
            <div class="kpi-value">{nps_display}</div>
            <div class="kpi-delta {nps_color}">
                {nps_delta if nps_delta else ("▲ Хороший" if nps_val and nps_val >= 80 else "▼ Требует внимания")}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Карточка 2: Общий балл
    with cols[1]:
        score_val = metrics.get("score_last") or metrics.get("total_score")
        score_display = f"{score_val}" if score_val is not None else "—"
        score_delta = _delta_badge(metrics.get("score_delta"))
        last_p = metrics.get("last_period", "")
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">⭐ Общий балл</div>
            <div class="kpi-value">{score_display}</div>
            <div class="kpi-delta kpi-neutral">
                {score_delta if score_delta else "—"} <span style="font-size:0.7rem;color:#64748B;">({last_p})</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Карточка 3: Лидер
    with cols[2]:
        leader_val = f"{metrics['leader_dept']}" if metrics['leader_dept'] else "—"
        leader_score = f"{metrics['leader_score']}" if metrics['leader_score'] else ""
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">🏆 Лидер</div>
            <div class="kpi-value" style="font-size: 1.4rem;">{leader_val}</div>
            <div class="kpi-delta kpi-positive">
                {"★ " + leader_score if leader_score else ""}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Карточка 4: Зона риска
    with cols[3]:
        risk_val = f"{metrics['risk_dept']}" if metrics['risk_dept'] else "Нет"
        risk_score = f"{metrics['risk_score']}" if metrics['risk_score'] else ""
        risk_class = "kpi-negative" if metrics['risk_dept'] else "kpi-positive"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">⚠️ Зона риска</div>
            <div class="kpi-value" style="font-size: 1.4rem;">{risk_val}</div>
            <div class="kpi-delta {risk_class}">
                {"▼ " + risk_score if risk_score else "✓ Все показатели в норме"}
            </div>
        </div>
        """, unsafe_allow_html=True)


def _render_insights(data: dict[str, Any]):
    """Панель автоматических инсайтов под KPI-карточками."""
    insights = be.generate_insights(data)
    if not insights:
        return

    icon_map = {
        "positive": ("✅", "#34D399", "rgba(52, 211, 153, 0.08)"),
        "negative": ("🔴", "#E11D48", "rgba(225, 29, 72, 0.08)"),
        "warning": ("⚠️", "#F59E0B", "rgba(245, 158, 11, 0.08)"),
        "info": ("💡", "#38BDF8", "rgba(56, 189, 248, 0.08)"),
    }

    items_html = ""
    for ins in insights[:10]:
        icon, color, bg = icon_map.get(ins["type"], ("ℹ️", "#94A3B8", "rgba(148, 163, 184, 0.08)"))
        items_html += (
            f'<div style="background:{bg};border-left:3px solid {color};padding:0.5rem 0.8rem;'
            f'border-radius:0 8px 8px 0;margin-bottom:0.4rem;font-size:0.85rem;color:#F8FAFC;line-height:1.4;">'
            f'{icon} {ins["text"]}</div>'
        )

    html = (
        '<div style="background:rgba(30,41,59,0.3);backdrop-filter:blur(8px);'
        'border:1px solid rgba(56,189,248,0.1);border-radius:12px;padding:1rem;margin-top:1rem;">'
        '<div style="font-size:0.85rem;font-weight:600;color:#38BDF8;margin-bottom:0.6rem;">'
        '🧠 АВТОМАТИЧЕСКИЕ ИНСАЙТЫ</div>'
        f'{items_html}</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def _render_ranking_tab(data: dict[str, Any]):
    """Вкладка рейтинга: Top-5 и Bottom-5 вопросов."""
    rankings = be.get_top_bottom_questions(data, n=5)

    top_df = rankings.get("top", pd.DataFrame())
    bottom_df = rankings.get("bottom", pd.DataFrame())

    if top_df.empty and bottom_df.empty:
        st.info("Нет данных для построения рейтинга")
        return

    def _build_card_html(df, title, title_color, score_color):
        """Строит HTML-карточку рейтинга без отступов."""
        bg = "rgba(52,211,153,0.08)" if score_color == "#34D399" else "rgba(225,29,72,0.06)"
        border = "rgba(52,211,153,0.2)" if score_color == "#34D399" else "rgba(225,29,72,0.2)"

        rows_html = ""
        for _, row in df.iterrows():
            delta_html = ""
            if pd.notna(row.get("Δ")):
                d = row["Δ"]
                dc = "#34D399" if d >= 0 else "#E11D48"
                arrow = "▲" if d > 0 else "▼" if d < 0 else "●"
                delta_html = f' <span style="color:{dc};font-size:0.75rem;">{arrow}{abs(d)}</span>'

            rows_html += (
                f'<div style="padding:0.5rem 0;border-bottom:1px solid rgba(148,163,184,0.1);">'
                f'<span style="color:#94A3B8;font-size:0.7rem;">{row["Отдел"]}</span><br>'
                f'<span style="color:#F8FAFC;font-size:0.85rem;">{row["Вопрос"]}</span>'
                f'<span style="float:right;color:{score_color};font-weight:700;font-size:1.1rem;">{row["Средняя"]}{delta_html}</span>'
                f'</div>'
            )

        return (
            f'<div style="background:{bg};border:1px solid {border};border-radius:12px;padding:1rem;">'
            f'<div style="font-size:1rem;font-weight:700;color:{title_color};margin-bottom:0.5rem;">{title}</div>'
            f'{rows_html}</div>'
        )

    col1, col2 = st.columns(2)

    with col1:
        if not top_df.empty:
            html = _build_card_html(top_df, "🏆 TOP-5 лучших показателей", "#34D399", "#34D399")
            st.markdown(html, unsafe_allow_html=True)

    with col2:
        if not bottom_df.empty:
            html = _build_card_html(bottom_df, "⚠️ BOTTOM-5 требуют внимания", "#E11D48", "#E11D48")
            st.markdown(html, unsafe_allow_html=True)

    # Горизонтальный bar chart
    all_q = pd.concat([top_df.assign(_type="top"), bottom_df.assign(_type="bottom")])
    if not all_q.empty:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=all_q["Вопрос"],
            x=all_q["Средняя"],
            orientation='h',
            marker_color=["#34D399" if t == "top" else "#E11D48" for t in all_q["_type"]],
            text=all_q["Средняя"].apply(lambda x: f"{x:.2f}"),
            textposition='outside',
            textfont=dict(color='#F8FAFC', size=10),
            hovertemplate='<b>%{y}</b><br>Балл: %{x:.2f}<extra></extra>',
        ))
        fig.update_layout(
            height=max(350, len(all_q) * 38 + 60),
            margin=dict(l=20, r=50, t=30, b=20),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(
                range=[3.5, 5.2], tickfont=dict(color='#94A3B8'),
                gridcolor='rgba(148, 163, 184, 0.1)', showgrid=True,
            ),
            yaxis=dict(
                tickfont=dict(color='#F8FAFC', size=9), showgrid=False,
                autorange="reversed",
            ),
            title=dict(text="Рейтинг показателей", font=dict(size=14, color='#94A3B8'), x=0.5),
        )
        st.plotly_chart(fig, use_container_width=True, key="ranking_bar")


def _render_nps_tab(data: dict[str, Any]):
    """Вкладка с динамикой NPS — area chart с целевой линией."""
    nps_df = data.get("nps", pd.DataFrame())

    if nps_df.empty:
        st.info("Нет данных NPS для отображения")
        return

    # Создаём area chart
    fig = px.area(
        nps_df,
        x="Месяц",
        y="NPS",
        title=None,
        labels={"NPS": "Индекс NPS", "Месяц": ""},
        template="plotly_dark",
    )

    # Настройка заливки под линией
    fig.update_traces(
        fill='tozeroy',
        fillcolor='rgba(56, 189, 248, 0.2)',
        line=dict(color='#38BDF8', width=3),
        mode='lines+markers',
        marker=dict(size=8, color='#38BDF8', line=dict(width=2, color='#0F172A')),
        hovertemplate='<b>%{x}</b><br>NPS: %{y:.1f}<extra></extra>'
    )

    # Целевая линия на уровне 80%
    fig.add_hline(
        y=80,
        line_dash="dash",
        line_color="#34D399",
        line_width=2,
        annotation_text="Целевой показатель 80%",
        annotation_position="top right",
        annotation_font_color="#34D399",
        annotation_font_size=12,
    )

    # Дополнительные линии для промоутеров/детракторов если есть
    if "Промоутеры" in nps_df.columns:
        fig.add_scatter(
            x=nps_df["Месяц"],
            y=nps_df["Промоутеры"],
            mode='lines+markers',
            name='Промоутеры',
            line=dict(color='#34D399', width=2),
            marker=dict(size=6),
            hovertemplate='<b>%{x}</b><br>Промоутеры: %{y:.1f}%<extra></extra>'
        )
    if "Детракторы" in nps_df.columns:
        fig.add_scatter(
            x=nps_df["Месяц"],
            y=nps_df["Детракторы"],
            mode='lines+markers',
            name='Детракторы',
            line=dict(color='#E11D48', width=2),
            marker=dict(size=6),
            hovertemplate='<b>%{x}</b><br>Детракторы: %{y:.1f}%<extra></extra>'
        )

    fig.update_layout(
        height=500,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color='#94A3B8')
        ),
        xaxis=dict(
            gridcolor='rgba(148, 163, 184, 0.1)',
            tickfont=dict(color='#94A3B8'),
            showgrid=True,
        ),
        yaxis=dict(
            gridcolor='rgba(148, 163, 184, 0.1)',
            tickfont=dict(color='#94A3B8'),
            showgrid=True,
            zeroline=False,
        ),
        hovermode='x unified',
    )

    st.plotly_chart(fig, use_container_width=True, key="nps_chart")


def _render_radar_tab(data: dict[str, Any]):
    """Вкладка с радаром качества — radar chart по отделам с сравнением периодов."""
    months = be.get_available_months(data)

    if not months:
        st.info("Нет данных по отделам для построения радара")
        return

    # Два селектора: основной месяц и опциональный для сравнения
    col_sel1, col_sel2 = st.columns(2)
    with col_sel1:
        selected_month = st.selectbox(
            "Период 1 (основной)",
            options=months,
            index=len(months) - 1,
            key="radar_month_1"
        )
    with col_sel2:
        compare_options = ["— не сравнивать —"] + months
        compare_month = st.selectbox(
            "Период 2 (для сравнения)",
            options=compare_options,
            index=0,
            key="radar_month_2"
        )

    radar_df = be.get_radar_data(data, selected_month)
    if radar_df.empty:
        st.info("Нет данных за выбранный период")
        return

    categories = radar_df["Отдел"].tolist()
    values = radar_df["Средняя оценка"].tolist()
    categories_closed = categories + [categories[0]]
    values_closed = values + [values[0]]

    fig = go.Figure()

    # Основной период
    fig.add_trace(go.Scatterpolar(
        r=values_closed,
        theta=categories_closed,
        fill='toself',
        fillcolor='rgba(52, 211, 153, 0.25)',
        line=dict(color='#34D399', width=2.5),
        marker=dict(size=8, color='#34D399', line=dict(width=2, color='#0F172A')),
        name=selected_month,
        hovertemplate='<b>%{theta}</b><br>Оценка: %{r:.2f}<extra></extra>'
    ))

    # Если выбран второй период — накладываем
    compare_active = compare_month != "— не сравнивать —"
    if compare_active:
        radar_df2 = be.get_radar_data(data, compare_month)
        if not radar_df2.empty:
            values2 = []
            for dept in categories:
                row = radar_df2[radar_df2["Отдел"] == dept]
                values2.append(row["Средняя оценка"].iloc[0] if not row.empty else 0)
            values2_closed = values2 + [values2[0]]

            fig.add_trace(go.Scatterpolar(
                r=values2_closed,
                theta=categories_closed,
                fill='toself',
                fillcolor='rgba(56, 189, 248, 0.15)',
                line=dict(color='#38BDF8', width=2, dash='dash'),
                marker=dict(size=6, color='#38BDF8'),
                name=compare_month,
                hovertemplate='<b>%{theta}</b><br>Оценка: %{r:.2f}<extra></extra>'
            ))

    fig.update_layout(
        polar=dict(
            bgcolor='rgba(30, 41, 59, 0.3)',
            radialaxis=dict(
                visible=True, range=[0, 5.5],
                gridcolor='rgba(148, 163, 184, 0.15)',
                tickfont=dict(color='#94A3B8', size=10),
            ),
            angularaxis=dict(
                tickfont=dict(color='#F8FAFC', size=11),
                linecolor='rgba(148, 163, 184, 0.2)',
                gridcolor='rgba(148, 163, 184, 0.15)',
            ),
        ),
        showlegend=compare_active,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5,
            font=dict(color='#F8FAFC', size=12),
            bgcolor='rgba(30, 41, 59, 0.5)',
            bordercolor='rgba(56, 189, 248, 0.2)', borderwidth=1,
        ),
        height=550,
        margin=dict(l=80, r=80, t=40, b=40),
        paper_bgcolor='rgba(0,0,0,0)',
        title=dict(
            text=f"Радар качества — {selected_month}" + (f" vs {compare_month}" if compare_active else ""),
            font=dict(size=16, color='#F8FAFC'), x=0.5,
        ),
    )

    st.plotly_chart(
        fig, 
        use_container_width=True, 
        key="radar_chart"
    )

    # Таблица сравнения под радаром
    if compare_active:
        comp_df = be.compare_periods(data, selected_month, compare_month)
        if not comp_df.empty:
            with st.expander("📊 Таблица сравнения периодов"):
                st.dataframe(comp_df, use_container_width=True, hide_index=True)
    else:
        with st.expander("📋 Данные радара"):
            st.dataframe(
                radar_df.sort_values("Средняя оценка", ascending=False),
                use_container_width=True, hide_index=True,
            )


def _render_heatmap_tab(data: dict[str, Any]):
    """Вкладка с тепловой матрицей оценок — с фильтрами по периодам и отделам."""
    heatmap_df = be.get_heatmap_data(data)

    if heatmap_df.empty:
        st.info("Нет данных для построения тепловой карты")
        return

    # --- Фильтры ---
    all_periods = heatmap_df.columns.tolist()
    all_categories = heatmap_df.index.tolist()

    # Извлекаем уникальные отделы из индекса "Отдел | Вопрос"
    all_depts = sorted(set(cat.split(" | ")[0] for cat in all_categories if " | " in cat))

    col_f1, col_f2 = st.columns([3, 3])
    with col_f1:
        selected_periods = st.multiselect(
            "📅 Периоды",
            options=all_periods,
            default=all_periods,
            key="hm_periods",
        )
    with col_f2:
        selected_depts = st.multiselect(
            "🏢 Направления (отделы)",
            options=all_depts,
            default=all_depts,
            key="hm_depts",
        )

    if not selected_periods:
        st.warning("Выберите хотя бы один период")
        return
    if not selected_depts:
        st.warning("Выберите хотя бы одно направление")
        return

    # Фильтруем данные
    filtered_df = heatmap_df[selected_periods]
    mask = filtered_df.index.map(lambda cat: any(cat.startswith(d + " |") or cat == d for d in selected_depts))
    filtered_df = filtered_df[mask]

    if filtered_df.empty:
        st.info("Нет данных для выбранных фильтров")
        return

    # Создаём heatmap
    fig = px.imshow(
        filtered_df.values,
        x=filtered_df.columns.tolist(),
        y=filtered_df.index.tolist(),
        color_continuous_scale=[
            [0.0, "#E55B4B"],  # Красный
            [0.2, "#F29D4B"],  # Оранжевый
            [0.4, "#D1BA70"],  # Желто-оливковый
            [0.6, "#98C895"],  # Бледно-зелёный
            [0.8, "#5BA780"],  # Бирюзовый
            [1.0, "#428B6B"],  # Тёмно-бирюзовый
        ],
        aspect="auto",
        labels=dict(x="Период", y="Отдел | Вопрос", color="Оценка"),
    )

    fig.update_traces(
        text=filtered_df.values,
        texttemplate="%{text:.2f}",
        textfont=dict(size=10, color='white'),
        hoverongaps=False,
        hovertemplate='<b>%{y}</b><br>Период: %{x}<br>Оценка: %{z:.2f}<extra></extra>',
        xgap=2,
        ygap=2,
    )

    fig.update_layout(
        height=max(400, len(filtered_df) * 40 + 120),
        margin=dict(l=20, r=20, t=60, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(
            tickfont=dict(color='#94A3B8', size=11),
            showgrid=False,
        ),
        yaxis=dict(
            tickfont=dict(color='#F8FAFC', size=10),
            showgrid=False,
            autorange="reversed",
        ),
        coloraxis_colorbar=dict(
            title=dict(text="Оценка", font=dict(color='#94A3B8')),
            tickfont=dict(color='#94A3B8'),
            thickness=15,
            len=0.8,
            outlinecolor='rgba(148, 163, 184, 0.2)',
            outlinewidth=1,
        ),
    )

    st.plotly_chart(fig, use_container_width=True, key="heatmap_chart")


def _render_compare_tab(data: dict[str, Any]):
    """Вкладка сравнения двух периодов — grouped bar chart + таблица с дельтами."""
    months = be.get_available_months(data)

    if len(months) < 2:
        st.info("Нужно минимум 2 периода для сравнения")
        return

    # Селекторы периодов
    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        period_a = st.selectbox("Период A", options=months, index=max(0, len(months) - 2), key="cmp_a")
    with col2:
        period_b = st.selectbox("Период B", options=months, index=len(months) - 1, key="cmp_b")
    with col3:
        departments = be.get_available_departments(data)
        dept_options = ["Все отделы"] + departments
        sel_dept = st.selectbox("Фильтр по отделу", options=dept_options, key="cmp_dept")

    if period_a == period_b:
        st.warning("Выберите разные периоды для сравнения")
        return

    dept_filter = None if sel_dept == "Все отделы" else sel_dept

    # --- Сравнение по отделам (grouped bar) ---
    comp_dept = be.compare_periods(data, period_a, period_b)

    if not comp_dept.empty:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=comp_dept["Отдел"], y=comp_dept[period_a],
            name=period_a, marker_color='#34D399',
            text=comp_dept[period_a].apply(lambda x: f"{x:.2f}" if pd.notna(x) else ""),
            textposition='outside', textfont=dict(color='#34D399', size=11),
            hovertemplate='<b>%{x}</b><br>' + period_a + ': %{y:.2f}<extra></extra>',
        ))
        fig.add_trace(go.Bar(
            x=comp_dept["Отдел"], y=comp_dept[period_b],
            name=period_b, marker_color='#38BDF8',
            text=comp_dept[period_b].apply(lambda x: f"{x:.2f}" if pd.notna(x) else ""),
            textposition='outside', textfont=dict(color='#38BDF8', size=11),
            hovertemplate='<b>%{x}</b><br>' + period_b + ': %{y:.2f}<extra></extra>',
        ))
        fig.update_layout(
            barmode='group', height=420,
            margin=dict(l=20, r=20, t=50, b=20),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5,
                font=dict(color='#F8FAFC', size=12),
                bgcolor='rgba(30, 41, 59, 0.5)',
            ),
            xaxis=dict(tickfont=dict(color='#F8FAFC', size=12), showgrid=False),
            yaxis=dict(
                tickfont=dict(color='#94A3B8'), showgrid=True,
                gridcolor='rgba(148, 163, 184, 0.1)', range=[0, 5.5],
            ),
            title=dict(
                text=f"Сравнение: {period_a} → {period_b}",
                font=dict(size=16, color='#F8FAFC'), x=0.5,
            ),
        )
        st.plotly_chart(fig, use_container_width=True, key="compare_bar")

    # --- Таблица дельт по вопросам ---
    comp_q = be.compare_periods_by_question(data, period_a, period_b, dept_filter)

    if not comp_q.empty:
        st.markdown(f"""
        <div style="margin: 1rem 0 0.5rem 0; font-size: 1rem; font-weight: 600; color: #F8FAFC;">
            📋 Детальное сравнение по вопросам
            <span style="font-size: 0.8rem; color: #94A3B8; font-weight: 400;">
                 — {sel_dept} | {period_a} → {period_b}
            </span>
        </div>
        """, unsafe_allow_html=True)

        # Рисуем горизонтальный bar chart для дельт
        comp_q_clean = comp_q.dropna(subset=["Δ"])
        if not comp_q_clean.empty:
            labels = comp_q_clean["Вопрос"].str[:45].tolist()
            deltas = comp_q_clean["Δ"].tolist()
            colors = ["#34D399" if d >= 0 else "#E11D48" for d in deltas]

            fig_delta = go.Figure()
            fig_delta.add_trace(go.Bar(
                y=labels, x=deltas, orientation='h',
                marker_color=colors,
                text=[f"{d:+.2f}" for d in deltas],
                textposition='outside', textfont=dict(color='#F8FAFC', size=10),
                hovertemplate='<b>%{y}</b><br>Δ: %{x:+.2f}<extra></extra>',
            ))
            fig_delta.update_layout(
                height=max(300, len(labels) * 32 + 80),
                margin=dict(l=20, r=60, t=30, b=20),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(
                    tickfont=dict(color='#94A3B8'), showgrid=True,
                    gridcolor='rgba(148, 163, 184, 0.1)', zeroline=True,
                    zerolinecolor='rgba(248, 250, 252, 0.3)', zerolinewidth=2,
                    title=dict(text="Изменение оценки", font=dict(color='#94A3B8', size=11)),
                ),
                yaxis=dict(
                    tickfont=dict(color='#F8FAFC', size=10), showgrid=False,
                    autorange="reversed",
                ),
                title=dict(
                    text="Дельта оценок (что улучшилось / ухудшилось)",
                    font=dict(size=13, color='#94A3B8'), x=0.5,
                ),
            )
            st.plotly_chart(fig_delta, use_container_width=True, key="compare_delta_bar")

        # Таблица
        with st.expander("📊 Полная таблица сравнения"):
            st.dataframe(comp_q, use_container_width=True, hide_index=True)


def _render_drilldown_tab(data: dict[str, Any]):
    """Вкладка с drill-down по отделам — bar chart + trend line + table."""
    departments = be.get_available_departments(data)

    if not departments:
        st.info("Нет данных по отделам")
        return

    # Выбор отдела
    selected_dept = st.selectbox(
        "Выберите отдел для детализации",
        options=departments,
        key="drill_dept"
    )

    # Данные для графика
    drill_df = be.get_drilldown_data(data, selected_dept)

    if drill_df.empty:
        st.info(f"Нет данных для отдела «{selected_dept}»")
        return

    # Bar chart + trend line
    fig = go.Figure()

    # Столбцы
    fig.add_trace(go.Bar(
        x=drill_df["Период_Краткий"],
        y=drill_df["Средняя_оценка"],
        name="Средняя оценка",
        marker=dict(
            color=drill_df["Средняя_оценка"],
            colorscale=[[0, "#E11D48"], [0.5, "#F59E0B"], [1, "#34D399"]],
            line=dict(width=1, color='rgba(15, 23, 42, 0.5)'),
            cornerradius=6,
        ),
        text=drill_df["Средняя_оценка"].apply(lambda x: f"{x:.2f}"),
        textposition='outside',
        textfont=dict(color='#F8FAFC', size=11),
        hovertemplate='<b>%{x}</b><br>Оценка: %{y:.2f}<extra></extra>',
    ))

    # Сглаженная линия тренда
    if len(drill_df) >= 2:
        fig.add_trace(go.Scatter(
            x=drill_df["Период_Краткий"],
            y=drill_df["Средняя_оценка"],
            mode='lines',
            name='Тренд',
            line=dict(color='#38BDF8', width=3, shape='spline', smoothing=1.3),
            marker=dict(size=0),
            hovertemplate='<b>%{x}</b><br>Тренд: %{y:.2f}<extra></extra>',
        ))

    fig.update_layout(
        height=450,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color='#94A3B8'),
        ),
        xaxis=dict(
            gridcolor='rgba(148, 163, 184, 0.1)',
            tickfont=dict(color='#94A3B8'),
            showgrid=False,
        ),
        yaxis=dict(
            gridcolor='rgba(148, 163, 184, 0.1)',
            tickfont=dict(color='#94A3B8'),
            showgrid=True,
            range=[0, 5.5],
            zeroline=False,
        ),
        hovermode='x unified',
        title=dict(
            text=f"Динамика оценок — {selected_dept}",
            font=dict(size=16, color='#F8FAFC'),
            x=0.5,
        ),
    )

    st.plotly_chart(fig, use_container_width=True, key="drill_chart")

    # Таблица с детализацией по вопросам
    st.markdown("<br>", unsafe_allow_html=True)
    breakdown_df = be.get_question_breakdown(data, selected_dept)

    if not breakdown_df.empty:
        st.markdown(f"**Детализация по вопросам — {selected_dept}**")

        # Форматируем таблицу с цветовой подсветкой
        def color_score(val):
            if val >= 4.5:
                return 'background-color: rgba(52, 211, 153, 0.3); color: #34D399; font-weight: 600'
            elif val >= 3.5:
                return 'background-color: rgba(245, 158, 11, 0.2); color: #F59E0B'
            else:
                return 'background-color: rgba(225, 29, 72, 0.2); color: #E11D48; font-weight: 600'

        styled_df = breakdown_df.style\
            .map(color_score, subset=["Средняя оценка"])\
            .set_properties(**{'text-align': 'left'})\
            .set_table_styles([
                {'selector': 'th', 'props': [
                    ('background-color', 'rgba(30, 41, 59, 0.8)'),
                    ('color', '#38BDF8'),
                    ('font-weight', '600'),
                    ('padding', '0.5rem'),
                ]},
                {'selector': 'td', 'props': [
                    ('padding', '0.5rem'),
                    ('border-bottom', '1px solid rgba(148, 163, 184, 0.1)'),
                ]},
            ])

        st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True,
            height=min(400, len(breakdown_df) * 40 + 50),
            column_config={
                "Вопрос": st.column_config.TextColumn("Вопрос", width="large"),
                "Средняя оценка": st.column_config.NumberColumn("Средняя оценка", format="%.2f"),
            }
        )




# ---------------------------------------------------------------------------
# Заголовок дашборда
# ---------------------------------------------------------------------------

st.markdown("<h1 class='gradient-title'>ГОЛОС ГОСТЯ</h1>", unsafe_allow_html=True)
st.markdown("<p class='subtitle'>Аналитическая система мониторинга качества сервиса</p>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Основной контент
# ---------------------------------------------------------------------------

if st.session_state.data is None:
    # Приветственный экран
    _show_welcome()
else:
    # Отображаем дашборд
    _render_dashboard(st.session_state.data)
