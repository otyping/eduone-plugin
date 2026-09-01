# -*- coding: utf-8 -*-
"""
build_content.py — สร้างเอกสารประกอบเนื้อหา (.docx) ของ EDU ONE
รองรับทั้งแบบเชิงวิชาการ (C1) และเล่าเรื่อง (C2) จาก JSON เดียวกัน

ใช้งาน:
    python build_content.py <content.json> <output.docx>

โครงสร้าง content.json:
{
  "header": "ระดับชั้น... > วิชา... > หน่วย... > เรื่อง...",
  "cover": {
    "title": "เอกสารประกอบเนื้อหา",
    "grade_line": "ระดับชั้นประถมศึกษาปีที่ 1",
    "rows": [
      ["รหัสวิชา", "ว11101"],
      ["วิชา", "วิทยาศาสตร์และเทคโนโลยี"],
      ["หน่วย", "..."],
      ["เรื่อง", "..."],
      ["จุดประสงค์ประจำหน่วยการเรียน", ["1. ...", "2. ..."]],
      ["ผลลัพธ์การเรียนรู้ระดับหน่วยการเรียน", ["1. ...", "2. ..."]]
    ]
  },
  "mode_label": "แบบที่ 1 - เชิงวิชาการ",
  "title": "เรื่อง...",
  "body": [
    {"type": "h", "text": "1. ..."},
    {"type": "p", "text": "..."},
    {"type": "table", "header": ["คอลัมน์1", "คอลัมน์2"], "rows": [["...", "..."]]},
    {"type": "p", "text": "..."}
  ]
}

หน้า 1 = หน้าปก (title 18pt + บรรทัดระดับชั้น 18pt + ตาราง 6 แถว)
หน้า 2+ = mode_label + title (18pt กึ่งกลาง) แล้ว body blocks (14pt)
ความยาวเนื้อหา (ไม่นับหน้าปก) ควร 3-5 หน้า A4 — ตรวจด้วย verify_docx.py
"""
import json
import sys

import docx_common as dc
from docx_common import Pt


def build(data, out_path):
    doc = dc.new_document(data["header"])

    # ===== หน้า 1 : หน้าปก =====
    cover = data["cover"]
    dc.add_heading(doc, cover.get("title", "เอกสารประกอบเนื้อหา"),
                   size=dc.COVER_TITLE_SIZE, space_after=4)
    if cover.get("grade_line"):
        dc.add_heading(doc, cover["grade_line"], size=dc.COVER_TITLE_SIZE,
                       space_before=0, space_after=10)
    dc.add_two_col_table(doc, cover["rows"])

    doc.add_page_break()

    # ===== หน้า 2+ : เนื้อหา =====
    if data.get("mode_label"):
        dc.add_heading(doc, data["mode_label"], size=dc.COVER_TITLE_SIZE, space_after=4)
    if data.get("title"):
        dc.add_heading(doc, data["title"], size=dc.COVER_TITLE_SIZE, space_before=0)

    for block in data.get("body", []):
        bt = block.get("type")
        if bt == "h":
            dc.add_paragraph(doc, block["text"], size=dc.BODY_SIZE, bold=True,
                             align="thaiDistribute", space_before=6, space_after=2)
        elif bt == "p":
            dc.add_paragraph(doc, block["text"], size=dc.BODY_SIZE,
                             align="thaiDistribute", space_after=4)
        elif bt == "table":
            dc.add_content_table(doc, block["header"], block["rows"])
            dc.add_paragraph(doc, "", space_after=4)
        elif bt == "eq":
            dc.add_paragraph(doc, f"${block['text']}$", align="center", space_after=4)
        elif bt == "ep":
            dc.add_paragraph(doc, "", space_after=2)
        else:
            raise ValueError(f"unknown body block type: {bt!r}")

    dc.save(doc, out_path)


def main():
    if len(sys.argv) != 3:
        print("usage: python build_content.py <content.json> <output.docx>", file=sys.stderr)
        sys.exit(2)
    with open(sys.argv[1], "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    build(data, sys.argv[2])
    print("OK ->", sys.argv[2])


if __name__ == "__main__":
    main()
