# -*- coding: utf-8 -*-
"""
srcpack.py — สร้าง "source pack" ให้ agent ปลายน้ำอ่านแทน C1 เต็ม (EDU ONE)

ทำไมต้องมี: C1 หนึ่งไฟล์ยาว 3-5 หน้า (~12k token) แต่มี agent ปลายน้ำหลายตัวที่ต้องรู้แค่
**แกนของเรื่อง** ไม่ต้องรู้ทุกย่อหน้า (เพลง · วิดีโอ · แผนการสอน) การให้ทุกตัวอ่าน C1 เต็ม
คือจ่ายค่า input ซ้ำหลายรอบเพื่อข้อมูลชุดเดิม — ไฟล์นี้ย่อ C1 เหลือ ~2.5k token
โดยดึงจาก `digest` ที่ content-academic เขียนไว้ตอนเขียน C1 (ไม่ต้องเรียกโมเดลใหม่)

ผลพลอยได้ที่สำคัญกว่าการประหยัด: **ทุกสื่อยึดศัพท์/ตัวเลข/ตัวอย่างชุดเดียวกัน**
เพราะอ่านจากไฟล์เดียวกัน ไม่ใช่ต่างคนต่างสรุป C1 เอง

ใช้:
  srcpack.py <C1.json> [<out.md>]        # ไม่ระบุ out → เขียนข้าง ๆ เป็น {BASE}_srcpack.md
  srcpack.py <C1.json> -                 # พิมพ์ออก stdout เฉย ๆ ไม่เขียนไฟล์

exit 0 = สร้างได้ (ถึงจะไม่มี digest ก็ยังสร้างจากหน้าปก+โครงหัวข้อให้)
exit 2 = อ่านไฟล์ไม่ได้

ใช้ Python 3.12: %LOCALAPPDATA%\\Programs\\Python\\Python312\\python.exe
"""
from __future__ import annotations

import io
import json
import os
import sys


def load(path):
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def _rows(cover, label):
    """ดึงค่าของแถวหน้าปกตามชื่อแถว — คืน list ของบรรทัดเสมอ"""
    for row in cover.get("rows") or []:
        if row and row[0] == label:
            val = row[1] if len(row) > 1 else ""
            if isinstance(val, list):
                return [str(x) for x in val]
            return [str(val)]
    return []


def _bullets(items):
    return "\n".join("- %s" % str(x).strip() for x in items if str(x).strip())


def render(data, src_name):
    cover = data.get("cover") or {}
    dg = data.get("digest") or {}
    out = []
    add = out.append

    add("# SOURCE PACK — %s" % (data.get("title") or "").strip())
    add("")
    add("> สรุปแกนของ C1 สำหรับ agent ปลายน้ำ **สร้างอัตโนมัติจาก `%s` — ห้ามแก้ด้วยมือ**"
        % src_name)
    add("> ต้องการรายละเอียดมากกว่านี้ให้เปิด C1 ฉบับเต็มได้ แต่ปกติไฟล์นี้พอ")
    add("")
    add("**header:** %s" % (data.get("header") or "-"))
    add("")

    for label, title in (
        ("รหัสวิชา", "รหัสวิชา"),
        ("วิชา", "วิชา"),
        ("หน่วย", "หน่วย"),
        ("เรื่อง", "เรื่อง"),
    ):
        vals = _rows(cover, label)
        if vals:
            add("- **%s:** %s" % (title, " / ".join(vals)))
    add("")

    obj = _rows(cover, "จุดประสงค์ประจำหน่วยการเรียน")
    comp = _rows(cover, "ผลลัพธ์การเรียนรู้ระดับหน่วยการเรียน")
    if obj:
        add("## จุดประสงค์ประจำหน่วย (OBJ)")
        add(_bullets(obj))
        add("")
    if comp:
        add("## ผลลัพธ์การเรียนรู้ระดับหน่วย (COMP)")
        add(_bullets(comp))
        add("")

    heads = [b.get("text", "") for b in data.get("body", []) if b.get("type") == "h"]
    if heads:
        add("## โครงหัวข้อของ C1")
        add(_bullets(heads))
        add("")

    facts = dg.get("facts") or []
    if facts:
        add("## ข้อเท็จจริงแกน (ทุกสื่อต้องไม่ขัดกับข้อเหล่านี้)")
        add(_bullets(facts))
        add("")

    vocab = dg.get("vocab") or []
    if vocab:
        add("## ศัพท์ที่ทุกสื่อต้องใช้ให้ตรงกัน")
        add("| คำ | คำอ่าน | ความหมาย |")
        add("|----|--------|-----------|")
        for v in vocab:
            cells = [str(c).strip() for c in v] if isinstance(v, list) else [str(v), "", ""]
            cells = (cells + ["", "", ""])[:3]
            add("| %s | %s | %s |" % tuple(cells))
        add("")

    examples = dg.get("examples") or []
    if examples:
        add("## ตัวอย่าง / ตัวเลขหลัก (ใช้ซ้ำในสื่ออื่นเพื่อความสอดคล้อง)")
        add(_bullets(examples))
        add("")

    cautions = dg.get("cautions") or []
    if cautions:
        add("## จุดที่มักเข้าใจผิด / ข้อควรระวัง")
        add(_bullets(cautions))
        add("")

    if not dg:
        add("## (artifact นี้ยังไม่มี `digest`)")
        add("C1 ไฟล์นี้เขียนก่อนที่สคีมา `digest` จะมีผล — pack นี้จึงมีแค่หน้าปกกับโครงหัวข้อ")
        add("ถ้าต้องการข้อเท็จจริง/ศัพท์/ตัวอย่าง ให้เปิด C1 ฉบับเต็ม")
        add("")

    return "\n".join(out).rstrip() + "\n"


def main():
    args = [a for a in sys.argv[1:]]
    if not args:
        print(__doc__)
        return 2
    src = args[0]
    if not os.path.exists(src):
        print("ไม่พบไฟล์: %s" % src, file=sys.stderr)
        return 2
    try:
        data = load(src)
    except Exception as exc:
        print("อ่าน JSON ไม่ได้: %s" % exc, file=sys.stderr)
        return 2

    text = render(data, os.path.basename(src))

    out = args[1] if len(args) > 1 else None
    if out == "-":
        sys.stdout.write(text)
        return 0
    if out is None:
        out = src
        for suffix in ("_C1.json", ".json"):
            if out.endswith(suffix):
                out = out[: -len(suffix)] + "_srcpack.md"
                break
    with io.open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)

    chars = len(text)
    src_chars = len(io.open(src, encoding="utf-8").read())
    print("OK -> %s  (%d อักษร ~%d%% ของ C1 ที่ %d อักษร)"
          % (out, chars, round(chars * 100 / max(src_chars, 1)), src_chars))
    if not data.get("digest"):
        print("WARN: C1 ไม่มี `digest` — pack มีแค่หน้าปก+โครงหัวข้อ "
              "(ให้ content-academic เติม digest เมื่อแก้ไข C1 ครั้งต่อไป)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
