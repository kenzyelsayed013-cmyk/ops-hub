import pandas as pd
import streamlit as st
from core import ui, metrics as M, insights as I
from core.config import SLOTS


def render():
    f = ui.filters()
    d = ui.get_couriers()
    ui.topbar(f"{f['platform'].upper()}  ·  SHIFTS & WORKING HOURS", f, days=(f["d2"] - f["d1"]).days + 1)
    if d.empty:
        st.info("No courier data for this period / filters.")
        return
    base = f"{f['platform']}_{f['city']}"
    ui.legend()

    # ---------------------------------------------------------- hours per day
    ui.section("Working hours per day", "valid online hours · couriers under 4 hrs are flagged because short days cost capacity")
    daily = d.groupby("date").agg(Total=("valid_hrs", "sum"), Active=("active", "sum")).reset_index()
    short = d[(d["valid_hrs"] > 0) & (d["valid_hrs"] < 4)].groupby("date").size().rename("Short").reset_index()
    daily = daily.merge(short, on="date", how="left").fillna({"Short": 0}).sort_values("date", ascending=False)
    dt = pd.DataFrame({"Date": daily["date"].dt.strftime("%Y-%m-%d"), "Day": daily["date"].dt.strftime("%a"),
                       "Active Couriers": daily["Active"], "Total Online Hrs": daily["Total"],
                       "Avg Hrs / Active Courier": daily["Total"] / daily["Active"].replace(0, float("nan")),
                       "Couriers under 4 hrs": daily["Short"],
                       "Active % under 4 hrs": daily["Short"] / daily["Active"].replace(0, float("nan")) * 100})
    ui.table(dt, f"hours_by_day_{base}", "hr_day", rules={"Active % under 4 hrs": (15, 30, False)})

    ui.section("Hours per courier per day", "green 6+ hrs · amber 3-6 · red under 3 · blank = did not work")
    hrs = d.assign(valid_hrs=d["valid_hrs"].round(2)).pivot_table(
        index=["courier_id", "name"], columns="date", values="valid_hrs", aggfunc="sum").fillna(0)
    act = hrs > 0
    avg = hrs.sum(axis=1) / act.sum(axis=1).replace(0, float("nan"))
    hrs.columns = [c.strftime("%m-%d") for c in hrs.columns]
    daycols = list(hrs.columns)
    hrs.insert(0, "Avg Hrs / Working Day", avg.round(2))
    hrs.insert(1, "Total Hrs", hrs[daycols].sum(axis=1).round(1))
    hrs.insert(2, "Working Days", act.sum(axis=1))
    hrs = hrs.reset_index().rename(columns={"courier_id": "Courier ID", "name": "Name"}).sort_values("Avg Hrs / Working Day")
    ui.table(ui.search(hrs, "hr_q"), f"daily_hours_{base}", "hr_t", height=520, rules={c: (6, 3, True, True) for c in daycols})

    # ---------------------------------------------------------- shifts
    sd = M.shift_day_stats(d)
    ui.section("Shift completion", "Keeta splits the day into 6 windows; each courier is usually scheduled on 3")
    if sd.empty:
        st.info("No scheduled shifts in this period.")
        return
    ui.note("A shift is qualified when the courier met the required online time in that window. "
            "Completed all = every scheduled window of the day is qualified.")
    tot_c = sd["Couriers_Scheduled"].sum()
    ca, qs = sd["Completed_All"].sum() / tot_c, sd["Qualified_Shifts"].sum() / sd["Sched_Shifts"].sum()
    k = st.columns(3)
    ui.card(k[0], "Couriers who completed all shifts", f"{ca:.1%}", "", I.grade(ca * 100, 70, 50, True), "Green ≥70% · red <50%")
    ui.card(k[1], "Qualified shifts", f"{qs:.1%}", "", I.grade(qs * 100, 80, 60, True), "Green ≥80% · red <60%")
    ui.card(k[2], "Scheduled courier-days", f"{tot_c:,}")

    sdd = sd.sort_values("date", ascending=False)
    ui.table(pd.DataFrame({"Date": sdd["date"].dt.strftime("%Y-%m-%d"), "Day": sdd["date"].dt.strftime("%a"),
                           "Couriers Scheduled": sdd["Couriers_Scheduled"], "Completed all": sdd["Completed_All"],
                           "Completed all %": sdd["Completed_All_%"], "Scheduled shifts": sdd["Sched_Shifts"],
                           "Qualified shifts": sdd["Qualified_Shifts"], "Qualified shifts %": sdd["Qualified_Shifts_%"]}),
             f"shift_compliance_{base}", "sh_day")

    ui.section("Shifts by courier", "lowest compliance first")
    sc = M.shift_courier_stats(d).rename(columns={
        "Days_Scheduled": "Days Scheduled", "Days_Completed_All": "Days Completed All", "Shifts_Scheduled": "Shifts Scheduled",
        "Shifts_Qualified": "Shifts Qualified", "Days_Not_Completed": "Days Not Completed",
        "Completed_All_%": "Completed all %", "Shifts_Qualified_%": "Qualified shifts %"})
    if st.checkbox("Only couriers with missed shifts", key="sh_bad"):
        sc = sc[sc["Days Not Completed"] > 0]
    ui.table(ui.search(sc, "sh_q"), f"shifts_by_courier_{base}", "sh_t1", height=420)

    ui.section("Shift detail by day", "✅ qualified · ❌ unqualified · · not scheduled")
    det = M.shift_symbols(d[d["shifts_scheduled"] > 0])
    if st.checkbox("Only days with a missed shift", key="sh_bad2"):
        det = det[det["shifts_qualified"] < det["shifts_scheduled"]]
    det = det.rename(columns={"date": "Date", "courier_id": "Courier ID", "name": "Name", "valid_hrs": "Valid Hrs",
                              "shifts_scheduled": "Scheduled", "shifts_qualified": "Qualified"})
    det = det.sort_values("Date", ascending=False)
    det["Date"] = det["Date"].dt.strftime("%Y-%m-%d")
    ui.table(ui.search(det, "sh_q2"), f"shifts_detail_{base}", "sh_t2", height=420, text_cols=SLOTS)
