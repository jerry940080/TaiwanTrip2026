#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重生底圖的周邊地名層 POIS——地圖太空的解法。

每日地圖原本只畫得出「行程上的點」，其餘一片空白；日月潭那張連湖都沒有，
溪頭那張只有一條線。這支工具從國土測繪中心的地標資料撈出<b>路線附近</b>的
景點、公園、車站等，變成淡色的小點＋地名，補在背景上，就像一般地圖會標的
周邊地標。座標全部來自官方資料，不是自己估的。

用法（現在 index.html 用的設定）：
  python3 tools/make_pois.py > pois.js
輸出一行 `const POIS=[...];`，取代 index.html 第一段 <script> 裡那一行。

--radius 只收路線點周圍這個距離內的地標（公里）。調大會變得很吵。
--per-cluster 每一叢路線點最多收幾個，避免台北市區一口氣塞幾百個。

資料來源：ronnywang/maps.nlsc.gov.tw（國土測繪中心地標開放資料）
"""
import csv, io, json, math, re, sys, argparse, urllib.request

BASE = "https://raw.githubusercontent.com/ronnywang/maps.nlsc.gov.tw/master/landmark/country/%s.csv"
COUNTIES = {"a": "臺北市", "b": "臺中市", "c": "基隆市", "f": "新北市", "m": "南投縣"}

# 只收「地圖上標出來有意義」的類別。飯店、加油站、國小、行政機關、
# 金融機構那些數量大又幫不上忙，一律不收。
# 分兩級：先收第一級，位子還有剩才補第二級。飯店在山區是唯一的地標
# （溪頭就是靠立德、米堤這些認路），但在台北市區會把真正的景點擠掉。
KEEP1 = {"觀光遊憩設施", "一般公園", "火車站", "客運站", "傳統市場", "大學及研究所"}
KEEP2 = {"飯店", "娛樂設施", "百貨公司", "生活百貨量販"}

# 地標名稱常常帶著一長串前綴，地圖上塞不下，這裡剃掉
STRIP = [r"^南投縣立", r"^臺北市立", r"^台北市立", r"^新北市立", r"^基隆市立", r"^臺中市立",
         r"^南投縣", r"^臺北市", r"^台北市", r"^新北市", r"^基隆市", r"^臺中市", r"^台中市",
         r"^縣立", r"^市立", r"^國立", r"^私立",
         r"^溪頭森林遊樂園", r"^溪頭自然教育園區", r"^日月潭", r"^臺大實驗林", r"^台大實驗林",
         r"^南投縣政府", r"^臺北市政府", r"^中油加油站-?"]
DROP = re.compile(
    r"停車場|廁所|管理處|辦公室|派出所|分駐所|清潔隊|代表會|戶政|衛生所"
    r"|民宿|旅社|旅店|旅館|商旅|山莊|會館|專賣街|零售市場|協會|婦聯|公司|研究所"
    r"|觀光局|客運站$|[(（][^)）]{0,4}[)）]"
    r"|[(（]\d+[)）]"          # 「瑞芳公園(3)」這種只有編號的
    r"|^[一二三四五六七八九十百]?[0-9一二三四五六七八九十]*號公園"
    r"|[0-9一二三四五六七八九十]號公園|[0-9一二三四五六七八九十]號綠地"
    r"|^體育場$|^大飯店$|^公園$|^市場$")
# 只有四五個字的「X公園」多半是社區小綠地，標出來沒有意義；
# 大安森林公園、涵碧半島景觀公園這種長名字才是真的地標。
def too_small(name):
    return (name.endswith("公園") or name.endswith("綠地")) and len(name) <= 5


def clean(name):
    # 前綴會疊好幾層（「南投縣臺大實驗林溪頭自然教育園區遊客服務中心」），
    # 一輪剃不乾淨，剃到不再變化為止
    for _ in range(6):
        before = name
        for pat in STRIP:
            name = re.sub(pat, "", name)
        name = name.strip("－- 　")
        if name == before:
            break
    return name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="index.html")
    ap.add_argument("--radius", type=float, default=2.0, help="離路線點多少公里以內才收")
    ap.add_argument("--per-cluster", type=int, default=14, help="每個路線點最多帶幾個周邊地標")
    ap.add_argument("--skip", type=float, default=0.12,
                    help="離路線點比這個近（公里）就不收，那多半就是同一個地方")
    ap.add_argument("--spacing", type=float, default=0.45,
                    help="地標彼此至少隔開幾公里，避免密集區擠成一團")
    ap.add_argument("--max-name", type=int, default=9, help="名字超過這個長度就不收，地圖上塞不下")
    a = ap.parse_args()

    # 從 index.html 的 P 撈出所有路線點，只在這些點附近找地標
    src = io.open(a.index, encoding="utf-8").read()
    blk = src[src.index("const P="):src.index("const RAILS=")]
    anchors = [(float(la), float(lo)) for la, lo in
               re.findall(r":\[(\d\d\.\d+),(\d\d\d\.\d+)\]", blk)]
    print("路線點 %d 個" % len(anchors), file=sys.stderr)

    seen, out = [], []
    for code, cname in COUNTIES.items():
        print("下載 %s ..." % cname, file=sys.stderr)
        raw = urllib.request.urlopen(BASE % code).read().decode("utf-8")
        rows = list(csv.DictReader(io.StringIO(raw)))
        cand = []
        for r in rows:
            tier = 0 if r["小類別名稱"] in KEEP1 else 1 if r["小類別名稱"] in KEEP2 else None
            if tier is None:
                continue
            name = clean(r["地標名稱"])
            if not name or len(name) > a.max_name or DROP.search(name) or too_small(name):
                continue
            try:
                la, lo = float(r["緯度"]), float(r["經度"])
            except ValueError:
                continue
            cand.append((tier, name, la, lo))
        # 依「離最近的路線點多遠」排序，一個路線點只留最近的幾個
        per = {}
        for tier, name, la, lo in cand:
            best, bi = 1e9, None
            for i, (ala, alo) in enumerate(anchors):
                d = math.hypot((la - ala) * 110.9, (lo - alo) * 101.7)
                if d < best:
                    best, bi = d, i
            if best > a.radius or best < a.skip:
                continue          # 太遠不收；太近就是路線點本身，會疊字
            per.setdefault(bi, []).append((tier, best, name, la, lo))
        for bi, lst in per.items():
            # 飯店這類第二級只有在附近幾乎沒有景點時才補上——山區靠它認路，
            # 台北市區放進去只會把真正的地標擠掉。
            n1 = sum(1 for t, *_ in lst if t == 0)
            pick = sorted(lst if n1 < 3 else [x for x in lst if x[0] == 0])
            for _, _, name, la, lo in pick[:a.per_cluster]:
                # 同名或幾乎同位置的只留一個（官方資料同一個地方常有兩三筆）
                if any(n == name or math.hypot((la - y) * 110.9, (lo - z) * 101.7) < .2
                       for n, y, z in seen):
                    continue
                seen.append((name, la, lo))
                out.append([name, round(la, 5), round(lo, 5)])

    # 疏化：台北市區地標密到誰也看不清，強制彼此至少隔開一段距離
    thin, kept = [], []
    for name, la, lo in out:
        if any(math.hypot((la - y) * 110.9, (lo - z) * 101.7) < a.spacing for y, z in kept):
            continue
        kept.append((la, lo)); thin.append([name, la, lo])
    print("疏化 %d → %d" % (len(out), len(thin)), file=sys.stderr)
    out = thin
    out.sort(key=lambda t: (t[1], t[2]))
    line = "const POIS=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n"
    sys.stdout.write(line)
    print("地名 %d 個 / %.0fKB" % (len(out), len(line) / 1024), file=sys.stderr)


if __name__ == "__main__":
    main()
