import pandas as pd
import streamlit as st
from core import ui, insights as I


def render():
    f = ui.filters()
    co, cd = ui.get_company(), ui.get_couriers()
    ui.topbar(f"{f['platform'].upper()}  ·  CITIES", f, days=(f["d2"] - f["d1"]).days + 1)
    if co.empty and cd.empty:
        st.info("No data for this period.")
        return
    ui.legend()
    ui.section("Whole period, per city")
    ui.table(I.city_table(co, cd), "cities_period", "ct_p", first_row=True, height=38 + 35 * (len(f["cities"]) + 2))
    days = sorted(set(co["date"]) | set(cd["date"]) if not cd.empty and not co.empty else (co["date"] if not co.empty else cd["date"]), reverse=True)
    day = st.selectbox("Day", days, format_func=lambda x: f"{x:%a %d %b %Y}", key="ct_day")
    ui.section(f"{day:%a %d %b %Y}, per city")
    ui.table(I.city_table(co, cd, day), f"cities_{day:%Y%m%d}", "ct_d", first_row=True, height=38 + 35 * (len(f["cities"]) + 2))
