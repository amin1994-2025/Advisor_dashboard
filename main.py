import os
import streamlit as st
import requests
import pandas as pd
import time
import re
import jdatetime
import traceback
import numpy as np

st.set_page_config(page_title="اطلاعات لحظه ای طلا و ارز", layout="wide")
st.title('💰 بازار طلا، ارز و رمزارز')

url = "https://Api.BrsApi.ir/Market/Gold_Currency.php?key=BqkI8HLRBU9MfLFE4vVl54pmiPslhhJj"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 OPR/106.0.0.0",
    "Accept": "application/json, text/plain, */*"
}

# تابع برای فرمت اعداد با کاما (انگلیسی)
def format_numbers(value, column_name):
    if column_name == 'change_percent':
        if isinstance(value, (int, float)):
            return f"{value}%"
        return value
    elif column_name == 'bubble_percent':
        if isinstance(value, (int, float)):
            return f"{value:.2f}%"
        return value if value else ""
    elif column_name == 'calculated_dollar':
        if isinstance(value, (int, float)):
            return f"{value:,.0f}"
        return value
    elif isinstance(value, (int, float)):
        return f"{value:,.0f}"
    return value

def convert_to_shamsi(gregorian_date):
    """تبدیل تاریخ میلادی به شمسی"""
    try:
        if isinstance(gregorian_date, str):
            year, month, day = map(int, gregorian_date.split('-'))
            shamsi_date = jdatetime.date.fromgregorian(year=year, month=month, day=day)
            return shamsi_date.strftime('%Y/%m/%d')
        return gregorian_date
    except:
        return gregorian_date
    
# تابع دریافت داده کامودیتی
def fetch_commodity_data():
    commodity_url = "https://Api.BrsApi.ir/Market/Commodity.php?key=BqkI8HLRBU9MfLFE4vVl54pmiPslhhJj"
    commodity_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 OPR/106.0.0.0",
        "Accept": "application/json, text/plain, */*"
    }
    try:
        response = requests.get(commodity_url, headers=commodity_headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"خطا در دریافت داده کامودیتی: کد وضعیت {response.status_code}")
            return None
    except Exception as e:
        st.error(f"خطا در اتصال به API کامودیتی: {e}")
        return None
    
# تابع دریافت داده گواهی‌ها از API جدید
def fetch_certificate_data_new():
    """دریافت داده گواهی‌ها از API جدید CDCLiveMarket"""
    url = "https://dataapi.ime.co.ir/api/CDC/CDCLiveMarket"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"خطا در دریافت داده گواهی‌ها: {e}")
        return None
    
# تابع پردازش داده گواهی‌ها
def process_certificate_data_new(data):
    """پردازش داده‌های گواهی از API جدید"""
    items = []
    if data and isinstance(data, list):
        for item in data:
            last_price = item.get('LastTradedPrice', 0)
            if last_price == 0 or last_price is None:
                last_price = item.get('LastSettlementPrice', 0)
            
            last_price_change = item.get('LastTradedPriceChangesPercent', 0)
            if last_price_change == 0 or last_price_change is None:
                last_price_change = item.get('LastTradedPriceChangesPercent', 0)
            
            processed_item = {
                'name': item.get('ContractDescription', ''),
                'ticker': item.get('CommodityName', ''),
                'last_price': last_price,
                'yesterday_price': item.get('LastSettlementPrice', 0),
                'last_price_change': last_price_change,
                'time': item.get('LastTradedPriceTime', ''),
                'date': item.get('LastSettlementPricePersianDate', ''),
                'type': 'گواهی کالایی'
            }
            items.append(processed_item)
    return items

# تابع دریافت داده از API ایمه (یک بار تعریف شده)
def fetch_ime_data():
    """دریافت داده از API ایمه برای طلا و نقره"""
    cdc_url = "https://dataapi.ime.co.ir/api/CDC/CDCLiveMarket"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
    }
    try:
        response = requests.get(cdc_url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return None

# تابع دریافت داده نقره از API کامودیتی
def fetch_silver_from_commodity_api():
    url = "https://Api.BrsApi.ir/Market/Commodity.php?key=BqkI8HLRBU9MfLFE4vVl54pmiPslhhJj"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 OPR/106.0.0.0",
        "Accept": "application/json, text/plain, */*"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"خطا در دریافت داده نقره: {e}")
        return None

# تابع برای محاسبه قیمت ذاتی و حباب طلا
def calculate_intrinsic_and_bubble(gold_data, currency_data):
    try:
        dollar_price = next((item.get('price', 0) for item in currency_data if item.get('name') == 'دلار'), 0)
        ounce_price = next((item.get('price', 0) for item in gold_data if item.get('name') == 'انس طلا'), 0)
        
        for item in gold_data:
            name = item.get('name')
            current_price = item.get('price', 0)
            intrinsic_price = 0
            
            if name == 'طلای 18 عیار':
                intrinsic_price = ((ounce_price * dollar_price) / 31.1) * (18/24)
            elif name == 'طلای 24 عیار':
                intrinsic_price = ((ounce_price * dollar_price) / 31.1) * (24/24)
            elif name == 'طلای آب‌شده نقدی':
                intrinsic_price = 4.6 * (18/24) * ((ounce_price * dollar_price) / 31.1)    
            elif name == 'سکه یک گرمی':
                intrinsic_price = 1.015 * (22/24) * ((ounce_price * dollar_price) / 31.1)
            elif name == 'ربع سکه':
                intrinsic_price = 2.033 * (22/24) * ((ounce_price * dollar_price) / 31.1)
            elif name == 'نیم سکه':
                intrinsic_price = 4.066 * (22/24) * ((ounce_price * dollar_price) / 31.1)
            elif name == 'سکه امامی':
                intrinsic_price = 8.133 * (22/24) * ((ounce_price * dollar_price) / 31.1)
            elif name == 'سکه بهار آزادی':
                intrinsic_price = 8.133 * (22/24) * ((ounce_price * dollar_price) / 31.1)
            elif name == 'گواهی تمام سکه بهار آزادی طرح جدید':
                intrinsic_price = (8.133 * (22/24) * ((ounce_price * dollar_price) / 31.1))*10
            elif name == 'گواهی سپرده پیوسته شمش طلای +995':
                intrinsic_price = ((ounce_price * dollar_price) / 31.1) * (24/24)
            
            if intrinsic_price > 0:
                item['intrinsic_price'] = intrinsic_price
                item['bubble_percent'] = ((current_price - intrinsic_price) / intrinsic_price) * 100
            else:
                item['intrinsic_price'] = ""
                item['bubble_percent'] = ""
        
        return gold_data
    except Exception as e:
        print(f"خطا در تابع calculate_intrinsic_and_bubble: {str(e)}")
        return gold_data

