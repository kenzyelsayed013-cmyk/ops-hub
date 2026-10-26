"""كل الحسابات هنا: مشتقات، تجميع الشركة (بأوزان صح)، ملخص المناديب، الشيفتات، الإلغاء."""
import numpy as np
import pandas as pd
from .config import SLOT_COLS

# اسم العرض لكل عمود
LABELS = {
    "assigned": "Assigned", "accepted": "Accepted", "arrivals": "Restaurant Arrivals", "picked": "Picked",
    "delivered": "Delivered", "large_orders": "Large Orders", "rejected": "Rejected",
    "rejected_courier": "Rejected (Courier)", "rejected_auto": "Rejected (Auto)",
    "di_cancels": "Delivery-Issue Cancels (est.)", "cancel_rate_di": "Cancel Rate (Delivery Issues)",
    "completion_rate": "Completion Rate", "large_cancel_rate": "Large Cancel Rate",
    "registered": "Registered Couriers", "online": "Online Couriers", "couriers_accepted": "Couriers (Accepted)",
    "couriers_delivered": "Couriers (Delivered)", "couriers_delivered_prop": "Couriers Delivered Prop",
    "courier_eff": "Courier Efficiency", "hourly_eff": "Hourly Efficiency", "avg_online_hrs": "Avg Online Hrs",
    "large_ontime_rate": "Large On-time", "ontime_rate": "On-time Rate", "avg_delivery_min": "Avg Delivery (min)",
    "acceptance_5min": "Acceptance (5min)", "over55_prop": "Over 55min Prop",
    "merchant_arrival_min": "Merchant Arrival (min)", "meal_wait_min": "Meal Waiting (min)",
    "meal_delivery_min": "Meal Delivery (min)", "overdue": "Overdue", "severe_overdue": "Severely Overdue",
}

SUM_COLS = ["assigned", "accepted", "arrivals", "picked", "delivered", "large_orders", "rejected",
            "rejected_courier", "rejected_auto", "overdue", "severe_overdue"]
CNT_COLS = ["registered", "online", "couriers_accepted", "couriers_delivered"]   # جمع بين الأنواع، متوسط بين الأيام
# عمود نسبة -> العمود اللي بيتوزن بيه (نفس منطق شيت Keeta الأصلي)
WEIGHT = {"cancel_rate_di": "assigned", "completion_rate": "assigned", "acceptance_5min": "assigned",
          "large_cancel_rate": "large_orders", "large_ontime_rate": "large_orders",
          "ontime_rate": "delivered", "avg_delivery_min": "delivered", "over55_prop": "delivered",
          "merchant_arrival_min": "delivered", "meal_wait_min": "delivered", "meal_delivery_min": "delivered",
          "courier_eff": "online", "hourly_eff": "online", "avg_online_hrs": "online"}


def _wavg(g, col, w):
    x = pd.to_numeric(g[col], errors="coerce")
    ww = pd.to_numeric(g[w], errors="coerce").fillna(0)
    m = x.notna() & (ww > 0)
    return float((x[m] * ww[m]).sum() / ww[m].sum()) if m.any() else np.nan


# ---------------------------------------------------------------- company
def company_by_day(df, group=("date",)):
    """يجمّع صفوف الشركة (كل نوع مندوب صف) على اليوم. group ممكن تضيف courier_type."""
    group = list(group)
    rows = []
    for key, g in df.groupby(group):
        r = dict(zip(group, key if isinstance(key, tuple) else (key,)))
        for c in SUM_COLS + CNT_COLS:
            r[c] = g[c].sum()
        for c, w in WEIGHT.items():
            r[c] = _wavg(g, c, w)
        rows.append(r)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["di_cancels"] = (out["cancel_rate_di"].fillna(0) * out["assigned"]).round()
    out["couriers_delivered_prop"] = np.where(out["registered"] > 0, out["couriers_delivered"] / out["registered"], np.nan)
    return out.sort_values(group).reset_index(drop=True)


def company_total(daily):
    """إجمالي المدى كله من جدول الأيام."""
    if daily.empty:
        return {}
    t = {c: daily[c].sum() for c in SUM_COLS}
    for c in CNT_COLS:
        t[c] = daily[c].mean()           # متوسط يومي
    for c, w in WEIGHT.items():
        t[c] = _wavg(daily, c, w) if c not in ("courier_eff", "hourly_eff", "avg_online_hrs") else \
            _wavg(daily, c, "online")
    t["di_cancels"] = daily["di_cancels"].sum()
    t["days"] = daily["date"].nunique()
    return t


# ---------------------------------------------------------------- couriers
def prep_couriers(df):
    d = df.copy()
    d["name"] = (d["first_name"].fillna("") + " " + d["last_name"].fillna("")).str.strip()
    d["valid_hrs"] = d["valid_online_sec"] / 3600
    d["app_hrs"] = d["app_online_sec"] / 3600
    d["peak_hrs"] = d["peak_online_sec"] / 3600
    d["di_cancels"] = (d["cancel_rate_di"].fillna(0) * d["accepted"]).round(2)
    d["w_ontime"] = d["ontime_rate"] * d["delivered"]
    d["w_avgdel"] = d["avg_delivery_min"] * d["delivered"]
    d["active"] = d["delivered"] > 0
    d["completed_all"] = (d["shifts_scheduled"] > 0) & (d["shifts_qualified"] == d["shifts_scheduled"])
    return d


