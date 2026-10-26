"""قراءة ملفات المنصات وتحويلها لنفس الشكل الداخلي. لكل منصة parser خاص بيها."""
import re
import numpy as np
import pandas as pd
from .config import SLOTS, SLOT_COLS

# ---------------------------------------------------------------- Keeta column maps
KEETA_COURIER = {
    "Date": "date", "Courier ID": "courier_id", "Courier First Name": "first_name",
    "Courier Last Name": "last_name", "Supervisor": "supervisor", "Vehicle type": "vehicle_type",
    "Courier Type": "courier_type",
    "Shift_Attendance summary based on valid online duration": "shift_summary",
    "Shift_On-Shift?": "on_shift", "Shift_Valid Day?": "valid_day",
    "Shift_Courier App Online Time": "app_online", "Shift_Valid Online Time": "valid_online",
    "Shift_Peak Online Hours": "peak_online",
    "Task Volumes_Accepted Tasks": "accepted",
    "Task Volumes_Tasks with restaurant arrivals": "arrivals",
    "Task Volumes_Delivered Tasks": "delivered",
    "Task Volumes_Large Order Tasks Completed": "large_orders",
    "Task Volumes_Rejected Tasks": "rejected",
    "Task Volumes_Rejected Tasks (Courier)": "rejected_courier",
    "Task Volumes_Rejected Tasks (Auto)": "rejected_auto",
    "Task Volumes_Cancellation Rate from Delivery Issues": "cancel_rate_di",
    "Task Volumes_Order completion rate (non-delivery related)": "completion_rate",
    "Delivery Experience_On-time Rate (D)": "ontime_rate",
    "Delivery Experience_Large order on-time rate": "large_ontime_rate",
    "Delivery Experience_Avg Delivery Time of Delivered Orders": "avg_delivery_min",
    "Delivery Experience_Delivered Orders Prop. (Over 55min)": "over55_prop",
    "Delivery Experience_Overdue Order Tasks": "overdue",
    "Delivery Experience_Severely Overdue Order Tasks": "severe_overdue",
}
KEETA_COMPANY = {
    "Date": "date", "Headquarters": "headquarters", "Courier Type": "courier_type",
    "Task Volumes_Assigned Tasks": "assigned", "Task Volumes_Accepted Tasks": "accepted",
    "Task Volumes_Tasks with restaurant arrivals": "arrivals", "Task Volumes_Picked Tasks": "picked",
    "Task Volumes_Delivered Tasks": "delivered", "Task Volumes_Large Order Tasks Completed": "large_orders",
    "Task Volumes_Rejected Tasks": "rejected", "Task Volumes_Rejected Tasks (Courier)": "rejected_courier",
    "Task Volumes_Rejected Tasks (Auto)": "rejected_auto",
    "Task Volumes_Cancellation Rate from Delivery Issues": "cancel_rate_di",
    "Task Volumes_Order completion rate (non-delivery related)": "completion_rate",
    "Task Volumes_Large Order Cancellation Rate from Delivery Issues": "large_cancel_rate",
    "Courier Capacity_Total Registered Couriers": "registered", "Courier Capacity_Online Couriers": "online",
    "Courier Capacity_Couriers (Accepted Tasks)": "couriers_accepted",
    "Courier Capacity_Couriers (Delivered Tasks)": "couriers_delivered",
    "Courier Capacity_Couriers (Delivered Tasks) Prop": "couriers_delivered_prop",
    "Courier Capacity_Courier Efficiency": "courier_eff",
    "Courier Capacity_Hourly Efficiency (Service)": "hourly_eff",
    "Courier Capacity_Avg Online Time": "avg_online_hrs",
    "Delivery Experience_Large order on-time rate": "large_ontime_rate",
    "Delivery Experience_On-time Rate (D)": "ontime_rate",
    "Delivery Experience_Avg Delivery Time of Delivered Orders": "avg_delivery_min",
    "Delivery Experience_Acceptance Rate (Within 5min)": "acceptance_5min",
    "Delivery Experience_Delivered Orders Prop. (Over 55min)": "over55_prop",
    "Delivery Experience_Avg Time of Merchant-Arrival": "merchant_arrival_min",
    "Delivery Experience_Avg Time of Meal-Waiting": "meal_wait_min",
    "Delivery Experience_Avg Time of Meal-Delivery": "meal_delivery_min",
    "Delivery Experience_Overdue Order Tasks": "overdue",
    "Delivery Experience_Severely Overdue Order Tasks": "severe_overdue",
}

COURIER_INT = ["accepted", "arrivals", "delivered", "large_orders", "rejected",
               "rejected_courier", "rejected_auto", "overdue", "severe_overdue"]
COURIER_RATE = ["cancel_rate_di", "completion_rate", "ontime_rate", "large_ontime_rate",
                "avg_delivery_min", "over55_prop"]
COMPANY_INT = ["assigned", "accepted", "arrivals", "picked", "delivered", "large_orders", "rejected",
               "rejected_courier", "rejected_auto", "registered", "online", "couriers_accepted",
               "couriers_delivered", "overdue", "severe_overdue"]
COMPANY_RATE = ["cancel_rate_di", "completion_rate", "large_cancel_rate", "couriers_delivered_prop",
                "courier_eff", "hourly_eff", "avg_online_hrs", "large_ontime_rate", "ontime_rate",
                "avg_delivery_min", "acceptance_5min", "over55_prop", "merchant_arrival_min",
                "meal_wait_min", "meal_delivery_min"]