# تابع برای محاسبه دلار محاسباتی
def calculate_dollar_for_gold(gold_data):
    try:
        ounce_price = next((item.get('price', 0) for item in gold_data if item.get('name') == 'انس طلا'), 0)
        
        if ounce_price <= 0:
            return gold_data
        
        for item in gold_data:
            name = item.get('name')
            current_price = item.get('price', 0)
            calculated_dollar = 0
            
            if name == 'سکه امامی' and current_price > 0:
                calculated_dollar = (current_price * 10) / ((ounce_price * 8.133 * 22) / (31.1 * 24))
            elif name == 'نیم سکه' and current_price > 0:
                calculated_dollar = (current_price * 10) / ((ounce_price * 4.066 * 22) / (31.1 * 24))
            elif name == 'سکه بهار آزادی' and current_price > 0:
                calculated_dollar = (current_price * 10) / ((ounce_price * 8.133 * 22) / (31.1 * 24))
            elif name == 'ربع سکه' and current_price > 0:
                calculated_dollar = (current_price * 10) / ((ounce_price * 2.033 * 22) / (31.1 * 24))
            elif name == 'سکه یک گرمی' and current_price > 0:
                calculated_dollar = (current_price * 10) / ((ounce_price * 1.015 * 22) / (31.1 * 24))
            elif name == 'طلای آب‌شده نقدی' and current_price > 0:
                calculated_dollar = (current_price * 10) / ((ounce_price * 4.6 * 18) / (31.1 * 24))
            elif name == 'طلای 24 عیار' and current_price > 0:
                calculated_dollar = (current_price * 10) / (ounce_price / 31.1)
            elif name == 'طلای 18 عیار' and current_price > 0:
                calculated_dollar = (current_price * 10) / ((ounce_price * 18) / (31.1 * 24))
            elif name == 'گواهی سپرده پیوسته شمش طلای +995' and current_price > 0:
                calculated_dollar = (current_price / (ounce_price / 31.1))*10
            elif name == 'گواهی تمام سکه بهار آزادی طرح جدید' and current_price > 0:
                calculated_dollar = (current_price / ((ounce_price * 0.008133 * 900) / (31.1 * 1000)))/1000
            
            item['calculated_dollar'] = calculated_dollar if calculated_dollar > 0 else ""
        
        return gold_data
    except Exception as e:
        print(f"خطا در تابع calculate_dollar_for_gold: {str(e)}")
        return gold_data

# تابع برای محاسبه قیمت ذاتی و حباب نقره
def calculate_silver_intrinsic_and_bubble(silver_data, dollar_price, ounce_silver_price):
    try:
        for item in silver_data:
            name = item.get('name')
            current_price = item.get('price', 0)
            intrinsic_price = 0
            
            if name in ['نقره 999', 'گواهی سپرده پیوسته شمش نقره 999.9'] and dollar_price > 0 and ounce_silver_price > 0 and current_price > 0:
                intrinsic_price = ((dollar_price*10) * ounce_silver_price * (1/31.1))
                item['intrinsic_price'] = intrinsic_price
                
                if intrinsic_price > 0:
                    bubble_percent = ((current_price - intrinsic_price) / intrinsic_price) * 100
                    item['bubble_percent'] = bubble_percent
                else:
                    item['bubble_percent'] = ""
            else:
                item['intrinsic_price'] = ""
                item['bubble_percent'] = ""
        
        return silver_data
    except Exception as e:
        print(f"خطا در محاسبه قیمت ذاتی نقره: {str(e)}")
        return silver_data

# تابع برای دریافت داده
def fetch_data():
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json(), True
        else:
            return None, False
    except:
        return None, False
    
# تابع برای دریافت داده دلار توافقی
def fetch_tavafoghi_dollar_data():
    url = "https://ice.ir/api/v1/markets/2/currencies/history/15/?days=6000&lang=fa"
    try:
        response = requests.get(url, timeout=10)  # حذف verify=False
        response.raise_for_status()
        data = response.json()
        
        if 'history' in data:
            history_data = data['history']
        elif 'data' in data and 'history' in data['data']:
            history_data = data['data']['history']
        elif 'results' in data:
            history_data = data['results']
        else:
            history_data = data
        
        if isinstance(history_data, list) and len(history_data) >= 2:
            last_day = history_data[0]
            prev_day = history_data[1]
            
            last_sell_price = float(last_day.get('sell_price', 0))
            prev_sell_price = float(prev_day.get('sell_price', 0))
            last_date = last_day.get('date', '')
            last_date = convert_to_shamsi(last_date)
            
            change_value = last_sell_price - prev_sell_price if prev_sell_price > 0 else 0
            change_percent = ((last_sell_price / prev_sell_price) - 1) * 100 if prev_sell_price > 0 else 0
            
            return {
                'name': 'ارز توافقی',
                'price': last_sell_price,
                'unit': 'ریال',
                'change_percent': change_percent,
                'change_value': change_value,
                'date': last_date,
                'time': ''
            }
        return None
    except Exception as e:
        print(f"خطا در دریافت دلار توافقی: {e}")
        return None

# تابع استخراج عدد از HTML
def extract_percent_from_html(html_string):
    if not html_string:
        return "0.00%", 0
    clean_text = re.sub(r'<[^>]+>', '', html_string).strip()
    try:
        num_str = clean_text.replace('%', '').strip()
        percent_value = float(num_str) if num_str else 0
        return f"{percent_value:+.2f}%", percent_value
    except:
        return "0.00%", 0

# تابع برای استایل دادن به تغییرات
def color_change(val):
    if isinstance(val, str):
        val_clean = val.strip()
        has_percent = '%' in val_clean
        clean_val = val_clean.replace('%', '').replace('+', '').strip()
        
        try:
            num = float(clean_val)
            if val_clean.startswith('+') or num > 0:
                return 'color: green; font-weight: bold;'
            elif val_clean.startswith('-') or num < 0:
                return 'color: red; font-weight: bold;'
            return 'color: black; font-weight: bold;'
        except ValueError:
            return ''
    elif isinstance(val, (int, float)):
        color = 'green' if val > 0 else 'red' if val < 0 else 'black'
        return f'color: {color}; font-weight: bold;'
    return ''

# تابع برای محاسبه دلار محاسباتی نقره
def calculate_silver_calculated_dollar(silver_data):
    try:
        ounce_silver_price = next((item.get('price', 0) for item in silver_data if item.get('name') == 'انس نقره'), 0)
        
        if ounce_silver_price <= 0:
            return silver_data
        
        for item in silver_data:
            name = item.get('name')
            current_price = item.get('price', 0)
            calculated_dollar = 0
            
            if name == 'نقره 999' and current_price > 0:
                calculated_dollar = (current_price * 31.1) / ounce_silver_price 
            elif name == 'گواهی سپرده پیوسته شمش نقره 999.9' and current_price > 0:
                calculated_dollar = (current_price * 31.1) / ounce_silver_price
            
            item['calculated_dollar'] = calculated_dollar if calculated_dollar > 0 else ""
        
        return silver_data
        
    except Exception as e:
        print(f"خطا در تابع calculate_silver_calculated_dollar: {str(e)}")
        return silver_data

