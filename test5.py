import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import finpy_tse as tse
import jdatetime

# تنظیمات صفحه
st.set_page_config(page_title="داشبورد بورسی", layout="wide")
st.title("📊 داشبورد ترکیبی بورس ایران")

# =============== بخش ۱: اطلاعات لحظه‌ای از tsetmc ===============
st.header("🔍 اطلاعات لحظه‌ای بازار")

# URL داده
url = "https://old.tsetmc.com/tsev2/excel/MarketWatchPlus.aspx?d=0"

# تابع بارگذاری داده لحظه‌ای
@st.cache_data
def load_live_data():
    try:
        response = requests.get(url)
        response.raise_for_status()
        workbook = BytesIO(response.content)
        df_raw = pd.read_excel(workbook, header=None, engine='openpyxl')

        # استخراج زمان بروزرسانی از سلول A3
        last_update_time = df_raw.iloc[1, 0]  # A3

        # تمیزکاری داده
        df = df_raw.iloc[2:].reset_index(drop=True)
        df.columns = df.iloc[0]
        df = df[1:].reset_index(drop=True)

        # تصحیح حروف
        def clean_arabic_chars(text):
            if pd.isna(text): return text
            if isinstance(text, str):
                return text.replace('ك', 'ک').replace('ي', 'ی')
            return text

        df.columns = [clean_arabic_chars(col) for col in df.columns]
        for col in df.columns:
            if df[col].dtype == "object":
                df[col] = df[col].apply(clean_arabic_chars)

        return df, last_update_time

    except Exception as e:
        st.error("خطا در دریافت داده لحظه‌ای")
        st.code(str(e))
        return pd.DataFrame(), "نامشخص"

# دکمه بروزرسانی داده لحظه‌ای
if st.button("🔄 بروزرسانی دستی داده لحظه‌ای"):
    st.cache_data.clear()

# بارگذاری داده لحظه‌ای
df_live, last_update_time = load_live_data()

# نمایش زمان بروزرسانی
if 'last_update_time' in locals():
    st.caption(f"📅 آخرین بروزرسانی قیمت‌ها: {last_update_time}")

# جستجو در داده لحظه‌ای
if not df_live.empty:
    symbol_col = None
    for col in df_live.columns:
        if 'نماد' in str(col):
            symbol_col = col
            break

    if not symbol_col:
        st.error("ستون 'نماد' یافت نشد.")
    else:
        symbols = df_live[symbol_col].dropna().unique().tolist()
        selected_symbol = st.selectbox(
            "🔹 نماد مورد نظر را برای جستجو انتخاب کنید",
            options=[""] + sorted([s for s in symbols if str(s).strip() != ""]),
            format_func=lambda x: "انتخاب نماد" if x == "" else x,
            key="live_selectbox"
        )

        if selected_symbol:
            result = df_live[df_live[symbol_col] == selected_symbol]
            if not result.empty:
                st.dataframe(result, use_container_width=True)
            else:
                st.warning("داده‌ای برای این نماد یافت نشد.")
else:
    st.info("داده لحظه‌ای در دسترس نیست.")

# =============== بخش ۲: بازدهی و میانگین ارزش (تکی) ===============
st.markdown("---")
st.header("📈 بازدهی و میانگین ارزش نماد")

# دکمه بروزرسانی برای بازدهی
if st.button("🔄 بروزرسانی دستی بازدهی"):
    st.cache_data.clear()

# تابع کمکی: پیدا کردن نزدیک‌ترین تاریخ قبلی
def find_closest_date(data_dates, target_jdate):
    try:
        date_objects = []
        for d in data_dates:
            try:
                y, m, day = map(int, d.split('-'))
                date_objects.append(jdatetime.date(y, m, day))
            except:
                continue
        valid_dates = [d for d in date_objects if d <= target_jdate]
        if not valid_dates:
            return None
        closest = max(valid_dates)
        for d in data_dates:
            y, m, day = map(int, d.split('-'))
            if jdatetime.date(y, m, day) == closest:
                return d
        return None
    except:
        return None

