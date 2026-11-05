import streamlit as st
from core import backup, db, ui, insights as I
from views import upload, overview, couriers, curve, shifts, cancels, actions, cities, rules, orders, monthly, citymgr, mincheck, pace, validation, pagesadmin

st.set_page_config(page_title="Ops Dashboard", page_icon="🛵", layout="wide", initial_sidebar_state="expanded")
ui.inject_css()
if backup.enabled() and not st.session_state.get("_restore_tried"):
    st.session_state["_restore_tried"] = True
    try:
        if db.meta().empty:                      # the app was restarted and the local data is gone
            with st.spinner("Restoring the saved data…"):
                backup.restore(db)
            st.cache_data.clear()
    except Exception:
        pass
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


SPECS = [(actions.render, "Action Center", ":material/crisis_alert:", "actions", True), (validation.render, "Validation", ":material/verified:", "validation", False),
         (orders.render, "Orders", ":material/inventory_2:", "orders", False), (pace.render, "Monthly Pace", ":material/speed:", "pace", False),
         (cities.render, "Cities", ":material/location_city:", "cities", False), (overview.render, "Daily Report", ":material/bar_chart:", "daily", False),
         (couriers.render, "Couriers", ":material/two_wheeler:", "couriers", False), (curve.render, "Courier Drill-down", ":material/person_search:", "curve", False),
         (shifts.render, "Shifts & Hours", ":material/schedule:", "shifts", False), (cancels.render, "Cancellations", ":material/cancel:", "cancels", False)]
st.session_state["_all_pages"] = [(u, t, i) for _, t, i, u, _ in SPECS]
hidden = [] if admin else ui.hidden_pages()
SPECS = [s for s in SPECS if s[3] not in hidden] or SPECS[:1]
if SPECS and not any(s[4] for s in SPECS):
    SPECS[0] = (*SPECS[0][:4], True)
pages = [st.Page(fn if filters else _nodata, title=t, icon=i, url_path=u, default=d) for fn, t, i, u, d in SPECS]
if admin:
    pages.append(st.Page(rules.render, title="Rules (admin)", icon=":material/tune:", url_path="rules"))
    pages.append(st.Page(pagesadmin.render, title="Pages (admin)", icon=":material/visibility:", url_path="pagesadmin"))
    pages.append(st.Page(citymgr.render, title="Cities (admin)", icon=":material/edit_location:", url_path="citymgr"))
    pages.append(st.Page(upload.render, title="Upload (admin)", icon=":material/upload:", url_path="upload", default=not filters))
if not pages:
    pages = [st.Page(_empty, title="Dashboard", url_path="home", default=True)]
st.navigation(pages).run()
ui.page_export()
