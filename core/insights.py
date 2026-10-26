"""Decision logic: targets, traffic-light grading, courier segments, and the auto-generated action list.

>>> EDIT THE TARGETS BELOW to match your real Keeta / company KPIs. Everything on screen
>>> (colours, status tags, the Action Center) is driven from this one place.
"""
import math
import numpy as np
import pandas as pd
from . import metrics as M

# (good, bad, higher_is_better)   good = green, between = amber, bad = red
TARGETS = {
    "ontime_rate": (0.90, 0.80, True),
    "large_ontime_rate": (0.90, 0.80, True),
    "completion_rate": (0.95, 0.90, True),
    "cancel_rate_di": (0.03, 0.06, False),
    "large_cancel_rate": (0.03, 0.06, False),
    "over55_prop": (0.03, 0.08, False),
    "avg_delivery_min": (35, 45, False),
    "couriers_delivered_prop": (0.70, 0.50, True),
    "acceptance_5min": (0.90, 0.80, True),
}
RATE_KEYS = {"ontime_rate", "large_ontime_rate", "completion_rate", "cancel_rate_di", "large_cancel_rate",
             "over55_prop", "couriers_delivered_prop", "acceptance_5min"}

# same idea for tables whose values are already in % (0-100) or plain numbers: (good, bad, higher_is_better[, zero_is_neutral])
TABLE_RULES = {
    "On-time %": (90, 80, True), "Large On-time %": (90, 80, True), "Completion %": (95, 90, True),
    "Over 55 min %": (3, 8, False), "Cancel %": (3, 6, False), "Reject %": (5, 10, False),
    "Avg Delivery (min)": (35, 45, False), "Overdue % of Delivered": (5, 10, False),
    "Completed all %": (70, 50, True), "Qualified shifts %": (80, 60, True),
    "Days Not Completed": (0, 3, False), "Avg Hrs / Working Day": (6, 4, True, True),
    "Avg Hrs / Active Courier": (6, 4, True), "Delivered vs prev day %": (0, -10, True),
    "Active % of Listed": (70, 50, True),
}