# تابع اصلی محاسبه بازدهی + میانگین ارزش
@st.cache_data
def get_returns_by_calendar(symbol):
    try:
        data = tse.Get_Price_History(
            stock=symbol,
            start_date="1402-01-01",
            end_date="1404-12-29",
            ignore_date=False
        )

        if data is None or data.empty:
            return None, "نماد پیدا نشد یا داده‌ای وجود ندارد."

        # ✅ ایجاد ستون value = Volume × Close
        if 'Volume' in data.columns and 'Close' in data.columns:
            data['value'] = data['Volume'] * data['Close']
        else:
            return None, "ستون‌های مورد نیاز (Volume یا Close) وجود ندارند."

        # آخرین روز معاملاتی
        last_date_str = data.index[-1]
        y, m, d = map(int, last_date_str.split('-'))
        last_jdate = jdatetime.date(y, m, d)
        price_today = data['Close'].iloc[-1]

        # تاریخ‌های هدف
        target_weekly = last_jdate - jdatetime.timedelta(days=7)
        target_monthly = last_jdate - jdatetime.timedelta(days=30)
        target_annual = last_jdate - jdatetime.timedelta(days=365)

        data_dates = data.index.tolist()
        results = {"امروز": last_date_str, "price_today": price_today}

        # تابع کمکی برای پیدا کردن نزدیک‌ترین تاریخ قبلی
        def find_closest_date(target):
            try:
                date_objects = []
                for d in data_dates:
                    try:
                        y, m, day = map(int, d.split('-'))
                        date_objects.append(jdatetime.date(y, m, day))
                    except:
                        continue
                valid_dates = [d for d in date_objects if d <= target]
                if not valid_dates:
                    return None
                closest = max(valid_dates)
                for d in data_dates:
                    y, m, day = map(int, d.split('-'))
                    if jdatetime.date(y, m, day) == closest:
                        return d
                return None
            except:
                return None

        # محاسبه بازدهی هفتگی
        ref_date_weekly = find_closest_date(target_weekly)
        if ref_date_weekly and ref_date_weekly in data.index:
            price_weekly = data.loc[ref_date_weekly, 'Close']
            ret_weekly = ((price_today - price_weekly) / price_weekly) * 100
            results["هفتگی"] = ret_weekly
            results["تاریخ_هفتگی"] = ref_date_weekly
        else:
            results["هفتگی"] = None
            results["تاریخ_هفتگی"] = None

        # محاسبه بازدهی ماهانه
        ref_date_monthly = find_closest_date(target_monthly)
        if ref_date_monthly and ref_date_monthly in data.index:
            price_monthly = data.loc[ref_date_monthly, 'Close']
            ret_monthly = ((price_today - price_monthly) / price_monthly) * 100
            results["ماهانه"] = ret_monthly
            results["تاریخ_ماهانه"] = ref_date_monthly
        else:
            results["ماهانه"] = None
            results["تاریخ_ماهانه"] = None

        # محاسبه بازدهی سالانه
        ref_date_annual = find_closest_date(target_annual)
        if ref_date_annual and ref_date_annual in data.index:
            price_annual = data.loc[ref_date_annual, 'Close']
            ret_annual = ((price_today - price_annual) / price_annual) * 100
            results["سالانه"] = ret_annual
            results["تاریخ_سالانه"] = ref_date_annual
        else:
            results["سالانه"] = None
            results["تاریخ_سالانه"] = None

        # --- محاسبه میانگین ارزش معاملات ۳۰ روز اخیر ---
        start_avg_date = target_monthly
        valid_dates_for_avg = []
        for d_str in data_dates:
            y, m, d = map(int, d_str.split('-'))
            jdate = jdatetime.date(y, m, d)
            if jdate >= start_avg_date and jdate <= last_jdate:
                valid_dates_for_avg.append(d_str)

        if len(valid_dates_for_avg) < 2:
            results["میانگین_ارزش"] = None
        else:
            values = data.loc[valid_dates_for_avg, 'value'].dropna()
            if len(values) == 0:
                results["میانگین_ارزش"] = None
            else:
                avg_value = values.mean()
                results["میانگین_ارزش"] = avg_value

        return results, None

    except Exception as e:
        return None, str(e)

# ورودی نماد برای بازدهی
symbol_hist = st.text_input(
    "🔹 نماد مورد نظر را برای محاسبه بازدهی وارد کنید",
    placeholder="مثلاً: فولاد، افران",
    key="hist_input"
)

