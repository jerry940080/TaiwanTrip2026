#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 index.html 的畫面切成一頁一張，貼進可以列印的 Word 檔。

先跑截圖，再跑這支：

    NODE_PATH=<playwright 位置> node tools/shoot_pages.js
    python3 tools/make_docx.py

Word 檔裡每一頁就是網頁的一段畫面——版面、照片、地圖、顏色都跟螢幕上一模一樣，
不是重新排版過的文字。只用標準庫寫 OOXML，切圖用 Pillow。
"""
import argparse, json, os, struct, sys, zipfile
from xml.sax.saxutils import escape

EMU = 914400                                  # 1 吋
A4_W, A4_H = 21.0, 29.7                       # cm
MARGIN = 1.0                                  # cm，圖要大就把邊界壓到最小
IMG_W = int((A4_W - 2 * MARGIN) / 2.54 * EMU)
IMG_H_MAX = int((A4_H - 2 * MARGIN) / 2.54 * EMU)

NS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"'
)


def png_size(path):
    with open(path, "rb") as f:
        return struct.unpack(">II", f.read(24)[16:24])


def page_image(rid, idx, w_px, h_px, first):
    """整頁一張圖。除了第一頁，都掛 pageBreakBefore 換頁。"""
    cx = IMG_W
    cy = int(cx * h_px / w_px)
    if cy > IMG_H_MAX:                        # 理論上不會，保險
        cx, cy = int(cx * IMG_H_MAX / cy), IMG_H_MAX
    brk = "" if first else "<w:pageBreakBefore/>"
    return (
        f'<w:p><w:pPr>{brk}<w:spacing w:before="0" w:after="0" w:line="240" '
        'w:lineRule="auto"/><w:jc w:val="center"/></w:pPr>'
        f'<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{idx}" name="page{idx}"/>'
        '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        f'<pic:pic><pic:nvPicPr><pic:cNvPr id="{idx}" name="page{idx}.png"/><pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
        "</a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>")


def slice_full(outdir, quality):
    """用 cuts.json 把 full.png 切成一頁一張。已經切好就不重切。

    每一頁 PNG 與 JPEG 各存一次、留比較小的那個：整頁都是字的頁面 PNG 反而比較小
    （顏色少），有照片的頁面則是 JPEG 小很多。兩種印出來都看不出差別。
    """
    cuts_path = os.path.join(outdir, "cuts.json")
    full_path = os.path.join(outdir, "full.png")
    if not os.path.exists(cuts_path):
        sys.exit(f"找不到 {cuts_path}——請先跑 node tools/shoot_pages.js")
    cuts = json.load(open(cuts_path, encoding="utf-8"))
    n_pages = len(cuts["slices"])
    stems = [os.path.join(outdir, f"page{i:02d}") for i in range(1, n_pages + 1)]
    if not os.path.exists(full_path):                  # full.png 已清掉，直接用切好的
        found = [next((st + e for e in (".png", ".jpg") if os.path.exists(st + e)), None)
                 for st in stems]
        if all(found):
            return found
        sys.exit(f"找不到 {full_path}——請先跑 node tools/shoot_pages.js")
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None                      # 整頁很長，不要被安全上限擋下
    full = Image.open(full_path).convert("RGB")
    sc = cuts["scale"]
    names = []
    for st, (top, h) in zip(stems, cuts["slices"]):
        part = full.crop((0, top * sc, full.width, min(full.height, (top + h) * sc)))
        png, jpg = st + ".png", st + ".jpg"
        part.save(png, "PNG", optimize=True)
        part.save(jpg, "JPEG", quality=quality, subsampling=0, optimize=True)
        keep, drop = ((png, jpg) if os.path.getsize(png) <= os.path.getsize(jpg)
                      else (jpg, png))
        os.remove(drop)
        names.append(keep)
    return names


def write_docx(out_path, document_xml, rels, media):
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Default Extension="png" ContentType="image/png"/>'
          '<Default Extension="jpg" ContentType="image/jpeg"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
          'officedocument.wordprocessingml.document.main+xml"/>'
          '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-'
          'officedocument.wordprocessingml.styles+xml"/></Types>')
    root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
                 '2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    doc_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
                '2006/relationships/styles" Target="styles.xml"/>' + "".join(rels) + "</Relationships>")
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              f'<w:styles {NS}><w:docDefaults><w:pPrDefault><w:pPr>'
              '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr></w:pPrDefault>'
              '</w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
              '<w:name w:val="Normal"/></w:style></w:styles>')
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("word/_rels/document.xml.rels", doc_rels)
        z.writestr("word/styles.xml", styles)
        z.writestr("word/document.xml", document_xml)
        for name, path in media:
            z.write(path, "word/" + name)


def build(outdir, out_path, quality):
    names = slice_full(outdir, quality)
    rels, media, body = [], [], []
    for i, n in enumerate(names):
        w, h = png_size(n) if n.endswith(".png") else (None, None)
        if w is None:
            from PIL import Image
            w, h = Image.open(n).size
        rid = f"rId{100 + i}"
        base = os.path.basename(n)
        media.append((f"media/{base}", n))
        rels.append(f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/'
                    f'officeDocument/2006/relationships/image" Target="media/{base}"/>')
        body.append(page_image(rid, i + 1, w, h, first=(i == 0)))

    sect = (f'<w:sectPr><w:pgSz w:w="{int(A4_W / 2.54 * EMU) // 635}" '
            f'w:h="{int(A4_H / 2.54 * EMU) // 635}"/>'
            f'<w:pgMar w:top="{int(MARGIN / 2.54 * EMU) // 635}" '
            f'w:right="{int(MARGIN / 2.54 * EMU) // 635}" '
            f'w:bottom="{int(MARGIN / 2.54 * EMU) // 635}" '
            f'w:left="{int(MARGIN / 2.54 * EMU) // 635}" '
            'w:header="0" w:footer="0" w:gutter="0"/></w:sectPr>')
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
           f"<w:document {NS}><w:body>{''.join(body)}{sect}</w:body></w:document>")
    write_docx(out_path, doc, rels, media)
    return len(names)


def main():
    ap = argparse.ArgumentParser(description="把 index.html 的畫面切成一頁一張貼進 Word")
    ap.add_argument("--dir", default="assets/print", help="截圖與切點所在的資料夾")
    ap.add_argument("--out", default="台灣行程.docx")
    ap.add_argument("--jpeg", type=int, default=92, metavar="品質",
                    help="有照片的頁面用的 JPEG 品質（1–95，預設 92）")
    a = ap.parse_args()
    n = build(a.dir, a.out, a.jpeg)
    print(f"寫出 {a.out}：{n} 頁、{os.path.getsize(a.out) / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
