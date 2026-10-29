import pandas as pd
import streamlit as st
from core import ui, metrics as M, insights as I

CARDS = [
    [("delivered", "Delivered orders", "{:,.0f}", "num", False), ("assigned", "Assigned tasks", "{:,.0f}", "num", False),
     ("accepted", "Accepted tasks", "{:,.0f}", "num", False), ("completion_rate", "Completion rate", "{:.2%}", "rate", False),
     ("cancel_rate", "Cancelled % (accepted − delivered)", "{:.2%}", "rate", True), ("ontime_rate", "On-time rate", "{:.2%}", "rate", False)],
    [("avg_delivery_min", "Avg delivery time (min)", "{:.1f}", "num", True), ("over55_prop", "Orders over 55 min", "{:.2%}", "rate", True),
     ("overdue", "Overdue tasks", "{:,.0f}", "num", True), ("severe_overdue", "Severely overdue", "{:,.0f}", "num", True),
     ("large_orders", "Large orders completed", "{:,.0f}", "num", False), ("large_ontime_rate", "Large-order on-time", "{:.2%}", "rate", False)],
    [("registered", "Registered couriers (avg/day)", "{:,.0f}", "num", False), ("online", "Online couriers (avg/day)", "{:,.0f}", "num", False),
     ("couriers_delivered", "Delivering couriers (avg/day)", "{:,.0f}", "num", False),
     ("couriers_delivered_prop", "Delivering % of registered", "{:.1%}", "rate", False),
     ("courier_eff", "Orders / courier / day", "{:.2f}", "num", False), ("avg_online_hrs", "Avg online time (hrs)", "{:.2f}", "num", False)],
    [("cancel_rate_di", "Delivery Issue % (Keeta)", "{:.2%}", "rate", True), ("di_cancels", "Delivery-Issue cancels (est.)", "{:,.0f}", "num", True),
     ("cancelled", "Cancelled orders (accepted − delivered)", "{:,.0f}", "num", True)],
]

M.LABELS.setdefault("cancelled", "Cancelled (accepted − delivered)")
M.LABELS.setdefault("cancel_rate", "Cancelled % (accepted − delivered)")
W = {"assigned": "Assigned", "delivered": "Delivered", "large_orders": "Large orders", "online": "Online couriers"}
SCORE = {
    "Task volumes": [("assigned", "sum"), ("accepted", "sum"), ("arrivals", "sum"), ("picked", "sum"), ("delivered", "sum"),
                     ("cancelled", "sum"), ("cancel_rate", "cn"), ("large_orders", "sum"), ("rejected", "sum"), ("rejected_courier", "sum"), ("rejected_auto", "sum"),
                     ("di_cancels", "sum"), ("cancel_rate_di", "w"), ("completion_rate", "w"), ("large_cancel_rate", "w")],
    "Courier capacity": [("registered", "avg"), ("online", "avg"), ("couriers_accepted", "avg"), ("couriers_delivered", "avg"),
                         ("couriers_delivered_prop", "calc"), ("courier_eff", "w"), ("hourly_eff", "w"), ("avg_online_hrs", "w")],
    "Delivery experience": [("large_ontime_rate", "w"), ("ontime_rate", "w"), ("avg_delivery_min", "w"), ("acceptance_5min", "w"),
                            ("over55_prop", "w"), ("merchant_arrival_min", "w"), ("meal_wait_min", "w"),
                            ("meal_delivery_min", "w"), ("overdue", "sum"), ("severe_overdue", "sum")],
}
WORD = {"good": "✔ On target", "warn": "⚠ Watch", "bad": "✖ Act now", "neutral": "–"}


def _basis(k, how):
    if k == "cancel_rate_di":
        return "Average of daily rates" if I.RULES.get("di_total", "average") == "average" else "Weighted by Assigned"
    return {"sum": "Sum", "avg": "Avg / day", "calc": "Delivering ÷ Registered", "cn": "Cancelled ÷ Accepted"}.get(how, "Weighted by " + W.get(M.WEIGHT.get(k, ""), "—"))


def _wk(daily):
    d = daily.copy()
    d["dow"] = d["date"].dt.dayofweek
    rows = []
    for dw, g in d.groupby("dow"):
        rows.append({"Weekday": g["date"].iloc[0].strftime("%A"), "Days": len(g), "Avg Delivered / Day": g["delivered"].mean(),
                     "On-time %": M._wavg(g, "ontime_rate", "delivered") * 100,
                     "Avg Delivery (min)": M._wavg(g, "avg_delivery_min", "delivered"),
                     "Cancel %": M._wavg(g, "cancel_rate", "accepted") * 100, "Delivery Issue %": I.di_avg(g, "cancel_rate_di", "assigned") * 100,
                     "Avg Overdue / Day": (g["overdue"] + g["severe_overdue"]).mean(), "Avg Online Couriers": g["online"].mean()})
    return pd.DataFrame(rows)


