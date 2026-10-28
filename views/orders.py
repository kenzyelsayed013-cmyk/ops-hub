import numpy as np
import pandas as pd
import streamlit as st
from core import ui, metrics as M, insights as I

GOOD = "background-color:#DCFCE7;color:#14532D;font-weight:700"
BAD = "background-color:#FEE2E2;color:#7F1D1D;font-weight:700"
GREY = "color:#9CA3AF"
INFO = ["Courier ID", "Name", "City", "Supervisor", "Total", "Working Days", "Avg / Working Day"]


def _n(v):
    if isinstance(v, str) or pd.isna(v):
        return "" if not isinstance(v, str) else v
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.1f}"


def render():
    f = ui.filters()
    d = ui.get_couriers()
    ui.topbar(f"{f['platform'].upper()}  ·  ORDERS BY COURIER", f, days=(f["d2"] - f["d1"]).days + 1)
    if d.empty:
        st.info("No courier data for this period / filters.")
        return
    R = I.RULES
    ui.legend()
    idx = ["courier_id", "name", "city", "supervisor"]
    P = d.pivot_table(index=idx, columns="date", values="delivered", aggfunc="sum")
    S = d.pivot_table(index=idx, columns="date", values="shifts_scheduled", aggfunc="max").reindex(index=P.index, columns=P.columns)
    P = P.loc[P.sum(axis=1).sort_values(ascending=False).index]
    S = S.loc[P.index]
    reg = P.sum(axis=1) > 0
    dates = list(P.columns)
    mand = {c: (c.dayofweek in R["mandatory_weekdays"]) or (c.strftime("%Y-%m-%d") in R["mandatory_dates"]) for c in dates}
    mins = {c: R["min_orders_mandatory"] if mand[c] else R["min_orders_normal"] for c in dates}
    tone = pd.DataFrame("", index=P.index, columns=P.columns)
    for c in dates:
        v, sch = P[c], S[c].fillna(0) > 0
        counted = sch & reg
        tone.loc[counted & v.notna() & (v >= mins[c]), c] = GOOD
        tone.loc[counted & v.notna() & (v < mins[c]), c] = BAD
        tone.loc[(v == 0) & ~counted, c] = GREY
    labels = {c: c.strftime("%m-%d") + (" ★" if mand[c] else "") for c in dates}
    wd = (P > 0).sum(axis=1)
    out = pd.DataFrame({"Courier ID": [i[0] for i in P.index], "Name": [i[1] for i in P.index], "City": [i[2] for i in P.index],
                        "Supervisor": [i[3] for i in P.index], "Total": P.sum(axis=1).values, "Working Days": wd.values,
                        "Avg / Working Day": (P.sum(axis=1) / wd.replace(0, np.nan)).values})
    for c in dates:
        out[labels[c]] = P[c].values
    tone = pd.concat([pd.DataFrame("", index=range(len(out)), columns=INFO), tone.reset_index(drop=True).set_axis([labels[c] for c in dates], axis=1)], axis=1)
    tot = {"Courier ID": "", "Name": "TOTAL", "City": "", "Supervisor": "", "Total": P.sum().sum(), "Working Days": np.nan, "Avg / Working Day": np.nan}
    tot.update({labels[c]: P[c].sum() for c in dates})
    out = pd.concat([pd.DataFrame([tot]), out], ignore_index=True)
    tone = pd.concat([pd.DataFrame("", index=[0], columns=tone.columns), tone.set_index(tone.index + 1)])

    ui.section("Orders per courier, day by day", f"green = met minimum ({R['min_orders_normal']} normal / {R['min_orders_mandatory']} mandatory ★) · red = below minimum on a scheduled day · grey = zero")
    shown = ui.search(out, "od_q")
    num = [c for c in out.columns if c not in ("Courier ID", "Name", "City", "Supervisor")]
    sty = shown.style.format(_n, subset=num)
    sty = sty.apply(lambda r: ["font-weight:800;background-color:#14181F;color:#fff"] * len(r) if r.name == 0 else [""] * len(r), axis=1)
    sty = sty.apply(lambda _: tone.loc[shown.index, shown.columns], axis=None)
    st.dataframe(sty, width="stretch", hide_index=True, height=min(760, 38 + 35 * (len(shown) + 1)))
    ui.export_row(out, f"orders_by_courier_{f['platform']}_{f['city']}", "od_x", title="Orders per courier, day by day", first_row=True, tone=tone)

    full = pd.date_range(min(dates), max(dates))
    ui.section("Orders curve, all couriers")
    tdf = d.groupby("date")["delivered"].sum().reindex(full).fillna(0).rename("Orders")
    st.line_chart(tdf, height=280)

    ui.section("Orders curve, selected couriers")
    labs = M.courier_labels(d)
    order = [i[0] for i in P.index]
    ids = st.multiselect("Couriers", order, default=order[:3], format_func=lambda i: labs.get(i, i), max_selections=8, key="od_ids")
    cum = st.checkbox("Cumulative", key="od_cum")
    if ids:
        c = d[d["courier_id"].isin(ids)].groupby(["date", "courier_id"])["delivered"].sum().unstack().reindex(full).fillna(0)
        c.columns = [labs.get(i, i) for i in c.columns]
        if cum:
            c = c.cumsum()
        elif len(ids) == 1:
            c["Required minimum"] = [mins.get(x, R["min_orders_normal"]) for x in full]
        st.line_chart(c, height=340)
