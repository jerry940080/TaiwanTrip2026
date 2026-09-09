#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""改完 index.html 的資料區後跑一次，抓常見手滑。

用法：python3 tools/check.py [index.html]

檢查：
  1. 兩段 <script> 的括號有沒有對稱（少一個 } 整頁就白畫面）
  2. DAYS 引用的地點 key 都在 P 裡
  3. DAYS 引用的卡片 key 都在 CARDS 裡
  4. legs 的 mode 都在 MODE 裡（漏了圖例會炸）
  5. P 裡有座標但 NAMES 沒給顯示名的點（會顯示成英文 key）
  6. 座標有沒有掉出台灣範圍（打錯經緯度最常見的症狀）
"""
import re, sys

TW = (21.5, 25.5, 119.3, 122.3)  # lat0, lat1, lng0, lng1


def block(s, name, open_ch, close_ch):
    """粗略抓出 `const NAME={...};` 或 `const NAME=[...];` 的內容。"""
    m = re.search(r"const\s+" + name + r"\s*=\s*" + re.escape(open_ch), s)
    if not m:
        return ""
    i = m.end() - 1
    depth = 0
    for j in range(i, len(s)):
        if s[j] == open_ch:
            depth += 1
        elif s[j] == close_ch:
            depth -= 1
            if depth == 0:
                return s[i:j + 1]
    return ""


def keys_of(body, top_only=True):
    """抓出物件的鍵。top_only=True 時只取最外層（不會把 name:/kind: 這種內層欄位算進去）。"""
    out, depth, i, n = set(), 0, 0, len(body)
    while i < n:
        ch = body[i]
        if ch in "'\"":
            q = ch
            i += 1
            while i < n and body[i] != q:
                i += 2 if body[i] == "\\" else 1
        elif ch in "{[(":
            depth += 1
        elif ch in "}])":
            depth -= 1
        elif not top_only or depth == 1:
            m = re.match(r"([A-Za-z_]\w*)\s*:", body[i:])
            if m and (i == 0 or not re.match(r"[\w$.]", body[i - 1])):
                out.add(m.group(1))
                i += m.end() - 1
        i += 1
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "index.html"
    s = open(path, encoding="utf-8").read()
    bad = []

    scripts = re.findall(r"<script>(.*?)</script>", s, re.S)
    if len(scripts) != 2:
        bad.append(f"預期 2 段 <script>，實際 {len(scripts)} 段")
    for n, sc in enumerate(scripts):
        stripped = re.sub(r"'[^'\n]*'|\"[^\"\n]*\"|`[^`]*`|//[^\n]*|/\*.*?\*/", "", sc, flags=re.S)
        for o, c, lab in (("{", "}", "大括號"), ("[", "]", "中括號"), ("(", ")", "小括號")):
            if stripped.count(o) != stripped.count(c):
                bad.append(f"script #{n+1} {lab}不對稱：{stripped.count(o)} 個 {o} vs {stripped.count(c)} 個 {c}")

    P = block(s, "P", "{", "}")
    pkeys = keys_of(P)
    ckeys = keys_of(block(s, "CARDS", "{", "}"))
    mkeys = keys_of(block(s, "MODE", "{", "}"))
    nkeys = keys_of(block(s, "NAMES", "{", "}"))
    days = block(s, "DAYS", "[", "]")
    hero = s[s.find("const cfg={pts:"):]
    hero = hero[:hero.find("};") + 2] if "const cfg={pts:" in s else ""

    used_pts, used_modes, used_cards = set(), set(), set()
    for src in (days, hero):
        for m in re.finditer(r"\b(?:a|b)\s*:\s*'([^']+)'", src):
            used_pts.add(m.group(1))
        for m in re.finditer(r"\b(?:pts|via)\s*:\s*\[([^\]]*)\]", src):
            used_pts |= set(re.findall(r"'([^']+)'", m.group(1)))
        for m in re.finditer(r"\bmode\s*:\s*'([^']+)'", src):
            used_modes.add(m.group(1))
    for m in re.finditer(r"\bcards\s*:\s*\[([^\]]*)\]", days):
        used_cards |= set(re.findall(r"'([^']+)'", m.group(1)))
    labels = set()
    for m in re.finditer(r"\blabels\s*:\s*\{([^}]*)\}", days + hero):
        labels |= keys_of(m.group(1), top_only=False)

    for k in sorted((used_pts | labels) - pkeys):
        bad.append(f"地點 '{k}' 被行程引用，但 P 裡沒有座標")
    for k in sorted(used_cards - ckeys):
        bad.append(f"卡片 '{k}' 被行程引用，但 CARDS 裡沒有")
    for k in sorted(used_modes - mkeys):
        bad.append(f"交通方式 '{k}' 被行程引用，但 MODE 裡沒有（圖例會炸）")
    for k in sorted(used_pts - nkeys):
        bad.append(f"提醒：地點 '{k}' 沒有 NAMES 顯示名，地圖上會印出英文 key")

    for k, la, lo in re.findall(r"(\w+)\s*:\s*\[\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\]", P):
        la, lo = float(la), float(lo)
        if not (TW[0] <= la <= TW[1] and TW[2] <= lo <= TW[3]):
            bad.append(f"提醒：'{k}' 的座標 [{la},{lo}] 掉出台灣範圍，確認有沒有把經緯度寫反")

    if bad:
        print("\n".join("!! " + b for b in bad))
        sys.exit(1 if any(not b.startswith("提醒") for b in bad) else 0)
    ndays = len(re.findall(r"\{n:'?[\d-]+", days))  # n 可能是 5 或 '5-7'（合併多天的區塊）
    print(f"OK：{len(pkeys)} 個地點、{len(ckeys)} 張卡片、{ndays} 天行程，沒有發現問題")


if __name__ == "__main__":
    main()
