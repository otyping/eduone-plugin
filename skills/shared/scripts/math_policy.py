# -*- coding: utf-8 -*-
"""นโยบายเดียวว่า "อันไหนต้องเป็นวัตถุ Equation จริง อันไหนเป็นข้อความธรรมดา"

ใช้ร่วมกันทั้ง .docx (`docx_common`) และ .pptx (`pptx_common`) — ก่อนหน้านี้สองฝั่ง
ตัดสินคนละแบบ: pptx มีเกณฑ์คัดกรองอยู่แล้ว ส่วน docx บังคับให้ `$...$` ทุกอันเป็น OMML

ผลของการไม่มีเกณฑ์ฝั่ง docx (นับจากไฟล์จริงของ ม.1 คณิต คาบ 1)

    _ex.json        220 ช่วง `$...$`   เข้าข่ายต้องใช้ Equation จริง   0
    _C1.json         94 ช่วง                                          0
    _slides_C1.json  58 ช่วง                                          0

ยอดฮิตคือ `-2` `0` `1` `-3` — ตัวเลขโดด ๆ ที่ถูกห่อเป็นวัตถุ Equation ทั้งหมด
ซึ่งคัดลอกไม่ได้ ค้นหาไม่เจอ แก้ในเวิร์ดลำบาก และทำให้บรรทัดสูงผิดปกติ

เกณฑ์
    ใช้ Equation  เมื่อสูตร "ซ้อนชั้น" หรือเขียนด้วยอักขระธรรมดาไม่ได้
                  \\frac \\sqrt \\binom \\overline \\vec เมทริกซ์ ผลรวม/อินทิกรัลมีขอบเขต
    ใช้ข้อความ    ตัวเลข · + - × ÷ = ≥ ≤ ≠ ± · \\ldots · ยกกำลัง/ตัวห้อยชั้นเดียว
                  (ยกกำลัง/ตัวห้อยใช้ vertAlign ของ Word และ baseline ของ PowerPoint)

★ ตัวตัดสินอยู่ที่ตัว render ไม่ใช่ที่ writer — artifact JSON เดิมไม่ต้องแก้แม้แต่ไฟล์เดียว
  build ใหม่แล้วได้ผลถูกทันที และ writer ยังเขียน `$...$` ได้ตามสบายเหมือนเดิม
"""
from __future__ import annotations

import os
import re

#: symbols.txt อยู่ที่ ${CLAUDE_PLUGIN_ROOT}/skills/shared/ (ขึ้นจาก scripts/ 1 ชั้น)
SYMBOLS_PATH = os.path.join(os.path.dirname(__file__), "..", "symbols.txt")

_ALIAS_RE = re.compile(r"\\([A-Za-z]+)")

#: สูตรที่ "ซ้อนชั้น" — เขียนด้วยอักขระบรรทัดเดียวไม่ได้ ต้องเป็นวัตถุ Equation
_HARD_RE = re.compile(
    r"\\(frac|dfrac|tfrac|cfrac|sqrt|binom|begin|overline|underline|vec|bar|hat"
    r"|widehat|widetilde|matrix|substack|over|atop)\b"
)
#: ผลรวม/ผลคูณ/อินทิกรัล/ลิมิต จะซ้อนชั้นก็ต่อเมื่อมีขอบเขตกำกับ (`\sum_{i=1}^{n}`)
#  (ไม่ใส่ \b เพราะ `_` เป็นอักขระคำในสายตา regex — `\sum_{i=1}` จะไม่มีขอบคำตรงนั้น
#   และการบังคับ [_^] ต่อท้ายก็กันคำอื่นที่ขึ้นต้นเหมือนกันอยู่แล้ว)
_BIGOP_RE = re.compile(r"\\(sum|prod|int|oint|lim|coprod)\s*[_^]")

_OPS_RE = re.compile(r"\s*([\u00d7\u00f7\u00b1=\u2260\u2264\u2265\u2248\u2261])\s*")
_FUNC_RE = re.compile(r"^(sin|cos|tan|log|ln|exp|max|min|lim)$")
_LETTERS_RE = re.compile(r"[A-Za-z]+")
DEGREE = "\u00b0"


