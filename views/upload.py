import streamlit as st
from core import db, parsers, ui
from core.config import PLATFORMS, DEFAULT_CITIES


def render():
    st.markdown('<div class="topbar"><div class="t1">UPLOAD DATA</div>'
                '<div class="t2">Drop the platform exports here — the system detects each file type, stores it and keeps history</div></div>',
                unsafe_allow_html=True)
    if not db.is_persistent():
        st.warning("No DATABASE_URL in secrets: data is saved locally and temporarily (it will be wiped on Streamlit Cloud). "
                   "Connect Supabase first — see the README.")
    c1, c2 = st.columns(2)
    platform = c1.selectbox("Platform", list(PLATFORMS), key="up_platform")
    cities = sorted(set(DEFAULT_CITIES) | set(db.known_cities())) + ["+ New city…"]
    city = c2.selectbox("City", cities, key="up_city")
    if city.startswith("+"):
        city = c2.text_input("New city name", key="up_newcity").strip()

    pkey = PLATFORMS[platform]["parser"]
    if pkey is None:
        st.info(f"**{platform}** is registered in the system but has no parser yet. Send the first export and it gets added in the same format.")
        return
    st.caption("Upload the couriers file and the company file (one or both). Re-uploading the same days replaces them — no duplicates.")
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
        st.success("Saved. Open any page from the sidebar.")
        st.rerun()

    ui.section("UPLOAD LOG")
    log = db.log_df()
    if not log.empty:
        st.dataframe(log, width="stretch", hide_index=True)
