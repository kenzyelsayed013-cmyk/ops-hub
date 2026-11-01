import pandas as pd
import streamlit as st
from core import insights as I, ui


def _months():
    m = ui.meta()
    today = pd.Timestamp.today().normalize()
    first = pd.to_datetime(m["dmin"]).min() if not m.empty else today
    last = max(pd.to_datetime(m["dmax"]).max() if not m.empty else today, today)
    keys = [p.strftime("%Y-%m") for p in pd.period_range(first, last + pd.offsets.MonthBegin(1), freq="M")][::-1]
    cur = pd.to_datetime(m["dmax"]).max().strftime("%Y-%m") if not m.empty else today.strftime("%Y-%m")
    return m, keys, (keys.index(cur) if cur in keys else 0)


def _saved(msg="Saved."):
    st.cache_data.clear()
    st.success(msg)


def render():
    st.markdown('<div class="topbar"><div class="t1">RULES & TARGETS</div><div class="t2">Admin only · every section has its own Save button · changes apply to every page at once</div></div>', unsafe_allow_html=True)
    R = I.RULES
    m, keys, cur = _months()

    # ------------------------------------------------------------ A. mandatory days as dates
    st.markdown("#### 1. Mandatory days (pick the dates)")
    a1, a2 = st.columns([1, 3])
    mk = a1.selectbox("Month", keys, index=cur, format_func=lambda k: pd.Period(k).strftime("%B %Y"), key="md_month")
    days = [d.strftime("%Y-%m-%d") for d in pd.date_range(pd.Period(mk).start_time, pd.Period(mk).end_time)]
    have = [d for d in R["mandatory_dates"] if d.startswith(mk)]
    picked = a2.multiselect("Mandatory days of this month", days, default=have, key=f"md_{mk}", format_func=lambda s: pd.Timestamp(s).strftime("%a %d %b"))
    b1, b2, b3 = st.columns(3)
    mr = b1.number_input("A courier must attend at least", 0, 31, int(R["mand_required"]))
    mt = b2.number_input("out of", 1, 31, int(R["mand_total"]))
    with b3.expander("Mandatory weekdays (optional)"):
        wd = st.multiselect("Every", range(7), default=R["mandatory_weekdays"], format_func=lambda i: I.WEEKDAYS[i])
    total = len(R["mandatory_dates"])
    st.caption(f"{len(have)} mandatory days saved for this month · {total} in all months")
    if st.button("Save mandatory days", key="save_md"):
        others = [d for d in R["mandatory_dates"] if not d.startswith(mk)]
        I.save_rules({"mandatory_dates": sorted(others + picked), "mand_required": int(mr), "mand_total": int(mt), "mandatory_weekdays": sorted(wd)})
        _saved(f"Saved {len(picked)} mandatory days for {pd.Period(mk).strftime('%B %Y')}.")

    # ------------------------------------------------------------ B. validation rules
    st.markdown("#### 2. When is a courier VALID")
    c1, c2, c3 = st.columns(3)
    mn = c1.number_input("Daily minimum orders, normal day", 0, 200, int(R["min_orders_normal"]))
    mm = c2.number_input("Daily minimum orders, mandatory day", 0, 200, int(R["min_orders_mandatory"]))
    req = c3.checkbox("Must complete all scheduled shifts each day", value=bool(R["require_all_shifts"]))
    d1, d2, d3 = st.columns(3)
    mx = d1.number_input("INVALID if more than this many INVALID days in the month", 0, 31, int(R["max_invalid_days"]))
    md = d2.number_input("Working days in the month (divides the orders target)", 1, 31, int(R["min_days_month"]))
    r1 = st.checkbox("Rule: reached his orders target (target ÷ days × days he worked)", value=bool(R["rule_orders_target"]))
    r2 = st.checkbox("Rule: no more than the allowed INVALID days in the month", value=bool(R["rule_invalid_days"]))
    r3 = st.checkbox("Rule: attended the required mandatory days", value=bool(R["rule_mandatory"]))
    r4 = st.checkbox("Rule: worked at least that many days in the month", value=bool(R["rule_min_days"]))
    if st.button("Save validation rules", key="save_val"):
        I.save_rules({"min_orders_normal": int(mn), "min_orders_mandatory": int(mm), "require_all_shifts": req, "max_invalid_days": int(mx),
                      "min_days_month": int(md), "rule_orders_target": r1, "rule_invalid_days": r2, "rule_mandatory": r3, "rule_min_days": r4})
        _saved()
    st.info(I.validation_text())

    # ------------------------------------------------------------ C. monthly orders target per city
    st.markdown("#### 3. Monthly orders target, per city")
    e1, e2 = st.columns([1, 3])
    dflt = e1.number_input("Default (any city not set)", 0, 5000, int(R["month_orders_default"]), step=10)
    tk = e1.selectbox("From month", keys, index=cur, format_func=lambda k: pd.Period(k).strftime("%B %Y"), key="mo_month")
    cities = sorted(m["city"].unique()) if not m.empty else []
    ed = None
    if cities:
        ct = pd.DataFrame({"City": cities, "Orders needed / month": [I.month_target(c, tk) for c in cities]})
        with e2:
            ed = st.data_editor(ct, hide_index=True, width="stretch", disabled=["City"], key=f"mo_ed_{tk}",
                                column_config={"Orders needed / month": st.column_config.NumberColumn(min_value=0, step=10)})
        ex, rd = int(ed["Orders needed / month"].iloc[0]), max(1, int(R["min_days_month"]))
        st.caption(f"Applies from the month you pick and every later month, until you set a different one. Example: {ex} ÷ {rd} = {ex / rd:.1f} per day, "
                   f"a courier who worked 12 days needs {ex / rd * 12:.0f} orders.")
    if st.button("Save orders targets", key="save_tg"):
        cur_by = R.get("month_orders_by_month", {})
        I.save_rules({"month_orders_default": int(dflt), "month_orders_by_month": {**cur_by, tk: ({r["City"]: int(r["Orders needed / month"]) for _, r in ed.iterrows()} if ed is not None else {})}})
        _saved(f"Saved the targets from {pd.Period(tk).strftime('%B %Y')}.")

    # ------------------------------------------------------------ D. colours + delivery issue
    st.markdown("#### 4. Colour targets and Delivery Issue")
    di = st.radio("Delivery Issue: period figure", ["average", "weighted"], horizontal=True, index=0 if R.get("di_total", "average") == "average" else 1,
                  format_func=lambda x: "Average of the daily rates (as in the sheet)" if x == "average" else "Weighted by volume")
    T, new_t = R["targets"], {}
    for key, lab in [("ontime_rate", "On-time rate"), ("cancel_rate_di", "Delivery Issue % (Keeta)"), ("attendance", "Attendance on scheduled days"), ("valid_rate", "Valid couriers")]:
        a, b, c = st.columns([2, 1, 1])
        a.markdown(f"**{lab}**")
        new_t[key] = [b.number_input("Target %", 0.0, 100.0, float(T[key][0]), 0.01, key=f"t_g_{key}", format="%.2f"),
                      c.number_input("Red line %", 0.0, 100.0, float(T[key][1]), 0.01, key=f"t_b_{key}", format="%.2f")]
    if st.button("Save colour targets", key="save_col"):
        I.save_rules({"di_total": di, "targets": new_t})
        _saved()
    st.caption("Saved in rules.json and backed up to GitHub when the backup is on.")