# تابع پردازش داده صندوق‌های طلا
def process_gold_funds_data_with_nav(data, gold_shamsh_dollar, gold_coin_dollar, silver_dollar):
    """پردازش داده‌های صندوق‌های طلا و استخراج فیلدهای مورد نیاز با ناو و دلار محاسباتی"""
    items = []
    
    fund_weights = {
        'عیار': {'gold_shamsh': 86.28, 'gold_coin': 13.53, 'silver': 0.09},
        'طلا': {'gold_shamsh': 85.49, 'gold_coin': 14.46, 'silver': 0},
        'کهربا': {'gold_shamsh': 83.34, 'gold_coin': 16.24, 'silver': 0.18}
    }
    
    if data and data.get('successful') and data.get('data'):
        total_items = len(data['data'])
        progress_bar = st.progress(0, text="در حال دریافت ناو صندوق‌ها...")
        
        for idx, item in enumerate(data['data']):
            name = item.get('l18', '')
            
            if name and (name.endswith('2') or (len(name) > 1 and name[-1] == '2')):
                continue
            
            insCode = item.get('insCode', '')
            
            last_price_change = item.get('plp', 0)
            if isinstance(last_price_change, str):
                try:
                    last_price_change = float(last_price_change.replace('%', ''))
                except:
                    last_price_change = 0
            
            tval = item.get('tval', 0)
            if isinstance(tval, (int, float)):
                tval_int = int(tval)
                tval_display = f"{tval_int:,}"
            else:
                tval_display = str(tval)
            
            def fetch_nav_data(insCode):
                if not insCode:
                    return None, None, None
                
                url = f"https://cdn.tsetmc.com/api/Fund/GetETFByInsCode/{insCode}"
                
                try:
                    response = requests.get(url, timeout=5)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        if 'etf' in data:
                            etf_data = data['etf']
                            predtran = etf_data.get('pRedTran')
                            hEven = etf_data.get('hEven')
                            deven = etf_data.get('deven')
                            
                            time_str = ""
                            shamsi_date = ""
                            
                            if hEven:
                                hEven_str = str(hEven).zfill(6)
                                time_str = f"{hEven_str[:2]}:{hEven_str[2:4]}:{hEven_str[4:6]}"
                            
                            if deven:
                                deven_str = str(deven)
                                if len(deven_str) == 8:
                                    gregorian_date = f"{deven_str[:4]}-{deven_str[4:6]}-{deven_str[6:8]}"
                                    shamsi_date = convert_to_shamsi(gregorian_date)
                                else:
                                    shamsi_date = deven_str
                            
                            return predtran, time_str, shamsi_date
                    
                    return None, None, None
                        
                except Exception as e:
                    return None, None, None
            
            predtran, nav_time, nav_date = fetch_nav_data(insCode)
            
            bubble_percent = None
            last_price_value = item.get('pl', 0)
            
            if predtran and isinstance(predtran, (int, float)) and predtran > 0:
                if isinstance(last_price_value, (int, float)) and last_price_value > 0:
                    bubble_percent = ((last_price_value / predtran) - 1) * 100
            
            if predtran and isinstance(predtran, (int, float)):
                predtran_display = f"{predtran:,.0f}"
            else:
                predtran_display = "-"
            
            nav_time_display = nav_time if nav_time else "-"
            nav_date_display = nav_date if nav_date else "-"
            
            calculated_fund_dollar = None
            gold_shamsh_weight = 0
            gold_coin_weight = 0
            silver_weight = 0
            
            fund_name_normalized = name.strip()
            
            for fund_key in fund_weights:
                if fund_key in fund_name_normalized:
                    weights = fund_weights[fund_key]
                    gold_shamsh_weight = weights.get('gold_shamsh', 0)
                    gold_coin_weight = weights.get('gold_coin', 0)
                    silver_weight = weights.get('silver', 0)
                    
                    if gold_shamsh_dollar and gold_coin_dollar and silver_dollar:
                        calculated_fund_dollar = (
                            (gold_shamsh_dollar * (gold_shamsh_weight /100)) +
                            ((gold_coin_dollar/10) * (gold_coin_weight /100)) +
                            (silver_dollar * (silver_weight /100))
                        )
                    break
            
            if calculated_fund_dollar and isinstance(calculated_fund_dollar, (int, float)):
                calculated_fund_dollar_display = f"{calculated_fund_dollar:,.0f}"
            else:
                calculated_fund_dollar_display = "-"
            
            processed_item = {
                'name': name,
                'full_name': item.get('l30', ''),
                'last_price': last_price_value,
                'adj_price': item.get('pc', 0),
                'transaction_value': tval_display,
                'last_price_change': last_price_change,
                'time': item.get('time', ''),
                'time_update': item.get('time_update', ''),
                'tno': item.get('tno', 0),
                'nav': predtran_display,
                'nav_time': nav_time_display,
                'nav_date': nav_date_display,
                'bubble_percent': bubble_percent,
                'calculated_fund_dollar': calculated_fund_dollar_display,
                'weight_gold_shamsh': f"{gold_shamsh_weight:.2f}%",
                'weight_gold_coin': f"{gold_coin_weight:.2f}%",
                'weight_silver': f"{silver_weight:.2f}%"
            }
            items.append(processed_item)
            
            progress_bar.progress((idx + 1) / total_items, text=f"در حال دریافت ناو {name}...")
        
        progress_bar.empty()
    return items

def fetch_future_gold_data():
    """دریافت داده آتی طلا از API ایمه"""
    url = "https://dataapi.ime.co.ir/api/Future/LiveMarket"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"خطا در دریافت داده آتی طلا: {e}")
        return None
    
def process_future_gold_data(data):
    """پردازش داده‌های آتی طلا و استخراج فیلدهای مورد نیاز"""
    items = []
    
    if data and isinstance(data, list):
        for item in data:
            # فیلدهای اصلی
            contract_description = item.get('ContractDescription', '')
            
            # فقط قراردادهای مرتبط با طلا را نمایش بده
            if 'طل' not in contract_description and 'طلا' not in contract_description:
                continue
            
            last_price = item.get('LastTradedPrice', 0)
            yesterday_price = item.get('LastSettlementPrice', 0)
            change_percent = item.get('LastTradedPriceChangesPercent', 0)
            trading_date = item.get('LastTradingDate', '')
            last_update = item.get('LastUpdate', '')
            
            # تبدیل تاریخ میلادی به شمسی برای تاریخ سررسید
            if trading_date:
                try:
                    date_part = trading_date.split('T')[0]
                    year, month, day = map(int, date_part.split('-'))
                    shamsi_date = jdatetime.date.fromgregorian(year=year, month=month, day=day)
                    trading_date = shamsi_date.strftime('%Y/%m/%d')
                except:
                    pass
            
            # تبدیل تاریخ LastUpdate به شمسی (فقط تاریخ، بدون ساعت)
            if last_update:
                try:
                    update_part = last_update.split('T')[0]
                    year, month, day = map(int, update_part.split('-'))
                    shamsi_update = jdatetime.date.fromgregorian(year=year, month=month, day=day)
                    last_update_display = shamsi_update.strftime('%Y/%m/%d')
                except:
                    last_update_display = last_update
            else:
                last_update_display = ''
            
            processed_item = {
                'name': contract_description,
                'contract_code': item.get('ContractCode', ''),
                'last_price': last_price,
                'yesterday_price': yesterday_price,
                'change_percent': change_percent,
                'trade_date': trading_date,
                'last_update': last_update_display,
                'calculated_dollar': '',  # دلار محاسباتی - بعداً پر می‌شود
                'price_distance': None    # مقدار موقت برای محاسبه بعدی
            }
            items.append(processed_item)
    
    return items

# دکمه بروزرسانی
col1, col2 = st.columns([4, 1])
with col2:
    if st.button('🔄 بروزرسانی', use_container_width=True):
        st.session_state.last_update = time.time()
        with st.spinner('در حال بروزرسانی داده‌ها...'):
            new_data, success = fetch_data()
            if success:
                st.session_state.market_data = new_data
                st.success('✅ داده‌ها با موفقیت بروزرسانی شدند')
            else:
                st.error('❌ خطا در بروزرسانی داده‌ها')

# مقداردهی اولیه session state
if 'market_data' not in st.session_state:
    with st.spinner('در حال دریافت داده‌ها...'):
        data, success = fetch_data()
        if success:
            st.session_state.market_data = data
            st.session_state.last_update = time.time()
        else:
            st.error('❌ خطا در دریافت داده‌ها از سرور')

# نمایش زمان آخرین بروزرسانی
if 'last_update' in st.session_state:
    last_update_time = time.strftime('%H:%M:%S', time.localtime(st.session_state.last_update))
    st.caption(f'🕒 آخرین بروزرسانی: {last_update_time}')

