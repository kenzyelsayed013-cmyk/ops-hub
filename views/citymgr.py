import pandas as pd
import streamlit as st
from core import db, ui


def render():
    st.markdown('<div class="topbar"><div class="t1">MANAGE CITIES</div><div class="t2">Rename or hide cities · admin only</div></div>', unsafe_allow_html=True)
    m = db.meta()
    if m.empty:
        st.info("No cities yet.")
        return
    A = ui.alias()
    t = pd.DataFrame({"Platform": m["platform"], "City (stored)": m["city"],
                      "Show as": [A["rename"].get(c, "") for c in m["city"]],
                      "Hide": [c in A["hidden"] for c in m["city"]],
                      "From": m["dmin"].astype(str), "To": m["dmax"].astype(str)}).sort_values(["Platform", "City (stored)"]).reset_index(drop=True)
    ed = st.data_editor(t, hide_index=True, width="stretch", key="cm_ed", disabled=["Platform", "City (stored)", "From", "To"],
                        column_config={"Show as": st.column_config.TextColumn(help="Leave empty to keep the stored name"),
                                       "Hide": st.column_config.CheckboxColumn(help="Remove from every page")})
    if st.button("Save", type="primary"):
        rename = {r["City (stored)"]: " ".join(str(r["Show as"]).split()) for _, r in ed.iterrows()
                  if str(r["Show as"]).strip() and str(r["Show as"]).strip() != r["City (stored)"]}
        hidden = [r["City (stored)"] for _, r in ed.iterrows() if r["Hide"]]
        ui.save_alias(rename, hidden)
        st.cache_data.clear()
        st.success("Saved. Every page now uses the new names.")
    st.caption("Two cities with the same 'Show as' name are merged into one. Hiding removes a city from the dashboard; its data stays stored.")
