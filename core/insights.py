"""Targets, grading, segments and the action list. EDIT TARGETS here: every colour in the app follows them."""
import json
import numpy as np
from pathlib import Path
import pandas as pd
from . import metrics as M
from .config import SLOT_COLS, SLOTS

# (good, bad, higher_is_better)
TARGETS = {
    "ontime_rate": (0.996, 0.99, True),
    "cancel_rate": (0.0019, 0.005, False),
    "attendance": (1.0, 0.95, True),     # scheduled courier-days where the courier actually worked
    "valid_rate": (1.0, 0.90, True),     # scheduled courier-days where every shift qualified
}
RATE_KEYS = {"ontime_rate", "cancel_rate", "cancel_rate_di", "attendance", "valid_rate", "completion_rate", "large_ontime_rate",
             "large_cancel_rate", "over55_prop", "couriers_delivered_prop", "acceptance_5min"}
COACH_BELOW = 97   # courier on-time % under this (with 30+ deliveries) = needs coaching

RULES_FILE = Path(__file__).resolve().parent.parent / "rules.json"
DEFAULT_RULES = {
    "min_orders_normal": 3, "min_orders_mandatory": 7, "mandatory_weekdays": [], "mandatory_dates": [],
    "mand_required": 6, "mand_total": 7, "min_days_month": 26, "di_total": "average",
    "require_all_shifts": True,
    "targets": {"ontime_rate": [99.6, 99.0], "cancel_rate": [0.19, 0.5], "attendance": [100, 95], "valid_rate": [100, 90]},
}
RULES = json.loads(json.dumps(DEFAULT_RULES))
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _sync():
    for k, (g, b) in RULES["targets"].items():
        TARGETS[k] = (g / 100, b / 100, k != "cancel_rate")
    o, c, a, v = (RULES["targets"][k] for k in ("ontime_rate", "cancel_rate", "attendance", "valid_rate"))
    TABLE_RULES.update({"On-time %": (o[0], o[1], True), "Cancel %": (c[0], c[1], False), "Attendance %": (a[0], a[1], True),
                        "Valid %": (v[0], v[1], True), "Completed all %": (v[0], v[1], True), "Qualified shifts %": (v[0], v[1], True)})


def load_rules():
    try:
        saved = json.loads(RULES_FILE.read_text())
        for k, v in saved.items():
            if k == "targets":
                if "cancel_rate_di" in v:
                    v["cancel_rate"] = v.pop("cancel_rate_di")
                RULES["targets"].update(v)
            else:
                RULES[k] = v
    except Exception:
        pass
    _sync()


def save_rules(new):
    RULES.update({k: v for k, v in new.items() if k != "targets"})
    RULES["targets"].update(new.get("targets", {}))
    RULES_FILE.write_text(json.dumps(RULES, indent=2))
    _sync()


def rule_sentence():
    R = RULES
    days = ", ".join(WEEKDAYS[i] for i in R["mandatory_weekdays"]) or "none"
    extra = f" + {len(R['mandatory_dates'])} extra date(s)" if R["mandatory_dates"] else ""
    return (f"A courier is VALID on a scheduled day if he " + ("completes all his shifts and " if R["require_all_shifts"] else "")
            + f"delivers at least {R['min_orders_normal']} orders on a normal day or {R['min_orders_mandatory']} on a mandatory day "
            f"(mandatory: {days}{extra}). The order minimum applies only to couriers who deliver at all in the period. "
            f"Monthly: attend {R['mand_required']} of {R['mand_total']} mandatory days and at least {R['min_days_month']} days in the month.")

TABLE_RULES = {
    "On-time %": (99.6, 99, True), "Cancel %": (0.19, 0.5, False),
    "Rejected (Courier)": (0, 0, False), "Courier Rejects": (0, 0, False),
    "Attendance %": (100, 95, True), "Valid %": (100, 90, True),
    "Completed all %": (100, 90, True), "Qualified shifts %": (100, 90, True),
    "Days Not Completed": (0, 2, False), "INVALID": (0, 0, False), "INVALID Days": (0, 0, False), "Missed Mandatory": (0, 1, False), "Absent": (0, 0, False),
    "Delivered vs prev day %": (0, -10, True),
}
TAGS = {"good": "ON TARGET", "warn": "WATCH", "bad": "ACT NOW"}
SEG_ORDER = ["Star", "Solid", "Low efficiency", "Needs coaching", "Idle (0 deliveries)"]
SEG_ACTION = {
    "Star": "Keep and reward.", "Solid": "No action.",
    "Low efficiency": "Online but far below median pace. Check or move.",
    "Needs coaching": f"On-time under {COACH_BELOW}%. Coach or review.",
    "Idle (0 deliveries)": "Listed, zero deliveries. Activate or remove.",
}


