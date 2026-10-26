import streamlit as st
from core import ui
from views import upload, overview, couriers, curve, shifts, cancels

st.set_page_config(page_title="Ops Dashboard", page_icon="🛵", layout="wide")
ui.inject_css()

# optional password (APP_PASSWORD in Streamlit secrets)
try:
    pwd = st.secrets.get("APP_PASSWORD")
except Exception:
    pwd = None
if pwd and not st.session_state.get("auth"):
    st.title("Ops Dashboard")
    p = st.text_input("Password", type="password")
    if p:
        if p == pwd:
            st.session_state["auth"] = True
            st.rerun()
        else:
            st.error("Wrong password")
    st.stop()

filters = ui.render_filters()
pages = [st.Page(upload.render, title="Upload", icon="📤", url_path="upload")]
if filters:
    pages = [
        st.Page(overview.render, title="Overview", icon="📊", url_path="overview", default=True),
        st.Page(couriers.render, title="Couriers", icon="🏍️", url_path="couriers"),
        st.Page(curve.render, title="Courier Curve", icon="📈", url_path="curve"),
        st.Page(shifts.render, title="Shifts & Hours", icon="🕒", url_path="shifts"),
        st.Page(cancels.render, title="Cancellations", icon="🚫", url_path="cancels"),
    ] + pages
else:
    st.sidebar.info("No data yet — upload your first files.")
st.navigation(pages).run()
