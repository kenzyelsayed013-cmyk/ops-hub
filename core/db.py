"""التخزين: Supabase (Postgres) لو DATABASE_URL موجود في secrets، وإلا SQLite محلي (للتجربة بس)."""
import os
from datetime import datetime
import pandas as pd
import streamlit as st
from sqlalchemy import (MetaData, Table, Column, String, Integer, Float, Date, DateTime, Index,
                        create_engine, delete, select, func, text, and_)
from .config import SLOT_COLS

md = MetaData()

_courier_cols = [
    Column("platform", String, nullable=False), Column("city", String, nullable=False),
    Column("date", Date, nullable=False), Column("courier_id", String, nullable=False),
    Column("first_name", String), Column("last_name", String), Column("supervisor", String),
    Column("vehicle_type", String), Column("courier_type", String),
    Column("on_shift", String), Column("valid_day", String),
    Column("app_online_sec", Float), Column("valid_online_sec", Float), Column("peak_online_sec", Float),
    *[Column(c, Integer) for c in ("accepted", "arrivals", "delivered", "large_orders", "rejected",
                                    "rejected_courier", "rejected_auto", "overdue", "severe_overdue")],
    *[Column(c, Float) for c in ("cancel_rate_di", "completion_rate", "ontime_rate", "large_ontime_rate",
                                  "avg_delivery_min", "over55_prop")],
    *[Column(c, String) for c in SLOT_COLS],
    Column("shifts_scheduled", Integer), Column("shifts_qualified", Integer),
]
courier_daily = Table("courier_daily", md, *_courier_cols,
                      Index("ix_cd_pcd", "platform", "city", "date"), Index("ix_cd_cid", "courier_id"))

_company_cols = [
    Column("platform", String, nullable=False), Column("city", String, nullable=False),
    Column("date", Date, nullable=False), Column("courier_type", String), Column("headquarters", String),
    *[Column(c, Integer) for c in ("assigned", "accepted", "arrivals", "picked", "delivered", "large_orders",
                                    "rejected", "rejected_courier", "rejected_auto", "registered", "online",
                                    "couriers_accepted", "couriers_delivered", "overdue", "severe_overdue")],
    *[Column(c, Float) for c in ("cancel_rate_di", "completion_rate", "large_cancel_rate",
                                  "couriers_delivered_prop", "courier_eff", "hourly_eff", "avg_online_hrs",
                                  "large_ontime_rate", "ontime_rate", "avg_delivery_min", "acceptance_5min",
                                  "over55_prop", "merchant_arrival_min", "meal_wait_min", "meal_delivery_min")],
]
company_daily = Table("company_daily", md, *_company_cols, Index("ix_co_pcd", "platform", "city", "date"))

upload_log = Table("upload_log", md,
                   Column("id", Integer, primary_key=True, autoincrement=True),
                   Column("uploaded_at", DateTime), Column("platform", String), Column("city", String),
                   Column("kind", String), Column("filename", String), Column("rows", Integer),
                   Column("date_min", Date), Column("date_max", Date))

TABLES = {"courier": courier_daily, "company": company_daily}


@st.cache_resource(show_spinner=False)
def get_engine():
    url = None
    try:
        url = st.secrets.get("DATABASE_URL")
    except Exception:
        pass
    url = url or os.environ.get("DATABASE_URL")
    persistent = bool(url)
    if not url:
        os.makedirs("data", exist_ok=True)
        url = "sqlite:///data/local.db"
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    eng = create_engine(url, pool_pre_ping=True, future=True)
    md.create_all(eng)
    eng.persistent = persistent
    return eng


def is_persistent():
    return get_engine().persistent


# ---------------------------------------------------------------- write
def save(kind, df, platform, city, filename=""):
    """يحذف أي صفوف قديمة لنفس (منصة، مدينة، تواريخ) ويدخل الجديد. رفع نفس الملف تاني آمن."""
    eng = get_engine()
    t = TABLES[kind]
    df = df.copy()
    df.insert(0, "city", city)
    df.insert(0, "platform", platform)
    dates = sorted(df["date"].unique())
    with eng.begin() as conn:
        for i in range(0, len(dates), 500):
            conn.execute(delete(t).where(and_(t.c.platform == platform, t.c.city == city,
                                              t.c.date.in_(dates[i:i + 500]))))
        keep = [c for c in df.columns if c in t.c]
        df[keep].to_sql(t.name, conn, if_exists="append", index=False, method="multi", chunksize=400)
        conn.execute(upload_log.insert().values(
            uploaded_at=datetime.utcnow(), platform=platform, city=city, kind=kind, filename=filename,
            rows=len(df), date_min=dates[0], date_max=dates[-1]))
    st.cache_data.clear()


# ---------------------------------------------------------------- read
@st.cache_data(show_spinner=False)
def meta():
    """المنصات/المدن/نطاق التواريخ الموجودة فعلاً في الداتا."""
    eng = get_engine()
    frames = []
    with eng.connect() as conn:
        for t in (courier_daily, company_daily):
            q = select(t.c.platform, t.c.city, func.min(t.c.date).label("dmin"),
                       func.max(t.c.date).label("dmax")).group_by(t.c.platform, t.c.city)
            frames.append(pd.read_sql(q, conn))
    m = pd.concat(frames, ignore_index=True)
    if m.empty:
        return m
    m["dmin"] = pd.to_datetime(m["dmin"]).dt.date
    m["dmax"] = pd.to_datetime(m["dmax"]).dt.date
    return m.groupby(["platform", "city"], as_index=False).agg(dmin=("dmin", "min"), dmax=("dmax", "max"))


@st.cache_data(show_spinner=False)
def load(kind, platform, city, d1, d2):
    t = TABLES[kind]
    q = select(t).where(and_(t.c.platform == platform, t.c.city == city, t.c.date >= d1, t.c.date <= d2))
    with get_engine().connect() as conn:
        df = pd.read_sql(q, conn)
    df["date"] = pd.to_datetime(df["date"])
    return df


@st.cache_data(show_spinner=False)
def known_cities():
    with get_engine().connect() as conn:
        rows = conn.execute(text("select distinct city from courier_daily union select distinct city from company_daily")).fetchall()
    return sorted({r[0] for r in rows})


def log_df():
    with get_engine().connect() as conn:
        return pd.read_sql(select(upload_log).order_by(upload_log.c.id.desc()).limit(200), conn)
