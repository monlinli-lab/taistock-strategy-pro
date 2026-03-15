# 台股兵策 Strategic Commander

這是一個可直接上傳到 GitHub 的 React + Vite 專案，提供台股代碼查詢、部位輸入、AI 戰略評分、新聞摘要與走勢視覺化介面。

## 功能特色

- 台股代碼輸入與分析
- 成本價、張數部位試算
- AI 戰略評分與多維度評估
- 三年趨勢與短期模擬圖表
- 歷史查詢紀錄
- GitHub 專案結構完整，可直接部署

## 技術堆疊

- React 18
- Vite 5
- Tailwind CSS 3
- Recharts
- Lucide React

## 本機執行

```bash
npm install
npm run dev
```

## 建置正式版

```bash
npm install
npm run build
```

## API 金鑰設定

1. 複製 `.env.example` 為 `.env`
2. 填入你的 Google AI Studio API Key：

```bash
VITE_GEMINI_API_KEY=你的金鑰
```

## GitHub 上傳方式

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin 你的 GitHub Repository URL
git push -u origin main
```

## 注意事項

- 本專案前端會直接呼叫 Gemini API，正式公開部署前，建議改為後端代理，避免 API Key 暴露。
- 畫面中的短期模擬數據為前端模擬值，不代表真實投資預測。
