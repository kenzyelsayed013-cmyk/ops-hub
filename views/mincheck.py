import numpy as np
import pandas as pd
import streamlit as st
from core import ui, insights as I


def _row(key, label, x, sched="Scheduled Courier-days"):
    b = x[~x["orders_ok"]]
    return {key: label, sched: len(x), "Met Minimum": len(x) - len(b), "Below Minimum": len(b), "Couriers Below Minimum": b["courier_id"].nunique(),
            "Orders Missing": int(b["short"].sum()), "Below Because of Orders Only": int(b["shifts_ok"].sum())}


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
    ui.topbar(f"{f['platform'].upper()}  ·  DAILY MINIMUM ORDERS", f, days=(f["d2"] - f["d1"]).days + 1)
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
    per = below.groupby("courier_id").size()
    st.caption(f"A scheduled courier must deliver at least {R['min_orders_normal']} orders on a normal day and {R['min_orders_mandatory']} on a mandatory day (★). "
               "One courier-day = one courier on one scheduled day.")

    ui.section("Numbers at a glance")
    k = st.columns(6)
    ui.card(k[0], "Scheduled courier-days", f"{len(pop):,}", f"{pop['courier_id'].nunique():,} couriers")
    ui.card(k[1], "Met the minimum", f"{len(pop) - len(below):,}", "courier-days", "good")
    ui.card(k[2], "Below the minimum", f"{len(below):,}", "courier-days", I.grade(len(below), 0, 0, False), "Target 0")
    ui.card(k[3], "Couriers below the minimum", f"{below['courier_id'].nunique():,}", "at least once", I.grade(below["courier_id"].nunique(), 0, 0, False))
    ui.card(k[4], "Below on 3 days or more", f"{int((per >= 3).sum()):,}", "couriers", I.grade(int((per >= 3).sum()), 0, 0, False))
    ui.card(k[5], "Orders missing", f"{int(below['short'].sum()):,}", "to reach the minimum on those days")

    ui.section("How many orders short")
    sh = below["short"]
    bands = [("Short by 1 order", sh == 1), ("Short by 2 orders", sh == 2), ("Short by 3 orders", sh == 3), ("Short by 4 to 5 orders", sh.between(4, 5)),
             ("Short by 6 orders or more", sh >= 6)]
    gap = pd.DataFrame([{"Gap": n, "Courier-days": int(m.sum()), "On Normal Days": int((m & ~below["mandatory"]).sum()),
                         "On Mandatory Days": int((m & below["mandatory"]).sum())} for n, m in bands])
    ui.table(gap, f"min_gap_{base}", "mn_gap", export=False, height=38 + 35 * 6)

    ui.section("Day by day")
    rows = []
    for dt, x in pop.groupby("date"):
        r = _row("Date", dt.strftime("%Y-%m-%d"), x, "Scheduled Couriers")
        rows.append({"Date": r.pop("Date"), "Day": dt.strftime("%a") + (" ★" if x["mandatory"].any() else ""), "Minimum Required": int(x["min_orders"].iloc[0]),
                     **r, "Zero Orders": int((x.loc[~x["orders_ok"], "delivered"] == 0).sum())})
    dd = pd.DataFrame(rows).sort_values("Date", ascending=False)
    tt = _row("Date", "PERIOD", pop)
    tt = {"Date": "PERIOD", "Day": "total", "Minimum Required": np.nan, "Scheduled Couriers": tt["Scheduled Courier-days"], **{k_: v for k_, v in tt.items() if k_ not in ("Date", "Scheduled Courier-days")},
          "Zero Orders": int((below["delivered"] == 0).sum())}
    ui.table(pd.concat([pd.DataFrame([tt]), dd[list(tt)]], ignore_index=True), f"min_days_{base}", "mn_day", first_row=True, height=min(560, 38 + 35 * (len(dd) + 2)))

    if pop["city"].nunique() > 1:
        ui.section("Per city")
        ct = pd.DataFrame([_row("City", "ALL CITIES", pop)] + [_row("City", c, x) for c, x in pop.groupby("city")])
        ui.table(ct, f"min_cities_{base}", "mn_city", first_row=True, export=False, height=38 + 35 * (len(ct) + 1))
    if pop["supervisor"].nunique() > 1:
        ui.section("Per supervisor")
        sp = pd.DataFrame([_row("Supervisor", c, x) for c, x in pop.groupby("supervisor")]).sort_values("Below Minimum", ascending=False)
        ui.table(sp, f"min_sup_{base}", "mn_sup", export=False, height=min(420, 38 + 35 * (len(sp) + 1)))

    ui.section("Courier by courier")
    rk = []
    for cid, g in pop.groupby("courier_id"):
        b = g[~g["orders_ok"]]
        if b.empty:
            continue
        rk.append({"Courier ID": cid, "Name": g["name"].iloc[-1], "City": g["city"].iloc[-1], "Supervisor": g["supervisor"].iloc[-1],
                   "Days Scheduled": len(g), "Days Met Minimum": len(g) - len(b), "Days Below Minimum": len(b), "Orders Missing": int(b["short"].sum()),
                   "Avg Orders / Scheduled Day": g["delivered"].mean(), "Avg Minimum Required": g["min_orders"].mean(),
                   "Zero-order Days": int((b["delivered"] == 0).sum()), "Mandatory Days Below": int(b["mandatory"].sum()),
                   "Last Day Below": b["date"].max().strftime("%Y-%m-%d"), "Days Below In A Row (now)": _streak(g)})
    rk = pd.DataFrame(rk).sort_values(["Days Below Minimum", "Orders Missing"], ascending=False) if rk else pd.DataFrame()
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
                          "Orders Delivered": x["delivered"].values, "Minimum Required": x["min_orders"].values, "Short By": x["short"].values,
                          "Mandatory Day": np.where(x["mandatory"], "Yes", "No"),
                          "Shifts Completed": x["shifts_qualified"].astype(int).astype(str).values + " of " + x["shifts_scheduled"].astype(int).astype(str).values,
                          "Shifts OK": np.where(x["shifts_ok"], "✔ OK", "✖ Missed"), "Online Hours": x["valid_hrs"].values,
                          "Why INVALID": np.where(x["shifts_ok"], "Orders only", "Orders + shifts")})
        ui.table(ui.search(t, "mn_q2"), f"min_day_{pd.Timestamp(day):%Y%m%d}", "mn_dayt", text_cols=["Shifts OK"], height=min(460, 38 + 35 * (len(t) + 1)))
