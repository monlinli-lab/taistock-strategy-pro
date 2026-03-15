import math
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from io import StringIO
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="台股兵策", page_icon="📈", layout="wide")

USER_AGENT = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://www.twse.com.tw/",
}


def safe_float(v, default=None):
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "")
    if s in {"", "--", "---", "X", "null", "None", "nan"}:
        return default
    try:
        return float(s)
    except Exception:
        return default


def roc_year_month(dt):
    return f"{dt.year - 1911}/{dt.month:02d}"


@st.cache_data(ttl=120)
def fetch_json(url, params=None, headers=None, timeout=20):
    h = dict(USER_AGENT)
    if headers:
        h.update(headers)
    r = requests.get(url, params=params, headers=h, timeout=timeout)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=120)
def fetch_text(url, params=None, headers=None, timeout=20):
    h = dict(USER_AGENT)
    if headers:
        h.update(headers)
    r = requests.get(url, params=params, headers=h, timeout=timeout)
    r.raise_for_status()
    return r.text


@st.cache_data(ttl=1800)
def get_twse_company_list():
    urls = [
        "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
        "https://openapi.twse.com.tw/v1/opendata/t187ap03_O",
    ]
    rows = []
    for url in urls:
        try:
            data = fetch_json(url)
            if isinstance(data, list):
                rows.extend(data)
        except Exception:
            pass
    mapping = {}
    for row in rows:
        code = str(row.get("公司代號") or row.get("SecuritiesCompanyCode") or "").strip()
        name = str(row.get("公司簡稱") or row.get("CompanyName") or row.get("公司名稱") or "").strip()
        industry = str(row.get("產業別") or row.get("Industry") or "").strip()
        if code:
            mapping[code] = {"name": name, "industry": industry, "market": "上市"}
    return mapping


@st.cache_data(ttl=1800)
def get_tpex_company_list():
    candidates = [
        "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O",
        "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_company_basic_info",
        "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis",
    ]
    mapping = {}
    for url in candidates:
        try:
            data = fetch_json(url)
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        for row in data:
            code = str(
                row.get("SecuritiesCompanyCode")
                or row.get("公司代號")
                or row.get("股票代號")
                or row.get("Code")
                or ""
            ).strip()
            name = str(
                row.get("CompanyName")
                or row.get("公司簡稱")
                or row.get("公司名稱")
                or row.get("Name")
                or ""
            ).strip()
            industry = str(row.get("Industry") or row.get("產業別") or "").strip()
            if code:
                mapping[code] = {"name": name, "industry": industry, "market": "上櫃"}
        if mapping:
            break
    return mapping


def get_company_meta(code):
    twse = get_twse_company_list()
    tpex = get_tpex_company_list()
    if code in twse:
        return twse[code]
    if code in tpex:
        return tpex[code]
    return {"name": f"{code}", "industry": "未分類", "market": "未知"}


@st.cache_data(ttl=120)
def get_live_quote(code):
    attempts = [
        ("tse", f"tse_{code}.tw"),
        ("otc", f"otc_{code}.tw"),
    ]
    last_error = None
    for market, ex_ch in attempts:
        url = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
        params = {"ex_ch": ex_ch, "json": 1, "delay": 0, "_": int(time.time() * 1000)}
        try:
            data = fetch_json(url, params=params, headers={"Referer": "https://mis.twse.com.tw/stock/index.jsp"})
            msg = data.get("msgArray") or []
            if not msg:
                continue
            row = msg[0]
            price = safe_float(row.get("z")) or safe_float(row.get("pz")) or safe_float(row.get("y"))
            prev_close = safe_float(row.get("y"))
            if price is None:
                continue
            change_pct = None
            if price is not None and prev_close not in (None, 0):
                change_pct = ((price - prev_close) / prev_close) * 100
            return {
                "market": "上市" if market == "tse" else "上櫃",
                "price": price,
                "prev_close": prev_close,
                "change_pct": change_pct,
                "name": row.get("n") or row.get("nf") or code,
                "time": row.get("tlong") or row.get("t"),
            }
        except Exception as e:
            last_error = e
    raise RuntimeError(f"即時行情來源暫時無法取得：{last_error}")


