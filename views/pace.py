import numpy as np
import pandas as pd
import streamlit as st
from core import ui, insights as I

BANDS = [("On track or ahead", None, 0), ("Behind by 1 to 20 orders", 0, 20), ("Behind by 21 to 50 orders", 20, 50),
         ("Behind by 51 to 100 orders", 50, 100), ("Behind by more than 100 orders", 100, 10**9)]


def _prep(d, last, left):
    g = I.month_orders(d, last, left)
    if g.empty:
        return g
    g = g[g["Working"] > 0].copy()
    g["Behind By"] = (-g["Over / Under"]).clip(lower=0)
    g.loc[g["Orders"] >= g["Target"], "Behind By"] = 0

    def status(r):
        if r["Orders"] >= r["Target"]:
            return "✔ Reached the full target"
        if r["Behind By"] <= 0:
            return "✔ On track"
        return f"{'⚠' if r['Behind By'] < r['Needed / Day'] else '✖'} Behind by {r['Behind By']:.0f} orders"
    g["Status"] = g.apply(status, axis=1)
    return g


def _row(key, label, x):
    return {key: label, "Couriers": len(x), "Orders So Far": int(x["Orders"].sum()), "Target So Far": int(round(x["Prorated Target"].sum())),
            "Over / Under": int(round(x["Over / Under"].sum())), "On Track (couriers)": int((x["Behind By"] <= 0).sum()),
            "Behind (couriers)": int((x["Behind By"] > 0).sum()), "Reached Full Target (couriers)": int((x["Orders"] >= x["Target"]).sum()),
            "Orders Behind (total)": int(round(x["Behind By"].sum()))}


def render():
    f = ui.filters()
    R = I.RULES
    req = max(1, int(R["min_days_month"]))
    months = list(pd.period_range(f["dmin"], f["dmax"], freq="M")[::-1])
    st.markdown(f'<div class="topbar"><div class="t1">{f["platform"].upper()}  ·  MONTHLY ORDERS TARGET</div>'
                f'<div class="t2">{f["city"]}  ·  is each courier delivering the orders his target needs for the days he worked?</div></div>', unsafe_allow_html=True)
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
    mkey = mo.strftime("%Y-%m")
    tg = {c: I.month_target(c, mkey) for c in sorted(g["City"].unique())}
    c0 = next(iter(tg))
    st.caption(f"Data until {last:%d %b}  ·  {left} days left  ·  monthly target: " + "  ·  ".join(f"{c} {v}" for c, v in tg.items()) +
               f"  ·  courier target = target ÷ {req} × days he worked  (example {c0}: {tg[c0]} ÷ {req} = {tg[c0] / req:.1f} per day, 12 days = {tg[c0] / req * 12:.0f} orders)")

    n = len(g)
    reached = int((g["Orders"] >= g["Target"]).sum())
    behind = int((g["Behind By"] > 0).sum())
    ui.section("Numbers at a glance")
    k = st.columns(6)
    ui.card(k[0], "Couriers who worked", f"{n:,}")
    ui.card(k[1], "On track or ahead", f"{n - behind:,}", "delivered what their days need", "good" if n - behind else "neutral")
    ui.card(k[2], "Behind", f"{behind:,}", "less than their days need", I.grade(behind, 0, 0, False), "Target 0")
    ui.card(k[3], "Reached the full month target", f"{reached:,}", "", "good" if reached else "neutral")
    ui.card(k[4], "Orders delivered", f"{int(g['Orders'].sum()):,}", f"target so far {int(round(g['Prorated Target'].sum())):,}")
    ui.card(k[5], "Orders behind (total)", f"{int(round(g['Behind By'].sum())):,}", "sum over the couriers who are behind", I.grade(int(g["Behind By"].sum()), 0, 0, False))

    ui.section("Per city")
    ct = pd.DataFrame([_row("City", "ALL CITIES", g)] + [_row("City", c, x) for c, x in g.groupby("City")])
    ct.insert(1, "Month Target / Courier", [""] + [tg[c] for c in ct["City"][1:]])
    ui.table(ct, f"pace_cities_{base}", "pc_city", first_row=True, height=38 + 35 * (len(ct) + 1))

    ui.section("How far behind")
    rows = []
    for lab, lo, hi in BANDS:
        x = g[g["Behind By"] <= 0] if lo is None else g[(g["Behind By"] > lo) & (g["Behind By"] <= hi)]
        rows.append({"Group": lab, "Couriers": len(x), "Orders Behind (total)": int(round(x["Behind By"].sum()))})
    ui.table(pd.DataFrame(rows), f"pace_bands_{base}", "pc_bands", export=False, height=38 + 35 * 6)

    if g["Supervisor"].nunique() > 1:
        ui.section("Per supervisor")
        sp = pd.DataFrame([_row("Supervisor", c, x) for c, x in g.groupby("Supervisor")]).sort_values("Behind (couriers)", ascending=False)
        ui.table(sp, f"pace_sup_{base}", "pc_sup", export=False, height=min(420, 38 + 35 * (len(sp) + 1)))

    ui.section("Courier by courier")
    only = st.checkbox("Only couriers who are behind", value=True, key="pc_only")
    t = (g[g["Behind By"] > 0] if only else g).sort_values("Over / Under")
    t = t.rename(columns={"Working": "Days Worked", "Orders": "Orders So Far", "Avg / Working Day": "Orders / Day So Far", "Needed / Day": "Orders / Day Needed",
                          "Prorated Target": "His Target (days worked)", "Target": "Month Target (full)", "Remaining": "Still Needed (full)"})
    t = t[["Courier ID", "Name", "City", "Supervisor", "Status", "Days Worked", "Orders So Far", "His Target (days worked)", "Over / Under",
           "Orders / Day So Far", "Orders / Day Needed", "Month Target (full)", "Still Needed (full)"]]
    if t.empty:
        st.success("Every courier is on track.")
    else:
        ui.table(ui.search(t, "pc_q"), f"pace_couriers_{base}", "pc_t", height=560)
