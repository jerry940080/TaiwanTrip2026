# CLAUDE.md

2026 台灣行程懶人包。單檔 HTML（`index.html`），部署在 GitHub Pages。

## 最重要的規則

**改資料，不動引擎。** `index.html` 分成三層：

1. 第一段 `<script>`：`const LAND=[...]`（地圖底圖，台灣縣市界）。只有換目的地或想改精細度時才動，用 `tools/make_land.py` 重生整段。
2. 第二段 `<script>` 開頭到 `/* ===== MAP ENGINE ===== */` 之前：**資料區**，日常修改都在這裡。
3. `MAP ENGINE` / `RENDER` / `PHOTOS` 三段：引擎，除非要加新功能否則不要改。
   例外：`RENDER` 區開頭的 hero overview `cfg` 是首頁總覽圖的資料，該改。

## 資料區順序

`WIKI_LANG` → `P`（座標）→ `RAILS`（背景鐵路）→ `MODE`（交通線型）→ `KIND`／`NAMES`（點樣式與顯示名）
→ `CARDS`（景點卡）→ `IMG`（照片，用工具塞）→ `DAYS`（每日行程）

各欄位格式見 `TEMPLATE_GUIDE.md`；要看填好長什麼樣，開 `reference/example-atami-izu.html`。

## 慣例

- **文案**：繁體中文。專名保留原文（日文漢字、英文原名放 `jp` 欄）。估算時間寫「約 X 分」。
- **時刻表 `tl`**：`h` 只放標題，長描述放到 `CARDS` 的 `text`。移動列加 `move:1`。
- **地圖**：`minSpan` 市區日 `.02`、跨縣市日 `.2–.3`；同段來回的回程 leg 加 `curve:.2`（負值彎另一邊）；
  標籤重疊就改 `labels` 的方位（`t/b/l/r`）。
- **配色**：和紙底 `#f8f5ee`、藍 `#2b4c7e`（高鐵／台鐵）、櫻粉 `#e28aa5`（景點）、朱紅 `#c8452e`（住宿／租車）、
  紫 `#6f5aa0`（捷運／纜車）、黃 `#d9a21b`（客運）。
- **新增地點**：先在 `P` 加座標，再在 `NAMES` 給顯示名與類型，最後才在 `DAYS`／`CARDS` 引用。
  座標請用實際查得的值，不要憑印象填。
- **照片**：不要手動貼 base64，一律用 `python3 tools/embed_images.py index.html key=a.jpg,b.jpg`。

## 改完要檢查

先跑檢查工具（括號對稱、key 有沒有對上、座標有沒有寫反）：

```bash
python3 tools/check.py
```

再開頁面確認每日地圖畫得出來、卡片點得開、console 沒有紅字。

## 部署

commit → push。GitHub Pages 由預設分支的 `/ (root)` 出版，網址 `https://jerry940080.github.io/TaiwanTrip2026/`。
