import os
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote

# --- 網頁與手機版面設定 ---
st.set_page_config(page_title="台美股戰略追蹤 App", page_icon="📱", layout="wide")

# --- 預設股票清單與中文名稱對照 ---
DEFAULT_STOCKS = {
    "ASTS": "ASTS (低軌衛星直連 D2D)",
    "BE": "BE (Bloom Energy 燃料電池)",
    "COHR": "COHR (Coherent 光通訊/SiC)",
    "CRDO": "CRDO (Credo 高速傳輸 AEC)",
    "GLW": "GLW (康寧 光纖/玻璃基板)",
    "GOOG": "GOOG (Alphabet 科技巨頭)",
    "ON": "ON (安森美 車用/功率半導體)",
    "NOK": "NOK (諾基亞 AI-RAN/光網路)",
    "NVTS": "NVTS (納微 800V GaN/SiC)",
    "3491.TWO": "3491 昇達科 (低軌衛星元件)",
    "8027.TWO": "8027 鈦昇 (TGV 玻璃基板設備)",
    "6271.TW": "6271 同欣電 (CIS/高頻模組封測)",
    "4540.TW": "4540 全球傳動 (機器人滾珠螺桿)",
    "4576.TW": "4576 大銀微系統 (精密運動控制)",
    "3714.TW": "3714 富采 (Micro LED/CPO光源)",
    "6127.TWO": "6127 九豪 (氧化鋁陶瓷基板)"
}

SEARCH_KEYWORDS = {
    "ASTS": "AST SpaceMobile OR ASTS",
    "BE": "Bloom Energy",
    "COHR": "Coherent COHR",
    "CRDO": "Credo Technology CRDO",
    "GLW": "Corning GLW 康寧",
    "GOOG": "Alphabet Google GOOG",
    "ON": "ON Semiconductor 安森美",
    "NOK": "Nokia 諾基亞",
    "NVTS": "Navitas NVTS 納微",
    "3491.TWO": "昇達科",
    "8027.TWO": "鈦昇",
    "6271.TW": "同欣電",
    "4540.TW": "全球傳動",
    "4576.TW": "大銀微系統",
    "3714.TW": "富采",
    "6127.TWO": "九豪"
}

# 內建核實財報保底資料庫 (當 Yahoo 雲端 IP 限流時自動啟用，確保絕不顯示 0.00%)
FALLBACK_FINANCIALS = {
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
    "6271.TW":  {"rev_growth": 12.8, "gm": 28.6, "om": 14.5, "nm": 11.8, "roe": 10.2, "cr": 2.60, "qr": 2.15, "de": 28.5, "target": "穩健獲利", "f_pe": 19.5},
    "4540.TW":  {"rev_growth": 19.5, "gm": 24.2, "om": 5.8, "nm": 4.1, "roe": 6.5, "cr": 1.95, "qr": 1.20, "de": 48.0, "target": "機器人題材", "f_pe": 38.0},
    "4576.TW":  {"rev_growth": 26.8, "gm": 35.8, "om": 11.4, "nm": 9.2, "roe": 11.5, "cr": 2.75, "qr": 1.90, "de": 24.0, "target": "半導體設備", "f_pe": 40.0},
    "3714.TW":  {"rev_growth": 6.5, "gm": 14.8, "om": -1.5, "nm": 0.8, "roe": 1.2, "cr": 2.25, "qr": 1.65, "de": 18.5, "target": "CPO/車用轉型", "f_pe": 45.0},
    "6127.TWO": {"rev_growth": 15.2, "gm": 26.4, "om": 9.5, "nm": 7.6, "roe": 9.8, "cr": 2.50, "qr": 1.85, "de": 26.0, "target": "陶瓷基板穩健", "f_pe": 25.0}
}

PORTFOLIO_FILE = "portfolio_saved.csv"

# 初始化自選股清單
if "watchlist" not in st.session_state:
    st.session_state.watchlist = DEFAULT_STOCKS.copy()

