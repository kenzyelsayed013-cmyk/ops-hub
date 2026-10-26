import html
import pandas as pd
import streamlit as st
from core import ui, metrics as M, insights as I

GROUPS = [("bad", "Fix now", "Problems that are costing orders or customers today"),
          ("warn", "Watch closely", "Not red yet, but moving the wrong way or below target"),
          ("good", "Protect what works", "On target. Keep doing it, no action needed")]


def _day_table(daily, n=5):
    d = daily.dropna(subset=["ontime_rate"]).nsmallest(n, "ontime_rate")
    return pd.DataFrame({"Date": d["date"].dt.strftime("%Y-%m-%d"), "Day": d["date"].dt.strftime("%a"),
                         "Delivered": d["delivered"], "On-time %": d["ontime_rate"] * 100,
                         "Avg Delivery (min)": d["avg_delivery_min"], "Cancel %": d["cancel_rate_di"] * 100,
                         "Overdue": d["overdue"], "Severely Overdue": d["severe_overdue"], "Online Couriers": d["online"]})


def _cour(df, extra=None):
    cols = {"Courier ID": "Courier ID", "Name": "Name", "Supervisor": "Supervisor", "Delivered": "Delivered",
            "Active_Days": "Active Days", "Valid_Hrs": "Valid Online Hrs", "Orders_per_Valid_Hr": "Orders / Valid Hr",
            "On_time_%": "On-time %", "Avg_Delivery_min": "Avg Delivery (min)", "Overdue": "Overdue",
            "Severe_Overdue": "Severely Overdue", **(extra or {})}
    return df[[c for c in cols if c in df.columns]].rename(columns=cols).reset_index(drop=True)


