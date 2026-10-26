import streamlit as st
from core import db, parsers, ui
from core.config import PLATFORMS, DEFAULT_CITIES


def render():
    st.title("📤 رفع الملفات")
    if not db.is_persistent():
        st.warning("⚠️ مفيش DATABASE_URL في الـ secrets، فالداتا بتتحفظ محلياً ومؤقتاً (هتتمسح على Streamlit Cloud). "
                   "اربط Supabase الأول — الخطوات في README.")
    c1, c2 = st.columns(2)
    platform = c1.selectbox("المنصة", list(PLATFORMS), key="up_platform")
    cities = sorted(set(DEFAULT_CITIES) | set(db.known_cities())) + ["➕ مدينة جديدة…"]
    city = c2.selectbox("المدينة", cities, key="up_city")
    if city.startswith("➕"):
        city = c2.text_input("اسم المدينة الجديدة", key="up_newcity").strip()

    pkey = PLATFORMS[platform]["parser"]
    if pkey is None:
        st.info(f"منصة **{platform}** موجودة في السيستم بس لسه معندهاش parser. ابعتلي أول إكسبورت منها وهضيفها بنفس الشكل.")
        return
    st.caption("ارفع ملف المناديب وملف الشركة (واحد أو أكتر، مع بعض). السيستم بيعرف نوع كل ملف لوحده. "
               "رفع نفس الأيام تاني بيستبدلها من غير تكرار.")
    files = st.file_uploader("ملفات Excel", type=["xlsx"], accept_multiple_files=True, key="up_files")
    if not files or not city:
        return

    parsed = []
    for f in files:
        try:
            kind, df = parsers.parse_file(parsers.read_excel_any(f), pkey)
            parsed.append((f.name, kind, df))
            kname = "مناديب" if kind == "courier" else "شركة"
            extra = f" · {df['courier_id'].nunique():,} مندوب" if kind == "courier" else ""
            st.success(f"**{f.name}** → ملف {kname} · {len(df):,} صف · {df['date'].min()} → {df['date'].max()}{extra}")
        except Exception as e:
            st.error(f"**{f.name}**: {e}")
    if parsed and st.button(f"💾 احفظ في {platform} / {city}", type="primary"):
        with st.spinner("بحفظ…"):
            for name, kind, df in parsed:
                db.save(kind, df, platform, city, name)
        st.success("تم الحفظ ✔️ — اختار أي صفحة من الجنب.")
        st.rerun()

    st.divider()
    st.subheader("سجل الرفع")
    log = db.log_df()
    if not log.empty:
        st.dataframe(log, width="stretch", hide_index=True)
