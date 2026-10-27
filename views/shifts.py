import pandas as pd
import streamlit as st
from core import ui, metrics as M, insights as I
from core.config import SLOTS


def render():
    f = ui.filters()
    d = ui.get_couriers()
    ui.topbar(f"{f['platform'].upper()}  ·  SHIFTS & ATTENDANCE", f, days=(f["d2"] - f["d1"]).days + 1)
    if d.empty:
        st.info("No courier data for this period / filters.")
        return
    base = f"{f['platform']}_{f['city']}"
    vd = I.valid_by_day(d)
    if vd.empty:
        st.info("No scheduled shifts in this period.")
        return
    ui.legend()
    A = I.attendance_stats(d)
    ui.section("Totals")
    k = st.columns(4)
    for col, lab, key, v in [(k[0], "Attendance", "attendance", A["att"]), (k[1], "Couriers completing all shifts", "valid_rate", A["valid"])]:
        ui.card(col, lab, f"{v:.2%}", "", I.status(key, v), I.target_hint(key) + "  ·  " + I.gap_txt(key, v))
    ui.card(k[2], "Qualified shifts", f"{A['qual']:.2%}", "", I.grade(A["qual"] * 100, 100, 90, True), "Target 100%")
    ui.card(k[3], "Scheduled courier-days", f"{A['n']:,}")

    ui.section("Day by day")
    t = pd.DataFrame({"Date": vd["date"].dt.strftime("%Y-%m-%d"), "Day": vd["date"].dt.strftime("%a") + vd["Mand"].map({True: " ★", False: ""}), "Scheduled": vd["Scheduled"],
                      "Worked": vd["Attended"], "Absent": vd["Absent"], "Attendance %": vd["Attendance %"],
                      "Valid": vd["Valid"], "INVALID": vd["Dropped"], "Missed shifts": vd["ShiftFail"], "Low orders": vd["OrderFail"], "Valid %": vd["Valid %"], "Qualified shifts %": vd["Qualified shifts %"]})
    tt = {"Date": "PERIOD", "Day": "total", "Scheduled": vd["Scheduled"].sum(), "Worked": vd["Attended"].sum(), "Absent": vd["Absent"].sum(),
          "Attendance %": A["att"] * 100, "Valid": vd["Valid"].sum(), "INVALID": vd["Dropped"].sum(), "Missed shifts": vd["ShiftFail"].sum(), "Low orders": vd["OrderFail"].sum(), "Valid %": A["valid"] * 100,
          "Qualified shifts %": A["qual"] * 100}
    ui.table(pd.concat([pd.DataFrame([tt]), t], ignore_index=True), f"shift_days_{base}", "sh_day", first_row=True,
             height=min(600, 38 + 35 * (len(t) + 2)))

    ui.section("VALID and INVALID couriers, by day")
    days = list(vd["date"])
    day = st.selectbox("Day", days, format_func=lambda x: f"{x:%a %d %b %Y}", key="sh_pick")
    st.caption(I.rule_sentence() + "  ★ = mandatory day")
    valid, drop = I.day_lists(d, day)
    c1, c2 = st.columns(2)
    ui.card(c1, "VALID couriers", f"{len(valid):,}", "", "good" if len(drop) == 0 else "neutral")
    ui.card(c2, "INVALID couriers", f"{len(drop):,}", "", "bad" if len(drop) else "good", "Target 0")
    st.markdown("**INVALID**")
    ui.table(ui.search(drop, "sh_q_drop"), f"invalid_{day:%Y%m%d}", "sh_t_drop", height=min(460, 38 + 35 * (len(drop) + 1)), text_cols=SLOTS + ["Status"], rules={"Orders": (0, 10**9, True)})
    st.markdown("**VALID**")
    ui.table(ui.search(valid, "sh_q_valid"), f"valid_{day:%Y%m%d}", "sh_t_valid", height=min(460, 38 + 35 * (len(valid) + 1)), text_cols=SLOTS + ["Status"])

    ns = d[(d["date"] == pd.Timestamp(day)) & (d["shifts_scheduled"] == 0) & ((d["delivered"] > 0) | (d["valid_hrs"] > 0))]
    if not ns.empty:
        st.markdown(f"**Worked but NOT scheduled ({len(ns)})**: not counted as VALID or INVALID")
        ui.table(ns[["courier_id", "name", "city", "supervisor", "delivered", "valid_hrs"]].rename(
            columns={"courier_id": "Courier ID", "name": "Name", "city": "City", "supervisor": "Supervisor", "delivered": "Orders", "valid_hrs": "Valid Hrs"}),
            f"not_scheduled_{day:%Y%m%d}", "sh_t_ns", height=min(300, 38 + 35 * (len(ns) + 1)), export=False)

    ui.section("By courier")
    s = I.sched_days(d)
    g = s.groupby("courier_id").agg(Name=("name", "last"), City=("city", "last"), Supervisor=("supervisor", "last"), Scheduled_Days=("date", "count"),
                                    Worked=("attended", "sum"), Valid=("valid", "sum")).reset_index().rename(columns={"courier_id": "Courier ID"})
    g["Absent"] = g["Scheduled_Days"] - g["Worked"]
    g["INVALID Days"] = g["Scheduled_Days"] - g["Valid"]
    g["Attendance %"] = g["Worked"] / g["Scheduled_Days"] * 100
    g["Valid %"] = g["Valid"] / g["Scheduled_Days"] * 100
    g = g.rename(columns={"Scheduled_Days": "Scheduled Days"}).sort_values(["Valid %", "Attendance %"])
    if st.checkbox("Only couriers with INVALID days", key="sh_bad"):
        g = g[g["INVALID Days"] > 0]
    ui.table(ui.search(g, "sh_q"), f"shifts_by_courier_{base}", "sh_t1", height=460)

    ui.section("Online hours per day")
    daily = d.groupby("date").agg(Total=("valid_hrs", "sum"), Active=("active", "sum")).reset_index().sort_values("date", ascending=False)
    ui.table(pd.DataFrame({"Date": daily["date"].dt.strftime("%Y-%m-%d"), "Day": daily["date"].dt.strftime("%a"), "Active Couriers": daily["Active"],
                           "Total Online Hrs": daily["Total"], "Avg Hrs / Active Courier": daily["Total"] / daily["Active"].replace(0, float("nan"))}),
             f"hours_{base}", "hr_day")
