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
    # 美股 9 檔
    "ASTS": "ASTS (低軌衛星直連 D2D)",
    "BE": "BE (Bloom Energy 燃料電池)",
    "COHR": "COHR (Coherent 光通訊/SiC)",
    "CRDO": "CRDO (Credo 高速傳輸 AEC)",
    "GLW": "GLW (康寧 光纖/玻璃基板)",
    "GOOG": "GOOG (Alphabet 科技巨頭)",
    "ON": "ON (安森美 車用/功率半導體)",
    "NOK": "NOK (諾基亞 AI-RAN/光網路)",
    "NVTS": "NVTS (納微 800V GaN/SiC)",
    # 台股 7 檔
    "3491.TWO": "3491 昇達科 (低軌衛星元件)",
    "8027.TWO": "8027 鈦昇 (TGV 玻璃基板設備)",
    "6271.TW": "6271 同欣電 (CIS/高頻模組封測)",
    "4540.TW": "4540 全球傳動 (機器人滾珠螺桿)",
    "4576.TW": "4576 大銀微系統 (精密運動控制)",
    "3714.TW": "3714 富采 (Micro LED/CPO光源)",
    "6127.TWO": "6127 九豪 (氧化鋁陶瓷基板)"
}

# 預設搜尋新聞用的乾淨關鍵字
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

# 初始化 Session State (讓您在手機上新增/刪除股票能記住)
if "watchlist" not in st.session_state:
    st.session_state.watchlist = DEFAULT_STOCKS.copy()

