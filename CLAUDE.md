# CLAUDE.md

2026 台灣行程懶人包。`index.html` 一個檔案裝所有內容與程式，照片放在 `assets/img/`，部署在 GitHub Pages。
`simple.html` 是給長輩看的大字版，另外一個獨立檔案（見下面「兩個版本」）。

> 照片原本是 base64 內嵌成單檔，但累積到 75 張時 `index.html` 會變成 18 MB——
> 全部下載完之前整頁都是白的，手機用行動網路開會等很久。現在改成外部檔案配
> `<img loading="lazy">`，頁面回到 320 KB，圖片邊捲邊載。

## 最重要的規則

**改資料，不動引擎。** `index.html` 分成三層：

1. 第一段 `<script>`：底圖資料層——`LAND`（台灣縣市界）、`METRO`（台北捷運路網）、
   `TOWNLINES`／`TOWNS`（雙北基隆的區界與區名）、`COUNTIES`（縣市名）、`STATIONS`（捷運站點）、
   `POIS`（路線附近的周邊地標）。只有換目的地或想改精細度時才動：
   LAND 用 `tools/make_land.py`、TOWNLINES／TOWNS 用 `tools/make_poi.py`、POIS 用 `tools/make_pois.py`。
2. 第二段 `<script>` 開頭到 `/* ===== MAP ENGINE ===== */` 之前：**資料區**，日常修改都在這裡。
3. `MAP ENGINE` / `REAL MAP` / `RENDER` / `PHOTOS` 四段：引擎，除非要加新功能否則不要改。
   例外：`RENDER` 區開頭的 hero overview `cfg` 是首頁總覽圖的資料，該改。
   `REAL MAP` 是疊在手繪圖上的 Leaflet 真實地圖，圖磚載不到會自動退回手繪圖；
   動這一段前先看 `TEMPLATE_GUIDE.md` 的「真實地圖底圖」，CSS 選擇器有兩個坑。

## 資料區順序

`WIKI_LANG` → `P`（座標）→ `RAILS`（背景鐵路＋捷運路網）→ `MODE`（交通線型）→ `KIND`／`NAMES`（點樣式與顯示名）
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
- **照片**：不要手動改 `IMG`，一律用工具。照片多用外部檔案（現在的做法）：
  `python3 tools/embed_images.py index.html --out assets/img key=a.jpg,b.jpg`；
  只有幾張、想維持單檔可攜時才省略 `--out` 走 base64 內嵌。
  `IMG` 的值不管是 data URI 還是相對路徑，引擎都直接當 `src` 用，不必改程式。
  原圖留一份在 `assets/`（工具會另外輸出縮圖到 `assets/img/`）。

## 兩個版本

- **`index.html`（完整版）**——地圖、卡片、照片、備註全都在，給安排行程的人看。
- **`simple.html`（大字版）**——給長輩在手機上看。字大、對比高、按鈕大，**沒有地圖也沒有照片**，
  一天最多六句話，點一天進一頁。有三段字級可調，底部是飯店地址（給計程車司機看）與 `tel:` 電話。

大字版**完全獨立**，沒有共用任何程式；裡面的 `const D` 是**人工濃縮**過的，不是從 `DAYS` 自動產生——
因為「濃縮成六句」需要判斷哪幾件事重要，機器做不好。代價是**改行程時兩邊都要改**，
`tools/check.py` 會比對兩邊的日期、星期與住宿，對不上就報錯。

改大字版的原則：講「要做什麼」，不講「為什麼」；不寫車種與路線編號（長輩不需要轉乘細節）；
有階梯或要走遠的地方一定寫清楚可以不去。

## 改完要檢查

先跑檢查工具（括號對稱、key 有沒有對上、座標有沒有寫反）：

```bash
python3 tools/check.py
```

再開頁面確認每日地圖畫得出來、卡片點得開、console 沒有紅字。

## 部署

commit → push。GitHub Pages 由預設分支的 `/ (root)` 出版，網址 `https://jerry940080.github.io/TaiwanTrip2026/`。
