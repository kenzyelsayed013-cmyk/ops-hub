import streamlit as st
from core import ui, insights as I
from views import upload, overview, couriers, curve, shifts, cancels, actions, cities, rules, orders

st.set_page_config(page_title="Ops Dashboard", page_icon="🛵", layout="wide")
ui.inject_css()
I.load_rules()

# optional viewer password (APP_PASSWORD in Streamlit secrets)
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

admin = ui.is_admin()          # managers never see Upload; admin opens the app with ?admin=1
filters = ui.render_filters()


def _empty():
    st.title("Ops Dashboard")
    st.info("No data has been loaded yet. Please contact the administrator.")


pages = []
if filters:
    pages = [
        st.Page(actions.render, title="Action Center", icon="🎯", url_path="actions", default=True),
        st.Page(orders.render, title="Orders", icon="📦", url_path="orders"),
        st.Page(cities.render, title="Cities", icon="🏙️", url_path="cities"),
        st.Page(overview.render, title="Daily Report", icon="📊", url_path="daily"),
        st.Page(couriers.render, title="Couriers", icon="🏍️", url_path="couriers"),
        st.Page(curve.render, title="Courier Drill-down", icon="🔎", url_path="curve"),
        st.Page(shifts.render, title="Shifts & Hours", icon="🕒", url_path="shifts"),
        st.Page(cancels.render, title="Cancellations", icon="🚫", url_path="cancels"),
    ]
if admin:
    pages.append(st.Page(rules.render, title="Rules (admin)", icon="⚙️", url_path="rules"))
    pages.append(st.Page(upload.render, title="Upload (admin)", icon="📤", url_path="upload", default=not filters))
if not pages:
    pages = [st.Page(_empty, title="Dashboard", url_path="home", default=True)]
st.navigation(pages).run()
