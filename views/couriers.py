import numpy as np
import pandas as pd
import streamlit as st
from core import ui, metrics as M

RANK_COLS = {"Courier ID": "Courier ID", "Name": "Name", "Type": "Type", "Delivered": "Delivered",
             "Active_Days": "Active Days", "Orders_per_Active_Day": "Orders / Day", "Valid_Hrs": "Valid Online Hrs",
             "Orders_per_Valid_Hr": "Orders / Valid Hr", "On_time_%": "On-time %", "Avg_Delivery_min": "Avg Delivery (min)"}


def _rank(df, name, key, cols=None):
    cols = cols or RANK_COLS
    t = df[list(cols)].rename(columns=cols).reset_index(drop=True)
    t.insert(0, "#", range(1, len(t) + 1))
    ui.table(t, name, key)


def _group(d, col):
    rows = []
    for g, x in d.groupby(col):
        dl = x["delivered"].sum()
        act = x[x["delivered"] > 0]
        rows.append({"Group": g, "Couriers Listed": x["courier_id"].nunique(), "Active Couriers": act["courier_id"].nunique(),
                     "Delivered": dl, "Orders / Active Courier-Day": dl / len(act) if len(act) else np.nan,
                     "Valid Online Hrs": x["valid_hrs"].sum(),
                     "Orders / Valid Hr": dl / x["valid_hrs"].sum() if x["valid_hrs"].sum() else np.nan,
                     "On-time %": x["w_ontime"].sum() / dl * 100 if dl else np.nan,
                     "Avg Delivery (min)": x["w_avgdel"].sum() / dl if dl else np.nan,
                     "Overdue": x["overdue"].sum(), "Rejected": x["rejected"].sum()})
    return pd.DataFrame(rows)


