#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重生底圖的背景資訊層：TOWNLINES（鄉鎮區界）與 TOWNS（鄉鎮區名）。

只有在「日圖的尺度放到新的區域」時才需要跑——例如行程新增了南投的日子，
原本只有雙北基隆的區界，南投那幾張圖會變成一片空白。

用法：
  # 現在 index.html 用的設定（雙北基隆＋南投，日月潭與溪頭再補村里層）
  python3 tools/make_poi.py --lines 台北市 新北市 基隆市 南投縣 \
      --labels 台北市 新北市 基隆市 桃園縣 南投縣 \
      --village-towns 魚池鄉 鹿谷鄉 > poi.js

  # 只要台北尺度
  python3 tools/make_poi.py --lines 台北市 新北市 基隆市 \
      --labels 台北市 新北市 基隆市 桃園縣 桃園市 > poi.js

輸出是 `const TOWNLINES=[...];` 與 `const TOWNS=[...];` 兩段，
取代 index.html 第一段 <script> 裡對應的兩行。COUNTIES 與 STATIONS 不在這支工具的範圍。

--lines  要畫出界線的縣市（點數多，只給實際會放大到那個尺度的）
--labels 要標地名的縣市（只有一個字串，便宜，可以多給一點當周邊參考）

TOWNS 的第四個欄位是該區的經緯度跨幅 max(Δlat, Δlng)，引擎用它決定
「地圖縮到這個尺度時這個區名夠不夠大、要不要顯示」（見 areaBg）。

資料來源：g0v/twgeojson 鄉鎮市區界（twTown1982.geo.json）
"""
import json, math, sys, argparse, urllib.request

URL = "https://raw.githubusercontent.com/g0v/twgeojson/master/json/twTown1982.geo.json"
VILLAGE_URL = "https://raw.githubusercontent.com/g0v/twgeojson/master/json/twVillage1982.geo.json"


def dp(pts, eps):
    """Douglas-Peucker 簡化（用堆疊，避免深度遞迴爆掉）。"""
    n = len(pts)
    if n < 3:
        return pts

    def d(p, a, b):
        (x, y), (x1, y1), (x2, y2) = p, a, b
        dx, dy = x2 - x1, y2 - y1
        if dx == dy == 0:
            return math.hypot(x - x1, y - y1)
        t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
        return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))

    keep = [False] * n
    keep[0] = keep[n - 1] = True
    stack = [(0, n - 1)]
    while stack:
        i0, i1 = stack.pop()
        if i1 <= i0 + 1:
            continue
        a, b = pts[i0], pts[i1]
        imax, dmax = -1, eps
        for i in range(i0 + 1, i1):
            dd = d(pts[i], a, b)
            if dd > dmax:
                dmax, imax = dd, i
        if imax >= 0:
            keep[imax] = True
            stack.append((i0, imax))
            stack.append((imax, i1))
    return [p for p, k in zip(pts, keep) if k]


def rings(geom):
    if geom["type"] == "Polygon":
        return geom["coordinates"]
    return [r for poly in geom["coordinates"] for r in poly]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lines", nargs="+", required=True, help="要畫界線的縣市名")
    ap.add_argument("--labels", nargs="+", required=True, help="要標地名的縣市名")
    ap.add_argument("--url", default=URL)
    ap.add_argument("--eps", type=float, default=0.0015, help="界線簡化容差(度)")
    ap.add_argument("--min-pts", type=int, default=4, help="小於這個點數的環直接丟掉")
    ap.add_argument("--village-towns", nargs="*", default=[],
                    help="這些鄉鎮再補一層村里界與村里名。鄉鎮界在幾公里的尺度下"
                         "太粗（整個鄉只有一個地名點，放大後會落在畫面外），"
                         "日月潭、溪頭這種只有幾公里見方的日圖要靠村里層才有東西看。")
    a = ap.parse_args()

    print(f"下載 {a.url} ...", file=sys.stderr)
    g = json.load(urllib.request.urlopen(a.url))

    line_set, label_set = set(a.lines), set(a.labels)
    for name in line_set | label_set:
        if not any(f["properties"]["COUNTYNAME"] == name for f in g["features"]):
            print(f"!! 找不到縣市 {name}", file=sys.stderr)

    lines, labels = [], []
    for f in g["features"]:
        p = f["properties"]
        county = p["COUNTYNAME"]
        if county not in line_set and county not in label_set:
            continue
        rs = rings(f["geometry"])
        if county in line_set:
            for r in rs:
                sr = dp(r, a.eps)
                if len(sr) >= a.min_pts:
                    lines.append([[round(y, 4), round(x, 4)] for x, y in sr])
        if county in label_set:
            best = max(rs, key=len)
            xs = [x for x, y in best]
            ys = [y for x, y in best]
            # 標籤點＝最大環的頂點平均；size＝該區的經緯度跨幅，引擎用它判斷顯不顯示
            size = max(max(ys) - min(ys), max(xs) - min(xs))
            labels.append((p["TOWNNAME"], round(sum(ys) / len(ys), 4),
                           round(sum(xs) / len(xs), 4), round(size, 3)))

    if a.village_towns:
        print(f"下載村里界 {VILLAGE_URL} ...", file=sys.stderr)
        gv = json.load(urllib.request.urlopen(VILLAGE_URL))
        want = set(a.village_towns)
        n0 = len(lines)
        for f in gv["features"]:
            p = f["properties"]
            if p["TOWNNAME"] not in want:
                continue
            rs = rings(f["geometry"])
            for r in rs:
                sr = dp(r, a.eps)
                if len(sr) >= a.min_pts:
                    lines.append([[round(y, 4), round(x, 4)] for x, y in sr])
            best = max(rs, key=len)
            xs = [x for x, y in best]
            ys = [y for x, y in best]
            size = max(max(ys) - min(ys), max(xs) - min(xs))
            labels.append((p["VILLAGENAM"], round(sum(ys) / len(ys), 4),
                           round(sum(xs) / len(xs), 4), round(size, 3)))
        print(f"  村里界多了 {len(lines)-n0} 環", file=sys.stderr)

    out = "const TOWNLINES=" + json.dumps(lines, separators=(",", ":")) + ";\n"
    out += "const TOWNS=[" + ",".join(
        "['%s',%s,%s,%s]" % (n, la, lo, sz) for n, la, lo, sz in labels) + "];\n"
    sys.stdout.write(out)
    pts = sum(len(l) for l in lines)
    print(f"界線環={len(lines)} 點={pts} / 地名={len(labels)} / 共 {len(out)/1024:.0f}KB",
          file=sys.stderr)


if __name__ == "__main__":
    main()