if symbol_hist:
    with st.spinner(f"در حال محاسبه بازدهی برای {symbol_hist}..."):
        returns, error = get_returns_by_calendar(symbol_hist.strip())

        if error:
            st.error(error)
        else:
            st.success(f"✅ بازدهی برای نماد **{symbol_hist}** محاسبه شد")
            st.markdown(f"**آخرین روز معاملاتی**: {returns['امروز']}")
            st.markdown(f"**قیمت آخرین معامله**: {returns['price_today']:,.0f} ریال")

            # نمایش میانگین ارزش معاملات
            if returns["میانگین_ارزش"] is not None:
                st.metric(
                    "میانگین ارزش معاملات (۳۰ روز اخیر)",
                    f"{returns['میانگین_ارزش']:,.0f} ریال"
                )
            else:
                st.caption("میانگین ارزش معاملات: داده کافی نیست")

            col1, col2, col3 = st.columns(3)

            if returns["هفتگی"] is not None:
                col1.metric("بازدهی ۷ روزه", f"{returns['هفتگی']:.2f}%", f"نسبت به {returns['تاریخ_هفتگی']}")
            else:
                col1.metric("بازدهی ۷ روزه", "ندارد", "داده کافی نیست")

            if returns["ماهانه"] is not None:
                col2.metric("بازدهی ۳۰ روزه", f"{returns['ماهانه']:.2f}%", f"نسبت به {returns['تاریخ_ماهانه']}")
            else:
                col2.metric("بازدهی ۳۰ روزه", "ندارد", "داده کافی نیست")

            if returns["سالانه"] is not None:
                col3.metric("بازدهی سالانه", f"{returns['سالانه']:.2f}%", f"نسبت به {returns['تاریخ_سالانه']}")
            else:
                col3.metric("بازدهی سالانه", "ندارد", "داده کافی نیست")


else:
    st.info("لطفاً یک نماد برای محاسبه بازدهی وارد کنید.")

# =============== بخش ۳: مقایسه چند نماد ===============
st.markdown("---")
st.header("🔍 مقایسه چند نماد")

# ایجاد session_state اگر وجود نداشته باشه
if 'compare_symbols' not in st.session_state:
    st.session_state.compare_symbols = []

# استفاده از session_state برای نگه داشتن مقدار
selected_symbols = st.multiselect(
    "🔹 نمادهای مورد نظر را برای مقایسه انتخاب کنید",
    options=sorted([s for s in symbols if str(s).strip() != ""]) if 'symbols' in locals() else [],
    default=st.session_state.compare_symbols,
    key="compare_multiselect"
)

# به‌روزرسانی session_state
st.session_state.compare_symbols = selected_symbols

# دکمه مقایسه
if st.button("📊 انجام مقایسه", key="run_compare"):
    if not selected_symbols:
        st.warning("لطفاً حداقل یک نماد انتخاب کنید.")
    else:
        with st.spinner("در حال دریافت داده و محاسبه بازدهی..."):
            results = []
            for symbol in selected_symbols:
                returns, error = get_returns_by_calendar(symbol.strip())
                if error or returns is None:
                    results.append({
                        "نماد": symbol,
                        "قیمت": "-",
                        "بازدهی ۷ روزه": "-",
                        "بازدهی ۳۰ روزه": "-",
                        "بازدهی سالانه": "-",
                        "میانگین ارزش ۳۰ روزه": "ندارد",
                        "وضعیت": "خطا"
                    })
                else:
                    def format_ret(val):
                        return f"{val:.2f}%" if val is not None else "ندارد"
                    avg_val = f"{int(returns['میانگین_ارزش']):,} ریال" if returns['میانگین_ارزش'] else "ندارد"
                    results.append({
                        "نماد": symbol,
                        "قیمت": f"{returns['price_today']:,.0f}",
                        "بازدهی ۷ روزه": format_ret(returns["هفتگی"]),
                        "بازدهی ۳۰ روزه": format_ret(returns["ماهانه"]),
                        "بازدهی سالانه": format_ret(returns["سالانه"]),
                        "میانگین ارزش ۳۰ روزه": avg_val,
                        "وضعیت": "موفق"
                    })

            # ذخیره نتایج در session_state
            st.session_state.compare_results = pd.DataFrame(results)

# نمایش نتایج (اگر قبلاً محاسبه شده باشه)
if 'compare_results' in st.session_state and not st.session_state.compare_results.empty:
    st.subheader("📋 جدول مقایسه")
    st.dataframe(st.session_state.compare_results.set_index("نماد"), use_container_width=True)

    # گزارش نمادهای با خطا
    failed = st.session_state.compare_results[st.session_state.compare_results["وضعیت"] == "خطا"]
    if len(failed) > 0:
        st.warning(f"⚠️ داده‌ای برای {len(failed)} نماد یافت نشد: {', '.join(failed['نماد'])}")