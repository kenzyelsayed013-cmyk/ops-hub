import numpy as np
import pandas as pd
import streamlit as st
from core import ui, insights as I

AMBER = "background-color:#FEF3C7;color:#78350F;font-weight:700"
RED = "background-color:#FEE2E2;color:#7F1D1D;font-weight:700"
GREY = "color:#D1D5DB"
INFO = ["Courier ID", "Name", "City", "Supervisor", "Total"]


def _n(v):
    if isinstance(v, str) or pd.isna(v):
        return v if isinstance(v, str) else ""
    return f"{v:,.0f}"


def _pct(a, b):
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(np.asarray(b) > 0, np.asarray(a) / np.asarray(b) * 100, np.nan)


def render():
    f = ui.filters()
    d = ui.get_couriers()
    ui.topbar(f"{f['platform'].upper()}  ·  CANCELLED ORDERS", f, days=(f["d2"] - f["d1"]).days + 1)
    if d.empty:
        st.info("No courier data for this period / filters.")
        return
    base = f"{f['platform']}_{f['city']}"
    d = d.assign(cancelled=(d["accepted"] - d["delivered"]).clip(lower=0))
    acc, dl, can, rj = d["accepted"].sum(), d["delivered"].sum(), d["cancelled"].sum(), d["rejected_courier"].sum()
    rate = can / acc if acc else np.nan

    ui.section("Cancelled = accepted − delivered")
    k = st.columns(5)
    ui.card(k[0], "Accepted orders", f"{acc:,.0f}")
    ui.card(k[1], "Delivered orders", f"{dl:,.0f}")
    ui.card(k[2], "Cancelled orders", f"{can:,.0f}", "", I.status("cancel_rate_di", rate))
    ui.card(k[3], "Cancelled %", f"{rate:.2%}" if pd.notna(rate) else "–", "", I.status("cancel_rate_di", rate),
            I.target_hint("cancel_rate_di") + "  ·  " + I.gap_txt("cancel_rate_di", rate))
    ui.card(k[4], "Rejected by couriers", f"{rj:,.0f}", "", I.grade(rj, 0, 0, False), "Target 0")

    if d["city"].nunique() > 1:
        ui.section("By city")
        g = d.groupby("city").agg(Accepted=("accepted", "sum"), Delivered=("delivered", "sum"), Cancelled=("cancelled", "sum"),
                                  Rejected=("rejected_courier", "sum")).reset_index()
        g["Cancel %"] = _pct(g["Cancelled"], g["Accepted"])
        g = g.rename(columns={"city": "City", "Rejected": "Rejected (Courier)"})
        tot = {"City": "ALL CITIES", "Accepted": acc, "Delivered": dl, "Cancelled": can, "Rejected (Courier)": rj, "Cancel %": rate * 100}
        ui.table(pd.concat([pd.DataFrame([tot]), g], ignore_index=True), f"cancel_cities_{base}", "cn_city", first_row=True, export=False,
                 height=38 + 35 * (len(g) + 2))

    ui.section("Day by day")
    dd = d.groupby("date").agg(Accepted=("accepted", "sum"), Delivered=("delivered", "sum"), Cancelled=("cancelled", "sum"),
                               Rej=("rejected_courier", "sum"), Couriers=("cancelled", lambda x: int((x > 0).sum()))).reset_index().sort_values("date", ascending=False)
    t = pd.DataFrame({"Date": dd["date"].dt.strftime("%Y-%m-%d"), "Day": dd["date"].dt.strftime("%a"), "Accepted": dd["Accepted"],
                      "Delivered": dd["Delivered"], "Cancelled": dd["Cancelled"], "Cancel %": _pct(dd["Cancelled"], dd["Accepted"]),
                      "Couriers with cancels": dd["Couriers"], "Rejected (Courier)": dd["Rej"]})
    top = {"Date": "PERIOD", "Day": "total", "Accepted": acc, "Delivered": dl, "Cancelled": can, "Cancel %": rate * 100,
           "Couriers with cancels": int((d.groupby("courier_id")["cancelled"].sum() > 0).sum()), "Rejected (Courier)": rj}
    ui.table(pd.concat([pd.DataFrame([top]), t], ignore_index=True), f"cancel_days_{base}", "cn_day", first_row=True,
             height=min(600, 38 + 35 * (len(t) + 2)))

    ui.section("Cancelled orders per courier, day by day", "amber = 1 · red = 2 or more · grey = zero")
    idx = ["courier_id", "name", "city", "supervisor"]
    P = d.pivot_table(index=idx, columns="date", values="cancelled", aggfunc="sum")
    P = P.loc[P.sum(axis=1).sort_values(ascending=False).index]
    if not st.checkbox("Show couriers with zero cancels too", key="cn_all"):
        P = P[P.sum(axis=1) > 0]
    if P.empty:
        st.success("No cancelled orders in this period.")
    else:
        dates = list(P.columns)
        labels = {c: c.strftime("%m-%d") for c in dates}
        out = pd.DataFrame({"Courier ID": [i[0] for i in P.index], "Name": [i[1] for i in P.index], "City": [i[2] for i in P.index],
                            "Supervisor": [i[3] for i in P.index], "Total": P.sum(axis=1).values})
        for c in dates:
            out[labels[c]] = P[c].values
        tone = pd.DataFrame("", index=range(len(out)), columns=out.columns)
        for c in dates:
            v = pd.Series(P[c].values)
            tone.loc[v == 0, labels[c]] = GREY
            tone.loc[v == 1, labels[c]] = AMBER
            tone.loc[v >= 2, labels[c]] = RED
        tot = {"Courier ID": "", "Name": "TOTAL", "City": "", "Supervisor": "", "Total": P.sum().sum()}
        tot.update({labels[c]: P[c].sum() for c in dates})
        out = pd.concat([pd.DataFrame([tot]), out], ignore_index=True)
        tone = pd.concat([pd.DataFrame("", index=[0], columns=tone.columns), tone.set_index(tone.index + 1)])
        shown = ui.search(out, "cn_q")
        num = [c for c in out.columns if c not in ("Courier ID", "Name", "City", "Supervisor")]
        sty = shown.style.format(_n, subset=num)
        sty = sty.apply(lambda r: ["font-weight:800;background-color:#14181F;color:#fff"] * len(r) if r.name == 0 else [""] * len(r), axis=1)
        sty = sty.apply(lambda _: tone.loc[shown.index, shown.columns], axis=None)
        st.dataframe(sty, width="stretch", hide_index=True, height=min(760, 38 + 35 * (len(shown) + 1)))
        c1, c2 = st.columns([1, 5])
        with c1:
            ui.download("Export to Excel", out, f"cancelled_by_courier_{base}", "cn_x")
        c2.caption(f"{len(out) - 1:,} couriers")

    ui.section("By courier")
    gc = d.groupby("courier_id").agg(Name=("name", "last"), City=("city", "last"), Supervisor=("supervisor", "last"), Accepted=("accepted", "sum"),
                                     Delivered=("delivered", "sum"), Cancelled=("cancelled", "sum"), Rejected=("rejected_courier", "sum")
                                     ).reset_index().rename(columns={"courier_id": "Courier ID", "Rejected": "Rejected (Courier)"})
    gc["Cancel %"] = _pct(gc["Cancelled"], gc["Accepted"])
    gc["% of All Cancelled"] = _pct(gc["Cancelled"], can)
    if st.checkbox("Only couriers with cancels or rejects", value=True, key="cn_only"):
        gc = gc[(gc["Cancelled"] > 0) | (gc["Rejected (Courier)"] > 0)]
    ui.table(ui.search(gc.sort_values("Cancelled", ascending=False), "cn_q2"), f"cancel_by_courier_{base}", "cn_t", height=480)

    ui.section("By supervisor")
    sp = d.groupby("supervisor").agg(Couriers=("courier_id", "nunique"), Accepted=("accepted", "sum"), Delivered=("delivered", "sum"),
                                     Cancelled=("cancelled", "sum"), Rejected=("rejected_courier", "sum")).reset_index()
    sp["Cancel %"] = _pct(sp["Cancelled"], sp["Accepted"])
    ui.table(sp.rename(columns={"supervisor": "Supervisor", "Rejected": "Rejected (Courier)"}).sort_values("Cancel %", ascending=False),
             f"cancel_by_supervisor_{base}", "cn_sup")
