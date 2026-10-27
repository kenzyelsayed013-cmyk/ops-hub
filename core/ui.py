"""Shared UI: filters, status cards, colour-highlighted tables, Excel export. Numbers only, no charts."""
import html
import io
from datetime import timedelta
import numpy as np
import pandas as pd
import streamlit as st
from . import db, metrics as M, insights as I

pd.set_option("styler.render.max_elements", 5_000_000)

CSS = """
<style>
#MainMenu, footer, [data-testid="stMainMenu"], [data-testid="stToolbarActions"], [data-testid="stAppDeployButton"],
[data-testid="stDeployButton"], [data-testid="stStatusWidget"], [data-testid="stDecoration"],
[class*="viewerBadge"], [class*="ViewerBadge"], [data-testid="manage-app-button"], .stAppDeployButton {display:none !important;}
[data-testid="stToolbar"] {display:flex !important; visibility:visible !important;}
[data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"], [data-testid="stSidebarNav"] {display:flex !important; visibility:visible !important;}
header[data-testid="stHeader"] {background:transparent !important;}
.block-container {padding-top: 1.2rem; max-width: 1600px;}
.topbar {background:#14181F; color:#fff; padding:16px 24px; border-radius:8px; margin-bottom:10px; border-bottom:5px solid #FFC400;}
.topbar .t1 {font-size:1.5rem; font-weight:800; letter-spacing:.02em;}
.topbar .t2 {font-size:.88rem; color:#C9CED6; margin-top:3px;}
.legend {display:flex; gap:14px; flex-wrap:wrap; font-size:.8rem; font-weight:700; margin:6px 0 4px;}
.legend span {padding:3px 12px; border-radius:20px;}
.lg-good {background:#DCFCE7; color:#14532D;} .lg-warn {background:#FEF3C7; color:#78350F;} .lg-bad {background:#FEE2E2; color:#7F1D1D;}
.sec {background:#FFC400; color:#14181F; font-weight:800; font-size:1.05rem; padding:9px 16px; border-radius:6px; margin:30px 0 4px;}
.secnote {color:#4B5563; font-size:.86rem; margin:0 0 10px 2px;}
.kc {background:#fff; border:1px solid #E5E7EB; border-left:9px solid #9CA3AF; border-radius:8px; padding:12px 14px; min-height:132px; margin-bottom:8px;}
.kc.good {border-left-color:#16A34A; background:#F0FDF4;} .kc.warn {border-left-color:#F59E0B; background:#FFFBEB;}
.kc.bad {border-left-color:#DC2626; background:#FEF2F2;}
.kl {display:flex; justify-content:space-between; align-items:center; gap:6px; font-size:.78rem; font-weight:700; color:#374151;}
.tag {font-size:.62rem; font-weight:800; padding:2px 8px; border-radius:10px; white-space:nowrap;}
.tag.good {background:#16A34A; color:#fff;} .tag.warn {background:#F59E0B; color:#fff;} .tag.bad {background:#DC2626; color:#fff;}
.kv {font-size:2.15rem; font-weight:900; color:#14181F; line-height:1.15; margin:5px 0 2px;}
.kd {font-size:.82rem; font-weight:800; min-height:1.1rem;} .kd.up {color:#15803D;} .kd.down {color:#B91C1C;}
.kh {font-size:.72rem; color:#6B7280; margin-top:3px;}
.verdict {border-radius:10px; padding:18px 24px; margin:10px 0 6px; color:#fff;}
.verdict.bad {background:#DC2626;} .verdict.warn {background:#D97706;} .verdict.good {background:#16A34A;}
.verdict .v1 {font-size:1.6rem; font-weight:900;} .verdict .v2 {font-size:1rem; margin-top:4px; opacity:.95;}
.act {border-radius:8px; padding:12px 16px; margin:8px 0; border:1px solid #E5E7EB; border-left:9px solid #9CA3AF;}
.act.bad {background:#FEF2F2; border-left-color:#DC2626;} .act.warn {background:#FFFBEB; border-left-color:#F59E0B;}
.act.good {background:#F0FDF4; border-left-color:#16A34A;}
.act .ah {font-size:1.05rem; font-weight:800; color:#14181F;}
.act .ae {font-size:.95rem; margin-top:5px; color:#1F2937;}
.act .aa {font-size:.92rem; margin-top:6px; font-weight:700; color:#14181F;}
.note {background:#F3F4F6; border-left:5px solid #FFC400; padding:8px 14px; border-radius:4px; font-size:.86rem; color:#374151; margin:6px 0 10px;}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def topbar(title, f, days=None):
    sub = f"{f['platform']}  ·  {f['city']}  ·  {f['d1']:%d %b %Y} → {f['d2']:%d %b %Y}"
    if days is not None:
        sub += f"  ·  {days} days"
    st.markdown(f'<div class="topbar"><div class="t1">{html.escape(title)}</div><div class="t2">{sub}</div></div>',
                unsafe_allow_html=True)


def legend():
    st.markdown('<div class="legend"><span class="lg-good">Green: on target</span><span class="lg-warn">Amber: watch</span>'
                '<span class="lg-bad">Red: act now</span></div>', unsafe_allow_html=True)


def section(title, note=""):
    st.markdown(f'<div class="sec">{html.escape(title)}</div>', unsafe_allow_html=True)


def note(text):
    pass


# ---------------------------------------------------------------- cards
def delta_txt(cur, prev, kind):
    if cur is None or prev is None or pd.isna(cur) or pd.isna(prev):
        return None
    if kind == "rate":
        return f"{(cur - prev) * 100:+.2f} pp vs prev"
    if prev == 0:
        return None
    return f"{(cur - prev) / abs(prev) * 100:+.1f}% vs prev"


def card(col, label, value, sub="", status="neutral", hint="", subcls=""):
    tag = f'<span class="tag {status}">{I.TAGS[status]}</span>' if status in I.TAGS else ""
    col.markdown(f'<div class="kc {status}"><div class="kl"><span>{label}</span>{tag}</div><div class="kv">{value}</div>'
                 f'<div class="kd {subcls}">{sub}</div><div class="kh">{hint}</div></div>', unsafe_allow_html=True)


def kpi(col, label, cur, prev, fmt="{:,.0f}", kind="num", bad_up=False, key=None):
    val = "–" if cur is None or pd.isna(cur) else fmt.format(cur)
    sub, cls = "", ""
    dt = delta_txt(cur, prev, kind)
    if dt:
        diff = cur - prev
        if diff != 0:
            good = (diff < 0) if bad_up else (diff > 0)
            cls = "up" if good else "down"
        sub = f"{'▲' if diff > 0 else ('▼' if diff < 0 else '=')} {dt}"
    hint = (I.target_hint(key) + "  ·  " + I.gap_txt(key, cur)) if key and I.target_hint(key) else ""
    card(col, label, val, sub, I.status(key, cur) if key else "neutral", hint, cls)


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


# ---------------------------------------------------------------- highlighted tables
_TONE = {"good": "background-color:#DCFCE7;color:#14532D;font-weight:700",
         "warn": "background-color:#FEF3C7;color:#78350F;font-weight:700",
         "bad": "background-color:#FEE2E2;color:#7F1D1D;font-weight:700"}


def _fmt(v):
    if not I.is_num(v):
        return "–" if v is None or (isinstance(v, float) and pd.isna(v)) else v
    if isinstance(v, (int, np.integer)):
        return f"{v:,}"
    return f"{v:,.0f}" if abs(v) >= 1000 else (f"{v:,.2f}" if abs(v) < 100 else f"{v:,.1f}")


def _pct(v):
    return f"{v:.1f}%" if I.is_num(v) else "–"


def rnd(df, nd=2):
    out = df.copy()
    for c in out.select_dtypes("float").columns:
        out[c] = out[c].round(nd)
    return out


def styled(df, rules=None, first_row=False, text_cols=None):
    rl = {**I.TABLE_RULES, **(rules or {})}
    rl = {c: r for c, r in rl.items() if c in df.columns}
    sty = df.style.format(_fmt)
    pcts = [c for c in df.columns if str(c).endswith("%")]
    if pcts:
        sty = sty.format(_pct, subset=pcts)
    mp = sty.map if hasattr(sty, "map") else sty.applymap
    if first_row:
        sty = sty.apply(lambda r: ["font-weight:800;background-color:#14181F;color:#fff"] * len(r) if r.name == 0
                        else [""] * len(r), axis=1)
    for c, r in rl.items():
        mp(lambda v, r=r: _TONE.get(I.grade(v, *r), ""), subset=[c])
    tc = [c for c in (text_cols or ["Status", "Segment"]) if c in df.columns]
    if tc:
        mp(lambda v: _TONE.get(I.tone_of_text(v), ""), subset=tc)
    return sty


def table(df, name, key, height=None, export=True, rules=None, first_row=False, text_cols=None):
    h = height or min(740, 38 + 35 * (len(df) + 1))
    st.dataframe(styled(df, rules, first_row, text_cols), width="stretch", hide_index=True, height=h)
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


# ---------------------------------------------------------------- admin (upload is hidden from managers)
def is_admin():
    """Upload page is invisible unless the URL has ?admin=1 (and ADMIN_PASSWORD matches, if set in secrets)."""
    if st.session_state.get("is_admin"):
        return True
    if st.query_params.get("admin") != "1":
        return False
    try:
        apw = st.secrets.get("ADMIN_PASSWORD")
    except Exception:
        apw = None
    if not apw:
        st.session_state["is_admin"] = True
        return True
    p = st.sidebar.text_input("Admin password", type="password", key="adm_pw")
    if p and p == apw:
        st.session_state["is_admin"] = True
        st.rerun()
    return False


# ---------------------------------------------------------------- global filters (sidebar)
PRESETS = {"7 days": 7, "14 days": 14, "30 days": 30, "All": None, "Custom": 0}


def _dates(v):
    if isinstance(v, (tuple, list)):
        if len(v) == 2:
            return v
        if len(v) == 1:
            return v[0], v[0]
    return v, v


def _load(kind, platform, cities, d1, d2):
    fr = []
    for c in cities:
        x = db.load(kind, platform, c, d1, d2)
        if not x.empty:
            fr.append(x.assign(city=c))
    return pd.concat(fr, ignore_index=True) if fr else pd.DataFrame()


def _multi(label, opts, key):
    if hasattr(st, "pills"):
        return list(st.pills(label, opts, selection_mode="multi", default=opts, key=key) or [])
    return st.multiselect(label, opts, default=opts, key=key)


def _seg(label, opts, default, key):
    if hasattr(st, "pills"):
        return st.pills(label, opts, selection_mode="single", default=default, key=key) or default
    return st.radio(label, opts, index=opts.index(default), horizontal=True, key=key)


def render_filters():
    """Filters live in the sidebar. Cities and period are buttons, not dropdowns."""
    m = db.meta()
    if m.empty:
        return None
    with st.sidebar:
        st.markdown("### Filters")
        plats = sorted(m["platform"].unique())
        platform = _seg("Platform", plats, plats[0], "f_platform") if len(plats) > 1 else plats[0]
        mm = m[m["platform"] == platform]
        allc = sorted(mm["city"].unique())
        sel = _multi("Cities", allc, f"f_cities_{platform}") or allc
        rows = mm[mm["city"].isin(sel)]
        dmin, dmax = pd.to_datetime(rows["dmin"]).min().date(), pd.to_datetime(rows["dmax"]).max().date()
        label = "All cities" if len(sel) == len(allc) and len(sel) > 1 else ", ".join(sel)
        preset = _seg("Period", list(PRESETS), "7 days", "f_preset")
        if preset == "Custom":
            d1, d2 = _dates(st.date_input("From → to", value=(dmin, dmax), min_value=dmin, max_value=dmax,
                                          key=f"f_dates_{platform}_{label}"))
        else:
            n = PRESETS[preset]
            d2 = dmax
            d1 = dmin if n is None else max(dmin, d2 - timedelta(days=n - 1))
        st.caption(f"{d1:%d %b} → {d2:%d %b %Y}  ·  latest data {dmax:%d %b}")
        cities = tuple(sel)
        full = _load("courier", platform, cities, d1, d2)
        f = dict(platform=platform, city=label, cities=cities, d1=d1, d2=d2, sup=(), ctype=(), veh=(), dmax=dmax)
        if not full.empty:
            with st.expander("More filters"):
                f["sup"] = tuple(st.multiselect("Supervisor", sorted(full["supervisor"].dropna().unique()), key="f_sup"))
                f["ctype"] = tuple(st.multiselect("Courier type", sorted(full["courier_type"].dropna().unique()), key="f_ctype"))
                f["veh"] = tuple(st.multiselect("Vehicle type", sorted(full["vehicle_type"].dropna().unique()), key="f_veh"))
    st.session_state["filters"] = f
    return f


def filters():
    return st.session_state.get("filters")


@st.cache_data(show_spinner=False)
def couriers(platform, cities, d1, d2, sup, ctype, veh):
    d = _load("courier", platform, cities, d1, d2)
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
def company(platform, cities, d1, d2, ctype):
    d = _load("company", platform, cities, d1, d2)
    if d.empty:
        return d
    return d[d["courier_type"].isin(ctype)] if ctype else d


def get_couriers():
    f = filters()
    return couriers(f["platform"], f["cities"], f["d1"], f["d2"], f["sup"], f["ctype"], f["veh"])


def get_company():
    f = filters()
    return company(f["platform"], f["cities"], f["d1"], f["d2"], f["ctype"])


def get_company_prev():
    f = filters()
    n = (f["d2"] - f["d1"]).days + 1
    p2 = f["d1"] - timedelta(days=1)
    p1 = p2 - timedelta(days=n - 1)
    return company(f["platform"], f["cities"], p1, p2, f["ctype"])
