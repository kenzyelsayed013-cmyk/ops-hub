import numpy as np
import pandas as pd
import streamlit as st
from core import ui, insights as I


def _row(key, label, x):
    return {key: label, "Couriers": len(x), "VALID": int((x["Result"] == "VALID").sum()), "AT RISK": int((x["Result"] == "AT RISK").sum()),
            "INVALID": int((x["Result"] == "INVALID").sum()), "Orders Target Not Reached": int(x["f_orders"].sum()), "Behind Orders Pace (at risk)": int(x["r_orders"].sum()),
            "Too Many INVALID Days": int(x["f_inv"].sum()), "Mandatory Days Missed": int(x["f_mand"].sum()), "Too Few Working Days": int(x["f_days"].sum())}


def render():
    f = ui.filters()
    R = I.RULES
    months = list(pd.period_range(f["dmin"], f["dmax"], freq="M")[::-1])
    st.markdown(f'<div class="topbar"><div class="t1">{f["platform"].upper()}  ·  VALIDATION</div>'
                f'<div class="t2">{f["city"]}  ·  who is VALID and who is INVALID this month, and why</div></div>', unsafe_allow_html=True)
    mo = st.selectbox("Month", months, format_func=lambda p: p.strftime("%B %Y"), key="va_pick")
    m1, m2 = mo.start_time.date(), mo.end_time.date()
    d = ui.couriers(f["platform"], f["cities"], m1, m2, f["sup"], f["ctype"], f["veh"])
    if d.empty:
        st.info("No courier data in this month.")
        return
    last = d["date"].max()
    left = max(0, (pd.Timestamp(m2) - last).days)
    v = I.monthly_verdict(d, last, left, m1, m2)
    if v.empty:
        st.info("No courier worked in this month.")
        return
    base = f"{f['platform']}_{f['city']}_{mo}"
    st.caption(f"Data until {last:%d %b} · {left} days left in the month")
    st.info(I.validation_text())

    n = len(v)
    nv, nr, ni = int((v["Result"] == "VALID").sum()), int((v["Result"] == "AT RISK").sum()), int((v["Result"] == "INVALID").sum())
    ui.section("The result")
    k = st.columns(4)
    ui.card(k[0], "Couriers evaluated", f"{n:,}")
    ui.card(k[1], "VALID", f"{nv:,}", "", "good" if nv else "neutral")
    ui.card(k[2], "AT RISK", f"{nr:,}", "one more miss and they are INVALID", "warn" if nr else "good")
    ui.card(k[3], "INVALID", f"{ni:,}", "", "bad" if ni else "good", "Target 0")
    k2 = st.columns(5)
    if R.get("rule_orders_target", True):
        ui.card(k2[4], "AT RISK: behind the orders pace", f"{int(v['r_orders'].sum()):,}", "INVALID if still behind when the month closes", "warn" if v["r_orders"].any() else "good")
        ui.card(k2[0], "INVALID: orders target", f"{int(v['f_orders'].sum()):,}", "month closed, target not reached", I.grade(int(v["f_orders"].sum()), 0, 0, False))
    if R.get("rule_invalid_days", True):
        ui.card(k2[1], f"INVALID: more than {int(R['max_invalid_days'])} INVALID days", f"{int(v['f_inv'].sum()):,}", "shifts or orders", I.grade(int(v["f_inv"].sum()), 0, 0, False))
    if R.get("rule_mandatory", True):
        ui.card(k2[2], "INVALID: mandatory days", f"{int(v['f_mand'].sum()):,}", "missed too many", I.grade(int(v["f_mand"].sum()), 0, 0, False))
    if R.get("rule_min_days", False):
        ui.card(k2[3], "INVALID: working days", f"{int(v['f_days'].sum()):,}", f"under {int(R['min_days_month'])} days", I.grade(int(v["f_days"].sum()), 0, 0, False))

    ui.section("Per city")
    ct = pd.DataFrame([_row("City", "ALL CITIES", v)] + [_row("City", c, x) for c, x in v.groupby("City")])
    ui.table(ct, f"validation_cities_{base}", "va_city", first_row=True, height=38 + 35 * (len(ct) + 1))
    if v["Supervisor"].nunique() > 1:
        ui.section("Per supervisor")
        sp = pd.DataFrame([_row("Supervisor", c, x) for c, x in v.groupby("Supervisor")]).sort_values("INVALID", ascending=False)
        ui.table(sp, f"validation_sup_{base}", "va_sup", export=False, height=min(420, 38 + 35 * (len(sp) + 1)))

    ui.section("Courier by courier")
    only = st.checkbox("Only INVALID and AT RISK", value=True, key="va_only")
    t = v[v["Result"] != "VALID"] if only else v
    t = t.rename(columns={"Working": "Days Worked", "Orders": "Orders So Far", "Prorated Target": "His Target (days worked)",
                          "Invalid by Shifts": "Invalid Days (shifts)", "Invalid by Orders": "Invalid Days (orders)"})
    t = t[["Courier ID", "Name", "City", "Supervisor", "Result", "Why", "Days Worked", "Orders So Far", "His Target (days worked)", "Over / Under",
           "Invalid Days", "Invalid Days (shifts)", "Invalid Days (orders)", "Mandatory Missed"]]
    if t.empty:
        st.success("Every courier is VALID.")
    else:
        ui.table(ui.search(t, "va_q"), f"validation_couriers_{base}", "va_t", height=560, text_cols=["Result"])

    vd = I.valid_by_day(d)
    if not vd.empty:
        ui.section("Day by day (daily validity)")
        tt = pd.DataFrame({"Date": vd["date"].dt.strftime("%Y-%m-%d"), "Day": vd["date"].dt.strftime("%a") + vd["Mand"].map({True: " ★", False: ""}),
                           "Scheduled": vd["Scheduled"], "VALID": vd["Valid"], "INVALID (shifts)": vd["ShiftFail"], "INVALID (orders)": vd["OrderFail"],
                           "INVALID (total)": vd["Dropped"]})
        top = {"Date": "PERIOD", "Day": "total", "Scheduled": vd["Scheduled"].sum(), "VALID": vd["Valid"].sum(), "INVALID (shifts)": vd["ShiftFail"].sum(),
               "INVALID (orders)": vd["OrderFail"].sum(), "INVALID (total)": vd["Dropped"].sum()}
        ui.table(pd.concat([pd.DataFrame([top]), tt], ignore_index=True), f"validation_days_{base}", "va_day", first_row=True, height=min(520, 38 + 35 * (len(tt) + 2)))