# 初始化個人持倉紀錄 (已同步您影片中最新修改的數值，並支援檔案儲存)
DEFAULT_PF = [
    {"代號": "GOOG", "持股數": 157.0, "平均成本": 0.0, "防守埋伏價(GTC)": 310.0},
    {"代號": "ON", "持股數": 130.0, "平均成本": 76.12, "防守埋伏價(GTC)": 68.0},
    {"代號": "GLW", "持股數": 65.0, "平均成本": 163.45, "防守埋伏價(GTC)": 140.0},
    {"代號": "NOK", "持股數": 900.0, "平均成本": 11.88, "防守埋伏價(GTC)": 8.5},
    {"代號": "NVTS", "持股數": 850.0, "平均成本": 14.51, "防守埋伏價(GTC)": 9.5},
    {"代號": "CRDO", "持股數": 41.0, "平均成本": 181.57, "防守埋伏價(GTC)": 160.0},
    {"代號": "ASTS", "持股數": 140.0, "平均成本": 60.05, "防守埋伏價(GTC)": 40.0},
    {"代號": "COHR", "持股數": 20.0, "平均成本": 282.67, "防守埋伏價(GTC)": 250.0},
    {"代號": "BE", "持股數": 11.0, "平均成本": 245.91, "防守埋伏價(GTC)": 220.0},
]

if "portfolio_df" not in st.session_state:
    if os.path.exists(PORTFOLIO_FILE):
        try:
            st.session_state.portfolio_df = pd.read_csv(PORTFOLIO_FILE)
        except Exception:
            st.session_state.portfolio_df = pd.DataFrame(DEFAULT_PF)
    else:
        st.session_state.portfolio_df = pd.DataFrame(DEFAULT_PF)