def render():
    f = ui.filters()
    co = ui.get_company()
    n_days = (f["d2"] - f["d1"]).days + 1
    ui.topbar(f"{f['platform'].upper()}  ·  DAILY REPORT", f, days=n_days)
    if co.empty:
        st.info("No company data for this period.")
        return
    daily, tot = I.company_stats(co)
    _, ptot = I.company_stats(ui.get_company_prev())
    ui.legend()

    ui.section("Headline numbers", "arrow = change vs the previous period of the same length, green = better, red = worse")
    for row in CARDS:
        cols = st.columns(6)
        for c, (k, lab, fmt, kind, bad) in zip(cols, row):
            ui.kpi(c, lab, tot.get(k), ptot.get(k), fmt, kind, bad, key=k)

    # ---------------------------------------------------------- day by day
    ui.section("Day by day", "first row = whole period · then newest day first · red/amber cells are where to look")
    asc = daily.sort_values("date").copy()
    asc["chg"] = asc["delivered"].pct_change() * 100
    d = asc.sort_values("date", ascending=False)
    t = pd.DataFrame({
        "Date": d["date"].dt.strftime("%Y-%m-%d"), "Day": d["date"].dt.strftime("%a"), "Assigned": d["assigned"],
        "Delivered": d["delivered"], "Cancelled": d["cancelled"], "Delivered vs prev day %": d["chg"], "Completion %": d["completion_rate"] * 100,
        "On-time %": d["ontime_rate"] * 100, "Avg Delivery (min)": d["avg_delivery_min"], "Over 55 min %": d["over55_prop"] * 100,
        "Cancel %": d["cancel_rate"] * 100, "Delivery Issue %": d["cancel_rate_di"] * 100, "Delivery-Issue (est.)": d["di_cancels"], "Rejected (Courier)": d["rejected_courier"], "Overdue": d["overdue"],
        "Severely Overdue": d["severe_overdue"], "Online Couriers": d["online"]})
    top = {"Date": "PERIOD", "Day": "total / avg", "Assigned": tot["assigned"], "Delivered": tot["delivered"], "Cancelled": tot["cancelled"],
           "Delivered vs prev day %": None, "Completion %": tot["completion_rate"] * 100, "On-time %": tot["ontime_rate"] * 100,
           "Avg Delivery (min)": tot["avg_delivery_min"], "Over 55 min %": tot["over55_prop"] * 100,
           "Cancel %": tot["cancel_rate"] * 100, "Delivery Issue %": tot["cancel_rate_di"] * 100, "Delivery-Issue (est.)": tot["di_cancels"], "Rejected (Courier)": tot["rejected_courier"], "Overdue": tot["overdue"],
           "Severely Overdue": tot["severe_overdue"], "Online Couriers": tot["online"]}
    t = pd.concat([pd.DataFrame([top]), t], ignore_index=True)
    ui.table(t, f"daily_{f['platform']}_{f['city']}", "ov_daily", height=min(740, 38 + 35 * (len(t) + 1)), first_row=True)

    # ---------------------------------------------------------- scorecard
    ui.section("Full scorecard", "every company metric · this period vs previous · status against target where a target exists")
    export = []
    for grp, items in SCORE.items():
        rows = []
        for k, how in items:
            fmt = "{:.2%}" if k in I.RATE_KEYS else ("{:,.2f}" if how == "w" else "{:,.0f}")
            cur, prv = tot.get(k), ptot.get(k)
            kind = "rate" if k in I.RATE_KEYS else "num"
            rows.append({"Metric": M.LABELS[k], "Basis": _basis(k, how),
                         "Current": "–" if cur is None or pd.isna(cur) else fmt.format(cur),
                         "Previous": "–" if prv is None or pd.isna(prv) else fmt.format(prv),
                         "Change": (ui.delta_txt(cur, prv, kind) or "–").replace(" vs prev", ""),
                         "Target": I.target_hint(k).split("  ·")[0] or "–", "Status": WORD[I.status(k, cur)]})
        g = pd.DataFrame(rows)
        st.markdown(f"**{grp}**")
        ui.table(g, f"score_{grp}", f"ov_sc_{grp}", export=False, height=38 + 35 * (len(g) + 1))
        export.append(g.assign(Group=grp))
    ui.export_row(pd.concat(export)[["Group", "Metric", "Basis", "Current", "Previous", "Change", "Target", "Status"]],
                  f"scorecard_{f['platform']}_{f['city']}", "ov_score", title="Full scorecard")

    ui.section("By courier type")
    rows = []
    for ct, g in co.groupby("courier_type"):
        _, tt = I.company_stats(g)
        rows.append({"Courier Type": ct, "Assigned": tt["assigned"], "Delivered": tt["delivered"], "Rejected": tt["rejected"],
                     "On-time %": tt["ontime_rate"] * 100, "Avg Delivery (min)": tt["avg_delivery_min"],
                     "Cancel %": tt["cancel_rate"] * 100, "Delivery Issue %": tt["cancel_rate_di"] * 100, "Online Couriers (avg/day)": tt["online"], "Overdue": tt["overdue"]})
    ui.table(pd.DataFrame(rows), "company_by_type", "ov_type")

    # ---------------------------------------------------------- data health (admin only)
    if ui.is_admin():
        ui.section("Data health checks (admin)")
        cd = ui.get_couriers()
        checks = [("Company rows loaded", f"{len(co):,} rows", len(co) > 0),
                  ("Courier rows loaded", f"{len(cd):,} rows", len(cd) > 0),
                  ("Every selected day has company data", f"{int(tot['days'])} of {n_days} days", int(tot["days"]) == n_days)]
        if not cd.empty:
            cdays = cd["date"].nunique()
            checks.append(("Every selected day has courier data", f"{cdays} of {n_days} days", cdays == n_days))
            a, b = cd.groupby("date")["delivered"].sum(), daily.set_index("date")["delivered"]
            j = pd.concat([a, b], axis=1, keys=["c", "o"]).dropna()
            diff = (j["c"] - j["o"]).abs().max() if len(j) else 0
            checks.append(("Company vs couriers-file delivered", f"max daily gap {diff:,.0f}",
                           bool(len(j)) and diff <= max(10, 0.005 * j["o"].max())))
            dup = cd.duplicated(["date", "courier_id"]).sum()
            checks.append(("No duplicated courier-day rows", f"{dup} duplicates", dup == 0))
        h = pd.DataFrame([{"Check": c, "Detail": x, "Status": "✔ OK" if ok else "⚠ CHECK"} for c, x, ok in checks])
        ui.table(h, "health", "ov_health", export=False)
