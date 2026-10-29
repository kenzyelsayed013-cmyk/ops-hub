import numpy as np
import pandas as pd
import streamlit as st
from core import ui, insights as I


def _row(key, label, x):
    b = x[~x["orders_ok"]]
    return {key: label, "Scheduled Courier-days": len(x), "Below Min Days": len(b), "Below Min %": len(b) / len(x) * 100 if len(x) else np.nan,
            "Couriers Below Min": b["courier_id"].nunique(), "Orders Short": int(b["short"].sum()), "Only Orders (shifts OK)": int(b["shifts_ok"].sum())}


def _streak(g):
    n = 0
    for ok in reversed(g.sort_values("date")["orders_ok"].tolist()):
        if ok:
            break
        n += 1
    return n


def render():
    f = ui.filters()
    d = ui.get_couriers()
    R = I.RULES
    ui.topbar(f"{f['platform'].upper()}  ·  MINIMUM ORDERS", f, days=(f["d2"] - f["d1"]).days + 1)
    s = I.sched_days(d) if not d.empty else pd.DataFrame()
    if s.empty:
        st.info("No scheduled courier-days in this period / filters.")
        return
    base = f"{f['platform']}_{f['city']}"
    pop = s[s["regular"]].copy()
    if pop.empty:
        st.info("No courier delivered in this period.")
        return
    pop["short"] = (pop["min_orders"] - pop["delivered"]).clip(lower=0)
    below = pop[~pop["orders_ok"]]
    only = below[below["shifts_ok"]]
    zero = below[below["delivered"] == 0]
    per = below.groupby("courier_id").size()
    pct = len(below) / len(pop) * 100
    st.caption(f"Minimum: {R['min_orders_normal']} orders on a normal day · {R['min_orders_mandatory']} on a mandatory day (★) · "
               f"scheduled days of couriers who deliver in the period ({pop['courier_id'].nunique():,} couriers)")

    ui.section("Headline")
    k = st.columns(6)
    ui.card(k[0], "Courier-days below minimum", f"{len(below):,}", f"{pct:.1f}% of {len(pop):,} scheduled", I.grade(pct, 0, 10, False), "Target 0")
    ui.card(k[1], "Couriers below minimum", f"{below['courier_id'].nunique():,}", f"of {pop['courier_id'].nunique():,} scheduled couriers",
            I.grade(below["courier_id"].nunique(), 0, 0, False))
    ui.card(k[2], "Repeat offenders (3+ days)", f"{int((per >= 3).sum()):,}", "below minimum on 3 or more days", I.grade(int((per >= 3).sum()), 0, 0, False))
    ui.card(k[3], "Orders short in total", f"{int(below['short'].sum()):,}", "missing to reach the minimum")
    ui.card(k[4], "INVALID only because of orders", f"{len(only):,}", "their shifts were OK", I.grade(len(only), 0, 0, False))
    ui.card(k[5], "Scheduled days with 0 orders", f"{len(zero):,}", "", I.grade(len(zero), 0, 0, False))

    ui.section("How far below the minimum")
    sh = below["short"]
    bands = [("Short by 1", sh == 1), ("Short by 2", sh == 2), ("Short by 3", sh == 3), ("Short by 4-5", sh.between(4, 5)), ("Short by 6+", sh >= 6)]
    gap = pd.DataFrame([{"Gap": n, "Courier-days": int(m.sum()), "% of Below-Min Days": m.sum() / len(below) * 100 if len(below) else np.nan,
                         "Normal Days": int((m & ~below["mandatory"]).sum()), "Mandatory Days": int((m & below["mandatory"]).sum())} for n, m in bands])
    ui.table(gap, f"min_gap_{base}", "mn_gap", export=False, height=38 + 35 * 6)

    ui.section("Day by day")
    rows = []
    for dt, x in pop.groupby("date"):
        r = _row("Date", dt.strftime("%Y-%m-%d"), x)
        r = {"Date": r.pop("Date"), "Day": dt.strftime("%a") + (" ★" if x["mandatory"].any() else ""), "Min Required": int(x["min_orders"].iloc[0]),
             "Zero Orders": int((x.loc[~x["orders_ok"], "delivered"] == 0).sum()), **r}
        rows.append(r)
    dd = pd.DataFrame(rows).sort_values("Date", ascending=False)
    tt = _row("Date", "PERIOD", pop)
    tt.update({"Day": "total", "Min Required": np.nan, "Zero Orders": len(zero)})
    ui.table(pd.concat([pd.DataFrame([tt]), dd[list(tt)]], ignore_index=True), f"min_days_{base}", "mn_day", first_row=True,
             height=min(560, 38 + 35 * (len(dd) + 2)))

    if pop["city"].nunique() > 1:
        ui.section("By city")
        ct = pd.DataFrame([_row("City", "ALL CITIES", pop)] + [_row("City", c, x) for c, x in pop.groupby("city")])
        ui.table(ct, f"min_cities_{base}", "mn_city", first_row=True, export=False, height=38 + 35 * (len(ct) + 1))
    if pop["supervisor"].nunique() > 1:
        ui.section("By supervisor")
        sp = pd.DataFrame([_row("Supervisor", c, x) for c, x in pop.groupby("supervisor")]).sort_values("Below Min %", ascending=False)
        ui.table(sp, f"min_sup_{base}", "mn_sup", export=False, height=min(420, 38 + 35 * (len(sp) + 1)))

    ui.section("Couriers ranked by days below minimum")
    rk = []
    for cid, g in pop.groupby("courier_id"):
        b = g[~g["orders_ok"]]
        if b.empty:
            continue
        rk.append({"Courier ID": cid, "Name": g["name"].iloc[-1], "City": g["city"].iloc[-1], "Supervisor": g["supervisor"].iloc[-1],
                   "Scheduled Days": len(g), "Days Below Min": len(b), "Days Below Min %": len(b) / len(g) * 100,
                   "Avg Orders / Scheduled Day": g["delivered"].mean(), "Avg Min Required": g["min_orders"].mean(),
                   "Orders Short": int(b["short"].sum()), "Zero-order Days": int((b["delivered"] == 0).sum()),
                   "Mandatory Days Below": int(b["mandatory"].sum()), "Only Orders (shifts OK)": int(b["shifts_ok"].sum()),
                   "Last Below Min": b["date"].max().strftime("%Y-%m-%d"), "Current Streak": _streak(g)})
    rk = pd.DataFrame(rk).sort_values(["Days Below Min", "Orders Short"], ascending=False) if rk else pd.DataFrame()
    if rk.empty:
        st.success("Every scheduled courier met the minimum.")
    else:
        ui.table(ui.search(rk, "mn_q"), f"min_couriers_{base}", "mn_cour", height=520)

    ui.section("Who was below the minimum on a day")
    days = sorted(below["date"].unique(), reverse=True)
    if days:
        day = st.selectbox("Day", days, format_func=lambda x: f"{pd.Timestamp(x):%a %d %b %Y}", key="mn_pick")
        x = below[below["date"] == pd.Timestamp(day)].sort_values("short", ascending=False)
        t = pd.DataFrame({"Courier ID": x["courier_id"].values, "Name": x["name"].values, "City": x["city"].values, "Supervisor": x["supervisor"].values,
                          "Orders": x["delivered"].values, "Min Orders": x["min_orders"].values, "Short By": x["short"].values,
                          "Mandatory Day": np.where(x["mandatory"], "Yes", "No"),
                          "Shifts": x["shifts_qualified"].astype(int).astype(str).values + "/" + x["shifts_scheduled"].astype(int).astype(str).values,
                          "Shifts OK": np.where(x["shifts_ok"], "✔ OK", "✖ Missed"), "Valid Hrs": x["valid_hrs"].values,
                          "Why INVALID": np.where(x["shifts_ok"], "Orders only", "Orders + shifts")})
        ui.table(ui.search(t, "mn_q2"), f"min_day_{pd.Timestamp(day):%Y%m%d}", "mn_dayt", text_cols=["Shifts OK"], height=min(460, 38 + 35 * (len(t) + 1)))
