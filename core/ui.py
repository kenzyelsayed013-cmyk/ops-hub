"""Shared UI: global filters, header bar, section bars, KPI cards, Excel export, charts."""
import io
from datetime import timedelta
import pandas as pd
import plotly.express as px
import streamlit as st
from . import db, metrics as M

CSS = """
<style>
.block-container {padding-top: 1.6rem; max-width: 1500px;}
.topbar {background:#14181F; color:#fff; padding:14px 22px; border-radius:6px; margin-bottom:10px;}
.topbar .t1 {font-size:1.35rem; font-weight:800; letter-spacing:.05em;}
.topbar .t2 {font-size:.85rem; color:#C9CED6; margin-top:2px;}
.sec {background:#FFF1BF; color:#14181F; font-weight:800; padding:7px 14px; border-radius:4px;
      margin:24px 0 10px; letter-spacing:.03em;}
.sec span {font-weight:500; font-size:.8rem; color:#4B5563; margin-left:10px;}
.strip {display:flex; gap:8px; margin-bottom:8px;}
.strip > div {flex:1; background:#F3F4F6; border-radius:4px; padding:5px 10px; font-size:.68rem;
              font-weight:700; color:#4B5563; letter-spacing:.04em;}
.strip b {display:block; font-size:.95rem; padding:3px 8px; border-radius:3px; margin-top:3px; color:#14181F; background:#fff;}
.strip .f b {background:#FFC400;}
[data-testid="stMetricLabel"] p {font-size:.7rem; font-weight:700; letter-spacing:.03em; text-transform:uppercase; color:#4B5563;}
[data-testid="stMetricValue"] {font-weight:800; font-size:1.6rem;}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def topbar(title, f, days=None):
    sub = f"Platform: {f['platform']}   ·   City: {f['city']}   ·   Period: {f['d1']:%d %b %Y}  →  {f['d2']:%d %b %Y}"
    if days is not None:
        sub += f"   ·   {days} days"
    st.markdown(f'<div class="topbar"><div class="t1">{title}</div><div class="t2">{sub}</div></div>',
                unsafe_allow_html=True)


def strip(f, latest, days_txt):
    cells = [("PLATFORM", f["platform"], True), ("CITY", f["city"], True), ("FROM", f"{f['d1']:%d %b %Y}", True),
             ("TO", f"{f['d2']:%d %b %Y}", True), ("LATEST DATA IN SHEET", latest, False),
             ("DAYS WITH DATA", days_txt, False)]
    html = "".join(f'<div class="{"f" if fl else ""}">{k}<b>{v}</b></div>' for k, v, fl in cells)
    st.markdown(f'<div class="strip">{html}</div>', unsafe_allow_html=True)
    st.caption("Filters (yellow) are controlled from the sidebar on the left.")


def section(title, note=""):
    n = f"<span>{note}</span>" if note else ""
    st.markdown(f'<div class="sec">{title}{n}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------- KPI cards
def delta_txt(cur, prev, kind):
    if cur is None or prev is None or pd.isna(cur) or pd.isna(prev):
        return None
    if kind == "rate":
        return f"{(cur - prev) * 100:+.2f} pp vs prev"
    if prev == 0:
        return None
    return f"{(cur - prev) / abs(prev) * 100:+.1f}% vs prev"


def kpi(col, label, cur, prev, fmt="{:,.0f}", kind="num", bad_up=False):
    val = "–" if cur is None or pd.isna(cur) else fmt.format(cur)
    col.metric(label, val, delta_txt(cur, prev, kind), delta_color="inverse" if bad_up else "normal", border=True)


# ---------------------------------------------------------------- excel
def xlsx_bytes(sheets: dict) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for name, df in sheets.items():
            df = df.copy()
            for c in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[c]):
                    df[c] = df[c].dt.date
            nm = str(name)[:31]
            df.to_excel(xw, sheet_name=nm, index=False)
            ws = xw.sheets[nm]
            ws.freeze_panes = "A2"
            for i, c in enumerate(df.columns, 1):
                ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = min(40, max(11, len(str(c)) + 2))
    return buf.getvalue()


def download(label, sheets, filename, key):
    if isinstance(sheets, pd.DataFrame):
        sheets = {"data": sheets}
    st.download_button(f"⬇ {label}", xlsx_bytes(sheets), file_name=f"{filename}.xlsx", key=key,
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def rnd(df, nd=2):
    out = df.copy()
    for c in out.select_dtypes("float").columns:
        out[c] = out[c].round(nd)
    return out


def table(df, name, key, height=None, export=True):
    h = height or min(740, 38 + 35 * (len(df) + 1))
    st.dataframe(rnd(df), width="stretch", hide_index=True, height=h)
    if export:
        c1, c2 = st.columns([1, 5])
        with c1:
            download("Export to Excel", rnd(df), name, key)
        with c2:
            st.caption(f"{len(df):,} rows")


def search(df, key, cols=("Courier ID", "Name")):
    q = st.text_input("Search by name or courier ID", key=key).strip().lower()
    if not q:
        return df
    m = False
    for c in cols:
        m = m | df[c].astype(str).str.lower().str.contains(q, regex=False)
    return df[m]


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


# ---------------------------------------------------------------- global filters (sidebar)
def _dates(v):
    if isinstance(v, (tuple, list)):
        if len(v) == 2:
            return v
        if len(v) == 1:
            return v[0], v[0]
    return v, v


def render_filters():
    m = db.meta()
    if m.empty:
        return None
    sb = st.sidebar
    sb.markdown("### FILTERS")
    platform = sb.selectbox("Platform", sorted(m["platform"].unique()), key="f_platform")
    mm = m[m["platform"] == platform]
    city = sb.selectbox("City", sorted(mm["city"].unique()), key="f_city")
    row = mm[mm["city"] == city].iloc[0]
    dr = sb.date_input("Period (from → to)", value=(row.dmin, row.dmax), min_value=row.dmin, max_value=row.dmax,
                       key=f"f_dates_{platform}_{city}")
    d1, d2 = _dates(dr)
    full = db.load("courier", platform, city, d1, d2)
    f = dict(platform=platform, city=city, d1=d1, d2=d2, sup=(), ctype=(), veh=(), dmax=row.dmax)
    if not full.empty:
        f["sup"] = tuple(sb.multiselect("Supervisor", sorted(full["supervisor"].dropna().unique()), key="f_sup"))
        f["ctype"] = tuple(sb.multiselect("Courier type", sorted(full["courier_type"].dropna().unique()), key="f_ctype"))
        f["veh"] = tuple(sb.multiselect("Vehicle type", sorted(full["vehicle_type"].dropna().unique()), key="f_veh"))
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


def get_company_prev():
    """Previous period of the same length, right before the selected one."""
    f = filters()
    n = (f["d2"] - f["d1"]).days + 1
    p2 = f["d1"] - timedelta(days=1)
    p1 = p2 - timedelta(days=n - 1)
    return company(f["platform"], f["city"], p1, p2, f["ctype"])
