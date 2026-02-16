"""Reusable design system helpers for Streamlit UI pages."""

from __future__ import annotations

from html import escape
from typing import Iterable

import streamlit as st


def _safe_text(value: object) -> str:
    return escape(str(value if value is not None else ""))


def load_custom_css() -> None:
    """Inject the global professional design system CSS once per session."""
    if st.session_state.get("_design_css_loaded"):
        return

    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        :root {
            --primary-color: #0066CC;
            --primary-dark: #004C99;
            --primary-light: #E6F2FF;
            --secondary-color: #00C896;
            --accent-color: #FF6B35;
            --danger-color: #DC3545;
            --neutral-dark: #2C3E50;
            --neutral-medium: #7F8C8D;
            --neutral-light: #ECF0F1;
            --white: #FFFFFF;
            --success: #28A745;
            --warning: #FFC107;
            --info: #17A2B8;

            --gradient-primary: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            --gradient-success: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            --gradient-warning: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            --gradient-info: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            --gradient-danger: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);

            --fs-xs: 0.75rem;
            --fs-sm: 0.875rem;
            --fs-base: 1rem;
            --fs-lg: 1.125rem;
            --fs-xl: 1.25rem;
            --fs-2xl: 1.5rem;
            --fs-3xl: 1.875rem;
            --fs-4xl: 2.25rem;

            --fw-normal: 400;
            --fw-medium: 500;
            --fw-semibold: 600;
            --fw-bold: 700;

            --space-xs: 0.25rem;
            --space-sm: 0.5rem;
            --space-md: 1rem;
            --space-lg: 1.5rem;
            --space-xl: 2rem;
            --space-2xl: 3rem;
            --space-3xl: 4rem;

            --radius-sm: 0.25rem;
            --radius-md: 0.5rem;
            --radius-lg: 0.75rem;
            --radius-xl: 1rem;
            --radius-full: 9999px;

            --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
            --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
            --shadow-2xl: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
        }

        * {
            font-family: 'Inter', 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI',
                         'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif !important;
        }

        [data-testid="stAppViewContainer"] {
            background: var(--gradient-primary);
            background-attachment: fixed;
        }

        [data-testid="stAppViewContainer"] .main {
            background: transparent;
        }

        .block-container {
            max-width: 1400px;
            padding: 2rem 2.25rem 2.5rem 2.25rem;
            margin: 1.5rem auto;
            background: rgba(255, 255, 255, 0.97);
            border-radius: var(--radius-xl);
            box-shadow: var(--shadow-2xl);
            animation: slideInUp 0.55s ease-out;
        }

        .ui-page-header {
            animation: slideInRight 0.55s ease-out;
            margin-bottom: 1.5rem;
        }

        .ui-page-header__row {
            display: flex;
            align-items: center;
            gap: 0.85rem;
            flex-wrap: wrap;
        }

        .ui-page-header__icon {
            font-size: 2.2rem;
            line-height: 1;
        }

        .ui-page-header__title {
            margin: 0;
            font-size: clamp(1.55rem, 2.8vw, 2.45rem);
            font-weight: var(--fw-bold);
            background: var(--gradient-primary);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .ui-page-header__subtitle {
            margin: 0.35rem 0 0 0;
            color: var(--neutral-medium);
            font-size: var(--fs-lg);
            font-weight: var(--fw-medium);
        }

        .ui-page-header__rule {
            margin-top: 0.95rem;
            height: 4px;
            width: 100%;
            border-radius: var(--radius-full);
            background: var(--gradient-primary);
            background-size: 200% 100%;
            animation: shimmer 2.25s linear infinite;
        }

        .ui-stat-card {
            position: relative;
            overflow: hidden;
            background: var(--white);
            border-radius: var(--radius-xl);
            padding: 1.2rem 1.15rem;
            box-shadow: var(--shadow-md);
            border: 1px solid rgba(0, 0, 0, 0.03);
            transition: transform 0.25s ease, box-shadow 0.25s ease;
            animation: scaleIn 0.4s ease-out;
            min-height: 128px;
        }

        .ui-stat-card:hover {
            transform: translateY(-4px);
            box-shadow: var(--shadow-xl);
        }

        .ui-stat-card::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 5px;
            background: var(--card-gradient, var(--gradient-primary));
        }

        .ui-stat-card__top {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.6rem;
        }

        .ui-stat-card__label {
            color: var(--neutral-medium);
            font-size: var(--fs-sm);
            font-weight: var(--fw-semibold);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin: 0;
        }

        .ui-stat-card__value {
            margin: 0.45rem 0 0 0;
            font-size: clamp(1.2rem, 2.1vw, 2.05rem);
            font-weight: var(--fw-bold);
            background: var(--card-gradient, var(--gradient-primary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            line-height: 1.1;
        }

        .ui-stat-card__icon {
            font-size: 2rem;
            opacity: 0.25;
            animation: pulse 3s ease-in-out infinite;
        }

        .ui-alert {
            border-radius: var(--radius-lg);
            padding: 0.9rem 1rem;
            margin: 0.75rem 0 1rem 0;
            display: flex;
            align-items: center;
            gap: 0.75rem;
            color: #fff;
            font-size: var(--fs-base);
            font-weight: var(--fw-semibold);
            box-shadow: var(--shadow-lg);
            animation: slideInRight 0.4s ease-out;
        }

        .ui-alert--success { background: var(--gradient-success); }
        .ui-alert--error { background: var(--gradient-danger); }
        .ui-alert--warning { background: var(--gradient-warning); }
        .ui-alert--info { background: var(--gradient-info); }

        .ui-loading-wrap {
            text-align: center;
            padding: 2rem 0.5rem;
            animation: fadeIn 0.35s ease-out;
        }

        .ui-loading-spinner {
            width: 52px;
            height: 52px;
            margin: 0 auto 0.75rem auto;
            border-radius: 50%;
            border: 4px solid #E9ECEF;
            border-top-color: var(--primary-color);
            animation: rotate 1s linear infinite;
        }

        .ui-loading-label {
            color: var(--neutral-medium);
            font-weight: var(--fw-semibold);
            font-size: var(--fs-lg);
            margin: 0;
        }

        .ui-progress-wrap {
            margin: 0.5rem 0 1rem 0;
        }

        .ui-progress-label {
            color: var(--neutral-dark);
            font-weight: var(--fw-semibold);
            margin: 0 0 0.45rem 0;
            font-size: var(--fs-sm);
        }

        .ui-progress-track {
            width: 100%;
            height: 0.7rem;
            border-radius: var(--radius-full);
            background: #DDE2E7;
            overflow: hidden;
        }

        .ui-progress-value {
            height: 100%;
            border-radius: var(--radius-full);
            background: var(--gradient-primary);
            background-size: 200% 100%;
            animation: shimmer 2s linear infinite;
            transition: width 0.45s ease;
        }

        .ui-progress-percent {
            text-align: right;
            color: var(--neutral-medium);
            margin: 0.3rem 0 0 0;
            font-size: var(--fs-xs);
            font-weight: var(--fw-semibold);
        }

        .ui-upload-zone {
            border: 2px dashed var(--primary-color);
            border-radius: var(--radius-xl);
            padding: 1.35rem 1rem;
            text-align: center;
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.08) 0%, rgba(118, 75, 162, 0.08) 100%);
            transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
            animation: fadeIn 0.45s ease-out;
            margin-bottom: 0.4rem;
        }

        .ui-upload-zone:hover {
            transform: translateY(-2px);
            border-color: var(--primary-dark);
            box-shadow: var(--shadow-md);
        }

        .ui-upload-zone__icon {
            font-size: 2.5rem;
            line-height: 1;
            margin-bottom: 0.35rem;
            animation: bounce 2s ease infinite;
        }

        .ui-upload-zone__title {
            margin: 0;
            color: var(--neutral-dark);
            font-size: var(--fs-lg);
            font-weight: var(--fw-semibold);
        }

        .ui-upload-zone__hint {
            margin: 0.25rem 0 0 0;
            color: var(--neutral-medium);
            font-size: var(--fs-sm);
        }

        .ui-upload-zone__types {
            margin: 0.3rem 0 0 0;
            color: #9BA7B4;
            font-size: var(--fs-xs);
            font-weight: var(--fw-medium);
        }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #2C3E50 0%, #34495E 100%);
            border-right: none;
            box-shadow: 4px 0 15px rgba(0, 0, 0, 0.1);
        }

        section[data-testid="stSidebar"] * {
            color: #fff !important;
        }

        section[data-testid="stSidebar"] [data-baseweb="select"] * {
            color: #1F2937 !important;
        }

        .stButton > button {
            background: var(--gradient-primary);
            color: #fff;
            border: none;
            border-radius: var(--radius-md);
            padding: 0.7rem 1rem;
            font-size: var(--fs-base);
            font-weight: var(--fw-semibold);
            box-shadow: var(--shadow-md);
            transition: transform 0.2s ease, box-shadow 0.2s ease, filter 0.2s ease;
        }

        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
            filter: brightness(1.02);
        }

        .stButton > button:active {
            transform: translateY(0);
        }

        .stDownloadButton > button {
            background: var(--gradient-success);
            color: #fff;
            border: none;
            border-radius: var(--radius-md);
            font-weight: var(--fw-semibold);
            box-shadow: var(--shadow-md);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .stDownloadButton > button:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }

        .stTextInput > div > div > input,
        .stNumberInput > div > div > input,
        .stTextArea textarea,
        [data-baseweb="select"] > div,
        [data-baseweb="base-input"] > div {
            border-radius: var(--radius-md) !important;
            border: 2px solid #E2E8F0 !important;
            background: #FAFCFF !important;
            transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease !important;
        }

        .stTextInput > div > div > input:focus,
        .stNumberInput > div > div > input:focus,
        .stTextArea textarea:focus,
        [data-baseweb="base-input"] > div:focus-within,
        [data-baseweb="select"] > div:focus-within {
            border-color: var(--primary-color) !important;
            box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.12) !important;
            background: #fff !important;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.45rem;
            border-bottom: 2px solid #E3E8EF;
        }

        .stTabs [data-baseweb="tab"] {
            border-radius: var(--radius-md) var(--radius-md) 0 0;
            color: var(--neutral-medium);
            font-weight: var(--fw-semibold);
            padding: 0.8rem 1rem;
            transition: all 0.2s ease;
        }

        .stTabs [data-baseweb="tab"]:hover {
            color: var(--primary-color);
            background: #F7FAFF;
        }

        .stTabs [aria-selected="true"] {
            color: #fff !important;
            background: var(--gradient-primary) !important;
            box-shadow: 0 -2px 8px rgba(102, 126, 234, 0.3);
        }

        .stDataFrame, .stTable {
            border-radius: var(--radius-lg) !important;
            overflow: hidden !important;
            box-shadow: var(--shadow-md);
            animation: fadeIn 0.45s ease-out;
        }

        [data-testid="stFileUploader"] {
            border-radius: var(--radius-lg);
            border: 2px dashed rgba(0, 102, 204, 0.45);
            padding: 0.9rem;
            background: #FAFCFF;
            transition: border-color 0.2s ease, background-color 0.2s ease;
        }

        [data-testid="stFileUploader"]:hover {
            border-color: rgba(0, 76, 153, 0.9);
            background: #F0F7FF;
        }

        .streamlit-expanderHeader {
            border-radius: var(--radius-md);
            background: #F8FAFC;
            font-weight: var(--fw-semibold);
            color: var(--neutral-dark);
            transition: background-color 0.2s ease;
        }

        .streamlit-expanderHeader:hover {
            background: #EEF2F7;
            color: var(--primary-dark);
        }

        .stProgress > div > div {
            background: var(--gradient-primary);
            border-radius: var(--radius-full);
            animation: shimmer 2s linear infinite;
            background-size: 200% 100%;
        }

        ::-webkit-scrollbar {
            width: 10px;
            height: 10px;
        }

        ::-webkit-scrollbar-track {
            background: #F1F1F1;
            border-radius: 10px;
        }

        ::-webkit-scrollbar-thumb {
            background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
            border-radius: 10px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: linear-gradient(180deg, #764ba2 0%, #667eea 100%);
        }

        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        @keyframes slideInUp {
            from { opacity: 0; transform: translateY(30px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @keyframes slideInRight {
            from { opacity: 0; transform: translateX(30px); }
            to { opacity: 1; transform: translateX(0); }
        }

        @keyframes scaleIn {
            from { opacity: 0; transform: scale(0.92); }
            to { opacity: 1; transform: scale(1); }
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.55; }
        }

        @keyframes shimmer {
            0% { background-position: -1000px 0; }
            100% { background-position: 1000px 0; }
        }

        @keyframes bounce {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-8px); }
        }

        @keyframes rotate {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }

        @media (max-width: 1024px) {
            .block-container {
                margin: 1rem;
                padding: 1.35rem;
            }
        }

        @media (max-width: 768px) {
            .block-container {
                margin: 0.6rem;
                padding: 1rem;
            }

            .ui-page-header__icon {
                font-size: 1.8rem;
            }

            .ui-page-header__subtitle {
                font-size: var(--fs-base);
            }
        }

        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        header { visibility: hidden; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state["_design_css_loaded"] = True


def page_header(title: str, subtitle: str = "", icon: str = "") -> None:
    """Render a reusable animated page header."""
    title_html = _safe_text(title)
    subtitle_html = _safe_text(subtitle)
    icon_html = _safe_text(icon)
    subtitle_block = f'<p class="ui-page-header__subtitle">{subtitle_html}</p>' if subtitle else ""

    st.markdown(
        f"""
        <div class="ui-page-header">
            <div class="ui-page-header__row">
                <span class="ui-page-header__icon">{icon_html}</span>
                <div>
                    <h1 class="ui-page-header__title">{title_html}</h1>
                    {subtitle_block}
                </div>
            </div>
            <div class="ui-page-header__rule"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def create_stat_card(title: str, value: str, icon: str, color: str = "primary") -> None:
    """Render an animated stat card with gradient accent."""
    color_map = {
        "primary": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
        "success": "linear-gradient(135deg, #11998e 0%, #38ef7d 100%)",
        "warning": "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)",
        "info": "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)",
        "danger": "linear-gradient(135deg, #eb3349 0%, #f45c43 100%)",
    }
    gradient = color_map.get(color, color_map["primary"])
    title_html = _safe_text(title)
    value_html = _safe_text(value)
    icon_html = _safe_text(icon)

    st.markdown(
        f"""
        <div class="ui-stat-card" style="--card-gradient: {gradient};">
            <div class="ui-stat-card__top">
                <div>
                    <p class="ui-stat-card__label">{title_html}</p>
                    <p class="ui-stat-card__value">{value_html}</p>
                </div>
                <div class="ui-stat-card__icon">{icon_html}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_loading(message: str = "Processing...") -> None:
    """Render an animated loading indicator."""
    message_html = _safe_text(message)
    st.markdown(
        f"""
        <div class="ui-loading-wrap">
            <div class="ui-loading-spinner"></div>
            <p class="ui-loading-label">{message_html}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_alert(message: str, level: str = "success") -> None:
    """Render an animated gradient alert banner."""
    config = {
        "success": ("ui-alert--success", "✅"),
        "error": ("ui-alert--error", "❌"),
        "warning": ("ui-alert--warning", "⚠️"),
        "info": ("ui-alert--info", "ℹ️"),
    }
    cls, icon = config.get(level, config["info"])
    message_html = _safe_text(message)
    icon_html = _safe_text(icon)
    st.markdown(
        f"""
        <div class="ui-alert {cls}">
            <span style="font-size: 1.2rem;">{icon_html}</span>
            <span>{message_html}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_progress(percentage: float, label: str = "") -> None:
    """Render an animated custom progress bar."""
    pct = max(0, min(100, int(round(float(percentage)))))
    label_html = _safe_text(label)
    label_block = f'<p class="ui-progress-label">{label_html}</p>' if label else ""
    st.markdown(
        f"""
        <div class="ui-progress-wrap">
            {label_block}
            <div class="ui-progress-track">
                <div class="ui-progress-value" style="width: {pct}%;"></div>
            </div>
            <p class="ui-progress-percent">{pct}%</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def file_upload_zone(label: str, file_types: Iterable[str], key: str):
    """Render a branded upload zone and return Streamlit uploader object."""
    clean_types = [str(item).lower().lstrip(".") for item in file_types]
    if not clean_types:
        clean_types = ["txt"]
    safe_label = _safe_text(label)
    supported = ", ".join(t.upper() for t in clean_types)
    supported_html = _safe_text(supported)

    st.markdown(
        f"""
        <div class="ui-upload-zone">
            <div class="ui-upload-zone__icon">📤</div>
            <p class="ui-upload-zone__title">{safe_label}</p>
            <p class="ui-upload-zone__hint">Drag and drop or click below to browse</p>
            <p class="ui-upload-zone__types">Supported: {supported_html}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return st.file_uploader(
        label=f"{label} ({supported})",
        type=clean_types,
        key=key,
        label_visibility="collapsed",
    )


def button_group(buttons: list[dict], key_prefix: str = "btn") -> list[bool]:
    """Create equal-width action buttons with optional icons."""
    if not buttons:
        return []
    cols = st.columns(len(buttons))
    clicked: list[bool] = []
    for idx, (col, cfg) in enumerate(zip(cols, buttons)):
        with col:
            label = str(cfg.get("label", "")).strip()
            icon = str(cfg.get("icon", "")).strip()
            text = f"{icon} {label}".strip()
            clicked.append(st.button(text, key=f"{key_prefix}_{idx}", use_container_width=True))
    return clicked


def toggle_dark_mode() -> bool:
    """Sidebar dark mode toggle with lightweight overrides."""
    if "dark_mode" not in st.session_state:
        st.session_state["dark_mode"] = False

    with st.sidebar:
        st.session_state["dark_mode"] = st.toggle("Dark Mode", value=st.session_state["dark_mode"])

    if st.session_state["dark_mode"]:
        st.markdown(
            """
            <style>
            [data-testid="stAppViewContainer"] {
                background: linear-gradient(135deg, #0f172a 0%, #1f2937 50%, #111827 100%) !important;
            }

            .block-container {
                background: rgba(17, 24, 39, 0.95) !important;
                color: #E5E7EB !important;
            }

            p, label, span, li, .stCaption, .stMarkdown {
                color: #D1D5DB !important;
            }

            .ui-page-header__subtitle {
                color: #9CA3AF !important;
            }

            .ui-stat-card {
                background: rgba(31, 41, 55, 0.9) !important;
                border-color: rgba(148, 163, 184, 0.15) !important;
            }

            [data-baseweb="tab"] {
                color: #D1D5DB !important;
            }

            [data-baseweb="tab"][aria-selected="true"] {
                color: #FFFFFF !important;
            }

            .streamlit-expanderHeader {
                background: rgba(55, 65, 81, 0.7) !important;
                color: #E5E7EB !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
    return bool(st.session_state["dark_mode"])

