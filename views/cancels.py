import streamlit as st
from core import ui


def render():
    f = ui.filters()
    d = ui.get_couriers()
    ui.topbar(f"{f['platform'].upper()}  ·  CANCELLATIONS & REJECTIONS", f, days=(f["d2"] - f["d1"]).days + 1)
    if d.empty:
        st.info("No courier data for this period / filters.")
        return
    base = f"{f['platform']}_{f['city']}"
    st.caption("The Keeta export has real counts for Rejected (Courier) and Rejected (Auto). "
               "Delivery-Issue cancellations come only as a rate, so their count here is an estimate (rate × accepted tasks). "
               "For the exact count per cancellation type we need another export from Keeta.")
    ui.section("CANCELLATION KPIs")
    k = st.columns(4)
    k[0].metric("Rejected (Courier)", f"{d['rejected_courier'].sum():,.0f}", border=True)
    k[1].metric("Rejected (Auto)", f"{d['rejected_auto'].sum():,.0f}", border=True)
    k[2].metric("Delivery-Issue Cancels (est.)", f"{d['di_cancels'].sum():,.0f}", border=True)
    k[3].metric("Total Rejected", f"{d['rejected'].sum():,.0f}", border=True)

    kinds = {"rejected_courier": "Rejected (Courier)", "rejected_auto": "Rejected (Auto)",
             "di_cancels": "Delivery-Issue Cancels (est.)"}
    ui.section("DAILY TREND")
    sel = st.multiselect("Type", list(kinds), default=list(kinds), format_func=kinds.get, key="cn_kinds")
    dd = d.groupby("date")[list(kinds)].sum().reset_index()
    if sel:
        st.plotly_chart(ui.line(dd, "date", sel, "Daily cancellations", names=kinds, bar=True), width="stretch")

    ui.section("BY COURIER")
    g = d.groupby("courier_id").agg(Name=("name", "last"), Supervisor=("supervisor", "last"), Accepted=("accepted", "sum"),
                                    Rejected=("rejected", "sum"), Rejected_Courier=("rejected_courier", "sum"),
                                    Rejected_Auto=("rejected_auto", "sum"), DI_Cancels_est=("di_cancels", "sum")
                                    ).reset_index().rename(columns={"courier_id": "Courier ID"})
    g["Reject %"] = g["Rejected"] / (g["Accepted"] + g["Rejected"]).replace(0, float("nan")) * 100
    g["Total Cancels"] = g["Rejected"] + g["DI_Cancels_est"]
    g = g[g["Total Cancels"] > 0].sort_values("Total Cancels", ascending=False)
    ui.table(ui.search(g, "cn_q"), f"cancels_by_courier_{base}", "cn_t", height=480)
