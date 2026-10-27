import numpy as np
import pandas as pd
import streamlit as st
from core import ui, metrics as M, insights as I

PRETTY = {"Active_Days": "Active Days", "Orders_per_Active_Day": "Orders / Day", "Valid_Hrs": "Valid Online Hrs",
          "Orders_per_Valid_Hr": "Orders / Valid Hr", "On_time_%": "On-time %", "Avg_Delivery_min": "Avg Delivery (min)",
          "Days_Listed": "Days Listed", "Large_Orders": "Large Orders", "App_Hrs": "App Online Hrs",
          "Severe_Overdue": "Severely Overdue", "Shifts_Scheduled": "Shifts Scheduled", "Shifts_Qualified": "Shifts Qualified",
          "Shifts_Qualified_%": "Qualified shifts %", "First_Active": "First Active", "Last_Active": "Last Active"}
RANK_COLS = {"Courier ID": "Courier ID", "Name": "Name", "Type": "Type", "Segment": "Segment", "Delivered": "Delivered",
             "Active_Days": "Active Days", "Orders_per_Active_Day": "Orders / Day", "Valid_Hrs": "Valid Online Hrs",
             "Orders_per_Valid_Hr": "Orders / Valid Hr", "On_time_%": "On-time %", "Avg_Delivery_min": "Avg Delivery (min)"}
SEG_HINT = {"Star": "good", "Solid": "neutral", "Low efficiency": "warn", "Needs coaching": "bad", "Idle (0 deliveries)": "bad"}


def _rank(df, name, key, cols=None):
    cols = cols or RANK_COLS
    t = df[[c for c in cols if c in df.columns]].rename(columns=cols).reset_index(drop=True)
    t.insert(0, "#", range(1, len(t) + 1))
    ui.table(t, name, key)


def _group(d, col):
    rows = []
    for g, x in d.groupby(col):
        dl = x["delivered"].sum()
        act = x[x["delivered"] > 0]
        lst = x["courier_id"].nunique()
        ac = act["courier_id"].nunique()
        rows.append({"Group": g, "Couriers Listed": lst, "Active Couriers": ac, "Active % of Listed": ac / lst * 100 if lst else np.nan,
                     "Delivered": dl, "Orders / Active Courier-Day": dl / len(act) if len(act) else np.nan,
                     "Valid Online Hrs": x["valid_hrs"].sum(),
                     "Orders / Valid Hr": dl / x["valid_hrs"].sum() if x["valid_hrs"].sum() else np.nan,
                     "On-time %": x["w_ontime"].sum() / dl * 100 if dl else np.nan,
                     "Avg Delivery (min)": x["w_avgdel"].sum() / dl if dl else np.nan,
                     "Overdue": x["overdue"].sum(), "Rejected": x["rejected"].sum()})
    return pd.DataFrame(rows)


def _segments(seg):
    tot_d, n = seg["Delivered"].sum(), len(seg)
    rows = []
    for k in I.SEG_ORDER:
        x = seg[seg["Segment"] == k]
        if x.empty:
            continue
        dl = x["Delivered"].sum()
        ot = (x["On_time_%"] * x["Delivered"]).sum() / dl if dl else np.nan
        rows.append({"Segment": k, "Couriers": len(x), "% of Couriers": len(x) / n * 100, "Delivered": dl,
                     "% of Orders": dl / tot_d * 100 if tot_d else np.nan, "On-time %": ot, "Valid Online Hrs": x["Valid_Hrs"].sum(),
                     "What to do": I.SEG_ACTION[k]})
    return pd.DataFrame(rows)


