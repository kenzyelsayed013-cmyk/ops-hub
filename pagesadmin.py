import streamlit as st
from core import ui


def render():
    st.markdown('<div class="topbar"><div class="t1">PAGES</div><div class="t2">Admin only · choose which pages the people who open the dashboard can see</div></div>', unsafe_allow_html=True)
    pages = st.session_state.get("_all_pages", [])
    hidden = ui.hidden_pages()
    st.caption("Tick = visible to viewers. Untick = hidden from them. You always see every page when you open the dashboard as admin.")
    new_hidden = []
    cols = st.columns(2)
    for i, (path, title, icon) in enumerate(pages):
        show = cols[i % 2].checkbox(f"{title}", value=path not in hidden, key=f"pg_{path}")
        if not show:
            new_hidden.append(path)
    if st.button("Save", type="primary", key="pg_save"):
        if len(new_hidden) >= len(pages):
            st.error("At least one page must stay visible.")
        else:
            ui.save_hidden(new_hidden)
            st.success("Saved. Viewers see the change on their next refresh.")