def is_num(v):
    return isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool) and not pd.isna(v)


def grade(v, good, bad, hb=True, zero_neutral=False):
    if not is_num(v) or (zero_neutral and v == 0):
        return "neutral"
    if hb:
        return "good" if v >= good else ("bad" if v < bad else "warn")
    return "good" if v <= good else ("bad" if v > bad else "warn")


def status(key, v):
    t = TARGETS.get(key)
    return grade(v, *t) if t else "neutral"


def target_hint(key):
    t = TARGETS.get(key)
    return f"Target {'≥' if t[2] else '≤'} {t[0] * 100:g}%" if t else ""


def gap_txt(key, v):
    t = TARGETS.get(key)
    if not t or not is_num(v):
        return ""
    d = (v - t[0]) * 100
    return "On target" if abs(d) < 0.005 else f"{d:+.2f} pp vs target"


def fmtv(k, v):
    if v is None or pd.isna(v):
        return "–"
    return f"{v * 100:.2f}%" if k in RATE_KEYS else f"{v:,.0f}"


def tone_of_text(v):
    s = str(v)
    if s.startswith("INVALID"):
        return "bad"
    if s.startswith(("✔", "✅", "Star", "VALID")):
        return "good"
    if s.startswith(("⚠", "Low eff")):
        return "warn"
    if s.startswith(("✖", "❌", "Idle", "Needs")):
        return "bad"
    return "neutral"


def enrich(t):
    if not t:
        return {}
    t = dict(t)
    t["couriers_delivered_prop"] = t["couriers_delivered"] / t["registered"] if t.get("registered") else np.nan
    return t


# ---------------------------------------------------------------- shifts / attendance
def sched_days(cd):
    """Scheduled courier-days with the validity rule applied (columns: valid, reason, mandatory, shifts_ok, orders_ok)."""
    if cd is None or cd.empty:
        return pd.DataFrame()
    R = RULES
    s = cd[cd["shifts_scheduled"] > 0].copy()
    s["attended"] = s["valid_hrs"] > 0
    regular = cd.groupby("courier_id")["delivered"].sum() > 0
    s["regular"] = s["courier_id"].map(regular).fillna(False).astype(bool)
    s["mandatory"] = s["date"].dt.dayofweek.isin(R["mandatory_weekdays"]) | s["date"].dt.strftime("%Y-%m-%d").isin(R["mandatory_dates"])
    s["min_orders"] = np.where(s["mandatory"], R["min_orders_mandatory"], R["min_orders_normal"])
    s["shifts_ok"] = s["completed_all"] if R["require_all_shifts"] else True
    s["orders_ok"] = ~s["regular"] | (s["delivered"] >= s["min_orders"])
    s["valid"] = s["shifts_ok"] & s["orders_ok"]
    sh = "Missed shifts (" + s["shifts_qualified"].astype(int).astype(str) + "/" + s["shifts_scheduled"].astype(int).astype(str) + ")"
    od = "Low orders (" + s["delivered"].astype(int).astype(str) + " < " + s["min_orders"].astype(int).astype(str) + (
        np.where(s["mandatory"], ", mandatory day)", ")"))
    s["reason"] = np.select([~s["shifts_ok"] & ~s["orders_ok"], ~s["shifts_ok"], ~s["orders_ok"]], [sh + " + " + od, sh, od], "OK")
    return s


def attendance_stats(cd):
    s = sched_days(cd)
    if s.empty:
        return dict(n=0, att=np.nan, valid=np.nan, qual=np.nan)
    return dict(n=len(s), att=s["attended"].mean(), valid=s["valid"].mean(),
                qual=s["shifts_qualified"].sum() / s["shifts_scheduled"].sum())


