"""Shared UI: filters, status cards, colour-highlighted tables, Excel export. Numbers only, no charts."""
import hashlib
import re
import html
import io
from datetime import timedelta
import numpy as np
import pandas as pd
import streamlit as st
from . import db, metrics as M, insights as I, export as E

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
    st.session_state["_reg"], st.session_state["_kpi"], st.session_state["_sec"] = [], [], ""


def topbar(title, f, days=None):
    sub = f"{f['platform']}  ·  {f['city']}  ·  {f['d1']:%d %b %Y} → {f['d2']:%d %b %Y}"
    if days is not None:
        sub += f"  ·  {days} days"
    st.markdown(f'<div class="topbar"><div class="t1">{html.escape(title)}</div><div class="t2">{sub}</div></div>',
                unsafe_allow_html=True)


def legend():
    pass


def section(title, note=""):
    st.session_state["_sec"] = title
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
    st.session_state.setdefault("_kpi", []).append({"Section": st.session_state.get("_sec", ""), "Metric": re.sub("<[^>]+>", "", str(label)), "Value": re.sub("<[^>]+>", "", str(value)), "Change": str(sub), "Target": str(hint)})
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


BUILD = "31 Oct 2026 · v17"
_DEFER = "callable" in (st.download_button.__doc__ or "")
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _data(fn):
    return fn if _DEFER else fn()


def _subtitle():
    f = filters()
    return f"{f['platform']}  ·  {f['city']}  ·  {f['d1']:%d %b %Y} → {f['d2']:%d %b %Y}" if f else ""


def export_row(df, name, key, title="", rules=None, first_row=False, text_cols=None, tone=None):
    """Excel + PDF buttons for one table (also registered for the whole-page export)."""
    blk = dict(title=title or st.session_state.get("_sec") or name, df=df, rules=rules, first_row=first_row, text_cols=text_cols, tone=tone)
    st.session_state.setdefault("_reg", []).append(blk)
    c1, c2, c3 = st.columns([1, 1, 5], gap="small")
    with c1:
        st.download_button("⬇ Excel", _data(lambda: E.xlsx_bytes([blk])), file_name=f"{name}.xlsx", key=key + "_x", mime=_XLSX)
    with c2:
        if E.HAS_PDF:
            st.download_button("⬇ PDF", _data(lambda: E.pdf_bytes([blk], blk["title"], _subtitle())), file_name=f"{name}.pdf", key=key + "_p", mime="application/pdf")
        else:
            st.caption("PDF off: add reportlab to requirements.txt")
    c3.caption(f"{len(df):,} rows")


def page_export():
    """Whole-page Excel / PDF in the sidebar (every table + the key numbers of the current page)."""
    reg, kp = st.session_state.get("_reg", []), st.session_state.get("_kpi", [])
    f = filters()
    st.sidebar.caption(f"Build {BUILD}")
    if not f or not (reg or kp):
        return
    blocks = ([dict(title="Key numbers", df=pd.DataFrame(kp))] if kp else []) + reg
    name = f"report_{f['platform']}_{f['d1']:%Y%m%d}_{f['d2']:%Y%m%d}"
    with st.sidebar:
        st.markdown("### Export this page")
        st.download_button("⬇ All tables, Excel", _data(lambda: E.xlsx_bytes(blocks)), file_name=f"{name}.xlsx", key="pg_x", mime=_XLSX, use_container_width=True)
        if E.HAS_PDF:
            st.download_button("⬇ All tables, PDF", _data(lambda: E.pdf_bytes(blocks, "Ops report", _subtitle())), file_name=f"{name}.pdf", key="pg_p",
                               mime="application/pdf", use_container_width=True)
        else:
            st.caption("PDF is off: add reportlab to requirements.txt")


def table(df, name, key, height=None, export=True, rules=None, first_row=False, text_cols=None):
    h = height or min(740, 38 + 35 * (len(df) + 1))
    st.dataframe(styled(df, rules, first_row, text_cols), width="stretch", hide_index=True, height=h)
    export_row(df, name, key, rules=rules, first_row=first_row, text_cols=text_cols)


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
import json
from pathlib import Path

ALIAS_FILE = Path(__file__).resolve().parent.parent / "city_alias.json"


def alias():
    try:
        a = json.loads(ALIAS_FILE.read_text())
    except Exception:
        a = {}
    return {"rename": a.get("rename", {}), "hidden": a.get("hidden", [])}


def save_alias(rename, hidden):
    ALIAS_FILE.write_text(json.dumps({"rename": rename, "hidden": hidden}, ensure_ascii=False, indent=1))
    try:
        from . import backup
        backup.push_text("city_alias.json", ALIAS_FILE.read_text())
    except Exception:
        pass


def meta():
    """db.meta() with city renames and hidden cities applied. `real` keeps the stored name."""
    m = db.meta()
    if m.empty:
        return m
    A = alias()
    m = m[~m["city"].isin(A["hidden"])].copy()
    m["real"] = m["city"]
    m["city"] = m["city"].map(lambda c: A["rename"].get(c) or c)
    return m


