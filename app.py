import os
import json
import re
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote

# --- 網頁與手機版面設定 ---
st.set_page_config(page_title="台美股戰略追蹤 App Ver. 9", page_icon="📱", layout="wide")

# --- 全域 CSS：隱藏輸入框提示字、防止下拉選單觸發手機鍵盤 ---
st.markdown(
    """
    <style>
    div[data-testid="InputInstructions"] {
        display: none !important;
        visibility: hidden !important;
    }
    div[data-baseweb="select"],
    div[data-baseweb="select"] > div {
        cursor: pointer !important;
    }
    div[data-baseweb="select"] input {
        caret-color: transparent !important;
        pointer-events: none !important;
        user-select: none !important;
        -webkit-user-select: none !important;
        width: 1px !important;
        opacity: 0 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 防彈鍵盤鎖：封鎖手機鍵盤彈出 ---
components.html(
    """
    <script>
    (function() {
        try {
            const pWin = window.parent;
            const pDoc = pWin.document;

            function makeSelectReadOnly() {
                try {
                    const inputs = pDoc.querySelectorAll('div[data-baseweb="select"] input');
                    inputs.forEach(inp => {
                        inp.disabled = false;
                        inp.removeAttribute('disabled');
                        inp.style.removeProperty('display');
                        inp.style.removeProperty('visibility');
                        inp.readOnly = true;
                        inp.setAttribute('readonly', 'readonly');
                        inp.setAttribute('inputmode', 'none');
                        inp.setAttribute('tabindex', '-1');
                    });
                } catch (e) {}
            }

            if (!pWin._ver9FocusPatched) {
                const origElemFocus = pWin.HTMLElement.prototype.focus;
                function patchedFocus() {
                    try {
                        if (this && this.tagName === 'INPUT' && this.closest && this.closest('div[data-baseweb="select"]')) {
                            this.readOnly = true;
                            this.setAttribute('readonly', 'readonly');
                            this.setAttribute('inputmode', 'none');
                            return;
                        }
                    } catch (e) {}
                    return origElemFocus.apply(this, arguments);
                }
                pWin.HTMLInputElement.prototype.focus = patchedFocus;
                pWin.HTMLElement.prototype.focus = patchedFocus;
                pWin._ver9FocusPatched = true;
            }

            ['touchstart', 'pointerdown', 'mousedown'].forEach(evtName => {
                pDoc.addEventListener(evtName, makeSelectReadOnly, {capture: true, passive: true});
            });

            makeSelectReadOnly();
            setInterval(makeSelectReadOnly, 150);
        } catch (err) {}
    })();
    </script>
    """,
    height=1,
)

# --- 預設股票清單 (標準模板格式) ---
DEFAULT_STOCKS = {
    "AMD": "AMD (超微 AI GPU/伺服器CPU)",
    "ASTS": "ASTS (低軌衛星直連 D2D)",
    "BE": "BE (Bloom Energy 燃料電池)",
    "COHR": "COHR (Coherent 光通訊/SiC)",
    "CRDO": "CRDO (Credo 高速傳輸 AEC)",
    "GLW": "GLW (康寧 光纖/玻璃基板)",
    "GOOG": "GOOG (Alphabet 科技巨頭)",
    "NOK": "NOK (諾基亞 AI-RAN/光網路)",
    "NVTS": "NVTS (納微 800V GaN/SiC)",
    "ON": "ON (安森美 車用/功率半導體)",
    "1303.TW": "1303 南亞 (塑化/電子材料)",
    "2313.TW": "2313 華通 (低軌衛星/高階HDI板)",
    "2330.TW": "2330 台積電 (先進製程/CoWoS龍頭)",
    "2408.TW": "2408 南亞科 (DRAM記憶體製造)",
    "3037.TW": "3037 欣興 (ABF載板/AI伺服器)",
    "3491.TWO": "3491 昇達科 (低軌衛星元件)",
    "3714.TW": "3714 富采 (Micro LED/CPO光源)",
    "4540.TW": "4540 全球傳動 (機器人滾珠螺桿)",
    "4576.TW": "4576 大銀微系統 (精密運動控制)",
    "6127.TWO": "6127 九豪 (氧化鋁陶瓷基板)",
    "6271.TW": "6271 同欣電 (CIS/高頻模組封測)",
    "8027.TWO": "8027 鈦昇 (TGV 玻璃基板設備)"
}

# --- 內建台美股智慧模板庫（加入防呆硬對應，杜絕南亞與南亞科混淆） ---
KNOWN_STOCK_PROFILES = {
    "1303": ("1303.TW", "1303 南亞 (塑化/電子材料)"),
    "南亞": ("1303.TW", "1303 南亞 (塑化/電子材料)"),
    "2313": ("2313.TW", "2313 華通 (低軌衛星/高階HDI板)"),
    "華通": ("2313.TW", "2313 華通 (低軌衛星/高階HDI板)"),
    "2330": ("2330.TW", "2330 台積電 (先進製程/CoWoS龍頭)"),
    "台積電": ("2330.TW", "2330 台積電 (先進製程/CoWoS龍頭)"),
    "2408": ("2408.TW", "2408 南亞科 (DRAM記憶體製造)"),
    "南亞科": ("2408.TW", "2408 南亞科 (DRAM記憶體製造)"),
    "2454": ("2454.TW", "2454 聯發科 (IC設計/邊緣AI晶片)"),
    "聯發科": ("2454.TW", "2454 聯發科 (IC設計/邊緣AI晶片)"),
    "2317": ("2317.TW", "2317 鴻海 (AI伺服器機櫃龍頭)"),
    "鴻海": ("2317.TW", "2317 鴻海 (AI伺服器機櫃龍頭)"),
    "2308": ("2308.TW", "2308 台達電 (AI伺服器電源/散熱)"),
    "台達電": ("2308.TW", "2308 台達電 (AI伺服器電源/散熱)"),
    "3037": ("3037.TW", "3037 欣興 (ABF載板/AI伺服器)"),
    "欣興": ("3037.TW", "3037 欣興 (ABF載板/AI伺服器)"),
    "3491": ("3491.TWO", "3491 昇達科 (低軌衛星元件)"),
    "昇達科": ("3491.TWO", "3491 昇達科 (低軌衛星元件)"),
    "AMD": ("AMD", "AMD (超微 AI GPU/伺服器CPU)"),
    "NVDA": ("NVDA", "NVDA (NVIDIA AI算力晶片霸主)"),
    "TSLA": ("TSLA", "TSLA (特斯拉 電動車/FSD/機器人)"),
    "AVGO": ("AVGO", "AVGO (博通 AI網路晶片/CPO霸主)")
}

@st.cache_data(ttl=86400)
def load_tw_stock_directory():
    try:
        url = "https://api.finmindtrade.com/api/v4/data"
        resp = requests.get(url, params={"dataset": "TaiwanStockInfo"}, timeout=8)
        data = resp.json().get("data", [])
        if data:
            df = pd.DataFrame(data)
            df = df[df["stock_id"].str.match(r"^\d{4}$", na=False)]
            df = df.drop_duplicates(subset=["stock_id"], keep="first")
            return df
    except Exception:
        pass
    return pd.DataFrame()

def auto_format_stock_entry(raw_input_str):
    text = raw_input_str.strip()
    if not text:
        return "", ""

    # 防呆第一道：精確比對智慧庫（杜絕南亞與南亞科混淆）
    clean_query = text.replace(".TW", "").replace(".TWO", "").strip()
    if clean_query.upper() in KNOWN_STOCK_PROFILES:
        return KNOWN_STOCK_PROFILES[clean_query.upper()]
    if clean_query in KNOWN_STOCK_PROFILES:
        return KNOWN_STOCK_PROFILES[clean_query]

    tw_dir = load_tw_stock_directory()

    # 中文名稱或代號對應
    if not tw_dir.empty:
        exact_match = tw_dir[(tw_dir["stock_id"] == clean_query) | (tw_dir["stock_name"] == clean_query)]
        if not exact_match.empty:
            r = exact_match.iloc[0]
            sid = r["stock_id"]
            if sid in KNOWN_STOCK_PROFILES:
                return KNOWN_STOCK_PROFILES[sid]
            sfx = ".TWO" if r.get("type") == "tpex" else ".TW"
            return f"{sid}{sfx}", f"{sid} {r['stock_name']} ({r.get('industry_category', '台股標的')})"

    match = re.match(r"^([A-Za-z0-9\.]+)\s*(.*)$", text)
    if match:
        code_raw = match.group(1).upper()
        user_note = match.group(2).strip()
    else:
        code_raw = ""
        user_note = text

    base_code = code_raw.replace(".TW", "").replace(".TWO", "")
    if base_code.isdigit() and len(base_code) == 4:
        if base_code in KNOWN_STOCK_PROFILES:
            return KNOWN_STOCK_PROFILES[base_code]
        return f"{base_code}.TW", f"{base_code} {user_note or '台股標的'} (台股自選)"

    full_ticker = code_raw if code_raw else text.upper()
    try:
        info = yf.Ticker(full_ticker).info or {}
        short_name = info.get("shortName", "").split(",")[0].split(" Inc")[0].strip()
        sector = info.get("industry") or info.get("sector") or "美股標的"
        if short_name:
            return full_ticker, f"{full_ticker} ({short_name} / {sector})"
    except Exception:
        pass
    return full_ticker, f"{full_ticker} (美股自選標的)"

def get_sorted_watchlist_keys(wl_dict):
    def sort_key(tk):
        base = tk.split(".")[0].strip()
        if base.isdigit():
            return (1, int(base), base)
        elif base and base[0].isalpha():
            return (0, 0, base.upper())
        else:
            return (2, 0, base)
    return sorted(wl_dict.keys(), key=sort_key)

def sort_portfolio_df(df):
    if df.empty or "代號" not in df.columns:
        return df
    df_copy = df.copy()
    df_copy["_sort_key"] = df_copy["代號"].astype(str).str.strip().str.upper()
    df_copy = df_copy.sort_values(by="_sort_key", ascending=True).drop(columns=["_sort_key"]).reset_index(drop=True)
    return df_copy

SEARCH_KEYWORDS = {
    "AMD": "AMD 超微",
    "ASTS": "AST SpaceMobile OR ASTS",
    "BE": "Bloom Energy",
    "COHR": "Coherent COHR",
    "CRDO": "Credo Technology CRDO",
    "GLW": "Corning GLW 康寧",
    "GOOG": "Alphabet Google GOOG",
    "ON": "ON Semiconductor 安森美",
    "NOK": "Nokia 諾基亞",
    "NVTS": "Navitas NVTS 納微",
    "1303.TW": "南亞",
    "2313.TW": "華通",
    "2330.TW": "台積電",
    "2408.TW": "南亞科",
    "3037.TW": "欣興",
    "3491.TWO": "昇達科",
    "8027.TWO": "鈦昇",
    "6271.TW": "同欣電"
}

FALLBACK_FINANCIALS = {
    "1303.TW": {"rev_growth": 5.2, "gm": 12.5, "om": 3.1, "nm": 4.2, "roe": 4.8, "cr": 1.45, "qr": 1.12, "de": 65.0, "target": "塑化/電子材料", "f_pe": 18.5},
    "2313.TW": {"rev_growth": 18.5, "gm": 19.8, "om": 11.2, "nm": 8.9, "roe": 14.5, "cr": 1.85, "qr": 1.35, "de": 42.0, "target": "低軌衛星主力", "f_pe": 16.5},
    "2330.TW": {"rev_growth": 36.5, "gm": 57.8, "om": 47.5, "nm": 42.1, "roe": 31.8, "cr": 2.45, "qr": 2.15, "de": 21.0, "target": 1500.0, "f_pe": 22.5},
    "2408.TW": {"rev_growth": 28.4, "gm": 15.2, "om": 4.5, "nm": 3.8, "roe": 4.2, "cr": 2.90, "qr": 2.10, "de": 18.5, "target": "DRAM復甦觀察", "f_pe": 26.0},
    "3037.TW": {"rev_growth": 24.45, "gm": 17.96, "om": 8.5, "nm": 6.8, "roe": 9.2, "cr": 1.75, "qr": 1.40, "de": 45.0, "target": 965.0, "f_pe": 28.0},
    "AMD":  {"rev_growth": 28.0, "gm": 53.5, "om": 21.0, "nm": 16.5, "roe": 12.4, "cr": 2.50, "qr": 1.90, "de": 4.5, "target": 220.0, "f_pe": 29.5},
    "CRDO": {"rev_growth": 68.5, "gm": 68.8, "om": 22.4, "nm": 20.1, "roe": 16.5, "cr": 5.8, "qr": 5.1, "de": 3.2, "target": 215.0, "f_pe": 45.2},
    "NVTS": {"rev_growth": -18.5, "gm": 38.12, "om": -269.3, "nm": -856.9, "roe": -52.6, "cr": 21.79, "qr": 20.34, "de": 0.64, "target": 15.0, "f_pe": "尚未獲利(轉機期)"},
    "NOK":  {"rev_growth": 12.4, "gm": 44.23, "om": 3.27, "nm": 2.8, "roe": 3.46, "cr": 1.51, "qr": 1.22, "de": 15.85, "target": 12.5, "f_pe": 14.8},
    "ASTS": {"rev_growth": 145.0, "gm": 38.91, "om": -410.26, "nm": -450.0, "roe": -44.82, "cr": 13.05, "qr": 12.39, "de": 158.06, "target": 65.0, "f_pe": "商轉初期(無P/E)"},
    "GLW":  {"rev_growth": 18.2, "gm": 37.8, "om": 16.5, "nm": 12.1, "roe": 15.4, "cr": 1.65, "qr": 1.15, "de": 68.0, "target": 165.0, "f_pe": 22.5},
    "GOOG": {"rev_growth": 15.1, "gm": 58.2, "om": 32.5, "nm": 27.8, "roe": 31.2, "cr": 2.05, "qr": 1.95, "de": 8.5, "target": 380.0, "f_pe": 24.1},
    "ON":   {"rev_growth": 8.5, "gm": 37.72, "om": 18.05, "nm": 10.17, "roe": 8.31, "cr": 3.46, "qr": 2.27, "de": 62.10, "target": 85.0, "f_pe": 16.8},
    "COHR": {"rev_growth": 24.6, "gm": 39.2, "om": 12.8, "nm": 6.5, "roe": 7.8, "cr": 2.35, "qr": 1.55, "de": 58.4, "target": 310.0, "f_pe": 28.5},
    "BE":   {"rev_growth": 31.0, "gm": 31.5, "om": 8.2, "nm": 4.5, "roe": 14.2, "cr": 2.10, "qr": 1.45, "de": 115.0, "target": 275.0, "f_pe": 32.0},
    "3491.TWO": {"rev_growth": 48.5, "gm": 52.3, "om": 26.8, "nm": 21.5, "roe": 24.6, "cr": 2.85, "qr": 2.10, "de": 22.0, "target": "法人看多", "f_pe": 35.0},
    "8027.TWO": {"rev_growth": 32.4, "gm": 34.5, "om": 6.2, "nm": 4.8, "roe": 8.5, "cr": 2.40, "qr": 1.75, "de": 35.0, "target": "訂單至2027", "f_pe": 42.0},
    "6271.TW":  {"rev_growth": 12.8, "gm": 28.6, "om": 14.5, "nm": 11.8, "roe": 10.2, "cr": 2.60, "qr": 2.15, "de": 28.5, "target": "穩健獲利", "f_pe": 19.5}
}

PORTFOLIO_FILE = "portfolio_saved.csv"
WATCHLIST_FILE = "watchlist_saved.json"

if "watchlist" not in st.session_state:
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                saved_wl = json.load(f)
            upgraded_wl = {}
            for k, v in saved_wl.items():
                if k in DEFAULT_STOCKS:
                    upgraded_wl[k] = DEFAULT_STOCKS[k]
                else:
                    new_k, new_v = auto_format_stock_entry(k)
                    if new_k:
                        upgraded_wl[new_k] = new_v
            if "2330.TW" not in upgraded_wl:
                upgraded_wl["2330.TW"] = DEFAULT_STOCKS["2330.TW"]
            st.session_state.watchlist = upgraded_wl
        except Exception:
            st.session_state.watchlist = DEFAULT_STOCKS.copy()
    else:
        st.session_state.watchlist = DEFAULT_STOCKS.copy()

def save_watchlist():
    try:
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(st.session_state.watchlist, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

DEFAULT_PF = [
    {"代號": "ASTS", "持股數": 140.0, "平均成本": 60.05, "前日收盤價": 0.0, "防守埋伏價(GTC)": 40.0},
    {"代號": "BE",   "持股數": 11.0,  "平均成本": 245.91, "前日收盤價": 0.0, "防守埋伏價(GTC)": 220.0},
    {"代號": "COHR", "持股數": 30.0,  "平均成本": 282.67, "前日收盤價": 0.0, "防守埋伏價(GTC)": 250.0},
    {"代號": "CRDO", "持股數": 54.0,  "平均成本": 179.32, "前日收盤價": 0.0, "防守埋伏價(GTC)": 160.0},
    {"代號": "GLW",  "持股數": 65.0,  "平均成本": 163.46, "前日收盤價": 0.0, "防守埋伏價(GTC)": 140.0},
    {"代號": "GOOG", "持股數": 157.0, "平均成本": 0.0,    "前日收盤價": 0.0, "防守埋伏價(GTC)": 310.0},
    {"代號": "NOK",  "持股數": 900.0, "平均成本": 11.88,  "前日收盤價": 0.0, "防守埋伏價(GTC)": 8.5},
    {"代號": "NVTS", "持股數": 850.0, "平均成本": 14.51,  "前日收盤價": 0.0, "防守埋伏價(GTC)": 9.5},
    {"代號": "ON",   "持股數": 130.0, "平均成本": 76.12,  "前日收盤價": 0.0, "防守埋伏價(GTC)": 68.0},
]

if "portfolio_df" not in st.session_state:
    if os.path.exists(PORTFOLIO_FILE):
        try:
            loaded_pf = pd.read_csv(PORTFOLIO_FILE)
            if "前日收盤價" not in loaded_pf.columns:
                loaded_pf.insert(3, "前日收盤價", 0.0)
            st.session_state.portfolio_df = sort_portfolio_df(loaded_pf)
        except Exception:
            st.session_state.portfolio_df = sort_portfolio_df(pd.DataFrame(DEFAULT_PF))
    else:
        st.session_state.portfolio_df = sort_portfolio_df(pd.DataFrame(DEFAULT_PF))

@st.cache_data(ttl=1800)
def fetch_stock_history(ticker, period="2y", interval="1d"):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period, interval=interval)
        if hist.empty and ticker.endswith(".TW"):
            alt_ticker = ticker.replace(".TW", ".TWO")
            hist = yf.Ticker(alt_ticker).history(period=period, interval=interval)
        return hist
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_comprehensive_financials(ticker):
    fb = FALLBACK_FINANCIALS.get(ticker, {
        "rev_growth": 10.0, "gm": 30.0, "om": 10.0, "nm": 8.0,
        "roe": 10.0, "cr": 2.0, "qr": 1.5, "de": 30.0, "target": "無資料", "f_pe": "無資料"
    }).copy()
    inc, bal, inst = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    try:
        stock = yf.Ticker(ticker)
        try: inc = stock.quarterly_income_stmt
        except Exception: pass
        try: bal = stock.quarterly_balance_sheet
        except Exception: pass
        try: inst = stock.institutional_holders
        except Exception: pass
    except Exception:
        pass
    return fb, inc, bal, inst

@st.cache_data(ttl=3600)
def fetch_tw_monthly_revenue(ticker):
    if not (ticker.endswith(".TW") or ticker.endswith(".TWO")):
        return pd.DataFrame()
    stock_id = ticker.split(".")[0]
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {"dataset": "TaiwanStockMonthRevenue", "data_id": stock_id, "start_date": "2025-01-01"}
    try:
        resp = requests.get(url, params=params, timeout=6)
        data = resp.json()
        if data.get("msg") == "success" and data.get("data"):
            df = pd.DataFrame(data["data"])
            df["年月"] = df["revenue_year"].astype(str) + "-" + df["revenue_month"].astype(str).str.zfill(2)
            df["月營收(億)"] = (df["revenue"] / 1e8).round(3)
            return df[["年月", "月營收(億)"]].tail(12)
    except Exception:
        pass
    return pd.DataFrame()

@st.cache_data(ttl=1800)
def fetch_google_news(query_str, max_items=12):
    encoded_q = quote(query_str)
    url = f"https://news.google.com/rss/search?q={encoded_q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    items = []
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            for item in root.findall(".//item")[:max_items]:
                title = item.find("title").text if item.find("title") is not None else ""
                link = item.find("link").text if item.find("link") is not None else ""
                pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                items.append({"title": title, "link": link, "pubDate": pub_date[:16]})
    except Exception:
        pass
    return items

def classify_news_sentiment(title):
    lawsuit_kw = ["訴訟", "官司", "專利", "侵權", "法院", "裁決", "和解", "調查", "SEC", "FERC", "lawsuit", "litigation", "court", "sued"]
    bull_kw = ["大漲", "創高", "新高", "獲利", "超預期", "大單", "追單", "擴產", "入股", "合作", "買超", "加碼", "轉盈", "成長", "調升", "突破"]
    bear_kw = ["大跌", "重挫", "虧損", "砍單", "延後", "遞延", "利空", "賣超", "減碼", "清倉", "下修", "跌破", "增資", "稀釋", "警告"]
    for kw in lawsuit_kw:
        if kw.lower() in title.lower():
            return "⚖️ 訴訟/監管"
    for kw in bull_kw:
        if kw in title:
            return "🟢 利多消息"
    for kw in bear_kw:
        if kw in title:
            return "🔴 利空警示"
    return "🟡 產業/題材觀察"

# --- 主畫面標題與 Ver. 9 ---
st.title("📊 台美股戰略追蹤儀表板 Ver. 9")

if "flash_success_msg" in st.session_state and st.session_state.flash_success_msg:
    st.success(st.session_state.flash_success_msg)
    st.sidebar.success(st.session_state.flash_success_msg)
    st.session_state.flash_success_msg = ""

ticker_options = get_sorted_watchlist_keys(st.session_state.watchlist)
if "selected_ticker_key" not in st.session_state or st.session_state.selected_ticker_key not in ticker_options:
    st.session_state.selected_ticker_key = ticker_options[0]

selected_ticker = st.session_state.selected_ticker_key
current_stock_label = st.session_state.watchlist.get(selected_ticker, selected_ticker)

st.caption("📌 目前檢視標的（點擊下方整條選單即可直接切換個股，0 打字框設計、絕不彈出手機鍵盤）：")

with st.expander(f"📈 {current_stock_label}", expanded=False):
    for tk in ticker_options:
        item_label = st.session_state.watchlist.get(tk, tk)
        prefix_icon = "✅ " if tk == selected_ticker else "  "
        if st.button(f"{prefix_icon}{item_label}", key=f"picker_btn_{tk}", use_container_width=True):
            st.session_state.selected_ticker_key = tk
            st.rerun()

# --- 側邊欄：新增 / 刪除自選股 (加入防手殘預覽機制) ---
st.sidebar.header("➕ 新增 / ➖ 刪除自選股")
if "input_reset_counter" not in st.session_state:
    st.session_state.input_reset_counter = 0

raw_input = st.sidebar.text_input(
    "輸入「代號」或「中文股名」皆可自動配對",
    placeholder="例: 南亞 或 1303 或 AMD",
    key=f"stock_input_{st.session_state.input_reset_counter}"
)

# 預覽確認機制的暫存狀態
if "pending_add_stock" not in st.session_state:
    st.session_state.pending_add_stock = None

if st.sidebar.button("➕ 確認新增股票", use_container_width=True):
    if raw_input.strip():
        code_clean, formatted_label = auto_format_stock_entry(raw_input)
        st.session_state.pending_add_stock = (code_clean, formatted_label)
    else:
        st.sidebar.warning("⚠️ 請先在上方框框輸入股票名稱或代號喔！")

# 若有待確認的新增項目，跳出防呆確認橫幅
if st.session_state.pending_add_stock:
    c_code, c_label = st.session_state.pending_add_stock
    st.sidebar.markdown(f"> ⚠️ **請確認是否新增：**\n> `🔮 {c_label}`")
    col_y, col_n = st.sidebar.columns(2)
    with col_y:
        if st.button("✅ 確定加入", use_container_width=True):
            st.session_state.watchlist[c_code] = c_label
            st.session_state.selected_ticker_key = c_code
            st.session_state.input_reset_counter += 1
            st.session_state.pending_add_stock = None
            save_watchlist()
            st.session_state.flash_success_msg = f"✅ 已成功新增：{c_label}"
            st.rerun()
    with col_n:
        if st.button("❌ 取消", use_container_width=True):
            st.session_state.pending_add_stock = None
            st.rerun()

if st.sidebar.button("➖ 刪除目前檢視的股票", use_container_width=True):
    if len(st.session_state.watchlist) > 1:
        removed_name = st.session_state.watchlist.pop(selected_ticker, selected_ticker)
        sorted_remaining = get_sorted_watchlist_keys(st.session_state.watchlist)
        st.session_state.selected_ticker_key = sorted_remaining[0]
        save_watchlist()
        st.session_state.flash_success_msg = f"🗑️ 已從清單移除：{removed_name}"
        st.rerun()

# 建立五大核心功能分頁
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 1.總覽與部位",
    "📈 2.技術線型",
    "💰 3.財報與訂單",
    "🏦 4.13F與籌碼",
    "⚖️ 5.訴訟與多空雷達"
])

# ==========================================
# 分頁 1：總覽與部位管理
# ==========================================
with tab1:
    latest_close_map = {}
    summary_rows = []
    with st.spinner("正在同步台美股最新報價與均線位階..."):
        for tk in ticker_options:
            name = st.session_state.watchlist[tk]
            df_h = fetch_stock_history(tk, period="1y", interval="1d")
            if not df_h.empty and len(df_h) >= 2:
                close_p = float(df_h["Close"].iloc[-1])
                prev_p = float(df_h["Close"].iloc[-2])
                latest_close_map[tk] = round(close_p, 2)
                latest_close_map[tk.split(".")[0]] = round(close_p, 2)
                chg_pct = ((close_p - prev_p) / prev_p) * 100
                ma20 = float(df_h["Close"].rolling(20).mean().iloc[-1]) if len(df_h) >= 20 else close_p
                ma60 = float(df_h["Close"].rolling(60).mean().iloc[-1]) if len(df_h) >= 60 else close_p
                if close_p >= ma20 and ma20 >= ma60:
                    status = "🟢 站上月/季線 (多頭)"
                elif close_p < ma20 and close_p >= ma60:
                    status = "🟡 跌破月線、守季線"
                else:
                    status = "🔴 跌破季線 (弱勢防守)"
                summary_rows.append({
                    "代號": tk,
                    "名稱與賽道": name,
                    "最新股價": round(close_p, 2),
                    "單日漲跌(%)": f"{chg_pct:+.2f}%",
                    "月線(20MA)": round(ma20, 2),
                    "季線(60MA)": round(ma60, 2),
                    "技術位階判讀": status
                })

    st.subheader("💼 個人持倉成本與 GTC 守株待兔防守座標")
    st.caption("💡 已自動依代號 **A 到 Z** 排序並填入 **前日收盤價**（最左側「代號」已凍結固定，往右滑動也不會消失）：")

    pf_current = sort_portfolio_df(st.session_state.portfolio_df)
    if "前日收盤價" not in pf_current.columns:
        pf_current.insert(3, "前日收盤價", 0.0)

    for idx, row in pf_current.iterrows():
        tk_code = str(row["代號"]).strip().upper()
        if tk_code in latest_close_map:
            pf_current.at[idx, "前日收盤價"] = latest_close_map[tk_code]
        else:
            df_tmp = fetch_stock_history(tk_code, period="5d", interval="1d")
            if not df_tmp.empty:
                pf_current.at[idx, "前日收盤價"] = round(float(df_tmp["Close"].iloc[-1]), 2)

    cols_order = ["代號", "持股數", "平均成本", "前日收盤價", "防守埋伏價(GTC)"]
    pf_current = pf_current[[c for c in cols_order if c in pf_current.columns]]
    st.session_state.portfolio_df = pf_current

    with st.form("portfolio_edit_form"):
        edited_pf = st.data_editor(
            st.session_state.portfolio_df,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "代號": st.column_config.TextColumn("代號", pinned=True, width="small"),
                "持股數": st.column_config.NumberColumn("持股數", format="%.0f"),
                "平均成本": st.column_config.NumberColumn("平均成本", format="%.2f"),
                "前日收盤價": st.column_config.NumberColumn("前日收盤價", format="%.2f", disabled=True),
                "防守埋伏價(GTC)": st.column_config.NumberColumn("防守埋伏價(GTC)", format="%.2f"),
            }
        )
        save_btn = st.form_submit_button("💾 確認儲存修改 (自動依 A-Z 排序)", use_container_width=True)
        if save_btn:
            sorted_edited = sort_portfolio_df(edited_pf)
            st.session_state.portfolio_df = sorted_edited.copy()
            try:
                sorted_edited.to_csv(PORTFOLIO_FILE, index=False)
            except Exception:
                pass
            st.success("✅ 持股與成本已成功儲存並依 A-Z 排序！")
            st.rerun()

    st.markdown("---")
    st.subheader("🌐 自選股今日行情與均線結構掃描")
    if summary_rows:
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

# ==========================================
# 分頁 2：技術線型
# ==========================================
with tab2:
    st.subheader(f"📈 {current_stock_label}")

    ALL_MA_OPTIONS = ["5MA", "10MA", "20MA", "60MA", "120MA", "240MA"]

    col_t1, col_t2 = st.columns([1, 2])
    with col_t1:
        tf_choice = st.radio("選擇 K 線週期：", ["日K線 (預設看近2個月，可往左滑)", "週K線 (3年)", "60分K線 (近1個月)"], horizontal=True)
    with col_t2:
        ma_selected = st.multiselect(
            "勾選要【新增/刪除】的均線 (預設全開)：",
            options=ALL_MA_OPTIONS,
            default=ALL_MA_OPTIONS
        )

    sub_indicators = st.multiselect(
        "勾選要【新增/刪除】的副圖指標：",
        options=["成交量 (Volume)", "KD 指標", "MACD 指標"],
        default=["成交量 (Volume)", "KD 指標"]
    )

    if "日K線" in tf_choice:
        df_raw = fetch_stock_history(selected_ticker, period="2y", interval="1d")
        date_fmt = "%m/%d"
        plot_tail_bars = 220
        default_bars = 43
    elif "週K線" in tf_choice:
        df_raw = fetch_stock_history(selected_ticker, period="5y", interval="1wk")
        date_fmt = "%y/%m/%d"
        plot_tail_bars = 150
        default_bars = 35
    else:
        df_raw = fetch_stock_history(selected_ticker, period="2mo", interval="60m")
        date_fmt = "%m/%d %H:%M"
        plot_tail_bars = 180
        default_bars = 50

    if not df_raw.empty:
        df_calc = df_raw.copy()
        ma_map = {"5MA": 5, "10MA": 10, "20MA": 20, "60MA": 60, "120MA": 120, "240MA": 240}
        ma_colors = {
            "5MA": "#FACC15",
            "10MA": "#38BDF8",
            "20MA": "#C084FC",
            "60MA": "#FB923C",
            "120MA": "#4ADE80",
            "240MA": "#F472B6"
        }

        latest_ma_prices = {}
        for m_label in ALL_MA_OPTIONS:
            win = ma_map[m_label]
            df_calc[m_label] = df_calc["Close"].rolling(window=win).mean()
            val = df_calc[m_label].iloc[-1]
            latest_ma_prices[m_label] = f"{val:.2f}" if pd.notna(val) else "計算中"

        low_min = df_calc["Low"].rolling(9).min()
        high_max = df_calc["High"].rolling(9).max()
        rsv = (df_calc["Close"] - low_min) / (high_max - low_min) * 100
        df_calc["K"] = rsv.ewm(com=2, adjust=False).mean()
        df_calc["D"] = df_calc["K"].ewm(com=2, adjust=False).mean()

        ema12 = df_calc["Close"].ewm(span=12, adjust=False).mean()
        ema26 = df_calc["Close"].ewm(span=26, adjust=False).mean()
        df_calc["DIF"] = ema12 - ema26
        df_calc["MACD"] = df_calc["DIF"].ewm(span=9, adjust=False).mean()
        df_calc["OSC"] = df_calc["DIF"] - df_calc["MACD"]

        df_k = df_calc.tail(plot_tail_bars).copy()
        df_k["DateLabel"] = df_k.index.strftime(date_fmt)
        if df_k["DateLabel"].duplicated().any():
            df_k["DateLabel"] = df_k.index.strftime("%y/%m/%d")

        latest_close = df_k["Close"].iloc[-1]
        k_now = df_k["K"].iloc[-1]
        d_now = df_k["D"].iloc[-1]

        ma_badges_html = [
            f"<span style='color:#FFFFFF; font-weight:700; margin-right:14px; font-size:14px; display:inline-block;'>"
            f"📌 收盤: {latest_close:.2f}</span>"
        ]
        for m_label in ma_selected:
            color = ma_colors[m_label]
            price_str = latest_ma_prices[m_label]
            ma_badges_html.append(
                f"<span style='color:{color}; font-weight:700; margin-right:12px; font-size:14px; display:inline-block;'>"
                f"● {m_label}: {price_str}</span>"
            )
        if "KD 指標" in sub_indicators:
            ma_badges_html.append(
                f"<span style='color:#FACC15; font-weight:600; margin-right:10px; font-size:13px; display:inline-block;'>"
                f"K9: {k_now:.1f}</span>"
                f"<span style='color:#38BDF8; font-weight:600; margin-right:10px; font-size:13px; display:inline-block;'>"
                f"D9: {d_now:.1f}</span>"
            )

        st.markdown(
            f"<div style='background-color:#0B0F19; padding:10px 14px; border-radius:8px; border:1px solid #334155; margin-bottom:6px;'>"
            f"{''.join(ma_badges_html)}</div>",
            unsafe_allow_html=True
        )

        num_rows = 1 + len(sub_indicators)
        row_heights = [0.60] + [0.40 / len(sub_indicators)] * len(sub_indicators) if sub_indicators else [1.0]
        fig = make_subplots(rows=num_rows, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=row_heights)

        fig.add_trace(go.Candlestick(
            x=df_k["DateLabel"],
            open=df_k["Open"], high=df_k["High"], low=df_k["Low"], close=df_k["Close"],
            increasing_line_color="#EF4444", decreasing_line_color="#10B981",
            increasing_fillcolor="#EF4444", decreasing_fillcolor="#10B981",
            increasing_line_width=0.9, decreasing_line_width=0.9,
            name="K線"
        ), row=1, col=1)

        for m_label in ma_selected:
            fig.add_trace(go.Scatter(
                x=df_k["DateLabel"], y=df_k[m_label], mode="lines", name=m_label,
                line=dict(color=ma_colors[m_label], width=1.0)
            ), row=1, col=1)

        curr_row = 2
        if "成交量 (Volume)" in sub_indicators:
            vol_colors = ["#EF4444" if c >= o else "#10B981" for c, o in zip(df_k["Close"], df_k["Open"])]
            fig.add_trace(go.Bar(x=df_k["DateLabel"], y=df_k["Volume"], name="成交量", marker_color=vol_colors), row=curr_row, col=1)
            fig.update_yaxes(side="right", fixedrange=True, tickfont=dict(color="#E2E8F0"), row=curr_row, col=1)
            curr_row += 1

        if "KD 指標" in sub_indicators:
            fig.add_trace(go.Scatter(x=df_k["DateLabel"], y=df_k["K"], name="K9", line=dict(color="#FACC15", width=1.0)), row=curr_row, col=1)
            fig.add_trace(go.Scatter(x=df_k["DateLabel"], y=df_k["D"], name="D9", line=dict(color="#38BDF8", width=1.0)), row=curr_row, col=1)
            fig.update_yaxes(range=[0, 100], side="right", fixedrange=True, tickfont=dict(color="#E2E8F0"), row=curr_row, col=1)
            curr_row += 1

        if "MACD 指標" in sub_indicators:
            osc_colors = ["#EF4444" if v >= 0 else "#10B981" for v in df_k["OSC"]]
            fig.add_trace(go.Bar(x=df_k["DateLabel"], y=df_k["OSC"], name="MACD柱", marker_color=osc_colors), row=curr_row, col=1)
            fig.add_trace(go.Scatter(x=df_k["DateLabel"], y=df_k["DIF"], name="DIF", line=dict(color="#FACC15", width=1.0)), row=curr_row, col=1)
            fig.add_trace(go.Scatter(x=df_k["DateLabel"], y=df_k["MACD"], name="MACD", line=dict(color="#38BDF8", width=1.0)), row=curr_row, col=1)
            fig.update_yaxes(side="right", fixedrange=True, tickfont=dict(color="#E2E8F0"), row=curr_row, col=1)

        total_len = len(df_k)
        start_idx = max(0, total_len - default_bars)
        end_idx = total_len - 1

        price_cols = ["Low", "High"] + [m for m in ma_selected if m in df_k.columns]
        recent_slice = df_k.iloc[start_idx:]
        y_min = float(recent_slice[price_cols].min().min()) * 0.96
        y_max = float(recent_slice[price_cols].max().max()) * 1.04

        fig.update_layout(
            height=590,
            showlegend=False,
            dragmode="pan",
            xaxis_rangeslider_visible=False,
            template="plotly_dark",
            paper_bgcolor="#0B0F19",
            plot_bgcolor="#0B0F19",
            font=dict(color="#FFFFFF", size=11),
            margin=dict(l=5, r=48, t=12, b=22)
        )
        fig.update_xaxes(type="category", range=[start_idx - 0.5, end_idx + 0.5], nticks=8, showgrid=True, gridcolor="#1E293B", tickfont=dict(color="#E2E8F0"))
        fig.update_yaxes(side="right", range=[y_min, y_max], fixedrange=True, showgrid=True, gridcolor="#1E293B", tickfont=dict(color="#E2E8F0"), row=1, col=1)

        row_min_list = [round(float(v), 4) if pd.notna(v) else None for v in df_k[price_cols].min(axis=1)]
        row_max_list = [round(float(v), 4) if pd.notna(v) else None for v in df_k[price_cols].max(axis=1)]

        plot_html = fig.to_html(
            include_plotlyjs="cdn",
            full_html=False,
            div_id="kline_plot",
            config={"scrollZoom": False, "displayModeBar": True, "responsive": True}
        )

        custom_chart_html = f"""
        <div style="background-color:#0B0F19; margin:0; padding:0; overflow:hidden;">
            {plot_html}
        </div>
        <script>
        (function() {{
            const ROW_MIN = {json.dumps(row_min_list)};
            const ROW_MAX = {json.dumps(row_max_list)};
            const TOTAL_BARS = ROW_MIN.length;

            function bindAutoYScale() {{
                const gd = document.getElementById("kline_plot");
                if (!gd || !gd._fullLayout || typeof gd.on !== "function" || typeof Plotly === "undefined") {{
                    setTimeout(bindAutoYScale, 50);
                    return;
                }}
                if (gd._yScaleBound) return;
                gd._yScaleBound = true;

                let isRelayouting = false;
                let touchDebounce = null;

                function adjustYRange() {{
                    if (isRelayouting || !gd._fullLayout || !gd._fullLayout.xaxis) return;
                    const xr = gd._fullLayout.xaxis.range;
                    if (!xr || xr.length < 2) return;

                    let r0 = Number(xr[0]);
                    let r1 = Number(xr[1]);
                    if (isNaN(r0) || isNaN(r1)) return;

                    let i0 = Math.max(0, Math.floor(Math.min(r0, r1)));
                    let i1 = Math.min(TOTAL_BARS - 1, Math.ceil(Math.max(r0, r1)));
                    if (i1 < i0) return;

                    let minP = Infinity;
                    let maxP = -Infinity;
                    for (let i = i0; i <= i1; i++) {{
                        const lo = ROW_MIN[i];
                        const hi = ROW_MAX[i];
                        if (lo !== null && lo < minP) minP = lo;
                        if (hi !== null && hi > maxP) maxP = hi;
                    }}

                    if (minP < Infinity && maxP > -Infinity && maxP >= minP) {{
                        const span = Math.max(maxP - minP, minP * 0.02);
                        const pad = span * 0.06;
                        const newMin = minP - pad;
                        const newMax = maxP + pad;

                        const curYr = gd._fullLayout.yaxis && gd._fullLayout.yaxis.range;
                        if (!curYr || Math.abs(curYr[0] - newMin) > 0.05 || Math.abs(curYr[1] - newMax) > 0.05) {{
                            isRelayouting = true;
                            Plotly.relayout(gd, {{"yaxis.range": [newMin, newMax]}}).then(function() {{
                                isRelayouting = false;
                            }}).catch(function() {{
                                isRelayouting = false;
                            }});
                        }}
                    }}
                }}

                gd.on("plotly_relayout", adjustYRange);

                gd.addEventListener("touchmove", function() {{
                    if (touchDebounce) clearTimeout(touchDebounce);
                    touchDebounce = setTimeout(adjustYRange, 70);
                }}, {{passive: true}});

                gd.addEventListener("touchend", function() {{
                    setTimeout(adjustYRange, 40);
                    setTimeout(adjustYRange, 150);
                }}, {{passive: true}});
            }}

            bindAutoYScale();
        }})();
        </script>
        """
        components.html(custom_chart_html, height=605, scrolling=False)
    else:
        st.warning("暫時無法載入線圖資料，請確認網路連線或股票代號。")

# ==========================================
# 分頁 3：財報紅黃綠燈、營收與未來訂單分析
# ==========================================
with tab3:
    st.subheader(f"💰 {current_stock_label} 財報紅黃綠燈體檢與未來訂單展望")
    fb, inc, bal, _ = fetch_comprehensive_financials(selected_ticker)

    gm, om, nm, roe = fb["gm"], fb["om"], fb["nm"], fb["roe"]
    cr, qr, de, rev_growth = fb["cr"], fb["qr"], fb["de"], fb["rev_growth"]
    target_price, f_pe = fb["target"], fb["f_pe"]

    def light_gm(v): return "🟢 優異 (>=40%)" if v >= 40 else ("🟡 爬坡中 (20~40%)" if v >= 20 else "🔴 偏低 (<20%)")
    def light_om(v): return "🟢 獲利穩健 (>15%)" if v >= 15 else ("🟡 損平邊緣 (0~15%)" if v >= 0 else "🔴 研發/重組虧損 (<0%)")
    def light_cr(v): return "🟢 安全墊厚 (>=2.0)" if v >= 2.0 else ("🟡 尚可 (1.2~2.0)" if v >= 1.2 else "🔴 偏緊 (<1.2)")
    def light_de(v): return "🟢 低負債 (<50%)" if v < 50 else ("🟡 中度槓桿 (50~100%)" if v <= 100 else "🔴 高負債警戒 (>100%)")

    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    col_f1.metric("最新營收年增率 (YoY)", f"{rev_growth:+.2f}%")
    col_f2.metric("毛利率 (Gross Margin)", f"{gm:.2f}%", light_gm(gm))
    col_f3.metric("市場平均目標價/評等", f"{target_price}")
    col_f4.metric("遠期本益比 (Forward P/E)", f"{f_pe}")

    st.markdown("#### 🚦 紅黃綠燈財務健康體檢表")
    health_df = pd.DataFrame([
        {"檢驗項目": "毛利率 (40%損平防線檢視)", "最新數值": f"{gm:.2f}%", "燈號判定": light_gm(gm)},
        {"檢驗項目": "營業利益率 (本業造血能力)", "最新數值": f"{om:.2f}%", "燈號判定": light_om(om)},
        {"檢驗項目": "淨利率 (最終獲利留存)", "最新數值": f"{nm:.2f}%", "燈號判定": "🟢 正獲利" if nm > 0 else "🔴 虧損投入期"},
        {"檢驗項目": "股東權益報酬率 (ROE)", "最新數值": f"{roe:.2f}%", "燈號判定": "🟢 優異 (>15%)" if roe >= 15 else ("🟡 普通 (0~15%)" if roe > 0 else "🔴 負值")},
        {"檢驗項目": "流動比率 (短期償債安全墊)", "最新數值": f"{cr:.2f} 倍", "燈號判定": light_cr(cr)},
        {"檢驗項目": "速動比率 (扣除庫存變現力)", "最新數值": f"{qr:.2f} 倍", "燈號判定": "🟢 充沛 (>=1.0)" if qr >= 1.0 else "🟡 留意庫存比重"},
        {"檢驗項目": "負債權益比 (Debt/Equity)", "最新數值": f"{de:.2f}%", "燈號判定": light_de(de)}
    ])
    st.dataframe(health_df, use_container_width=True, hide_index=True)

    tw_rev_df = fetch_tw_monthly_revenue(selected_ticker)
    if not tw_rev_df.empty:
        st.markdown("#### 📊 台股每月最新公布營收趨勢 (單位：新台幣億元)")
        st.bar_chart(tw_rev_df.set_index("年月")["月營收(億)"])
    elif not inc.empty and "Total Revenue" in inc.index:
        st.markdown("#### 📊 近期季度營收趨勢 (自動抓取最新財報)")
        rev_series = inc.loc["Total Revenue"].dropna().iloc[:6][::-1]
        st.bar_chart(rev_series)

    st.markdown("#### 📦 未來訂單 (Backlog)、產能與法說指引最新情報")
    kw_order = f"{SEARCH_KEYWORDS.get(selected_ticker, selected_ticker)} (訂單 OR 營收 OR 財報 OR 產能 OR 法說 OR backlog OR guidance OR revenue)"
    order_news = fetch_google_news(kw_order, max_items=6)
    if order_news:
        for n in order_news:
            st.markdown(f"- 📅 `{n['pubDate']}` | [{n['title']}]({n['link']})")
    else:
        st.info("目前暫無最新訂單相關新聞。")

# ==========================================
# 分頁 4：13F 機構持倉變動與法人籌碼
# ==========================================
with tab4:
    st.subheader(f"🏦 {current_stock_label} 13F 機構持股變動與籌碼防呆")
    _, _, _, inst_df = fetch_comprehensive_financials(selected_ticker)
    df_recent = fetch_stock_history(selected_ticker, period="3mo", interval="1d")

    if not df_recent.empty:
        curr_p = df_recent["Close"].iloc[-1]
        avg_60d = df_recent["Close"].mean()
        diff_pct = ((curr_p - avg_60d) / avg_60d) * 100
        if diff_pct > 20:
            st.warning(f"⚠️ **【13F 時間差防呆提醒】** 目前股價 ({curr_p:.2f}) 高於近一季均價 ({avg_60d:.2f}) 達 **{diff_pct:+.1f}%**。13F 報告有 45 天遞延，請留意機構建倉成本較低，切勿盲目追高抬轎！")
        else:
            st.success(f"✅ **【位階校準】** 目前股價 ({curr_p:.2f}) 與近一季機構持倉均價 ({avg_60d:.2f}) 差距為 **{diff_pct:+.1f}%**，尚未出現過度乖離。")

    if not inst_df.empty:
        st.markdown("#### 📋 最新申報之頂級機構持股名單 (SEC 13F / 法人持倉)")
        st.dataframe(inst_df, use_container_width=True, hide_index=True)
    else:
        st.info("此標的為台股或暫無 SEC 13F 表格，以下為您抓取最新「法人/投信/ETF/機構籌碼」動態：")

    kw_chip = f"{SEARCH_KEYWORDS.get(selected_ticker, selected_ticker)} (13F OR 機構 OR 外資 OR 投信 OR 法人 OR ETF OR 00981A OR 買超)"
    chip_news = fetch_google_news(kw_chip, max_items=6)
    for cn in chip_news:
        st.markdown(f"- 🏦 `{cn['pubDate']}` | [{cn['title']}]({cn['link']})")

# ==========================================
# 分頁 5：每日訴訟追蹤與多空消息雷達
# ==========================================
with tab5:
    st.subheader(f"⚖️ {current_stock_label} 進行中訴訟追蹤與每日多空雷達")

    col_n1, col_n2 = st.columns(2)
    with col_n1:
        st.markdown("#### ⚖️ 進行中訴訟、專利戰與監管決議專區")
        kw_law = f"{SEARCH_KEYWORDS.get(selected_ticker, selected_ticker)} (訴訟 OR 官司 OR 專利 OR 侵權 OR 法院 OR SEC OR FERC OR lawsuit OR patent OR litigation)"
        law_news = fetch_google_news(kw_law, max_items=8)
        if law_news:
            for ln in law_news:
                st.markdown(f"- ⚖️ `{ln['pubDate']}` | [{ln['title']}]({ln['link']})")
        else:
            st.success("🎉 近期無重大訴訟或監管利空新聞。")

    with col_n2:
        st.markdown("#### 📡 每日即時多空消息雷達 (自動標籤分類)")
        kw_daily = SEARCH_KEYWORDS.get(selected_ticker, selected_ticker)
        daily_news = fetch_google_news(kw_daily, max_items=10)
        if daily_news:
            for dn in daily_news:
                tag = classify_news_sentiment(dn["title"])
                st.markdown(f"- **{tag}** `{dn['pubDate']}` | [{dn['title']}]({dn['link']})")
        else:
            st.info("今日暫無最新新聞。")