def valid_by_day(cd):
    s = sched_days(cd)
    if s.empty:
        return pd.DataFrame()
    g = s.groupby("date").agg(Scheduled=("courier_id", "count"), Attended=("attended", "sum"), Valid=("valid", "sum"),
                              ShiftFail=("shifts_ok", lambda x: int((~x).sum())), OrderFail=("orders_ok", lambda x: int((~x).sum())),
                              SS=("shifts_scheduled", "sum"), SQ=("shifts_qualified", "sum"), Mand=("mandatory", "max")).reset_index()
    g["Absent"] = g["Scheduled"] - g["Attended"]
    g["Dropped"] = g["Scheduled"] - g["Valid"]
    g["Attendance %"] = g["Attended"] / g["Scheduled"] * 100
    g["Valid %"] = g["Valid"] / g["Scheduled"] * 100
    g["Qualified shifts %"] = g["SQ"] / g["SS"] * 100
    return g.sort_values("date", ascending=False)


def day_lists(cd, day):
    """(valid_df, dropped_df) for one date, display-ready."""
    s = sched_days(cd)
    s = s[s["date"] == pd.Timestamp(day)]
    sym = {"qualified": "✅", "unqualified": "❌", "off": "·"}

    def fmt(x, reason, status):
        cols = ["courier_id", "name", "city", "supervisor", "delivered", "min_orders", "shifts_scheduled", "shifts_qualified", "valid_hrs"]
        o = x[cols + (["reason"] if reason else []) + SLOT_COLS].copy()
        for c in SLOT_COLS:
            o[c] = o[c].map(sym).fillna("·")
        o.insert(2, "Status", status)
        return o.rename(columns={"courier_id": "Courier ID", "name": "Name", "city": "City", "supervisor": "Supervisor",
                                 "delivered": "Orders", "min_orders": "Min Orders", "shifts_scheduled": "Shifts", "shifts_qualified": "Qualified",
                                 "valid_hrs": "Valid Hrs", "reason": "Why INVALID", **dict(zip(SLOT_COLS, SLOTS))}).reset_index(drop=True)
    return fmt(s[s["valid"]], False, "VALID"), fmt(s[~s["valid"]].sort_values("delivered"), True, "INVALID")


def mandatory_between(d1, d2):
    R = RULES
    return [d for d in pd.date_range(d1, d2) if d.dayofweek in R["mandatory_weekdays"] or d.strftime("%Y-%m-%d") in R["mandatory_dates"]]


def di_avg(df, rate_col="cancel_rate_di", w_col="accepted"):
    """Delivery Issue rate for a group of rows. Each row's rate is Keeta's own rate, untouched.
    Period figure = plain average of those rates (default), or weighted by volume if RULES['di_total'] == 'weighted'."""
    if df is None or len(df) == 0:
        return np.nan
    x = pd.to_numeric(df[rate_col], errors="coerce")
    if RULES.get("di_total", "average") == "weighted":
        w = pd.to_numeric(df[w_col], errors="coerce").fillna(0)
        m = x.notna() & (w > 0)
        return float((x[m] * w[m]).sum() / w[m].sum()) if m.any() else np.nan
    return float(x.mean()) if x.notna().any() else np.nan


# ---------------------------------------------------------------- cancel = accepted - delivered
def fix_daily(daily):
    """Cancelled = accepted - delivered (never below 0 per day). cancel_rate_di is overwritten with this definition."""
    if daily is None or daily.empty:
        return daily
    d = daily.copy()
    d["cancelled"] = (d["accepted"] - d["delivered"]).clip(lower=0)
    d["cancel_rate"] = np.where(d["accepted"] > 0, d["cancelled"] / d["accepted"], np.nan)
    return d


def company_stats(co):
    """(daily, totals) from a company-file frame, using the accepted - delivered cancel definition."""
    if co is None or co.empty:
        return pd.DataFrame(), {}
    daily = fix_daily(M.company_by_day(co))
    tot = enrich(M.company_total(daily))
    acc, can = daily["accepted"].sum(), daily["cancelled"].sum()
    tot["cancelled"] = can
    tot["cancel_rate"] = can / acc if acc else np.nan
    tot["cancel_rate_di"] = di_avg(daily, "cancel_rate_di", "assigned")
    return daily, tot


