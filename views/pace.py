import numpy as np
import pandas as pd
import streamlit as st
from core import ui, insights as I

BANDS = [("On track or reached", None, 0), ("Behind by up to 1 order / day", 0, 1), ("Behind by 1 to 2 orders / day", 1, 2),
         ("Behind by 2 to 4 orders / day", 2, 4), ("Behind by more than 4 orders / day", 4, 10**9)]


def _prep(d, last, left):
    req = max(1, int(I.RULES["min_days_month"]))
    g = I.month_orders(d, last, left)
    if g.empty:
        return g
    g = g[g["Working"] > 0].copy()
    g["Days Left To Work"] = np.minimum(max(left, 0), (req - g["Working"]).clip(lower=0))
    g["Short per Day"] = (g["Needed / Day"] - g["Avg / Working Day"]).clip(lower=0)
    g.loc[g["Orders"] >= g["Target"], "Short per Day"] = 0
    g["Expected at Month End"] = g["Orders"] + g["Avg / Working Day"] * g["Days Left To Work"]
    g["Short / Over at Month End"] = g["Expected at Month End"] - g["Target"]
    g["Needed per Day From Now"] = np.where(g["Days Left To Work"] > 0, g["Remaining"] / g["Days Left To Work"].replace(0, np.nan), np.nan)

    def status(r):
        if r["Orders"] >= r["Target"]:
            return "✔ Reached the target"
        if r["Short per Day"] <= 0:
            return "✔ On track"
        return f"{'✖' if r['Short per Day'] >= 2 else '⚠'} Behind by {r['Short per Day']:.1f} orders / day"
    g["Status"] = g.apply(status, axis=1)
    return g


def _row(key, label, x):
    miss = (x["Target"] - x["Expected at Month End"]).clip(lower=0)
    miss[x["Orders"] >= x["Target"]] = 0
    return {key: label, "Couriers": len(x), "Orders So Far": int(x["Orders"].sum()), "Month Target (total)": int(x["Target"].sum()),
            "Still Needed (total)": int(x["Remaining"].sum()), "Reached Target (couriers)": int((x["Orders"] >= x["Target"]).sum()),
            "On Track (couriers)": int(((x["Short per Day"] <= 0) & (x["Orders"] < x["Target"])).sum()),
            "Behind Pace (couriers)": int((x["Short per Day"] > 0).sum()),
            "Expected Orders at Month End": int(x["Expected at Month End"].sum()), "Orders Short at Month End": int(miss.sum())}


def render():
    f = ui.filters()
    R = I.RULES
    req = int(R["min_days_month"])
    months = list(pd.period_range(f["dmin"], f["dmax"], freq="M")[::-1])
    st.markdown(f'<div class="topbar"><div class="t1">{f["platform"].upper()}  ·  MONTHLY ORDERS PACE</div>'
                f'<div class="t2">{f["city"]}  ·  is each courier delivering enough orders to reach his monthly target?</div></div>', unsafe_allow_html=True)
    mo = st.selectbox("Month", months, format_func=lambda p: p.strftime("%B %Y"), key="pc_pick")
    m1, m2 = mo.start_time.date(), mo.end_time.date()
    d = ui.couriers(f["platform"], f["cities"], m1, m2, f["sup"], f["ctype"], f["veh"])
    if d.empty:
        st.info("No courier data in this month.")
        return
    last = d["date"].max()
    left = max(0, (pd.Timestamp(m2) - last).days)
    g = _prep(d, last, left)
    if g.empty:
        st.info("No courier worked in this month.")
        return
    base = f"{f['platform']}_{f['city']}_{mo}"
    tg = {c: I.month_target(c) for c in sorted(g["City"].unique())}
    st.caption(f"Data until {last:%d %b}  ·  {left} days left in the month  ·  " + "  ·  ".join(
        f"{c}: {v} orders = {v / req:.1f} per working day ({v} ÷ {req})" for c, v in tg.items()))

    n = len(g)
    reached = int((g["Orders"] >= g["Target"]).sum())
    behind = int((g["Short per Day"] > 0).sum())
    onp = n - reached - behind
    miss = (g["Target"] - g["Expected at Month End"]).clip(lower=0)
    miss[g["Orders"] >= g["Target"]] = 0
    ui.section("Numbers at a glance")
    k = st.columns(6)
    ui.card(k[0], "Couriers who worked", f"{n:,}")
    ui.card(k[1], "Already reached the target", f"{reached:,}", "", "good" if reached else "neutral")
    ui.card(k[2], "On track", f"{onp:,}", "delivering enough per day", "good" if onp else "neutral")
    ui.card(k[3], "Behind", f"{behind:,}", "delivering less than needed per day", I.grade(behind, 0, 0, False), "Target 0")
    ui.card(k[4], "Orders delivered so far", f"{int(g['Orders'].sum()):,}", f"of {int(g['Target'].sum()):,} total target")
    ui.card(k[5], "Orders short at month end", f"{int(miss.sum()):,}", "if everyone keeps his current pace", I.grade(int(miss.sum()), 0, 0, False))

    ui.section("Per city")
    ct = pd.DataFrame([_row("City", "ALL CITIES", g)] + [_row("City", c, x) for c, x in g.groupby("City")])
    ui.table(ct, f"pace_cities_{base}", "pc_city", first_row=True, height=38 + 35 * (len(ct) + 1))

    ui.section("How far behind")
    rows = []
    for lab, lo, hi in BANDS:
        x = g[g["Short per Day"] <= 0] if lo is None else g[(g["Short per Day"] > lo) & (g["Short per Day"] <= hi)]
        rows.append({"Group": lab, "Couriers": len(x), "Avg Orders / Day": x["Avg / Working Day"].mean() if len(x) else np.nan,
                     "Orders Short at Month End": int(miss[x.index].sum())})
    ui.table(pd.DataFrame(rows), f"pace_bands_{base}", "pc_bands", export=False, height=38 + 35 * 6)

    if g["Supervisor"].nunique() > 1:
        ui.section("Per supervisor")
        sp = pd.DataFrame([_row("Supervisor", c, x) for c, x in g.groupby("Supervisor")]).sort_values("Behind Pace (couriers)", ascending=False)
        ui.table(sp, f"pace_sup_{base}", "pc_sup", export=False, height=min(420, 38 + 35 * (len(sp) + 1)))

    ui.section("Courier by courier")
    only = st.checkbox("Only couriers who are behind", value=True, key="pc_only")
    t = (g[g["Short per Day"] > 0] if only else g).sort_values("Short per Day", ascending=False)
    t = t.rename(columns={"Orders": "Orders So Far", "Target": "Month Target", "Remaining": "Still Needed", "Working": "Days Worked",
                          "Avg / Working Day": "Orders / Day So Far", "Needed / Day": "Orders / Day Needed"})
    t = t[["Courier ID", "Name", "City", "Supervisor", "Status", "Orders So Far", "Month Target", "Still Needed", "Days Worked", "Days Left To Work",
           "Orders / Day So Far", "Orders / Day Needed", "Short per Day", "Needed per Day From Now", "Expected at Month End", "Short / Over at Month End"]]
    if t.empty:
        st.success("Every courier is on track.")
    else:
        ui.table(ui.search(t, "pc_q"), f"pace_couriers_{base}", "pc_t", height=560)