def disp_names(names):
    A = alias()
    return sorted({A["rename"].get(c) or c for c in names if c not in A["hidden"]})


def real_city(platform, display):
    m = meta()
    r = m[(m["platform"] == platform) & (m["city"] == display)]["real"].unique() if not m.empty else []
    return r[0] if len(r) else display


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
    m = meta()
    for c in cities:
        reals = m[(m["platform"] == platform) & (m["city"] == c)]["real"].unique() if not m.empty else [c]
        for r in (reals if len(reals) else [c]):
            x = db.load(kind, platform, r, d1, d2)
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
    m = meta()
    if m.empty:
        return None
    with st.sidebar:
        st.markdown("### Filters")
        plats = sorted(m["platform"].unique())
        platform = _seg("Platform", plats, plats[0], "f_platform") if len(plats) > 1 else plats[0]
        mm = m[m["platform"] == platform]
        allc = sorted(mm["city"].unique())
        sel = _multi("Cities", allc, f"f_cities_{platform}_{hashlib.md5('|'.join(allc).encode()).hexdigest()[:8]}") or allc
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
        f = dict(platform=platform, city=label, cities=cities, d1=d1, d2=d2, sup=(), ctype=(), veh=(), dmin=dmin, dmax=dmax)
        if not full.empty:
            with st.expander("More filters"):
                f["sup"] = tuple(st.multiselect("Supervisor", sorted(full["supervisor"].dropna().unique()), key="f_sup"))
                f["ctype"] = tuple(st.multiselect("Courier type", sorted(full["courier_type"].dropna().unique()), key="f_ctype"))
                f["veh"] = tuple(st.multiselect("Vehicle type", sorted(full["vehicle_type"].dropna().unique()), key="f_veh"))
    st.session_state["filters"] = f
    return f


def filters():
    return st.session_state.get("filters")


_SUM = ["delivered", "accepted", "rejected", "rejected_courier", "rejected_auto", "large_orders", "overdue", "severe_overdue",
        "valid_online_sec", "app_online_sec", "peak_online_sec"]
_MAX = ["shifts_scheduled", "shifts_qualified"]


def merge_ids(d):
    """The courier ID is the identity. Same ID on the same day (two registrations) becomes ONE row with everything added up,
    and every row of an ID carries the name of its latest working day."""
    if d is None or d.empty or "courier_id" not in d.columns:
        return d
    from .config import SLOT_COLS
    d = d.copy()
    d["courier_id"] = d["courier_id"].astype(str).str.strip()
    for c in _SUM + _MAX:
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0)
    d = d.sort_values(["date"] + [c for c in ("delivered", "valid_online_sec") if c in d.columns], kind="stable")
    if d.duplicated(["date", "courier_id"]).any():
        d["_wo"] = pd.to_numeric(d.get("ontime_rate"), errors="coerce") * d["delivered"]
        d["_wa"] = pd.to_numeric(d.get("avg_delivery_min"), errors="coerce") * d["delivered"]
        d["_wd"] = pd.to_numeric(d.get("cancel_rate_di"), errors="coerce") * d["accepted"]
        agg = {}
        for c in d.columns:
            if c in ("date", "courier_id"):
                continue
            if c in _SUM or c in ("_wo", "_wa", "_wd"):
                agg[c] = "sum"
            elif c in _MAX:
                agg[c] = "max"
            elif c in SLOT_COLS:
                agg[c] = lambda s: "qualified" if (s == "qualified").any() else ("unqualified" if (s == "unqualified").any() else "off")
            else:
                agg[c] = "last"
        g = d.groupby(["date", "courier_id"], sort=False).agg(agg).reset_index()
        dl, ac = g["delivered"].where(g["delivered"] > 0), g["accepted"].where(g["accepted"] > 0)
        if "ontime_rate" in g:
            g["ontime_rate"] = (g["_wo"] / dl).fillna(g["ontime_rate"])
        if "avg_delivery_min" in g:
            g["avg_delivery_min"] = (g["_wa"] / dl).fillna(g["avg_delivery_min"])
        if "cancel_rate_di" in g:
            g["cancel_rate_di"] = (g["_wd"] / ac).fillna(g["cancel_rate_di"])
        d = g.drop(columns=["_wo", "_wa", "_wd"]).sort_values("date", kind="stable")
    if "first_name" in d.columns:
        active = d[(d["delivered"] > 0) | (d.get("valid_online_sec", 0) > 0)]
        last = pd.concat([d.drop_duplicates("courier_id", keep="last"), active.drop_duplicates("courier_id", keep="last")]).drop_duplicates("courier_id", keep="last").set_index("courier_id")
        for c in ("first_name", "last_name"):
            if c in d.columns:
                d[c] = d["courier_id"].map(last[c])
    return d.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def couriers(platform, cities, d1, d2, sup, ctype, veh):
    d = _load("courier", platform, cities, d1, d2)
    if d.empty:
        return d
    d = merge_ids(d)
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