def render():
    f = ui.filters()
    d = ui.get_couriers()
    ui.topbar(f"{f['platform'].upper()}  ·  COURIERS PERFORMANCE", f, days=(f["d2"] - f["d1"]).days + 1)
    if d.empty:
        st.info("No courier data for this period / filters.")
        return
    base = f"{f['platform']}_{f['city']}"
    s = I.segment_couriers(M.courier_summary(d))
    listed, active = len(s), int((s["Delivered"] > 0).sum())
    dl, hrs = s["Delivered"].sum(), s["Valid_Hrs"].sum()
    ontime = d["w_ontime"].sum() / dl if dl else np.nan
    avgdel = d["w_avgdel"].sum() / dl if dl else np.nan
    act_days = (d["delivered"] > 0).sum()
    idle_sh = (listed - active) / listed if listed else np.nan
    ui.legend()

    ui.section("Courier KPIs", "from the couriers file · respects the filters")
    c = st.columns(6)
    ui.card(c[0], "Couriers listed", f"{listed:,}")
    ui.card(c[1], "Active couriers", f"{active:,}", f"{active / listed:.0%} of listed" if listed else "")
    ui.card(c[2], "Listed, zero deliveries", f"{listed - active:,}", f"{idle_sh:.0%} of listed")
    ui.card(c[3], "Delivered orders", f"{dl:,.0f}")
    ui.card(c[4], "Orders / active courier / day", f"{dl / act_days:.1f}" if act_days else "–")
    ui.card(c[5], "Orders / valid online hour", f"{dl / hrs:.2f}" if hrs else "–")
    c = st.columns(6)
    ui.card(c[0], "Valid online hours", f"{hrs:,.0f}")
    ui.card(c[1], "Rejected tasks", f"{d['rejected'].sum():,.0f}")
    ui.card(c[2], "Overdue tasks", f"{d['overdue'].sum():,.0f}")
    ui.card(c[3], "Severely overdue", f"{d['severe_overdue'].sum():,.0f}")
    ui.card(c[4], "On-time rate (weighted)", f"{ontime:.2%}" if pd.notna(ontime) else "–", "", I.status("ontime_rate", ontime),
            I.target_hint("ontime_rate") + "  ·  " + I.gap_txt("ontime_rate", ontime))
    ui.card(c[5], "Avg delivery time (min)", f"{avgdel:.1f}" if pd.notna(avgdel) else "–", "", I.status("avg_delivery_min", avgdel),
            I.target_hint("avg_delivery_min"))

    ui.section("Who to reward, coach, or remove", "every courier falls in exactly one group")
    ui.table(_segments(s), f"segments_{base}", "cr_seg", export=False, height=38 + 35 * 6)
    pass

    ds = s[s["Delivered"] > 0]
    ui.section("Top 10 couriers", "most delivered orders")
    _rank(ds.nlargest(10, "Delivered"), f"top10_{base}", "cr_top")
    ui.section("Bottom 10 active couriers", "fewest delivered orders (at least 1 delivery)")
    _rank(ds.nsmallest(10, "Delivered"), f"bottom10_{base}", "cr_bot")

    ui.section("Lowest on-time rate", "couriers with at least N delivered")
    n = st.number_input("Minimum delivered (N)", 1, value=30, step=10, key="cr_n")
    _rank(s[s["Delivered"] >= n].dropna(subset=["On_time_%"]).nsmallest(10, "On_time_%"), f"lowest_ontime_{base}", "cr_low")

    ui.section("Most overdue orders", "overdue + severely overdue")
    o = s.assign(Total_Overdue=s["Overdue"] + s["Severe_Overdue"])
    o["Overdue_pct"] = np.where(o["Delivered"] > 0, o["Total_Overdue"] / o["Delivered"] * 100, np.nan)
    _rank(o[o["Total_Overdue"] > 0].nlargest(10, "Total_Overdue"), f"most_overdue_{base}", "cr_over",
          {"Courier ID": "Courier ID", "Name": "Name", "Segment": "Segment", "Delivered": "Delivered", "Overdue": "Overdue",
           "Severe_Overdue": "Severely Overdue", "Total_Overdue": "Total Overdue", "Overdue_pct": "Overdue % of Delivered",
           "On_time_%": "On-time %", "Avg_Delivery_min": "Avg Delivery (min)"})

    ui.section("By courier type")
    ui.table(_group(d, "courier_type").rename(columns={"Group": "Courier Type"}), f"by_type_{base}", "cr_type")
    ui.section("By supervisor", "compare teams: the gap between best and worst is the improvement potential")
    ui.table(_group(d, "supervisor").rename(columns={"Group": "Supervisor"}), f"by_supervisor_{base}", "cr_sup")

    ui.section("Daily courier activity", "newest day first")
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

    ui.section("All couriers", "full list for the selected period")
    only = st.checkbox("Hide couriers with zero deliveries", value=True, key="cr_hide")
    allc = (s[s["Delivered"] > 0] if only else s).rename(columns=PRETTY).reset_index(drop=True)
    ui.table(ui.search(allc, "cr_q"), f"all_couriers_{base}", "cr_all", height=520)
