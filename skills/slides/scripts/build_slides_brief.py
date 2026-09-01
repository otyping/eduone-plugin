# -*- coding: utf-8 -*-
"""
build_slides_brief.py — ใบสั่งผลิตรูปประกอบสไลด์ จาก {BASE}_slides_<SRC>.json

ผลลัพธ์: {BASE}_slides_<SRC>_media-brief.md
  กฎรวมของภาพ + บล็อก prompt ภาษาอังกฤษต่อไฟล์ (คัดลอกไปวาง Google Nano Banana ได้เลย)
  + คำบรรยายไทยไว้ตรวจว่าภาพตรงเนื้อหา + ตารางสรุปชื่อไฟล์ทั้งหมด

พอผลิตรูปเสร็จ วางไฟล์ลง {BASE}_slides_<SRC>_media/ แล้วรัน fill_slides_images.py
(หรือส่งรายการ URL มาก็ได้) จะเติม image_file ให้เอง ไม่ต้องแก้ json ด้วยมือ

ใช้:
  build_slides_brief.py <slides.json> [--out OUT.md]

รันผ่านตัวห่อ: eduone-py <ชื่อไฟล์นี้> <args>  (หา Python 3.12 ให้เองทุก OS)
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "shared", "scripts"))
import slides_media as sm  # noqa: E402  (แบบแผนชื่อไฟล์ + clean_prompt อยู่ที่ shared)

RULES = """## กฎรวมของทุกภาพ

- **ห้ามมีตัวหนังสือในภาพ** — ตัวอักษรที่ AI สร้างมักอ่านไม่ออก และสไลด์มีข้อความอธิบายอยู่แล้ว
  (ถ้า prompt ระบุป้ายกำกับไว้ ให้ตัดคำสั่งส่วนป้ายออก หรือใช้สัญลักษณ์/สีแทนคำ)
- ห้ามมีโลโก้แบรนด์ ลายน้ำ หรือใบหน้าที่ระบุตัวตนบุคคลจริงได้
- **สไตล์เดียวกันทั้งชุด** — isometric vector technical illustration, clean linework,
  engineering infographic style (ตาม Master Prompt) ให้ทุกหน้าในไฟล์เดียวกันดูเป็นชุดเดียว
- **ภาพต้องไม่ผิดเพี้ยนจากความเป็นจริง** — สัดส่วน โครงสร้าง และสีของสิ่งที่สอนต้องถูกต้อง
- **สัดส่วนเกือบจัตุรัส (~1:1)** เพราะกรอบภาพในสไลด์กว้าง 3.94 นิ้ว สูง 3.55 นิ้ว
  ด้านสั้นอย่างน้อย 1200 px · พื้นหลังสีขาวหรือโปร่งใส (สไลด์พื้นขาว)
- ส่งกลับเป็น `.png` หรือ `.jpg` ก็ได้ แต่ **ชื่อไฟล์ต้องตรงตามที่กำหนดเป๊ะ ๆ**

> **ผลิตที่ Google Nano Banana** ด้วย prompt ภาษาอังกฤษในบล็อก `Prompt` ของแต่ละไฟล์
> โมเดลสร้างภาพเข้าใจอังกฤษแม่นกว่าไทยมาก โดยเฉพาะคำกำกับมุมกล้อง สไตล์ และข้อห้าม
>
> prompt ในใบสั่งนี้ **คัดลอกไปวางได้เลย** — ตัดประโยคสั่งใส่ป้ายภาษาไทยออกให้แล้ว
> และต่อท้ายด้วยข้อห้ามมาตรฐาน (ไม่มีตัวหนังสือ · พื้นหลังขาว · สัดส่วน 1:1)
"""

HOWTO = """## ผลิตเสร็จแล้วทำอย่างไรต่อ

1. วางไฟล์รูปทั้งหมดลงโฟลเดอร์ `{media}/` (ชื่อไฟล์ตามตารางด้านล่าง)
2. รันตัวเติมอัตโนมัติ — ไม่ต้องแก้ json เอง

```bash
export PYTHONIOENCODING=utf-8
eduone-py fill_slides_images.py "{spec}"
eduone-py build_slides.py "{spec}" "{pptx}"
```

