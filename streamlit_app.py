import math
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="台股兵策 Lite", page_icon="📈", layout="wide")

YAHOO_QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"
TWSE_ISIN_URL = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
TPEx_ISIN_URL = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"
UA = {"User-Agent": "Mozilla/5.0"}


@st.cache_data(ttl=3600)
def get_ticker_mapping():
    mapping = {}
    for url in [TWSE_ISIN_URL, TPEx_ISIN_URL]:
        try:
            r = requests.get(url, headers=UA, timeout=20)
            r.raise_for_status()
            tables = pd.read_html(r.text)
            for df in tables:
                if df.empty or df.shape[1] < 1:
                    continue
                first_col = df.iloc[:, 0].astype(str)
                for cell in first_col:
                    m = re.match(r"^(\d{4,6})\s+(.+)$", cell.strip())
                    if m:
                        code, name = m.group(1), m.group(2)
                        if code not in mapping:
                            mapping[code] = name
        except Exception:
            continue
    return mapping


def tw_symbol(code: str) -> str:
    code = code.strip()
    if not code:
        return ""
    return f"{code}.TW"


@st.cache_data(ttl=300)
def get_quote(symbol: str):
    r = requests.get(YAHOO_QUOTE_URL, params={"symbols": symbol}, headers=UA, timeout=20)
    r.raise_for_status()
    result = r.json().get("quoteResponse", {}).get("result", [])
    if not result:
        alt = symbol.replace(".TW", ".TWO")
        r = requests.get(YAHOO_QUOTE_URL, params={"symbols": alt}, headers=UA, timeout=20)
        r.raise_for_status()
        result = r.json().get("quoteResponse", {}).get("result", [])
    if not result:
        raise ValueError("查無此股票代碼")
    return result[0]


@st.cache_data(ttl=3600)
def get_history(symbol: str):
    params = {"range": "3y", "interval": "1mo", "includePrePost": "false", "events": "div|split"}
    r = requests.get(YAHOO_CHART_URL.format(symbol=symbol), params=params, headers=UA, timeout=20)
    r.raise_for_status()
    data = r.json().get("chart", {}).get("result", [])
    if not data:
        alt = symbol.replace(".TW", ".TWO")
        r = requests.get(YAHOO_CHART_URL.format(symbol=alt), params=params, headers=UA, timeout=20)
        r.raise_for_status()
        data = r.json().get("chart", {}).get("result", [])
    if not data:
        return pd.DataFrame(columns=["date", "close"])

    item = data[0]
    ts = item.get("timestamp", [])
    closes = item.get("indicators", {}).get("quote", [{}])[0].get("close", [])
    rows = []
    for t, c in zip(ts, closes):
        if c is None:
            continue
        rows.append({"date": datetime.fromtimestamp(t), "close": float(c)})
    return pd.DataFrame(rows)


@st.cache_data(ttl=1800)
def get_news(query: str, max_items: int = 8):
    params = {"q": query, "hl": "zh-TW", "gl": "TW", "ceid": "TW:zh-Hant"}
    r = requests.get(GOOGLE_NEWS_RSS, params=params, headers=UA, timeout=20)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    items = []
    for item in root.findall(".//item")[:max_items]:
        items.append({
            "title": item.findtext("title", default="").strip(),
            "link": item.findtext("link", default="").strip(),
            "pubDate": item.findtext("pubDate", default="").strip(),
            "source": item.findtext("source", default="").strip(),
        })
    return items


def score_from_quote(quote, hist: pd.DataFrame):
    tech = 50
    fund = 50
    industry = 50

    change = quote.get("regularMarketChangePercent")
    if change is not None:
        tech += max(-20, min(20, change * 2))

    trailing_pe = quote.get("trailingPE")
    if trailing_pe:
        if trailing_pe < 15:
            fund += 15
        elif trailing_pe < 25:
            fund += 8
        elif trailing_pe > 35:
            fund -= 12

    market_cap = quote.get("marketCap")
    if market_cap:
        if market_cap > 500_000_000_000:
            industry += 15
        elif market_cap > 100_000_000_000:
            industry += 8

    if len(hist) >= 6:
        last = hist["close"].iloc[-1]
        avg6 = hist["close"].tail(6).mean()
        avg12 = hist["close"].tail(12).mean() if len(hist) >= 12 else avg6
        if last > avg6:
            tech += 10
        if last > avg12:
            tech += 10

    tech = max(0, min(100, round(tech)))
    fund = max(0, min(100, round(fund)))
    industry = max(0, min(100, round(industry)))
    total = round(tech * 0.4 + fund * 0.35 + industry * 0.25)
    return total, {"technical": tech, "fundamental": fund, "industry": industry}