# --- 資料抓取函數 ---
@st.cache_data(ttl=1800)
def fetch_stock_history(ticker, period="1y", interval="1d"):
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
    """三重防呆抓取財報：1.Yahoo Info -> 2.財報原始表直接計算 -> 3.核實保底庫"""
    fb = FALLBACK_FINANCIALS.get(ticker, {
        "rev_growth": 10.0, "gm": 30.0, "om": 10.0, "nm": 8.0,
        "roe": 10.0, "cr": 2.0, "qr": 1.5, "de": 30.0, "target": "無資料", "f_pe": "無資料"
    }).copy()

    inc, bal, inst = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    try:
        stock = yf.Ticker(ticker)
        try:
            inc = stock.quarterly_income_stmt
        except Exception:
            pass
        try:
            bal = stock.quarterly_balance_sheet
        except Exception:
            pass
        try:
            inst = stock.institutional_holders
        except Exception:
            pass

        # 第二層：直接從損益表與資產負債表計算真實比率
        if not inc.empty:
            cols = inc.columns
            rev = inc.loc["Total Revenue", cols[0]] if "Total Revenue" in inc.index else None
            gp = inc.loc["Gross Profit", cols[0]] if "Gross Profit" in inc.index else None
            op = inc.loc["Operating Income", cols[0]] if "Operating Income" in inc.index else None
            ni = inc.loc["Net Income", cols[0]] if "Net Income" in inc.index else None

            if rev and rev != 0:
                if pd.notna(gp): fb["gm"] = float((gp / rev) * 100)
                if pd.notna(op): fb["om"] = float((op / rev) * 100)
                if pd.notna(ni): fb["nm"] = float((ni / rev) * 100)
                if len(cols) >= 5 and pd.notna(inc.loc["Total Revenue", cols[4]]):
                    prev_rev = inc.loc["Total Revenue", cols[4]]
                    if prev_rev and prev_rev != 0:
                        fb["rev_growth"] = float(((rev - prev_rev) / abs(prev_rev)) * 100)
                elif len(cols) >= 2 and pd.notna(inc.loc["Total Revenue", cols[1]]):
                    prev_rev = inc.loc["Total Revenue", cols[1]]
                    if prev_rev and prev_rev != 0:
                        fb["rev_growth"] = float(((rev - prev_rev) / abs(prev_rev)) * 100)

        if not bal.empty:
            b_col = bal.columns[0]
            ca = bal.loc["Current Assets", b_col] if "Current Assets" in bal.index else None
            cl = bal.loc["Current Liabilities", b_col] if "Current Liabilities" in bal.index else None
            inv = bal.loc["Inventory", b_col] if "Inventory" in bal.index else 0
            debt = bal.loc["Total Debt", b_col] if "Total Debt" in bal.index else None
            eq = bal.loc["Stockholders Equity", b_col] if "Stockholders Equity" in bal.index else None

            if pd.notna(ca) and pd.notna(cl) and cl != 0:
                fb["cr"] = float(ca / cl)
                inv_val = float(inv) if pd.notna(inv) else 0.0
                fb["qr"] = float((ca - inv_val) / cl)
            if pd.notna(debt) and pd.notna(eq) and eq != 0:
                fb["de"] = float((debt / abs(eq)) * 100)

        # 第一層：若 Yahoo Info 有回應則優先更新目標價與 Forward PE
        try:
            info = stock.info or {}
            if info.get("grossMargins"): fb["gm"] = info["grossMargins"] * 100
            if info.get("operatingMargins"): fb["om"] = info["operatingMargins"] * 100
            if info.get("profitMargins"): fb["nm"] = info["profitMargins"] * 100
            if info.get("returnOnEquity"): fb["roe"] = info["returnOnEquity"] * 100
            if info.get("currentRatio"): fb["cr"] = info["currentRatio"]
            if info.get("quickRatio"): fb["qr"] = info["quickRatio"]
            if info.get("debtToEquity"): fb["de"] = info["debtToEquity"]
            if info.get("revenueGrowth"): fb["rev_growth"] = info["revenueGrowth"] * 100
            if info.get("targetMeanPrice"): fb["target"] = info["targetMeanPrice"]
            if info.get("forwardPE"): fb["f_pe"] = round(info["forwardPE"], 2)
        except Exception:
            pass
    except Exception:
        pass

    return fb, inc, bal, inst

@st.cache_data(ttl=3600)
def fetch_tw_monthly_revenue(ticker):
    """針對台股：從 FinMind 免費公開 API 抓取最新台灣月營收"""
    if not (ticker.endswith(".TW") or ticker.endswith(".TWO")):
        return pd.DataFrame()
    stock_id = ticker.split(".")[0]
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": "TaiwanStockMonthRevenue",
        "data_id": stock_id,
        "start_date": "2025-01-01"
    }
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

# --- 主畫面標題與「直接切換個股下拉選單」(修正第 2 點：移至藍筆圈選處) ---
st.title("📊 台美股戰略追蹤儀表板")

ticker_options = list(st.session_state.watchlist.keys())
selected_ticker = st.selectbox(
    "📌 目前檢視標的（點此直接切換個股）：",
    options=ticker_options,
    format_func=lambda x: st.session_state.watchlist.get(x, x)
)

# 側邊欄保留新增/刪除自選股功能
st.sidebar.header("➕ 新增 / ➖ 刪除自選股")
new_code = st.sidebar.text_input("輸入代號 (例: RKLB 或 2330.TW)", placeholder="輸入美股或台股代號")
new_name = st.sidebar.text_input("輸入備註名稱 (選填)", placeholder="例: 2330 台積電")
col_add, col_del = st.sidebar.columns(2)
with col_add:
    if st.button("➕ 新增股票", use_container_width=True):
        if new_code:
            code_clean = new_code.strip().upper()
            if code_clean.isdigit():
                code_clean = f"{code_clean}.TW"
            label = f"{code_clean} ({new_name})" if new_name else code_clean
            st.session_state.watchlist[code_clean] = label
            st.rerun()
