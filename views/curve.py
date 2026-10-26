import numpy as np
import pandas as pd
import streamlit as st
from core import ui, metrics as M, insights as I
from core.config import SLOT_COLS, SLOTS


def _weekly(cur):
    c = cur.copy()
    c["week"] = c["date"] - pd.to_timedelta(c["date"].dt.dayofweek, unit="D")
    c["w_ot"] = c["ontime_rate"].fillna(0) * c["delivered"]
    rows = []
    for (nm, wk), g in c.groupby(["name", "week"]):
        dl = g["delivered"].sum()
        rows.append({"Name": nm, "Week starting": wk.strftime("%Y-%m-%d"), "Working Days": int((g["delivered"] > 0).sum()),
                     "Delivered": dl, "Valid Hrs": g["valid_hrs"].sum(),
                     "Orders / Hr": dl / g["valid_hrs"].sum() if g["valid_hrs"].sum() else np.nan,
                     "On-time %": g["w_ot"].sum() / dl * 100 if dl else np.nan, "Rejected": g["rejected"].sum(),
                     "Overdue": g["overdue"].sum()})
    w = pd.DataFrame(rows).sort_values(["Name", "Week starting"])
    w["Delivered vs prev week %"] = w.groupby("Name")["Delivered"].pct_change() * 100
    return w.sort_values(["Name", "Week starting"], ascending=[True, False])


def render():
    f = ui.filters()
    d = ui.get_couriers()
    ui.topbar(f"{f['platform'].upper()}  ·  COURIER DRILL-DOWN", f, days=(f["d2"] - f["d1"]).days + 1)
    if d.empty:
        st.info("No courier data for this period / filters.")
        return
    labels = M.courier_labels(d)
    order = d.groupby("courier_id")["delivered"].sum().sort_values(ascending=False).index.tolist()
    ui.section("Select courier", "pick one, or several to compare. Type a name or ID to search")
    ids = st.multiselect("Couriers", order, default=order[:1], format_func=lambda i: labels.get(i, i), max_selections=8, key="cv_ids")
    if not ids:
        st.info("Pick a courier.")
        return
    start_mode = st.radio("Start from", ["First working day", "First record"], horizontal=True, key="cv_start")
    ui.legend()

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

    s = I.segment_couriers(M.courier_summary(sub))
    ui.section("Summary")
    if len(ids) == 1:
        r = s.iloc[0]
        k = st.columns(6)
        ot = r["On_time_%"]
        ui.card(k[0], "Group", str(r["Segment"]), "", I.tone_of_text(r["Segment"]), I.SEG_ACTION[r["Segment"]][:60])
        ui.card(k[1], "Total delivered", f"{r['Delivered']:,.0f}", f"{r['First_Active']} → {r['Last_Active']}")
        ui.card(k[2], "Orders / working day", f"{r['Orders_per_Active_Day']:.1f}" if pd.notna(r["Orders_per_Active_Day"]) else "–",
                f"{int(r['Active_Days'])} working days")
        ui.card(k[3], "Hours / working day", f"{r['Hrs_per_Active_Day']:.1f}" if pd.notna(r["Hrs_per_Active_Day"]) else "–")
        ui.card(k[4], "On-time rate", f"{ot:.1f}%" if pd.notna(ot) else "–", "", I.grade(ot, 90, 80, True), "Target ≥ 90%")
        ui.card(k[5], "Avg delivery (min)", f"{r['Avg_Delivery_min']:.1f}" if pd.notna(r["Avg_Delivery_min"]) else "–", "",
                I.grade(r["Avg_Delivery_min"], 35, 45, False), "Target ≤ 35")
    else:
        t = s[["Courier ID", "Name", "Segment", "First_Active", "Last_Active", "Active_Days", "Delivered", "Orders_per_Active_Day",
               "Hrs_per_Active_Day", "On_time_%", "Rejected"]].rename(columns={
                   "First_Active": "First Active", "Last_Active": "Last Active", "Active_Days": "Active Days",
                   "Orders_per_Active_Day": "Orders / Day", "Hrs_per_Active_Day": "Hrs / Day", "On_time_%": "On-time %"})
        ui.table(t, "courier_compare", "cv_cmp", export=False)

    ui.section("Week by week", "newest week first · change in delivered orders vs the previous week")
    ui.table(_weekly(cur), f"courier_weekly_{'_'.join(ids[:3])}", "cv_wk")

    ui.section("Day by day", "✅ qualified shift · ❌ unqualified · · not scheduled")
    t = cur.copy()
    sym = {"qualified": "✅", "unqualified": "❌", "off": "·"}
    for col in SLOT_COLS:
        t[col] = t[col].map(sym).fillna("·")
    t = t.rename(columns=dict(zip(SLOT_COLS, SLOTS)))
    t["On-time %"] = t["ontime_rate"] * 100
    keep = ["date", "name", "delivered", "accepted", "rejected", "rejected_courier", "rejected_auto", "di_cancels", "large_orders",
            "valid_hrs", "On-time %", "avg_delivery_min", "overdue", "shifts_scheduled", "shifts_qualified"] + SLOTS
    t = t[keep].rename(columns={**M.LABELS, "date": "Date", "name": "Name", "valid_hrs": "Valid Hrs",
                                "shifts_scheduled": "Shifts Scheduled", "shifts_qualified": "Shifts Qualified"})
    t = t.sort_values(["Name", "Date"], ascending=[True, False])
    t["Date"] = t["Date"].dt.strftime("%Y-%m-%d")
    ui.table(t, f"courier_daily_{'_'.join(ids[:3])}", "cv_t", height=460, text_cols=SLOTS)
