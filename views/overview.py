import pandas as pd
import streamlit as st
from core import ui, metrics as M

# key, label, fmt, kind (num/rate), bad_when_up
CARDS = [
    [("delivered", "Delivered Orders", "{:,.0f}", "num", False), ("assigned", "Assigned Tasks", "{:,.0f}", "num", False),
     ("accepted", "Accepted Tasks", "{:,.0f}", "num", False), ("completion_rate", "Order Completion Rate", "{:.2%}", "rate", False),
     ("cancel_rate_di", "Cancellation Rate", "{:.2%}", "rate", True), ("ontime_rate", "On-time Rate", "{:.2%}", "rate", False)],
    [("avg_delivery_min", "Avg Delivery Time (min)", "{:.1f}", "num", True), ("over55_prop", "Orders Over 55 Min", "{:.2%}", "rate", True),
     ("overdue", "Overdue Tasks", "{:,.0f}", "num", True), ("severe_overdue", "Severely Overdue", "{:,.0f}", "num", True),
     ("large_orders", "Large Orders Completed", "{:,.0f}", "num", False), ("large_ontime_rate", "Large Order On-time", "{:.2%}", "rate", False)],
    [("registered", "Registered Couriers (avg/day)", "{:,.0f}", "num", False), ("online", "Online Couriers (avg/day)", "{:,.0f}", "num", False),
     ("couriers_delivered", "Active Couriers (delivered, avg/day)", "{:,.0f}", "num", False),
     ("couriers_delivered_prop", "Active Couriers % of Registered", "{:.1%}", "rate", False),
     ("courier_eff", "Orders / Courier / Day", "{:.2f}", "num", False), ("avg_online_hrs", "Avg Online Time (hrs)", "{:.2f}", "num", False)],
]

W = {"assigned": "Assigned", "delivered": "Delivered", "large_orders": "Large orders", "online": "Online couriers"}
SCORE = {
    "TASK VOLUMES": [("assigned", "sum"), ("accepted", "sum"), ("arrivals", "sum"), ("picked", "sum"), ("delivered", "sum"),
                     ("large_orders", "sum"), ("rejected", "sum"), ("rejected_courier", "sum"), ("rejected_auto", "sum"),
                     ("cancel_rate_di", "w"), ("completion_rate", "w"), ("large_cancel_rate", "w")],
    "COURIER CAPACITY": [("registered", "avg"), ("online", "avg"), ("couriers_accepted", "avg"), ("couriers_delivered", "avg"),
                         ("couriers_delivered_prop", "calc"), ("courier_eff", "w"), ("hourly_eff", "w"), ("avg_online_hrs", "w")],
    "DELIVERY EXPERIENCE": [("large_ontime_rate", "w"), ("ontime_rate", "w"), ("avg_delivery_min", "w"), ("acceptance_5min", "w"),
                            ("over55_prop", "w"), ("merchant_arrival_min", "w"), ("meal_wait_min", "w"),
                            ("meal_delivery_min", "w"), ("overdue", "sum"), ("severe_overdue", "sum")],
}
FMT = {k: ("{:.2%}", "rate") for k in ("cancel_rate_di", "completion_rate", "large_cancel_rate", "couriers_delivered_prop",
                                      "large_ontime_rate", "ontime_rate", "acceptance_5min", "over55_prop")}


def _basis(k, how):
    if how == "sum":
        return "Sum"
    if how == "avg":
        return "Avg / day"
    if how == "calc":
        return "Active ÷ Registered"
    return "Weighted by " + W.get(M.WEIGHT.get(k, ""), "—")


