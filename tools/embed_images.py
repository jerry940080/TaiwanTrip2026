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

  分組（卡片裡再切分頁，標題就是組名）
    python3 embed_images.py index.html --out assets/img \
      "beitou=瀧乃湯:a.jpg,b.jpg|春天酒店大眾池:c.jpg"

    用 | 分組、組名和檔案之間用 :。有分組時模態框會出現一排分頁按鈕，
    點了跳到該組第一張；沒分組就是原本的單一相簿。

照片一多就要用 --out：base64 會讓整個頁面在圖片下載完之前都是白的，
手機用行動網路開會等很久；外部檔案配上 <img loading="lazy"> 才會邊捲邊載。

自動處理：轉 JPEG、寬度縮到 --maxw（預設 1200）、quality --q（預設 82）。
裁切浮水印請先自行處理（常見：截圖底部 8–9% 有 Google 圖示）。
需要 Pillow：pip install pillow
"""
import base64, io, json, os, re, sys
from PIL import Image

def read_img(lit):
    """把 index.html 裡的 IMG 物件讀回來。現在是標準 JSON；
    舊版是單引號的 JS 物件字面值，這裡一併相容。"""
    lit = lit.strip()
    try:
        return json.loads(lit)
    except ValueError:
        pass
    out = {}
    for k, v in re.findall(r"(\w+):(\[[^\]]*\]|'[^']*')", lit):
        out[k] = re.findall(r"'([^']*)'", v) if v.startswith("[") else v.strip("'")
    return out

def load(path, maxw, q):
    """讀檔、縮圖、轉 JPEG，回傳 bytes。"""
    im = Image.open(path).convert("RGB")
    if im.width > maxw:
        im = im.resize((maxw, int(im.height * maxw / im.width)), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "JPEG", quality=q, optimize=True)
    return b.getvalue()

def enc(path, maxw=1200, q=82):
    return "data:image/jpeg;base64," + base64.b64encode(load(path, maxw, q)).decode()

def flat(v):
    """IMG 的值可能是字串、清單，或分組的 [{t,u}]；一律攤成路徑清單。"""
    if not v: return []
    a = v if isinstance(v, list) else [v]
    return [u for o in a for u in (o["u"] if isinstance(o, dict) else [o])]

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
    m = re.search(r"const IMG=(\{.*?\});", s, re.S)
    cur = read_img(m.group(1))
    for pair in pairs:
        k, p = pair.split("=", 1)
        base = k[1:] if k.startswith("+") else k
        # "組名:a.jpg,b.jpg|組名2:c.jpg" → 分組；沒有 | 也沒有 : 就是一般的平鋪清單
        groups = []
        for chunk in p.split("|"):
            if ":" in chunk and not os.path.exists(chunk.split(",")[0]):
                title, fs = chunk.split(":", 1)
                groups.append((title, fs.split(",")))
            else:
                groups.append((None, chunk.split(",")))
        n = len(flat(cur.get(base))) if k.startswith("+") else 0
        out = []
        for title, files in groups:
            got = []
            for x in files:
                n += 1
                if out_dir:
                    rel = os.path.join(out_dir, f"{base}-{n}.jpg")
                    open(rel, "wb").write(load(x, maxw, q))
                    got.append(rel)
                else:
                    got.append(enc(x, maxw, q))
            out.append({"t": title, "u": got} if title else got)
        grouped = any(isinstance(o, dict) for o in out)
        new = out if grouped else [u for o in out for u in o]
        if k.startswith("+"):
            k = k[1:]
            prev = cur.get(k, []); prev = prev if isinstance(prev, list) else [prev]
            cur[k] = prev + new
        else:
            cur[k] = new if (len(new) > 1 or grouped) else new[0]
    s = s[:m.start()] + "const IMG=" + json.dumps(cur, ensure_ascii=False,
                                                   separators=(",", ":")) + ";" + s[m.end():]
    open(html_path, "w", encoding="utf-8").write(s)
    print("done:", {k: len(flat(v)) for k, v in cur.items()})

if __name__ == "__main__":
    main()