def _load_aliases(path=SYMBOLS_PATH):
    aliases = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.rstrip("\n").rstrip("\r")
                if not line or line.lstrip().startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 2 and parts[0].startswith("\\"):
                    aliases[parts[0][1:]] = parts[1]
    except FileNotFoundError:
        pass
    return aliases


_ALIASES = _load_aliases()


def apply_aliases(text):
    r"""แทน \alias ด้วย Unicode แบบ longest-match (\muA -> μA)"""
    def repl(m):
        rest = m.group(1)
        for length in range(len(rest), 0, -1):
            sym = _ALIASES.get(rest[:length])
            if sym is not None:
                return sym + rest[length:]
        return m.group(0)
    return _ALIAS_RE.sub(repl, text)


def is_hard(latex: str) -> bool:
    """สูตรนี้ต้องเป็นวัตถุ Equation จริงหรือไม่"""
    return bool(_HARD_RE.search(latex) or _BIGOP_RE.search(latex))


def split_italic(text: str, upright: bool):
    """ตัวแปรละตินตัวเดียวให้เอียง (ตาม math-symbols-guide) นอกนั้นตัวตรง"""
    if upright:
        return [(text, False)]
    out, pos = [], 0
    for m in _LETTERS_RE.finditer(text):
        if m.start() > pos:
            out.append((text[pos:m.start()], False))
        word = m.group(0)
        out.append((word, len(word) == 1 and not _FUNC_RE.match(word)))
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], False))
    return out or [(text, False)]


def simple_runs(latex: str):
    r"""LaTeX ที่ไม่ซ้อนชั้น -> [(text, vert, italic)]

    vert in {None, 'superscript', 'subscript'} — ผู้เรียกแปลงเป็นรูปแบบของตัวเอง
    (Word ใช้ w:vertAlign · PowerPoint ใช้ baseline %)

    ครอบ x^{2} · H_{2}O · 3.0 \times 10^{8} · 25\ \mathrm{cm^2} · \mathrm{30^\circ C}
    """
    s = latex
    s = re.sub(r"\\mathrm\s*\{([^{}]*)\}", lambda m: "\x01" + m.group(1) + "\x02", s)
    s = re.sub(r"\\(?:,|;|:|!|quad|qquad)", " ", s)
    s = s.replace("\\ ", "\x03")                  # \<เว้นวรรค> = ช่องว่างที่สั่งไว้จริง
    s = re.sub(r"(\\[A-Za-z]+) ", r"\1", s)       # LaTeX กลืนช่องว่างที่ปิดท้ายชื่อคำสั่ง
    s = apply_aliases(s).replace("\x03", " ")
    s = s.replace("\u2218", DEGREE)               # \circ -> องศา ไม่ใช่ ring operator
    s = re.sub(_OPS_RE, r" \1 ", s)               # คืนช่องว่างรอบเครื่องหมาย = × ÷ ...
    s = re.sub(r" {2,}", " ", s)

    runs = []
    upright = 0
    i = 0
    buf = []

    def flush(vert=None):
        if buf:
            txt = "".join(buf)
            for part, ital in split_italic(txt, upright > 0):
                if part:
                    runs.append((part, vert, ital))
            buf.clear()

    while i < len(s):
        c = s[i]
        if c == "\x01":
            flush(); upright += 1; i += 1; continue
        if c == "\x02":
            flush(); upright = max(0, upright - 1); i += 1; continue
        if c in "^_" and i + 1 < len(s):
            j = i + 1
            if s[j] == "{":
                k = s.find("}", j)
                inner, i = (s[j + 1:k], k + 1) if k != -1 else (s[j + 1:], len(s))
            else:
                inner, i = s[j], j + 1
            flush()
            inner = inner.replace("\x01", "").replace("\x02", "").strip()
            if inner == DEGREE:      # ^\circ — องศาลอยอยู่แล้ว ไม่ต้องยกซ้ำ
                runs.append((inner, None, False))
                continue
            vert = "superscript" if c == "^" else "subscript"
            for part, ital in split_italic(inner, True):
                if part:
                    runs.append((part, vert, ital))
            continue
        if c in "{}":
            i += 1
            continue
        buf.append(c)
        i += 1
    flush()
    return runs