@st.cache_data(ttl=3600)
def get_twse_month_history(code, year, month):
    date = f"{year}{month:02d}01"
    url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
    params = {"response": "json", "date": date, "stockNo": code}
    data = fetch_json(url, params=params)
    rows = data.get("data") or []
    out = []
    for r in rows:
        if len(r) < 7:
            continue
        dt = r[0].strip()
        close = safe_float(r[6])
        if close is None:
            continue
        out.append({"date": dt, "close": close})
    return out


@st.cache_data(ttl=3600)
def get_tpex_month_history(code, year, month):
    url = "https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43_result.php"
    params = {"l": "zh-tw", "d": roc_year_month(datetime(year, month, 1)), "stkno": code}
    data = fetch_json(url, params=params, headers={"Referer": "https://www.tpex.org.tw/"})
    rows = data.get("aaData") or []
    out = []
    for r in rows:
        if len(r) < 7:
            continue
        close = safe_float(r[6])
        if close is None:
            continue
        out.append({"date": r[0].strip(), "close": close})
    return out


@st.cache_data(ttl=3600)
def get_history_3y(code, market):
    today = datetime.today().replace(day=1)
    months = []
    for i in range(36):
        dt = (today - timedelta(days=30 * i)).replace(day=1)
        months.append((dt.year, dt.month))
    months = sorted(set(months))

    records = []
    for year, month in months:
        try:
            if market == "上市":
                records.extend(get_twse_month_history(code, year, month))
            else:
                records.extend(get_tpex_month_history(code, year, month))
        except Exception:
            continue

    if not records:
        return pd.DataFrame(columns=["date", "close"])

    df = pd.DataFrame(records)
    df = df.dropna(subset=["close"]).copy()
    # 兼容日期格式
    def parse_any(s):
        s = str(s).strip()
        for fmt in ["%Y/%m/%d", "%Y-%m-%d", "%y/%m/%d"]:
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                pass
        m = re.match(r"(\d{2,3})/(\d{1,2})/(\d{1,2})", s)
        if m:
            y, mo, d = map(int, m.groups())
            y += 1911 if y < 1911 else 0
            try:
                return datetime(y, mo, d)
            except Exception:
                return None
        return None

    df["date"] = df["date"].map(parse_any)
    df = df.dropna(subset=["date"]).sort_values("date")
    return df


@st.cache_data(ttl=600)
def get_google_news(keyword):
    url = f"https://news.google.com/rss/search?q={quote(keyword)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    xml_text = fetch_text(url, headers={"Referer": "https://news.google.com/"})
    root = ET.fromstring(xml_text)
    items = []
    for item in root.findall("./channel/item")[:8]:
        items.append(
            {
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "pubDate": (item.findtext("pubDate") or "").strip(),
            }
        )
    return items


def build_short_term_projection(current_price):
    if current_price is None:
        return pd.DataFrame(columns=["月份", "模擬價"])
    vals = []
    for i in range(1, 13):
        factor = 1 + math.sin(i / 2.2) * 0.04 + (i - 6) * 0.002
        vals.append({"月份": f"{i}月", "模擬價": round(current_price * factor, 2)})
    return pd.DataFrame(vals)


def make_score(change_pct, hist_df, news_count):
    technical = 50
    if change_pct is not None:
        technical += max(-20, min(20, change_pct * 2))
    if not hist_df.empty and len(hist_df) >= 20:
        ma20 = hist_df["close"].tail(20).mean()
        last = hist_df["close"].iloc[-1]
        technical += 10 if last >= ma20 else -10
    technical = max(0, min(100, round(technical)))

    fundamental = 55
    if not hist_df.empty and len(hist_df) >= 240:
        y1 = hist_df["close"].iloc[-1]
        y0 = hist_df["close"].iloc[max(0, len(hist_df) - 240)]
        if y0:
            growth = (y1 - y0) / y0
            fundamental += max(-20, min(20, growth * 40))
    fundamental = max(0, min(100, round(fundamental)))

    industry = max(35, min(85, 45 + min(news_count, 8) * 4))
    overall = round(technical * 0.4 + fundamental * 0.4 + industry * 0.2)
    return overall, technical, fundamental, industry


