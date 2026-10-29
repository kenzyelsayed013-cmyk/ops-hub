import numpy as np
import pandas as pd
import streamlit as st
from core import ui, insights as I

BANDS = [("Far behind (under 70%)", 0, 70), ("Behind (70-85%)", 70, 85), ("Slightly behind (85-100%)", 85, 100),
         ("On pace (100-120%)", 100, 120), ("Ahead (120%+)", 120, 10**9)]


def _prep(d, last, left):
    R = I.RULES
    req = max(1, int(R["min_days_month"]))
    g = I.month_orders(d, last, left)
    if g.empty:
        return g
    g = g[g["Working"] > 0].copy()
    g["Pace %"] = g["Avg / Working Day"] / g["Needed / Day"] * 100
    g["Expected So Far"] = g["Needed / Day"] * g["Working"]
    g["Orders vs Expected"] = g["Orders"] - g["Expected So Far"]
    rem_work = (req - g["Working"]).clip(lower=0).clip(upper=max(left, 0))
    g["Projected Month"] = g["Orders"] + g["Avg / Working Day"] * rem_work
    g["Projected vs Target"] = g["Projected Month"] - g["Target"]
    g["Needed / Remaining Day"] = np.where(rem_work > 0, g["Remaining"] / rem_work.replace(0, np.nan), np.nan)
    g["Status"] = np.select([g["Orders"] >= g["Target"], g["Pace %"] >= 100, g["Pace %"] >= 85],
                            ["✔ Reached", "✔ On pace", "⚠ Slightly behind"], "✖ Behind")
    return g


def _row(key, label, x):
    behind = x["Status"].str.startswith(("⚠", "✖"))
    short = (x["Target"] - x["Projected Month"]).clip(lower=0)
    short[x["Orders"] >= x["Target"]] = 0
    return {key: label, "Couriers": len(x), "Reached": int((x["Status"] == "✔ Reached").sum()), "On Pace": int((x["Status"] == "✔ On pace").sum()),
            "Behind": int(behind.sum()), "Behind %": behind.mean() * 100 if len(x) else np.nan,
            "Needed / Day": x["Needed / Day"].mean(), "Avg Orders / Working Day": x["Orders"].sum() / x["Working"].sum() if x["Working"].sum() else np.nan,
            "Projected Orders Short": int(short.sum())}


def render():
    f = ui.filters()
    R = I.RULES
    months = list(pd.period_range(f["dmin"], f["dmax"], freq="M")[::-1])
    st.markdown(f'<div class="topbar"><div class="t1">{f["platform"].upper()}  ·  MONTHLY ORDERS PACE</div>'
                f'<div class="t2">{f["city"]}  ·  daily pace needed = monthly orders ÷ {int(R["min_days_month"])} working days</div></div>', unsafe_allow_html=True)
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
    st.caption(f"Data until {last:%d %b} · {left} days left · target per courier: " + " · ".join(f"{c} {v} ({v / max(1, R['min_days_month']):.1f}/day)" for c, v in tg.items()))

    n = len(g)
    reached = int((g["Status"] == "✔ Reached").sum())
    onp = int((g["Status"] == "✔ On pace").sum())
    beh = g["Status"].str.startswith(("⚠", "✖"))
    short = (g["Target"] - g["Projected Month"]).clip(lower=0)
    short[g["Orders"] >= g["Target"]] = 0
    will_miss = int((short > 0).sum())
    ui.section("Headline")
    k = st.columns(6)
    ui.card(k[0], "Couriers evaluated", f"{n:,}", "worked at least 1 day")
    ui.card(k[1], "Reached the target", f"{reached:,}", f"{reached / n:.0%}", "good" if reached else "neutral")
    ui.card(k[2], "On pace", f"{onp:,}", f"{onp / n:.0%}", "good" if onp else "neutral")
    ui.card(k[3], "Behind pace", f"{int(beh.sum()):,}", f"{beh.mean():.0%}", I.grade(beh.mean() * 100, 0, 20, False), "Target 0")
    ui.card(k[4], "Projected to miss the target", f"{will_miss:,}", "at their current pace", I.grade(will_miss, 0, 0, False))
    ui.card(k[5], "Projected orders short", f"{int(short.sum()):,}", "total across couriers")

    ui.section("Pace bands", "courier's average per working day ÷ daily pace needed")
    rows = []
    for lab, lo, hi in BANDS:
        x = g[(g["Pace %"] >= lo) & (g["Pace %"] < hi)]
        rows.append({"Band": lab, "Couriers": len(x), "% of Couriers": len(x) / n * 100, "Reached Target": int((x["Orders"] >= x["Target"]).sum()),
                     "Avg Pace %": x["Pace %"].mean() if len(x) else np.nan, "Orders Short (projected)": int(short[x.index].sum())})
    bt = pd.DataFrame(rows)
    ui.table(bt, f"pace_bands_{base}", "pc_bands", export=False, height=38 + 35 * 6, rules={"Avg Pace %": (100, 85, True)})

    if g["City"].nunique() > 1:
        ui.section("By city")
        ct = pd.DataFrame([_row("City", "ALL CITIES", g)] + [_row("City", c, x) for c, x in g.groupby("City")])
        ui.table(ct, f"pace_cities_{base}", "pc_city", first_row=True, export=False, height=38 + 35 * (len(ct) + 1))
    if g["Supervisor"].nunique() > 1:
        ui.section("By supervisor")
        sp = pd.DataFrame([_row("Supervisor", c, x) for c, x in g.groupby("Supervisor")]).sort_values("Behind %", ascending=False)
        ui.table(sp, f"pace_sup_{base}", "pc_sup", export=False, height=min(420, 38 + 35 * (len(sp) + 1)))

    ui.section("Couriers, worst pace first")
    only = st.checkbox("Only couriers behind pace", value=True, key="pc_only")
    t = g.sort_values("Pace %") if not only else g[beh].sort_values("Pace %")
    t = t.rename(columns={"Working": "Working Days"})[["Courier ID", "Name", "City", "Supervisor", "Status", "Orders", "Target", "Remaining", "Working Days",
                                                     "Avg / Working Day", "Needed / Day", "Pace %", "Expected So Far", "Orders vs Expected",
                                                     "Projected Month", "Projected vs Target", "Needed / Remaining Day"]]
    if t.empty:
        st.success("Every courier is on pace.")
    else:
        ui.table(ui.search(t, "pc_q"), f"pace_couriers_{base}", "pc_t", height=560)
