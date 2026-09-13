# assets — 放原始圖片的地方

把照片／導覽圖丟進這個資料夾（GitHub 網頁版可以直接拖拉上傳），
再跑 `tools/embed_images.py` 把它們轉成 base64 塞進 `index.html` 的 `IMG`。

嵌進去之後，那張卡片就不會再去抓維基百科的圖（`imgsHTML()` 只在 `IMG[key]`
是空的時候才產生 `data-wiki`）。原圖留在這裡當備份，不影響頁面大小。

## 已經嵌進 index.html 的

| key | 檔案 | 用在哪 |
|---|---|---|
| `sysMemorial` | `國父紀念館-外觀.webp`（封面）、`國父紀念館-儀隊.webp` | 9/27 |
| `songyan` | `松菸-園區入口.webp`（封面）、`松菸-廣場與誠品.webp`、`松菸-倉庫展場.webp`、`松菸-夜間市集.webp` | 9/27 |
| `sightseeingBus` | `巴士-外觀.webp`（封面）、`巴士-上層座位.webp` | 9/27 |

`松菸-倉庫展場.webp` 已裁掉下方 22%（原圖左下角有 roundTAIWANround 浮水印）。

## 還缺的兩張

| key | 內容 | 用在哪 |
|---|---|---|
| `xitouGuide` | 溪頭園區官方導覽圖 | 10/1 |
| `smlAccess` | 日月潭無障礙路線圖 | 9/30 |

檔名隨意，指令裡對應得上就好：

```bash
pip install pillow   # 只需一次
python3 tools/embed_images.py index.html \
  sysMemorial=assets/國父紀念館.jpg,assets/儀隊交接.jpg \
  songyan=assets/松菸入口.jpg,assets/誠品松菸.jpg
```

第一張是卡片封面。`+key=檔案` 是追加而不是覆蓋。
