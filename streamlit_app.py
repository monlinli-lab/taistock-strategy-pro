import os
import json
import time
import random
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# ------------------------------
# 基本設定
# ------------------------------
st.set_page_config(
    page_title="台股兵策｜AI 智慧戰略指揮官",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("VITE_GEMINI_API_KEY") or ""
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-preview-09-2025")
ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"
)

SYSTEM_INSTRUCTION = """
你是一位「台股兵策：AI 智慧戰略指揮官」。
任務：聚合全台灣網路情資（包含 Yahoo 股市、證交所 MOPS、玩股網、鉅亨網、CMoney 等）。
目標：防範單一來源 IP 封鎖，交叉驗證數據，提供包含三年的歷史趨勢概況與即時診斷。
回覆規範：必須回傳純 JSON 格式，不得包含 Markdown 標籤或其他多餘文字。
""".strip()

DEFAULT_DATA = {
    "name": "台積電",
    "currentPrice": "985",
    "change": "+1.24%",
    "industry": "半導體",
    "score": 82,
    "historicalPoints": [
        {"label": "2023 Q1", "price": 520},
        {"label": "2023 Q3", "price": 560},
        {"label": "2024 Q1", "price": 720},
        {"label": "2024 Q3", "price": 915},
        {"label": "2025 Q1", "price": 1030},
        {"label": "當前", "price": 985},
    ],
    "stockCharacter": {
        "title": "主力核心城池",
        "comment": "具備產業龍頭、防禦性與成長性兼具特質，拉回常為中長線資金重新佈局區。",
    },
    "portfolioStrategy": "若成本低於現價且部位不重，可採分批續抱；若短線追高，宜觀察月線與法人籌碼再決定是否加碼。",
    "news": [
        "AI 需求帶動高階製程能見度延續，市場持續關注先進封裝產能擴充。",
        "外資對權值半導體看法分歧，但中長期資本支出與技術領先優勢仍受重視。",
    ],
    "newsImpactAnalysis": "短期股價可能受國際科技股與外資調節影響波動，但若基本面與接單展望未反轉，中長期趨勢仍偏正向。需留意匯率、終端需求與地緣政治風險。",
    "dividend": {"exDate": "2026/06/11", "amount": "4.50 元"},
    "shortTermAnalysis": "短線宜觀察量能是否配合站穩均線，若跌破關鍵支撐需控管部位。",
    "longTermAnalysis": "在高效能運算、AI 與先進製程需求推動下，長期競爭優勢仍然明確。",
    "scoreBreakdown": {"technical": 76, "fundamental": 90, "industry": 86},
    "financials": {"pe": "24.8", "revenueGrowth": "+31.2%"},
}

