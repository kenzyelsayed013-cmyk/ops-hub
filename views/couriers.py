import pandas as pd
import streamlit as st
from core import ui, metrics as M
from core.config import SLOT_COLS


def _search(df, key, cols=("Courier ID", "Name")):
    q = st.text_input("🔎 بحث بالاسم أو الـ ID", key=key).strip().lower()
    if not q:
        return df
    m = False
    for c in cols:
        m = m | df[c].astype(str).str.lower().str.contains(q, regex=False)
    return df[m]


def render():
    f = ui.filters()
    st.title(f"🏍️ المناديب · {f['platform']} · {f['city']}")
    d = ui.get_couriers()
    if d.empty:
        st.info("مفيش داتا مناديب للفترة/الفلاتر دي.")
        return
    tabs = st.tabs(["ملخص المناديب", "ساعات الدوام اليومية", "الشيفتات", "الكانسل والرفض"])
    base = f"{f['platform']}_{f['city']}"

    # ------------------------------------------------ summary
    with tabs[0]:
        s = M.courier_summary(d)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("مناديب", f"{len(s):,}")
        c2.metric("مناديب شغالين", f"{(s['Active_Days'] > 0).sum():,}")
        c3.metric("Delivered", f"{s['Delivered'].sum():,.0f}")
        c4.metric("متوسط طلبات/يوم شغل", f"{s['Orders_per_Active_Day'].mean():.1f}")
        a, b = st.columns(2)
        only_active = a.checkbox("اخفي اللي مشتغلش خالص", value=True, key="cs_active")
        min_del = b.number_input("أقل عدد Delivered", 0, value=0, step=10, key="cs_min")
        v = s[(s["Delivered"] >= min_del) & ((s["Active_Days"] > 0) | (not only_active))]
        v = _search(v, "cs_q")
        ui.table(v, f"couriers_summary_{base}", "cs_t", height=520)
        top = v.nlargest(15, "Delivered")
        if not top.empty:
            st.plotly_chart(ui.line(top, "Name", ["Delivered"], "أعلى 15 مندوب Delivered", bar=True,
                                    names={"Delivered": "Delivered"}), width="stretch")

    # ------------------------------------------------ hours
    with tabs[1]:
        hrs = d.assign(valid_hrs=d["valid_hrs"].round(2)).pivot_table(
            index=["courier_id", "name"], columns="date", values="valid_hrs", aggfunc="sum").fillna(0)
        act = (hrs > 0)
        avg = (hrs.sum(axis=1) / act.sum(axis=1).replace(0, float("nan")))
        hrs.columns = [c.strftime("%m-%d") for c in hrs.columns]
        hrs.insert(0, "Avg Hrs / Active Day", avg.round(2))
        hrs.insert(1, "Total Hrs", hrs.drop(columns="Avg Hrs / Active Day").sum(axis=1).round(1))
        hrs.insert(2, "Active Days", act.sum(axis=1))
        hrs = hrs.reset_index().rename(columns={"courier_id": "Courier ID", "name": "Name"})
        daily = d.groupby("date").agg(Total_Valid_Hrs=("valid_hrs", "sum"), Active=("active", "sum")).reset_index()
        daily["Avg_Hrs_per_Active_Courier"] = daily["Total_Valid_Hrs"] / daily["Active"].replace(0, float("nan"))
        st.plotly_chart(ui.line(daily, "date", ["Avg_Hrs_per_Active_Courier"], "متوسط ساعات الدوام لكل مندوب شغال في اليوم",
                                names={"Avg_Hrs_per_Active_Courier": "Avg hrs / active courier"}), width="stretch")
        st.caption("Valid Online Hours = ساعات الدوام المعتمدة من Keeta (مش الـ App Online).")
        ui.table(_search(hrs, "hr_q"), f"daily_hours_{base}", "hr_t", height=520)

    # ------------------------------------------------ shifts
    with tabs[2]:
        sd = M.shift_day_stats(d)
        if sd.empty:
            st.info("مفيش شيفتات مجدولة في الفترة دي.")
        else:
            st.caption("كل مندوب ليه 3 شيفتات غالباً من 6 فترات (00-03، 03-08، 08-12، 12-16، 16-20، 20-24). "
                       "'كمّل كل شيفتاته' = كل الفترات المجدولة له qualified.")
            tot_c = sd["Couriers_Scheduled"].sum()
            k1, k2, k3 = st.columns(3)
            k1.metric("كمّلوا كل شيفتاتهم", f"{sd['Completed_All'].sum() / tot_c:.1%}", help="من إجمالي (مندوب × يوم) مجدول")
            k2.metric("شيفتات qualified", f"{sd['Qualified_Shifts'].sum() / sd['Sched_Shifts'].sum():.1%}")
            k3.metric("مندوب-يوم مجدول", f"{tot_c:,}")
            st.plotly_chart(ui.line(sd, "date", ["Completed_All_%", "Qualified_Shifts_%"], "نسبة الالتزام اليومية",
                                    names={"Completed_All_%": "كمّلوا كل الشيفتات %",
                                           "Qualified_Shifts_%": "شيفتات qualified %"}), width="stretch")
            st.markdown("**لكل مندوب**")
            sc = M.shift_courier_stats(d)
            only_bad = st.checkbox("اعرض اللي ناقصهم شيفتات بس", key="sh_bad")
            if only_bad:
                sc = sc[sc["Days_Not_Completed"] > 0]
            ui.table(_search(sc, "sh_q"), f"shifts_by_courier_{base}", "sh_t1", height=380)
            st.markdown("**تفصيل يومي** (✅ qualified · ❌ unqualified · · مش مجدول)")
            det = M.shift_symbols(d[d["shifts_scheduled"] > 0])
            if st.checkbox("اعرض الأيام اللي فيها شيفت ناقص بس", key="sh_bad2"):
                det = det[det["shifts_qualified"] < det["shifts_scheduled"]]
            det = det.rename(columns={"date": "Date", "courier_id": "Courier ID", "name": "Name",
                                      "valid_hrs": "Valid Hrs", "shifts_scheduled": "Scheduled",
                                      "shifts_qualified": "Qualified"})
            det["Date"] = det["Date"].dt.strftime("%Y-%m-%d")
            ui.table(_search(det, "sh_q2"), f"shifts_detail_{base}", "sh_t2", height=380)

    # ------------------------------------------------ cancels
    with tabs[3]:
        st.caption("المتاح في إكسبورت Keeta: رفض المندوب، الرفض التلقائي (أعداد حقيقية)، وكانسل Delivery Issue كنسبة فقط — "
                   "فعدده هنا **تقريبي** (النسبة × Accepted). لو عايز العدد الحقيقي لكل نوع كانسل محتاجين إكسبورت تاني.")
        k = st.columns(4)
        tot_rej_c, tot_rej_a, tot_di = d["rejected_courier"].sum(), d["rejected_auto"].sum(), d["di_cancels"].sum()
        k[0].metric("رفض المندوب", f"{tot_rej_c:,.0f}")
        k[1].metric("رفض تلقائي", f"{tot_rej_a:,.0f}")
        k[2].metric("Delivery Issue (تقريبي)", f"{tot_di:,.0f}")
        k[3].metric("إجمالي Rejected", f"{d['rejected'].sum():,.0f}")
        kinds = {"rejected_courier": "رفض المندوب", "rejected_auto": "رفض تلقائي", "di_cancels": "Delivery Issue (تقريبي)"}
        sel = st.multiselect("النوع", list(kinds), default=list(kinds), format_func=kinds.get, key="cn_kinds")
        dd = d.groupby("date")[list(kinds)].sum().reset_index()
        if sel:
            st.plotly_chart(ui.line(dd, "date", sel, "الكانسل اليومي", names=kinds, bar=True), width="stretch")
        g = d.groupby("courier_id").agg(Name=("name", "last"), Supervisor=("supervisor", "last"),
                                        Accepted=("accepted", "sum"), Rejected=("rejected", "sum"),
                                        Rejected_Courier=("rejected_courier", "sum"), Rejected_Auto=("rejected_auto", "sum"),
                                        DI_Cancels_est=("di_cancels", "sum")).reset_index().rename(columns={"courier_id": "Courier ID"})
        g["Reject_%"] = (g["Rejected"] / (g["Accepted"] + g["Rejected"]).replace(0, float("nan")) * 100)
        g["Total_Cancels"] = g["Rejected"] + g["DI_Cancels_est"]
        g = g[g["Total_Cancels"] > 0].sort_values("Total_Cancels", ascending=False)
        ui.table(_search(g, "cn_q"), f"cancels_by_courier_{base}", "cn_t", height=420)