try:
    if 'market_data' in st.session_state:
        data = st.session_state.market_data

        # دریافت داده گواهی طلا (شمش و سکه)
        gold_shamsh_calculated_dollar = None
        gold_coin_calculated_dollar = None
        silver_calculated_dollar = None

        try:
            ime_data = fetch_ime_data()
            if ime_data and isinstance(ime_data, list):
                ounce_price = 0
                if 'gold_data' in st.session_state:
                    for item in st.session_state.gold_data:
                        if item.get('name') == 'انس طلا':
                            ounce_price = item.get('price', 0)
                            break
                
                for item in ime_data:
                    contract_desc = item.get('ContractDescription', '')
                    
                    if 'گواهی سپرده پیوسته شمش طلای +995' in contract_desc:
                        if ounce_price > 0:
                            last_price = item.get('LastTradedPrice', 0)
                            if last_price == 0 or last_price is None:
                                last_price = item.get('LastSettlementPrice', 0)
                            if last_price > 0:
                                gold_shamsh_calculated_dollar = (last_price / (ounce_price / 31.1)) * 10
                    
                    elif 'گواهی تمام سکه بهار آزادی طرح جدید' in contract_desc or 'گواهی سپرده پیوسته تمام سکه بهار آزادی طرح جدید' in contract_desc:
                        if ounce_price > 0:
                            last_price = item.get('LastTradedPrice', 0)
                            if last_price == 0 or last_price is None:
                                last_price = item.get('LastSettlementPrice', 0)
                            if last_price > 0:
                                gold_coin_calculated_dollar = (last_price * 10) / ((ounce_price * 8.133 * 22) / (31.1 * 24))
        except Exception as e:
            st.warning(f"خطا در دریافت داده گواهی طلا: {e}")

        # دریافت دلار نقره از گواهی نقره
        try:
            ime_data = fetch_ime_data()
            if ime_data and isinstance(ime_data, list):
                ounce_silver_price = 0
                if 'silver_data' in st.session_state:
                    for item in st.session_state.silver_data:
                        if item.get('name') == 'انس نقره':
                            ounce_silver_price = item.get('price', 0)
                            break
                
                for item in ime_data:
                    if 'گواهی سپرده پیوسته شمش نقره 999.9' in item.get('ContractDescription', ''):
                        if ounce_silver_price > 0:
                            last_price = item.get('LastTradedPrice', 0)
                            if last_price == 0 or last_price is None:
                                last_price = item.get('LastSettlementPrice', 0)
                            if last_price > 0:
                                silver_calculated_dollar = (last_price * 31.1) / ounce_silver_price
                        break
        except Exception as e:
            st.warning(f"خطا در دریافت داده گواهی نقره: {e}")

        # ذخیره در session_state برای استفاده در تب صندوق‌ها
        st.session_state.gold_shamsh_dollar = gold_shamsh_calculated_dollar
        st.session_state.gold_coin_dollar = gold_coin_calculated_dollar
        st.session_state.silver_dollar = silver_calculated_dollar
        
        # ایجاد تب‌های جداگانه برای هر دسته
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(["🏅 طلا", "💵 ارز", "₿ رمزارز", "🥈 نقره", "📦 کامودیتی", "📜 گواهی‌ها", "🏦 صندوق‌های طلا",
                                                                         "📈 آتی طلا"])
        
        with tab1:
            st.subheader("قیمت طلا")
            
            try:
                ime_cdc_data = fetch_ime_data()
                
                currency_data = data.get('currency', [])
                dollar_price = 0
                if currency_data:
                    dollar_item = next((item for item in currency_data if item.get('name') == 'دلار'), None)
                    if dollar_item:
                        dollar_price = dollar_item.get('price', 0)
                
                gold_data = []
                
                if 'gold' in data:
                    original_gold_data = data['gold']
                    if isinstance(original_gold_data, list):
                        for item in original_gold_data:
                            change_percent_raw = item.get('change_percent', '0')
                            if isinstance(change_percent_raw, str):
                                change_percent_str, change_percent_float = extract_percent_from_html(change_percent_raw)
                            elif isinstance(change_percent_raw, (int, float)):
                                change_percent_float = change_percent_raw
                                change_percent_str = f"{change_percent_float:+.2f}%" if change_percent_float != 0 else "0.00%"
                            else:
                                change_percent_float = 0
                                change_percent_str = "0.00%"
                            
                            gold_item = {
                                'name': item.get('name', ''),
                                'price': item.get('price', 0),
                                'unit': item.get('unit', 'ریال'),
                                'change_percent': change_percent_str,
                                'change_percent_value': change_percent_float,
                                'date': item.get('date', ''),
                                'time': item.get('time', ''),
                                'intrinsic_price': item.get('intrinsic_price', 0),
                                'bubble_percent': item.get('bubble_percent', "")
                            }
                            gold_data.append(gold_item)
                
                target_contracts = [
                    'گواهی سپرده پیوسته تمام سکه بهار آزادی طرح جدید',
                    'گواهی سپرده پیوسته شمش طلای +995'
                ]
                
                if ime_cdc_data and isinstance(ime_cdc_data, list):
                    for item in ime_cdc_data:
                        contract_desc = item.get('ContractDescription', '')
                        
                        if any(target in contract_desc for target in target_contracts):
                            if 'تمام سکه' in contract_desc:
                                display_name = 'گواهی تمام سکه بهار آزادی طرح جدید'
                            elif 'شمش طلای' in contract_desc:
                                display_name = 'گواهی سپرده پیوسته شمش طلای +995'
                            else:
                                display_name = contract_desc
                            
                            change_percent = item.get('LastTradedPriceChangesPercent', 0)
                            if isinstance(change_percent, (int, float)):
                                change_percent_str = f"{change_percent:+.2f}%" if change_percent != 0 else "0.00%"
                                change_percent_float = change_percent
                            else:
                                change_percent_str = "0.00%"
                                change_percent_float = 0
                            
                            last_traded_price = item.get('LastTradedPrice', 0)
                            last_settlement_price = item.get('LastSettlementPrice', 0)

                            if last_traded_price == 0 or last_traded_price is None:
                                final_price = last_settlement_price
                            else:
                                final_price = last_traded_price

                            gold_item = {
                                'name': display_name,
                                'price': final_price,
                                'unit': 'ریال',
                                'change_percent': change_percent_str,
                                'change_percent_value': change_percent_float,
                                'date': item.get('LastSettlementPricePersianDate', ''),
                                'time': '',
                                'intrinsic_price': 0,
                                'bubble_percent': ""
                            }
                            gold_data.append(gold_item)
                
                gold_data = calculate_intrinsic_and_bubble(gold_data, currency_data)
                gold_data = calculate_dollar_for_gold(gold_data)
        
                st.session_state.gold_data = gold_data
                
                if isinstance(gold_data, list) and len(gold_data) > 0:
                    df_gold = pd.DataFrame(gold_data)
                    
                    important_gold_items = ['طلای 18 عیار', 'سکه امامی', 'نیم سکه', 'ربع سکه', 'انس طلا', 'گواهی سپرده پیوسته شمش طلای +995']

                    cols = st.columns(len(important_gold_items))

                    for i, item_name in enumerate(important_gold_items):
                        item_data = next((item for item in gold_data if item.get('name') == item_name), None)
                        if item_data:
                            with cols[i]:
                                bubble_info = ""
                                if 'bubble_percent' in item_data and item_data['bubble_percent'] != "":
                                    bubble_value = item_data['bubble_percent']
                                    if isinstance(bubble_value, (int, float)):
                                        bubble_info = f"حباب: {bubble_value:.1f}%"
                                    else:
                                        bubble_info = f"حباب: {bubble_value}"
                                
                                change_percent_float = item_data.get('change_percent_value', 0)
                                
                                st.metric(
                                    label=item_name,
                                    value=f"{format_numbers(item_data.get('price', 0), 'price')}",
                                    delta=f"{change_percent_float:+.2f}%" if change_percent_float != 0 else "0.00%",
                                    help=f"واحد: {item_data.get('unit', '')}\n{bubble_info}"
                                )
                    
                    columns_to_drop_gold = ['time_unix', 'symbol', 'name_en', 'change_percent_value']
                    existing_columns_to_drop = [col for col in columns_to_drop_gold if col in df_gold.columns]
                    df_gold = df_gold.drop(columns=existing_columns_to_drop, errors='ignore')
                    
                    gold_column_order = ['name', 'price', 'calculated_dollar', 'intrinsic_price', 'bubble_percent', 'unit', 'change_percent', 'date', 'time']
                    existing_columns = [col for col in gold_column_order if col in df_gold.columns]
                    remaining_columns = [col for col in df_gold.columns if col not in existing_columns]
                    final_column_order = existing_columns + remaining_columns
                    
                    df_gold = df_gold[final_column_order]
                    df_gold = df_gold.fillna('')
                    
                    for column in df_gold.columns:
                        if column in ['intrinsic_price', 'price', 'change_value', 'calculated_dollar']:
                            df_gold[column] = df_gold[column].apply(lambda x: format_numbers(x, column) if x != '' and x != 0 and pd.notna(x) else '')
                        elif column == 'bubble_percent':
                            df_gold[column] = df_gold[column].apply(lambda x: format_numbers(x, column) if x != '' and x != 0 and pd.notna(x) else '')
                    
                    styled_df = df_gold.style.applymap(color_change, subset=['change_percent', 'bubble_percent'])
                    st.dataframe(styled_df, use_container_width=True, hide_index=True, height=423)
                else:
                    st.warning("داده طلا یافت نشد")
                    
            except Exception as e:
                st.error(f"❌ خطا در بارگذاری داده‌های طلا: {e}")
        
        with tab2:
            st.subheader("نرخ ارز")
            
            if 'currency' in data:
                currency_data = data['currency']
                tavafoghi_data = fetch_tavafoghi_dollar_data()
                if tavafoghi_data:
                    currency_data = [item for item in currency_data if item.get('name') != 'ارز توافقی']
                    
                    change_percent_val = tavafoghi_data['change_percent']
                    tavafoghi_data['change_percent'] = f"{change_percent_val:+.2f}%" if change_percent_val != 0 else "0.00%"
                    
                    dollar_tether_index = next((i for i, item in enumerate(currency_data) if item.get('name') == 'دلار تتر'), None)
                    if dollar_tether_index is not None:
                        currency_data.insert(dollar_tether_index + 1, tavafoghi_data)
                    else:
                        currency_data.append(tavafoghi_data)

                if isinstance(currency_data, list):
                    df_currency = pd.DataFrame(currency_data)
                    
                    important_currency_items = ['دلار', 'دلار تتر', 'ارز توافقی', 'یورو', 'درهم امارات', 'پوند']
                    
                    cols = st.columns(len(important_currency_items))
                    
                    for i, item_name in enumerate(important_currency_items):
                        item_data = next((item for item in currency_data if item.get('name') == item_name), None)
                        if item_data:
                            with cols[i]:
                                st.metric(
                                    label=item_name,
                                    value=f"{format_numbers(item_data.get('price', 0), 'price')}",
                                    delta=f"{format_numbers(item_data.get('change_percent', 0), 'change_percent')}",
                                    help=f"واحد: {item_data.get('unit', '')}"
                                )
                    
                    columns_to_drop_currency = ['time_unix', 'symbol', 'name_en']
                    existing_columns_to_drop = [col for col in columns_to_drop_currency if col in df_currency.columns]
                    df_currency = df_currency.drop(columns=existing_columns_to_drop, errors='ignore')
                    
                    currency_column_order = ['name', 'price', 'unit', 'change_percent', 'change_value', 'date', 'time']
                    existing_columns = [col for col in currency_column_order if col in df_currency.columns]
                    remaining_columns = [col for col in df_currency.columns if col not in existing_columns]
                    final_column_order = existing_columns + remaining_columns
                    
                    df_currency = df_currency[final_column_order]
                    
                    for column in df_currency.columns:
                        df_currency[column] = df_currency[column].apply(lambda x: format_numbers(x, column))

                    styled_df = df_currency.style.applymap(color_change, subset=['change_percent'])
                    st.dataframe(styled_df, use_container_width=True, hide_index=True, height=600)    
                else:
                    st.write("داده ارز به صورت لیست نیست")
            else:
                st.warning("داده ارز یافت نشد")
        
        with tab3:
            st.subheader("قیمت رمزارزها")
            
            crypto_key = 'crypto' if 'crypto' in data else 'cryptocurrency' if 'cryptocurrency' in data else None
            
            if crypto_key:
                crypto_data = data[crypto_key]
                if isinstance(crypto_data, list):
                    df_crypto = pd.DataFrame(crypto_data)
                    
                    important_crypto_items = ['bitcoin', 'ethereum', 'solana', 'dogecoin', 'cardano']
                    
                    cols = st.columns(len(important_crypto_items))
                    
                    for i, item_name in enumerate(important_crypto_items):
                        item_data = next((item for item in crypto_data if item.get('name_en', '').lower() == item_name.lower()), None)
                        if item_data:
                            with cols[i]:
                                st.metric(
                                    label=item_data.get('name', item_name),
                                    value=f"{format_numbers(item_data.get('price', 0), 'price')}",
                                    delta=f"{format_numbers(item_data.get('change_percent', 0), 'change_percent')}",
                                    help=f"واحد: {item_data.get('unit', '')}"
                                )
                    
                    columns_to_drop_crypto = ['time_unix', 'description']
                    existing_columns_to_drop = [col for col in columns_to_drop_crypto if col in df_crypto.columns]
                    df_crypto = df_crypto.drop(columns=existing_columns_to_drop, errors='ignore')
                    
                    crypto_column_order = ['name_en', 'name', 'symbol', 'price', 'unit', 'change_percent', 'market_cap', 'date', 'time']
                    existing_columns = [col for col in crypto_column_order if col in df_crypto.columns]
                    remaining_columns = [col for col in df_crypto.columns if col not in existing_columns]
                    final_column_order = existing_columns + remaining_columns
                    
                    df_crypto = df_crypto[final_column_order]
                    
                    for column in df_crypto.columns:
                        df_crypto[column] = df_crypto[column].apply(lambda x: format_numbers(x, column))

                    styled_df = df_crypto.style.applymap(color_change, subset=['change_percent'])
                    st.dataframe(styled_df, use_container_width=True, hide_index=True, height=600)
                else:
                    st.write("داده رمزارز به صورت لیست نیست")
            else:
                st.warning("داده رمزارز یافت نشد")

        with tab4:
            st.subheader("قیمت نقره")
            
            try:
                commodity_data = fetch_silver_from_commodity_api()
                
                silver_data = []
                
                if commodity_data and isinstance(commodity_data, dict) and 'metal_precious' in commodity_data:
                    metal_precious_list = commodity_data['metal_precious']
                    
                    if isinstance(metal_precious_list, list):
                        for item in metal_precious_list:
                            name = item.get('name', '')
                            
                            if name == 'انس نقره':
                                price_ons = float(item.get('price', 0))
                                
                                change_percent_raw = item.get('change_percent', 0)
                                if isinstance(change_percent_raw, (int, float)):
                                    change_percent_ons = f"{change_percent_raw:+.2f}%" if change_percent_raw != 0 else "0.00%"
                                else:
                                    change_percent_ons = "0.00%"
                                
                                ons_silver_item = {
                                    'name': 'انس نقره',
                                    'price': price_ons,
                                    'unit': item.get('unit', 'دلار'),
                                    'change_percent': change_percent_ons,
                                    'date': item.get('date', ''),
                                    'time': item.get('time', ''),
                                    'intrinsic_price': "",
                                    'bubble_percent': ""
                                }
                                silver_data.append(ons_silver_item)
                            
                            elif name == 'نقره 999':
                                price_999 = float(item.get('price', 0))
                                
                                change_percent_raw = item.get('change_percent', 0)
                                if isinstance(change_percent_raw, (int, float)):
                                    change_percent_999 = f"{change_percent_raw:+.2f}%" if change_percent_raw != 0 else "0.00%"
                                else:
                                    change_percent_999 = "0.00%"
                                
                                silver999_item = {
                                    'name': 'نقره 999',
                                    'price': price_999,
                                    'unit': item.get('unit', 'ریال'),
                                    'change_percent': change_percent_999,
                                    'date': item.get('date', ''),
                                    'time': item.get('time', ''),
                                    'intrinsic_price': 0,
                                    'bubble_percent': ""
                                }
                                silver_data.append(silver999_item)
                
                ime_cdc_data = fetch_ime_data()
                
                if ime_cdc_data and isinstance(ime_cdc_data, list):
                    for item in ime_cdc_data:
                        if item.get('ContractDescription') == 'گواهی سپرده پیوسته شمش نقره 999.9':
                            change_percent = item.get('LastTradedPriceChangesPercent', 0)
                            if isinstance(change_percent, (int, float)):
                                change_percent_str = f"{change_percent:+.2f}%" if change_percent != 0 else "0.00%"
                            else:
                                change_percent_str = str(change_percent)
                            
                            last_traded_price = item.get('LastTradedPrice', 0)
                            last_settlement_price = item.get('LastSettlementPrice', 0)
                            
                            if last_traded_price == 0 or last_traded_price is None:
                                final_price = last_settlement_price
                            else:
                                final_price = last_traded_price
                            
                            shemesh_item = {
                                'name': item.get('ContractDescription', 'گواهی سپرده پیوسته شمش نقره 999.9'),
                                'price': final_price,
                                'unit': 'ریال',
                                'change_percent': change_percent_str,
                                'date': item.get('LastSettlementPricePersianDate', ''),
                                'time': '',
                                'intrinsic_price': 0,
                                'bubble_percent': ""
                            }
                            silver_data.append(shemesh_item)
                            break
                
                dollar_price = 0
                if 'currency' in data:
                    currency_data = data['currency']
                    dollar_item = next((item for item in currency_data if item.get('name') == 'دلار'), None)
                    if dollar_item:
                        dollar_price = dollar_item.get('price', 0)
                
                ounce_silver_price = 0
                if silver_data:
                    ons_item = next((item for item in silver_data if item['name'] == 'انس نقره'), None)
                    if ons_item:
                        ounce_silver_price = ons_item['price']
                
                silver_data = calculate_silver_intrinsic_and_bubble(silver_data, dollar_price, ounce_silver_price)
                silver_data = calculate_silver_calculated_dollar(silver_data)
                st.session_state.silver_data = silver_data
                
                if silver_data:
                    df_silver = pd.DataFrame(silver_data)
                    
                    important_silver_items = ['نقره 999', 'انس نقره', 'گواهی سپرده پیوسته شمش نقره 999.9']
                    
                    cols = st.columns(len(important_silver_items))
                    
                    for i, item_name in enumerate(important_silver_items):
                        item_data = next((item for item in silver_data if item.get('name') == item_name), None)
                        
                        if item_data:
                            with cols[i]:
                                bubble_info = ""
                                if 'bubble_percent' in item_data and item_data['bubble_percent'] != "" and item_data['bubble_percent']:
                                    bubble_value = item_data['bubble_percent']
                                    if isinstance(bubble_value, (int, float)):
                                        bubble_info = f"حباب: {bubble_value:.1f}%"
                                    else:
                                        bubble_info = f"حباب: {bubble_value}"
                                
                                change_percent_str = item_data.get('change_percent', '0')
                                change_percent_float = 0
                                try:
                                    clean_percent = str(change_percent_str).replace('%', '').strip()
                                    if '+' in clean_percent:
                                        clean_percent = clean_percent.replace('+', '')
                                    change_percent_float = float(clean_percent) if clean_percent else 0
                                except:
                                    change_percent_float = 0
                                
                                price_value = item_data.get('price', 0)
                                if item_data.get('name') == 'انس نقره':
                                    price_display = f"{price_value:,.2f}" if price_value else "۰"
                                else:
                                    price_display = format_numbers(price_value, 'price')
                                
                                st.metric(
                                    label=item_data.get('name', item_name),
                                    value=price_display,
                                    delta=f"{change_percent_float:+.2f}%" if change_percent_float != 0 else "0.00%",
                                    delta_color="normal" if change_percent_float >= 0 else "inverse",
                                    help=f"واحد: {item_data.get('unit', '')}\n{bubble_info}"
                                )
                    
                    silver_column_order = ['name', 'price', 'calculated_dollar', 'intrinsic_price', 'bubble_percent', 'unit', 'change_percent', 'date', 'time']
                    existing_columns = [col for col in silver_column_order if col in df_silver.columns]
                    remaining_columns = [col for col in df_silver.columns if col not in existing_columns]
                    final_column_order = existing_columns + remaining_columns
                    
                    df_silver = df_silver[final_column_order]
                    df_silver = df_silver.fillna('')
                    
                    def format_price_with_name(row):
                        name = row.get('name', '')
                        price = row.get('price', 0)
                        if price == '' or price == 0 or pd.isna(price):
                            return ''
                        if name == 'انس نقره':
                            return f"{price:,.2f}"
                        else:
                            return format_numbers(price, 'price')
                    
                    if 'price' in df_silver.columns:
                        df_silver['price'] = df_silver.apply(format_price_with_name, axis=1)
                    
                    for column in df_silver.columns:
                        if column in ['intrinsic_price']:
                            df_silver[column] = df_silver[column].apply(lambda x: format_numbers(x, column) if x != '' and x != 0 and pd.notna(x) else '')
                        if column == 'calculated_dollar':
                            df_silver[column] = df_silver[column].apply(lambda x: format_numbers(x, column) if x != '' and x != 0 and pd.notna(x) else '')
                        elif column == 'bubble_percent':
                            df_silver[column] = df_silver[column].apply(lambda x: format_numbers(x, column) if x != '' and x != 0 and pd.notna(x) else '')
                    
                    styled_df = df_silver.style.applymap(color_change, subset=['change_percent', 'bubble_percent'])
                    st.dataframe(styled_df, use_container_width=True, hide_index=True)
                else:
                    st.warning("داده‌های نقره یافت نشد")
                    
            except Exception as e:
                st.error(f"❌ خطا در بارگذاری داده‌های نقره: {e}")
                st.code(traceback.format_exc())
        
        with tab5:
            st.subheader("📊 قیمت کامودیتی‌ها")
            
            commodity_data = fetch_commodity_data()
            
            if commodity_data and isinstance(commodity_data, dict):
                all_items = []
                
                for key, items in commodity_data.items():
                    if isinstance(items, list):
                        for item in items:
                            if isinstance(item, dict) and 'name' in item:
                                change_percent_raw = item.get('change_percent', 0)
                                if isinstance(change_percent_raw, (int, float)):
                                    change_percent_display = f"{change_percent_raw:+.2f}%" if change_percent_raw != 0 else "0.00%"
                                    change_percent_value = change_percent_raw
                                else:
                                    change_percent_display = str(change_percent_raw) if change_percent_raw else "0.00%"
                                    try:
                                        change_percent_value = float(str(change_percent_raw).replace('%', '').strip())
                                    except:
                                        change_percent_value = 0
                                
                                change_value_raw = item.get('change_value', 0)
                                if isinstance(change_value_raw, (int, float)):
                                    change_value_display = f"{change_value_raw:+,.2f}" if change_value_raw != 0 else "0"
                                    change_value_num = change_value_raw
                                else:
                                    change_value_display = str(change_value_raw) if change_value_raw else "0"
                                    try:
                                        change_value_num = float(change_value_raw)
                                    except:
                                        change_value_num = 0
                                
                                all_items.append({
                                    'name': item.get('name', ''),
                                    'price': item.get('price', 0),
                                    'unit': item.get('unit', ''),
                                    'change_value': change_value_display,
                                    'change_value_num': change_value_num,
                                    'change_percent': change_percent_display,
                                    'change_percent_num': change_percent_value,
                                    'date': item.get('date', ''),
                                    'time': item.get('time', '')
                                })
                
                if all_items:
                    df_commodity = pd.DataFrame(all_items)
                    
                    important_commodities = ['نفت برنت', 'مس', 'آلومینیوم', 'روی', 'سرب', 'نیکل']
                    cols = st.columns(min(len(important_commodities), 6))
                    for i, comp_name in enumerate(important_commodities):
                        if i < len(cols):
                            item_data = next((item for item in all_items if item['name'] == comp_name), None)
                            if item_data:
                                with cols[i]:
                                    st.metric(
                                        label=item_data['name'],
                                        value=f"{format_numbers(item_data['price'], 'price')} {item_data['unit']}",
                                        delta=f"{item_data['change_percent_num']:+.2f}%",
                                        help=f"تغییر ارزش: {item_data['change_value']} {item_data['unit']}"
                                    )
                    
                    columns_to_show = ['name', 'price', 'unit', 'change_value', 'change_percent', 'date', 'time']
                    existing_columns = [col for col in columns_to_show if col in df_commodity.columns]
                    df_commodity_display = df_commodity[existing_columns].copy()
                    
                    df_commodity_display['price'] = df_commodity_display.apply(
                        lambda row: format_numbers(row['price'], 'price') if pd.notna(row['price']) else '', axis=1
                    )
                    
                    styled_df = df_commodity_display.style.applymap(
                        color_change, subset=['change_percent', 'change_value']
                    )
                    
                    st.dataframe(styled_df, use_container_width=True, hide_index=True, height=515)
                    
                else:
                    st.warning("هیچ آیتم کامودیتی یافت نشد.")
            else:
                st.error("دریافت داده‌های کامودیتی با مشکل مواجه شد. لطفاً بعداً تلاش کنید.")

        with tab6:
            st.subheader("📜 گواهی‌های سپرده کالایی")
            
            with st.spinner("در حال دریافت داده‌های گواهی‌ها..."):
                certificate_data = fetch_certificate_data_new()
                
                certificates = []
                
                if certificate_data:
                    certificates = process_certificate_data_new(certificate_data)
                
                if certificates:
                    df_certificates = pd.DataFrame(certificates)
                    
                    df_display = df_certificates.copy()
                    
                    df_display['last_price'] = df_display['last_price'].apply(
                        lambda x: f"{x:,.0f}" if isinstance(x, (int, float)) and x > 0 else "0"
                    )
                    df_display['yesterday_price'] = df_display['yesterday_price'].apply(
                        lambda x: f"{x:,.0f}" if isinstance(x, (int, float)) and x > 0 else "0"
                    )
                    
                    df_display['last_price_change'] = df_display['last_price_change'].apply(
                        lambda x: f"{x:+.2f}%" if isinstance(x, (int, float)) else "0.00%"
                    )
                    
                    column_names = {
                        'name': 'نام گواهی',
                        'ticker': 'نماد',
                        'last_price': 'قیمت آخر',
                        'yesterday_price': 'قیمت دیروز',
                        'last_price_change': 'تغییر',
                        'time': 'زمان',
                        'date': 'تاریخ',
                        'type': 'نوع'
                    }
                    df_display = df_display.rename(columns=column_names)
                    
                    display_columns = ['نام گواهی', 'نماد', 'قیمت آخر', 'قیمت دیروز', 'تغییر', 'تاریخ', 'زمان']
                    existing_columns = [col for col in display_columns if col in df_display.columns]
                    df_final = df_display[existing_columns]
                    
                    styled_df = df_final.style.applymap(
                        color_change, subset=['تغییر']
                    )
                    
                    st.dataframe(styled_df, use_container_width=True, hide_index=True)
                    
                else:
                    st.error("❌ هیچ داده‌ای از گواهی‌ها دریافت نشد")

        with tab7:
            st.subheader("🏦 صندوق‌های طلا")
            
            gold_shamsh_dollar = st.session_state.get('gold_shamsh_dollar', None)
            gold_coin_dollar = st.session_state.get('gold_coin_dollar', None)
            silver_dollar_calc = st.session_state.get('silver_dollar', None)
            
            def fetch_funds_from_fipiran():
                url = "https://www.fipiran.com/services/fund/fundcompare"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 OPR/106.0.0.0",
                    "Accept": "application/json, text/plain, */*"
                }
                try:
                    response = requests.get(url, headers=headers, timeout=15)
                    response.raise_for_status()
                    data = response.json()
                    
                    items = data.get("items", [])
                    filtered_items = [item for item in items if item.get("fundType") == 5]
                    
                    return filtered_items
                except Exception as e:
                    st.error(f"خطا در دریافت لیست صندوق‌ها: {e}")
                    return []
            
            def fetch_price_info_from_tsetmc(ins_code):
                url = f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceInfo/{ins_code}"
                try:
                    response = requests.get(url, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    
                    closing_info = data.get("closingPriceInfo", {})
                    
                    trade_price = closing_info.get("pDrCotVal")
                    yesterday_price = closing_info.get("priceYesterday")
                    
                    change_percent = None
                    if trade_price and yesterday_price and yesterday_price > 0:
                        change_percent = ((trade_price / yesterday_price) - 1) * 100
                    
                    return {
                        "pl": trade_price,
                        "pc": closing_info.get("pClosing"),
                        "plp": change_percent,
                        "tval": closing_info.get("qTotCap"),
                        "tno": closing_info.get("zTotTran"),
                        "time": closing_info.get("hEven"),
                        "date": closing_info.get("dEven")
                    }
                except Exception as e:
                    return None
            
            def convert_to_old_format(fund_item, price_info):
                if not price_info:
                    return None
                
                time_str = ""
                h_even = price_info.get("time")
                if h_even and len(str(h_even)) == 6:
                    time_str = f"{str(h_even)[:2]}:{str(h_even)[2:4]}:{str(h_even)[4:6]}"
                
                date_str = ""
                d_even = price_info.get("date")
                if d_even and len(str(d_even)) == 8:
                    greg_date = f"{str(d_even)[:4]}-{str(d_even)[4:6]}-{str(d_even)[6:8]}"
                    date_str = convert_to_shamsi(greg_date)
                
                old_format_data = {
                    "l18": fund_item.get("smallSymbolName", fund_item.get("name", "")),
                    "l30": fund_item.get("name", ""),
                    "insCode": fund_item.get("insCode", ""),
                    "pl": price_info.get("pl", 0),
                    "pc": price_info.get("pc", 0),
                    "plp": price_info.get("plp", 0),
                    "tval": price_info.get("tval", 0),
                    "tno": price_info.get("tno", 0),
                    "time": time_str,
                    "time_update": date_str
                }
                
                return old_format_data
            
            with st.spinner("در حال دریافت داده‌های صندوق‌های طلا..."):
                funds_from_fipiran = fetch_funds_from_fipiran()
                
                if not funds_from_fipiran:
                    st.warning("هیچ صندوقی با fundType=5 پیدا نشد.")
                else:
                    converted_funds = []
                    progress_bar = st.progress(0, text="در حال دریافت اطلاعات قیمت صندوق‌ها...")
                    
                    for idx, fund in enumerate(funds_from_fipiran):
                        ins_code = fund.get("insCode")
                        
                        if ins_code:
                            price_info = fetch_price_info_from_tsetmc(ins_code)
                            if price_info:
                                converted_item = convert_to_old_format(fund, price_info)
                                if converted_item:
                                    converted_funds.append(converted_item)
                        
                        progress_bar.progress((idx + 1) / len(funds_from_fipiran), 
                                            text=f"در حال پردازش {fund.get('name', '')}...")
                    
                    progress_bar.empty()
                    
                    if not converted_funds:
                        st.warning("هیچ اطلاعات قیمتی برای صندوق‌ها دریافت نشد.")
                    else:
                        fund_data = {
                            "successful": True,
                            "data": converted_funds
                        }
                        
                        gold_funds = process_gold_funds_data_with_nav(
                            fund_data, 
                            gold_shamsh_dollar, 
                            gold_coin_dollar, 
                            silver_dollar_calc
                        )
                        
                        if gold_funds:
                            df_funds = pd.DataFrame(gold_funds)
                            
                            df_display = df_funds.copy()
                            
                            df_display['bubble_percent'] = df_display['bubble_percent'].apply(
                                lambda x: f"{x:+.2f}%" if isinstance(x, (int, float)) and x is not None else "-")
                            
                            df_display['last_price'] = df_display['last_price'].apply(
                                lambda x: f"{x:,.0f}" if isinstance(x, (int, float)) and x > 0 else "0"
                            )
                            df_display['adj_price'] = df_display['adj_price'].apply(
                                lambda x: f"{x:,.0f}" if isinstance(x, (int, float)) and x > 0 else "0"
                            )
                            
                            df_display['last_price_change'] = df_display['last_price_change'].apply(
                                lambda x: f"{x:+.2f}%" if isinstance(x, (int, float)) else "0.00%"
                            )
                            
                            column_names = {
                                'name': 'نماد',
                                'last_price': 'قیمت معامله',
                                'adj_price': 'قیمت پایانی',
                                'transaction_value': 'ارزش معاملات',
                                'last_price_change': 'تغییر',
                                'time': 'زمان',
                                'full_name': 'نام کامل',
                                'tno': 'تعداد معاملات',
                                'nav': 'ناو ابطال',
                                'nav_time': 'زمان ناو',
                                'nav_date': 'تاریخ ناو',
                                'bubble_percent': 'حباب',
                                'calculated_fund_dollar': 'دلار محاسباتی',
                                'weight_gold_shamsh': 'وزن شمش (%)',
                                'weight_gold_coin': 'وزن سکه (%)',
                                'weight_silver': 'وزن نقره (%)'
                            }
                            df_display = df_display.rename(columns=column_names)
                            
                            display_columns = ['نماد', 'قیمت معامله', 'قیمت پایانی', 'تغییر', 'حباب', 'دلار محاسباتی', 'ناو ابطال', 'وزن شمش (%)', 'وزن سکه (%)', 'وزن نقره (%)', 'ارزش معاملات', 'تاریخ ناو', 'زمان ناو', 'زمان']
                            existing_columns = [col for col in display_columns if col in df_display.columns]
                            df_final = df_display[existing_columns]
                            
                            styled_df = df_final.style.applymap(
                                color_change, subset=['تغییر', 'حباب']
                            )
                            
                            st.dataframe(styled_df, use_container_width=True, hide_index=True, height=600)
                            
                            if converted_funds and len(converted_funds) > 0:
                                last_update = converted_funds[0].get('time_update', 'نامشخص')
                                st.caption(f"🕒 آخرین بروزرسانی داده: {last_update}")
                            
                        else:
                            st.warning("هیچ داده معتبری از صندوق‌های طلا یافت نشد (تمام نمادها فیلتر شدند)")   


        with tab8:
            st.subheader("📈 قراردادهای آتی طلا")
            
            with st.spinner("در حال دریافت داده‌های آتی طلا..."):
                future_data = fetch_future_gold_data()
                
                if future_data:
                    future_items = process_future_gold_data(future_data)
                    
                    if future_items:
                        # دریافت قیمت گواهی سپرده پیوسته شمش طلای +995 از تب طلا
                        gold_certificate_price = None
                        if 'gold_data' in st.session_state:
                            for item in st.session_state.gold_data:
                                if item.get('name') == 'گواهی سپرده پیوسته شمش طلای +995':
                                    gold_certificate_price = item.get('price', 0)
                                    break
                        
                        # دریافت قیمت انس طلا از تب طلا
                        ounce_price = None
                        if 'gold_data' in st.session_state:
                            for item in st.session_state.gold_data:
                                if item.get('name') == 'انس طلا':
                                    ounce_price = item.get('price', 0)
                                    break
                        
                        # محاسبه فاصله با قیمت اصلی و دلار محاسباتی برای قراردادهای آتی شمش طلا
                        for item in future_items:
                            contract_name = item.get('name', '')
                            
                            # فقط برای قراردادهایی که با "قرارداد آتی شمش طلای خام 995" شروع می‌شوند
                            if contract_name.startswith('قرارداد آتی شمش طلای خام 995'):
                                # انتخاب قیمت مناسب (اگر قیمت آخر صفر بود از قیمت دیروز استفاده کن)
                                contract_price = item.get('last_price', 0)
                                if contract_price == 0:
                                    contract_price = item.get('yesterday_price', 0)
                                
                                # محاسبه درصد اختلاف با گواهی
                                if gold_certificate_price and gold_certificate_price > 0 and contract_price > 0:
                                    price_diff_percent = (((contract_price/10) / gold_certificate_price) - 1) * 100
                                    item['price_distance'] = price_diff_percent
                                else:
                                    item['price_distance'] = None
                                
                                # محاسبه دلار محاسباتی
                                if ounce_price and ounce_price > 0 and contract_price > 0:
                                    calculated_dollar = contract_price / (ounce_price / 31.1)
                                    item['calculated_dollar'] = calculated_dollar
                                else:
                                    item['calculated_dollar'] = None
                            else:
                                item['price_distance'] = None
                                item['calculated_dollar'] = None
                        
                        df_future = pd.DataFrame(future_items)
                        
                        # آماده‌سازی دیتافریم برای نمایش
                        df_display = df_future.copy()
                        
                        # فرمت کردن اعداد
                        df_display['last_price'] = df_display['last_price'].apply(
                            lambda x: f"{x:,.0f}" if isinstance(x, (int, float)) and x > 0 else "0"
                        )
                        df_display['yesterday_price'] = df_display['yesterday_price'].apply(
                            lambda x: f"{x:,.0f}" if isinstance(x, (int, float)) and x > 0 else "0"
                        )
                        df_display['change_percent'] = df_display['change_percent'].apply(
                            lambda x: f"{x:+.2f}%" if isinstance(x, (int, float)) else "0.00%"
                        )
                        
                        # فرمت کردن ستون فاصله با قیمت اصلی
                        def format_price_distance(x):
                            if x is None:
                                return "-"
                            if isinstance(x, (int, float)) and pd.notna(x):
                                return f"{x:+.2f}%"
                            return "-"
                        
                        df_display['price_distance'] = df_display['price_distance'].apply(format_price_distance)
                        
                        # فرمت کردن ستون دلار محاسباتی
                        def format_calculated_dollar(x):
                            if x is None:
                                return "-"
                            if isinstance(x, (int, float)) and pd.notna(x) and x > 0:
                                return f"{x:,.0f}"
                            return "-"
                        
                        df_display['calculated_dollar'] = df_display['calculated_dollar'].apply(format_calculated_dollar)
                        
                        # نام‌گذاری ستون‌ها
                        column_names = {
                            'name': 'نام قرارداد',
                            'last_price': 'قیمت آخر',
                            'yesterday_price': 'قیمت دیروز',
                            'change_percent': 'تغییر',
                            'trade_date': 'تاریخ سررسید',
                            'calculated_dollar': 'دلار محاسباتی',
                            'price_distance': 'فاصله با قیمت اصلی',
                            'last_update': 'تاریخ'
                        }
                        df_display = df_display.rename(columns=column_names)
                        
                        # ترتیب ستون‌ها
                        display_columns = ['نام قرارداد', 'قیمت آخر', 'قیمت دیروز', 'تغییر', 
                                        'تاریخ سررسید', 'دلار محاسباتی', 'فاصله با قیمت اصلی', 'تاریخ']
                        existing_columns = [col for col in display_columns if col in df_display.columns]
                        df_final = df_display[existing_columns]
                        
                        # استایل دهی
                        styled_df = df_final.style.applymap(
                            lambda x: 'color: green; font-weight: bold;' if isinstance(x, str) and x.startswith('+') 
                            else ('color: red; font-weight: bold;' if isinstance(x, str) and x.startswith('-') else ''),
                            subset=['تغییر', 'فاصله با قیمت اصلی']
                        )
                        
                        st.dataframe(styled_df, use_container_width=True, hide_index=True)
                        
                    else:
                        st.warning("هیچ قرارداد آتی مرتبط با طلا یافت نشد.")
                else:
                    st.error("❌ خطا در دریافت داده‌های آتی طلا. لطفاً بعداً تلاش کنید.")

except Exception as e:
    st.error(f"❌ خطای غیرمنتظره: {e}")
    st.write("داده دریافتی برای دیباگ:")
    if 'market_data' in st.session_state:
        st.json(st.session_state.market_data)
