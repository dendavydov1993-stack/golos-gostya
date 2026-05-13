"""
backend.py — Слой бизнес-логики аналитической системы «Голос Гостя».

Модуль отвечает за:
  • Чтение и кэширование файлов .xlsx / .csv
  • Эвристический парсинг листов (NPS, отделы)
  • Агрегацию и стандартизацию данных
  • Генерацию PDF-отчётов через fpdf2 + kaleido
"""

from __future__ import annotations

import io
import os
import re
import base64
from typing import Any
from datetime import datetime
from functools import lru_cache

import matplotlib
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from fpdf import FPDF

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

# Ожидаемые листы в Excel-файле
EXPECTED_SHEETS = ["NPS", "СПИР", "Горничные", "Питание", "Мед.часть", "Столовая"]

# Премиальная цветовая палитра для тёмной темы
COLORS_PREMIUM = {
    "sky": "#38BDF8",
    "emerald": "#34D399",
    "ruby": "#E11D48",
    "amber": "#F59E0B",
    "emerald_dark": "#059669",
    "slate_50": "#F8FAFC",
    "slate_100": "#F1F5F9",
    "slate_200": "#E2E8F0",
    "slate_300": "#CBD5E1",
    "slate_400": "#94A3B8",
    "slate_500": "#64748B",
    "slate_600": "#475569",
    "slate_700": "#334155",
    "slate_800": "#1E293B",
    "slate_900": "#0F172A",
}

# Цвета для отделов (для радара и других визуализаций)
DEPT_COLORS = [
    "#38BDF8", "#34D399", "#F59E0B", "#E11D48",
    "#A78BFA", "#F472B6", "#2DD4BF", "#FB923C"
]

# Путь к шрифту DejaVuSans для PDF (локально из matplotlib)
MATPLOTLIB_FONT_PATH = os.path.join(
    os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf", "DejaVuSans.ttf"
)


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

def _clean_question(text: str) -> str:
    """
    Удаляет вводные слова из текста вопроса, делая его лаконичным.
    Примеры: "Как Вы оцените качество обслуживания?" → "Качество обслуживания"
    """
    if pd.isna(text):
        return ""
    text = str(text).strip()
    # Удаляем вводные конструкции
    patterns = [
        r"^(Как\s+Вы\s+оцените\s+)",
        r"^(Оцените\s+)",
        r"^(Пожалуйста,\s+оцените\s+)",
        r"^(Насколько\s+Вы\s+довольны\s+)",
        r"^(Каково\s+Ваше\s+мнение\s+о\s+)",
        r"^(Расскажите,\s+как\s+Вы\s+оцениваете\s+)",
    ]
    for pat in patterns:
        text = re.sub(pat, "", text, flags=re.IGNORECASE)
    # Удаляем вопросительный знак в конце
    text = text.rstrip("?").strip()
    # Делаем первую букву заглавной
    if text:
        text = text[0].upper() + text[1:]
    return text


def _safe_float(val: Any) -> float | None:
    """Безопасно преобразует строку (даже с запятыми или %) в число."""
    if pd.isna(val) or str(val).strip() == "":
        return None
    try:
        s = str(val).replace(',', '.').strip()
        # Извлекаем только числовые символы (цифры, точка, минус)
        s = re.sub(r'[^\d\.\-]', '', s)
        return float(s) if s else None
    except ValueError:
        return None


def _standardize_column_name(col: Any) -> str:
    """Приводит название колонки к строковому представлению."""
    if isinstance(col, datetime):
        return col.strftime("%Y-%m")
    return str(col).strip()


def _parse_month_label(col: str) -> str:
    """Преобразует название колонки с датой в короткий формат 'Июн \'24'."""
    col_str = str(col).strip()
    month_names = {
        1: "Янв", 2: "Фев", 3: "Мар", 4: "Апр", 5: "Май", 6: "Июн",
        7: "Июл", 8: "Авг", 9: "Сен", 10: "Окт", 11: "Ноя", 12: "Дек"
    }
    # Формат YYYY-MM (например "2024-06")
    ym_match = re.search(r"(20\d{2})[-/.](0[1-9]|1[0-2])\b", col_str)
    if ym_match:
        year = ym_match.group(1)[2:]
        month = int(ym_match.group(2))
        return f"{month_names.get(month, month)} \'{year}"
    # Формат MM.YYYY или MM/YYYY (например "06.2024")
    my_match = re.search(r"\b(0[1-9]|1[0-2])[-/.](20\d{2})", col_str)
    if my_match:
        year = my_match.group(2)[2:]
        month = int(my_match.group(1))
        return f"{month_names.get(month, month)} \'{year}"
    # Если уже текстовый формат с названием месяца
    for num, name in month_names.items():
        if name.lower() in col_str.lower():
            year_match = re.search(r"(20\d{2})", col_str)
            year = year_match.group(1)[2:] if year_match else ""
            return f"{name} \'{year}" if year else name
    # Fallback: возвращаем обрезанную строку
    return col_str[:10]


def _month_sort_key(label: str) -> tuple:
    """Ключ для сортировки месяцев в хронологическом порядке."""
    month_map = {
        "Янв": 1, "Фев": 2, "Мар": 3, "Апр": 4, "Май": 5, "Июн": 6,
        "Июл": 7, "Авг": 8, "Сен": 9, "Окт": 10, "Ноя": 11, "Дек": 12
    }
    for abbr, num in month_map.items():
        if abbr in label:
            # Извлекаем год
            year_match = re.search(r"'(\d{2})", label)
            year = int(year_match.group(1)) if year_match else 0
            return (year, num)
    return (0, 0)


# ---------------------------------------------------------------------------
# Чтение файлов
# ---------------------------------------------------------------------------

# Названия месяцев (для фильтрации листов-месяцев)
_MONTH_NAMES_FULL = {
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
}

# Листы, которые всегда нужно игнорировать как «не-отделы»
_SKIP_SHEETS = {
    "nps", "nps2", "количество гостей", "отчет по моб.прил",
    "отчет моб.прил столовая",
}

# Известные листы-отделы (приоритетные)
_KNOWN_DEPTS = {"спир", "горничные", "питание", "мед.часть", "столовая", "кмр"}