# ---------------------------------------------------------------- cities
def city_table(co, cd, day=None):
    if day is not None:
        co = co[co["date"] == pd.Timestamp(day)] if not co.empty else co
        cd = cd[cd["date"] == pd.Timestamp(day)] if not cd.empty else cd
    names = set()
    for x in (co, cd):
        if x is not None and not x.empty and "city" in x.columns:
            names |= set(x["city"].unique())

    def one(label, a, b):
        r = {"City": label}
        if a is not None and not a.empty:
            _, t = company_stats(a)
            r.update({"Delivered": t["delivered"], "Cancelled": t["cancelled"], "On-time %": t["ontime_rate"] * 100, "Cancel %": t["cancel_rate"] * 100,
                      "Delivery Issue %": t["cancel_rate_di"] * 100,
                      "Online Couriers / day": t["online"]})
        if b is not None and not b.empty:
            st_ = attendance_stats(b)
            s = sched_days(b)
            r.update({"Scheduled Courier-days": st_["n"], "Attendance %": st_["att"] * 100 if st_["n"] else np.nan,
                      "Valid %": st_["valid"] * 100 if st_["n"] else np.nan,
                      "VALID Courier-days": int(s["valid"].sum()) if len(s) else 0, "INVALID Courier-days": int((~s["valid"]).sum()) if len(s) else 0,
                      "Couriers with INVALID day": int(s.loc[~s["valid"], "courier_id"].nunique()) if len(s) else 0,
                      "Courier Rejects": b["rejected_courier"].sum()})
        return r
    rows = [one("ALL CITIES", co, cd)]
    for c in sorted(names):
        rows.append(one(c, co[co["city"] == c] if not co.empty else co, cd[cd["city"] == c] if not cd.empty else cd))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- segments
def segment_couriers(s):
    if s is None or s.empty:
        return s
    s = s.copy()
    med_eff = s.loc[s["Valid_Hrs"] >= 10, "Orders_per_Valid_Hr"].median()
    med_day = s.loc[s["Delivered"] > 0, "Orders_per_Active_Day"].median()

    def seg(r):
        ot = r["On_time_%"]
        if r["Delivered"] == 0:
            return "Idle (0 deliveries)"
        if r["Delivered"] >= 30 and pd.notna(ot) and ot < COACH_BELOW:
            return "Needs coaching"
        if r["Valid_Hrs"] >= 20 and pd.notna(med_eff) and r["Orders_per_Valid_Hr"] < 0.5 * med_eff:
            return "Low efficiency"
        if pd.notna(ot) and ot >= 99.6 and r["Orders_per_Active_Day"] >= (med_day if pd.notna(med_day) else 0):
            return "Star"
        return "Solid"
    s["Segment"] = s.apply(seg, axis=1)
    s.attrs["med_eff"] = med_eff
    return s


# ---------------------------------------------------------------- actions
def _names(df, col, val, n=3):
    return ", ".join(f"{a} ({b:g})" for a, b in df.nlargest(n, val)[[col, val]].itertuples(index=False))