ถ้าอัปโหลดขึ้น CDN แล้ว ให้เก็บ URL เป็นไฟล์ข้อความบรรทัดละ 1 URL แล้วส่งเป็นอาร์กิวเมนต์ที่สองแทน
`fill_slides_images.py "{spec}" urls.txt` (ตัว build จะโหลดรูปมาแคชในเครื่องให้เอง)
"""


def build(spec_path: str, out_path: str | None = None) -> int:
    spec = sm.load_spec(spec_path)
    stem = sm.stem_of(spec_path)
    out_path = out_path or sm.brief_path_of(spec_path)
    slots = sm.image_slots(spec)

    if not slots:
        print("ไม่มีหน้าไหนต้องใช้รูป (ไม่มี image_prompt) — ไม่ได้เขียนใบสั่งผลิต")
        return 0

    header = spec.get("header", "")
    todo = [(n, s) for n, s in slots if not s.get("image_file")]

    lines = []
    lines.append("# ใบสั่งผลิตรูปประกอบสไลด์ — %s" % stem)
    lines.append("")
    if header:
        lines.append("> %s" % header)
        lines.append("")
    lines.append("รูปทั้งหมด **%d ไฟล์** (ยังไม่มี %d · มีแล้ว %d)"
                 % (len(slots), len(todo), len(slots) - len(todo)))
    lines.append("")
    lines.append(RULES)
    lines.append(HOWTO.format(media=os.path.basename(sm.media_dir_of(spec_path)),
                              spec=spec_path, pptx=spec_path[:-5] + ".pptx"))
    lines.append("---")
    lines.append("")

    for no, s in slots:
        name = sm.asset_name(stem, no)
        done = " — ✅ มีแล้ว (`%s`)" % s["image_file"] if s.get("image_file") else ""
        lines.append("### `%s`%s" % (name, done))
        lines.append("")
        lines.append("หน้า %d · %s" % (no, s.get("title", "")))
        lines.append("")
        lines.append("**Prompt**")
        lines.append("")
        prompt, stripped = sm.clean_prompt(s.get("image_prompt"))
        lines.append("```text")
        lines.append(prompt)
        lines.append("```")
        lines.append("")
        if stripped:
            lines.append("> ตัดประโยคสั่งใส่ป้ายภาษาไทยออกจาก prompt เดิมแล้ว "
                         "(ป้ายกำกับให้ใส่เป็นกล่องข้อความในสไลด์แทน ถ้าจำเป็น)")
            lines.append("")
        bullets = s.get("bullets") or []
        if bullets:
            lines.append("<details><summary>เนื้อหาหน้านี้ (ไว้ตรวจว่าภาพตรงเรื่อง)</summary>")
            lines.append("")
            for b in bullets:
                lines.append("- %s" % b)
            lines.append("")
            lines.append("</details>")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## ตารางสรุปชื่อไฟล์")
    lines.append("")
    lines.append("| ไฟล์ที่ต้องส่งกลับ | หน้า | หัวข้อ | สถานะ |")
    lines.append("|---|---|---|---|")
    for no, s in slots:
        lines.append("| `%s` | %d | %s | %s |"
                     % (sm.asset_name(stem, no), no, s.get("title", ""),
                        "มีแล้ว" if s.get("image_file") else "ยังไม่มี"))
    lines.append("")

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    # เตรียมโฟลเดอร์ปลายทางไว้เลย ผู้ใช้จะได้ลากไฟล์รูปมาวางได้ทันที
    os.makedirs(sm.media_dir_of(spec_path), exist_ok=True)

    print("เขียนใบสั่งผลิต: %s" % out_path)
    print("  วางไฟล์รูปที่: %s" % sm.media_dir_of(spec_path))
    print("  รูปทั้งหมด %d ไฟล์ — ยังไม่มี %d ไฟล์:" % (len(slots), len(todo)))
    for no, s in todo:
        print("    %s  (หน้า %d · %s)" % (sm.asset_name(stem, no), no, s.get("title", "")))
    return 0


def main():
    ap = argparse.ArgumentParser(description="ใบสั่งผลิตรูปประกอบสไลด์")
    ap.add_argument("spec", help="{BASE}_slides_<SRC>.json")
    ap.add_argument("--out", help="ที่เก็บใบสั่งผลิต (ค่าเริ่มต้น: วางข้าง ๆ json)")
    a = ap.parse_args()
    if not os.path.exists(a.spec):
        print("ไม่พบไฟล์: %s" % a.spec, file=sys.stderr)
        return 2
    return build(a.spec, a.out)


if __name__ == "__main__":
    raise SystemExit(main())
