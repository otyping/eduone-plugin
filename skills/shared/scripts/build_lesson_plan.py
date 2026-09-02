# -*- coding: utf-8 -*-
"""
build_lesson_plan.py — สร้างแผนการจัดการเรียนรู้ (.docx) ของ EDU ONE
L1 = การเรียนรู้เชิงสำรวจ (Inquiry-Based) / L2 = การเรียนรู้ผ่านกิจกรรม (Activity-Based)

ใช้งาน:
    python build_lesson_plan.py <plan.json> <output.docx>

โครงสร้าง plan.json:
{
  "header": "ระดับชั้น... > วิชา... > หน่วย... > เรื่อง...",
  "cover": {
    "title": "แผนการจัดการเรียนรู้",
    "grade_line": "ระดับชั้นประถมศึกษาปีที่ 1",
    "rows": [ ...verbatim จาก TABLE หน้าปกของ Content C1... ]
  },
  "plan_title": "แบบที่ 1 — การเรียนรู้เชิงสำรวจ (Inquiry-Based Learning)",
  "plan": {
    "rows": [
      ["1. ชื่อแผนการจัดการเรียนรู้", "..."],
      ["2. วัตถุประสงค์การเรียนรู้", ["**ด้านความรู้ (K):** ...", "**ด้านทักษะ (P):** ...", "**ด้านคุณลักษณะ (A):** ..."]],
      ["3. ทักษะ 8C", ["**C1 Critical Thinking and Problem Solving:** ...", "... ครบ C1-C8"]],
      ["4. กิจกรรมการเรียนรู้", ["**ขั้นนำ (ทฤษฎี - X นาที):** ...", "**ขั้นสอน (กิจกรรม - X นาที):** ...",
                                 "**ขั้นสรุป (X นาที):** ...", "**ขั้นวัดผลการเรียนรู้ (แบบฝึกหัด - X นาที):** ..."]],
      ["5. วัสดุและอุปกรณ์", ["..."]],
      ["6. การวัดและประเมินผล", ["**วิธีวัด:** ...", "**เครื่องมือ:** ...", "**เกณฑ์ผ่าน:** ..."]],
      ["7. เกณฑ์การประเมิน (Rubric)", {"template": "4c_standard", "topic": "...", "skill": "..."}],
      ["8. การนำไปใช้ในชีวิตประจำวัน", ["..."]]
    ]
  }
}

เซลล์รับ str / list[str] / dict template (4c_standard -> rubric 4 มิติ)
"""
import json
import sys

import docx_common as dc
from docx_common import Pt

# --- Rubric template (4C × 4 ระดับ) ---
RUBRIC_4C_STANDARD = [
    {"name": "Critical Thinking (การคิดวิเคราะห์)", "levels": [
        "ระดับ 4 (ดีเยี่ยม) — วิเคราะห์{topic}อย่างเป็นระบบ ระบุความสัมพันธ์ครบ และสรุปโดยอ้างอิงหลักฐาน",
        "ระดับ 3 (ดี) — วิเคราะห์{topic}ได้ถูกต้อง อธิบายเหตุผลของผลลัพธ์ได้",
        "ระดับ 2 (พอใช้) — วิเคราะห์{topic}ได้บางส่วน เข้าใจหลักการแต่ยังต้องการคำแนะนำ",
        "ระดับ 1 (ควรปรับปรุง) — ยังต้องการความช่วยเหลือในการวิเคราะห์{topic}",
    ]},
    {"name": "Creativity (ความคิดสร้างสรรค์)", "levels": [
        "ระดับ 4 (ดีเยี่ยม) — เสนอวิธี{skill}แปลกใหม่ ใช้ได้จริง อธิบายข้อดี/ข้อจำกัดได้",
        "ระดับ 3 (ดี) — เสนอวิธี{skill}ที่ปรับจากแบบเดิม สมเหตุสมผล",
        "ระดับ 2 (พอใช้) — ทำตามแบบที่กำหนด ปรับเปลี่ยนเล็กน้อยตามคำแนะนำ",
        "ระดับ 1 (ควรปรับปรุง) — ทำตามแบบที่กำหนดเท่านั้น ยังไม่กล้าปรับ",
    ]},
    {"name": "Communication (การสื่อสาร)", "levels": [
        "ระดับ 4 (ดีเยี่ยม) — นำเสนอ{topic}ชัดเจน ใช้คำศัพท์ถูกต้อง ตอบคำถามเชิงลึกได้",
        "ระดับ 3 (ดี) — นำเสนอ{topic}เข้าใจง่าย ใช้คำศัพท์ถูกต้องเป็นส่วนใหญ่",
        "ระดับ 2 (พอใช้) — นำเสนอ{topic}ได้แต่ยังขาดความชัดเจนบางจุด",
        "ระดับ 1 (ควรปรับปรุง) — นำเสนอ{topic}ไม่ชัดเจน",
    ]},
    {"name": "Collaboration (การทำงานร่วมกัน)", "levels": [
        "ระดับ 4 (ดีเยี่ยม) — แบ่งหน้าที่ชัด ช่วยเพื่อนแก้ปัญหา รับผิดชอบงานของตนเต็มที่",
        "ระดับ 3 (ดี) — ทำงานร่วมได้ดี รับฟังความเห็นเพื่อน แลกเปลี่ยนข้อมูลอย่างเปิดเผย",
        "ระดับ 2 (พอใช้) — ทำงานร่วมได้ แต่ยังไม่กระตือรือร้น",
        "ระดับ 1 (ควรปรับปรุง) — ทำงานคนเดียวเป็นหลัก หรือไม่ร่วมกลุ่ม",
    ]},
]
_RUBRIC_TEMPLATES = {"4c_standard": RUBRIC_4C_STANDARD}


def expand_rubric_template(spec):
    tmpl = _RUBRIC_TEMPLATES.get(spec.get("template", "4c_standard"))
    if tmpl is None:
        raise ValueError(f"unknown rubric template: {spec.get('template')!r}")
    topic = spec.get("topic", "")
    skill = spec.get("skill", "")
    out = []
    for i, dim in enumerate(tmpl, 1):
        out.append(f"**มิติที่ {i} — {dim['name']}**")
        for level in dim["levels"]:
            out.append(level.replace("{topic}", topic).replace("{skill}", skill))
    return out


def _expand_cell(value):
    if isinstance(value, dict) and "template" in value:
        return expand_rubric_template(value)
    return value


def build(data, out_path):
    doc = dc.new_document(data["header"])

    cover = data["cover"]
    dc.add_heading(doc, cover.get("title", "แผนการจัดการเรียนรู้"),
                   size=dc.COVER_TITLE_SIZE, space_after=4)
    if cover.get("grade_line"):
        dc.add_heading(doc, cover["grade_line"], size=dc.COVER_TITLE_SIZE,
                       space_before=0, space_after=10)
    dc.add_two_col_table(doc, cover["rows"])

    doc.add_page_break()

    dc.add_heading(doc, data["plan_title"], size=Pt(15))
    rows = [[label, _expand_cell(val)] for label, val in data["plan"]["rows"]]
    dc.add_two_col_table(doc, rows)

    dc.save(doc, out_path)


def main():
    if len(sys.argv) != 3:
        print("usage: python build_lesson_plan.py <plan.json> <output.docx>", file=sys.stderr)
        sys.exit(2)
    with open(sys.argv[1], "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    build(data, sys.argv[2])
    print("OK ->", sys.argv[2])


if __name__ == "__main__":
    main()