def render():
    f = ui.filters()
    co = ui.get_company()
    ui.topbar(f"{f['platform'].upper()}  ·  OPERATIONS DASHBOARD", f)
    if co.empty:
        st.info("No company data for this period. Upload the company file from the Upload page.")
        return
    daily = M.company_by_day(co)
    tot = M.company_total(daily)
    cp = ui.get_company_prev()
    ptot = M.company_total(M.company_by_day(cp)) if not cp.empty else {}
    n_days = (f["d2"] - f["d1"]).days + 1
    ui.strip(f, f"{daily['date'].max():%d %b %Y}", f"{int(tot['days'])} / {n_days}")

    ui.section("HEADLINE KPIs", "delta = change vs the previous period of the same length")
    for row in CARDS:
        cols = st.columns(6)
        for c, (k, lab, fmt, kind, bad) in zip(cols, row):
            ui.kpi(c, lab, tot.get(k), ptot.get(k), fmt, kind, bad)

    # ---------------------------------------------------------- daily performance
    ui.section("DAILY PERFORMANCE", "period total on top · then latest day first")
    d = daily.sort_values("date", ascending=False)
    t = pd.DataFrame({
        "Date": d["date"].dt.strftime("%Y-%m-%d"), "Day": d["date"].dt.strftime("%a"),
        "Assigned": d["assigned"], "Accepted": d["accepted"], "Delivered": d["delivered"],
        "Completion %": d["completion_rate"] * 100, "On-time %": d["ontime_rate"] * 100,
        "Avg Delivery (min)": d["avg_delivery_min"], "Over 55 min %": d["over55_prop"] * 100,
        "Overdue": d["overdue"], "Severely Overdue": d["severe_overdue"], "Online Couriers": d["online"]})
    top = {"Date": "PERIOD", "Day": "total / avg", "Assigned": tot["assigned"], "Accepted": tot["accepted"],
           "Delivered": tot["delivered"], "Completion %": tot["completion_rate"] * 100, "On-time %": tot["ontime_rate"] * 100,
           "Avg Delivery (min)": tot["avg_delivery_min"], "Over 55 min %": tot["over55_prop"] * 100,
           "Overdue": tot["overdue"], "Severely Overdue": tot["severe_overdue"], "Online Couriers": tot["online"]}
    t = pd.concat([pd.DataFrame([top]), t], ignore_index=True)
    ui.table(t, f"daily_performance_{f['platform']}_{f['city']}", "ov_daily", height=min(740, 38 + 35 * (len(t) + 1)))

    opts = [c for c in M.LABELS if c in daily.columns]
    sel = st.multiselect("Plot daily trend", opts, default=["assigned", "delivered"], format_func=M.LABELS.get, key="ov_metrics")
    if sel:
        st.plotly_chart(ui.line(daily, "date", sel), width="stretch")

    # ---------------------------------------------------------- scorecard
    ui.section("FULL SCORECARD", "every company metric · current vs previous period")
    export = []
    for grp, items in SCORE.items():
        rows = []
        for k, how in items:
            fmt, kind = FMT.get(k, ("{:,.2f}" if how in ("w",) else "{:,.0f}", "num"))
            cur, prv = tot.get(k), ptot.get(k)
            if k == "couriers_delivered_prop":
                cur = tot["couriers_delivered"] / tot["registered"] if tot["registered"] else None
                prv = (ptot["couriers_delivered"] / ptot["registered"]) if ptot and ptot.get("registered") else None
            rows.append({"Metric": M.LABELS[k], "Basis": _basis(k, how),
                         "Current": "–" if cur is None or pd.isna(cur) else fmt.format(cur),
                         "Previous": "–" if prv is None or pd.isna(prv) else fmt.format(prv),
                         "Change": (ui.delta_txt(cur, prv, kind) or "–").replace(" vs prev", "")})
        g = pd.DataFrame(rows)
        st.markdown(f"**{grp}**")
        st.dataframe(g, width="stretch", hide_index=True, height=38 + 35 * (len(g) + 1))
        export.append(g.assign(Group=grp))
    ui.download("Export scorecard to Excel", pd.concat(export)[["Group", "Metric", "Basis", "Current", "Previous", "Change"]],
                f"scorecard_{f['platform']}_{f['city']}", "ov_score")

    # ---------------------------------------------------------- by courier type
    ui.section("BY COURIER TYPE")
    rows = []
    for ct, g in co.groupby("courier_type"):
        tt = M.company_total(M.company_by_day(g))
        rows.append({"Courier Type": ct, "Assigned": tt["assigned"], "Delivered": tt["delivered"], "Rejected": tt["rejected"],
                     "On-time %": tt["ontime_rate"] * 100, "Avg Delivery (min)": tt["avg_delivery_min"],
                     "Online Couriers (avg/day)": tt["online"], "Overdue": tt["overdue"]})
    ui.table(pd.DataFrame(rows), "company_by_type", "ov_type")
    dd = M.company_by_day(co, ("date", "courier_type"))
    st.plotly_chart(ui.line(dd, "date", ["delivered"], "Delivered by courier type", color="courier_type"), width="stretch")

    # ---------------------------------------------------------- health
    ui.section("DATA HEALTH CHECKS")
    cd = ui.get_couriers()
    checks = [("Company rows loaded", f"{len(co):,} rows", len(co) > 0),
              ("Courier rows loaded", f"{len(cd):,} rows", len(cd) > 0),
              ("Every selected day has company data", f"{int(tot['days'])} of {n_days} days", int(tot["days"]) == n_days)]
    if not cd.empty:
        cdays = cd["date"].nunique()
        checks.append(("Every selected day has courier data", f"{cdays} of {n_days} days", cdays == n_days))
        a = cd.groupby("date")["delivered"].sum()
        b = daily.set_index("date")["delivered"]
        j = pd.concat([a, b], axis=1, keys=["c", "o"]).dropna()
        diff = (j["c"] - j["o"]).abs().max() if len(j) else 0
        checks.append(("Company delivered vs couriers-file delivered (same filters)", f"max daily gap {diff:,.0f}",
                       bool(len(j)) and diff <= max(10, 0.005 * j["o"].max())))
        dup = cd.duplicated(["date", "courier_id"]).sum()
        checks.append(("No duplicated courier-day rows", f"{dup} duplicates", dup == 0))
    h = pd.DataFrame([{"Check": c, "Detail": d_, "Status": "✔ OK" if ok else "⚠ CHECK"} for c, d_, ok in checks])
    st.dataframe(h, width="stretch", hide_index=True, height=38 + 35 * (len(h) + 1))
    if len(f["ctype"]) or len(f["sup"]) or len(f["veh"]):
        st.caption("Courier filters (supervisor / type / vehicle) are active, so a gap vs the company file is expected.")