def summarize_strategy(change_pct, hist_df):
    if hist_df.empty:
        return "資料不足，先觀察成交與新聞變化，避免在資訊不完整時重押。", "資料不足，建議先蒐集基本面與法人動向。"
    last = hist_df["close"].iloc[-1]
    ma20 = hist_df["close"].tail(min(20, len(hist_df))).mean()
    ma60 = hist_df["close"].tail(min(60, len(hist_df))).mean()

    if last >= ma20 >= ma60:
        short = "短線偏強，若量能延續可採分批偏多操作；追價前仍需設好停損。"
    elif last < ma20 < ma60:
        short = "短線偏弱，宜保守應對，優先等待止跌訊號或量縮整理完成。"
    else:
        short = "短線進入整理區，較適合區間思維，避免情緒化追高殺低。"

    if change_pct is not None and change_pct > 3:
        short += " 今日波動偏大，留意隔日獲利了結賣壓。"
    elif change_pct is not None and change_pct < -3:
        short += " 今日跌幅偏大，先觀察是否出現技術性反彈。"

    if last >= ma60:
        long_ = "長線趨勢仍維持相對正向，可搭配分批布局與風險控管。"
    else:
        long_ = "長線趨勢尚未明朗，建議控制持股比重，等待更完整的趨勢確認。"
    return short, long_


def stock_character(score, change_pct):
    if score >= 80:
        title = "攻守兼備型"
        comment = "趨勢與市場關注度同步偏強，但仍要防止高檔震盪帶來的追價風險。"
    elif score >= 65:
        title = "穩健推進型"
        comment = "結構中性偏多，適合用紀律分批方式操作，不宜單次重押。"
    elif score >= 50:
        title = "盤整觀察型"
        comment = "缺乏明確主升段訊號，較適合等待突破或轉強條件出現。"
    else:
        title = "防守警戒型"
        comment = "現階段優先保留彈性，先觀察價格是否止穩與消息面是否改善。"
    if change_pct is not None:
        if change_pct > 4:
            comment += " 今日漲幅偏大，短線情緒明顯升溫。"
        elif change_pct < -4:
            comment += " 今日跌幅偏大，市場風險意識升高。"
    return title, comment


def portfolio_stats(entry_price, shares, current_price):
    if current_price is None:
        return None
    shares = safe_float(shares, 0) or 0
    entry_price = safe_float(entry_price)
    market_value = current_price * shares * 1000
    if entry_price in (None, 0):
        return {
            "shares": shares,
            "market_value": market_value,
            "profit_pct": None,
            "profit_amount": None,
        }
    profit_pct = ((current_price - entry_price) / entry_price) * 100
    profit_amount = (current_price - entry_price) * shares * 1000
    return {
        "shares": shares,
        "market_value": market_value,
        "profit_pct": profit_pct,
        "profit_amount": profit_amount,
    }


