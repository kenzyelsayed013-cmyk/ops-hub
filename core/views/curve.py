import pandas as pd
import streamlit as st
from core import ui, metrics as M
from core.config import SLOT_COLS

METRICS = {"delivered": "Delivered (طلبات متسلّمة)", "accepted": "Accepted", "rejected": "Rejected",
           "valid_hrs": "ساعات الدوام (Valid)", "ontime_rate": "On-time rate", "avg_delivery_min": "Avg Delivery (min)",
           "large_orders": "Large Orders", "overdue": "Overdue"}


def render():
    f = ui.filters()
    st.title(f"📈 منحنى المندوب · {f['platform']} · {f['city']}")
    d = ui.get_couriers()
    if d.empty:
        st.info("مفيش داتا مناديب للفترة/الفلاتر دي.")
        return
    labels = M.courier_labels(d)
    order = d.groupby("courier_id")["delivered"].sum().sort_values(ascending=False).index.tolist()
    ids = st.multiselect("اختار مندوب (أو أكتر للمقارنة) — اكتب الاسم أو الـ ID", order,
                         default=order[:1], format_func=lambda i: labels.get(i, i), max_selections=8, key="cv_ids")
    if not ids:
        st.info("اختار مندوب.")
        return
    a, b, c = st.columns(3)
    start_mode = a.radio("البداية", ["من أول يوم شغل", "من أول سجل"], horizontal=True, key="cv_start")
    cum = b.checkbox("تراكمي", key="cv_cum")
    ma = c.checkbox("متوسط متحرك 7 أيام", key="cv_ma")

    sub = d[d["courier_id"].isin(ids)].copy()
    frames = []
    for cid, g in sub.groupby("courier_id"):
        act = g[g["active"]]
        first = act["date"].min() if (start_mode == "من أول يوم شغل" and not act.empty) else g["date"].min()
        last = act["date"].max() if not act.empty else g["date"].max()
        g = g[(g["date"] >= first) & (g["date"] <= last)].set_index("date")
        g = g.reindex(pd.date_range(first, last, freq="D"))
        g.index.name = "date"
        for col in ("delivered", "accepted", "rejected", "rejected_courier", "rejected_auto", "di_cancels",
                    "large_orders", "valid_hrs", "overdue", "shifts_scheduled", "shifts_qualified"):
            g[col] = g[col].fillna(0)
        g["courier_id"] = cid
        g["name"] = labels.get(cid, cid)
        frames.append(g.reset_index())
    cur = pd.concat(frames, ignore_index=True)

    # KPIs (مندوب واحد) أو جدول مقارنة
    s = M.courier_summary(sub)
    if len(ids) == 1:
        r = s.iloc[0]
        k = st.columns(5)
        k[0].metric("أول يوم شغل", str(r["First_Active"]))
        k[1].metric("آخر يوم شغل", str(r["Last_Active"]))
        k[2].metric("إجمالي Delivered", f"{r['Delivered']:,.0f}")
        k[3].metric("متوسط/يوم شغل", f"{r['Orders_per_Active_Day']:.1f}")
        k[4].metric("متوسط ساعات/يوم", f"{r['Hrs_per_Active_Day']:.1f}")
    else:
        st.dataframe(ui.rnd(s[["Courier ID", "Name", "First_Active", "Last_Active", "Active_Days", "Delivered",
                               "Orders_per_Active_Day", "Hrs_per_Active_Day", "On_time_%", "Rejected"]]),
                     width="stretch", hide_index=True)

    metric = st.selectbox("الرقم اللي في الكيرف", list(METRICS), format_func=METRICS.get, key="cv_metric")
    plot = cur[["date", "name", metric]].copy()
    if metric in ("delivered", "accepted", "rejected", "valid_hrs", "large_orders", "overdue"):
        if cum:
            plot[metric] = plot.groupby("name")[metric].cumsum()
    if ma and not cum:
        plot[metric] = plot.groupby("name")[metric].transform(lambda x: x.rolling(7, min_periods=1).mean())
    st.plotly_chart(ui.line(plot, "date", [metric], METRICS[metric] + (" — تراكمي" if cum else ""), color="name"),
                    width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(ui.line(cur, "date", ["valid_hrs"], "ساعات الدوام اليومية", bar=len(ids) == 1, color="name", height=300),
                        width="stretch")
    with c2:
        if len(ids) == 1:
            st.plotly_chart(ui.line(cur, "date", ["rejected_courier", "rejected_auto", "di_cancels"], "الكانسل والرفض",
                                    names={"rejected_courier": "رفض المندوب", "rejected_auto": "رفض تلقائي",
                                           "di_cancels": "Delivery Issue (تقريبي)"}, bar=True, height=300),
                            width="stretch")
        else:
            st.plotly_chart(ui.line(cur, "date", ["rejected"], "Rejected", color="name", height=300), width="stretch")

    st.subheader("الجدول اليومي")
    t = cur.copy()
    sym = {"qualified": "✅", "unqualified": "❌", "off": "·"}
    for col in SLOT_COLS:
        t[col] = t[col].map(sym).fillna("·")
    t = t.rename(columns={col: col.replace("shift_", "").replace("_", "–") for col in SLOT_COLS})
    keep = ["date", "courier_id", "name", "delivered", "accepted", "rejected", "rejected_courier", "rejected_auto",
            "di_cancels", "large_orders", "valid_hrs", "ontime_rate", "avg_delivery_min", "overdue",
            "shifts_scheduled", "shifts_qualified"] + [col.replace("shift_", "").replace("_", "–") for col in SLOT_COLS]
    t = t[keep].rename(columns={**M.LABELS, "date": "Date", "courier_id": "Courier ID", "name": "Name",
                                "valid_hrs": "Valid Hrs", "shifts_scheduled": "Shifts Sched",
                                "shifts_qualified": "Shifts Qualified"})
    t["Date"] = t["Date"].dt.strftime("%Y-%m-%d")
    ui.table(t, f"courier_curve_{'_'.join(ids[:3])}", "cv_t", height=420)