def courier_labels(d):
    """اسم أحدث لكل Courier ID: 'ID — Name'"""
    last = d.sort_values("date").drop_duplicates("courier_id", keep="last")
    return {r.courier_id: f"{r.name} — {r.courier_id}" for r in last.itertuples()}


def courier_summary(d):
    if d.empty:
        return pd.DataFrame()
    g = d.groupby("courier_id")
    out = g.agg(Name=("name", "last"), Supervisor=("supervisor", "last"), Type=("courier_type", "last"),
                Days_Listed=("date", "nunique"), Active_Days=("active", "sum"),
                Delivered=("delivered", "sum"), Accepted=("accepted", "sum"), Rejected=("rejected", "sum"),
                Large_Orders=("large_orders", "sum"), Valid_Hrs=("valid_hrs", "sum"), App_Hrs=("app_hrs", "sum"),
                Overdue=("overdue", "sum"), Severe_Overdue=("severe_overdue", "sum"),
                w_ontime=("w_ontime", "sum"), w_avgdel=("w_avgdel", "sum"),
                First_Active=("date", lambda s: s[d.loc[s.index, "active"]].min()),
                Last_Active=("date", lambda s: s[d.loc[s.index, "active"]].max()),
                Sched=("shifts_scheduled", "sum"), Qual=("shifts_qualified", "sum"))
    out["Orders_per_Active_Day"] = np.where(out["Active_Days"] > 0, out["Delivered"] / out["Active_Days"], np.nan)
    out["Hrs_per_Active_Day"] = np.where(out["Active_Days"] > 0, out["Valid_Hrs"] / out["Active_Days"], np.nan)
    out["Orders_per_Valid_Hr"] = np.where(out["Valid_Hrs"] > 0, out["Delivered"] / out["Valid_Hrs"], np.nan)
    out["On_time_%"] = np.where(out["Delivered"] > 0, out["w_ontime"] / out["Delivered"] * 100, np.nan)
    out["Avg_Delivery_min"] = np.where(out["Delivered"] > 0, out["w_avgdel"] / out["Delivered"], np.nan)
    out["Shifts_Qualified_%"] = np.where(out["Sched"] > 0, out["Qual"] / out["Sched"] * 100, np.nan)
    out = out.drop(columns=["w_ontime", "w_avgdel"]).rename(columns={"Sched": "Shifts_Scheduled", "Qual": "Shifts_Qualified"})
    for c in ("First_Active", "Last_Active"):
        out[c] = pd.to_datetime(out[c]).dt.date
    return out.reset_index().rename(columns={"courier_id": "Courier ID"}).sort_values("Delivered", ascending=False)


def courier_daily_curve(d):
    """صف لكل (مندوب، يوم) بالأرقام اللي بتتعرض في الكيرف."""
    cols = ["date", "courier_id", "name", "delivered", "accepted", "rejected", "rejected_courier", "rejected_auto",
            "di_cancels", "large_orders", "valid_hrs", "app_hrs", "peak_hrs", "ontime_rate", "avg_delivery_min",
            "overdue", "shifts_scheduled", "shifts_qualified"]
    return d[cols].sort_values(["courier_id", "date"])


# ---------------------------------------------------------------- shifts
def shift_day_stats(d):
    s = d[d["shifts_scheduled"] > 0]
    if s.empty:
        return pd.DataFrame()
    g = s.groupby("date")
    out = g.agg(Couriers_Scheduled=("courier_id", "nunique"), Completed_All=("completed_all", "sum"),
                Sched_Shifts=("shifts_scheduled", "sum"), Qualified_Shifts=("shifts_qualified", "sum")).reset_index()
    out["Completed_All_%"] = out["Completed_All"] / out["Couriers_Scheduled"] * 100
    out["Qualified_Shifts_%"] = out["Qualified_Shifts"] / out["Sched_Shifts"] * 100
    return out


def shift_courier_stats(d):
    s = d[d["shifts_scheduled"] > 0]
    if s.empty:
        return pd.DataFrame()
    g = s.groupby("courier_id")
    out = g.agg(Name=("name", "last"), Supervisor=("supervisor", "last"), Days_Scheduled=("date", "nunique"),
                Days_Completed_All=("completed_all", "sum"), Shifts_Scheduled=("shifts_scheduled", "sum"),
                Shifts_Qualified=("shifts_qualified", "sum")).reset_index()
    out["Days_Not_Completed"] = out["Days_Scheduled"] - out["Days_Completed_All"]
    out["Completed_All_%"] = out["Days_Completed_All"] / out["Days_Scheduled"] * 100
    out["Shifts_Qualified_%"] = out["Shifts_Qualified"] / out["Shifts_Scheduled"] * 100
    return out.rename(columns={"courier_id": "Courier ID"}).sort_values("Completed_All_%")


def shift_symbols(d):
    """Detail table: ✅ qualified · ❌ unqualified · · not scheduled"""
    from .config import SLOTS
    sym = {"qualified": "✅", "unqualified": "❌", "off": "·"}
    out = d[["date", "courier_id", "name", "valid_hrs", "shifts_scheduled", "shifts_qualified"] + SLOT_COLS].copy()
    for c in SLOT_COLS:
        out[c] = out[c].map(sym).fillna("·")
    return out.rename(columns=dict(zip(SLOT_COLS, SLOTS)))
