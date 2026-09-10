#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重生模板用的海岸線／行政區輪廓資料（LAND）。

用法（台灣，預設）：
  python3 tools/make_land.py --preset taiwan --all > land.js
  python3 tools/make_land.py --preset taiwan --regions 台北市 新北市 宜蘭縣 --eps 0.0005 > land.js

用法（日本）：
  python3 tools/make_land.py --preset japan --lat0 34.4 --lat1 36.0 --lng0 138.2 --lng1 140.6 \
      --regions 静岡県 神奈川県 東京都 千葉県 山梨県 埼玉県 > land.js

只把某一小塊畫細（例如要放大到步行尺度的八斗子）：
  python3 tools/make_land.py --preset taiwan --all --eps 0.002 \
      --fine-eps 0.00015 --fine-lat0 25.125 --fine-lat1 25.155 --fine-lng0 121.785 --fine-lng1 121.815 > land.js

用法（其他國家，Natural Earth 海岸線）：
  python3 tools/make_land.py --preset world --lat0 -45 --lat1 -34 --lng0 166 --lng1 179 > land.js

輸出是一整段 `const LAND=[...];`，直接取代 index.html 第一段 <script> 的內容。
純城市行程不想要地形，可以直接寫 `const LAND=[];`（地圖變純色底）。

資料來源：
  taiwan → g0v/twgeojson 縣市界（COUNTYNAME）
  japan  → dataofjapan/land 都道府縣界（nam_ja）
  world  → Natural Earth 10m coastline（無屬性，只能用 bbox 篩）
"""
import json, math, sys, argparse, urllib.request

PRESETS = {
    "taiwan": {
        "url": "https://raw.githubusercontent.com/g0v/twgeojson/master/json/twCounty2010.geo.json",
        "prop": "COUNTYNAME",
        "bbox": (21.5, 25.5, 119.3, 122.3),
    },
    "japan": {
        "url": "https://raw.githubusercontent.com/dataofjapan/land/master/japan.geojson",
        "prop": "nam_ja",
        "bbox": (24.0, 46.0, 122.0, 154.0),
    },
    "world": {
        "url": "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_coastline.geojson",
        "prop": None,
        "bbox": (-90.0, 90.0, -180.0, 180.0),
    },
}


def dp(pts, eps, fine=None, eps_fine=None):
    """Douglas-Peucker 簡化（用堆疊，避免深度遞迴爆掉）。

    fine 給 (lat0, lat1, lng0, lng1) 時，落在那個範圍內的點改用 eps_fine 判斷，
    可以只把某一小塊海岸線畫細（例如要放大到步行尺度的那一區），其他地方維持粗簡化。
    """
    n = len(pts)
    if n < 3:
        return pts

    def thresh(p):
        if fine and fine[0] <= p[1] <= fine[1] and fine[2] <= p[0] <= fine[3]:
            return eps_fine
        return eps

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
        # 用「距離／該點的容差」的比值來挑，這樣不同區域可以有不同容差
        imax, rmax = -1, 1.0
        for i in range(i0 + 1, i1):
            r = d(pts[i], a, b) / thresh(pts[i])
            if r > rmax:
                rmax, imax = r, i
        if imax >= 0:
            keep[imax] = True
            stack.append((i0, imax))
            stack.append((imax, i1))
    return [p for p, k in zip(pts, keep) if k]


def rings(geom):
    t = geom["type"]
    if t == "Polygon":
        yield from geom["coordinates"]
    elif t == "MultiPolygon":
        for poly in geom["coordinates"]:
            yield from poly
    elif t == "LineString":
        yield geom["coordinates"]
    elif t == "MultiLineString":
        yield from geom["coordinates"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="taiwan", choices=sorted(PRESETS), help="資料來源")
    ap.add_argument("--url", help="自訂 GeoJSON 網址（蓋掉 preset）")
    ap.add_argument("--prop", help="用來比對 --regions 的屬性欄位（蓋掉 preset）")
    ap.add_argument("--regions", nargs="+", default=[], help="要保留的行政區名，例：台北市 宜蘭縣")
    ap.add_argument("--all", action="store_true", help="不篩行政區，全部收進來（再由 bbox 過濾）")
    ap.add_argument("--lat0", type=float)
    ap.add_argument("--lat1", type=float)
    ap.add_argument("--lng0", type=float)
    ap.add_argument("--lng1", type=float)
    ap.add_argument("--eps", type=float, default=0.0007, help="簡化容差(度)，越大檔越小")
    ap.add_argument("--fine-eps", type=float, help="細節區的容差，配合 --fine-* 四個邊界")
    ap.add_argument("--fine-lat0", type=float)
    ap.add_argument("--fine-lat1", type=float)
    ap.add_argument("--fine-lng0", type=float)
    ap.add_argument("--fine-lng1", type=float)
    ap.add_argument("--min-pts", type=int, default=5, help="小於這個點數的環直接丟掉（濾掉小島）")
    a = ap.parse_args()

    pre = PRESETS[a.preset]
    url = a.url or pre["url"]
    prop = a.prop or pre["prop"]
    b = pre["bbox"]
    lat0 = a.lat0 if a.lat0 is not None else b[0]
    lat1 = a.lat1 if a.lat1 is not None else b[1]
    lng0 = a.lng0 if a.lng0 is not None else b[2]
    lng1 = a.lng1 if a.lng1 is not None else b[3]

    if not a.all and not a.regions:
        if prop:
            sys.exit("!! 請給 --regions（行政區名）或 --all")
        a.all = True

    print(f"下載 {url} ...", file=sys.stderr)
    g = json.load(urllib.request.urlopen(url))
    feats = g["features"]

    if not a.all:
        picked = []
        for name in a.regions:
            hit = [f for f in feats if f["properties"].get(prop) == name]
            if not hit:
                print(f"!! 找不到 {name}（欄位 {prop}）", file=sys.stderr)
            picked += hit
        feats = picked

    fine = None
    if a.fine_eps is not None:
        if None in (a.fine_lat0, a.fine_lat1, a.fine_lng0, a.fine_lng1):
            sys.exit("!! --fine-eps 要配 --fine-lat0/lat1/lng0/lng1 一起給")
        fine = (a.fine_lat0, a.fine_lat1, a.fine_lng0, a.fine_lng1)
        print(f"細節區 {fine} 容差 {a.fine_eps}", file=sys.stderr)

    out = []
    for f in feats:
        for r in rings(f["geometry"]):
            if not any(lat0 <= y <= lat1 and lng0 <= x <= lng1 for x, y in r):
                continue
            sr = dp(r, a.eps, fine, a.fine_eps)
            if len(sr) < a.min_pts:
                continue
            # 細節區的點留 5 位小數（約 1 公尺），其餘 4 位（約 11 公尺）——只在需要的地方付檔案大小
            def rd(x, y):
                if fine and fine[0] <= y <= fine[1] and fine[2] <= x <= fine[3]:
                    return [round(x, 5), round(y, 5)]
                return [round(x, 4), round(y, 4)]
            out.append([rd(x, y) for x, y in sr])

    sys.stdout.write("const LAND=" + json.dumps(out, separators=(",", ":")) + ";\n")
    pts = sum(len(o) for o in out)
    print(f"rings={len(out)} points={pts} approx={pts*13/1024:.0f}KB", file=sys.stderr)


if __name__ == "__main__":
    main()