TAGS = {"good": "ON TARGET", "warn": "WATCH", "bad": "ACT NOW"}
SEG_ORDER = ["Star", "Solid", "Low efficiency", "Needs coaching", "Idle (0 deliveries)"]
SEG_ACTION = {
    "Star": "Recognise and keep. Use as mentors and give them the peak slots.",
    "Solid": "Healthy core. No action, just keep stable.",
    "Low efficiency": "Online but delivering far below the median pace. Move to busier zones / slots or review.",
    "Needs coaching": "Late too often. Coaching call, route check, take off peak slots until they improve.",
    "Idle (0 deliveries)": "Listed but delivered nothing. Re-activate or remove from the roster.",
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


def _t(key, x):
    return f"{x * 100:.0f}%" if key in RATE_KEYS else f"{x:g}"


def target_hint(key):
    t = TARGETS.get(key)
    if not t:
        return ""
    g, b, hb = t
    return f"Target {'≥' if hb else '≤'} {_t(key, g)}  ·  red {'below' if hb else 'above'} {_t(key, b)}"


def fmtv(k, v):
    if v is None or pd.isna(v):
        return "–"
    if k in RATE_KEYS:
        return f"{v * 100:.1f}%"
    return f"{v:,.1f}" if k == "avg_delivery_min" else f"{v:,.0f}"


def tone_of_text(v):
    s = str(v)
    if s.startswith(("✔", "✅", "Star")):
        return "good"
    if s.startswith(("⚠", "Low eff")):
        return "warn"
    if s.startswith(("✖", "❌", "Idle", "Needs")):
        return "bad"
    return "neutral"


def enrich(t):
    """Adds Active % of Registered to a company_total dict."""
    if not t:
        return {}
    t = dict(t)
    t["couriers_delivered_prop"] = t["couriers_delivered"] / t["registered"] if t.get("registered") else np.nan
    return t


# ---------------------------------------------------------------- courier segments
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
        if r["Delivered"] >= 30 and pd.notna(ot) and ot < 80:
            return "Needs coaching"
        if r["Valid_Hrs"] >= 20 and pd.notna(med_eff) and r["Orders_per_Valid_Hr"] < 0.5 * med_eff:
            return "Low efficiency"
        if pd.notna(ot) and ot >= 90 and r["Orders_per_Active_Day"] >= (med_day if pd.notna(med_day) else 0):
            return "Star"
        return "Solid"

    s["Segment"] = s.apply(seg, axis=1)
    s.attrs["med_eff"] = med_eff
    return s


# ---------------------------------------------------------------- action list
KPI_ACTIONS = {
    "ontime_rate": ("On-time rate", "Late deliveries hit customers directly. Start with the worst days and the couriers to coach below; add couriers in the time slots where orders run late."),
    "completion_rate": ("Completion rate", "Assigned orders are not being delivered. Check who rejects (Cancellations page) and which days lose the most orders."),
    "cancel_rate_di": ("Cancellation rate (delivery issues)", "Too many orders cancelled for delivery problems. Review couriers and days with the most cancels, and merchant waiting times."),
    "over55_prop": ("Orders over 55 minutes", "Too many very slow orders. Check meal waiting and merchant arrival times and the zones where they happen."),
    "avg_delivery_min": ("Average delivery time", "Deliveries take too long. Check peak-hour coverage and the slowest couriers."),
    "couriers_delivered_prop": ("Share of registered couriers who deliver", "Many registered couriers deliver nothing, so real capacity is lower than it looks. Re-activate them or clean the roster."),
}


def build_actions(daily, tot, ptot, cd, s, n_days):
    A = []

    def add(sev, title, evidence, action):
        A.append(dict(sev=sev, title=title, evidence=evidence, action=action))

    tot, ptot = tot or {}, ptot or {}

    # 1. headline KPIs vs target
    for k, (lab, act) in KPI_ACTIONS.items():
        v = tot.get(k)
        st_ = status(k, v)
        if st_ == "neutral":
            continue
        ev = f"{fmtv(k, v)} this period  ·  {target_hint(k)}  ·  previous period {fmtv(k, ptot.get(k))}"
        if st_ == "good":
            add("good", f"{lab} is on target", ev, "Keep doing what you are doing. No action needed.")
        else:
            add("bad" if st_ == "bad" else "warn", f"{lab} is {'in the red' if st_ == 'bad' else 'off target'}", ev, act)

    # 2. data gaps
    if tot and tot.get("days", n_days) < n_days:
        add("warn", "Some days have no company data",
            f"Only {int(tot['days'])} of {n_days} selected days are loaded, so every total here is understated.",
            "Ask for the missing days to be uploaded before judging the period.")

    # 3. trend / worst day / weekday (company daily)
    if daily is not None and not daily.empty:
        dd = daily.sort_values("date").reset_index(drop=True)
        if len(dd) >= 6:
            last, prev = dd.tail(3), dd.iloc[:-3]
            lo, po = M._wavg(last, "ontime_rate", "delivered"), M._wavg(prev, "ontime_rate", "delivered")
            if pd.notna(lo) and pd.notna(po):
                if lo < po - 0.03:
                    add("bad" if lo < po - 0.06 else "warn", "On-time rate is sliding",
                        f"Last 3 days {lo * 100:.1f}% vs {po * 100:.1f}% in the days before ({(lo - po) * 100:+.1f} pp).",
                        "Something changed in the last 3 days. Check courier availability, weather and restaurant delays for those dates.")
                elif lo > po + 0.03:
                    add("good", "On-time rate is improving",
                        f"Last 3 days {lo * 100:.1f}% vs {po * 100:.1f}% before ({(lo - po) * 100:+.1f} pp).",
                        "Find what was done differently in these days and keep it.")
            lv, pv = last["delivered"].mean(), prev["delivered"].mean()
            if pv > 0 and lv < 0.9 * pv:
                add("warn", "Order volume is falling",
                    f"Last 3 days average {lv:,.0f} delivered per day vs {pv:,.0f} before ({(lv / pv - 1) * 100:+.1f}%).",
                    "Check whether demand dropped or orders were lost (rejections, no couriers online).")
        ok = dd.dropna(subset=["ontime_rate"])
        if not ok.empty:
            w = ok.loc[ok["ontime_rate"].idxmin()]
            st_ = status("ontime_rate", w["ontime_rate"])
            if st_ != "good":
                add("bad" if st_ == "bad" else "warn", f"Worst day: {w['date']:%a %d %b}",
                    f"On-time {w['ontime_rate'] * 100:.1f}%  ·  {w['overdue']:,.0f} overdue + {w['severe_overdue']:,.0f} severely overdue  ·  "
                    f"{w['delivered']:,.0f} delivered  ·  {w['online']:,.0f} couriers online.",
                    "Find the cause for this date (courier shortage, weather, merchants) and plan so it does not repeat.")
        if len(dd) >= 7:
            dd["dow"] = dd["date"].dt.dayofweek
            g = {d: M._wavg(x, "ontime_rate", "delivered") for d, x in dd.groupby("dow")}
            g = {d: v for d, v in g.items() if pd.notna(v)}
            if len(g) >= 3:
                wd, bd = min(g, key=g.get), max(g, key=g.get)
                nm = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                if g[bd] - g[wd] > 0.04:
                    add("warn", f"{nm[wd]} is the weakest weekday",
                        f"On-time {g[wd] * 100:.1f}% on {nm[wd]} vs {g[bd] * 100:.1f}% on {nm[bd]} (gap {(g[bd] - g[wd]) * 100:.1f} pp).",
                        f"Schedule more couriers on {nm[wd]}, and copy the {nm[bd]} setup.")

    # 4. couriers
    if s is not None and not s.empty:
        tot_ov = float((s["Overdue"] + s["Severe_Overdue"]).sum())
        c = s[(s["Delivered"] >= 30) & (s["On_time_%"] < 80)]
        if len(c):
            share = float((c["Overdue"] + c["Severe_Overdue"]).sum()) / tot_ov if tot_ov else 0
            worst = ", ".join(f"{n} {o:.0f}%" for n, o in c.nsmallest(3, "On_time_%")[["Name", "On_time_%"]].itertuples(index=False))
            add("bad" if (share >= 0.3 or len(c) >= 5) else "warn", f"{len(c)} couriers are late too often",
                f"Below 80% on-time with 30+ deliveries. Together they cause {share:.0%} of all overdue orders "
                f"({(c['Overdue'] + c['Severe_Overdue']).sum():,.0f} of {tot_ov:,.0f}). Lowest: {worst}.",
                "Coach or review these couriers this week (list below). Fixing them alone removes most of the overdue orders.")
        else:
            add("good", "No courier is below 80% on-time", "Among couriers with 30+ deliveries.", "Keep monitoring weekly.")

        listed, idle = len(s), int((s["Delivered"] == 0).sum())
        if listed:
            sh = idle / listed
            idle_hrs = s.loc[s["Delivered"] == 0, "Valid_Hrs"].sum()
            if sh >= 0.2:
                add("bad" if sh >= 0.4 else "warn", f"{sh:.0%} of listed couriers delivered nothing",
                    f"{idle:,} of {listed:,} couriers have zero deliveries; they logged {idle_hrs:,.0f} online hours.",
                    "Re-activate them or remove them from the roster, so capacity planning uses real numbers.")
            else:
                add("good", "Roster is mostly active", f"Only {idle:,} of {listed:,} listed couriers ({sh:.0%}) have zero deliveries.", "No action needed.")

        seg = segment_couriers(s)
        le = seg[seg["Segment"] == "Low efficiency"]
        if len(le):
            med = seg.attrs.get("med_eff") or 0
            lost = max(0.0, float((le["Valid_Hrs"] * med - le["Delivered"]).sum()))
            add("bad" if lost > 0.1 * s["Delivered"].sum() else "warn", f"{len(le)} couriers are online but under-delivering",
                f"Under half the median pace ({med:.2f} orders per online hour). They logged {le['Valid_Hrs'].sum():,.0f} hrs; "
                f"at median pace that is about {lost:,.0f} extra orders.",
                "Move them to busier zones or slots, or check if they stay online without taking orders.")

        rej, acc = float(s["Rejected"].sum()), float(s["Accepted"].sum())
        if rej + acc > 0:
            rt = rej / (rej + acc)
            top = s.nlargest(5, "Rejected")["Rejected"].sum() / rej if rej else 0
            sev = "bad" if rt > 0.10 else ("warn" if rt > 0.05 else "good")
            add(sev, "Rejection level" if sev == "good" else "Too many rejected orders",
                f"{rej:,.0f} rejected = {rt:.1%} of tasks  ·  the top 5 couriers cause {top:.0%} of all rejections.",
                "No action needed." if sev == "good" else "Talk to the top rejecters first (Cancellations page); a few couriers drive most of it.")

        act = s[s["Delivered"] > 0].sort_values("Delivered", ascending=False)
        if len(act) >= 10:
            k = max(1, math.ceil(0.2 * len(act)))
            sh = act["Delivered"].head(k).sum() / act["Delivered"].sum()
            if sh >= 0.6:
                add("warn", "Orders depend on a few couriers",
                    f"The top 20% of couriers ({k}) deliver {sh:.0%} of all orders.",
                    "If a few of them leave or are absent, volume drops. Retain them and grow the rest.")

        st_n = seg[seg["Segment"] == "Star"]
        if len(st_n):
            add("good", f"{len(st_n)} star couriers", f"90%+ on-time and above-median volume; they deliver {st_n['Delivered'].sum() / s['Delivered'].sum():.0%} of all orders.",
                "Recognise them, protect their slots, use them as mentors.")

    # 5. supervisors
    if cd is not None and not cd.empty and cd["supervisor"].nunique() >= 2:
        g = cd.groupby("supervisor").agg(dl=("delivered", "sum"), wo=("w_ontime", "sum"))
        g = g[g["dl"] >= 50]
        if len(g) >= 2:
            g["ot"] = g["wo"] / g["dl"]
            w, b = g["ot"].idxmin(), g["ot"].idxmax()
            if g.loc[b, "ot"] - g.loc[w, "ot"] > 0.05:
                add("warn", f"Supervisor gap: {w}",
                    f"{w} on-time {g.loc[w, 'ot'] * 100:.1f}% vs {b} {g.loc[b, 'ot'] * 100:.1f}% "
                    f"(gap {(g.loc[b, 'ot'] - g.loc[w, 'ot']) * 100:.1f} pp).",
                    f"Review {w}'s team and share what {b} does.")

    # 6. shifts
    if cd is not None and not cd.empty:
        sd = M.shift_day_stats(cd)
        if not sd.empty:
            ca = sd["Completed_All"].sum() / sd["Couriers_Scheduled"].sum()
            qs = sd["Qualified_Shifts"].sum() / sd["Sched_Shifts"].sum()
            sc = M.shift_courier_stats(cd)
            rep = int((sc["Days_Not_Completed"] >= 3).sum()) if not sc.empty else 0
            sev = grade(ca * 100, 70, 50, True)
            add("good" if sev == "good" else ("bad" if sev == "bad" else "warn"),
                "Shift discipline is good" if sev == "good" else "Couriers are missing their shifts",
                f"{ca:.0%} of scheduled courier-days completed all shifts  ·  {qs:.0%} of shifts qualified  ·  {rep} couriers missed 3+ days.",
                "No action needed." if sev == "good" else "Contact the couriers who repeatedly miss (Shifts page, 'only couriers with missed shifts').")

    order = {"bad": 0, "warn": 1, "good": 2}
    return sorted(A, key=lambda a: order[a["sev"]])
