#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把照片放進懶人包的 IMG 資料區。

兩種模式：

  內嵌 base64（單檔 HTML，照片少的時候用）
    python3 embed_images.py index.html kinomiya=a.jpg,b.jpg +kinomiya=c.jpg

  外部檔案（照片多的時候用；IMG 存相對路徑，引擎照樣吃）
    python3 embed_images.py index.html --out assets/img kinomiya=a.jpg,b.jpg

    key=檔案   → 覆蓋該景點的照片（逗號分隔多張，第一張是卡片封面）
    +key=檔案  → 追加到現有照片後面

照片一多就要用 --out：base64 會讓整個頁面在圖片下載完之前都是白的，
手機用行動網路開會等很久；外部檔案配上 <img loading="lazy"> 才會邊捲邊載。

自動處理：轉 JPEG、寬度縮到 --maxw（預設 1200）、quality --q（預設 82）。
裁切浮水印請先自行處理（常見：截圖底部 8–9% 有 Google 圖示）。
需要 Pillow：pip install pillow
"""
import base64, io, os, re, sys
from PIL import Image

def load(path, maxw, q):
    """讀檔、縮圖、轉 JPEG，回傳 bytes。"""
    im = Image.open(path).convert("RGB")
    if im.width > maxw:
        im = im.resize((maxw, int(im.height * maxw / im.width)), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "JPEG", quality=q, optimize=True)
    return b.getvalue()

def enc(path, maxw=1200, q=82):
    return "data:image/jpeg;base64," + base64.b64encode(load(path, maxw, q)).decode()

def main():
    args = sys.argv[1:]
    out_dir, maxw, q = None, 1200, 82
    pairs = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--out":   out_dir = args[i + 1]; i += 2
        elif a == "--maxw": maxw = int(args[i + 1]); i += 2
        elif a == "--q":    q = int(args[i + 1]); i += 2
        else: pairs.append(a); i += 1
    html_path, *pairs = pairs
    s = open(html_path, encoding="utf-8").read()
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    m = re.search(r"const IMG=\{(.*?)\};", s, re.S)
    cur = {}
    for k, v in re.findall(r"(\w+):(\[[^\]]*\]|'[^']+')", m.group(1)):
        cur[k] = re.findall(r"'([^']+)'", v) if v.startswith("[") else v.strip("'")
    for pair in pairs:
        k, p = pair.split("=", 1)
        base = k[1:] if k.startswith("+") else k
        files = p.split(",")
        if out_dir:
            start = len(cur.get(base, [])) if k.startswith("+") else 0
            new = []
            for n, x in enumerate(files, start + 1):
                rel = os.path.join(out_dir, f"{base}-{n}.jpg")
                open(rel, "wb").write(load(x, maxw, q))
                new.append(rel)
        else:
            new = [enc(x, maxw, q) for x in files]
        if k.startswith("+"):
            k = k[1:]
            old = cur.get(k, []); old = old if isinstance(old, list) else [old]
            cur[k] = old + new
        else:
            cur[k] = new if len(new) > 1 else new[0]
    body = ",".join(
        (f"{k}:[{','.join(chr(39)+x+chr(39) for x in v)}]" if isinstance(v, list)
         else f"{k}:'{v}'") for k, v in cur.items())
    s = s[:m.start()] + "const IMG={" + body + "};" + s[m.end():]
    open(html_path, "w", encoding="utf-8").write(s)
    print("done:", {k: (len(v) if isinstance(v, list) else 1) for k, v in cur.items()})

if __name__ == "__main__":
    main()
