# TaiwanTrip2026

2026 台灣行程懶人包。單一 HTML 檔，放上 GitHub Pages 就有網址可以分享，
內含每日路線地圖、時刻表、景點卡片、車票費用與訂票時程。

**目前狀態：模板骨架已完成，行程細節待填。**

## 網址

啟用 GitHub Pages 後：`https://jerry940080.github.io/TaiwanTrip2026/`

啟用方式：GitHub repo → **Settings → Pages** → Source 選 `Deploy from a branch`，
分支選目前的預設分支、資料夾 `/ (root)` → Save，約一分鐘後生效。

## 內容

| 檔案 | 說明 |
|---|---|
| `index.html` | 網站本體（台灣底圖 ＋ 待填資料區 ＋ 兩天示範行程） |
| `TEMPLATE_GUIDE.md` | 怎麼改資料、怎麼塞照片、怎麼部署 |
| `CLAUDE.md` | 用 Claude Code 協作時的專案慣例 |
| `tools/make_land.py` | 重生地圖底圖（台灣／日本／全球海岸線） |
| `tools/check.py` | 改完資料跑一次，抓括號、key、座標的手滑 |
| `tools/embed_images.py` | 把照片轉 base64 內嵌（離線也看得到） |
| `reference/example-atami-izu.html` | 完整範例，抄格式時打開它看 |

## 本機預覽

```bash
python3 -m http.server 8000
# 開 http://localhost:8000
```

直接雙擊 `index.html` 也可以，只是 YouTube 內嵌在 `file://` 下會顯示錯誤 153，上線後正常。