def render():
    f = ui.filters()
    d = ui.get_couriers()
    ui.topbar(f"{f['platform'].upper()}  ·  COURIERS PERFORMANCE", f, days=(f["d2"] - f["d1"]).days + 1)
    if d.empty:
        st.info("No courier data for this period / filters. Upload the couriers file from the Upload page.")
        return
    base = f"{f['platform']}_{f['city']}"
    s = M.courier_summary(d)
    listed = len(s)
    active = int((s["Delivered"] > 0).sum())
    dl = s["Delivered"].sum()
    hrs = s["Valid_Hrs"].sum()
    ontime = (d["w_ontime"].sum() / dl) if dl else np.nan
    avgdel = (d["w_avgdel"].sum() / dl) if dl else np.nan
    act_days = (d["delivered"] > 0).sum()

    ui.section("COURIER KPIs", "from the couriers file · respects the filters")
    r1 = st.columns(6)
    for c, (lab, v, fm) in zip(r1, [("Couriers Listed in Period", listed, "{:,.0f}"), ("Active Couriers (≥1 delivery)", active, "{:,.0f}"),
                                    ("Listed but Zero Deliveries", listed - active, "{:,.0f}"),
                                    ("Delivered Orders (couriers file)", dl, "{:,.0f}"),
                                    ("Avg Orders / Active Courier / Day", dl / act_days if act_days else np.nan, "{:.1f}"),
                                    ("Orders / Valid Online Hour", dl / hrs if hrs else np.nan, "{:.2f}")]):
        c.metric(lab, "–" if pd.isna(v) else fm.format(v), border=True)
    r2 = st.columns(6)
    for c, (lab, v, fm) in zip(r2, [("Valid Online Hours", hrs, "{:,.0f}"), ("Rejected Tasks", d["rejected"].sum(), "{:,.0f}"),
                                    ("Overdue Tasks", d["overdue"].sum(), "{:,.0f}"),
                                    ("Severely Overdue Tasks", d["severe_overdue"].sum(), "{:,.0f}"),
                                    ("On-time Rate (weighted)", ontime, "{:.2%}"), ("Avg Delivery Time (min)", avgdel, "{:.1f}")]):
        c.metric(lab, "–" if pd.isna(v) else fm.format(v), border=True)

    delivered_s = s[s["Delivered"] > 0]
    ui.section("TOP 10 COURIERS", "most delivered orders")
    _rank(delivered_s.nlargest(10, "Delivered"), f"top10_{base}", "cr_top")
    ui.section("BOTTOM 10 ACTIVE COURIERS", "fewest delivered orders (≥1 delivery)")
    _rank(delivered_s.nsmallest(10, "Delivered"), f"bottom10_{base}", "cr_bot")

    ui.section("LOWEST ON-TIME RATE", "couriers with at least N delivered")
    n = st.number_input("Minimum delivered (N)", 1, value=30, step=10, key="cr_n")
    low = s[s["Delivered"] >= n].dropna(subset=["On_time_%"]).nsmallest(10, "On_time_%")
    _rank(low, f"lowest_ontime_{base}", "cr_low")

    ui.section("MOST OVERDUE ORDERS", "overdue + severely overdue")
    o = s.assign(Total_Overdue=s["Overdue"] + s["Severe_Overdue"])
    o["Overdue_pct"] = np.where(o["Delivered"] > 0, o["Total_Overdue"] / o["Delivered"] * 100, np.nan)
    o = o[o["Total_Overdue"] > 0].nlargest(10, "Total_Overdue")
    _rank(o, f"most_overdue_{base}", "cr_over",
          {"Courier ID": "Courier ID", "Name": "Name", "Type": "Type", "Delivered": "Delivered", "Overdue": "Overdue",
           "Severe_Overdue": "Severely Overdue", "Total_Overdue": "Total Overdue", "Overdue_pct": "Overdue % of Delivered",
           "On_time_%": "On-time %", "Avg_Delivery_min": "Avg Delivery (min)"})

    ui.section("BY COURIER TYPE")
    ui.table(_group(d, "courier_type").rename(columns={"Group": "Courier Type"}), f"by_type_{base}", "cr_type")
    ui.section("BY SUPERVISOR")
    ui.table(_group(d, "supervisor").rename(columns={"Group": "Supervisor"}), f"by_supervisor_{base}", "cr_sup")

    ui.section("DAILY COURIER ACTIVITY", "latest day first · couriers file")
    rows = []
    for dt, x in d.groupby("date"):
        dd = x["delivered"].sum()
        a = x[x["delivered"] > 0]
        rows.append({"Date": dt.strftime("%Y-%m-%d"), "Day": dt.strftime("%a"), "Couriers Listed": x["courier_id"].nunique(),
                     "Active Couriers": a["courier_id"].nunique(), "On-Shift": int((x["on_shift"] == "Yes").sum()),
                     "Delivered": dd, "Valid Online Hrs": x["valid_hrs"].sum(),
                     "Orders / Valid Hr": dd / x["valid_hrs"].sum() if x["valid_hrs"].sum() else np.nan,
                     "Orders / Active Courier": dd / len(a) if len(a) else np.nan,
                     "On-time %": x["w_ontime"].sum() / dd * 100 if dd else np.nan,
                     "Avg Delivery (min)": x["w_avgdel"].sum() / dd if dd else np.nan,
                     "Overdue + Severe": x["overdue"].sum() + x["severe_overdue"].sum()})
    day = pd.DataFrame(rows).sort_values("Date", ascending=False)
    ui.table(day, f"daily_courier_activity_{base}", "cr_day", height=min(740, 38 + 35 * (len(day) + 1)))

    ui.section("ALL COURIERS", "full list for the selected period")
    only = st.checkbox("Hide couriers with zero deliveries", value=True, key="cr_hide")
    allc = s[s["Delivered"] > 0] if only else s
    ui.table(ui.search(allc, "cr_q"), f"all_couriers_{base}", "cr_all", height=520)