@st.cache_data(show_spinner=False)
def read_file(uploaded_file) -> dict[str, pd.DataFrame] | None:
    """Читает загруженный файл и возвращает словарь {лист: DataFrame}."""
    if uploaded_file is None:
        return None
    try:
        file_name = uploaded_file.name.lower()
        if file_name.endswith((".xlsx", ".xls")):
            xls = pd.ExcelFile(uploaded_file)
            return {
                name: pd.read_excel(xls, sheet_name=name, header=None)
                for name in xls.sheet_names
            }
        elif file_name.endswith(".csv"):
            return {"data": pd.read_csv(uploaded_file)}
        else:
            st.error("Неподдерживаемый формат файла. Загрузите .xlsx или .csv")
            return None
    except Exception as e:
        st.error(f"Ошибка чтения файла: {e}")
        return None


# ---------------------------------------------------------------------------
# Парсинг NPS (из листа NPS2 или вычисление из NPS)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def parse_nps_from_nps2(df: pd.DataFrame) -> pd.DataFrame:
    """
    Парсит лист NPS2, который содержит % рекомендации и % возврата по месяцам.
    Строка 3 = «Порекомендуете ли Вы…» — это и есть наш «Промоутеры %».
    NPS ≈ Промоутеры% × 100 (упрощённая метрика лояльности).
    """
    if df is None or df.empty:
        return pd.DataFrame()

    # Строка 0 — заголовки месяцев
    headers = df.iloc[0]

    # Ищем строку с «Порекомендуете» (обычно строка 3)
    recommend_row = None
    revisit_row = None
    for i, row in df.iterrows():
        text = str(row.iloc[0]).lower() if pd.notna(row.iloc[0]) else ""
        if "порекоменд" in text:
            recommend_row = i
        elif "выбер" in text:
            revisit_row = i

    if recommend_row is None:
        return pd.DataFrame()

    result_data = []
    for c in range(1, len(df.columns)):
        month_name = headers.iloc[c] if pd.notna(headers.iloc[c]) else None
        if month_name is None or str(month_name).strip() == "":
            continue
        month_str = str(month_name).strip()
        # Пропускаем итоговые столбцы и годовые
        if re.match(r"^\d{4}", month_str):
            continue

        promo_val = _safe_float(df.iloc[recommend_row, c])
        revisit_val = _safe_float(df.iloc[revisit_row, c]) if revisit_row is not None else None

        if promo_val is not None:
            # Если значение < 1, это доля — переводим в проценты
            if promo_val <= 1:
                promo_pct = round(promo_val * 100, 1)
            else:
                promo_pct = promo_val

            revisit_pct = None
            if revisit_val is not None:
                revisit_pct = round(revisit_val * 100, 1) if revisit_val <= 1 else revisit_val

            result_data.append({
                "Месяц": month_str,
                "NPS": promo_pct,
                "Промоутеры": promo_pct,
                "Нейтралы": None,
                "Детракторы": round(100 - promo_pct, 1) if promo_pct else None,
                "Возврат": revisit_pct,
            })

    return pd.DataFrame(result_data) if result_data else pd.DataFrame()