def render():
    f = ui.filters()
    co, cd = ui.get_company(), ui.get_couriers()
    n_days = (f["d2"] - f["d1"]).days + 1
    ui.topbar(f"{f['platform'].upper()}  ·  ACTION CENTER", f, days=n_days)
    if co.empty and cd.empty:
        st.info("No data for this period.")
        return
    daily = M.company_by_day(co) if not co.empty else pd.DataFrame()
    tot = I.enrich(M.company_total(daily)) if not daily.empty else {}
    cp = ui.get_company_prev()
    ptot = I.enrich(M.company_total(M.company_by_day(cp))) if not cp.empty else {}
    s = M.courier_summary(cd) if not cd.empty else pd.DataFrame()
    acts = I.build_actions(daily, tot, ptot, cd, s, n_days)
    nb, nw = sum(a["sev"] == "bad" for a in acts), sum(a["sev"] == "warn" for a in acts)

    # ---- verdict
    if nb:
        sev, head = "bad", f"{nb} critical issue{'s' if nb > 1 else ''} need action"
    elif nw:
        sev, head = "warn", f"No critical issues, {nw} item{'s' if nw > 1 else ''} to watch"
    else:
        sev, head = "good", "Everything is on target"
    line = ""
    if tot:
        line = (f"{tot['delivered']:,.0f} orders delivered  ·  on-time {tot['ontime_rate'] * 100:.1f}%  ·  "
                f"completion {tot['completion_rate'] * 100:.1f}%  ·  {tot['overdue'] + tot['severe_overdue']:,.0f} overdue orders")
    st.markdown(f'<div class="verdict {sev}"><div class="v1">{head}</div><div class="v2">{line}</div></div>', unsafe_allow_html=True)
    ui.legend()
    ui.note("Targets are set in <b>core/insights.py</b>. Every colour on every page comes from them.")

    # ---- scoreboard
    if tot:
        ui.section("Scoreboard", "this period vs the previous period of the same length")
        r1 = st.columns(6)
        for c, (k, lab, fm, kind, bad) in zip(r1, [
                ("delivered", "Delivered orders", "{:,.0f}", "num", False), ("ontime_rate", "On-time rate", "{:.1%}", "rate", False),
                ("completion_rate", "Completion rate", "{:.1%}", "rate", False), ("cancel_rate_di", "Cancellation rate", "{:.1%}", "rate", True),
                ("avg_delivery_min", "Avg delivery (min)", "{:.1f}", "num", True), ("over55_prop", "Orders over 55 min", "{:.1%}", "rate", True)]):
            ui.kpi(c, lab, tot.get(k), ptot.get(k), fm, kind, bad, key=k)
        r2 = st.columns(6)
        od, pod = tot["overdue"] + tot["severe_overdue"], (ptot["overdue"] + ptot["severe_overdue"]) if ptot else None
        ui.kpi(r2[0], "Overdue orders (all)", od, pod, "{:,.0f}", "num", True)
        ui.kpi(r2[1], "Rejected tasks", tot["rejected"], ptot.get("rejected"), "{:,.0f}", "num", True)
        ui.kpi(r2[2], "Online couriers / day", tot["online"], ptot.get("online"), "{:,.0f}", "num", False)
        ui.kpi(r2[3], "Active % of registered", tot["couriers_delivered_prop"], ptot.get("couriers_delivered_prop"), "{:.1%}", "rate", False,
               key="couriers_delivered_prop")
        ui.kpi(r2[4], "Orders / courier / day", tot.get("courier_eff"), ptot.get("courier_eff"), "{:.2f}", "num", False)
        ui.kpi(r2[5], "Large-order on-time", tot.get("large_ontime_rate"), ptot.get("large_ontime_rate"), "{:.1%}", "rate", False,
               key="large_ontime_rate")

    # ---- actions
    ui.section("What to do, in priority order", "every item shows the number behind it and the action to take")
    for sev_k, title, sub in GROUPS:
        items = [a for a in acts if a["sev"] == sev_k]
        if not items:
            continue
        st.markdown(f"**{title}** ({len(items)}) — {sub}")
        for a in items:
            st.markdown(f'<div class="act {sev_k}"><div class="ah">{html.escape(a["title"])}</div>'
                        f'<div class="ae">{html.escape(a["evidence"])}</div>'
                        f'<div class="aa">Action: {html.escape(a["action"])}</div></div>', unsafe_allow_html=True)

    # ---- evidence tables
    if not daily.empty:
        ui.section("Worst 5 days", "lowest on-time rate in the period: find out what happened on these dates")
        ui.table(_day_table(daily), f"worst_days_{f['platform']}_{f['city']}", "ac_days", export=False)
    if not s.empty:
        seg = I.segment_couriers(s)
        coach = seg[seg["Segment"] == "Needs coaching"].assign(Total_Overdue=lambda x: x["Overdue"] + x["Severe_Overdue"])
        ui.section("Couriers to coach", "30+ deliveries and below 80% on-time, biggest overdue count first")
        if coach.empty:
            st.success("No courier is below 80% on-time with 30+ deliveries.")
        else:
            ui.table(_cour(coach.nlargest(15, "Total_Overdue")), "to_coach", "ac_coach", export=False)
        low = seg[seg["Segment"] == "Low efficiency"]
        ui.section("Online but under-delivering", "20+ online hours at less than half the median orders per hour")
        if low.empty:
            st.success("No courier falls into this group.")
        else:
            ui.table(_cour(low.nlargest(15, "Valid_Hrs")), "low_eff", "ac_low", export=False)
        idle = seg[(seg["Segment"] == "Idle (0 deliveries)") & (seg["Valid_Hrs"] > 0)]
        ui.section("Online hours with zero deliveries", "couriers who logged time but delivered nothing")
        if idle.empty:
            st.success("No courier logged online hours without delivering.")
        else:
            ui.table(_cour(idle.nlargest(15, "Valid_Hrs")), "idle_online", "ac_idle", export=False)
        ui.section("Stars to recognise", "90%+ on-time and above-median orders per working day")
        stars = seg[seg["Segment"] == "Star"]
        if stars.empty:
            st.info("No courier meets the star criteria in this period.")
        else:
            ui.table(_cour(stars.nlargest(10, "Delivered")), "stars", "ac_stars", export=False)