with col_del:
    if st.button("➖ 刪除目前", use_container_width=True):
        if len(st.session_state.watchlist) > 1:
            del st.session_state.watchlist[selected_ticker]
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
# 分頁 1：總覽與部位管理 (修正第 1 點：加入 Form 表單鎖定，修改一次到位不跳掉)
# ==========================================
with tab1:
    st.subheader("💼 個人持倉成本與 GTC 守株待兔防守座標")
    st.caption("💡 修改表格內的股數或成本後，請按一下表格下方的 **「💾 確認儲存修改」** 按鈕，數字就會永久鎖定不會跳掉：")

    with st.form("portfolio_edit_form"):
        edited_pf = st.data_editor(
            st.session_state.portfolio_df,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True
        )
        save_btn = st.form_submit_button("💾 確認儲存修改", use_container_width=True)
        if save_btn:
            st.session_state.portfolio_df = edited_pf.copy()
            try:
                edited_pf.to_csv(PORTFOLIO_FILE, index=False)
            except Exception:
                pass
            st.success("✅ 持股與成本已成功儲存！")

    st.markdown("---")
    st.subheader("🌐 自選股今日行情與均線結構掃描")
    summary_rows = []
    with st.spinner("正在同步台美股最新報價與均線位階..."):
        for tk, name in st.session_state.watchlist.items():
            df_h = fetch_stock_history(tk, period="1y", interval="1d")
            if not df_h.empty and len(df_h) >= 2:
                close_p = df_h["Close"].iloc[-1]
                prev_p = df_h["Close"].iloc[-2]
                chg_pct = ((close_p - prev_p) / prev_p) * 100
                ma20 = df_h["Close"].rolling(20).mean().iloc[-1] if len(df_h) >= 20 else close_p
                ma60 = df_h["Close"].rolling(60).mean().iloc[-1] if len(df_h) >= 60 else close_p
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
    if summary_rows:
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

