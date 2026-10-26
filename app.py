import streamlit as st
from core import db, ui
from views import upload, overview, couriers, curve
 
st.set_page_config(page_title="Ops Hub", page_icon="🛵", layout="wide")
ui.inject_css()
 
# ---- باسورد اختياري (APP_PASSWORD في الـ secrets)
try:
    pwd = st.secrets.get("APP_PASSWORD")
except Exception:
    pwd = None
if pwd and not st.session_state.get("auth"):
    st.title("🔒 Ops Hub")
    p = st.text_input("الباسورد", type="password")
    if p:
        if p == pwd:
            st.session_state["auth"] = True
            st.rerun()
        else:
            st.error("الباسورد غلط")
    st.stop()
 
filters = ui.render_filters()
pages = [st.Page(upload.render, title="رفع الملفات", icon="📤", url_path="upload")]
if filters:
    pages = [
        st.Page(overview.render, title="أرقام الشركة", icon="📊", url_path="overview", default=True),
        st.Page(curve.render, title="منحنى المندوب", icon="📈", url_path="curve"),
        st.Page(couriers.render, title="المناديب", icon="🏍️", url_path="couriers"),
    ] + pages
else:
    st.sidebar.info("مفيش داتا لسه — ارفع أول ملفات.")
st.navigation(pages).run()
 