# ---------------------------------------------------------------- helpers
def _norm(c):
    return re.sub(r"\s+", " ", str(c)).strip().lower()


def detect_kind(df):
    cols = {_norm(c) for c in df.columns}
    if "courier id" in cols:
        return "courier"
    if "headquarters" in cols:
        return "company"
    return None


def parse_duration(v):
    """'1 hr, 58 min' / '19 min, 33 sec' / '0 sec' -> seconds"""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return 0.0
    t = 0.0
    for num, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(hr|min|sec)", str(v)):
        t += float(num) * {"hr": 3600, "min": 60, "sec": 1}[unit]
    return t


_SEG = re.compile(r"^(\d\d:\d\d-\d\d:\d\d),(On-Shift|Off-Shift),(.*?)(?:,(qualified|unqualified))?$")


def parse_shift(summary):
    """يرجع ({slot_col: 'qualified'|'unqualified'|'off'}, scheduled, qualified)"""
    out = {c: "off" for c in SLOT_COLS}
    if not isinstance(summary, str) or summary.strip() in ("", "-"):
        return out, 0, 0
    sched = qual = 0
    for part in summary.split("|"):
        m = _SEG.match(part.strip())
        if not m:
            continue
        slot, state, _dur, q = m.groups()
        if slot not in SLOTS or state != "On-Shift":
            continue
        out[SLOT_COLS[SLOTS.index(slot)]] = "qualified" if q == "qualified" else "unqualified"
        sched += 1
        qual += q == "qualified"
    return out, sched, qual


def _to_num(s):
    return pd.to_numeric(s.replace("-", np.nan) if s.dtype == object else s, errors="coerce")


def _rename(df, mapping):
    lookup = {_norm(k): v for k, v in mapping.items()}
    ren = {}
    for c in df.columns:
        key = _norm(c)
        if key in lookup and lookup[key] not in ren.values():
            ren[c] = lookup[key]
    return df.rename(columns=ren)[list(ren.values())]


def _clean_date(s):
    n = pd.to_numeric(s, errors="coerce").astype("Int64").astype(str)
    return pd.to_datetime(n, format="%Y%m%d", errors="coerce").dt.date


def _clean_id(s):
    if pd.api.types.is_numeric_dtype(s):
        return s.astype("Int64").astype(str)
    return s.astype(str).str.replace(r"\.0$", "", regex=True).str.strip()


# ---------------------------------------------------------------- Keeta
def parse_keeta_courier(df):
    d = _rename(df, KEETA_COURIER)
    for need in ("date", "courier_id"):
        if need not in d:
            raise ValueError(f"العمود الأساسي ناقص: {need}")
    d["date"] = _clean_date(d["date"])
    d = d.dropna(subset=["date", "courier_id"]).copy()
    d["courier_id"] = _clean_id(d["courier_id"])
    for c in ("first_name", "last_name", "supervisor", "vehicle_type", "courier_type", "on_shift", "valid_day"):
        d[c] = d[c].fillna("-").astype(str).str.strip() if c in d else "-"
    for src, dst in (("app_online", "app_online_sec"), ("valid_online", "valid_online_sec"),
                     ("peak_online", "peak_online_sec")):
        d[dst] = d[src].map(parse_duration) if src in d else 0.0
    d = d.drop(columns=[c for c in ("app_online", "valid_online", "peak_online") if c in d])
    for c in COURIER_INT:
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0).astype(int) if c in d else 0
    for c in COURIER_RATE:
        d[c] = _to_num(d[c]) if c in d else np.nan
    if "shift_summary" in d:
        sh = d["shift_summary"].map(parse_shift)
    else:
        sh = pd.Series([parse_shift(None)] * len(d), index=d.index)
    slots = pd.DataFrame([x[0] for x in sh], index=d.index)
    d = pd.concat([d.drop(columns=["shift_summary"], errors="ignore"), slots], axis=1)
    d["shifts_scheduled"] = [x[1] for x in sh]
    d["shifts_qualified"] = [x[2] for x in sh]
    return d.reset_index(drop=True)


def parse_keeta_company(df):
    d = _rename(df, KEETA_COMPANY)
    if "date" not in d:
        raise ValueError("العمود الأساسي ناقص: Date")
    d["date"] = _clean_date(d["date"])
    d = d.dropna(subset=["date"]).copy()
    for c in ("headquarters", "courier_type"):
        d[c] = d[c].fillna("-").astype(str).str.strip() if c in d else "-"
    for c in COMPANY_INT:
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0).astype(int) if c in d else 0
    for c in COMPANY_RATE:
        d[c] = _to_num(d[c]) if c in d else np.nan
    return d.reset_index(drop=True)


# ---------------------------------------------------------------- registry
PARSERS = {
    "keeta": {"courier": parse_keeta_courier, "company": parse_keeta_company},
    # "hungerstation": {"courier": ..., "company": ...},   <- هنضيفها بعدين بنفس الشكل
}


def read_excel_any(file):
    return pd.read_excel(file, sheet_name=0)


def parse_file(raw, parser_key):
    kind = detect_kind(raw)
    if kind is None:
        raise ValueError("مش عارف نوع الملف: مفيش عمود Courier ID (ملف مناديب) ولا Headquarters (ملف شركة).")
    if parser_key not in PARSERS:
        raise ValueError("المنصة دي لسه معندهاش parser.")
    return kind, PARSERS[parser_key][kind](raw)