def analyze_stock(code, entry_price, shares_count):
    meta = get_company_meta(code)
    quote = get_live_quote(code)
    market = quote["market"] if quote.get("market") != "未知" else meta["market"]
    hist_df = get_history_3y(code, market)
    news = get_google_news(f"{code} {meta['name']} 台股")
    score, technical, fundamental, industry = make_score(quote.get("change_pct"), hist_df, len(news))
    short_term, long_term = summarize_strategy(quote.get("change_pct"), hist_df)
    title, comment = stock_character(score, quote.get("change_pct"))
    pf = portfolio_stats(entry_price, shares_count, quote.get("price"))

    quarter_df = pd.DataFrame(columns=["label", "price"])
    if not hist_df.empty:
        tmp = hist_df.set_index("date").resample("Q").last().dropna().tail(12).reset_index()
        quarter_df = pd.DataFrame(
            {
                "label": tmp["date"].dt.strftime("%Y Q") + (((tmp["date"].dt.month - 1) // 3) + 1).astype(str),
                "price": tmp["close"].round(2),
            }
        )

    return {
        "meta": meta,
        "quote": quote,
        "history": hist_df,
        "quarter": quarter_df,
        "short_projection": build_short_term_projection(quote.get("price")),
        "news": news,
        "score": score,
        "score_breakdown": {
            "technical": technical,
            "fundamental": fundamental,
            "industry": industry,
        },
        "short_term": short_term,
        "long_term": long_term,
        "stock_character": {"title": title, "comment": comment},
        "portfolio": pf,
    }


def show_portfolio(pf):
    if not pf:
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("持有張數", f"{pf['shares']:.2f}")
    c2.metric("市值", f"NT$ {pf['market_value']:,.0f}")
    if pf["profit_pct"] is None:
        c3.metric("損益", "未提供成本")
    else:
        c3.metric("損益", f"{pf['profit_pct']:+.2f}%", delta=f"NT$ {pf['profit_amount']:,.0f}")


st.markdown("# 台股兵策 PRO｜免 API Key 版")
st.caption("即時行情改用台灣公開行情來源；新聞改用 Google News RSS。若外部站台暫時異常，請稍後重試。")

with st.sidebar:
    st.header("查詢條件")
    code = st.text_input("台股代碼", value="2330").strip()
    entry_price = st.text_input("成本價", value="")
    shares_count = st.text_input("張數", value="")
    scan = st.button("執行戰略掃描", type="primary", use_container_width=True)
    st.markdown("---")
    st.caption("不需要設定 Gemini / Yahoo API Key。")

if "last_code" not in st.session_state:
    st.session_state.last_code = "2330"

if scan or st.session_state.get("analysis") is None or code != st.session_state.last_code:
    with st.spinner("正在彙整公開行情、歷史走勢與新聞..."):
        try:
            analysis = analyze_stock(code, entry_price, shares_count)
            st.session_state.analysis = analysis
            st.session_state.last_code = code
            st.session_state.last_error = None
        except Exception as e:
            st.session_state.last_error = f"戰略掃描失敗：{e}"

if st.session_state.get("last_error"):
    st.error(st.session_state.last_error)

analysis = st.session_state.get("analysis")
if analysis:
    meta = analysis["meta"]
    quote = analysis["quote"]

    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    c1.subheader(f"{meta['name']}（{code}）")
    c1.caption(f"市場：{quote.get('market', meta['market'])}｜產業：{meta['industry'] or '未分類'}")
    c2.metric("現價", f"{quote['price']:.2f}")
    change_txt = "--" if quote.get("change_pct") is None else f"{quote['change_pct']:+.2f}%"
    c3.metric("漲跌幅", change_txt)
    c4.metric("戰略評分", str(analysis["score"]))

    show_portfolio(analysis["portfolio"])

    st.markdown("---")
    left, right = st.columns([1.2, 1])
    with left:
        st.markdown("### 三年戰略走勢")
        if not analysis["history"].empty:
            chart_df = analysis["history"].copy().set_index("date")[["close"]]
            st.line_chart(chart_df)
        else:
            st.info("暫無足夠歷史資料。")

        st.markdown("### 近期模擬")
        st.area_chart(analysis["short_projection"].set_index("月份"))

    with right:
        st.markdown("### 股性診斷")
        st.info(f"**{analysis['stock_character']['title']}**\n\n{analysis['stock_character']['comment']}")

        st.markdown("### 評分拆解")
        score_df = pd.DataFrame(
            {
                "項目": ["技術面", "基本面", "產業面"],
                "分數": [
                    analysis["score_breakdown"]["technical"],
                    analysis["score_breakdown"]["fundamental"],
                    analysis["score_breakdown"]["industry"],
                ],
            }
        ).set_index("項目")
        st.bar_chart(score_df)

    c5, c6 = st.columns(2)
    c5.markdown("### 短期戰術指令")
    c5.write(analysis["short_term"])
    c6.markdown("### 長期戰略展望")
    c6.write(analysis["long_term"])

    st.markdown("### 最新新聞彙整")
    if analysis["news"]:
        for item in analysis["news"]:
            st.markdown(f"- [{item['title']}]({item['link']})")
    else:
        st.info("目前查無新聞資料。")

    st.markdown("---")
    st.caption("本工具僅供資訊整理與研究參考，不構成任何投資建議。")
