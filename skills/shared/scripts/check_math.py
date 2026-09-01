# -*- coding: utf-8 -*-
"""
check_math.py — ตรวจสัญลักษณ์คณิต/วิทย์ในไฟล์ JSON ก่อน build เอกสาร

ตรวจ 3 อย่าง
  1. ทุกสูตรใน $...$ แปลงเป็น OMML (Word Equation) ได้จริง
  2. `$` ครบคู่ (ไม่มีที่เปิดแล้วไม่ปิด)
  3. รูปแบบต้องห้ามที่ควรใช้กลไกของระบบแทน — 3/4, x^2, H2O, <=, ครอบไทยด้วย $

ใช้:
  check_math.py <ไฟล์.json> [--strict]
  --strict = นับ "รูปแบบต้องห้าม" เป็นความผิดด้วย (ค่าเริ่มต้นเป็นคำเตือน)

exit 0 = ผ่าน / 1 = พบปัญหา / 2 = usage
รองรับทั้ง {BASE}_ex.json (questions[]) และ JSON อื่น ๆ (ไล่ทุก string ในไฟล์)

รันผ่านตัวห่อ: eduone-py <ชื่อไฟล์นี้> <args>  (หา Python 3.12 ให้เองทุก OS)
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import docx_common as dc  # noqa: E402

THAI_RE = re.compile(r"[฀-๿]")
MATH_SPAN_RE = re.compile(r"\$([^$]+)\$")

# รูปแบบต้องห้าม -> คำแนะนำ
BAD_PATTERNS = [
    (re.compile(r"(?<![\d$\\])\b\d+\s*/\s*\d+\b(?![^$]*\$)"),
     "เศษส่วนแบบขีดทับ (เช่น 3/4) -> ใช้ $\\\\frac{3}{4}$"),
    (re.compile(r"[A-Za-z0-9\)]\^(?!\{)"),
     "ยกกำลังไม่มีปีกกา (เช่น x^2) -> ใช้ x^{2}"),
    (re.compile(r"\b(?:H2O|CO2|O2|N2|H2SO4|NaCl2|CH4|NH3)\b"),
     "สูตรเคมีไม่มีตัวห้อย (เช่น H2O) -> ใช้ H_{2}O"),
    (re.compile(r"(<=|>=|!=|=<|=>)"),
     "เครื่องหมายเปรียบเทียบแบบ ASCII -> ใช้ \\\\leq \\\\geq \\\\neq"),
    (re.compile(r"[½¼¾⅓⅔⅛²³⁴]"),
     "อักขระ Unicode เศษส่วน/ยกกำลังพิมพ์ตรง ๆ -> ใช้ $\\\\frac{}{}$ หรือ ^{}"),
]

# ตัวเลข 4 หลักขึ้นไปที่ไม่ได้คั่นหลักพัน (ตรวจแยกเพราะต้องดูทั้งในและนอก $...$)
THOUSANDS_RE = re.compile(r"(?<![\d,.])\d{4,}(?![\d,])")
# ปี พ.ศ./ค.ศ. ไม่ต้องคั่น — ข้ามเมื่อมีคำบอกปีนำหน้า
YEAR_CONTEXT_RE = re.compile(r"(พ\.?ศ\.?|ค\.?ศ\.?|ปี)\s*$")

# ---- สัญญาความพกพา: JSON ต้องใช้ LaTeX มาตรฐานใน $...$ เท่านั้น ----
# เพราะ JSON ถูกใช้ทั้งโดย build_exercise.py (-> Word Equation) และระบบข้อสอบเว็บ (-> KaTeX)
CMD_RE = re.compile(r"\\([A-Za-z]+)")
SUPSUB_OUT_RE = re.compile(r"[\^_]\{")

# คำสั่งที่ทั้ง Word (latex2mathml) และ KaTeX รองรับ
KATEX_SAFE = {
    "frac", "dfrac", "tfrac", "sqrt",
    "times", "div", "cdot", "pm", "mp",
    "leq", "geq", "le", "ge", "neq", "ne", "approx", "equiv", "propto", "sim", "ll", "gg",
    "angle", "perp", "parallel", "circ", "triangle",
    "alpha", "beta", "gamma", "delta", "epsilon", "varepsilon", "zeta", "eta", "theta",
    "iota", "kappa", "lambda", "mu", "nu", "xi", "rho", "sigma", "tau", "upsilon",
    "phi", "varphi", "chi", "psi", "omega", "pi",
    "Gamma", "Delta", "Theta", "Lambda", "Xi", "Pi", "Sigma", "Upsilon", "Phi", "Psi", "Omega",
    "sum", "prod", "int", "infty", "partial", "nabla",
    "sin", "cos", "tan", "log", "ln", "exp", "min", "max",
    "to", "rightarrow", "leftarrow", "leftrightarrow",
    "Rightarrow", "Leftarrow", "Leftrightarrow", "uparrow", "downarrow",
    "mathrm", "text", "left", "right", "ldots", "cdots", "dots", "bullet", "prime",
}
# alias เฉพาะโปรเจกต์ที่ KaTeX ไม่รู้จัก -> ตัวแทนมาตรฐาน
ALIAS_FIX = {
    "ohm": "\\Omega", "celsius": "\\mathrm{^\\circ C}", "micro": "\\mu",
    "degree": "^\\circ", "dprime": "''", "gets": "\\leftarrow",
}


def iter_strings(node, path="$"):
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from iter_strings(v, "%s.%s" % (path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from iter_strings(v, "%s[%d]" % (path, i))


def check_text(where, text, problems, warnings):
    # 1) $ ครบคู่
    if text.count("$") % 2 != 0:
        problems.append("%s: เครื่องหมาย $ ไม่ครบคู่ -> %s" % (where, text[:70]))
        return

    # 2) ทุกสูตรแปลงเป็น OMML ได้ + ใช้เฉพาะคำสั่งที่ KaTeX รองรับ
    for formula in MATH_SPAN_RE.findall(text):
        if not formula.strip():
            problems.append("%s: มี $$ ว่าง" % where)
            continue
        if THAI_RE.search(formula):
            problems.append("%s: มีข้อความไทยอยู่ใน $...$ (จะเพี้ยนใน Word) -> $%s$"
                            % (where, formula[:50]))
            continue
        if dc.latex_to_omml(formula) is None:
            problems.append("%s: แปลงสมการไม่ได้ -> $%s$" % (where, formula[:60]))
        for c in CMD_RE.findall(formula):
            if c in KATEX_SAFE:
                continue
            fix = ALIAS_FIX.get(c)
            problems.append(
                "%s: คำสั่ง \\%s ไม่อยู่ใน whitelist ระบบข้อสอบเว็บ (KaTeX) จะ render ไม่ได้%s"
                % (where, c, (" -> ใช้ %s แทน" % fix) if fix else ""))

    # 2b) สัญกรณ์คณิตต้องไม่หลุดออกนอก $...$ (ไม่งั้นเว็บแสดงเป็นข้อความดิบ)
    outside_math = MATH_SPAN_RE.sub(" ", text)
    for c in CMD_RE.findall(outside_math):
        problems.append("%s: \\%s อยู่นอก $...$ — ต้องย้ายเข้าไปใน $...$ ไม่งั้นเว็บอ่านไม่ออก"
                        % (where, c))
    if SUPSUB_OUT_RE.search(outside_math):
        problems.append("%s: ตัวยก/ตัวห้อย ^{} หรือ _{} อยู่นอก $...$ — ต้องย้ายเข้าไปใน $...$"
                        % where)

    # 3) รูปแบบต้องห้าม (ตรวจเฉพาะนอก $...$)
    outside = MATH_SPAN_RE.sub(" ", text)
    for rx, advice in BAD_PATTERNS:
        m = rx.search(outside)
        if m:
            warnings.append("%s: %s  (เจอ %r)" % (where, advice, m.group(0)))

    # 4) เครื่องหมายคั่นหลักพัน — ตรวจทั้งข้อความและในสมการ (ข้ามปี พ.ศ./ค.ศ.)
    for m in THOUSANDS_RE.finditer(text):
        if YEAR_CONTEXT_RE.search(text[:m.start()]):
            continue
        warnings.append("%s: ตัวเลข %s ควรคั่นหลักพันเป็น %s (ใช้ได้ทั้งในและนอก $...$)"
                        % (where, m.group(0), "{:,}".format(int(m.group(0)))))
        break


def main():
    ap = argparse.ArgumentParser(description="ตรวจสัญลักษณ์คณิต/วิทย์ใน JSON")
    ap.add_argument("json_file")
    ap.add_argument("--strict", action="store_true",
                    help="นับรูปแบบต้องห้ามเป็นความผิดด้วย")
    args = ap.parse_args()

    # utf-8-sig = ทนทั้งไฟล์ที่มี BOM (Notepad) และไม่มี BOM
    with open(args.json_file, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    problems, warnings = [], []
    n_formula = 0
    for where, text in iter_strings(data):
        interesting = ("$" in text
                       or CMD_RE.search(text)          # \alias หลุดนอกสมการ
                       or SUPSUB_OUT_RE.search(text)   # ^{} _{} หลุดนอกสมการ
                       or any(rx.search(text) for rx, _ in BAD_PATTERNS)
                       or THOUSANDS_RE.search(text))
        if not interesting:
            continue
        n_formula += len(MATH_SPAN_RE.findall(text))
        check_text(where, text, problems, warnings)

    if dc.latex_to_omml(r"\frac{1}{2}") is None:
        print("WARN: เครื่องนี้แปลง LaTeX -> OMML ไม่ได้ (ขาด latex2mathml?) "
              "สมการจะตกเป็นข้อความธรรมดา", file=sys.stderr)

    print("ตรวจแล้ว: พบสูตรใน $...$ จำนวน %d รายการ" % n_formula)
    for w in warnings:
        print("  WARN: %s" % w)
    if problems:
        print("\nFAIL — พบ %d ปัญหา:" % len(problems))
        for i, p in enumerate(problems, 1):
            print("  %d. %s" % (i, p))
        return 1
    if warnings and args.strict:
        print("\nFAIL — โหมด strict: มีคำเตือน %d รายการ" % len(warnings))
        return 1
    print("OK — สัญลักษณ์คณิต/วิทย์ผ่านทุก check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
