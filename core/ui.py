"""عناصر واجهة مشتركة: فلاتر عامة، تصدير Excel، جداول، شارتات."""
import io
import pandas as pd
import plotly.express as px
import streamlit as st
from . import db, metrics as M

CSS = """
<style>
p, label, h1, h2, h3, h4, li, .stMarkdown, [data-testid="stCaptionContainer"] {unicode-bidi: plaintext; text-align: start;}
[data-testid="stMetricValue"] {font-size: 1.55rem;}
.block-container {padding-top: 2.2rem;}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------- excel
def xlsx_bytes(sheets: dict) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for name, df in sheets.items():
            df = df.copy()
            for c in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[c]):
                    df[c] = df[c].dt.date
            df.to_excel(xw, sheet_name=str(name)[:31], index=False)
            ws = xw.sheets[str(name)[:31]]
            ws.freeze_panes = "A2"
            for i, c in enumerate(df.columns, 1):
                width = min(40, max(10, len(str(c)) + 2))
                ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = width
    return buf.getvalue()


def download(label, sheets, filename, key):
    if isinstance(sheets, pd.DataFrame):
        sheets = {"data": sheets}
    st.download_button(f"⬇️ {label}", xlsx_bytes(sheets), file_name=f"{filename}.xlsx", key=key,
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def rnd(df, nd=2):
    out = df.copy()
    for c in out.select_dtypes("float").columns:
        out[c] = out[c].round(nd)
    return out


def table(df, name, key, height=420):
    st.dataframe(rnd(df), width="stretch", hide_index=True, height=height)
    c1, c2 = st.columns([1, 4])
    with c1:
        download("تحميل Excel", rnd(df), name, key)
    with c2:
        st.caption(f"{len(df):,} صف")


# ---------------------------------------------------------------- charts
def line(df, x, ys, title="", names=None, bar=False, color=None, height=360):
    names = names or {}
    if color:
        fig = px.bar(df, x=x, y=ys[0], color=color, title=title, barmode="group") if bar else \
            px.line(df, x=x, y=ys[0], color=color, title=title, markers=True)
    else:
        long = df.melt(id_vars=[x], value_vars=ys, var_name="metric", value_name="value")
        long["metric"] = long["metric"].map(lambda m: names.get(m, M.LABELS.get(m, m)))
        fig = px.bar(long, x=x, y="value", color="metric", title=title) if bar else \
            px.line(long, x=x, y="value", color="metric", title=title, markers=True)
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=50, b=10), legend_title_text="",
                      legend=dict(orientation="h", y=-0.2))
    fig.update_xaxes(title=None)
    fig.update_yaxes(title=None)
    return fig


# ---------------------------------------------------------------- global filters
def _dates(v):
    if isinstance(v, (tuple, list)):
        if len(v) == 2:
            return v
        if len(v) == 1:
            return v[0], v[0]
    return v, v


def render_filters():
    """بتترسم في الـ sidebar من app.py (فبتفضل ثابتة بين الصفحات). بترجع dict أو None لو مفيش داتا."""
    m = db.meta()
    if m.empty:
        return None
    sb = st.sidebar
    sb.markdown("### 🎛️ الفلاتر")
    platform = sb.selectbox("المنصة", sorted(m["platform"].unique()), key="f_platform")
    mm = m[m["platform"] == platform]
    city = sb.selectbox("المدينة", sorted(mm["city"].unique()), key="f_city")
    row = mm[mm["city"] == city].iloc[0]
    dr = sb.date_input("الفترة", value=(row.dmin, row.dmax), min_value=row.dmin, max_value=row.dmax,
                       key=f"f_dates_{platform}_{city}")
    d1, d2 = _dates(dr)
    full = db.load("courier", platform, city, d1, d2)
    f = dict(platform=platform, city=city, d1=d1, d2=d2, sup=(), ctype=(), veh=())
    if not full.empty:
        f["sup"] = tuple(sb.multiselect("المشرف", sorted(full["supervisor"].dropna().unique()), key="f_sup"))
        f["ctype"] = tuple(sb.multiselect("نوع المندوب", sorted(full["courier_type"].dropna().unique()), key="f_ctype"))
        f["veh"] = tuple(sb.multiselect("نوع المركبة", sorted(full["vehicle_type"].dropna().unique()), key="f_veh"))
    st.session_state["filters"] = f
    return f


def filters():
    return st.session_state.get("filters")


@st.cache_data(show_spinner=False)
def couriers(platform, city, d1, d2, sup, ctype, veh):
    d = db.load("courier", platform, city, d1, d2)
    if d.empty:
        return d
    if sup:
        d = d[d["supervisor"].isin(sup)]
    if ctype:
        d = d[d["courier_type"].isin(ctype)]
    if veh:
        d = d[d["vehicle_type"].isin(veh)]
    return M.prep_couriers(d)


@st.cache_data(show_spinner=False)
def company(platform, city, d1, d2, ctype):
    d = db.load("company", platform, city, d1, d2)
    if d.empty:
        return d
    return d[d["courier_type"].isin(ctype)] if ctype else d


def get_couriers():
    f = filters()
    return couriers(f["platform"], f["city"], f["d1"], f["d2"], f["sup"], f["ctype"], f["veh"])


def get_company():
    f = filters()
    return company(f["platform"], f["city"], f["d1"], f["d2"], f["ctype"])
