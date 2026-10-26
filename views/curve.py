import pandas as pd
import streamlit as st
from core import ui, metrics as M
from core.config import SLOT_COLS, SLOTS

METRICS = {"delivered": "Delivered", "accepted": "Accepted", "rejected": "Rejected", "valid_hrs": "Valid Online Hrs",
           "ontime_rate": "On-time rate", "avg_delivery_min": "Avg Delivery (min)", "large_orders": "Large Orders",
           "overdue": "Overdue"}


def render():
    f = ui.filters()
    d = ui.get_couriers()
    ui.topbar(f"{f['platform'].upper()}  ·  COURIER CURVE", f, days=(f["d2"] - f["d1"]).days + 1)
    if d.empty:
        st.info("No courier data for this period / filters.")
        return
    labels = M.courier_labels(d)
    order = d.groupby("courier_id")["delivered"].sum().sort_values(ascending=False).index.tolist()
    ui.section("SELECT COURIER", "pick one, or several to compare — type a name or ID to search")
    ids = st.multiselect("Couriers", order, default=order[:1], format_func=lambda i: labels.get(i, i),
                         max_selections=8, key="cv_ids")
    if not ids:
        st.info("Pick a courier.")
        return
    a, b, c = st.columns(3)
    start_mode = a.radio("Start from", ["First working day", "First record"], horizontal=True, key="cv_start")
    cum = b.checkbox("Cumulative", key="cv_cum")
    ma = c.checkbox("7-day moving average", key="cv_ma")

    sub = d[d["courier_id"].isin(ids)].copy()
    frames = []
    for cid, g in sub.groupby("courier_id"):
        act = g[g["active"]]
        first = act["date"].min() if (start_mode == "First working day" and not act.empty) else g["date"].min()
        last = act["date"].max() if not act.empty else g["date"].max()
        g = g[(g["date"] >= first) & (g["date"] <= last)].set_index("date")
        g = g.reindex(pd.date_range(first, last, freq="D"))
        g.index.name = "date"
        for col in ("delivered", "accepted", "rejected", "rejected_courier", "rejected_auto", "di_cancels", "large_orders",
                    "valid_hrs", "overdue", "shifts_scheduled", "shifts_qualified"):
            g[col] = g[col].fillna(0)
        g["courier_id"] = cid
        g["name"] = labels.get(cid, cid)
        frames.append(g.reset_index())
    cur = pd.concat(frames, ignore_index=True)

    s = M.courier_summary(sub)
    ui.section("SUMMARY")
    if len(ids) == 1:
        r = s.iloc[0]
        k = st.columns(5)
        for col, (lab, v) in zip(k, [("First working day", str(r["First_Active"])), ("Last working day", str(r["Last_Active"])),
                                     ("Total delivered", f"{r['Delivered']:,.0f}"),
                                     ("Avg orders / working day", f"{r['Orders_per_Active_Day']:.1f}"),
                                     ("Avg hours / working day", f"{r['Hrs_per_Active_Day']:.1f}")]):
            col.metric(lab, v, border=True)
    else:
        st.dataframe(ui.rnd(s[["Courier ID", "Name", "First_Active", "Last_Active", "Active_Days", "Delivered",
                               "Orders_per_Active_Day", "Hrs_per_Active_Day", "On_time_%", "Rejected"]]),
                     width="stretch", hide_index=True)

    ui.section("ORDERS CURVE", "day by day")
    metric = st.selectbox("Metric", list(METRICS), format_func=METRICS.get, key="cv_metric")
    plot = cur[["date", "name", metric]].copy()
    if cum and metric in ("delivered", "accepted", "rejected", "valid_hrs", "large_orders", "overdue"):
        plot[metric] = plot.groupby("name")[metric].cumsum()
    if ma and not cum:
        plot[metric] = plot.groupby("name")[metric].transform(lambda x: x.rolling(7, min_periods=1).mean())
    st.plotly_chart(ui.line(plot, "date", [metric], METRICS[metric] + (" — cumulative" if cum else ""), color="name"),
                    width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(ui.line(cur, "date", ["valid_hrs"], "Daily working hours", bar=len(ids) == 1, color="name", height=300),
                        width="stretch")
    with c2:
        if len(ids) == 1:
            st.plotly_chart(ui.line(cur, "date", ["rejected_courier", "rejected_auto", "di_cancels"], "Cancellations & rejections",
                                    names={"rejected_courier": "Rejected (Courier)", "rejected_auto": "Rejected (Auto)",
                                           "di_cancels": "Delivery-Issue (est.)"}, bar=True, height=300), width="stretch")
        else:
            st.plotly_chart(ui.line(cur, "date", ["rejected"], "Rejected", color="name", height=300), width="stretch")

    ui.section("DAILY TABLE", "✅ qualified shift · ❌ unqualified · · not scheduled")
    t = cur.copy()
    sym = {"qualified": "✅", "unqualified": "❌", "off": "·"}
    for col in SLOT_COLS:
        t[col] = t[col].map(sym).fillna("·")
    t = t.rename(columns=dict(zip(SLOT_COLS, SLOTS)))
    keep = ["date", "courier_id", "name", "delivered", "accepted", "rejected", "rejected_courier", "rejected_auto",
            "di_cancels", "large_orders", "valid_hrs", "ontime_rate", "avg_delivery_min", "overdue",
            "shifts_scheduled", "shifts_qualified"] + SLOTS
    t = t[keep].rename(columns={**M.LABELS, "date": "Date", "courier_id": "Courier ID", "name": "Name",
                                "valid_hrs": "Valid Hrs", "shifts_scheduled": "Shifts Scheduled",
                                "shifts_qualified": "Shifts Qualified"})
    t["Date"] = t["Date"].dt.strftime("%Y-%m-%d")
    ui.table(t, f"courier_curve_{'_'.join(ids[:3])}", "cv_t", height=420)
