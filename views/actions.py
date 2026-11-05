import html
import numpy as np
import pandas as pd
import streamlit as st
from core import ui, metrics as M, insights as I

GROUPS = [("bad", "Fix now"), ("warn", "Watch"), ("good", "On target")]


def _card(col, label, key, v, fm="{:.2%}"):
    ui.card(col, label, fm.format(v) if I.is_num(v) else "–", "", I.status(key, v), (I.target_hint(key) + "  ·  " + I.gap_txt(key, v)).strip(" ·"), key=key)


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
    ui.set_who({"ontime_rate": lambda: I.who_ontime(cd), "cancel_rate_di": lambda: I.who_di(cd), "attendance": lambda: I.who_attendance(cd),
                "valid_rate": lambda: I.who_invalid(cd), "rejects": lambda: I.who_rejects(cd)})
    c = st.columns(6)
    ui.kpi(c[0], "On-time rate", tot.get("ontime_rate"), ptot.get("ontime_rate"), "{:.2%}", "rate", False, key="ontime_rate")
    ui.kpi(c[1], "Delivery Issue % (Keeta)", tot.get("cancel_rate_di"), ptot.get("cancel_rate_di"), "{:.2%}", "rate", True, key="cancel_rate_di")
    _card(c[2], "Attendance (scheduled days)", "attendance", A["att"])
    _card(c[3], "Couriers completing all shifts", "valid_rate", A["valid"])
    ui.card(c[4], "Rejected by couriers", f"{rejc:,.0f}" if I.is_num(rejc) else "–", "", I.grade(rejc, 0, 0, False), "Target 0", key="rejects")
    ui.kpi(c[5], "Delivered orders", tot.get("delivered"), ptot.get("delivered"), "{:,.0f}", "num", False)

    c = st.columns(6)
    ui.kpi(c[0], "Accepted orders", tot.get("accepted"), ptot.get("accepted"), "{:,.0f}", "num", False)
    ui.kpi(c[1], "Cancelled orders", tot.get("cancelled"), ptot.get("cancelled"), "{:,.0f}", "num", True)
    ui.kpi(c[2], "Cancelled % (accepted − delivered)", tot.get("cancel_rate"), ptot.get("cancel_rate"), "{:.2%}", "rate", True)
    ui.kpi(c[3], "Delivery-Issue cancels (est.)", tot.get("di_cancels"), ptot.get("di_cancels"), "{:,.0f}", "num", True)
    m1, m2 = f["dmax"].replace(day=1), pd.Period(f["dmax"], "M").end_time.date()
    dm = ui.couriers(f["platform"], f["cities"], m1, m2, f["sup"], f["ctype"], f["veh"])
    pace = pd.DataFrame()
    if not dm.empty:
        lastm = dm["date"].max()
        pace = I.month_orders(dm, lastm, max(0, (pd.Timestamp(m2) - lastm).days))
    behind = pace[pace["Pace"].str.startswith("✖ Behind")] if not pace.empty else pace
    vv = pd.DataFrame()
    if not dm.empty:
        vv = I.monthly_verdict(dm, lastm, max(0, (pd.Timestamp(m2) - lastm).days), m1, m2)
    ui.card(c[4], "Behind monthly pace", f"{len(behind):,}", f"of {len(pace):,} couriers · {f['dmax']:%B}", I.grade(len(behind), 0, 0, False), "Target 0")

    if not vv.empty:
        c = st.columns(6)
        ui.card(c[0], f"VALID couriers, {f['dmax']:%B}", f"{int((vv['Result'] == 'VALID').sum()):,}", f"of {len(vv):,} couriers", "good")
        ui.card(c[1], "AT RISK", f"{int((vv['Result'] == 'AT RISK').sum()):,}", "", "warn" if (vv["Result"] == "AT RISK").any() else "good")
        ui.card(c[2], "INVALID", f"{int((vv['Result'] == 'INVALID').sum()):,}", "this month so far", I.grade(int((vv["Result"] == "INVALID").sum()), 0, 0, False), "Target 0")

    if len(f["cities"]) > 1:
        ui.section("Cities")
        ui.table(I.city_table(co, cd), "cities_total", "ac_city", export=False, first_row=True, height=38 + 35 * (len(f["cities"]) + 2))

    if not cd.empty:
        vd = I.valid_by_day(cd)
        ibd = I.invalid_by_day(cd)
        n_inv_days = len(ibd)
        ui.section(f"INVALID by day, {f['d1']:%d %b} → {f['d2']:%d %b}" if f["d1"] != f["d2"] else f"INVALID on {f['d1']:%a %d %b %Y}")
        if not vd.empty:
            tt = pd.DataFrame({"Date": vd["date"].dt.strftime("%Y-%m-%d"), "Day": vd["date"].dt.strftime("%a") + vd["Mand"].map({True: " ★", False: ""}),
                               "Scheduled": vd["Scheduled"], "VALID": vd["Valid"], "INVALID (shifts)": vd["ShiftFail"], "INVALID (orders)": vd["OrderFail"],
                               "INVALID (total)": vd["Dropped"]})
            ui.table(tt, "valid_by_day_ac", "ac_vbd", export=False, height=min(380, 38 + 35 * (len(tt) + 1)))
        if ibd.empty:
            st.success("No INVALID courier in these dates.")
        else:
            st.markdown(f"**Who was INVALID** ({n_inv_days:,} courier-days)")
            ui.table(ui.search(ibd, "ac_ibd_q"), "invalid_by_day_ac", "ac_ibd", height=min(520, 38 + 35 * (len(ibd) + 1)), text_cols=["Result"])
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

    if not behind.empty:
        ui.section(f"Behind monthly pace, {f['dmax']:%B}")
        b = behind.sort_values("Over / Under").head(25).rename(columns={
            "Working": "Days Worked", "Orders": "Orders So Far", "Prorated Target": "His Target (days worked)", "Avg / Working Day": "Orders / Day So Far",
            "Needed / Day": "Orders / Day Needed", "Target": "Month Target (full)"})
        ui.table(b[["Courier ID", "Name", "City", "Supervisor", "Days Worked", "Orders So Far", "His Target (days worked)", "Over / Under",
                    "Orders / Day So Far", "Orders / Day Needed", "Month Target (full)"]], "behind_pace", "ac_pace", export=False)