def build_actions(co, daily, tot, ptot, cd, s, n_days):
    A = []
    add = lambda sev, t, e, a: A.append(dict(sev=sev, title=t, evidence=e, action=a))
    tot, ptot = tot or {}, ptot or {}

    for k, lab, act in [("ontime_rate", "On-time rate", "Review worst days and late couriers below."),
                        ("cancel_rate", "Cancelled % (accepted - delivered)", "Find the days and couriers with the most delivery-issue cancels.")]:
        v = tot.get(k)
        st_ = status(k, v)
        if st_ != "neutral":
            add(st_, f"{lab} {fmtv(k, v)}", f"{target_hint(k)}  ·  {gap_txt(k, v)}  ·  previous {fmtv(k, ptot.get(k))}",
                "On target." if st_ == "good" else act)

    if cd is not None and not cd.empty:
        rc = cd.groupby(["courier_id", "name"])["rejected_courier"].sum().reset_index()
        rc = rc[rc["rejected_courier"] > 0]
        tr = cd["rejected_courier"].sum()
        if tr > 0:
            add("bad", f"{tr:,.0f} orders rejected by couriers", f"Target is zero  ·  {len(rc)} couriers  ·  top: {_names(rc, 'name', 'rejected_courier')}",
                "Call every courier on the list below. No rejection is acceptable.")
        else:
            add("good", "No courier rejections", "Target is zero", "On target.")

        a = attendance_stats(cd)
        if a["n"]:
            for k, v, lab in [("attendance", a["att"], "Attendance on scheduled days"), ("valid_rate", a["valid"], "Couriers completing all shifts")]:
                st_ = status(k, v)
                s_ = sched_days(cd)
                miss = int((~s_["attended"]).sum()) if k == "attendance" else int((~s_["valid"]).sum())
                extra = "" if k == "attendance" else f"  ·  {int((~s_['shifts_ok']).sum())} missed shifts, {int((~s_['orders_ok']).sum())} low orders"
                add(st_, f"{lab} {v * 100:.1f}%", f"{target_hint(k)}  ·  {gap_txt(k, v)}  ·  {miss:,} of {a['n']:,} courier-days missed" + extra,
                    "On target." if st_ == "good" else
                    ("Contact couriers who skipped scheduled days (Shifts page)." if k == "attendance" else "See who dropped each day (Shifts page)."))
            vd = valid_by_day(cd)
            if not vd.empty:
                w = vd.loc[vd["Valid %"].idxmin()]
                if w["Valid %"] < 100:
                    add("warn", f"Worst shift day: {w['date']:%a %d %b}", f"{w['Valid']:.0f} valid, {w['Dropped']:.0f} INVALID of {w['Scheduled']:.0f} scheduled ({w['Valid %']:.1f}%)",
                        "Find why that day lost couriers.")

    if daily is not None and not daily.empty:
        ok = daily.dropna(subset=["ontime_rate"])
        if not ok.empty:
            w = ok.loc[ok["ontime_rate"].idxmin()]
            if status("ontime_rate", w["ontime_rate"]) != "good":
                add(status("ontime_rate", w["ontime_rate"]), f"Worst on-time day: {w['date']:%a %d %b}",
                    f"{w['ontime_rate'] * 100:.2f}%  ·  {w['overdue'] + w['severe_overdue']:,.0f} overdue  ·  {w['delivered']:,.0f} delivered", "Check cause for that date.")

    ct = city_table(co, cd)
    if len(ct) > 2:
        c = ct.iloc[1:]
        for col, key, hb in [("On-time %", "ontime_rate", True), ("Cancel %", "cancel_rate", False),
                             ("Attendance %", "attendance", True), ("Valid %", "valid_rate", True)]:
            if col in c.columns and c[col].notna().any():
                r = c.loc[c[col].idxmin() if hb else c[col].idxmax()]
                st_ = status(key, r[col] / 100)
                if st_ != "good":
                    add(st_, f"Weakest city for {col.replace(' %', '').lower()}: {r['City']}", f"{r[col]:.2f}%  ·  {target_hint(key)}", f"Focus {r['City']} first.")

    if s is not None and not s.empty:
        tot_ov = float((s["Overdue"] + s["Severe_Overdue"]).sum())
        c = s[(s["Delivered"] >= 30) & (s["On_time_%"] < COACH_BELOW)]
        if len(c):
            share = float((c["Overdue"] + c["Severe_Overdue"]).sum()) / tot_ov if tot_ov else 0
            add("bad" if share >= 0.3 or len(c) >= 5 else "warn", f"{len(c)} couriers late too often",
                f"On-time under {COACH_BELOW}% with 30+ deliveries  ·  they cause {share:.0%} of overdue orders", "Coach them (list below).")
        idle = int((s["Delivered"] == 0).sum())
        if idle / len(s) >= 0.2:
            add("warn", f"{idle:,} of {len(s):,} listed couriers delivered nothing", f"{idle / len(s):.0%} of roster", "Activate or remove them.")
        stars = segment_couriers(s)
        stars = stars[stars["Segment"] == "Star"]
        if len(stars):
            add("good", f"{len(stars)} star couriers", f"On-time ≥ 99.6% and above-median volume  ·  {stars['Delivered'].sum() / s['Delivered'].sum():.0%} of orders", "Reward and protect.")
    if tot and tot.get("days", n_days) < n_days:
        add("warn", "Missing days", f"Only {int(tot['days'])} of {n_days} days loaded", "Upload the missing days.")
    return sorted(A, key=lambda a: {"bad": 0, "warn": 1, "good": 2, "neutral": 3}[a["sev"]])
