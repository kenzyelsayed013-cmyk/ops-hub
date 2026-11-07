import importlib
import streamlit as st
from core import db, ui, insights as I
try:
    from core import backup
except Exception:                                  # core/backup.py not uploaded yet: run without the GitHub backup
    class backup:
        enabled = staticmethod(lambda: False)

MISSING = []


def _mod(name):
    """Load a page file. A missing or broken file only removes that page; it never takes the whole app down."""
    try:
        return importlib.import_module(f"views.{name}")
    except Exception as e:
        MISSING.append(f"views/{name}.py ({type(e).__name__}: {str(e)[:70]})")
        return None


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


_SPECS = [("actions", "Action Center", ":material/crisis_alert:", "actions"), ("validation", "Validation", ":material/verified:", "validation"),
          ("orders", "Orders", ":material/inventory_2:", "orders"), ("pace", "Monthly Pace", ":material/speed:", "pace"),
          ("cities", "Cities", ":material/location_city:", "cities"), ("overview", "Daily Report", ":material/bar_chart:", "daily"),
          ("couriers", "Couriers", ":material/two_wheeler:", "couriers"), ("curve", "Courier Drill-down", ":material/person_search:", "curve"),
          ("shifts", "Shifts & Hours", ":material/schedule:", "shifts"), ("cancels", "Cancellations", ":material/cancel:", "cancels")]
SPECS = []
for mod, title, icon, url in _SPECS:
    m = _mod(mod)
    if m is not None:
        SPECS.append([m.render, title, icon, url, False])
st.session_state["_all_pages"] = [(u, t, i) for _, t, i, u, _ in SPECS]
hidden = [] if admin else ui.hidden_pages()
SPECS = [s for s in SPECS if s[3] not in hidden] or SPECS[:1]
up = _mod("upload") if admin else None
upload_first = up is not None and not filters          # admin and no data yet: the Upload page opens first
if SPECS and not upload_first:
    SPECS[0][4] = True                                 # exactly ONE default page, always
pages = [st.Page(fn if filters else _nodata, title=t, icon=i, url_path=u, default=d) for fn, t, i, u, d in SPECS]
if admin:
    for mod, title, icon, url in [("rules", "Rules (admin)", ":material/tune:", "rules"), ("pagesadmin", "Pages (admin)", ":material/visibility:", "pagesadmin"),
                                  ("citymgr", "Cities (admin)", ":material/edit_location:", "citymgr")]:
        m = _mod(mod)
        if m is not None:
            pages.append(st.Page(m.render, title=title, icon=icon, url_path=url))
    if up is not None:
        pages.append(st.Page(up.render, title="Upload (admin)", icon=":material/upload:", url_path="upload", default=upload_first))
    if MISSING:
        st.sidebar.error("Missing or broken files: " + ", ".join(MISSING))
if not pages:
    pages = [st.Page(_empty, title="Dashboard", url_path="home", default=True)]
st.navigation(pages).run()
ui.page_export()