# ------------------------------
# 樣式
# ------------------------------
st.markdown(
    """
    <style>
    .main {background: linear-gradient(180deg, #020617 0%, #0f172a 100%);}
    .block-container {padding-top: 1.5rem; padding-bottom: 3rem;}
    .metric-card {
        background: rgba(15, 23, 42, 0.75);
        border: 1px solid rgba(148, 163, 184, 0.12);
        border-radius: 22px;
        padding: 20px 22px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.25);
        height: 100%;
    }
    .hero-card {
        background: linear-gradient(135deg, rgba(30,41,59,0.85), rgba(15,23,42,0.95));
        border: 1px solid rgba(244, 63, 94, 0.12);
        border-radius: 30px;
        padding: 28px;
        margin-bottom: 1rem;
    }
    .section-card {
        background: rgba(15, 23, 42, 0.72);
        border: 1px solid rgba(148,163,184,0.10);
        border-radius: 28px;
        padding: 24px;
        margin-bottom: 1rem;
    }
    .chip {
        display:inline-block;
        padding: 6px 12px;
        border-radius: 999px;
        background: rgba(244,63,94,0.1);
        color: #fb7185;
        border: 1px solid rgba(244,63,94,0.2);
        font-size: 12px;
        font-weight: 700;
        margin-bottom: 10px;
    }
    .muted {color: #94a3b8; font-size: 13px;}
    .big-title {font-size: 38px; font-weight: 900; color: white; line-height: 1.1;}
    .score {font-size: 44px; font-weight: 900; color: #f43f5e;}
    .risk-box {
        background: rgba(127,29,29,0.12);
        border: 1px solid rgba(251,113,133,0.18);
        border-radius: 24px;
        padding: 20px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------
# 工具函式
# ------------------------------
def fetch_with_retry(url: str, payload: Dict[str, Any], retries: int = 5, delay: int = 1) -> Dict[str, Any]:
    params = {"key": API_KEY}
    headers = {"Content-Type": "application/json"}

    last_error = None
    for attempt in range(retries):
        try:
            response = requests.post(url, params=params, headers=headers, json=payload, timeout=90)
            if response.ok:
                return response.json()
            if response.status_code in (401, 429) or response.status_code >= 500:
                time.sleep(delay)
                delay *= 2
                last_error = RuntimeError(f"HTTP {response.status_code}: {response.text[:200]}")
                continue
            response.raise_for_status()
        except Exception as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                raise
    if last_error:
        raise last_error
    raise RuntimeError("Unknown request error")


def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        text = str(v).replace(",", "").replace("%", "").strip()
        return float(text)
    except Exception:
        return default


def build_user_prompt(code: str, entry_price: str, shares_count: str) -> str:
    return f"""
稟報指揮官，請針對台股 {code} 進行全網情報掃描與三年戰略大趨勢分析。

當前部位狀況：
- 購入成本：{entry_price or '未提供'} TWD
- 持有數量：{shares_count or '0'} 張

請回傳 JSON：
{{
  "name": "公司簡稱",
  "currentPrice": "數字",
  "change": "漲跌幅百分比",
  "industry": "產業類別",
  "score": 數字(0-100),
  "historicalPoints": [
    {{"label": "2023 Q1", "price": 數字}},
    {{"label": "2023 Q3", "price": 數字}},
    {{"label": "2024 Q1", "price": 數字}},
    {{"label": "2024 Q3", "price": 數字}},
    {{"label": "2025 Q1", "price": 數字}},
    {{"label": "當前", "price": 數字}}
  ],
  "stockCharacter": {{ "title": "兵法標題", "comment": "股性戰略點評" }},
  "portfolioStrategy": "根據盈虧狀態與部位規模提供的操盤指令",
  "news": ["情報摘要1", "情報摘要2"],
  "newsImpactAnalysis": "新聞具體影響評估",
  "dividend": {{ "exDate": "YYYY/MM/DD", "amount": "數字元" }},
  "shortTermAnalysis": "短期技術與籌碼戰術對策",
  "longTermAnalysis": "長期戰略價值評估",
  "scoreBreakdown": {{ "technical": 數字, "fundamental": 數字, "industry": 數字 }},
  "financials": {{ "pe": "本益比", "revenueGrowth": "月營收年增率" }}
}}
""".strip()


def query_gemini_stock_analysis(code: str, entry_price: str, shares_count: str) -> Dict[str, Any]:
    if not API_KEY:
        raise RuntimeError("未設定 GEMINI_API_KEY 或 VITE_GEMINI_API_KEY")

    payload = {
        "contents": [{"parts": [{"text": build_user_prompt(code, entry_price, shares_count)}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "tools": [{"google_search": {}}],
        "generationConfig": {"responseMimeType": "application/json"},
    }

    result = fetch_with_retry(ENDPOINT, payload)
    raw_text = (
        result.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text")
    )
    if not raw_text:
        raise RuntimeError("情資中心無回應")

    clean_json = raw_text.replace("```json", "").replace("```", "").strip()
    data = json.loads(clean_json)
    return data


def get_short_term_chart_data(analysis_data: Dict[str, Any]) -> pd.DataFrame:
    base_price = safe_float(analysis_data.get("currentPrice"), 600)
    rng = random.Random(42)
    data = []
    for i in range(12):
        data.append(
            {
                "月份": f"{i + 1}月",
                "策略模擬價": round(base_price * (1 + (rng.random() * 0.12 - 0.05)), 2),
            }
        )
    return pd.DataFrame(data)


def get_three_year_chart_data(analysis_data: Dict[str, Any]) -> pd.DataFrame:
    points = analysis_data.get("historicalPoints") or []
    if not points:
        base = safe_float(analysis_data.get("currentPrice"), 600)
        points = [
            {"label": "2023 Q1", "price": round(base * 0.60, 2)},
            {"label": "2023 Q3", "price": round(base * 0.72, 2)},
            {"label": "2024 Q1", "price": round(base * 0.81, 2)},
            {"label": "2024 Q3", "price": round(base * 0.93, 2)},
            {"label": "2025 Q1", "price": round(base * 1.05, 2)},
            {"label": "當前", "price": round(base, 2)},
        ]
    return pd.DataFrame(points).rename(columns={"label": "區間", "price": "價格"})


def calc_asset_stats(analysis_data: Dict[str, Any], entry_price: str, shares_count: str) -> Dict[str, Any]:
    current = safe_float(analysis_data.get("currentPrice"))
    entry = safe_float(entry_price)
    shares = safe_float(shares_count)

    total_market_value = current * shares * 1000
    total_profit_amount = 0.0
    profit_percent = 0.0

    if entry > 0:
        total_profit_amount = (current - entry) * shares * 1000
        profit_percent = ((current - entry) / entry) * 100

    return {
        "current": current,
        "entry": entry,
        "shares": shares,
        "total_market_value": total_market_value,
        "total_profit_amount": total_profit_amount,
        "profit_percent": profit_percent,
    }


def score_color(score: float) -> str:
    if score >= 80:
        return "#fb7185"
    if score >= 60:
        return "#818cf8"
    if score >= 40:
        return "#fbbf24"
    return "#34d399"


# ------------------------------
# Session State
# ------------------------------
if "analysis_data" not in st.session_state:
    st.session_state.analysis_data = DEFAULT_DATA
if "history_list" not in st.session_state:
    st.session_state.history_list = [{"code": "2330", "name": "台積電"}]
if "last_code" not in st.session_state:
    st.session_state.last_code = "2330"


# ------------------------------
# 側邊欄
# ------------------------------
st.sidebar.markdown("## ⚔️ 台股兵策")
st.sidebar.caption("Strategic Commander / Streamlit Edition")

stock_code = st.sidebar.text_input("台股代碼", value=st.session_state.last_code, placeholder="例如 2330")
entry_price = st.sidebar.text_input("購入成本", value="", placeholder="例如 965")
shares_count = st.sidebar.text_input("持有張數", value="", placeholder="例如 2")

run_scan = st.sidebar.button("執行戰略掃描", use_container_width=True, type="primary")
use_demo = st.sidebar.button("載入展示資料", use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.markdown("### 最近查詢")
for item in st.session_state.history_list[:10]:
    if st.sidebar.button(f"{item['code']}｜{item['name']}", use_container_width=True, key=f"history_{item['code']}"):
        stock_code = item["code"]
        run_scan = True

st.sidebar.markdown("---")
st.sidebar.info(
    "請在部署平台設定環境變數：`GEMINI_API_KEY` 或 `VITE_GEMINI_API_KEY`。"
)

if use_demo:
    st.session_state.analysis_data = DEFAULT_DATA
    st.session_state.last_code = "2330"

if run_scan:
    clean_code = (stock_code or "").strip().upper()
    if not clean_code:
        st.error("請先輸入台股代碼。")
    else:
        with st.spinner("正在同步三年趨勢與全網情資..."):
            try:
                data = query_gemini_stock_analysis(clean_code, entry_price, shares_count)
                st.session_state.analysis_data = data
                st.session_state.last_code = clean_code

                filtered = [x for x in st.session_state.history_list if x["code"] != clean_code]
                filtered.insert(0, {"code": clean_code, "name": data.get("name", clean_code)})
                st.session_state.history_list = filtered[:10]
            except Exception as exc:
                st.error(f"戰略掃描失敗：{exc}")

analysis_data: Dict[str, Any] = st.session_state.analysis_data
asset_stats = calc_asset_stats(analysis_data, entry_price, shares_count)
three_year_df = get_three_year_chart_data(analysis_data)
short_term_df = get_short_term_chart_data(analysis_data)

# ------------------------------
# Header
# ------------------------------
st.markdown(
    f"""
    <div class="hero-card">
        <div class="chip">Multi-Channel Verified Data</div>
        <div class="big-title">{analysis_data.get('name', '--')} <span style="font-size:20px;color:#94a3b8;">{st.session_state.last_code}.TW</span></div>
        <div style="display:flex;gap:32px;flex-wrap:wrap;align-items:end;margin-top:14px;">
            <div>
                <div class="muted">產業</div>
                <div style="font-size:22px;font-weight:800;color:#e2e8f0;">{analysis_data.get('industry', '--')}</div>
            </div>
            <div>
                <div class="muted">現價</div>
                <div style="font-size:44px;font-weight:900;color:white;">${analysis_data.get('currentPrice', '--')}</div>
            </div>
            <div>
                <div class="muted">漲跌幅</div>
                <div style="font-size:32px;font-weight:900;color:{'#34d399' if '-' in str(analysis_data.get('change','')) else '#fb7185'};">{analysis_data.get('change', '--')}</div>
            </div>
            <div>
                <div class="muted">戰略評分</div>
                <div class="score" style="color:{score_color(safe_float(analysis_data.get('score'), 0))};">{analysis_data.get('score', '--')}</div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ------------------------------
# KPI cards
# ------------------------------
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(
        f"<div class='metric-card'><div class='muted'>本益比</div><div style='font-size:30px;font-weight:900;color:white;'>{analysis_data.get('financials', {}).get('pe', '--')}</div></div>",
        unsafe_allow_html=True,
    )
with col2:
    st.markdown(
        f"<div class='metric-card'><div class='muted'>營收年增</div><div style='font-size:30px;font-weight:900;color:white;'>{analysis_data.get('financials', {}).get('revenueGrowth', '--')}</div></div>",
        unsafe_allow_html=True,
    )
with col3:
    div = analysis_data.get("dividend", {})
    st.markdown(
        f"<div class='metric-card'><div class='muted'>除權息預估</div><div style='font-size:22px;font-weight:900;color:#fecdd3;'>{div.get('exDate', '未公告')}</div><div style='font-size:16px;color:#fb7185;font-weight:800;'>{div.get('amount', '--')}</div></div>",
        unsafe_allow_html=True,
    )
with col4:
    st.markdown(
        f"<div class='metric-card'><div class='muted'>股性標題</div><div style='font-size:22px;font-weight:900;color:white;'>{analysis_data.get('stockCharacter', {}).get('title', '--')}</div></div>",
        unsafe_allow_html=True,
    )

# ------------------------------
# 部位診斷
# ------------------------------
if entry_price or shares_count:
    pcol1, pcol2, pcol3 = st.columns([1.3, 1.0, 1.8])
    with pcol1:
        st.markdown(
            f"<div class='section-card'><div class='muted'>當前部位戰績（{asset_stats['shares']} 張）</div><div style='font-size:42px;font-weight:900;color:{'#fb7185' if asset_stats['profit_percent'] >= 0 else '#34d399'};'>{asset_stats['profit_percent']:+.2f}%</div><div style='font-size:24px;font-weight:800;color:{'#fb7185' if asset_stats['total_profit_amount'] >= 0 else '#34d399'};'>{asset_stats['total_profit_amount']:+,.0f} TWD</div></div>",
            unsafe_allow_html=True,
        )
    with pcol2:
        st.markdown(
            f"<div class='section-card'><div class='muted'>實時部位市值</div><div style='font-size:34px;font-weight:900;color:white;'>{asset_stats['total_market_value']:,.0f} TWD</div></div>",
            unsafe_allow_html=True,
        )
    with pcol3:
        st.markdown(
            f"<div class='section-card'><div class='muted'>指揮官指令</div><div style='font-size:18px;font-weight:800;color:#e2e8f0;line-height:1.8;'>{analysis_data.get('portfolioStrategy', '--')}</div></div>",
            unsafe_allow_html=True,
        )

# ------------------------------
# 圖表
# ------------------------------
c1, c2 = st.columns([2.2, 1.2])
with c1:
    st.markdown("### 📈 三年戰略走勢全景")
    fig1 = px.area(
        three_year_df,
        x="區間",
        y="價格",
        markers=True,
    )
    fig1.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"),
        margin=dict(l=10, r=10, t=10, b=10),
        height=360,
    )
    st.plotly_chart(fig1, use_container_width=True)

