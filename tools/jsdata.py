#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 index.html 資料區的 JS 物件實字讀成 Python 資料。

只認得這份檔案實際用到的語法：未加引號的 key、單引號字串（含 \\' 跳脫）、
數字、true/false、陣列、物件、`'a'+'b'` 串接、// 與 /* */ 註解。
夠用就好——不是通用的 JS parser。
"""
import re

_WS = re.compile(r"(?:\s+|//[^\n]*|/\*.*?\*/)+", re.S)


class _P:
    def __init__(self, s, i=0):
        self.s, self.i = s, i

    def ws(self):
        m = _WS.match(self.s, self.i)
        if m:
            self.i = m.end()

    def value(self):
        self.ws()
        c = self.s[self.i]
        if c == "{":
            return self.obj()
        if c == "[":
            return self.arr()
        if c == "'" or c == '"':
            return self.string()
        return self.atom()

    def string(self):
        out = []
        while True:
            self.ws()
            q = self.s[self.i]
            if q not in "'\"":
                break
            self.i += 1
            buf = []
            while True:
                ch = self.s[self.i]
                if ch == "\\":
                    nxt = self.s[self.i + 1]
                    buf.append({"n": "\n", "t": "\t", "r": "\r"}.get(nxt, nxt))
                    self.i += 2
                elif ch == q:
                    self.i += 1
                    break
                else:
                    buf.append(ch)
                    self.i += 1
            out.append("".join(buf))
            save = self.i
            self.ws()
            if self.i < len(self.s) and self.s[self.i] == "+":   # 'a'+'b' 串接
                self.i += 1
                continue
            self.i = save
            break
        return "".join(out)

    def atom(self):
        m = re.compile(r"[^,}\]\s]+").match(self.s, self.i)
        tok = m.group(0)
        self.i = m.end()
        if tok == "true":
            return True
        if tok == "false":
            return False
        if tok == "null":
            return None
        try:
            return int(tok)
        except ValueError:
            pass
        try:
            return float(tok)
        except ValueError:
            return tok

    def arr(self):
        self.i += 1
        out = []
        while True:
            self.ws()
            if self.s[self.i] == "]":
                self.i += 1
                return out
            out.append(self.value())
            self.ws()
            if self.s[self.i] == ",":
                self.i += 1

    def obj(self):
        self.i += 1
        out = {}
        while True:
            self.ws()
            if self.s[self.i] == "}":
                self.i += 1
                return out
            if self.s[self.i] in "'\"":
                k = self.string()
            else:
                m = re.compile(r"[A-Za-z_$][\w$]*").match(self.s, self.i)
                k = m.group(0)
                self.i = m.end()
            self.ws()
            self.i += 1          # ':'
            out[k] = self.value()
            self.ws()
            if self.s[self.i] == ",":
                self.i += 1


def const(src, name):
    """讀出 `const NAME=…;` 的值。"""
    m = re.search(r"\bconst\s+" + name + r"\s*=\s*", src)
    if not m:
        raise KeyError(name)
    return _P(src, m.end()).value()


def data_area(path="index.html"):
    """回傳 index.html 第二段 <script> 裡 MAP ENGINE 之前的那段原始碼。"""
    s = open(path, encoding="utf-8").read()
    blocks = re.findall(r"<script>(.*?)</script>", s, re.S)
    body = blocks[1]
    return body[: body.index("/* ===== MAP ENGINE") if "/* ===== MAP ENGINE" in body
                else body.index("MAP ENGINE")]
