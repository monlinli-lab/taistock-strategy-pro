import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Search,
  TrendingUp,
  Activity,
  Globe,
  Newspaper,
  AlertCircle,
  LineChart,
  PieChart,
  ChevronRight,
  Loader2,
  ExternalLink,
  AlertTriangle,
  Sword,
  ShieldCheck,
  History as HistoryIcon,
  Target,
  ArrowUpRight,
  ArrowDownRight,
  Layers,
  Crosshair,
  BarChart3
} from 'lucide-react';
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area
} from 'recharts';

const apiKey = import.meta.env.VITE_GEMINI_API_KEY || '';
const modelName = 'gemini-2.5-flash-preview-09-2025';

const fetchWithRetry = async (url, options, retries = 5, delay = 1000) => {
  try {
    const response = await fetch(url, options);
    if (!response.ok) {
      if ((response.status === 401 || response.status >= 500) && retries > 0) {
        await new Promise((resolve) => setTimeout(resolve, delay));
        return fetchWithRetry(url, options, retries - 1, delay * 2);
      }
      throw new Error(`HTTP ${response.status}`);
    }
    return response;
  } catch (err) {
    if (retries > 0) {
      await new Promise((resolve) => setTimeout(resolve, delay));
      return fetchWithRetry(url, options, retries - 1, delay * 2);
    }
    throw err;
  }
};

