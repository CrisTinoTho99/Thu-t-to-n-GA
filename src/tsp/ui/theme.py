"""Small, consistent dashboard design system."""
import html
import streamlit as st


def apply_theme() -> None:
    """Style native Streamlit widgets without hiding their labels or controls."""
    st.markdown("""<style>
    .stApp {background: #0b1120;}
    .block-container {padding-top: 2rem; padding-bottom: 2rem; max-width: 1540px;}
    [data-testid="stSidebar"] {background:#111827;border-right:1px solid #233047;}
    [data-testid="stSidebar"] .block-container {padding-top:1.5rem;}
    h1 {font-size:2.1rem!important;letter-spacing:-.055rem;font-weight:750!important;}
    h2 {font-size:1.25rem!important;letter-spacing:-.02rem;}
    h3 {font-size:1.05rem!important;}
    [data-testid="stVerticalBlockBorderWrapper"]>div {border-radius:14px!important;}
    [data-testid="stMetric"] {padding:18px 21px;background:#111b2c;border:1px solid #243148;border-radius:13px;}
    [data-testid="stMetricLabel"] {color:#94a3b8;}
    [data-testid="stMetricValue"] {font-size:1.85rem;font-weight:700;}
    [data-testid="stCaptionContainer"] {color:#94a3b8;}
    .brand {display:flex;gap:11px;align-items:center;margin:4px 0 22px;}
    .brand-icon {background:#6366f1;border-radius:12px;color:white;width:42px;height:42px;display:grid;place-items:center;font-size:27px;}
    .brand-title {font-weight:750;font-size:18px;letter-spacing:-.4px;}
    .brand-sub {color:#94a3b8;font-size:11px;letter-spacing:1.5px;}
    .eyebrow {color:#a5b4fc;font-size:11px;font-weight:700;letter-spacing:1.8px;margin-bottom:9px;}
    .badge {display:inline-flex;padding:5px 10px;border-radius:20px;background:#162d30;color:#6ee7b7;font-size:12px;border:1px solid #23524c;}
    .route-step {display:inline-block;padding:5px 9px;background:#1e293b;border:1px solid #334155;border-radius:6px;font-size:12px;margin:3px;}
    .route-arrow {color:#64748b;font-size:11px;}
    .note {font-size:13px;color:#94a3b8;line-height:1.65;}
    .small-label {font-size:11px;color:#94a3b8;letter-spacing:1px;text-transform:uppercase;}
    div.stButton>button[kind="primary"],div.stFormSubmitButton>button[kind="primary"] {border:0;border-radius:9px;font-weight:650;}
    [data-testid="stSidebar"] [data-testid="stRadio"] label {font-size:14px;}
    @media(max-width:760px){.block-container{padding:1.2rem .8rem;} h1{font-size:1.65rem!important;}}
    </style>""", unsafe_allow_html=True)


def brand() -> None:
    st.markdown('<div class="brand"><div class="brand-icon">⌘</div><div><div class="brand-title">Route / AI</div><div class="brand-sub">OPTIMIZATION STUDIO</div></div></div>', unsafe_allow_html=True)


def header(title: str, description: str) -> None:
    left, right = st.columns([5, 1])
    with left:
        st.markdown('<div class="eyebrow">TSP AI ROUTE OPTIMIZER / WORKSPACE</div>', unsafe_allow_html=True)
        st.title(title)
        st.caption(description)
    with right:
        st.markdown('<span class="badge">● Local engine ready</span>', unsafe_allow_html=True)


def route_chips(names: list[str]) -> None:
    """Render route order safely even for uploaded labels."""
    st.markdown('<span class="route-arrow"> → </span>'.join(
        f'<span class="route-step">{html.escape(str(name))}</span>' for name in names
    ), unsafe_allow_html=True)