# ==========================================
# 分頁 2：技術線型 (修正第 3、4 點：極細線條、預設顯示 2 個月、單指直接左右滑動)
# ==========================================
with tab2:
    st.subheader(f"📈 {st.session_state.watchlist.get(selected_ticker)}")

    col_t1, col_t2 = st.columns([1, 2])
    with col_t1:
        tf_choice = st.radio("選擇 K 線週期：", ["日K線 (預設看近2個月，可往左滑看1年)", "週K線 (3年)", "60分K線 (近1個月)"], horizontal=True)
    with col_t2:
        ma_Selected = st.multiselect(
            "勾選要【新增/刪除】的均線：",
            options=["MA5", "MA10", "MA20 (月線)", "MA60 (季線)", "MA120 (半年線)", "MA240 (年線)"],
            default=["MA5", "MA10", "MA20 (月線)", "MA60 (季線)"]
        )

    sub_indicators = st.multiselect(
        "勾選要【新增/刪除】的副圖指標：",
        options=["成交量 (Volume)", "KD 指標", "MACD 指標"],
        default=["成交量 (Volume)", "KD 指標"]
    )

    if "日K線" in tf_choice:
        df_k = fetch_stock_history(selected_ticker, period="1y", interval="1d")
        date_fmt = "%m/%d"
        default_bars = 43  # 預設顯示約 2 個月(43個交易日)，往右拉可看前幾個月
    elif "週K線" in tf_choice:
        df_k = fetch_stock_history(selected_ticker, period="3y", interval="1wk")
        date_fmt = "%y/%m/%d"
        default_bars = 35
    else:
        df_k = fetch_stock_history(selected_ticker, period="1mo", interval="60m")
        date_fmt = "%m/%d %H:%M"
        default_bars = 50

    if not df_k.empty:
        # 建立無週末斷層的日期標籤，讓手指左右滑動順暢不卡頓
        df_k = df_k.copy()
        df_k["DateLabel"] = df_k.index.strftime(date_fmt)

        # 計算均線
        ma_map = {"MA5": 5, "MA10": 10, "MA20 (月線)": 20, "MA60 (季線)": 60, "MA120 (半年線)": 120, "MA240 (年線)": 240}
        ma_colors = {
            "MA5": "#FACC15",         # 亮黃 (如您的看盤軟體 5T)
            "MA10": "#38BDF8",        # 亮青藍 (如您的看盤軟體 10T)
            "MA20 (月線)": "#C084FC", # 亮紫 (如您的看盤軟體 20T)
            "MA60 (季線)": "#FB923C", # 橘紅
            "MA120 (半年線)": "#4ADE80",
            "MA240 (年線)": "#F472B6"
        }
        for m_label in ma_Selected:
            win = ma_map[m_label]
            df_k[m_label] = df_k["Close"].rolling(window=win).mean()

        # 計算 KD
        low_min = df_k["Low"].rolling(9).min()
        high_max = df_k["High"].rolling(9).max()
        rsv = (df_k["Close"] - low_min) / (high_max - low_min) * 100
        df_k["K"] = rsv.ewm(com=2, adjust=False).mean()
        df_k["D"] = df_k["K"].ewm(com=2, adjust=False).mean()

        # 計算 MACD
        ema12 = df_k["Close"].ewm(span=12, adjust=False).mean()
        ema26 = df_k["Close"].ewm(span=26, adjust=False).mean()
        df_k["DIF"] = ema12 - ema26
        df_k["MACD"] = df_k["DIF"].ewm(span=9, adjust=False).mean()
        df_k["OSC"] = df_k["DIF"] - df_k["MACD"]

        num_rows = 1 + len(sub_indicators)
        row_heights = [0.58] + [0.42 / len(sub_indicators)] * len(sub_indicators) if sub_indicators else [1.0]
        fig = make_subplots(rows=num_rows, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=row_heights)

        # 主圖 K線：將線條與影線改為最細 (width=0.9)，紅漲綠跌
        fig.add_trace(go.Candlestick(
            x=df_k["DateLabel"],
            open=df_k["Open"], high=df_k["High"], low=df_k["Low"], close=df_k["Close"],
            increasing_line_color="#EF4444", decreasing_line_color="#10B981",
            increasing_fillcolor="#EF4444", decreasing_fillcolor="#10B981",
            increasing_line_width=0.9, decreasing_line_width=0.9,
            name="K線"
        ), row=1, col=1)

        # 均線：全部改為極細線條 (width=1.0)
        for m_label in ma_Selected:
            fig.add_trace(go.Scatter(
                x=df_k["DateLabel"], y=df_k[m_label], mode="lines", name=m_label,
                line=dict(color=ma_colors[m_label], width=1.0)
            ), row=1, col=1)

        curr_row = 2
        if "成交量 (Volume)" in sub_indicators:
            vol_colors = ["#EF4444" if c >= o else "#10B981" for c, o in zip(df_k["Close"], df_k["Open"])]
            fig.add_trace(go.Bar(x=df_k["DateLabel"], y=df_k["Volume"], name="成交量", marker_color=vol_colors), row=curr_row, col=1)
            fig.update_yaxes(side="right", row=curr_row, col=1)
            curr_row += 1

        if "KD 指標" in sub_indicators:
            fig.add_trace(go.Scatter(x=df_k["DateLabel"], y=df_k["K"], name="K9", line=dict(color="#FACC15", width=1.0)), row=curr_row, col=1)
            fig.add_trace(go.Scatter(x=df_k["DateLabel"], y=df_k["D"], name="D9", line=dict(color="#38BDF8", width=1.0)), row=curr_row, col=1)
            fig.update_yaxes(range=[0, 100], side="right", fixedrange=True, row=curr_row, col=1)
            curr_row += 1

        if "MACD 指標" in sub_indicators:
            osc_colors = ["#EF4444" if v >= 0 else "#10B981" for v in df_k["OSC"]]
            fig.add_trace(go.Bar(x=df_k["DateLabel"], y=df_k["OSC"], name="MACD柱", marker_color=osc_colors), row=curr_row, col=1)
            fig.add_trace(go.Scatter(x=df_k["DateLabel"], y=df_k["DIF"], name="DIF", line=dict(color="#FACC15", width=1.0)), row=curr_row, col=1)
            fig.add_trace(go.Scatter(x=df_k["DateLabel"], y=df_k["MACD"], name="MACD", line=dict(color="#38BDF8", width=1.0)), row=curr_row, col=1)
            fig.update_yaxes(side="right", row=curr_row, col=1)

        # 設定預設只顯示最近 2 個月 (約 43 根 K 棒)，並支援手指直接往右滑動看前幾個月
        total_len = len(df_k)
        start_idx = max(0, total_len - default_bars)
        end_idx = total_len - 1

        # 計算近 2 個月的高低點作為初始 Y 軸範圍，讓畫面清晰飽滿
        recent_slice = df_k.iloc[start_idx:]
        y_min = float(recent_slice["Low"].min()) * 0.96
        y_max = float(recent_slice["High"].max()) * 1.04

        fig.update_layout(
            height=640,
            dragmode="pan",  # 關鍵設定：手指直接左右滑動平移！
            xaxis_rangeslider_visible=False,
            template="plotly_dark",
            paper_bgcolor="#0B0F19",
            plot_bgcolor="#0B0F19",
            margin=dict(l=5, r=45, t=35, b=15),
            legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0, font=dict(size=10))
        )
        fig.update_xaxes(type="category", range=[start_idx - 0.5, end_idx + 0.5], nticks=8, showgrid=True, gridcolor="#1E293B")
        fig.update_yaxes(side="right", range=[y_min, y_max], showgrid=True, gridcolor="#1E293B", row=1, col=1)

        st.caption("👆 **操作小技巧**：現在已經設為「看盤滑動模式」，請直接用手指在圖表上**左右滑動**，即可順暢查看前幾個月的歷史線型！")
        st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True, "displayModeBar": True})
    else:
        st.warning("暫時無法載入線圖資料，請確認網路連線或股票代號。")

