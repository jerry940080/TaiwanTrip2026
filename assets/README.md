# assets — 放原始圖片的地方

把照片／導覽圖丟進這個資料夾（GitHub 網頁版可以直接拖拉上傳），
再跑 `tools/embed_images.py` 把它們轉成 base64 塞進 `index.html` 的 `IMG`。

嵌進去之後，那張卡片就不會再去抓維基百科的圖（`imgsHTML()` 只在 `IMG[key]`
是空的時候才產生 `data-wiki`）。原圖留在這裡當備份，不影響頁面大小。

目前等著補的五組：

| key | 內容 | 用在哪 |
|---|---|---|
| `sysMemorial` | 國父紀念館外觀、儀隊交接 | 9/27 |
| `songyan` | 松菸入口、誠品松菸、市集、倉庫展場 | 9/27 |
| `sightseeingBus` | 雙層巴士外觀、上層座位 | 9/27 |
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
