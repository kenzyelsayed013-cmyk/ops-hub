import streamlit as st
from core import ui, insights as I
from views import upload, overview, couriers, curve, shifts, cancels, actions, cities, rules, orders, monthly

st.set_page_config(page_title="Ops Dashboard", page_icon="🛵", layout="wide", initial_sidebar_state="expanded")
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


def _nodata():
    st.title("Ops Dashboard")
    st.info("No data loaded yet. The administrator needs to upload the files (they may have been cleared by a restart).")


SPECS = [(actions.render, "Action Center", "🎯", "actions", True), (orders.render, "Orders", "📦", "orders", False),
         (cities.render, "Cities", "🏙️", "cities", False), (monthly.render, "Monthly Rules", "📅", "monthly", False), (overview.render, "Daily Report", "📊", "daily", False),
         (couriers.render, "Couriers", "🏍️", "couriers", False), (curve.render, "Courier Drill-down", "🔎", "curve", False),
         (shifts.render, "Shifts & Hours", "🕒", "shifts", False), (cancels.render, "Cancellations", "🚫", "cancels", False)]
pages = [st.Page(fn if filters else _nodata, title=t, icon=i, url_path=u, default=d) for fn, t, i, u, d in SPECS]
if admin:
    pages.append(st.Page(rules.render, title="Rules (admin)", icon="⚙️", url_path="rules"))
    pages.append(st.Page(upload.render, title="Upload (admin)", icon="📤", url_path="upload"))
st.navigation(pages).run()
