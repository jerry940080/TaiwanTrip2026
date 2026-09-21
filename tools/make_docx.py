#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 index.html 匯出成可以列印的 Word 檔（給長輩當紙本筆記用）。

用法：
    python3 tools/make_docx.py                     # 產生 台灣行程.docx
    python3 tools/make_docx.py --out 行程.docx --no-maps

只用標準庫寫 OOXML，不必裝 python-docx。地圖圖片來自 assets/print/，
用 tools/shoot_maps.js 產生；沒有那個資料夾就自動略過地圖。

字級刻意放大（內文 13pt、時間 13pt 粗體、大標 22pt），A4 邊界 1.8cm，
每天各自一頁，最後附幾張空白筆記頁。
"""
import argparse, os, re, struct, sys, zipfile
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jsdata

EMU = 914400                      # 1 吋
PAGE_W = int(21.0 / 2.54 * EMU)   # A4 寬
MARGIN = int(1.8 / 2.54 * EMU)
BODY_W = PAGE_W - 2 * MARGIN      # 可用寬度

FONT = "Microsoft JhengHei"       # Windows 的微軟正黑體；Mac 會退回系統字
FONT_EA = "微軟正黑體"
BLUE, RED, GREY = "24456F", "B93D28", "5A5F66"

NS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"'
)


# ---------------------------------------------------------------- HTML → 文字片段
def segs(html):
    """把 <b>粗體</b> 的 HTML 片段拆成 [(文字, 粗體?)]，其餘標籤丟掉。"""
    html = re.sub(r"<br\s*/?>", "\n", html or "")
    html = re.sub(r"</li>\s*<li>", "\n・", html)
    html = re.sub(r"<li>", "・", html)
    html = re.sub(r"</?(ul|ol|li)[^>]*>", "", html)
    out, bold, i = [], 0, 0
    for m in re.finditer(r"<(/?)(b|strong)\b[^>]*>", html):
        txt = html[i:m.start()]
        if txt:
            out.append((txt, bold))
        bold = 0 if m.group(1) else 1
        i = m.end()
    if html[i:]:
        out.append((html[i:], bold))
    return [(re.sub(r"<[^>]+>", "", t), b) for t, b in out if re.sub(r"<[^>]+>", "", t)]


def plain(html):
    return "".join(t for t, _ in segs(html))


# ---------------------------------------------------------------- OOXML 小積木
def rpr(size=26, bold=0, color=None, italic=0):
    x = f'<w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:eastAsia="{FONT_EA}" w:cs="{FONT}"/>'
    if bold:
        x += "<w:b/><w:bCs/>"
    if italic:
        x += "<w:i/>"
    if color:
        x += f'<w:color w:val="{color}"/>'
    return f"<w:rPr>{x}<w:sz w:val=\"{size}\"/><w:szCs w:val=\"{size}\"/></w:rPr>"


def run(text, **kw):
    out = []
    for j, line in enumerate(str(text).split("\n")):
        if j:
            out.append(f"<w:r>{rpr(**kw)}<w:br/></w:r>")
        if line:
            out.append(f'<w:r>{rpr(**kw)}<w:t xml:space="preserve">{escape(line)}</w:t></w:r>')
    return "".join(out)


def para(content="", size=26, bold=0, color=None, before=0, after=80, align=None,
         indent=0, shade=None, border=None, underline=None, line=300,
         keep=0, exact=0):
    # w:pPr 的子元素有固定順序：keepLines → pBdr → shd → spacing → ind → jc。
    # 順序錯了 Word 會直接拒收整份檔案。
    p = "<w:keepLines/>" if keep else ""
    if border:
        p += ('<w:pBdr><w:left w:val="single" w:sz="24" w:space="8" '
              f'w:color="{border}"/></w:pBdr>')
    elif underline:
        p += ('<w:pBdr><w:bottom w:val="single" w:sz="4" w:space="6" '
              f'w:color="{underline}"/></w:pBdr>')
    if shade:
        p += f'<w:shd w:val="clear" w:fill="{shade}"/>'
    rule = "exact" if exact else "auto"
    p += f'<w:spacing w:before="{before}" w:after="{after}" w:line="{line}" w:lineRule="{rule}"/>'
    if indent:
        p += f'<w:ind w:left="{indent}"/>'
    if align:
        p += f'<w:jc w:val="{align}"/>'
    body = content if content.startswith("<w:r") else run(content, size=size, bold=bold, color=color)
    return f"<w:p><w:pPr>{p}</w:pPr>{body}</w:p>"


def rich(html, **kw):
    """把含 <b> 的片段排成一段。"""
    size = kw.pop("size", 26)
    color = kw.pop("color", None)
    body = "".join(run(t, size=size, bold=b, color=color) for t, b in segs(html))
    return para(body or run("", size=size), **kw)


def pagebreak():
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


SPACER = '<w:p w:rsidR="00000000"><w:pPr><w:spacing w:before="0" w:after="0" '\
         'w:line="1" w:lineRule="exact"/></w:pPr></w:p>'


def table(rows, widths, head=True, size=24):
    """rows：[[cell_html, …], …]，widths：各欄百分比（合計 100）。"""
    total = BODY_W // 635          # EMU → dxa（twips）
    cols = [int(total * w / 100) for w in widths]
    grid = "".join(f'<w:gridCol w:w="{c}"/>' for c in cols)
    bd = ('<w:tblBorders>'
          + "".join(f'<w:{s} w:val="single" w:sz="4" w:space="0" w:color="D5CEC0"/>'
                    for s in ("top", "left", "bottom", "right", "insideH", "insideV"))
          + "</w:tblBorders>")
    out = [f'<w:tbl><w:tblPr><w:tblW w:w="{total}" w:type="dxa"/>{bd}'
           f'<w:tblCellMar><w:top w:w="60" w:type="dxa"/><w:bottom w:w="60" w:type="dxa"/>'
           f'<w:left w:w="110" w:type="dxa"/><w:right w:w="110" w:type="dxa"/></w:tblCellMar>'
           f"</w:tblPr><w:tblGrid>{grid}</w:tblGrid>"]
    for ri, r in enumerate(rows):
        hdr = head and ri == 0
        cells = []
        for ci, c in enumerate(r):
            body = "".join(run(t, size=size, bold=(b or hdr),
                               color=GREY if hdr else None) for t, b in segs(c)) or run("", size=size)
            cells.append(
                f'<w:tc><w:tcPr><w:tcW w:w="{cols[ci]}" w:type="dxa"/>'
                + (f'<w:shd w:val="clear" w:fill="F3EEE2"/>' if hdr else "")
                + "</w:tcPr>"
                + para(body, after=0, line=280) + "</w:tc>")
        trpr = "<w:trPr><w:cantSplit/>" + ("<w:tblHeader/>" if hdr else "") + "</w:trPr>"
        out.append(f'<w:tr>{trpr}{"".join(cells)}</w:tr>')
    out.append("</w:tbl>" + SPACER)
    return "".join(out)


def notelines(rows=20, height=620):
    """筆記頁的橫線。只畫每一列的下框線。"""
    total = BODY_W // 635
    bd = ('<w:tblBorders>'
          '<w:top w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
          '<w:left w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
          '<w:right w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
          '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="D5CEC0"/>'
          '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="D5CEC0"/>'
          '<w:insideV w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
          "</w:tblBorders>")
    out = [f'<w:tbl><w:tblPr><w:tblW w:w="{total}" w:type="dxa"/>{bd}</w:tblPr>'
           f'<w:tblGrid><w:gridCol w:w="{total}"/></w:tblGrid>']
    for _ in range(rows):
        out.append(f'<w:tr><w:trPr><w:cantSplit/><w:trHeight w:val="{height}"/></w:trPr>'
                   f'<w:tc><w:tcPr><w:tcW w:w="{total}" w:type="dxa"/></w:tcPr>'
                   + para("", size=24, after=0) + "</w:tc></w:tr>")
    out.append("</w:tbl>" + SPACER)
    return "".join(out)


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    w, h = struct.unpack(">II", head[16:24])
    return w, h


MAP_W = int(BODY_W * 0.72)                  # 地圖最寬吃掉七成版面
MAP_H1 = int(5.8 / 2.54 * EMU)              # 也限高，免得一張圖就把當天擠到第二頁
MAP_H2 = int(5.4 / 2.54 * EMU)              # 一天有兩張圖時各自再矮一點


def image(rid, path, idx, max_w=MAP_W, max_h=MAP_H1):
    w, h = png_size(path)
    cx = min(max_w, int(w * EMU / 144))     # 截圖是 2 倍解析度 → 當成 144dpi
    cy = int(cx * h / w)
    if cy > max_h:
        cx, cy = int(cx * max_h / cy), max_h
    return (
        '<w:p><w:pPr><w:spacing w:before="40" w:after="60"/><w:jc w:val="center"/></w:pPr>'
        f'<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{idx}" name="map{idx}"/>'
        '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        f'<pic:pic><pic:nvPicPr><pic:cNvPr id="{idx}" name="map{idx}.png"/><pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
        "</a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>")


# ---------------------------------------------------------------- 從 index.html 撈 HTML 區塊
def section(html, sid):
    i = html.index(f'id="{sid}"')
    j = html.index("</section>", i)
    return html[i:j]


def htables(block):
    """回傳 [[[cell,…],…], …]——一個區塊裡的每張表。"""
    out = []
    for t in re.findall(r"<table>(.*?)</table>", block, re.S):
        rows = []
        for tr in re.findall(r"<tr>(.*?)</tr>", t, re.S):
            rows.append(re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S))
        out.append(rows)
    return out


def todos(block):
    """<ul class="todo"> → [(狀態, 內容)]，按 h3 分組。"""
    out = []
    for m in re.finditer(r"<h3>(.*?)</h3>(.*?)(?=<h3>|$)", block, re.S):
        items = [(plain(a), b) for a, b in
                 re.findall(r'<li><span class="d[^"]*">(.*?)</span><span>(.*?)</span></li>',
                            m.group(2), re.S)]
        if items:
            out.append((plain(m.group(1)), items))
    return out


# ---------------------------------------------------------------- 主體
def build(path, out_path, with_maps=True):
    html = open(path, encoding="utf-8").read()
    src = jsdata.data_area(path)
    DAYS = jsdata.const(src, "DAYS")
    CARDS = jsdata.const(src, "CARDS")

    root = os.path.dirname(os.path.abspath(path))
    mapdir = os.path.join(root, "assets", "print")
    rels, media = [], []

    def add_img(fname):
        p = os.path.join(mapdir, fname)
        if not (with_maps and os.path.exists(p)):
            return None
        rid = f"rId{100 + len(media)}"
        media.append((f"media/{fname}", p))
        rels.append(f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/'
                    f'officeDocument/2006/relationships/image" Target="media/{fname}"/>')
        return rid

    B = []
    H1 = dict(size=42, bold=1, color=BLUE, after=40)
    H2 = dict(size=34, bold=1, color=BLUE, before=200, after=120)
    H3 = dict(size=28, bold=1, before=160, after=60)
    BODY = dict(size=26, after=100)
    SMALL = dict(size=22, color=GREY, after=80)

    # ---- 封面
    B.append(para("2026 台灣行程", size=64, bold=1, color=BLUE, align="center", after=60))
    B.append(para("9 月 26 日（六）— 10 月 5 日（一）　十天九夜", size=30, align="center", after=200))
    kicker = re.search(r'<div class="route">(.*?)</div>', html, re.S)
    if kicker:
        B.append(rich(plain(kicker.group(1)), size=26, color=BLUE, align="center", after=240))
    for line in re.findall(r"<div>(去程|回程) (.*?)</div>", html, re.S)[:2]:
        B.append(rich(f"<b>{line[0]}</b>　{line[1]}", size=26, align="center", after=60))
    B.append(para("", after=200))
    B.append(rich("這是<b>紙本版</b>：十天的行程、時刻表與地圖都印在上面，"
                  "每天從新的一頁開始。手機上想看照片與地圖細節，請開網頁版。",
                  size=24, color=GREY, align="center"))

    # ---- 同行者・住宿
    B.append(pagebreak())
    pre = section(html, "pre")
    tbls = htables(pre)
    B.append(para("同行者", **H2))
    if tbls:
        B.append(table(tbls[0], [22, 48, 30]))
    B.append(para("住宿", **H2))
    if len(tbls) > 1:
        B.append(table(tbls[1], [22, 14, 30, 34]))
    m = re.search(r'<p class="mute"[^>]*>(.*?)</p>', pre, re.S)
    if m:
        B.append(rich(m.group(1), **SMALL))

    # ---- 每天一頁
    for d in DAYS:
        B.append(pagebreak())
        B.append(para(f"第 {d['n']} 天　{d['date']}（{d['wd']}）", size=24, color=BLUE,
                      bold=1, after=40))
        B.append(para(plain(d["title"]), **H1))
        if d.get("sub"):
            B.append(rich(d["sub"], size=23, color=GREY, after=100))

        info = []
        if d.get("stay") and d["stay"] != "—":
            info.append(f"<b>今晚住</b>　{d['stay']}")
        if d.get("who"):
            info.append(f"<b>同行</b>　{plain(d['who'])}")
        for t in info:
            B.append(rich(t, size=26, after=40, indent=140, border=RED))
        if info:
            B.append(para("", size=12, after=60))

        # 地圖（同一天可能有第二張）——兩張的話各自矮一點，才塞得進同一頁
        shots = [(f"day{d['n']}.png", "map"), (f"day{d['n']}_2.png", "map2")]
        have = sum(1 for f, _ in shots if os.path.exists(os.path.join(mapdir, f)))
        cap_h = MAP_H2 if have > 1 else MAP_H1
        for suffix, key in shots:
            rid = add_img(suffix)
            if not rid:
                continue
            cap = (d.get(key) or {}).get("cap")
            B.append(image(rid, os.path.join(mapdir, suffix), len(media), max_h=cap_h))
            if cap:
                B.append(rich(cap, size=19, color=GREY, align="center", after=100))

        # 時刻表
        tl = d.get("tl") or []
        if not tl and d.get("plans"):
            tl = d["plans"][0].get("tl") or []
        if tl:
            B.append(para("當天流程", **H3))
            B.append(table([["時間", "做什麼"]] + [[r["t"], r["h"]] for r in tl],
                           [20, 80], size=24))

        # 備註
        notes = d.get("notes") or {}
        labs = [("pack", "要帶什麼"), ("tickets", "票"), ("book", "要先訂・先約"),
                ("other", "注意"), ("rain", "下雨的話")]
        if any(notes.get(k) for k, _ in labs):
            B.append(para("提醒", **H3))
            for k, lab in labs:
                if notes.get(k):
                    B.append(rich(f"<b>{lab}</b>", size=23, color=BLUE, after=0))
                    B.append(rich(notes[k], size=23, after=50, indent=140, line=270, keep=1))

        # 當天的景點
        names = [CARDS[c]["name"] for c in (d.get("cards") or []) if c in CARDS]
        if names:
            B.append(rich("<b>當天會去的點</b>　" + "・".join(names), size=23,
                          color=GREY, before=80))

    # ---- 訂票・預約
    B.append(pagebreak())
    B.append(para("要訂的票・要預約的事項", **H2))
    for title, items in todos(section(html, "booking")):
        B.append(para(title, **H3))
        B.append(table([["狀態", "項目"]] + [[s, t] for s, t in items], [16, 84], size=24))

    # ---- 車票與費用
    B.append(pagebreak())
    B.append(para("車票與費用", **H2))
    tt = htables(section(html, "tickets"))
    if tt:
        B.append(table(tt[0], [22, 17, 14, 17, 30], size=21))

    # ---- 出發前要確認的事
    B.append(pagebreak())
    B.append(para("出發前要確認的事", **H2))
    chk = section(html, "check")
    items = [(plain(a), b) for a, b in
             re.findall(r'<li><span class="d[^"]*">(.*?)</span><span>(.*?)</span></li>', chk, re.S)]
    B.append(table([["何時", "要確認什麼"]] + [[s, t] for s, t in items], [15, 85], size=23))
    m = re.search(r'<p class="mute"[^>]*>(.*?)</p>', chk, re.S)
    if m:
        B.append(rich(m.group(1), **SMALL))

    # ---- 行李
    food = section(html, "food")
    packing = re.search(r"<h3>行李清單</h3>\s*<ul>(.*?)</ul>", food, re.S)
    if packing:
        B.append(pagebreak())
        B.append(para("行李清單", **H2))
        for li in re.findall(r"<li>(.*?)</li>", packing.group(1), re.S):
            B.append(rich("☐　" + plain(li), size=28, after=140))

    # ---- 筆記頁
    for i in range(3):
        B.append(pagebreak())
        B.append(para("筆記", **H2))
        B.append(notelines())

    # 表格後面的空段落，如果後面就是分頁，直接拿掉
    # 分頁改成掛在下一段的 pageBreakBefore 上。用單獨一個「只有分頁符號的段落」的話，
    # 前一頁剛好填滿時那個段落會自己佔掉一整頁，印出來就是一張全白的紙。
    out = []
    for i, x in enumerate(B):
        if x == pagebreak() and i + 1 < len(B) and B[i + 1].startswith("<w:p><w:pPr>"):
            nxt = B[i + 1]
            head = "<w:p><w:pPr>"
            if nxt.startswith(head + "<w:keepLines/>"):
                head += "<w:keepLines/>"
            B[i + 1] = head + "<w:pageBreakBefore/>" + nxt[len(head):]
            continue
        if x.endswith(SPACER) and i + 1 < len(B) and B[i + 1] == pagebreak():
            x = x[: -len(SPACER)]
        out.append(x)
    B = out

    sect = (f'<w:sectPr><w:pgSz w:w="{PAGE_W // 635}" w:h="{int(29.7 / 2.54 * EMU) // 635}"/>'
            f'<w:pgMar w:top="{MARGIN // 635}" w:right="{MARGIN // 635}" '
            f'w:bottom="{MARGIN // 635}" w:left="{MARGIN // 635}" '
            'w:header="708" w:footer="708" w:gutter="0"/>'
            '<w:footerReference w:type="default" r:id="rIdFooter"/></w:sectPr>')
    doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
           f"<w:document {NS}><w:body>{''.join(B)}{sect}</w:body></w:document>")

    write_docx(out_path, doc, rels, media)
    return len(DAYS), len(media)


def write_docx(out_path, document_xml, rels, media):
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Default Extension="png" ContentType="image/png"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
          'officedocument.wordprocessingml.document.main+xml"/>'
          '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-'
          'officedocument.wordprocessingml.styles+xml"/>'
          '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-'
          'officedocument.wordprocessingml.footer+xml"/></Types>')
    root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
                 '2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    doc_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
                '2006/relationships/styles" Target="styles.xml"/>'
                '<Relationship Id="rIdFooter" Type="http://schemas.openxmlformats.org/officeDocument/'
                '2006/relationships/footer" Target="footer1.xml"/>'
                + "".join(rels) + "</Relationships>")
    footer = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              f'<w:ftr {NS}><w:p><w:pPr><w:spacing w:before="0" w:after="0"/>'
              '<w:jc w:val="center"/></w:pPr>'
              f'<w:r>{rpr(size=18, color=GREY)}<w:fldChar w:fldCharType="begin"/></w:r>'
              f'<w:r>{rpr(size=18, color=GREY)}<w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
              f'<w:r>{rpr(size=18, color=GREY)}<w:fldChar w:fldCharType="end"/></w:r>'
              '</w:p></w:ftr>')
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              f'<w:styles {NS}><w:docDefaults><w:rPrDefault><w:rPr>'
              f'<w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:eastAsia="{FONT_EA}" w:cs="{FONT}"/>'
              '<w:sz w:val="26"/><w:szCs w:val="26"/></w:rPr></w:rPrDefault>'
              '<w:pPrDefault><w:pPr><w:spacing w:after="100" w:line="300" w:lineRule="auto"/>'
              '</w:pPr></w:pPrDefault></w:docDefaults>'
              '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/>'
              "</w:style></w:styles>")
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("word/_rels/document.xml.rels", doc_rels)
        z.writestr("word/styles.xml", styles)
        z.writestr("word/footer1.xml", footer)
        z.writestr("word/document.xml", document_xml)
        for name, path in media:
            z.write(path, "word/" + name)


def main():
    ap = argparse.ArgumentParser(description="把 index.html 匯出成可列印的 Word 檔")
    ap.add_argument("src", nargs="?", default="index.html")
    ap.add_argument("--out", default="台灣行程.docx")
    ap.add_argument("--no-maps", action="store_true", help="不要貼地圖（檔案小很多）")
    a = ap.parse_args()
    n, imgs = build(a.src, a.out, with_maps=not a.no_maps)
    size = os.path.getsize(a.out) / 1024
    print(f"寫出 {a.out}：{n} 天、{imgs} 張地圖、{size:.0f} KB")


if __name__ == "__main__":
    main()
