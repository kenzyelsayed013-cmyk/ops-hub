import pandas as pd
import streamlit as st
from core import ui, metrics as M


def render():
    f = ui.filters()
    d = ui.get_couriers()
    ui.topbar(f"{f['platform'].upper()}  ·  SHIFTS & WORKING HOURS", f, days=(f["d2"] - f["d1"]).days + 1)
    if d.empty:
        st.info("No courier data for this period / filters.")
        return
    base = f"{f['platform']}_{f['city']}"

    # ---------------------------------------------------------- hours
    ui.section("DAILY WORKING HOURS", "Valid Online Hours per courier per day (not App Online)")
    daily = d.groupby("date").agg(Total=("valid_hrs", "sum"), Active=("active", "sum")).reset_index()
    daily["Avg Hrs / Active Courier"] = daily["Total"] / daily["Active"].replace(0, float("nan"))
    st.plotly_chart(ui.line(daily, "date", ["Avg Hrs / Active Courier"], "Average valid online hours per active courier"),
                    width="stretch")
    hrs = d.assign(valid_hrs=d["valid_hrs"].round(2)).pivot_table(
        index=["courier_id", "name"], columns="date", values="valid_hrs", aggfunc="sum").fillna(0)
    act = hrs > 0
    avg = hrs.sum(axis=1) / act.sum(axis=1).replace(0, float("nan"))
    hrs.columns = [c.strftime("%m-%d") for c in hrs.columns]
    hrs.insert(0, "Avg Hrs / Working Day", avg.round(2))
    hrs.insert(1, "Total Hrs", hrs.drop(columns="Avg Hrs / Working Day").sum(axis=1).round(1))
    hrs.insert(2, "Working Days", act.sum(axis=1))
    hrs = hrs.reset_index().rename(columns={"courier_id": "Courier ID", "name": "Name"})
    ui.table(ui.search(hrs, "hr_q"), f"daily_hours_{base}", "hr_t", height=520)

    # ---------------------------------------------------------- shifts
    sd = M.shift_day_stats(d)
    ui.section("SHIFT COMPLETION", "Keeta splits the day into 6 windows; each courier is usually scheduled on 3")
    if sd.empty:
        st.info("No scheduled shifts in this period.")
        return
    st.caption("A shift is 'qualified' when the courier met the required online time in that window. "
               "'Completed all' = every scheduled window for that day is qualified.")
    tot_c = sd["Couriers_Scheduled"].sum()
    k = st.columns(3)
    k[0].metric("Couriers who completed all their shifts", f"{sd['Completed_All'].sum() / tot_c:.1%}", border=True)
    k[1].metric("Qualified shifts", f"{sd['Qualified_Shifts'].sum() / sd['Sched_Shifts'].sum():.1%}", border=True)
    k[2].metric("Scheduled courier-days", f"{tot_c:,}", border=True)
    st.plotly_chart(ui.line(sd, "date", ["Completed_All_%", "Qualified_Shifts_%"], "Daily shift compliance",
                            names={"Completed_All_%": "Completed all shifts %", "Qualified_Shifts_%": "Qualified shifts %"}),
                    width="stretch")

    ui.section("SHIFTS BY COURIER")
    sc = M.shift_courier_stats(d)
    if st.checkbox("Only couriers with missed shifts", key="sh_bad"):
        sc = sc[sc["Days_Not_Completed"] > 0]
    ui.table(ui.search(sc, "sh_q"), f"shifts_by_courier_{base}", "sh_t1", height=420)

    ui.section("SHIFT DETAIL BY DAY", "✅ qualified · ❌ unqualified · · not scheduled")
    det = M.shift_symbols(d[d["shifts_scheduled"] > 0])
    if st.checkbox("Only days with a missed shift", key="sh_bad2"):
        det = det[det["shifts_qualified"] < det["shifts_scheduled"]]
    det = det.rename(columns={"date": "Date", "courier_id": "Courier ID", "name": "Name", "valid_hrs": "Valid Hrs",
                              "shifts_scheduled": "Scheduled", "shifts_qualified": "Qualified"})
    det["Date"] = det["Date"].dt.strftime("%Y-%m-%d")
    ui.table(ui.search(det, "sh_q2"), f"shifts_detail_{base}", "sh_t2", height=420)
