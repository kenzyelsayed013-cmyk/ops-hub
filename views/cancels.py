import numpy as np
import pandas as pd
import streamlit as st
from core import ui, metrics as M, insights as I


def render():
    f = ui.filters()
    d = ui.get_couriers()
    ui.topbar(f"{f['platform'].upper()}  ·  CANCELLATIONS & REJECTIONS", f, days=(f["d2"] - f["d1"]).days + 1)
    if d.empty:
        st.info("No courier data for this period / filters.")
        return
    base = f"{f['platform']}_{f['city']}"
    ui.legend()

    rej, acc = d["rejected"].sum(), d["accepted"].sum()
    rt = rej / (rej + acc) * 100 if (rej + acc) else np.nan
    g = d.groupby("courier_id")["rejected"].sum().sort_values(ascending=False)
    top10 = g.head(10).sum() / rej * 100 if rej else np.nan

    ui.section("Cancellation numbers")
    k = st.columns(6)
    ui.card(k[0], "Rejected (courier)", f"{d['rejected_courier'].sum():,.0f}")
    ui.card(k[1], "Rejected (auto)", f"{d['rejected_auto'].sum():,.0f}")
    ui.card(k[2], "Delivery-issue cancels (est.)", f"{d['di_cancels'].sum():,.0f}")
    ui.card(k[3], "Total rejected", f"{rej:,.0f}")
    ui.card(k[4], "Rejected by couriers", f"{d['rejected_courier'].sum():,.0f}", "", I.grade(d["rejected_courier"].sum(), 0, 0, False), "Target 0")
    ui.card(k[5], "Top 10 couriers' share", f"{top10:.0f}%" if pd.notna(top10) else "–",
            "of all rejections")

    ui.section("Day by day", "newest first · red days are where the most orders were lost")
    dd = d.groupby("date").agg(Accepted=("accepted", "sum"), Rejected_Courier=("rejected_courier", "sum"),
                               Rejected_Auto=("rejected_auto", "sum"), DI=("di_cancels", "sum"),
                               Rejected=("rejected", "sum")).reset_index().sort_values("date", ascending=False)
    t = pd.DataFrame({"Date": dd["date"].dt.strftime("%Y-%m-%d"), "Day": dd["date"].dt.strftime("%a"), "Accepted": dd["Accepted"],
                      "Rejected (Courier)": dd["Rejected_Courier"], "Rejected (Auto)": dd["Rejected_Auto"],
                      "Total Rejected": dd["Rejected"], "Delivery-Issue (est.)": dd["DI"],
                      "Reject %": dd["Rejected"] / (dd["Accepted"] + dd["Rejected"]).replace(0, float("nan")) * 100})
    ui.table(t, f"cancels_by_day_{base}", "cn_day", height=min(740, 38 + 35 * (len(t) + 1)))

    ui.section("By supervisor", "which team loses the most orders")
    sp = d.groupby("supervisor").agg(Couriers=("courier_id", "nunique"), Accepted=("accepted", "sum"), Rejected=("rejected", "sum"),
                                     Rejected_Courier=("rejected_courier", "sum"), Rejected_Auto=("rejected_auto", "sum")).reset_index()
    sp["Reject %"] = sp["Rejected"] / (sp["Accepted"] + sp["Rejected"]).replace(0, float("nan")) * 100
    ui.table(sp.rename(columns={"supervisor": "Supervisor", "Rejected_Courier": "Rejected (Courier)", "Rejected_Auto": "Rejected (Auto)"})
             .sort_values("Reject %", ascending=False), f"cancels_by_supervisor_{base}", "cn_sup")

    ui.section("By courier", "highest total cancels first")
    gc = d.groupby("courier_id").agg(Name=("name", "last"), Supervisor=("supervisor", "last"), Accepted=("accepted", "sum"),
                                     Rejected=("rejected", "sum"), Rejected_Courier=("rejected_courier", "sum"),
                                     Rejected_Auto=("rejected_auto", "sum"), DI_Cancels_est=("di_cancels", "sum")
                                     ).reset_index().rename(columns={"courier_id": "Courier ID"})
    gc["Reject %"] = gc["Rejected"] / (gc["Accepted"] + gc["Rejected"]).replace(0, float("nan")) * 100
    gc["Total Cancels"] = gc["Rejected"] + gc["DI_Cancels_est"]
    gc["% of All Rejections"] = gc["Rejected"] / rej * 100 if rej else np.nan
    gc = gc[gc["Total Cancels"] > 0].sort_values("Total Cancels", ascending=False).rename(
        columns={"Rejected_Courier": "Rejected (Courier)", "Rejected_Auto": "Rejected (Auto)", "DI_Cancels_est": "Delivery-Issue (est.)"})
    ui.table(ui.search(gc, "cn_q"), f"cancels_by_courier_{base}", "cn_t", height=480)
