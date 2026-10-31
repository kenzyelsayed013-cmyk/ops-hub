import streamlit as st
import pandas as pd
from core import insights as I, ui


def render():
    st.markdown('<div class="topbar"><div class="t1">RULES & TARGETS</div><div class="t2">Admin only · changes apply to every page immediately</div></div>', unsafe_allow_html=True)
    R = I.RULES
    st.markdown("#### Who counts as a valid courier on a scheduled day")
    c1, c2, c3 = st.columns(3)
    mn = c1.number_input("Minimum orders, normal day", 0, 200, int(R["min_orders_normal"]))
    mm = c2.number_input("Minimum orders, mandatory day", 0, 200, int(R["min_orders_mandatory"]))
    req = c3.checkbox("Must complete all scheduled shifts", value=bool(R["require_all_shifts"]))
    m1, m2, m3 = st.columns(3)
    mr = m1.number_input("Mandatory days: attend at least", 0, 31, int(R["mand_required"]))
    mt = m2.number_input("out of", 1, 31, int(R["mand_total"]))
    md = m3.number_input("Minimum working days per month", 0, 31, int(R["min_days_month"]))
    days = st.multiselect("Mandatory weekdays (leave empty if you use dates)", range(7), default=R["mandatory_weekdays"], format_func=lambda i: I.WEEKDAYS[i])
    extra = st.text_area("Mandatory dates (YYYY-MM-DD, one per line)", "\n".join(R["mandatory_dates"]), height=90)
    di = st.radio("Delivery Issue: how the period figure is calculated", ["average", "weighted"], horizontal=True,
                  index=0 if R.get("di_total", "average") == "average" else 1,
                  format_func=lambda x: "Average of the daily rates (as in the sheet)" if x == "average" else "Weighted by volume")
    st.markdown("#### Monthly orders target, per city and per month")
    d1, d2 = st.columns([1, 3])
    dflt = d1.number_input("Default (any city / month not set)", 0, 5000, int(R["month_orders_default"]), step=10)
    m = ui.meta()
    cities = sorted(m["city"].unique()) if not m.empty else []
    today = pd.Timestamp.today().normalize()
    first = pd.to_datetime(m["dmin"]).min() if not m.empty else today
    last = max(pd.to_datetime(m["dmax"]).max() if not m.empty else today, today)
    months = [p.strftime("%Y-%m") for p in pd.period_range(first, last + pd.offsets.MonthBegin(1), freq="M")][::-1]
    mkey = d1.selectbox("Month", months, format_func=lambda k: pd.Period(k).strftime("%B %Y"), key="mo_month")
    ct = pd.DataFrame({"City": cities, "Orders needed / month": [I.month_target(c, mkey) for c in cities]})
    ed = None
    if cities:
        with d2:
            ed = st.data_editor(ct, hide_index=True, width="stretch", disabled=["City"], key=f"mo_ed_{mkey}",
                                column_config={"Orders needed / month": st.column_config.NumberColumn(min_value=0, step=10)})
        ex = int(ed["Orders needed / month"].iloc[0]) if len(ed) else 350
        req_d = max(1, int(R["min_days_month"]))
        st.caption(f"Each courier's target = target ÷ {req_d} × the days he worked. Example: {ex} ÷ {req_d} = {ex / req_d:.1f} per day, "
                   f"so a courier who worked 12 days needs {ex / req_d * 12:.0f} orders.")
    st.markdown("#### Targets (green line) and red line, in %")
    T, new_t = R["targets"], {}
    for key, lab in [("ontime_rate", "On-time rate"), ("cancel_rate_di", "Delivery Issue % (Keeta)"), ("attendance", "Attendance on scheduled days"), ("valid_rate", "Valid couriers")]:
        a, b, _ = st.columns([2, 1, 1])
        a.markdown(f"**{lab}**")
        g = b.number_input("Target", 0.0, 100.0, float(T[key][0]), 0.01, key=f"t_g_{key}", format="%.2f")
        r = _.number_input("Red line", 0.0, 100.0, float(T[key][1]), 0.01, key=f"t_b_{key}", format="%.2f")
        new_t[key] = [g, r]
    if st.button("Save", type="primary"):
        dates = [x.strip() for x in extra.splitlines() if x.strip()]
        I.save_rules({"min_orders_normal": int(mn), "min_orders_mandatory": int(mm), "require_all_shifts": req, "month_orders_default": int(dflt),
                      "month_orders_by_month": {**R.get("month_orders_by_month", {}), mkey: ({row["City"]: int(row["Orders needed / month"]) for _, row in ed.iterrows()} if ed is not None else {})}, "di_total": di, "mand_required": int(mr), "mand_total": int(mt), "min_days_month": int(md),
                      "mandatory_weekdays": sorted(days), "mandatory_dates": dates, "targets": new_t})
        st.cache_data.clear()
        st.success("Saved.")
    st.info(I.rule_sentence())
    st.caption("Saved in rules.json next to the app. Without a database it resets on a Streamlit Cloud reboot, same as the uploaded data.")