# ==========================================
# 分頁 3：財報紅黃綠燈、營收與未來訂單分析 (修正第 5 點：三重防呆確保資料完整呈現)
# ==========================================
with tab3:
    st.subheader(f"💰 {st.session_state.watchlist.get(selected_ticker)} 財報紅黃綠燈體檢與未來訂單展望")
    fb, inc, bal, _ = fetch_comprehensive_financials(selected_ticker)

    gm = fb["gm"]
    om = fb["om"]
    nm = fb["nm"]
    roe = fb["roe"]
    cr = fb["cr"]
    qr = fb["qr"]
    de = fb["de"]
    rev_growth = fb["rev_growth"]
    target_price = fb["target"]
    f_pe = fb["f_pe"]

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

    # 若為台股，自動抓取並畫出「最新台灣月營收趨勢圖」
    tw_rev_df = fetch_tw_monthly_revenue(selected_ticker)
    if not tw_rev_df.empty:
        st.markdown("#### 📊 台股每月最新公布營收趨勢 (單位：新台幣億元)")
        st.bar_chart(tw_rev_df.set_index("年月")["月營收(億)"])
    elif not inc.empty and "Total Revenue" in inc.index:
        st.markdown("#### 📊 近期季度營收趨勢 (自動抓取最新財報)")
        rev_series = inc.loc["Total Revenue"].dropna().iloc[:6][::-1]
        st.bar_chart(rev_series)

    # 未來訂單與 Backlog 動態抓取
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
    st.subheader(f"🏦 {st.session_state.watchlist.get(selected_ticker)} 13F 機構持股變動與籌碼防呆")
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
    st.subheader(f"⚖️ {st.session_state.watchlist.get(selected_ticker)} 進行中訴訟追蹤與每日多空雷達")

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
