import pandas as pd
import streamlit as st
from core import ui, metrics as M

KPIS = [("assigned", "Assigned", "{:,.0f}"), ("delivered", "Delivered", "{:,.0f}"), ("accepted", "Accepted", "{:,.0f}"),
        ("rejected", "Rejected", "{:,.0f}"), ("rejected_courier", "Rejected (Courier)", "{:,.0f}"),
        ("rejected_auto", "Rejected (Auto)", "{:,.0f}"), ("di_cancels", "Delivery-Issue Cancels (est.)", "{:,.0f}"),
        ("large_orders", "Large Orders", "{:,.0f}"), ("ontime_rate", "On-time", "{:.2%}"),
        ("avg_delivery_min", "Avg Delivery (min)", "{:.1f}"), ("online", "Online Couriers / day", "{:,.0f}"),
        ("completion_rate", "Completion Rate", "{:.2%}")]


def render():
    f = ui.filters()
    st.title(f"📊 أرقام الشركة · {f['platform']} · {f['city']}")
    co = ui.get_company()
    if co.empty:
        st.info("مفيش داتا شركة للفترة دي. ارفع ملف الشركة من صفحة الرفع.")
        return
    daily = M.company_by_day(co)
    tot = M.company_total(daily)
    st.caption(f"{f['d1']} → {f['d2']} · {tot['days']:.0f} يوم فيه داتا")

    cols = st.columns(4)
    for i, (k, lab, fmt) in enumerate(KPIS):
        v = tot.get(k)
        cols[i % 4].metric(lab, "–" if v is None or pd.isna(v) else fmt.format(v))

    st.subheader("المنحنى اليومي")
    opts = [c for c in M.LABELS if c in daily.columns]
    sel = st.multiselect("اختار الأرقام", opts, default=["assigned", "delivered"], format_func=M.LABELS.get, key="ov_metrics")
    if sel:
        st.plotly_chart(ui.line(daily, "date", sel), width="stretch")

    t1, t2, t3 = st.tabs(["جدول الأيام + الإجمالي", "حسب نوع المندوب", "مطابقة مع ملف المناديب"])
    with t1:
        show = daily.rename(columns=M.LABELS)
        total = {M.LABELS[k]: v for k, v in tot.items() if k in M.LABELS}
        total["date"] = "TOTAL / AVG"
        show["date"] = show["date"].dt.strftime("%Y-%m-%d")
        show = pd.concat([show, pd.DataFrame([total])], ignore_index=True)
        ui.table(show, f"company_daily_{f['platform']}_{f['city']}", "ov_t1", height=520)
        st.caption("الأعداد = مجموع. النسب والمتوسطات = موزونة بنفس منطق شيتك (Assigned / Delivered / Large). "
                   "المناديب Online = متوسط يومي. Delivery-Issue Cancels تقريبي (النسبة × Assigned).")
    with t2:
        rows = []
        for ct, g in co.groupby("courier_type"):
            d = M.company_by_day(g)
            t = M.company_total(d)
            rows.append({"Courier Type": ct, **{M.LABELS[k]: v for k, v in t.items() if k in M.LABELS}})
        ui.table(pd.DataFrame(rows), "company_by_type", "ov_t2", height=200)
        dd = M.company_by_day(co, ("date", "courier_type"))
        st.plotly_chart(ui.line(dd, "date", ["delivered"], "Delivered حسب النوع", color="courier_type"), width="stretch")
    with t3:
        cd = ui.get_couriers()
        if cd.empty:
            st.info("مفيش ملف مناديب للفترة.")
        else:
            a = cd.groupby("date")["delivered"].sum().rename("Delivered (Couriers file)")
            b = daily.set_index("date")["delivered"].rename("Delivered (Company file)")
            j = pd.concat([a, b], axis=1).dropna().reset_index()
            j["Diff"] = j["Delivered (Couriers file)"] - j["Delivered (Company file)"]
            j["date"] = j["date"].dt.strftime("%Y-%m-%d")
            st.caption("فروق صغيرة طبيعية (مناديب مش ظاهرين في ملف المناديب). لو الفرق كبير يبقى فيه ملف ناقص أو فلتر شغال.")
            ui.table(j, "reconciliation", "ov_t3", height=300)