# 預設載入您的核心持倉紀錄 (可在畫面上直接修改)
if "portfolio_df" not in st.session_state:
    st.session_state.portfolio_df = pd.DataFrame([
        {"代號": "GOOG", "持股數": 167.0, "平均成本": 147.14, "防守埋伏價(GTC)": 310.0},
        {"代號": "ON", "持股數": 130.0, "平均成本": 76.12, "防守埋伏價(GTC)": 68.0},
        {"代號": "GLW", "持股數": 65.0, "平均成本": 163.45, "防守埋伏價(GTC)": 140.0},
        {"代號": "NOK", "持股數": 900.0, "平均成本": 11.88, "防守埋伏價(GTC)": 8.5},
        {"代號": "NVTS", "持股數": 850.0, "平均成本": 14.51, "防守埋伏價(GTC)": 9.5},
        {"代號": "CRDO", "持股數": 41.0, "平均成本": 181.57, "防守埋伏價(GTC)": 160.0},
        {"代號": "ASTS", "持股數": 140.0, "平均成本": 60.05, "防守埋伏價(GTC)": 40.0},
        {"代號": "COHR", "持股數": 20.0, "平均成本": 296.50, "防守埋伏價(GTC)": 250.0},
        {"代號": "BE", "持股數": 5.0, "平均成本": 277.00, "防守埋伏價(GTC)": 220.0},
    ])

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
def fetch_stock_info(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return info if info else {}
    except Exception:
        return {}

@st.cache_data(ttl=3600)
def fetch_financial_statements(ticker):
    try:
        stock = yf.Ticker(ticker)
        inc = stock.quarterly_income_stmt
        bal = stock.quarterly_balance_sheet
        cf = stock.quarterly_cashflow
        inst = stock.institutional_holders
        return inc, bal, cf, inst
    except Exception:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

@st.cache_data(ttl=1800)
def fetch_google_news(query_str, max_items=12):
    """從 Google News RSS 抓取每日最新新聞與訴訟動態"""
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
    """自動將新聞分類為利多、利空、訴訟或題材觀察"""
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

# --- 側邊欄：切換股票與新增/刪除自選股 ---
st.sidebar.header("⚙️ 戰略追蹤控制台")

ticker_options = list(st.session_state.watchlist.keys())
selected_ticker = st.sidebar.selectbox(
    "📌 選擇要分析的個股：",
    options=ticker_options,
    format_func=lambda x: st.session_state.watchlist.get(x, x)
)

st.sidebar.markdown("---")
st.sidebar.subheader("➕ 新增 / ➖ 刪除自選股")
new_code = st.sidebar.text_input("輸入代號 (例: RKLB 或 2330.TW)", placeholder="輸入美股或台股代號")
new_name = st.sidebar.text_input("輸入備註名稱 (選填)", placeholder="例: 2330 台積電")

col_add, col_del = st.sidebar.columns(2)
with col_add:
    if st.button("➕ 新增股票", use_container_width=True):
        if new_code:
            code_clean = new_code.strip().upper()
            # 若輸入純數字自動補上 .TW
            if code_clean.isdigit():
                code_clean = f"{code_clean}.TW"
            label = f"{code_clean} ({new_name})" if new_name else code_clean
            st.session_state.watchlist[code_clean] = label
            st.rerun()

with col_del:
    if st.button("➖ 刪除目前股票", use_container_width=True):
        if len(st.session_state.watchlist) > 1:
            del st.session_state.watchlist[selected_ticker]
            st.rerun()

# --- 主畫面標題 ---
st.title("📊 台美股戰略追蹤儀表板")
st.caption(f"目前檢視標的：**{st.session_state.watchlist.get(selected_ticker, selected_ticker)}**")

# 建立五大核心功能分頁 (Bottom/Top Tabs)
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

    st.markdown("---")
    st.subheader("💼 個人持倉成本與 GTC 守株待兔防守座標")
    st.caption("💡 您可以直接在下方表格點擊數字進行修改，或點擊表格底部「＋」新增持股，系統會自動重算損益與到價提醒：")
    edited_pf = st.data_editor(st.session_state.portfolio_df, num_rows="dynamic", use_container_width=True)
    st.session_state.portfolio_df = edited_pf

# ==========================================
# 分頁 2：可新增/刪除的動態技術線型
# ==========================================
with tab2:
    st.subheader(f"📈 {st.session_state.watchlist.get(selected_ticker)} 互動式技術線型")
    
    col_t1, col_t2 = st.columns([1, 2])
    with col_t1:
        tf_choice = st.radio("選擇 K 線週期：", ["日K線 (1年)", "週K線 (3年)", "60分K線 (近1個月)"], horizontal=True)
    with col_t2:
        ma_Selected = st.multiselect(
            "勾選要【新增/刪除】的均線：",
            options=["MA5", "MA10", "MA20 (月線)", "MA60 (季線)", "MA120 (半年線)", "MA240 (年線)"],
            default=["MA20 (月線)", "MA60 (季線)"]
        )
    
    sub_indicators = st.multiselect(
        "勾選要【新增/刪除】的副圖指標：",
        options=["成交量 (Volume)", "KD 指標", "MACD 指標"],
        default=["成交量 (Volume)", "KD 指標"]
    )

    if tf_choice == "日K線 (1年)":
        df_k = fetch_stock_history(selected_ticker, period="1y", interval="1d")
    elif tf_choice == "週K線 (3年)":
        df_k = fetch_stock_history(selected_ticker, period="3y", interval="1wk")
    else:
        df_k = fetch_stock_history(selected_ticker, period="1mo", interval="60m")

    if not df_k.empty:
        # 計算均線
        ma_map = {"MA5": 5, "MA10": 10, "MA20 (月線)": 20, "MA60 (季線)": 60, "MA120 (半年線)": 120, "MA240 (年線)": 240}
        ma_colors = {"MA5": "#F59E0B", "MA10": "#3B82F6", "MA20 (月線)": "#EF4444", "MA60 (季線)": "#10B981", "MA120 (半年線)": "#8B5CF6", "MA240 (年線)": "#EC4899"}
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

        # 動態建立副圖數量
        num_rows = 1 + len(sub_indicators)
        row_heights = [0.55] + [0.45 / len(sub_indicators)] * len(sub_indicators) if sub_indicators else [1.0]
        fig = make_subplots(rows=num_rows, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=row_heights)

        # 主圖：K線 (符合台灣習慣：紅漲綠跌)
        fig.add_trace(go.Candlestick(
            x=df_k.index, open=df_k["Open"], high=df_k["High"], low=df_k["Low"], close=df_k["Close"],
            increasing_line_color="#EF4444", decreasing_line_color="#10B981", name="K線"
        ), row=1, col=1)

        for m_label in ma_Selected:
            fig.add_trace(go.Scatter(
                x=df_k.index, y=df_k[m_label], mode="lines", name=m_label,
                line=dict(color=ma_colors[m_label], width=1.8)
            ), row=1, col=1)

        # 副圖繪製
        curr_row = 2
        if "成交量 (Volume)" in sub_indicators:
            vol_colors = ["#EF4444" if c >= o else "#10B981" for c, o in zip(df_k["Close"], df_k["Open"])]
            fig.add_trace(go.Bar(x=df_k.index, y=df_k["Volume"], name="成交量", marker_color=vol_colors), row=curr_row, col=1)
            curr_row += 1

        if "KD 指標" in sub_indicators:
            fig.add_trace(go.Scatter(x=df_k.index, y=df_k["K"], name="K值", line=dict(color="#F59E0B", width=1.5)), row=curr_row, col=1)
            fig.add_trace(go.Scatter(x=df_k.index, y=df_k["D"], name="D值", line=dict(color="#3B82F6", width=1.5)), row=curr_row, col=1)
            curr_row += 1

        if "MACD 指標" in sub_indicators:
            osc_colors = ["#EF4444" if v >= 0 else "#10B981" for v in df_k["OSC"]]
            fig.add_trace(go.Bar(x=df_k.index, y=df_k["OSC"], name="MACD柱", marker_color=osc_colors), row=curr_row, col=1)
            fig.add_trace(go.Scatter(x=df_k.index, y=df_k["DIF"], name="DIF", line=dict(color="#F59E0B", width=1.5)), row=curr_row, col=1)
            fig.add_trace(go.Scatter(x=df_k.index, y=df_k["MACD"], name="訊號線", line=dict(color="#3B82F6", width=1.5)), row=curr_row, col=1)

        fig.update_layout(height=680, xaxis_rangeslider_visible=False, template="plotly_dark", margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("暫時無法載入線圖資料，請確認網路連線或股票代號。")

# ==========================================
# 分頁 3：財報紅黃綠燈、營收與未來訂單分析
# ==========================================
with tab3:
    st.subheader(f"💰 {st.session_state.watchlist.get(selected_ticker)} 財報紅黃綠燈體檢與未來訂單展望")
    info = fetch_stock_info(selected_ticker)
    inc, bal, cf, _ = fetch_financial_statements(selected_ticker)

    # 萃取關鍵財務指標
    gm = (info.get("grossMargins", 0) or 0) * 100
    om = (info.get("operatingMargins", 0) or 0) * 100
    nm = (info.get("profitMargins", 0) or 0) * 100
    roe = (info.get("returnOnEquity", 0) or 0) * 100
    cr = info.get("currentRatio", 0) or 0
    qr = info.get("quickRatio", 0) or 0
    de = info.get("debtToEquity", 0) or 0
    rev_growth = (info.get("revenueGrowth", 0) or 0) * 100
    target_price = info.get("targetMeanPrice", "無資料")
    f_pe = info.get("forwardPE", "尚未獲利/無資料")

    def light_gm(v): return "🟢 優異 (>=40%)" if v >= 40 else ("🟡 爬坡中 (20~40%)" if v >= 20 else "🔴 偏低 (<20%)")
    def light_om(v): return "🟢 獲利穩健 (>15%)" if v >= 15 else ("🟡 損平邊緣 (0~15%)" if v >= 0 else "🔴 營業虧損 (<0%)")
    def light_cr(v): return "🟢 安全墊厚 (>=2.0)" if v >= 2.0 else ("🟡 尚可 (1.2~2.0)" if v >= 1.2 else "🔴 偏緊 (<1.2)")
    def light_de(v): return "🟢 低負債 (<50%)" if v < 50 else ("🟡 中度槓桿 (50~100%)" if v <= 100 else "🔴 高負債警戒 (>100%)")

    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    col_f1.metric("最新營收年增率 (YoY)", f"{rev_growth:.2f}%")
    col_f2.metric("毛利率 (Gross Margin)", f"{gm:.2f}%", light_gm(gm))
    col_f3.metric("華爾街平均目標價", f"{target_price}")
    col_f4.metric("遠期本益比 (Forward P/E)", f"{f_pe if isinstance(f_pe, str) else round(f_pe, 2)}")

    st.markdown("#### 🚦 紅黃綠燈財務健康體檢表")
    health_df = pd.DataFrame([
        {"檢驗項目": "毛利率 (40%損平防線檢視)", "最新數值": f"{gm:.2f}%", "燈號判定": light_gm(gm)},
        {"檢驗項目": "營業利益率 (本業造血能力)", "最新數值": f"{om:.2f}%", "燈號判定": light_om(om)},
        {"檢驗項目": "淨利率 (最終獲利留存)", "最新數值": f"{nm:.2f}%", "燈號判定": "🟢 正獲利" if nm > 0 else "🔴 虧損失血期"},
        {"檢驗項目": "股東權益報酬率 (ROE)", "最新數值": f"{roe:.2f}%", "燈號判定": "🟢 優異 (>15%)" if roe >= 15 else ("🟡 普通" if roe > 0 else "🔴 負值")},
        {"檢驗項目": "流動比率 (短期償債安全墊)", "最新數值": f"{cr:.2f} 倍", "燈號判定": light_cr(cr)},
        {"檢驗項目": "速動比率 (扣除庫存變現力)", "最新數值": f"{qr:.2f} 倍", "燈號判定": "🟢 充沛 (>=1.0)" if qr >= 1.0 else "🟡 留意庫存比重"},
        {"檢驗項目": "負債權益比 (Debt/Equity)", "最新數值": f"{de:.2f}%", "燈號判定": light_de(de)}
    ])
    st.dataframe(health_df, use_container_width=True, hide_index=True)

    # 歷史季度營收與庫存變化圖表
    if not inc.empty and "Total Revenue" in inc.index:
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
    _, _, _, inst_df = fetch_financial_statements(selected_ticker)
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