@st.cache_data(show_spinner=False)
def parse_nps_from_raw(df: pd.DataFrame) -> pd.DataFrame:
    """
    Парсит «сырой» лист NPS: ищет строку «Порекомендуете ли Вы…»,
    берёт колонки-месяцы (чётные: количество, нечётные: доля).
    Вычисляет NPS = доля «Да» × 100.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    # Ищем строку с «Порекомендуете»
    rec_idx = None
    for i, row in df.iterrows():
        text = str(row.iloc[0]).lower() if pd.notna(row.iloc[0]) else ""
        if "порекоменд" in text:
            rec_idx = i
            break
    if rec_idx is None:
        return pd.DataFrame()

    # Строка 0 — заголовки: "Вопросы", "Варианты ответов", "Январь", NaN, "Февраль", NaN...
    headers = df.iloc[0]

    # Собираем колонки-месяцы: каждый чётный индекс (2,4,6...) = количество,
    # следующий нечётный (3,5,7...) = доля
    result_data = []
    c = 2  # Начинаем с 3-й колонки (индекс 2)
    while c < len(df.columns):
        month_name = headers.iloc[c] if pd.notna(headers.iloc[c]) else None
        if month_name is None:
            c += 2
            continue
        month_str = str(month_name).strip()
        if "итого" in month_str.lower():
            c += 2
            continue

        # Доля «Да» — в следующей колонке (c+1)
        pct_col = c + 1 if (c + 1) < len(df.columns) else c
        promo_val = _safe_float(df.iloc[rec_idx, pct_col])

        if promo_val is not None:
            promo_pct = round(promo_val * 100, 1) if promo_val <= 1 else promo_val
            result_data.append({
                "Месяц": month_str,
                "NPS": promo_pct,
                "Промоутеры": promo_pct,
                "Нейтралы": None,
                "Детракторы": round(100 - promo_pct, 1),
            })
        c += 2

    return pd.DataFrame(result_data) if result_data else pd.DataFrame()


# ---------------------------------------------------------------------------
# Парсинг листов отделов
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def parse_department_sheet(df: pd.DataFrame, dept_name: str) -> pd.DataFrame:
    """
    Парсит лист отдела (СПИР, Горничные, Питание, Мед.часть, КМР).
    Строка 0 — месяцы (Январь, Февраль, …). Строки 1+ — вопрос + оценки.
    Возвращает melted DataFrame: [Отдел, Вопрос, Период, Оценка, Период_Краткий].
    """
    if df is None or df.empty:
        return pd.DataFrame()

    # Ищем строку заголовков (где есть названия месяцев или даты)
    header_row = None
    for i, row in df.iterrows():
        row_text = " ".join(str(x) for x in row if pd.notna(x))
        if re.search(r"(20\d{2}|Янв|Фев|Мар|Апр|Май|Июн|Июл|Авг|Сен|Окт|Ноя|Дек)", row_text, re.IGNORECASE):
            header_row = i
            break

    if header_row is None:
        header_row = 0

    # Устанавливаем заголовки
    df.columns = df.iloc[header_row]
    df = df.iloc[header_row + 1:].reset_index(drop=True)

    # Переименовываем первую колонку
    cols = list(df.columns)
    cols[0] = "Вопрос"
    df.columns = cols

    # Месячные колонки — все кроме первой, которые не пустые
    month_cols = [c for c in df.columns[1:] if pd.notna(c) and str(c).strip()]

    # Удаляем строки без вопроса
    df = df.dropna(subset=["Вопрос"]).copy()

    # Фильтруем строки «Всего» (они есть в сводном листе «2025»)
    df = df[~df["Вопрос"].astype(str).str.strip().str.lower().isin(["всего", "всего:"])].copy()

    if df.empty:
        return pd.DataFrame()

    # Чистим текст вопросов
    df["Вопрос"] = df["Вопрос"].apply(_clean_question)
    df["Отдел"] = dept_name

    keep_cols = ["Отдел", "Вопрос"] + month_cols
    keep_cols = [c for c in keep_cols if c in df.columns]
    df = df[keep_cols]

    value_vars = [c for c in month_cols if c in df.columns]
    if not value_vars:
        return pd.DataFrame()

    melted = pd.melt(df, id_vars=["Отдел", "Вопрос"], value_vars=value_vars,
                     var_name="Период", value_name="Оценка")
    melted["Оценка"] = melted["Оценка"].apply(_safe_float)
    melted["Период_Краткий"] = melted["Период"].apply(_parse_month_label)
    melted = melted.dropna(subset=["Оценка"])

    if melted.empty:
        return pd.DataFrame()

    # Фильтр: оценки качества обычно 1–5. Если max > 10 — это не лист оценок.
    if melted["Оценка"].max() > 10:
        return pd.DataFrame()

    return melted.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def parse_summary_sheet(df: pd.DataFrame) -> pd.DataFrame:
    """
    Парсит сводный лист (например, «2025»): чередование строк
    «Вопрос» (без оценок) → «Всего» (с оценками по месяцам).
    """
    if df is None or df.empty:
        return pd.DataFrame()

    # Строка 0 — даты-месяцы
    headers = df.iloc[0]
    month_cols_map = {}  # col_index -> month_label
    for c in range(1, len(df.columns)):
        val = headers.iloc[c]
        if pd.notna(val):
            s = str(val).strip()
            # Обработка datetime объектов
            if hasattr(val, 'strftime'):
                s = val.strftime("%Y-%m")
            month_cols_map[c] = _parse_month_label(s)

    if not month_cols_map:
        return pd.DataFrame()

    # Проходим по строкам: вопрос, затем «Всего» с оценками
    result_data = []
    current_question = None
    for i in range(1, len(df)):
        col0 = df.iloc[i, 0]
        col0_str = str(col0).strip() if pd.notna(col0) else ""

        if col0_str.lower() in ("всего", "всего:"):
            if current_question:
                for c_idx, month_label in month_cols_map.items():
                    if c_idx < len(df.columns):
                        score = _safe_float(df.iloc[i, c_idx])
                        if score is not None and 1.0 <= score <= 5.0:
                            result_data.append({
                                "Вопрос": _clean_question(current_question),
                                "Период_Краткий": month_label,
                                "Оценка": score,
                            })
            current_question = None
        elif col0_str and col0_str.lower() not in ("nan",):
            # Пропускаем вопросы типа «Вы впервые…» (без числовых ответов)
            current_question = col0_str

    if not result_data:
        return pd.DataFrame()

    melted = pd.DataFrame(result_data)

    # Назначаем отделы по вопросам эвристически
    def _assign_dept(q: str) -> str:
        q_low = q.lower()
        if any(w in q_low for w in ["заезд", "выезд", "приветлив", "регистр", "владен"]):
            return "СПИР"
        if any(w in q_low for w in ["уборк", "оборуд", "прибор", "мебел", "своевремен", "расход"]):
            return "Горничные"
        if any(w in q_low for w in ["столов", "приготовл", "ассортимент", "блюд", "обслуж"]):
            return "Питание"
        if any(w in q_low for w in ["медицин", "врач", "лечебн", "процедур", "квалифиц", "грамот", "вежлив", "доброжел"]):
            return "Мед.часть"
        if any(w in q_low for w in ["культур", "досуг", "массов"]):
            return "КМР"
        return "Прочее"

    melted["Отдел"] = melted["Вопрос"].apply(_assign_dept)
    melted["Период"] = melted["Период_Краткий"]

    return melted


# ---------------------------------------------------------------------------
# Главный парсер
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def parse_all_sheets(sheets: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """
    Парсит все листы файла и возвращает структурированные данные.
    Результат: {"nps": DataFrame, "departments": {name: DataFrame}, "combined": DataFrame}
    """
    result = {"nps": pd.DataFrame(), "departments": {}, "combined": pd.DataFrame()}

    # 1. NPS: приоритет — лист NPS2, затем сырой NPS
    if "NPS2" in sheets:
        result["nps"] = parse_nps_from_nps2(sheets["NPS2"])
    if result["nps"].empty and "NPS" in sheets:
        result["nps"] = parse_nps_from_raw(sheets["NPS"])

    # 2. Листы отделов (СПИР, Горничные, Питание, Мед.часть, КМР, Столовая)
    for sheet_name, df in sheets.items():
        name_lower = sheet_name.strip().lower()

        # Пропускаем служебные листы
        if name_lower in _SKIP_SHEETS:
            continue
        # Пропускаем листы-месяцы (Январь, Февраль, ...)
        if name_lower.rstrip() in _MONTH_NAMES_FULL:
            continue
        # Пропускаем годовые сводки (цифра, например «2025»)
        if re.match(r"^\d{4}$", name_lower):
            continue

        dept_df = parse_department_sheet(df, sheet_name.strip())
        if not dept_df.empty:
            result["departments"][sheet_name.strip()] = dept_df

    # 3. Если из отделов ничего не нашли, пробуем сводный лист (2025, 2024)
    if not result["departments"]:
        for sheet_name, df in sheets.items():
            if re.match(r"^\d{4}$", sheet_name.strip()):
                summary_df = parse_summary_sheet(df)
                if not summary_df.empty:
                    for dept in summary_df["Отдел"].unique():
                        dept_data = summary_df[summary_df["Отдел"] == dept].copy()
                        result["departments"][dept] = dept_data

    # 4. Объединяем все отделы
    dept_frames = [df for df in result["departments"].values() if not df.empty]
    if dept_frames:
        result["combined"] = pd.concat(dept_frames, ignore_index=True)

    return result


# ---------------------------------------------------------------------------
# Агрегации для KPI и визуализаций
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def compute_kpi_metrics(data: dict[str, Any]) -> dict[str, Any]:
    """
    Вычисляет ключевые метрики для KPI-карточек.
    Возвращает словарь со средним NPS, общим баллом, лидером и зоной риска.
    """
    metrics = {
        "avg_nps": None,
        "total_score": None,
        "leader_dept": None,
        "leader_score": None,
        "risk_dept": None,
        "risk_score": None,
        "risk_count": 0,
    }

    # Средний NPS
    nps_df = data.get("nps", pd.DataFrame())
    if not nps_df.empty and "NPS" in nps_df.columns:
        metrics["avg_nps"] = round(nps_df["NPS"].mean(), 1)

    # Общий средний балл по всем отделам (последний период)
    combined = data.get("combined", pd.DataFrame())
    if not combined.empty:
        # Общий балл — среднее всех оценок
        metrics["total_score"] = round(combined["Оценка"].mean(), 2)

        # Лидер — отдел с highest средней оценкой
        dept_avg = combined.groupby("Отдел")["Оценка"].mean().sort_values(ascending=False)
        if not dept_avg.empty:
            metrics["leader_dept"] = dept_avg.index[0]
            metrics["leader_score"] = round(dept_avg.iloc[0], 2)

        # Зона риска — отделы со средней оценкой < 3.5
        risk = dept_avg[dept_avg < 3.5]
        if not risk.empty:
            metrics["risk_dept"] = risk.index[-1]  # худший
            metrics["risk_score"] = round(risk.iloc[-1], 2)
            metrics["risk_count"] = len(risk)

    return metrics


@st.cache_data(show_spinner=False)
def get_radar_data(data: dict[str, Any], month_label: str | None = None) -> pd.DataFrame:
    """
    Подготавливает данные для радара качества.
    Возвращает средние оценки по отделам за выбранный месяц.
    """
    combined = data.get("combined", pd.DataFrame())
    if combined.empty:
        return pd.DataFrame()

    # Если месяц не выбран — берём последний доступный
    if month_label is None:
        periods = sorted(combined["Период_Краткий"].unique(), key=_month_sort_key)
        if periods:
            month_label = periods[-1]

    if month_label:
        filtered = combined[combined["Период_Краткий"] == month_label]
    else:
        filtered = combined

    if filtered.empty:
        return pd.DataFrame()

    # Средняя оценка по каждому отделу
    radar_df = filtered.groupby("Отдел")["Оценка"].mean().reset_index()
    radar_df.columns = ["Отдел", "Средняя оценка"]
    radar_df["Средняя оценка"] = radar_df["Средняя оценка"].round(2)

    return radar_df


@st.cache_data(show_spinner=False)
def get_heatmap_data(data: dict[str, Any]) -> pd.DataFrame:
    """
    Подготавливает данные для тепловой матрицы.
    Возвращает сводную таблицу: индекс = Отдел | Вопрос, колонки = периоды.
    """
    combined = data.get("combined", pd.DataFrame())
    if combined.empty:
        return pd.DataFrame()

    # Создаём составной индекс Отдел | Вопрос
    combined["Категория"] = combined["Отдел"] + " | " + combined["Вопрос"]

    # Сводная таблица
    pivot = combined.pivot_table(
        index="Категория",
        columns="Период_Краткий",
        values="Оценка",
        aggfunc="mean"
    ).round(2)

    # Сортируем периоды хронологически
    period_cols = sorted(pivot.columns.tolist(), key=_month_sort_key)
    pivot = pivot[period_cols]

    return pivot


@st.cache_data(show_spinner=False)
def get_drilldown_data(data: dict[str, Any], department: str) -> pd.DataFrame:
    """
    Возвращает данные для drill-down по выбранному отделу.
    """
    combined = data.get("combined", pd.DataFrame())
    if combined.empty or not department:
        return pd.DataFrame()

    dept_data = combined[combined["Отдел"] == department].copy()
    if dept_data.empty:
        return pd.DataFrame()

    # Агрегируем по периодам
    agg = dept_data.groupby("Период_Краткий").agg(
        Средняя_оценка=("Оценка", "mean"),
        Количество=("Оценка", "count")
    ).round(2).reset_index()

    # Сортируем хронологически
    agg["_sort"] = agg["Период_Краткий"].apply(_month_sort_key)
    agg = agg.sort_values("_sort").drop(columns=["_sort"]).reset_index(drop=True)

    return agg


@st.cache_data(show_spinner=False)
def get_question_breakdown(data: dict[str, Any], department: str) -> pd.DataFrame:
    """
    Возвращает детализацию по вопросам для выбранного отдела.
    """
    combined = data.get("combined", pd.DataFrame())
    if combined.empty or not department:
        return pd.DataFrame()

    dept_data = combined[combined["Отдел"] == department].copy()
    if dept_data.empty:
        return pd.DataFrame()

    # Средняя оценка по каждому вопросу за все время
    breakdown = dept_data.groupby("Вопрос")["Оценка"].mean().round(2).reset_index()
    breakdown.columns = ["Вопрос", "Средняя оценка"]
    breakdown = breakdown.sort_values("Средняя оценка", ascending=True).reset_index(drop=True)

    return breakdown


@st.cache_data(show_spinner=False)
def compare_periods(data: dict[str, Any], period_a: str, period_b: str) -> pd.DataFrame:
    """
    Сравнивает два периода по отделам.
    Возвращает DataFrame: [Отдел, Период_A, Период_B, Дельта, Дельта_%].
    """
    combined = data.get("combined", pd.DataFrame())
    if combined.empty:
        return pd.DataFrame()

    df_a = combined[combined["Период_Краткий"] == period_a].groupby("Отдел")["Оценка"].mean().round(2)
    df_b = combined[combined["Период_Краткий"] == period_b].groupby("Отдел")["Оценка"].mean().round(2)

    all_depts = sorted(set(df_a.index) | set(df_b.index))
    rows = []
    for dept in all_depts:
        val_a = df_a.get(dept, None)
        val_b = df_b.get(dept, None)
        delta = round(val_b - val_a, 2) if val_a is not None and val_b is not None else None
        delta_pct = round((delta / val_a) * 100, 1) if delta is not None and val_a and val_a != 0 else None
        rows.append({
            "Отдел": dept,
            period_a: val_a,
            period_b: val_b,
            "Δ": delta,
            "Δ %": delta_pct,
        })
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def compare_periods_by_question(data: dict[str, Any], period_a: str, period_b: str, department: str | None = None) -> pd.DataFrame:
    """
    Сравнивает два периода по вопросам (с опциональным фильтром по отделу).
    """
    combined = data.get("combined", pd.DataFrame())
    if combined.empty:
        return pd.DataFrame()

    if department:
        combined = combined[combined["Отдел"] == department]

    grp = ["Отдел", "Вопрос"]
    df_a = combined[combined["Период_Краткий"] == period_a].groupby(grp)["Оценка"].mean().round(2)
    df_b = combined[combined["Период_Краткий"] == period_b].groupby(grp)["Оценка"].mean().round(2)

    all_keys = sorted(set(df_a.index) | set(df_b.index))
    rows = []
    for key in all_keys:
        val_a = df_a.get(key, None)
        val_b = df_b.get(key, None)
        delta = round(val_b - val_a, 2) if val_a is not None and val_b is not None else None
        rows.append({
            "Отдел": key[0],
            "Вопрос": key[1],
            period_a: val_a,
            period_b: val_b,
            "Δ": delta,
        })
    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values("Δ", ascending=True, na_position="last").reset_index(drop=True)
    return result


@st.cache_data(show_spinner=False)
def compute_kpi_with_delta(data: dict[str, Any]) -> dict[str, Any]:
    """
    Расширенные KPI с дельтами к предыдущему периоду.
    """
    metrics = compute_kpi_metrics(data)

    # Дельты NPS
    nps_df = data.get("nps", pd.DataFrame())
    if not nps_df.empty and "NPS" in nps_df.columns and len(nps_df) >= 2:
        metrics["nps_last"] = round(nps_df["NPS"].iloc[-1], 1)
        metrics["nps_prev"] = round(nps_df["NPS"].iloc[-2], 1)
        metrics["nps_delta"] = round(metrics["nps_last"] - metrics["nps_prev"], 1)
    else:
        metrics["nps_last"] = metrics.get("avg_nps")
        metrics["nps_prev"] = None
        metrics["nps_delta"] = None

    # Дельты по общему баллу (последний vs предпоследний период)
    combined = data.get("combined", pd.DataFrame())
    if not combined.empty:
        periods = sorted(combined["Период_Краткий"].unique(), key=_month_sort_key)
        if len(periods) >= 2:
            last_p = periods[-1]
            prev_p = periods[-2]
            last_score = combined[combined["Период_Краткий"] == last_p]["Оценка"].mean()
            prev_score = combined[combined["Период_Краткий"] == prev_p]["Оценка"].mean()
            metrics["score_last"] = round(last_score, 2)
            metrics["score_prev"] = round(prev_score, 2)
            metrics["score_delta"] = round(last_score - prev_score, 2)
            metrics["last_period"] = last_p
            metrics["prev_period"] = prev_p
        else:
            metrics["score_delta"] = None
            metrics["last_period"] = periods[0] if periods else None
            metrics["prev_period"] = None
    else:
        metrics["score_delta"] = None
        metrics["last_period"] = None
        metrics["prev_period"] = None

    return metrics


# ---------------------------------------------------------------------------
# Автоматические инсайты
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def generate_insights(data: dict[str, Any]) -> list[dict[str, str]]:
    """
    Генерирует автоматические инсайты на основе данных.
    Возвращает список: [{"type": "positive|negative|warning|info", "text": "..."}]
    """
    insights = []
    combined = data.get("combined", pd.DataFrame())
    nps_df = data.get("nps", pd.DataFrame())

    if combined.empty:
        return insights

    periods = sorted(combined["Период_Краткий"].unique(), key=_month_sort_key)

    # --- NPS-инсайты ---
    if not nps_df.empty and "NPS" in nps_df.columns and len(nps_df) >= 2:
        last_nps = nps_df["NPS"].iloc[-1]
        avg_nps = nps_df["NPS"].mean()
        max_nps = nps_df["NPS"].max()
        min_nps = nps_df["NPS"].min()
        max_month = nps_df.loc[nps_df["NPS"].idxmax(), "Месяц"]
        min_month = nps_df.loc[nps_df["NPS"].idxmin(), "Месяц"]

        if last_nps >= 90:
            insights.append({"type": "positive", "text": f"NPS на высоком уровне ({last_nps}%) — гости активно рекомендуют"})
        elif last_nps < 70:
            insights.append({"type": "negative", "text": f"NPS ниже 70% ({last_nps}%) — требуется срочное внимание к качеству сервиса"})

        if max_nps - min_nps > 15:
            insights.append({"type": "warning", "text": f"Высокая волатильность NPS: от {min_nps}% ({min_month}) до {max_nps}% ({max_month}) — разброс {max_nps - min_nps:.0f}%"})

        # Тренд последних 3 месяцев
        if len(nps_df) >= 3:
            last_3 = nps_df["NPS"].iloc[-3:].tolist()
            if all(last_3[i] <= last_3[i+1] for i in range(len(last_3)-1)):
                insights.append({"type": "positive", "text": f"NPS растёт 3 месяца подряд: {last_3[0]}% → {last_3[-1]}%"})
            elif all(last_3[i] >= last_3[i+1] for i in range(len(last_3)-1)):
                insights.append({"type": "negative", "text": f"NPS падает 3 месяца подряд: {last_3[0]}% → {last_3[-1]}%"})

    # --- Общий средний балл ---
    overall_avg = combined["Оценка"].mean()
    if overall_avg >= 4.7:
        insights.append({"type": "positive", "text": f"Общий балл за все периоды: {overall_avg:.2f} — отличный уровень сервиса"})
    elif overall_avg < 4.0:
        insights.append({"type": "negative", "text": f"Общий балл за все периоды: {overall_avg:.2f} — ниже целевого (4.0)"})

    # --- Инсайты по отделам ---
    if len(periods) >= 2:
        last_p = periods[-1]
        prev_p = periods[-2]

        for dept in combined["Отдел"].unique():
            dept_last = combined[(combined["Отдел"] == dept) & (combined["Период_Краткий"] == last_p)]["Оценка"].mean()
            dept_prev = combined[(combined["Отдел"] == dept) & (combined["Период_Краткий"] == prev_p)]["Оценка"].mean()

            if pd.notna(dept_last) and pd.notna(dept_prev):
                delta = dept_last - dept_prev
                if delta >= 0.03:
                    insights.append({"type": "positive", "text": f"{dept}: рост +{delta:.2f} за {last_p} ({dept_prev:.2f} → {dept_last:.2f})"})
                elif delta <= -0.03:
                    insights.append({"type": "negative", "text": f"{dept}: снижение {delta:.2f} за {last_p} ({dept_prev:.2f} → {dept_last:.2f})"})

    # --- Худшие 3 вопроса ---
    question_avg = combined.groupby(["Отдел", "Вопрос"])["Оценка"].mean()
    worst_3 = question_avg.nsmallest(3)
    for (dept, q), score in worst_3.items():
        if score < 4.7:
            insights.append({"type": "warning", "text": f"Слабое место: «{q}» ({dept}) — {score:.2f}"})

    # --- Лучший вопрос ---
    best = question_avg.nlargest(1)
    if not best.empty:
        (dept, q), score = best.index[0], best.iloc[0]
        insights.append({"type": "positive", "text": f"Лучший показатель: «{q}» ({dept}) — {score:.2f}"})

    # --- Стабильность ---
    dept_std = combined.groupby("Отдел")["Оценка"].std()
    most_stable = dept_std.idxmin()
    most_volatile = dept_std.idxmax()
    if dept_std.max() - dept_std.min() > 0.02:
        insights.append({"type": "info", "text": f"Самый стабильный: {most_stable} (σ={dept_std.min():.3f}) | Нестабильный: {most_volatile} (σ={dept_std.max():.3f})"})

    # --- Количество периодов ---
    insights.append({"type": "info", "text": f"Охват данных: {len(periods)} месяцев, {len(combined['Отдел'].unique())} отделов, {len(question_avg)} показателей"})

    return insights


# ---------------------------------------------------------------------------
# Top / Bottom рейтинг вопросов
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def get_top_bottom_questions(data: dict[str, Any], n: int = 5) -> dict[str, pd.DataFrame]:
    """
    Возвращает top-N и bottom-N вопросов по средней оценке.
    С дельтой к предыдущему периоду.
    """
    combined = data.get("combined", pd.DataFrame())
    if combined.empty:
        return {"top": pd.DataFrame(), "bottom": pd.DataFrame()}

    periods = sorted(combined["Период_Краткий"].unique(), key=_month_sort_key)

    # Средние за всё время
    q_avg = combined.groupby(["Отдел", "Вопрос"])["Оценка"].mean().round(2)

    # Дельта (последний vs предпоследний)
    deltas = {}
    if len(periods) >= 2:
        last_p, prev_p = periods[-1], periods[-2]
        q_last = combined[combined["Период_Краткий"] == last_p].groupby(["Отдел", "Вопрос"])["Оценка"].mean()
        q_prev = combined[combined["Период_Краткий"] == prev_p].groupby(["Отдел", "Вопрос"])["Оценка"].mean()
        for key in q_last.index:
            if key in q_prev.index:
                deltas[key] = round(q_last[key] - q_prev[key], 2)

    def _build_df(series):
        rows = []
        for (dept, q), score in series.items():
            rows.append({
                "Отдел": dept,
                "Вопрос": q,
                "Средняя": score,
                "Δ": deltas.get((dept, q), None),
            })
        return pd.DataFrame(rows)

    top_df = _build_df(q_avg.nlargest(n))
    bottom_df = _build_df(q_avg.nsmallest(n))

    return {"top": top_df, "bottom": bottom_df}


# ---------------------------------------------------------------------------
# Excel-экспорт
# ---------------------------------------------------------------------------

def export_to_excel(data: dict[str, Any]) -> bytes:
    """
    Экспортирует данные в Excel с несколькими листами:
    - Сводка по отделам
    - Детализация по вопросам
    - NPS по месяцам
    - Тепловая матрица
    """
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Лист 1: Сводка по отделам
        combined = data.get("combined", pd.DataFrame())
        if not combined.empty:
            dept_summary = combined.groupby("Отдел").agg(
                Средний_балл=("Оценка", "mean"),
                Мин=("Оценка", "min"),
                Макс=("Оценка", "max"),
                Кол_во_оценок=("Оценка", "count"),
            ).round(2).sort_values("Средний_балл", ascending=False)
            dept_summary.to_excel(writer, sheet_name="Сводка по отделам")

            # Лист 2: Детализация
            detail = combined.groupby(["Отдел", "Вопрос", "Период_Краткий"])["Оценка"].mean().round(2).reset_index()
            detail = detail.sort_values(["Отдел", "Вопрос", "Период_Краткий"])
            detail.to_excel(writer, sheet_name="Детализация", index=False)

            # Лист 3: Тепловая матрица
            heatmap = get_heatmap_data(data)
            if not heatmap.empty:
                heatmap.to_excel(writer, sheet_name="Тепловая матрица")

        # Лист 4: NPS
        nps_df = data.get("nps", pd.DataFrame())
        if not nps_df.empty:
            nps_df.to_excel(writer, sheet_name="NPS", index=False)

    output.seek(0)
    return output.getvalue()


# ---------------------------------------------------------------------------
# PDF-генерация
# ---------------------------------------------------------------------------

# Фирменные цвета для PDF
_PDF_DARK = (15, 23, 42)        # slate_900
_PDF_BRAND = (56, 189, 248)     # sky
_PDF_EMERALD = (52, 211, 153)
_PDF_AMBER = (245, 158, 11)
_PDF_RUBY = (225, 29, 72)
_PDF_GRAY = (100, 116, 139)
_PDF_LIGHT = (241, 245, 249)    # slate_100
_PDF_WHITE = (255, 255, 255)


class GuestVoicePDF(FPDF):
    """Кастомный PDF с фирменным стилем «Голос Гостя»."""

    def __init__(self):
        super().__init__()
        if os.path.exists(MATPLOTLIB_FONT_PATH):
            self.add_font("DejaVu", "", MATPLOTLIB_FONT_PATH, uni=True)
            self.add_font("DejaVu", "B", MATPLOTLIB_FONT_PATH, uni=True)
            self.add_font("DejaVu", "I", MATPLOTLIB_FONT_PATH, uni=True)
        self._font_name = "DejaVu" if os.path.exists(MATPLOTLIB_FONT_PATH) else "helvetica"

    def _f(self, style="", size=10):
        self.set_font(self._font_name, style, size)

    def header(self):
        # Тёмная полоса-хедер
        self.set_fill_color(*_PDF_DARK)
        self.rect(0, 0, 210, 22, "F")
        # Акцентная линия
        self.set_fill_color(*_PDF_BRAND)
        self.rect(0, 22, 210, 1.5, "F")
        # Текст в хедере
        self._f("B", 11)
        self.set_text_color(*_PDF_WHITE)
        self.set_y(5)
        self.cell(0, 12, "ГОЛОС ГОСТЯ  |  Аналитический отчёт", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_y(26)

    def footer(self):
        self.set_y(-14)
        # Линия
        self.set_draw_color(*_PDF_BRAND)
        self.line(15, self.get_y(), 195, self.get_y())
        self.ln(2)
        self._f("", 7)
        self.set_text_color(*_PDF_GRAY)
        self.cell(0, 8, f"Страница {self.page_no()}  |  Сформировано: {datetime.now().strftime('%d.%m.%Y %H:%M')}", align="C")

    def section_title(self, text: str, icon: str = ""):
        """Рисует заголовок секции с акцентной полосой."""
        self.ln(4)
        # Акцентная полоска слева
        y = self.get_y()
        self.set_fill_color(*_PDF_BRAND)
        self.rect(15, y, 3, 9, "F")
        # Текст
        self._f("B", 13)
        self.set_text_color(*_PDF_DARK)
        self.set_x(21)
        self.cell(0, 9, f"  {icon} {text}", new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

    def kpi_block(self, x: float, y: float, w: float, label: str, value: str, color: tuple):
        """Рисует KPI-карточку как цветной блок."""
        # Фон карточки
        self.set_fill_color(*color)
        self.rounded_rect(x, y, w, 28, 3, "F")
        # Метка
        self._f("", 8)
        self.set_text_color(*_PDF_WHITE)
        self.set_xy(x + 3, y + 3)
        self.cell(w - 6, 6, label, align="C")
        # Значение
        self._f("B", 16)
        self.set_xy(x + 3, y + 11)
        self.cell(w - 6, 12, value, align="C")

    def rounded_rect(self, x, y, w, h, r, style=""):
        """Прямоугольник с закруглёнными углами."""
        # Упрощение: рисуем обычный rect (fpdf2 не поддерживает rounded rect нативно)
        self.rect(x, y, w, h, style)


def _add_image_from_plotly(fig: go.Figure, pdf: FPDF, width: int = 175, img_height: int = 500) -> None:
    """Конвертирует Plotly-фигуру в PNG и добавляет в PDF."""
    import uuid
    try:
        img_bytes = fig.to_image(format="png", engine="kaleido", scale=2.5, width=1200, height=img_height)
        img_path = f"/tmp/plotly_pdf_{uuid.uuid4().hex[:8]}.png"
        with open(img_path, "wb") as f:
            f.write(img_bytes)
        pdf.image(img_path, x=(210 - width) / 2, w=width)
        os.remove(img_path)
    except Exception as e:
        pdf._f("", 9)
        pdf.set_text_color(*_PDF_RUBY)
        pdf.cell(0, 8, f"Ошибка рендера графика: {e}", new_x="LMARGIN", new_y="NEXT")


def _make_print_chart(fig: go.Figure, title: str = "") -> go.Figure:
    """Стилизует Plotly-фигуру для печати (белый фон, чёткие цвета)."""
    import copy
    fig_copy = copy.deepcopy(fig)
    fig_copy.update_layout(
        template="plotly_white",
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family="Arial, sans-serif", size=12, color="#1E293B"),
        title=dict(text=title, font=dict(size=16, color="#0F172A"), x=0.5) if title else None,
        margin=dict(l=50, r=30, t=50 if title else 20, b=40),
    )
    return fig_copy


def generate_pdf_report(data: dict[str, Any], charts: dict[str, go.Figure]) -> bytes:
    """Генерирует премиальный PDF-отчёт."""
    pdf = GuestVoicePDF()
    pdf.set_auto_page_break(auto=True, margin=18)

    # ================================================================
    # СТРАНИЦА 1: Титул + KPI
    # ================================================================
    pdf.add_page()

    # Большой заголовок
    pdf.ln(8)
    pdf._f("B", 22)
    pdf.set_text_color(*_PDF_DARK)
    pdf.cell(0, 14, "Отчёт по качеству сервиса", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf._f("", 10)
    pdf.set_text_color(*_PDF_GRAY)
    pdf.cell(0, 8, f"Дата формирования: {datetime.now().strftime('%d %B %Y г.').replace('January','января').replace('February','февраля').replace('March','марта').replace('April','апреля').replace('May','мая').replace('June','июня').replace('July','июля').replace('August','августа').replace('September','сентября').replace('October','октября').replace('November','ноября').replace('December','декабря')}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    # KPI-карточки
    metrics = compute_kpi_with_delta(data)
    kpi_items = [
        ("NPS", f"{metrics.get('nps_last') or metrics.get('avg_nps', '—')}%", _PDF_BRAND),
        ("Общий балл", f"{metrics.get('score_last') or metrics.get('total_score', '—')}", (30, 58, 95)),
        ("Лидер", f"{metrics.get('leader_dept', '—')}", (5, 150, 105)),
        ("Зона риска", f"{metrics.get('risk_dept') or 'Нет'}", _PDF_RUBY if metrics.get('risk_dept') else (5, 150, 105)),
    ]
    card_w = 42
    gap = 3
    start_x = (210 - (card_w * 4 + gap * 3)) / 2
    y = pdf.get_y()
    for i, (label, value, color) in enumerate(kpi_items):
        pdf.kpi_block(start_x + i * (card_w + gap), y, card_w, label, str(value), color)
    pdf.set_y(y + 34)

    # Разделитель
    pdf.set_draw_color(*_PDF_LIGHT)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(6)

    # NPS-график
    if "nps" in charts and not data.get("nps", pd.DataFrame()).empty:
        pdf.section_title("Динамика NPS", "📈")
        fig_print = _make_print_chart(charts["nps"])
        fig_print.update_traces(fillcolor='rgba(56, 189, 248, 0.3)', line=dict(color='#0284C7', width=3))
        _add_image_from_plotly(fig_print, pdf)
        pdf.ln(4)

    # ================================================================
    # СТРАНИЦА 2: Радар
    # ================================================================
    if "radar" in charts:
        pdf.add_page()
        pdf.section_title("Радар качества по отделам", "🕸️")
        fig_print = _make_print_chart(charts["radar"])
        fig_print.update_layout(
            polar=dict(
                bgcolor="white",
                radialaxis=dict(gridcolor="#E2E8F0", linecolor="#CBD5E1"),
                angularaxis=dict(linecolor="#CBD5E1", gridcolor="#E2E8F0"),
            ),
        )
        fig_print.update_traces(
            fillcolor='rgba(5, 150, 105, 0.2)',
            line=dict(color='#059669', width=3),
        )
        _add_image_from_plotly(fig_print, pdf)
        pdf.ln(6)

        # Таблица средних баллов по отделам под радаром
        combined = data.get("combined", pd.DataFrame())
        if not combined.empty:
            dept_avg = combined.groupby("Отдел")["Оценка"].mean().round(2).sort_values(ascending=False)
            pdf.section_title("Средние баллы по отделам", "📊")
            # Заголовок таблицы
            pdf._f("B", 9)
            pdf.set_fill_color(*_PDF_DARK)
            pdf.set_text_color(*_PDF_WHITE)
            pdf.cell(90, 8, "  Отдел", border=0, fill=True)
            pdf.cell(40, 8, "Средний балл", border=0, fill=True, align="C")
            pdf.cell(50, 8, "Статус", border=0, fill=True, align="C")
            pdf.ln()
            # Строки
            pdf._f("", 9)
            for i, (dept, score) in enumerate(dept_avg.items()):
                bg = _PDF_LIGHT if i % 2 == 0 else _PDF_WHITE
                pdf.set_fill_color(*bg)
                pdf.set_text_color(*_PDF_DARK)
                pdf.cell(90, 7, f"  {dept}", border=0, fill=True)
                # Цвет оценки
                if score >= 4.7:
                    pdf.set_text_color(*_PDF_EMERALD[:3])
                elif score >= 4.3:
                    pdf.set_text_color(*_PDF_AMBER)
                else:
                    pdf.set_text_color(*_PDF_RUBY)
                pdf.cell(40, 7, f"{score:.2f}", border=0, fill=True, align="C")
                status = "Отлично" if score >= 4.7 else "Хорошо" if score >= 4.3 else "Внимание"
                pdf.cell(50, 7, status, border=0, fill=True, align="C")
                pdf.ln()

    # ================================================================
    # СТРАНИЦА 3: Тепловая матрица
    # ================================================================
    if "heatmap" in charts:
        pdf.add_page()
        pdf.section_title("Тепловая матрица оценок", "🔥")
        import copy
        fig_hm = copy.deepcopy(charts["heatmap"])
        fig_hm.update_layout(
            template="plotly_white",
            paper_bgcolor="white",
            plot_bgcolor="white",
            font=dict(family="Arial, sans-serif", size=11, color="#1E293B"),
            margin=dict(l=50, r=30, t=20, b=40),
            coloraxis_colorbar=dict(
                title=dict(text="Оценка", font=dict(color="#1E293B")),
                tickfont=dict(color="#1E293B"),
            ),
        )
        # Heatmap needs a taller image to show all rows
        hm_data = data.get("combined", pd.DataFrame())
        n_rows = len(fig_hm.data[0].y) if fig_hm.data else 15
        hm_height = max(500, n_rows * 35 + 100)
        _add_image_from_plotly(fig_hm, pdf, width=185, img_height=hm_height)
        pdf.ln(6)

    # ================================================================
    # СТРАНИЦА 4: Сводная таблица
    # ================================================================
    combined = data.get("combined", pd.DataFrame())
    if not combined.empty:
        pdf.add_page()
        pdf.section_title("Детализация по вопросам", "📋")

        summary = combined.groupby(["Отдел", "Вопрос"])["Оценка"].mean().round(2).reset_index()
        summary = summary.sort_values(["Отдел", "Оценка"], ascending=[True, False])

        # Заголовок
        col_widths = [40, 105, 35]
        headers = ["Отдел", "Вопрос", "Балл"]
        pdf._f("B", 9)
        pdf.set_fill_color(*_PDF_DARK)
        pdf.set_text_color(*_PDF_WHITE)
        for w, h in zip(col_widths, headers):
            pdf.cell(w, 8, f"  {h}", border=0, fill=True)
        pdf.ln()

        # Строки с группировкой по отделу
        pdf._f("", 8)
        current_dept = ""
        for i, (_, row) in enumerate(summary.iterrows()):
            score = row["Оценка"]
            dept = str(row["Отдел"])

            # Разделитель между отделами
            if dept != current_dept:
                current_dept = dept
                if i > 0:
                    pdf.ln(1)

            bg = _PDF_LIGHT if i % 2 == 0 else _PDF_WHITE
            pdf.set_fill_color(*bg)
            pdf.set_text_color(*_PDF_DARK)

            pdf.cell(col_widths[0], 7, f"  {dept[:18]}", border=0, fill=True)
            pdf.cell(col_widths[1], 7, f"  {str(row['Вопрос'])[:48]}", border=0, fill=True)

            # Цветной балл
            if score >= 4.7:
                pdf.set_text_color(5, 150, 105)
            elif score >= 4.3:
                pdf.set_text_color(217, 119, 6)
            else:
                pdf.set_text_color(225, 29, 72)
            pdf._f("B", 9)
            pdf.cell(col_widths[2], 7, f"{score:.2f}", border=0, fill=True, align="C")
            pdf._f("", 8)
            pdf.ln()

    return bytes(pdf.output())

# ---------------------------------------------------------------------------
# Вспомогательные функции для UI
# ---------------------------------------------------------------------------

def get_available_months(data: dict[str, Any]) -> list[str]:
    """Возвращает список доступных месяцев для выбора."""
    combined = data.get("combined", pd.DataFrame())
    if combined.empty:
        return []
    periods = sorted(combined["Период_Краткий"].unique().tolist(), key=_month_sort_key)
    return periods


def get_available_departments(data: dict[str, Any]) -> list[str]:
    """Возвращает список доступных отделов."""
    combined = data.get("combined", pd.DataFrame())
    if combined.empty:
        return []
    return sorted(combined["Отдел"].unique().tolist())
