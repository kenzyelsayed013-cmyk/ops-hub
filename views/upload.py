import json
import re
from pathlib import Path
import pandas as pd
import streamlit as st
from core import db, parsers, ui
from core.config import PLATFORMS, DEFAULT_CITIES

CITIES_FILE = Path(__file__).resolve().parent.parent / "cities.json"
_HEADERISH = ("order", "date", "courier", "total", "id", "name", "count", "rate", "time", "hour", "task", "number", "no.")
_LABEL = re.compile(r"^\s*(branch(?:\s*name|_name|\s*id)?|city|station|site)\s*([:：=])?\s*(.*)$", re.I)


def _saved():
    try:
        return [c for c in json.loads(CITIES_FILE.read_text()) if c]
    except Exception:
        return []


def _remember(name):
    cur = _saved()
    if name.lower() not in [c.lower() for c in cur]:
        try:
            CITIES_FILE.write_text(json.dumps(cur + [name], ensure_ascii=False))
        except Exception:
            pass


def _clean(v):
    return " ".join(str(v).split())


def _bad(s):
    return s == "" or s.lower() in ("nan", "none", "nat", "-", "branch", "city", "total", "all", "station", "site")


def detect_branch(f, parsed=None):
    """Find the branch name inside the Excel file. Returns (name or None, all distinct names found)."""
    if parsed is not None:
        for c in parsed.columns:
            if str(c).lower() in ("branch", "branch_name", "branch name", "city", "station", "site"):
                v = parsed[c].dropna().astype(str).map(_clean)
                v = v[~v.map(_bad)]
                if len(v):
                    u = sorted(v.unique())
                    return (v.mode().iloc[0] if len(u) == 1 else None), u
    try:
        f.seek(0)
        raw = pd.read_excel(f, header=None, sheet_name=None, nrows=300)
    except Exception:
        return None, []
    finally:
        try:
            f.seek(0)
        except Exception:
            pass
    for _, df in raw.items():
        for r in range(min(len(df), 25)):
            row = df.iloc[r]
            for c, cell in enumerate(row):
                if pd.isna(cell):
                    continue
                txt = _clean(cell)
                m = _LABEL.match(txt) if len(txt) <= 40 else None
                if not m:
                    continue
                if m.group(2) and m.group(3) and not _bad(_clean(m.group(3))):      # "Branch: Jeddah"
                    return _clean(m.group(3)), [_clean(m.group(3))]
                if m.group(3):                                                        # a sentence, not a label
                    continue
                filled = [_clean(x) for x in row if pd.notna(x) and _clean(x)]
                if len(filled) == 2 and filled[0] == txt:                              # "Branch" | "Jeddah" (a key-value row)
                    val = filled[1]
                    if not _bad(val) and not any(w in val.lower() for w in _HEADERISH):
                        return val, [val]
                below = df.iloc[r + 1:, c].dropna().astype(str).map(_clean)          # column "Branch" with values under it
                below = below[~below.map(_bad)]
                if len(below):
                    u = sorted(below.unique())
                    return (below.mode().iloc[0] if len(u) == 1 else None), u
                right = [_clean(x) for x in row.iloc[c + 1:] if pd.notna(x) and not _bad(_clean(x))]   # "Branch" | "Jeddah"
                if right:
                    return right[0], right[:1]
    return None, []


def _real(name, known):
    """Reuse the exact stored spelling if the city already exists (case-insensitive)."""
    return known.get(name.lower(), name)


def render():
    st.markdown('<div class="topbar"><div class="t1">UPLOAD DATA</div>'
                '<div class="t2">Drop the exports of any cities together. The city is read from the branch name inside each file</div></div>',
                unsafe_allow_html=True)
    if not db.is_persistent():
        st.warning("No DATABASE_URL in secrets: data is saved locally and temporarily (it will be wiped on Streamlit Cloud). "
                   "Connect Supabase first, see the README.")
    platform = st.selectbox("Platform", list(PLATFORMS), key="up_platform")
    pkey = PLATFORMS[platform]["parser"]
    if pkey is None:
        st.info(f"**{platform}** is registered in the system but has no parser yet. Send the first export and it gets added in the same format.")
        return
    known = {c.lower(): c for c in list(DEFAULT_CITIES) + list(db.known_cities()) + _saved()}
    files = st.file_uploader("Excel files (.xlsx), any cities", type=["xlsx"], accept_multiple_files=True, key="up_files")
    if not files:
        return

    items = []
    for f in files:
        try:
            kind, df = parsers.parse_file(parsers.read_excel_any(f), pkey)
        except Exception as e:
            st.error(f"**{f.name}**: {e}")
            continue
        name, found = detect_branch(f, df)
        items.append(dict(file=f.name, kind=kind, df=df, branch=_real(name, known) if name else None, found=found))
    if not items:
        return

    ui.section("What the system read")
    for i, it in enumerate(items):
        if it["branch"] is None:
            if len(it["found"]) > 1:
                st.warning(f"**{it['file']}** has more than one branch inside: {', '.join(it['found'][:8])}. Choose the city for this file.")
            else:
                st.warning(f"**{it['file']}**: no branch name found in the file. Choose the city for this file.")
            opts = sorted(set(known.values()))
            pick = st.selectbox(f"City for {it['file']}", opts + ["+ type a new city"], key=f"up_pick_{i}")
            if pick.startswith("+"):
                pick = " ".join(st.text_input("New city name", key=f"up_new_{i}").split())
            it["branch"] = pick or None
    table = pd.DataFrame([{"File": it["file"], "Type": "Couriers" if it["kind"] == "courier" else "Company", "Branch / City": it["branch"] or "?",
                           "Rows": len(it["df"]), "From": str(it["df"]["date"].min()), "To": str(it["df"]["date"].max()),
                           "Couriers": it["df"]["courier_id"].nunique() if it["kind"] == "courier" else None} for it in items])
    st.dataframe(table, hide_index=True, width="stretch", height=38 + 35 * (len(table) + 1))
    by_city = {}
    for it in items:
        by_city.setdefault(it["branch"] or "?", []).append(it["kind"])
    for c, kinds in by_city.items():
        if c != "?" and sorted(set(kinds)) != ["company", "courier"]:
            st.caption(f"{c}: {'couriers file' if 'courier' in kinds else 'company file'} only (the other file of this city is not in this upload)")
    ready = all(it["branch"] for it in items)
    if st.button(f"Save {len(items)} file(s)", type="primary", disabled=not ready):
        with st.spinner("Saving…"):
            for it in items:
                db.save(it["kind"], it["df"], platform, it["branch"], it["file"])
                _remember(it["branch"])
        st.cache_data.clear()
        st.success("Saved: " + " · ".join(f"{c} ({len(k)})" for c, k in by_city.items()))
        st.rerun()

    ui.section("Upload log")
    log = db.log_df()
    if not log.empty:
        st.dataframe(log, width="stretch", hide_index=True)
