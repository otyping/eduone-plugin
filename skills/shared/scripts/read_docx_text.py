# -*- coding: utf-8 -*-
"""
read_docx_text.py — ดึงข้อความจาก .docx ออกมาเป็น text (EDU ONE)

⚠️ **นี่คือทางสำรอง ไม่ใช่ทางหลัก** — ถ้ามีไฟล์ `.json` คู่กัน (`content_c1_json`,
`content_c2_json`, `plan_l1_json`, `plan_l2_json` จาก `paths.py`) **ให้ `Read` ไฟล์ JSON แทน**
เพราะ JSON เป็น source of truth และ **เก็บสมการไว้ครบเป็น `$...$` LaTeX**
ส่วน .docx เก็บสมการเป็น Word Equation (OMML) ซึ่งแปลงกลับมาได้ไม่ครบรูป
ใช้ไฟล์นี้เมื่อ: หัวข้อเก่าที่มีแต่ .docx · ต้องตรวจว่าสิ่งที่ครูเห็นจริง ๆ ตรงกับ spec ไหม

ทำไมต้องมี: sub-agent (writer/checkwork) ต้องอ่านต้นทางเอง แทนที่จะให้ orchestrator
อ่านแล้วแปะเข้า prompt — เนื้อหาหนักจะได้อยู่ใน context ของลูกที่ทิ้งได้ ไม่ค้างในแม่ตลอด pipeline
(ดูกฎทองของ orchestrator ใน CLAUDE.md)

ก่อนหน้านี้แต่ละ SKILL.md เขียน snippet python-docx ของตัวเอง — ต่างกันนิดหน่อยทุกที่
และ **ทุกอันทำสมการหายเงียบ ๆ** เพราะ `paragraph.text` ของ python-docx อ่านแต่ `w:t`
ไม่แตะ `m:oMath` ไฟล์นี้รวบให้เป็นจุดเดียวและอุดรูนั้น

สิ่งที่จัดการให้:
  · เดินตามลำดับจริงในเอกสาร (ย่อหน้าสลับตารางไม่สลับที่)
  · **ดึงสมการ OMML ออกมาด้วย** ครอบ `$…$` ให้รู้ว่าตรงนั้นเป็นสมการ (ได้ข้อความเชิงเส้น
    เช่น `$3×8=24$` — เศษส่วน/รากจะแบนลง ตรงนี้แหละที่ JSON ดีกว่า)
  · ตารางออกมาเป็น markdown pipe table (หน้าปก 7 แถวจึงยังอ่านรู้เรื่อง)
  · ลบ ZWSP ที่ใส่ไว้ตัดคำไทย (U+200B) ออก ไม่งั้นคำจะดูขาดเป็นท่อน ๆ
  · ตัดย่อหน้าว่างซ้ำซ้อน

ใช้:
  read_docx_text.py <file.docx>              # พิมพ์ออก stdout
  read_docx_text.py <file.docx> --no-tables  # ข้ามตาราง (เอาแต่ย่อหน้า)
  read_docx_text.py <file.docx> -o <out.txt> # เขียนลงไฟล์

exit 0 = อ่านได้ · exit 2 = ไม่พบไฟล์/อ่านไม่ได้

รันผ่านตัวห่อ: eduone-py <ชื่อไฟล์นี้> <args>  (หา Python 3.12 ให้เองทุก OS)
ตั้ง PYTHONIOENCODING=utf-8 ก่อนรัน
"""
from __future__ import annotations

import argparse
import io
import os
import sys

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

ZWSP = "​"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def _clean(text):
    return text.replace(ZWSP, "").strip()


def _para_text(paragraph):
    """ข้อความของย่อหน้า **รวมสมการ OMML** — `paragraph.text` ของ python-docx ทำสมการหาย

    เดิน descendant ตามลำดับเอกสาร เก็บ w:t (ข้อความธรรมดา) และ m:t (ข้อความในสมการ)
    ช่วงที่ติดกันเป็นสมการจะถูกครอบ `$…$` เพื่อให้ผู้อ่านรู้ว่าเดิมเป็น Equation
    """
    parts = []          # [(is_math, text), ...]
    for node in paragraph._p.iter():
        tag = node.tag
        if tag == f"{{{W_NS}}}t":
            parts.append((False, node.text or ""))
        elif tag == f"{{{M_NS}}}t":
            parts.append((True, node.text or ""))

    out = []
    buf = []
    buf_is_math = False
    for is_math, text in parts:
        if is_math != buf_is_math:
            if buf:
                chunk = "".join(buf)
                out.append(f"${chunk}$" if buf_is_math and chunk.strip() else chunk)
            buf, buf_is_math = [], is_math
        buf.append(text)
    if buf:
        chunk = "".join(buf)
        out.append(f"${chunk}$" if buf_is_math and chunk.strip() else chunk)
    return "".join(out)


def _iter_block_items(doc):
    """เดิน body ตามลำดับจริง คืน Paragraph หรือ Table สลับกันได้"""
    body = doc.element.body
    for child in body.iterchildren():
        tag = child.tag.split("}")[-1]
        if tag == "p":
            yield Paragraph(child, doc)
        elif tag == "tbl":
            yield Table(child, doc)


def _table_to_md(table):
    rows = []
    for row in table.rows:
        cells = [
            _clean(" ".join(_para_text(p) for p in c.paragraphs)).replace("\n", " ") or "—"
            for c in row.cells
        ]
        rows.append("| " + " | ".join(cells) + " |")
    if not rows:
        return ""
    # แถวแรกเป็นหัวตาราง (หน้าปก/ตารางเนื้อหาของโปรเจกต์นี้เป็นแบบนั้นทั้งหมด)
    width = len(table.rows[0].cells)
    sep = "|" + "---|" * width
    return "\n".join([rows[0], sep] + rows[1:])


def extract(path, include_tables=True):
    doc = Document(path)
    out = []
    for block in _iter_block_items(doc):
        if isinstance(block, Paragraph):
            text = _clean(_para_text(block))
            if text:
                out.append(text)
            elif out and out[-1] != "":
                out.append("")
        elif include_tables:
            md = _table_to_md(block)
            if md:
                out.append("")
                out.append(md)
                out.append("")
    # ยุบบรรทัดว่างติดกัน
    lines = []
    for line in out:
        if line == "" and (not lines or lines[-1] == ""):
            continue
        lines.append(line)
    return "\n".join(lines).strip() + "\n"


def main():
    ap = argparse.ArgumentParser(description="ดึงข้อความจาก .docx")
    ap.add_argument("docx", help="ไฟล์ .docx")
    ap.add_argument("--no-tables", action="store_true", help="ข้ามตาราง")
    ap.add_argument("-o", "--out", help="เขียนลงไฟล์ (ไม่ระบุ = stdout)")
    args = ap.parse_args()

    if not os.path.isfile(args.docx):
        print(f"ไม่พบไฟล์: {args.docx}", file=sys.stderr)
        return 2
    try:
        text = extract(args.docx, include_tables=not args.no_tables)
    except Exception as exc:  # noqa: BLE001 — คืน exit 2 ให้ caller ตัดสินใจ
        print(f"อ่านไฟล์ไม่ได้: {exc}", file=sys.stderr)
        return 2

    if args.out:
        with io.open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print(f"เขียนแล้ว: {args.out} ({len(text)} ตัวอักษร)")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
