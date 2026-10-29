import pandas as pd
import streamlit as st
from core import ui, insights as I

ORDER = {"✖": 0, "⚠": 1, "✔": 2}


def render():
    f = ui.filters()
    R = I.RULES
    months = list(pd.period_range(f["dmin"], f["dmax"], freq="M")[::-1])
    st.markdown(f'<div class="topbar"><div class="t1">{f["platform"].upper()}  ·  MONTHLY RULES</div>'
                f'<div class="t2">{f["city"]}  ·  mandatory days {R["mand_required"]} of {R["mand_total"]}  ·  {R["min_days_month"]} working days in the month</div></div>',
                unsafe_allow_html=True)
    mo = st.selectbox("Month", months, format_func=lambda p: p.strftime("%B %Y"), key="mo_pick")
    m1, m2 = mo.start_time.date(), mo.end_time.date()
    d = ui.couriers(f["platform"], f["cities"], m1, m2, f["sup"], f["ctype"], f["veh"])
    if d.empty:
        st.info("No courier data in this month.")
        return
    last = d["date"].max()
    left = max(0, (pd.Timestamp(m2) - last).days)
    mand = I.mandatory_between(m1, m2)
    passed = [x for x in mand if x <= last]
    st.caption(f"Data until {last:%d %b}  ·  {left} days left in the month  ·  mandatory days: " +
               (", ".join(x.strftime("%d %b") for x in mand) if mand else "none defined yet (add them in Rules)"))

    d = d.assign(worked=d["valid_hrs"] > 0, is_mand=d["date"].isin(mand))
    base = d.groupby("courier_id").agg(Name=("name", "last"), City=("city", "last"), Supervisor=("supervisor", "last"),
                                       Days_Worked=("worked", "sum"), Sched=("shifts_scheduled", "sum"))
    base = base[(base["Days_Worked"] > 0) | (base["Sched"] > 0)].drop(columns="Sched")
    mw = d[d["is_mand"] & d["worked"]].groupby("courier_id")["date"].nunique()
    base["Mandatory Worked"] = base.index.map(mw).fillna(0).astype(int)
    base["Mandatory Days"] = len(mand)
    base["Missed Mandatory"] = len(passed) - base["Mandatory Worked"]
    allowed = max(0, R["mand_total"] - R["mand_required"])

    def mrule(r):
        if not mand:
            return "–"
        if r["Missed Mandatory"] > allowed:
            return "✖ Failed"
        if r["Missed Mandatory"] == allowed and len(mand) > len(passed):
            return "⚠ At risk"
        return "✔ OK"

    def drule(r):
        w, req = r["Days_Worked"], R["min_days_month"]
        if w >= req:
            return "✔ Achieved"
        if left == 0 or w + left < req:
            return f"✖ Failed ({w}/{req})"
        return f"⚠ Needs {req - w} in {left} days"
    base["Mandatory Rule"] = base.apply(mrule, axis=1)
    base["Month Rule"] = base.apply(drule, axis=1)
    pc = I.month_orders(d, last, left, keep_all=True).set_index("Courier ID")
    for col, dflt in [("Orders", 0), ("Target", None), ("Avg / Working Day", None), ("Needed / Day", None), ("Orders Rule", "–"), ("Pace", "–")]:
        base[col] = pc[col].reindex(base.index)
        if dflt is not None:
            base[col] = base[col].fillna(dflt)
    base["Orders"] = base["Orders"].astype(int)
    base["Target"] = base["Target"].fillna(base["City"].map(I.month_target)).astype(int)
    base["Overall"] = base.apply(lambda r: "✖ FAILED" if "✖" in r["Mandatory Rule"] + r["Month Rule"] + r["Orders Rule"] else
                                 ("⚠ At risk" if "⚠" in r["Mandatory Rule"] + r["Month Rule"] + r["Orders Rule"] else "✔ OK"), axis=1)
    t = base.reset_index().rename(columns={"courier_id": "Courier ID", "Days_Worked": "Days Worked"})
    t["_o"] = t["Overall"].str[0].map(ORDER)
    t = t.sort_values(["_o", "Days Worked"]).drop(columns="_o")
    t = t[["Courier ID", "Name", "City", "Supervisor", "Overall", "Days Worked", "Month Rule", "Orders", "Target", "Orders Rule", "Avg / Working Day",
           "Needed / Day", "Pace", "Mandatory Days", "Mandatory Worked", "Missed Mandatory", "Mandatory Rule"]]

    n = len(t)
    ok_m = (~t["Mandatory Rule"].str.startswith("✖")).mean() * 100
    ok_d = (~t["Month Rule"].str.startswith("✖")).mean() * 100
    ui.section("Totals")
    c = st.columns(5)
    ui.card(c[0], "Couriers evaluated", f"{n:,}")
    ui.card(c[1], f"Met {R['min_days_month']} days (or can still)", f"{ok_d:.0f}%", "", I.grade(ok_d, 100, 90, True))
    ui.card(c[2], "Mandatory rule OK", f"{ok_m:.0f}%" if mand else "–", "", I.grade(ok_m, 100, 90, True) if mand else "neutral")
    behind = int(t["Pace"].str.startswith("✖ Behind").sum())
    ui.card(c[4], "Behind monthly pace", f"{behind:,}", "", I.grade(behind, 0, 0, False), "Target 0")
    ui.card(c[3], "FAILED overall", f"{int(t['Overall'].str.startswith('✖').sum()):,}", "", I.grade(int(t["Overall"].str.startswith("✖").sum()), 0, 0, False), "Target 0")

    if t["City"].nunique() > 1:
        ui.section("By city")
        g = t.groupby("City").agg(Couriers=("Courier ID", "count"),
                                  Failed_Month=("Month Rule", lambda x: int(x.str.startswith("✖").sum())),
                                  Failed_Mandatory=("Mandatory Rule", lambda x: int(x.str.startswith("✖").sum())),
                                  Failed_Orders=("Orders Rule", lambda x: int(x.str.startswith("✖").sum())),
                                  Behind_Pace=("Pace", lambda x: int(x.str.startswith("✖ Behind").sum())),
                                  FAILED=("Overall", lambda x: int(x.str.startswith("✖").sum()))).reset_index()
        g["FAILED %"] = g["FAILED"] / g["Couriers"] * 100
        ui.table(g.rename(columns={"Failed_Month": "Failed Month Rule", "Failed_Mandatory": "Failed Mandatory Rule", "Failed_Orders": "Failed Orders Rule", "Behind_Pace": "Behind Pace"}), "monthly_by_city", "mo_city",
                 export=False, rules={"FAILED": (0, 0, False), "FAILED %": (0, 10, False), "Failed Month Rule": (0, 0, False), "Failed Mandatory Rule": (0, 0, False), "Failed Orders Rule": (0, 0, False), "Behind Pace": (0, 0, False)})

    ui.section("Per courier")
    only = st.checkbox("Only couriers who failed or are at risk", key="mo_only")
    if only:
        t = t[~t["Overall"].str.startswith("✔")]
    ui.table(ui.search(t, "mo_q"), f"monthly_rules_{mo}", "mo_t", height=560, text_cols=["Overall", "Month Rule", "Mandatory Rule", "Orders Rule", "Pace"])