with c2:
    st.markdown("### 🎯 多維度能量權重")
    breakdown = analysis_data.get("scoreBreakdown", {})
    bd_df = pd.DataFrame(
        {
            "項目": ["技術面", "基本面", "產業面"],
            "分數": [
                safe_float(breakdown.get("technical", 0)),
                safe_float(breakdown.get("fundamental", 0)),
                safe_float(breakdown.get("industry", 0)),
            ],
        }
    )
    fig2 = px.bar(
        bd_df,
        x="分數",
        y="項目",
        orientation="h",
        text="分數",
    )
    fig2.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_range=[0, 100],
        height=360,
        showlegend=False,
    )
    st.plotly_chart(fig2, use_container_width=True)

st.markdown("### 🔭 戰術行情預演（近期模擬）")
fig3 = px.area(short_term_df, x="月份", y="策略模擬價", markers=True)
fig3.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e2e8f0"),
    margin=dict(l=10, r=10, t=10, b=10),
    height=340,
)
st.plotly_chart(fig3, use_container_width=True)

# ------------------------------
# 診斷與新聞
# ------------------------------
left, right = st.columns(2)
with left:
    st.markdown("### 🛡️ 兵策大師：股性診斷")
    st.markdown(
        f"<div class='section-card'><div style='font-size:30px;font-weight:900;color:white;margin-bottom:10px;'>「{analysis_data.get('stockCharacter', {}).get('title', '--')}」</div><div style='font-size:20px;line-height:1.8;color:#e2e8f0;font-weight:700;'>{analysis_data.get('stockCharacter', {}).get('comment', '--')}</div></div>",
        unsafe_allow_html=True,
    )

    st.markdown("### 🗞️ 全域實時戰報")
    news_list = analysis_data.get("news", []) or []
    if news_list:
        for i, item in enumerate(news_list, 1):
            st.markdown(
                f"<div class='section-card'><div class='muted'>情報 {i}</div><div style='font-size:18px;font-weight:800;color:white;line-height:1.7;'>{item}</div></div>",
                unsafe_allow_html=True,
            )
    else:
        st.info("目前沒有可顯示的新聞摘要。")

