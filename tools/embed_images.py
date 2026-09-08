#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把照片轉成 base64 塞進懶人包的 IMG 資料區。

用法：
  python3 embed_images.py index.html kinomiya=a.jpg,b.jpg +kinomiya=c.jpg baien=d.png
    key=檔案      → 覆蓋該景點的照片（逗號分隔多張，第一張是卡片封面）
    +key=檔案     → 追加到現有照片後面
自動處理：轉 JPEG、寬度縮到 1200、quality 82。
裁切浮水印請先自行處理（常見：截圖底部 8–9% 有 Google 圖示）。
需要 Pillow：pip install pillow
"""
import base64, io, re, sys
from PIL import Image

def enc(path, maxw=1200, q=82):
    im = Image.open(path).convert("RGB")
    if im.width > maxw:
        im = im.resize((maxw, int(im.height * maxw / im.width)), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "JPEG", quality=q, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()

def main():
    html_path, *pairs = sys.argv[1:]
    s = open(html_path, encoding="utf-8").read()
    m = re.search(r"const IMG=\{(.*?)\};", s, re.S)
    cur = {}
    for k, v in re.findall(r"(\w+):(\[[^\]]*\]|'data:[^']+')", m.group(1)):
        cur[k] = re.findall(r"'(data:[^']+)'", v) if v.startswith("[") else v.strip("'")
    for pair in pairs:
        k, p = pair.split("=", 1)
        new = [enc(x) for x in p.split(",")]
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