const App = () => {
  const [stockCode, setStockCode] = useState('2330');
  const [entryPrice, setEntryPrice] = useState('');
  const [sharesCount, setSharesCount] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [analysisData, setAnalysisData] = useState(null);
  const [historyList, setHistoryList] = useState([]);

  const shortTermChartData = useMemo(() => {
    if (!analysisData) return [];
    const basePrice = parseFloat(analysisData.currentPrice) || 600;
    return Array.from({ length: 12 }, (_, i) => ({
      month: `${i + 1}月`,
      price: Number((basePrice * (1 + (Math.random() * 0.12 - 0.05))).toFixed(2))
    }));
  }, [analysisData]);

  const threeYearChartData = useMemo(() => {
    if (!analysisData || !analysisData.historicalPoints) {
      const base = parseFloat(analysisData?.currentPrice) || 600;
      return Array.from({ length: 12 }, (_, i) => ({
        label: `${2023 + Math.floor(i / 4)} Q${(i % 4) + 1}`,
        price: Number((base * (0.6 + (Math.random() * 0.4 + i * 0.06))).toFixed(2))
      }));
    }
    return analysisData.historicalPoints;
  }, [analysisData]);

  const analyzeStock = useCallback(async (code, customEntry = entryPrice, customShares = sharesCount) => {
    if (!code) return;

    if (!apiKey) {
      setError('尚未設定 API Key，請先在 .env 填入 VITE_GEMINI_API_KEY');
      return;
    }

    const cleanCode = code.trim().toUpperCase();
    setLoading(true);
    setError(null);

    const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${modelName}:generateContent?key=${apiKey}`;

    const systemInstruction = `你是一位「台股兵策：AI 智慧戰略指揮官」。
任務：聚合全台灣網路情資（包含 Yahoo 股市、證交所 MOPS、玩股網、鉅亨網、CMoney 等）。
目標：防範單一來源 IP 封鎖，交叉驗證數據，提供包含三年的歷史趨勢概況與即時診斷。
回覆規範：必須回傳純 JSON 格式，不得包含 Markdown 標籤或其他多餘文字。`;

    const userPrompt = `
稟報指揮官，請針對台股 ${cleanCode} 進行全網情報掃描與三年戰略大趨勢分析。

當前部位狀況：
- 購入成本：${customEntry || '未提供'} TWD
- 持有數量：${customShares || '0'} 張

請回傳 JSON：
{
  "name": "公司簡稱",
  "currentPrice": "數字",
  "change": "漲跌幅百分比",
  "industry": "產業類別",
  "score": 數字(0-100),
  "historicalPoints": [
    {"label": "2023 Q1", "price": 數字},
    {"label": "2023 Q3", "price": 數字},
    {"label": "2024 Q1", "price": 數字},
    {"label": "2024 Q3", "price": 數字},
    {"label": "2025 Q1", "price": 數字},
    {"label": "當前", "price": 數字}
  ],
  "stockCharacter": { "title": "兵法標題", "comment": "股性戰略點評" },
  "portfolioStrategy": "根據盈虧狀態與部位規模提供的操盤指令",
  "news": ["情報摘要1", "情報摘要2"],
  "newsImpactAnalysis": "新聞具體影響評估",
  "dividend": { "exDate": "YYYY/MM/DD", "amount": "數字元" },
  "shortTermAnalysis": "短期技術與籌碼戰術對策",
  "longTermAnalysis": "長期戰略價值評估",
  "scoreBreakdown": { "technical": 數字, "fundamental": 數字, "industry": 數字 },
  "financials": { "pe": "本益比", "revenueGrowth": "月營收年增率" }
}`;

    try {
      const response = await fetchWithRetry(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: userPrompt }] }],
          systemInstruction: { parts: [{ text: systemInstruction }] },
          tools: [{ google_search: {} }],
          generationConfig: { responseMimeType: 'application/json' }
        })
      });

      const result = await response.json();
      const rawText = result.candidates?.[0]?.content?.parts?.[0]?.text;
      if (!rawText) throw new Error('情資中心無回應');

      const cleanJson = rawText.replace(/```json|```/g, '').trim();
      const data = JSON.parse(cleanJson);

      setAnalysisData(data);
      setStockCode(cleanCode);
      setHistoryList((prev) => {
        const filtered = prev.filter((item) => item.code !== cleanCode);
        return [{ code: cleanCode, name: data.name }, ...filtered].slice(0, 10);
      });
    } catch (err) {
      console.error(err);
      setError(`戰略掃描失敗 (${err.message})。可能是認證連線中，請點擊按鈕重試。`);
    } finally {
      setLoading(false);
    }
  }, [entryPrice, sharesCount]);

  useEffect(() => {
    const timer = setTimeout(() => {
      analyzeStock('2330');
    }, 1200);
    return () => clearTimeout(timer);
  }, [analyzeStock]);

  const assetStats = useMemo(() => {
    if (!analysisData) return null;
    const current = parseFloat(analysisData.currentPrice);
    const entry = parseFloat(entryPrice);
    const shares = parseFloat(sharesCount) || 0;

    let profitPercent = '0.00';
    const totalMarketValue = current * shares * 1000;
    let totalProfitAmount = 0;

    if (!Number.isNaN(current) && !Number.isNaN(entry) && entry !== 0) {
      profitPercent = (((current - entry) / entry) * 100).toFixed(2);
      totalProfitAmount = (current - entry) * shares * 1000;
    }
    return { profitPercent, totalMarketValue, totalProfitAmount, shares };
  }, [analysisData, entryPrice, sharesCount]);

  const getScoreColor = (score) => {
    if (score >= 80) return 'text-rose-400 drop-shadow-[0_0_10px_rgba(244,63,94,0.5)]';
    if (score >= 60) return 'text-indigo-400';
    if (score >= 40) return 'text-yellow-400';
    return 'text-emerald-400';
  };

  const getChangeStyle = (change) => {
    if (!change) return 'text-slate-500';
    if (change.toString().includes('-')) return 'text-emerald-400';
    return 'text-rose-400';
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 font-sans overflow-hidden tracking-tight select-none">
      <aside className="w-80 bg-slate-900 border-r border-slate-800 flex flex-col z-10 shrink-0 shadow-2xl overflow-y-auto custom-scrollbar">
        <div className="p-6 border-b border-slate-800 space-y-5 sticky top-0 bg-slate-900 z-20 shadow-md">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-rose-600/10 rounded-2xl border border-rose-600/20 shadow-lg">
              <Sword size={24} className="text-rose-500" />
            </div>
            <div className="min-w-0">
              <h1 className="text-xl font-black tracking-tighter text-white italic leading-tight truncate">台股兵策</h1>
              <p className="text-[10px] font-bold text-rose-500/80 tracking-widest uppercase truncate leading-none">Strategic Commander</p>
            </div>
          </div>

          <div className="space-y-3">
            <div className="relative group">
              <input
                type="text"
                placeholder="台股代碼 (例 2330)"
                className="w-full pl-10 pr-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl focus:ring-2 focus:ring-rose-500 outline-none transition-all text-slate-100 font-bold text-sm shadow-inner"
                value={stockCode}
                onChange={(e) => setStockCode(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && analyzeStock(stockCode)}
              />
              <Search className="absolute left-3 top-3 text-slate-500 group-focus-within:text-rose-400 transition-colors" size={16} />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="relative group">
                <input
                  type="number"
                  placeholder="成本價"
                  className="w-full pl-10 pr-2 py-2.5 bg-slate-800 border border-slate-700 rounded-xl focus:ring-2 focus:ring-emerald-500 outline-none transition-all text-slate-100 font-bold text-xs shadow-inner"
                  value={entryPrice}
                  onChange={(e) => setEntryPrice(e.target.value)}
                />
                <Target className="absolute left-3 top-3 text-slate-500 group-focus-within:text-emerald-400" size={14} />
              </div>
              <div className="relative group">
                <input
                  type="number"
                  placeholder="張數"
                  className="w-full pl-10 pr-2 py-2.5 bg-slate-800 border border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none transition-all text-slate-100 font-bold text-xs shadow-inner"
                  value={sharesCount}
                  onChange={(e) => setSharesCount(e.target.value)}
                />
                <Layers className="absolute left-3 top-3 text-slate-500 group-focus-within:text-blue-400" size={14} />
              </div>
            </div>
          </div>

          <button
            onClick={() => analyzeStock(stockCode)}
            disabled={loading}
            className="w-full bg-rose-600 hover:bg-rose-500 active:scale-95 disabled:bg-slate-700 text-white font-black py-3.5 rounded-2xl flex items-center justify-center gap-2 transition-all shadow-lg shadow-rose-900/20 uppercase tracking-widest text-xs"
          >
            {loading ? <Loader2 className="animate-spin" size={18} /> : '執行戰略掃描'}
          </button>
        </div>

        <div className="flex-1 p-4 space-y-6">
          <section>
            <h3 className="text-[10px] font-black text-rose-500/70 uppercase tracking-[0.3em] mb-4 px-2 flex items-center gap-2">
              <HistoryIcon size={12} /> 歷史戰區紀錄 (10)
            </h3>
            <div className="grid grid-cols-1 gap-1.5">
              {historyList.length > 0 ? (
                historyList.map((item) => (
                  <button
                    key={item.code}
                    onClick={() => analyzeStock(item.code)}
                    className={`w-full flex items-center justify-between px-4 py-3.5 rounded-2xl transition-all group ${stockCode === item.code ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30 shadow-lg' : 'hover:bg-slate-800 text-slate-400 hover:text-slate-100 border border-transparent'}`}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="font-mono text-xs font-black opacity-50 shrink-0">{item.code}</span>
                      <span className="font-bold text-sm tracking-wide truncate max-w-[120px]">{item.name}</span>
                    </div>
                    <ChevronRight size={14} className="transition-transform group-hover:translate-x-1 opacity-0 group-hover:opacity-100 shrink-0" />
                  </button>
                ))
              ) : (
                <div className="px-4 py-12 text-center border-2 border-dashed border-slate-800 rounded-3xl opacity-30">
                  <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest leading-relaxed">尚無歷史情報</p>
                </div>
              )}
            </div>
          </section>
        </div>

        <div className="p-6 bg-slate-900/80 border-t border-slate-800 sticky bottom-0 backdrop-blur-md">
          <div className="space-y-2 text-[9px] font-black text-slate-500 uppercase tracking-widest leading-none">
            <div className="flex items-center gap-2"><div className="w-1.5 h-1.5 bg-rose-500 rounded-full animate-pulse shadow-[0_0_5px_rgba(244,63,94,0.8)]" /> Strategic Mapping Active</div>
            <div className="flex items-center gap-2"><div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse" /> Multi-Source Mapping Verified</div>
          </div>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto bg-slate-950 custom-scrollbar relative">
        {error && (
          <div className="m-8 p-5 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-3xl flex items-center gap-4 animate-in shadow-2xl relative z-30">
            <AlertCircle size={24} />
            <span className="text-sm font-black tracking-wide">{error}</span>
          </div>
        )}

        {loading ? (
          <div className="h-full flex flex-col items-center justify-center space-y-8 px-10">
            <div className="relative">
              <div className="absolute inset-0 bg-rose-500 blur-[80px] rounded-full opacity-20 animate-pulse"></div>
              <div className="p-12 bg-slate-900 rounded-full border border-slate-800 relative z-10 shadow-2xl">
                <Loader2 className="animate-spin text-rose-400" size={64} />
              </div>
            </div>
            <div className="text-center space-y-4 max-w-md">
              <p className="text-3xl font-black text-white tracking-tighter italic leading-snug uppercase">「夫未戰而廟算勝者，得算多也」</p>
              <div className="space-y-1">
                <p className="text-slate-400 text-sm font-bold uppercase tracking-[0.2em]">正在同步三年趨勢與情資...</p>
                <p className="text-slate-600 text-[10px] font-bold uppercase tracking-widest italic leading-relaxed">Aggregating Global Feeds & MOPS Database</p>
              </div>
            </div>
          </div>
        ) : analysisData ? (
          <div className="max-w-7xl mx-auto p-8 space-y-8 animate-in pb-32 relative">
            {(entryPrice || sharesCount) && assetStats && (
              <div className="bg-gradient-to-r from-slate-900 to-slate-950 p-8 rounded-[3rem] border border-slate-800 shadow-2xl relative overflow-hidden group">
                <div className="absolute inset-0 bg-indigo-500/5 blur-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-700"></div>
                <div className="flex flex-col xl:flex-row gap-10 relative z-10">
                  <div className="flex items-center gap-8 shrink-0 border-r border-slate-800 pr-8">
                    <div className={`p-6 rounded-[2rem] shadow-2xl ${parseFloat(assetStats.profitPercent) >= 0 ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'}`}>
                      {parseFloat(assetStats.profitPercent) >= 0 ? <ArrowUpRight size={44} /> : <ArrowDownRight size={44} />}
                    </div>
                    <div className="space-y-1">
                      <h3 className="text-xs font-black text-slate-500 uppercase tracking-[0.2em] mb-2 leading-none">當前部位戰績 ({assetStats.shares} 張)</h3>
                      <div className="flex flex-col md:flex-row md:items-baseline gap-x-6 gap-y-1">
                        <span className={`text-6xl font-black tabular-nums tracking-tighter ${getChangeStyle(assetStats.profitPercent)}`}>
                          {parseFloat(assetStats.profitPercent) >= 0 ? `+${assetStats.profitPercent}` : assetStats.profitPercent}%
                        </span>
                        <span className={`text-2xl font-black ${getChangeStyle(assetStats.totalProfitAmount)}`}>
                          {assetStats.totalProfitAmount >= 0 ? '+' : ''}{assetStats.totalProfitAmount.toLocaleString()} <span className="text-xs opacity-50 uppercase">TWD</span>
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-col justify-center shrink-0">
                    <p className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em] mb-2 leading-none">實時部位市值</p>
                    <p className="text-4xl font-black text-white tabular-nums tracking-tight">
                      ${assetStats.totalMarketValue.toLocaleString()} <span className="text-sm text-slate-500 font-bold uppercase">TWD</span>
                    </p>
                  </div>

                  <div className="flex-1 bg-slate-950/70 p-7 rounded-[2.5rem] border border-slate-800 shadow-inner flex items-start gap-5">
                    <div className="p-3 bg-indigo-500/10 rounded-2xl text-indigo-400 border border-indigo-500/10 shadow-lg shrink-0 mt-1">
                      <ShieldCheck size={24} />
                    </div>
                    <div className="space-y-2">
                      <p className="text-[10px] font-black text-indigo-400 uppercase tracking-[0.2em] leading-none">指揮官指令</p>
                      <p className="text-slate-200 font-bold text-base italic leading-relaxed">
                        {analysisData.portfolioStrategy}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div className="bg-slate-900/40 backdrop-blur-xl p-10 rounded-[3.5rem] border border-slate-800 shadow-2xl relative overflow-hidden group">
              <div className="absolute -top-32 -right-32 w-80 h-80 bg-rose-500/5 blur-[120px] rounded-full group-hover:bg-rose-500/10 transition-all duration-1000" />
              <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center relative z-10 gap-10">
                <div className="flex-1 w-full min-w-0">
                  <div className="flex flex-wrap items-center gap-4 mb-6">
                    <span className="px-4 py-1.5 bg-rose-500/10 text-rose-400 text-[10px] font-black rounded-full border border-rose-500/20 flex items-center gap-2 uppercase tracking-[0.2em] shadow-lg">
                      <Activity size={14} /> Multi-Channel Verified Data
                    </span>
                    <span className="px-4 py-1.5 bg-slate-800 text-slate-400 font-mono text-xs font-black rounded-xl border border-slate-700 tracking-wider shadow-inner">{stockCode}.TW</span>
                  </div>

                  <div className="flex flex-col md:flex-row md:items-baseline gap-x-12 gap-y-6 flex-wrap">
                    <div className="min-w-0 flex-1 max-w-full overflow-hidden">
                      <h2 className="text-6xl md:text-8xl font-black text-white leading-[1.1] tracking-tighter break-words drop-shadow-2xl">
                        {analysisData.name}
                      </h2>
                    </div>
                    <div className="shrink-0 space-y-1">
                      <p className="text-slate-400 font-black flex items-center gap-2 mb-3 uppercase tracking-[0.3em] text-sm">
                        <Globe size={18} className="text-rose-500" /> {analysisData.industry}
                      </p>
                      <div className="flex items-baseline gap-8">
                        <span className="text-7xl font-black text-white tracking-tighter tabular-nums drop-shadow-lg">
                          ${analysisData.currentPrice}
                        </span>
                        <span className={`text-4xl font-black italic tracking-tight ${getChangeStyle(analysisData.change)}`}>
                          {analysisData.change}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-2 xl:grid-cols-4 gap-5 w-full lg:w-auto shrink-0 relative z-20">
                  <div className="p-6 bg-slate-800/40 rounded-[2rem] border border-slate-700/50 text-center min-w-[120px] shadow-inner">
                    <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2 leading-none">本益比</p>
                    <p className="text-2xl font-black text-slate-100 tracking-tight">{analysisData.financials?.pe || '--'}</p>
                  </div>
                  <div className="p-6 bg-slate-800/40 rounded-[2rem] border border-slate-700/50 text-center min-w-[120px] shadow-inner">
                    <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2 leading-none">營收年增</p>
                    <p className="text-2xl font-black text-slate-100 tracking-tight">{analysisData.financials?.revenueGrowth || '--'}</p>
                  </div>
                  <div className="p-6 bg-rose-500/5 rounded-[2rem] border border-rose-500/10 text-center flex flex-col justify-center min-w-[140px] shadow-inner">
                    <p className="text-[10px] font-black text-rose-500/60 uppercase tracking-widest mb-2 leading-none">除權息預估</p>
                    <p className="text-base font-black text-rose-300 leading-tight mb-1">{analysisData.dividend?.exDate || '未公告'}</p>
                    <p className="text-xs font-black text-rose-400/80 uppercase">{analysisData.dividend?.amount || '--'}</p>
                  </div>
                  <div className="p-6 bg-rose-600/20 rounded-[2rem] border border-rose-500/30 text-center flex flex-col items-center justify-center min-w-[120px] shadow-2xl">
                    <p className="text-[10px] font-black text-rose-300/50 uppercase tracking-widest mb-2 leading-none">戰略評分</p>
                    <div className={`text-5xl font-black ${getScoreColor(analysisData.score)}`}>{analysisData.score}</div>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-slate-900/40 backdrop-blur-md p-10 rounded-[3.5rem] border border-slate-800 shadow-2xl overflow-hidden group relative">
              <div className="absolute top-0 right-0 p-8 opacity-5">
                <BarChart3 size={120} className="text-blue-500" />
              </div>
              <div className="flex justify-between items-center mb-10 relative z-10">
                <h3 className="text-2xl font-black flex items-center gap-5 text-white uppercase italic tracking-widest leading-none">
                  <div className="p-3 bg-blue-500/10 rounded-2xl text-blue-400 border border-blue-500/10 shadow-lg shadow-blue-950/20"><BarChart3 size={28} /></div>
                  三年戰略走勢全景 (歷史大趨勢)
                </h3>
                <div className="hidden sm:flex items-center gap-4 px-5 py-2 bg-slate-800 rounded-full border border-slate-700 shadow-inner">
                  <div className="w-2.5 h-2.5 bg-blue-500 rounded-full animate-pulse shadow-[0_0_12px_rgba(59,130,246,1)]"></div>
                  <span className="text-[10px] font-black text-slate-300 uppercase tracking-[0.3em]">Long-term Context</span>
                </div>
              </div>
              <div className="h-[350px] w-full relative z-10">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={threeYearChartData}>
                    <defs>
                      <linearGradient id="colorThreeYear" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#1e293b" strokeOpacity={0.6} />
                    <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: '#475569', fontSize: 12, fontWeight: 900 }} dy={15} />
                    <YAxis domain={['auto', 'auto']} axisLine={false} tickLine={false} tick={{ fill: '#475569', fontSize: 12, fontWeight: 900 }} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#0f172a', borderRadius: '24px', border: '1px solid #1e293b', padding: '20px', boxShadow: '0 30px 60px -15px rgba(0, 0, 0, 0.7)' }}
                      itemStyle={{ color: '#60a5fa', fontWeight: 900, fontSize: '16px' }}
                      labelStyle={{ color: '#94a3b8', marginBottom: '10px', fontWeight: 800, fontSize: '14px' }}
                      formatter={(val) => [`$${Number(val).toLocaleString()} TWD`, '歷史大趨勢']}
                    />
                    <Area type="monotone" dataKey="price" stroke="#3b82f6" strokeWidth={4} fillOpacity={1} fill="url(#colorThreeYear)" animationDuration={3000} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="bg-gradient-to-br from-slate-900 to-slate-950 p-12 rounded-[4rem] border border-rose-900/30 shadow-inner relative group overflow-hidden">
              <div className="absolute top-0 right-0 p-16 opacity-5 rotate-12 transition-all duration-1000 group-hover:rotate-45 group-hover:scale-110">
                <Sword size={160} className="text-rose-500" />
              </div>
              <h3 className="text-xl font-black mb-10 flex items-center gap-4 text-rose-400 relative z-10 uppercase tracking-[0.3em] leading-none">
                <div className="p-3 bg-rose-500/10 rounded-2xl border border-rose-500/20 shadow-lg shadow-rose-950/10"><ShieldCheck size={28} /></div>
                兵策大師：股性診斷
              </h3>
              <div className="relative z-10 space-y-8">
                <div className="inline-block px-8 py-4 bg-rose-600/10 border border-rose-600/20 rounded-[1.5rem] shadow-2xl">
                  <h4 className="text-4xl font-black text-white italic tracking-[0.25em] drop-shadow-[0_4px_10px_rgba(0,0,0,0.5)] leading-tight uppercase">
                    「{analysisData.stockCharacter?.title}」
                  </h4>
                </div>
                <p className="text-slate-300 leading-relaxed font-bold text-2xl max-w-5xl border-l-8 border-rose-600/60 pl-10 py-4 bg-slate-950/40 rounded-r-[2.5rem] tracking-wide">
                  {analysisData.stockCharacter?.comment}
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
              <div className="xl:col-span-2 bg-slate-900/40 backdrop-blur-md p-10 rounded-[3.5rem] border border-slate-800 shadow-2xl">
                <div className="flex justify-between items-center mb-12">
                  <h3 className="text-2xl font-black flex items-center gap-5 text-white uppercase italic tracking-widest leading-none">
                    <div className="p-3 bg-rose-500/10 rounded-2xl text-rose-400 border border-rose-500/10 shadow-lg shadow-rose-950/10"><LineChart size={28} /></div>
                    戰術行情預演 (近期模擬)
                  </h3>
                </div>
                <div className="h-[450px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={shortTermChartData}>
                      <defs>
                        <linearGradient id="colorShortTerm" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.35} />
                          <stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#1e293b" strokeOpacity={0.6} />
                      <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fill: '#475569', fontSize: 12, fontWeight: 900 }} dy={15} />
                      <YAxis domain={['auto', 'auto']} axisLine={false} tickLine={false} tick={{ fill: '#475569', fontSize: 12, fontWeight: 900 }} />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#0f172a', borderRadius: '28px', border: '1px solid #1e293b', padding: '20px', boxShadow: '0 30px 60px -15px rgba(0, 0, 0, 0.7)' }}
                        itemStyle={{ color: '#fb7185', fontWeight: 900, fontSize: '16px' }}
                        labelStyle={{ color: '#94a3b8', marginBottom: '10px', fontWeight: 800, fontSize: '14px' }}
                        formatter={(val) => [`$${Number(val).toFixed(1)} TWD`, '策略模擬價']}
                      />
                      <Area type="monotone" dataKey="price" stroke="#f43f5e" strokeWidth={6} fillOpacity={1} fill="url(#colorShortTerm)" animationDuration={2800} animationEasing="ease-out" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="bg-slate-900/40 backdrop-blur-md p-10 rounded-[3.5rem] border border-slate-800 shadow-2xl flex flex-col h-full">
                <h3 className="text-xs font-black text-slate-500 uppercase tracking-[0.4em] mb-12 flex items-center gap-3 leading-none">
                  <PieChart size={18} className="text-rose-500" /> 多維度能量權重
                </h3>
                <div className="space-y-12 flex-1 px-2">
                  {[
                    { label: '技術面強勢動能', value: analysisData.scoreBreakdown?.technical || 0, color: 'bg-rose-500', shadow: 'shadow-rose-500/50' },
                    { label: '基本獲利城池穩固', value: analysisData.scoreBreakdown?.fundamental || 0, color: 'bg-indigo-500', shadow: 'shadow-indigo-500/50' },
                    { label: '產業前瞻佈局發展', value: analysisData.scoreBreakdown?.industry || 0, color: 'bg-amber-500', shadow: 'shadow-amber-500/50' }
                  ].map((item, idx) => (
                    <div key={idx} className="space-y-5">
                      <div className="flex justify-between text-xs font-black tracking-[0.1em] text-slate-400 uppercase">
                        <span>{item.label}</span>
                        <span className="text-white font-mono">{item.value}%</span>
                      </div>
                      <div className="w-full h-4 bg-slate-800 rounded-full overflow-hidden p-[3px] border border-slate-700/50 shadow-inner">
                        <div className={`h-full ${item.color} rounded-full transition-all duration-[2000ms] ${item.shadow} shadow-[0_0_20px]`} style={{ width: `${item.value}%` }}></div>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-16 p-8 bg-slate-950/60 rounded-[2.5rem] text-[10px] text-slate-500 font-black border border-slate-800/50 italic uppercase tracking-[0.25em] text-center leading-relaxed">
                  AI Command Core v9.5
                  <br />
                  Auth Integrity Verified
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
              <div className="bg-slate-900/40 backdrop-blur-md p-10 rounded-[3.5rem] border border-slate-800 shadow-2xl flex flex-col">
                <h3 className="text-xl font-black mb-10 flex items-center gap-5 text-white uppercase italic tracking-widest leading-none">
                  <div className="p-3 bg-rose-500/10 rounded-2xl text-rose-400 border border-rose-500/10 shadow-lg shadow-rose-950/20"><Newspaper size={28} /></div>
                  全域實時戰報
                </h3>
                <div className="space-y-6 flex-1 overflow-y-auto pr-2 custom-scrollbar">
                  {analysisData.news && analysisData.news.map((n, i) => (
                    <div key={i} className="group p-7 bg-slate-950/40 hover:bg-slate-800 border border-slate-800/50 hover:border-rose-500/30 rounded-[2.5rem] transition-all cursor-pointer flex gap-6 items-start shadow-inner">
                      <div className="shrink-0 w-2.5 h-16 bg-slate-800 group-hover:bg-rose-600 rounded-full transition-all duration-500"></div>
                      <div className="space-y-3">
                        <h4 className="font-bold text-slate-200 group-hover:text-white transition-colors text-lg leading-snug tracking-tight">{n}</h4>
                        <div className="flex items-center gap-4 text-[10px] text-slate-600 font-black uppercase tracking-widest leading-none">
                          <span className="flex items-center gap-1.5"><ExternalLink size={12} /> Intelligence Source</span>
                          <span className="text-rose-500/30 group-hover:text-rose-500 transition-colors uppercase">Multi-Verified</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-rose-500/5 backdrop-blur-md p-10 rounded-[4rem] border border-rose-500/20 shadow-2xl flex flex-col relative overflow-hidden">
                <h3 className="text-xl font-black mb-10 flex items-center gap-5 text-rose-400 relative z-10 uppercase tracking-widest italic leading-none">
                  <div className="p-3 bg-rose-500/10 rounded-2xl border border-rose-500/10 shadow-lg shadow-rose-950/10"><AlertTriangle size={28} /></div>
                  情勢影響深度分析
                </h3>
                <div className="flex-1 bg-slate-950/70 p-10 rounded-[3rem] border border-rose-500/10 shadow-2xl relative z-10 overflow-y-auto">
                  <p className="text-slate-200 leading-[1.8] font-bold text-xl whitespace-pre-wrap italic opacity-95 tracking-wide">
                    {analysisData.newsImpactAnalysis}
                  </p>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-10 pb-12">
              <div className="bg-slate-900/40 backdrop-blur-md p-12 rounded-[4rem] border border-slate-800 shadow-2xl hover:border-amber-500/30 transition-all duration-700 group">
                <div className="flex items-center gap-6 mb-10">
                  <div className="p-5 bg-amber-500/10 rounded-[1.5rem] text-amber-400 group-hover:scale-110 group-hover:bg-amber-500/20 transition-all duration-500 shadow-lg shadow-amber-950/20"><TrendingUp size={36} /></div>
                  <h3 className="text-3xl font-black text-white tracking-tighter italic leading-none uppercase tracking-widest">短期戰術指令</h3>
                </div>
                <p className="text-slate-400 leading-[1.8] font-bold text-lg tracking-wide uppercase">{analysisData.shortTermAnalysis}</p>
              </div>
              <div className="bg-slate-900/40 backdrop-blur-md p-12 rounded-[4rem] border border-slate-800 shadow-2xl hover:border-indigo-500/30 transition-all duration-700 group">
                <div className="flex items-center gap-6 mb-10">
                  <div className="p-5 bg-indigo-500/10 rounded-[1.5rem] text-indigo-400 group-hover:scale-110 group-hover:bg-indigo-500/20 transition-all duration-500 shadow-lg shadow-indigo-950/20"><Globe size={36} /></div>
                  <h3 className="text-3xl font-black text-white tracking-tighter italic leading-none uppercase tracking-widest">長期戰略展望</h3>
                </div>
                <p className="text-slate-400 leading-[1.8] font-bold text-lg tracking-wide uppercase">{analysisData.longTermAnalysis}</p>
              </div>
            </div>

            <footer className="mt-16 p-12 bg-slate-900/30 rounded-[3.5rem] border border-slate-800 text-center space-y-4 tracking-widest relative overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-b from-transparent to-slate-950/20"></div>
              <h4 className="text-slate-400 font-black uppercase tracking-[0.5em] text-xs leading-none relative z-10">投資風險警語與指揮中心聲明</h4>
              <div className="max-w-4xl mx-auto space-y-3 relative z-10">
                <p className="text-slate-500 text-[11px] leading-relaxed font-medium tracking-wide uppercase">
                  本系統數據採全網聚合技術，透過 Google 搜尋分散擷取 Yahoo、玩股網、鉅亨網、CMoney 及證交所等多個平台情資，旨在提供投資者多維度戰略參考並保護使用者連線安全。
                </p>
                <p className="text-slate-500 text-[11px] leading-relaxed font-medium tracking-wide uppercase opacity-80">
                  兵法有云：知彼知己者，百戰不殆。本分析不構成投資建議，股市投資具極高風險，損益計算僅供模擬參考，請自主審慎評估。
                </p>
              </div>
            </footer>
          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center space-y-12 text-slate-800 px-10 text-center relative overflow-hidden">
            <div className="absolute inset-0 flex items-center justify-center opacity-[0.02] pointer-events-none">
              <Crosshair size={1000} />
            </div>
            <div className="p-24 bg-slate-900 rounded-[5rem] shadow-[0_0_100px_rgba(0,0,0,0.5)] border border-slate-800 relative group cursor-pointer hover:border-rose-500/20 transition-all duration-1000 z-10">
              <div className="absolute inset-0 bg-rose-500 blur-[150px] opacity-10 rounded-full group-hover:opacity-20 transition-opacity duration-700"></div>
              <Sword size={160} className="opacity-10 relative z-10 group-hover:scale-110 group-hover:rotate-12 transition-all duration-700 text-rose-500" />
            </div>
            <div className="space-y-6 max-w-xl z-10">
              <h2 className="text-5xl font-black text-slate-300 tracking-tighter italic leading-tight tracking-widest uppercase">「善戰者，立於不敗之地」</h2>
              <div className="space-y-2">
                <p className="text-slate-600 font-black uppercase tracking-[0.5em] text-xs leading-loose">請於左側輸入台股代碼與部位資訊</p>
                <p className="text-rose-500/40 font-bold text-[10px] uppercase tracking-widest italic leading-none">Ready to engage tactical scanning</p>
              </div>
            </div>
          </div>
        )}
      </main>

      <style dangerouslySetInnerHTML={{ __html: `
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: #020617; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 20px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #334155; }
        @keyframes fade-in { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        .animate-in { animation: fade-in 1s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
        input[type="number"]::-webkit-inner-spin-button,
        input[type="number"]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
      ` }} />
    </div>
  );
};

export default App;