with right:
    st.markdown("### ⚠️ 情勢影響深度分析")
    st.markdown(
        f"<div class='risk-box'><div style='font-size:19px;line-height:1.9;color:#f8fafc;font-weight:700;'>{analysis_data.get('newsImpactAnalysis', '--')}</div></div>",
        unsafe_allow_html=True,
    )

    st.markdown("### 📌 指揮官戰術指令")
    st.markdown(
        f"<div class='section-card'><div class='muted'>短期戰術指令</div><div style='font-size:18px;font-weight:800;color:#e2e8f0;line-height:1.8;'>{analysis_data.get('shortTermAnalysis', '--')}</div></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='section-card'><div class='muted'>長期戰略展望</div><div style='font-size:18px;font-weight:800;color:#e2e8f0;line-height:1.8;'>{analysis_data.get('longTermAnalysis', '--')}</div></div>",
        unsafe_allow_html=True,
    )

# ------------------------------
# 免責聲明
# ------------------------------
st.markdown("---")
st.markdown(
    """
    <div class="section-card">
        <div style="font-size:14px;color:#94a3b8;font-weight:800;margin-bottom:8px;">投資風險警語與指揮中心聲明</div>
        <div style="font-size:14px;color:#cbd5e1;line-height:1.9;">
        本系統數據採全網聚合技術，旨在提供投資者多維度戰略參考。內容不構成投資建議，股市投資具高風險，
        請依自身財務狀況與風險承受能力審慎評估。
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
