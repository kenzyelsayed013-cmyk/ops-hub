import html
import numpy as np
import pandas as pd
import streamlit as st
from core import ui, metrics as M, insights as I

GROUPS = [("bad", "Fix now"), ("warn", "Watch"), ("good", "On target")]


def _card(col, label, key, v, fm="{:.2%}"):
    ui.card(col, label, fm.format(v) if I.is_num(v) else "–", "", I.status(key, v), (I.target_hint(key) + "  ·  " + I.gap_txt(key, v)).strip(" ·"))


def render():
    f = ui.filters()
    co, cd = ui.get_company(), ui.get_couriers()
    n_days = (f["d2"] - f["d1"]).days + 1
    ui.topbar(f"{f['platform'].upper()}  ·  ACTION CENTER", f, days=n_days)
    if co.empty and cd.empty:
        st.info("No data for this period.")
        return
    daily, tot = I.company_stats(co)
    _, ptot = I.company_stats(ui.get_company_prev())
    s = M.courier_summary(cd) if not cd.empty else pd.DataFrame()
    A = I.attendance_stats(cd)
    rejc = cd["rejected_courier"].sum() if not cd.empty else np.nan
    ui.legend()

    ui.section("Key numbers")
    c = st.columns(6)
    ui.kpi(c[0], "On-time rate", tot.get("ontime_rate"), ptot.get("ontime_rate"), "{:.2%}", "rate", False, key="ontime_rate")
    ui.kpi(c[1], "Cancelled % (accepted − delivered)", tot.get("cancel_rate"), ptot.get("cancel_rate"), "{:.2%}", "rate", True, key="cancel_rate")
    _card(c[2], "Attendance (scheduled days)", "attendance", A["att"])
    _card(c[3], "Couriers completing all shifts", "valid_rate", A["valid"])
    ui.card(c[4], "Rejected by couriers", f"{rejc:,.0f}" if I.is_num(rejc) else "–", "", I.grade(rejc, 0, 0, False), "Target 0")
    ui.kpi(c[5], "Delivered orders", tot.get("delivered"), ptot.get("delivered"), "{:,.0f}", "num", False)

    c = st.columns(6)
    ui.kpi(c[0], "Accepted orders", tot.get("accepted"), ptot.get("accepted"), "{:,.0f}", "num", False)
    ui.kpi(c[1], "Cancelled orders", tot.get("cancelled"), ptot.get("cancelled"), "{:,.0f}", "num", True)
    ui.kpi(c[2], "Delivery Issue % (Keeta)", tot.get("cancel_rate_di"), ptot.get("cancel_rate_di"), "{:.2%}", "rate", True)
    ui.kpi(c[3], "Delivery-Issue cancels (est.)", tot.get("di_cancels"), ptot.get("di_cancels"), "{:,.0f}", "num", True)

    if len(f["cities"]) > 1:
        ui.section("Cities")
        ui.table(I.city_table(co, cd), "cities_total", "ac_city", export=False, first_row=True, height=38 + 35 * (len(f["cities"]) + 2))

    if not cd.empty:
        last = cd["date"].max()
        v, dr = I.day_lists(cd, last)
        ui.section(f"Latest day {last:%a %d %b}: {len(v)} valid · {len(dr)} INVALID")
        if dr.empty:
            st.success("No INVALID courier.")
        else:
            ui.table(dr, "invalid_latest", "ac_drop", export=False, height=min(420, 38 + 35 * (len(dr) + 1)), text_cols=["Status"] + list(dr.columns[-6:]))
        rc = cd.groupby(["courier_id", "name", "city", "supervisor"])[["rejected_courier", "accepted"]].sum().reset_index()
        rc = rc[rc["rejected_courier"] > 0].sort_values("rejected_courier", ascending=False).head(20)
        ui.section("Couriers who rejected orders (target 0)")
        if rc.empty:
            st.success("No rejections.")
        else:
            ui.table(rc.rename(columns={"courier_id": "Courier ID", "name": "Name", "city": "City", "supervisor": "Supervisor",
                                        "rejected_courier": "Rejected (Courier)", "accepted": "Accepted"}), "rejecters", "ac_rej", export=False)
    if not s.empty:
        seg = I.segment_couriers(s)
        coach = seg[seg["Segment"] == "Needs coaching"].assign(T=lambda x: x["Overdue"] + x["Severe_Overdue"]).nlargest(15, "T")
        if not coach.empty:
            ui.section("Couriers to coach")
            ui.table(coach[["Courier ID", "Name", "Supervisor", "Delivered", "On_time_%", "Overdue", "Severe_Overdue"]].rename(
                columns={"On_time_%": "On-time %", "Severe_Overdue": "Severely Overdue"}), "coach", "ac_coach", export=False)
