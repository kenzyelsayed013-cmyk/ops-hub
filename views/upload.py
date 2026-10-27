import json
from pathlib import Path
import streamlit as st
from core import db, parsers, ui
from core.config import PLATFORMS, DEFAULT_CITIES

CITIES_FILE = Path(__file__).resolve().parent.parent / "cities.json"


def _saved():
    try:
        return [c for c in json.loads(CITIES_FILE.read_text()) if c]
    except Exception:
        return []


def _add_city():
    name = " ".join(st.session_state.get("up_newcity", "").split())
    if not name:
        return
    cur = _saved()
    if name.lower() not in [c.lower() for c in cur]:
        cur.append(name)
        try:
            CITIES_FILE.write_text(json.dumps(cur, ensure_ascii=False))
        except Exception:
            pass
    st.session_state["extra_cities"] = sorted(set(st.session_state.get("extra_cities", [])) | {name})
    st.session_state["up_city"] = name
    st.session_state["up_newcity"] = ""
    st.session_state["up_added"] = name


def render():
    st.markdown('<div class="topbar"><div class="t1">UPLOAD DATA</div>'
                '<div class="t2">Drop the platform exports here. The system detects each file type, stores it and keeps history</div></div>',
                unsafe_allow_html=True)
    if not db.is_persistent():
        st.warning("No DATABASE_URL in secrets: data is saved locally and temporarily (it will be wiped on Streamlit Cloud). "
                   "Connect Supabase first, see the README.")
    c1, c2 = st.columns(2)
    platform = c1.selectbox("Platform", list(PLATFORMS), key="up_platform")
    known = {c.lower(): c for c in list(DEFAULT_CITIES) + list(db.known_cities()) + _saved() + st.session_state.get("extra_cities", [])}
    cities = sorted(known.values())
    city = c2.selectbox("City", cities, key="up_city")

    a, b = st.columns([3, 1])
    a.text_input("Add a new city (type the name, then press the button)", key="up_newcity", placeholder="e.g. Dammam, Abha, Khamis Mushait, Al-Ahsa")
    b.markdown("<div style='height:1.9rem'></div>", unsafe_allow_html=True)
    b.button("Add city", on_click=_add_city, key="up_addcity")
    if st.session_state.get("up_added"):
        st.success(f"Added **{st.session_state.pop('up_added')}**. It is selected above. Now upload its files and press Save.")

    pkey = PLATFORMS[platform]["parser"]
    if pkey is None:
        st.info(f"**{platform}** is registered in the system but has no parser yet. Send the first export and it gets added in the same format.")
        return
    st.caption(f"Files will be saved to: **{platform} / {city}**. Re-uploading the same days replaces them, no duplicates. "
               "A city shows up in the dashboard filters after its first Save.")
    files = st.file_uploader("Excel files (.xlsx)", type=["xlsx"], accept_multiple_files=True, key="up_files")
    if not files or not city:
        return

    parsed = []
    for f in files:
        try:
            kind, df = parsers.parse_file(parsers.read_excel_any(f), pkey)
            parsed.append((f.name, kind, df))
            kname = "Couriers" if kind == "courier" else "Company"
            extra = f" · {df['courier_id'].nunique():,} couriers" if kind == "courier" else ""
            st.success(f"**{f.name}** → {kname} file · {len(df):,} rows · {df['date'].min()} → {df['date'].max()}{extra}")
        except Exception as e:
            st.error(f"**{f.name}**: {e}")
    if parsed and st.button(f"Save to {platform} / {city}", type="primary"):
        with st.spinner("Saving…"):
            for name, kind, df in parsed:
                db.save(kind, df, platform, city, name)
        st.cache_data.clear()
        st.success("Saved. Open any page from the sidebar.")
        st.rerun()

    ui.section("Upload log")
    log = db.log_df()
    if not log.empty:
        st.dataframe(log, width="stretch", hide_index=True)
