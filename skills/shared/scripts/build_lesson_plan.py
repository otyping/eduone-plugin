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
      ["7. เกณฑ์การประเมิน (Rubric)", {"template": "8c_standard", "codes": ["C1", "C4"],
                                       "topic": "...", "skill": "..."}],
      ["8. การนำไปใช้ในชีวิตประจำวัน", ["..."]]
    ]
  }
}

เซลล์รับ str / list[str] / dict template (8c_standard + codes -> rubric 2 มิติ × 4 ระดับ)
มิติของ Rubric ต้องเป็นทักษะ 8C สองข้อที่หลักสูตรระบุว่าคาบนั้นเน้น
"""
import json
import sys

import docx_common as dc
from docx_common import Pt

# --- Rubric template (ทักษะ 8C × 4 ระดับ) ---
# ★ มิติของ Rubric ต้องเป็นมิติของ 8C และใช้ **เฉพาะสองข้อที่หลักสูตรระบุว่าคาบนี้เน้น**
#   (บรรทัด `SKILLS8C|` ของคาบนั้น) — ครบ 8 ข้อจะได้ตาราง 32 ช่องซึ่งคาบเดียววัดจริงไม่ได้
#   ส่วนคำอธิบายครบทั้ง 8 ข้ออยู่ในหัวข้อ 3 ของแผนอยู่แล้ว
#   ชื่ออังกฤษต้องตรงกับ skills-8c.txt ตัวต่อตัว ห้ามย่อ ห้ามแปลใหม่
RUBRIC_8C = {
    "C1": {"name": "C1 Critical Thinking and Problem Solving (คิดอย่างมีวิจารณญาณและแก้ปัญหา)",
           "levels": [
               "ระดับ 4 (ดีเยี่ยม) — วิเคราะห์{topic}อย่างเป็นระบบ ระบุความสัมพันธ์ครบ และสรุปโดยอ้างอิงหลักฐาน",
               "ระดับ 3 (ดี) — วิเคราะห์{topic}ได้ถูกต้อง อธิบายเหตุผลของผลลัพธ์ได้",
               "ระดับ 2 (พอใช้) — วิเคราะห์{topic}ได้บางส่วน เข้าใจหลักการแต่ยังต้องการคำแนะนำ",
               "ระดับ 1 (ควรปรับปรุง) — ยังต้องการความช่วยเหลือในการวิเคราะห์{topic}",
           ]},
    "C2": {"name": "C2 Creativity and Innovation (คิดสร้างสรรค์และนวัตกรรม)",
           "levels": [
               "ระดับ 4 (ดีเยี่ยม) — เสนอวิธี{skill}แปลกใหม่ ใช้ได้จริง อธิบายข้อดีและข้อจำกัดได้",
               "ระดับ 3 (ดี) — เสนอวิธี{skill}ที่ปรับจากแบบเดิมอย่างสมเหตุสมผล",
               "ระดับ 2 (พอใช้) — ทำตามแบบที่กำหนด ปรับเปลี่ยนเล็กน้อยตามคำแนะนำ",
               "ระดับ 1 (ควรปรับปรุง) — ทำตามแบบที่กำหนดเท่านั้น ยังไม่กล้าปรับ",
           ]},
    "C3": {"name": "C3 Cross-cultural Understanding (เข้าใจความต่างวัฒนธรรม ต่างกระบวนทัศน์)",
           "levels": [
               "ระดับ 4 (ดีเยี่ยม) — ยกตัวอย่างมุมมองที่ต่างออกไปเรื่อง{topic} และอธิบายที่มาของความต่างได้",
               "ระดับ 3 (ดี) — รับฟังมุมมองที่ต่างและเปรียบเทียบกับของตนเองได้",
               "ระดับ 2 (พอใช้) — รับฟังมุมมองที่ต่าง แต่ยังเชื่อมโยงกับเนื้อหาไม่ชัด",
               "ระดับ 1 (ควรปรับปรุง) — ยึดมุมมองของตนเองเป็นหลัก",
           ]},
    "C4": {"name": "C4 Collaboration, Teamwork and Leadership (ร่วมมือ ทำงานเป็นทีม และภาวะผู้นำ)",
           "levels": [
               "ระดับ 4 (ดีเยี่ยม) — แบ่งหน้าที่ชัด ช่วยเพื่อนแก้ปัญหา รับผิดชอบงานของตนเต็มที่",
               "ระดับ 3 (ดี) — ทำงานร่วมได้ดี รับฟังความเห็นเพื่อน แลกเปลี่ยนข้อมูลอย่างเปิดเผย",
               "ระดับ 2 (พอใช้) — ทำงานร่วมได้ แต่ยังไม่กระตือรือร้น",
               "ระดับ 1 (ควรปรับปรุง) — ทำงานคนเดียวเป็นหลัก หรือไม่ร่วมกลุ่ม",
           ]},
    "C5": {"name": "C5 Communications, Information and Media Literacy (สื่อสาร สารสนเทศ และรู้เท่าทันสื่อ)",
           "levels": [
               "ระดับ 4 (ดีเยี่ยม) — นำเสนอ{topic}ชัดเจน ใช้คำศัพท์ถูกต้อง ตอบคำถามเชิงลึกได้",
               "ระดับ 3 (ดี) — นำเสนอ{topic}เข้าใจง่าย ใช้คำศัพท์ถูกต้องเป็นส่วนใหญ่",
               "ระดับ 2 (พอใช้) — นำเสนอ{topic}ได้แต่ยังขาดความชัดเจนบางจุด",
               "ระดับ 1 (ควรปรับปรุง) — นำเสนอ{topic}ไม่ชัดเจน",
           ]},
    "C6": {"name": "C6 Computing and ICT Literacy (คอมพิวเตอร์ เทคโนโลยีสารสนเทศและการสื่อสาร)",
           "levels": [
               "ระดับ 4 (ดีเยี่ยม) — เลือกใช้เครื่องมือหรือสื่อดิจิทัลช่วย{skill}ได้เหมาะสม และตรวจสอบผลลัพธ์เป็น",
               "ระดับ 3 (ดี) — ใช้เครื่องมือที่ครูแนะนำช่วย{skill}ได้ถูกต้อง",
               "ระดับ 2 (พอใช้) — ใช้เครื่องมือได้เมื่อมีคนช่วยกำกับ",
               "ระดับ 1 (ควรปรับปรุง) — ยังใช้เครื่องมือช่วยงานไม่ได้",
           ]},
    "C7": {"name": "C7 Career and Learning Skills (ทักษะอาชีพและการเรียนรู้)",
           "levels": [
               "ระดับ 4 (ดีเยี่ยม) — เชื่อมโยง{topic}กับการใช้งานจริงนอกห้องเรียน และวางแผนเรียนรู้ต่อเองได้",
               "ระดับ 3 (ดี) — ยกตัวอย่างการใช้{topic}ในชีวิตจริงได้ถูกต้อง",
               "ระดับ 2 (พอใช้) — ยกตัวอย่างได้เมื่อมีคนช่วยชี้แนะ",
               "ระดับ 1 (ควรปรับปรุง) — ยังเชื่อมโยงกับชีวิตจริงไม่ได้",
           ]},
    "C8": {"name": "C8 Compassion (เมตตา กรุณา มีวินัย คุณธรรม จริยธรรม)",
           "levels": [
               "ระดับ 4 (ดีเยี่ยม) — ช่วยเพื่อนที่ยังไม่เข้าใจด้วยความเต็มใจ ใช้อุปกรณ์ร่วมกันอย่างมีวินัย",
               "ระดับ 3 (ดี) — ช่วยเพื่อนเมื่อได้รับการร้องขอ และรักษาข้อตกลงของกลุ่ม",
               "ระดับ 2 (พอใช้) — ทำงานของตนเรียบร้อย แต่ยังไม่ค่อยช่วยเพื่อน",
               "ระดับ 1 (ควรปรับปรุง) — ยังไม่รักษาข้อตกลงของกลุ่ม",
           ]},
}
#: จำนวนมิติต่อแผน — เจ้าของโปรเจกต์กำหนดให้ใช้เฉพาะตัวที่คาบนั้นเน้น
RUBRIC_DIMS = 2


def expand_rubric_template(spec):
    """คืนรายการบรรทัดของ Rubric จากรหัส 8C ที่หลักสูตรระบุว่าคาบนี้เน้น

    spec = {"template": "8c_standard", "topic": ..., "skill": ..., "codes": ["C1","C4"]}
    `codes` มาจาก `skills_8c` ของ no_to_token (บรรทัด SKILLS8C| ในไฟล์หลักสูตร)
    """
    name = spec.get("template", "8c_standard")
    if name != "8c_standard":
        raise ValueError(
            "unknown rubric template: %r — Rubric ต้องวัดจากมิติของ 8C "
            "ใช้ {'template':'8c_standard','codes':['C1','C4'],'topic':...,'skill':...}"
            % name)
    codes = [str(c).strip().upper() for c in (spec.get("codes") or [])]
    unknown = [c for c in codes if c not in RUBRIC_8C]
    if unknown:
        raise ValueError("รหัสทักษะ 8C ไม่รู้จัก: %s (ต้องเป็น C1-C8)" % ", ".join(unknown))
    if len(codes) != RUBRIC_DIMS:
        raise ValueError(
            "Rubric ต้องมี %d มิติ = ทักษะ 8C ที่หลักสูตรระบุว่าคาบนี้เน้น — ได้ %d (%s)"
            % (RUBRIC_DIMS, len(codes), ", ".join(codes) or "ไม่ระบุ"))
    topic = spec.get("topic", "")
    skill = spec.get("skill", "")
    out = []
    for i, code in enumerate(codes, 1):
        dim = RUBRIC_8C[code]
        out.append("**มิติที่ %d — %s**" % (i, dim["name"]))
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
