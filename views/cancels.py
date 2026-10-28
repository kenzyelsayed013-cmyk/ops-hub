import numpy as np
import pandas as pd
import streamlit as st
from core import ui, insights as I

AMBER = "background-color:#FEF3C7;color:#78350F;font-weight:700"
RED = "background-color:#FEE2E2;color:#7F1D1D;font-weight:700"
GREY = "color:#D1D5DB"
MODES = ["Cancelled (accepted − delivered)", "Delivery Issue % (as in the sheet)", "Delivery-Issue (est. count)"]


def _fmt(dec):
    def f(v):
        if isinstance(v, str) or pd.isna(v):
            return v if isinstance(v, str) else ""
        return f"{v:,.{dec}f}"
    return f


def _pct(a, b):
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(np.asarray(b) > 0, np.asarray(a) / np.asarray(b) * 100, np.nan)


def _di(df, wcol="accepted"):
    return I.di_avg(df, "cancel_rate_di", wcol) * 100


def render():
    f = ui.filters()
    d = ui.get_couriers()
    co = ui.get_company()
    ui.topbar(f"{f['platform'].upper()}  ·  CANCELLED ORDERS", f, days=(f["d2"] - f["d1"]).days + 1)
    if d.empty:
        st.info("No courier data for this period / filters.")
        return
    base = f"{f['platform']}_{f['city']}"
    d = d.assign(cancelled=(d["accepted"] - d["delivered"]).clip(lower=0), di_pct=d["cancel_rate_di"] * 100)
    cdaily, ctot = I.company_stats(co)
    di_day = cdaily.set_index("date")["cancel_rate_di"] * 100 if not cdaily.empty else pd.Series(dtype=float)
    acc, dl, can, rj, diest = d["accepted"].sum(), d["delivered"].sum(), d["cancelled"].sum(), d["rejected_courier"].sum(), d["di_cancels"].sum()
    rate = can / acc if acc else np.nan
    di_tot = ctot.get("cancel_rate_di", np.nan) * 100 if ctot else _di(d)
    how = "average of daily rates" if I.RULES.get("di_total", "average") == "average" else "weighted by volume"

    ui.section("Cancelled = accepted − delivered")
    k = st.columns(6)
    ui.card(k[0], "Accepted orders", f"{acc:,.0f}")
    ui.card(k[1], "Delivered orders", f"{dl:,.0f}")
    ui.card(k[2], "Cancelled orders", f"{can:,.0f}", "", I.status("cancel_rate", rate))
    ui.card(k[3], "Cancelled %", f"{rate:.2%}" if pd.notna(rate) else "–", "", I.status("cancel_rate", rate),
            I.target_hint("cancel_rate") + "  ·  " + I.gap_txt("cancel_rate", rate))
    ui.card(k[4], "Rejected by couriers", f"{rj:,.0f}", "", I.grade(rj, 0, 0, False), "Target 0")
    ui.card(k[5], "Delivery Issue %", f"{di_tot:.2f}%" if pd.notna(di_tot) else "–", f"≈ {diest:,.0f} orders (est.)", "neutral", how)

    if d["city"].nunique() > 1:
        ui.section("By city")
        g = d.groupby("city").agg(Accepted=("accepted", "sum"), Delivered=("delivered", "sum"), Cancelled=("cancelled", "sum"),
                                  Rejected=("rejected_courier", "sum"), DI=("di_cancels", "sum")).reset_index()
        g["Cancel %"] = _pct(g["Cancelled"], g["Accepted"])
        cdi = {c: (I.company_stats(co[co["city"] == c])[1].get("cancel_rate_di", np.nan) * 100 if not co.empty else np.nan) for c in g["city"]}
        g["Delivery Issue %"] = g["city"].map(cdi)
        g = g.rename(columns={"city": "City", "Rejected": "Rejected (Courier)", "DI": "Delivery-Issue (est.)"})
        tot = {"City": "ALL CITIES", "Accepted": acc, "Delivered": dl, "Cancelled": can, "Cancel %": rate * 100, "Delivery Issue %": di_tot,
               "Rejected (Courier)": rj, "Delivery-Issue (est.)": diest}
        ui.table(pd.concat([pd.DataFrame([tot]), g[list(tot)]], ignore_index=True), f"cancel_cities_{base}", "cn_city", first_row=True,
                 height=38 + 35 * (len(g) + 2))

    ui.section("Day by day")
    dd = d.groupby("date").agg(Accepted=("accepted", "sum"), Delivered=("delivered", "sum"), Cancelled=("cancelled", "sum"),
                               DI=("di_cancels", "sum"), Rej=("rejected_courier", "sum"),
                               Couriers=("cancelled", lambda x: int((x > 0).sum()))).reset_index().sort_values("date", ascending=False)
    t = pd.DataFrame({"Date": dd["date"].dt.strftime("%Y-%m-%d"), "Day": dd["date"].dt.strftime("%a"), "Accepted": dd["Accepted"],
                      "Delivered": dd["Delivered"], "Cancelled": dd["Cancelled"], "Cancel %": _pct(dd["Cancelled"], dd["Accepted"]),
                      "Delivery Issue %": dd["date"].map(di_day).values, "Delivery-Issue (est.)": dd["DI"],
                      "Couriers with cancels": dd["Couriers"], "Rejected (Courier)": dd["Rej"]})
    top = {"Date": "PERIOD", "Day": "total / avg", "Accepted": acc, "Delivered": dl, "Cancelled": can, "Cancel %": rate * 100,
           "Delivery Issue %": di_tot, "Delivery-Issue (est.)": diest,
           "Couriers with cancels": int((d.groupby("courier_id")["cancelled"].sum() > 0).sum()), "Rejected (Courier)": rj}
    ui.table(pd.concat([pd.DataFrame([top]), t], ignore_index=True), f"cancel_days_{base}", "cn_day", first_row=True,
             height=min(600, 38 + 35 * (len(t) + 2)))

    ui.section("Per courier, day by day")
    mx = st.radio("Show", MODES, horizontal=True, key="cn_metric2")
    idx = ["courier_id", "name", "city", "supervisor"]
    if mx == MODES[0]:
        P, dec = d.pivot_table(index=idx, columns="date", values="cancelled", aggfunc="sum"), 0
    elif mx == MODES[1]:
        P, dec = d.pivot_table(index=idx, columns="date", values="di_pct", aggfunc="mean"), 2
    else:
        P, dec = d.pivot_table(index=idx, columns="date", values="di_cancels", aggfunc="sum"), 1
    P = P.fillna(0) if mx == MODES[1] else P
    if mx == MODES[1]:
        tc = pd.Series({k_: _di(g_) for k_, g_ in d.groupby(idx)}).reindex(P.index)
        P = P.loc[tc.fillna(0).sort_values(ascending=False).index]
        tcol = tc.reindex(P.index).values
    else:
        P = P.loc[P.sum(axis=1).sort_values(ascending=False).index]
        tcol = P.sum(axis=1).values
    if not st.checkbox("Show couriers with zero too", key="cn_all"):
        keep = (np.nan_to_num(tcol) > 0)
        P, tcol = P[keep], tcol[keep]
    if P.empty:
        st.success("Nothing in this period.")
    else:
        dates = list(P.columns)
        labels = {c: c.strftime("%m-%d") for c in dates}
        tname = "Avg" if mx == MODES[1] else "Total"
        out = pd.DataFrame({"Courier ID": [i[0] for i in P.index], "Name": [i[1] for i in P.index], "City": [i[2] for i in P.index],
                            "Supervisor": [i[3] for i in P.index], tname: tcol})
        for c in dates:
            out[labels[c]] = P[c].values
        tone = pd.DataFrame("", index=range(len(out)), columns=out.columns)
        for c in dates:
            v = pd.Series(P[c].values)
            tone.loc[v.fillna(0) == 0, labels[c]] = GREY
            if mx == MODES[0]:
                tone.loc[v == 1, labels[c]] = AMBER
                tone.loc[v >= 2, labels[c]] = RED
        tot = {"Courier ID": "", "Name": "TOTAL" if mx != MODES[1] else "ALL (sheet)", "City": "", "Supervisor": "",
               tname: P.sum().sum() if mx != MODES[1] else di_tot}
        tot.update({labels[c]: (P[c].sum() if mx != MODES[1] else di_day.get(c, np.nan)) for c in dates})
        out = pd.concat([pd.DataFrame([tot]), out], ignore_index=True)
        tone = pd.concat([pd.DataFrame("", index=[0], columns=tone.columns), tone.set_index(tone.index + 1)])
        shown = ui.search(out, "cn_q")
        num = [c for c in out.columns if c not in ("Courier ID", "Name", "City", "Supervisor")]
        sty = shown.style.format(_fmt(dec), subset=num)
        sty = sty.apply(lambda r: ["font-weight:800;background-color:#14181F;color:#fff"] * len(r) if r.name == 0 else [""] * len(r), axis=1)
        sty = sty.apply(lambda _: tone.loc[shown.index, shown.columns], axis=None)
        st.dataframe(sty, width="stretch", hide_index=True, height=min(760, 38 + 35 * (len(shown) + 1)))
        ui.export_row(out, f"cancel_matrix_{base}", "cn_x", title=f"{mx} per courier, day by day", first_row=True, tone=tone)

    ui.section("By courier")
    gc = d.groupby("courier_id").agg(Name=("name", "last"), City=("city", "last"), Supervisor=("supervisor", "last"), Accepted=("accepted", "sum"),
                                     Delivered=("delivered", "sum"), Cancelled=("cancelled", "sum"), DI=("di_cancels", "sum"),
                                     Rejected=("rejected_courier", "sum")).reset_index().rename(
        columns={"courier_id": "Courier ID", "Rejected": "Rejected (Courier)", "DI": "Delivery-Issue (est.)"})
    gc["Cancel %"] = _pct(gc["Cancelled"], gc["Accepted"])
    gc["Delivery Issue %"] = gc["Courier ID"].map({k_: _di(g_) for k_, g_ in d.groupby("courier_id")})
    gc["% of All Cancelled"] = _pct(gc["Cancelled"], can)
    gc = gc[["Courier ID", "Name", "City", "Supervisor", "Accepted", "Delivered", "Cancelled", "Cancel %", "Delivery Issue %",
             "Delivery-Issue (est.)", "Rejected (Courier)", "% of All Cancelled"]]
    if st.checkbox("Only couriers with cancels, delivery issues or rejects", value=True, key="cn_only"):
        gc = gc[(gc["Cancelled"] > 0) | (gc["Rejected (Courier)"] > 0) | (gc["Delivery-Issue (est.)"] > 0)]
    ui.table(ui.search(gc.sort_values("Cancelled", ascending=False), "cn_q2"), f"cancel_by_courier_{base}", "cn_t", height=480)

    ui.section("By supervisor")
    sp = d.groupby("supervisor").agg(Couriers=("courier_id", "nunique"), Accepted=("accepted", "sum"), Delivered=("delivered", "sum"),
                                     Cancelled=("cancelled", "sum"), DI=("di_cancels", "sum"), Rejected=("rejected_courier", "sum")).reset_index()
    sp["Cancel %"] = _pct(sp["Cancelled"], sp["Accepted"])
    sp["Delivery Issue %"] = sp["supervisor"].map({k_: _di(g_) for k_, g_ in d.groupby("supervisor")})
    ui.table(sp.rename(columns={"supervisor": "Supervisor", "Rejected": "Rejected (Courier)", "DI": "Delivery-Issue (est.)"})
             .sort_values("Cancel %", ascending=False), f"cancel_by_supervisor_{base}", "cn_sup")
