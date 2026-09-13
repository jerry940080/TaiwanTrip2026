# assets — 原始圖片

- `assets/` 這一層放**使用者提供的原圖**（未縮放），當備份。
- `assets/img/` 是 `tools/embed_images.py --out` 產生的**縮圖**（1200 寬、JPEG q82），
  就是頁面實際載入的檔案，檔名固定是 `<卡片 key>-<序號>.jpg`。

`index.html` 的 `IMG` 存的是 `assets/img/xxx-1.jpg` 這種相對路徑。
引擎不管值是相對路徑還是 base64 data URI，都直接當 `<img src>` 用。

## 為什麼不內嵌 base64

75 張照片轉成 base64 是 15.7 MB，`index.html` 會變成 18 MB。
單檔 HTML 的內容全部內嵌，**整份下載完之前頁面都是白的**，手機用行動網路開會等很久。
改成外部檔案之後 `index.html` 回到 320 KB，圖片靠 `<img loading="lazy">` 邊捲邊載。

只有幾張圖、又想要單檔可攜（例如寄給別人）的話，省略 `--out` 就會走 base64。

## 換圖／補圖

```bash
pip install pillow   # 只需一次
python3 tools/embed_images.py index.html --out assets/img \
  jiufen=原圖1.jpg,原圖2.jpg        # 覆蓋，第一張是卡片封面
python3 tools/embed_images.py index.html --out assets/img \
  +jiufen=原圖3.jpg                 # 追加
```

浮水印要自己先裁掉（`松菸-倉庫展場` 那張原圖左下角有 roundTAIWANround，已裁掉下方 22%）。

## 還沒有照片的卡片

象山、貓空、陽明山、十分（以上都在候選區，未排入行程）、淡水、
南投好行卡、溪頭導覽電動車、草悟道——這些目前仍以維基百科的圖當暫代。