def summarize_news(news, price_change_pct):
    if not news:
        return "目前未抓到近期公開新聞，建議改查公司名稱或稍後重試。"
    hot_words = ["營收", "法說", "AI", "擴產", "訂單", "配息", "除息", "外資", "EPS", "獲利"]
    hit = {w: 0 for w in hot_words}
    for item in news:
        title = item["title"]
        for w in hot_words:
            if w in title:
                hit[w] += 1
    top = [k for k, v in sorted(hit.items(), key=lambda x: x[1], reverse=True) if v > 0][:3]
    tone = "偏多" if (price_change_pct or 0) >= 0 else "偏保守"
    if top:
        return f"近期新聞主軸集中在：{'、'.join(top)}。以今日股價表現觀察，市場情緒暫時{tone}，但仍要搭配成交量與下次公告數據確認延續性。"
    return f"近期新聞量能正常，以今日股價表現看市場情緒暫時{tone}。建議優先關注下一次營收、法說會與配息公告。"


def build_short_term_projection(current_price: float):
    vals = []
    base = current_price or 100.0
    for i in range(1, 13):
        drift = math.sin(i / 2.1) * 0.04 + (i * 0.002)
        vals.append({"month": f"{i}月", "price": round(base * (1 + drift), 2)})
    return pd.DataFrame(vals)


def format_currency(val):
    return f"{val:,.0f}"


st.title("📈 台股兵策 Lite")
st.caption("免 API Key 版｜公開行情 + 公開新聞彙整")

with st.sidebar:
    st.header("查詢條件")
    stock_code = st.text_input("台股代碼", value="2330")
    entry_price = st.number_input("成本價", min_value=0.0, value=0.0, step=0.1)
    shares_count = st.number_input("張數", min_value=0.0, value=0.0, step=1.0)
    run = st.button("執行戰略掃描", use_container_width=True)
    st.markdown("---")
    st.caption("若部署後仍出現 Gemini 錯誤，代表你使用的是舊版檔案，請用這份完整替換。")

if "auto_loaded" not in st.session_state:
    st.session_state.auto_loaded = True
    run = True

if run:
    try:
        symbol = tw_symbol(stock_code)
        mapping = get_ticker_mapping()
        quote = get_quote(symbol)
        hist = get_history(symbol)
        code = stock_code.strip()
        name = quote.get("shortName") or mapping.get(code) or code
        current_price = float(quote.get("regularMarketPrice") or 0)
        change_pct = quote.get("regularMarketChangePercent") or 0.0
        previous_close = float(quote.get("regularMarketPreviousClose") or 0)
        volume = int(quote.get("regularMarketVolume") or 0)
        market_cap = int(quote.get("marketCap") or 0)
        trailing_pe = quote.get("trailingPE")
        news = get_news(f"{code} {name} 台股")
        total_score, breakdown = score_from_quote(quote, hist)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("股票", f"{code} {name}")
        col2.metric("現價", f"{current_price:,.2f}")
        col3.metric("漲跌幅", f"{change_pct:+.2f}%")
        col4.metric("戰略評分", total_score)

        if entry_price > 0 and shares_count > 0:
            market_value = current_price * shares_count * 1000
            profit = (current_price - entry_price) * shares_count * 1000
            profit_pct = ((current_price - entry_price) / entry_price) * 100
            a, b, c = st.columns(3)
            a.metric("部位市值", f"{format_currency(market_value)} TWD")
            b.metric("損益金額", f"{profit:+,.0f} TWD")
            c.metric("報酬率", f"{profit_pct:+.2f}%")

        st.subheader("核心數據")
        c1, c2, c3, c4 = st.columns(4)
        c1.write(f"**昨收**：{previous_close:,.2f}")
        c2.write(f"**成交量**：{volume:,}")
        c3.write(f"**本益比**：{trailing_pe if trailing_pe else '—'}")
        c4.write(f"**市值**：{market_cap:,}" if market_cap else "**市值**：—")

        st.subheader("三年歷史走勢")
        if not hist.empty:
            chart_df = hist.copy().set_index("date")
            st.line_chart(chart_df[["close"]])
        else:
            st.info("目前抓不到三年走勢資料。")

        st.subheader("短期戰術模擬")
        proj = build_short_term_projection(current_price).set_index("month")
        st.area_chart(proj)

        st.subheader("評分拆解")
        st.bar_chart(pd.DataFrame([breakdown]).T.rename(columns={0: "score"}))

        st.subheader("新聞彙整")
        st.write(summarize_news(news, change_pct))
        for item in news:
            st.markdown(f"- [{item['title']}]({item['link']})")

        st.subheader("規則式判讀")
        if change_pct >= 3:
            st.success("短線動能偏強，追價前先留意量價是否同步放大。")
        elif change_pct <= -3:
            st.warning("短線波動偏大，建議先觀察支撐與市場消息是否持續發酵。")
        else:
            st.info("目前走勢偏中性，建議搭配營收、法說與市場量能一起看。")

    except Exception as e:
        st.error(f"戰略掃描失敗：{e}")
        st.info("若你看到的是 Gemini 或 generativelanguage.googleapis.com 錯誤，表示目前部署的不是這份免 API Key 版本。請用本檔完整覆蓋 GitHub 上的 streamlit_app.py。")
