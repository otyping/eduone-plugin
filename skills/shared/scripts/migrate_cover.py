# -*- coding: utf-8 -*-
"""ย้ายหน้าปกของ artifact เดิม (6 แถว) ให้เป็นรูปแบบใหม่ (7 แถว)

    python migrate_cover.py <gradeSlug> <subjectSlug> <No>            # ดูอย่างเดียว
    python migrate_cover.py <gradeSlug> <subjectSlug> <No> --apply    # เขียนจริง

ทำอะไร — กับ C1 · C2 · L1 · L2 ของคาบนั้น (ทั้ง 4 ไฟล์ใช้หน้าปกชุดเดียวกัน)
    1. แทรกแถว `ตัวชี้วัด` ต่อจากแถว `หน่วย`      (ค่าจาก metadata คอลัมน์ F)
    2. `จุดประสงค์ประจำหน่วยการเรียน`  -> `จุดประสงค์ประจำหน่วย`      (ป้ายชื่อ)
    3. `ผลลัพธ์การเรียนรู้ระดับหน่วยการเรียน` -> `สาระสำคัญ / จุดประสงค์ประจำคาบ`
       **พร้อมเปลี่ยนค่า** จาก COMP ระดับหน่วยเป็น COMP ของคาบ (คอลัมน์ I)
    4. `header` เขียนใหม่จาก metadata (รูปแบบ ... > หัวข้อX > เรื่องY)

ทำไมต้องเปลี่ยนค่าไม่ใช่แค่ชื่อ
    ค่าเดิมในแถวสุดท้ายคือผลลัพธ์ระดับ**หน่วย** ซึ่งกินหลายคาบ เอามาวางในช่องที่
    บอกว่า "จุดประสงค์ประจำคาบ" จะกลายเป็นสัญญาเท็จกับครูผู้ใช้เอกสาร

หลัง migrate ต้อง build .docx ใหม่ทุกไฟล์ (สคริปต์นี้แตะเฉพาะ .json ที่เป็นแหล่งจริง)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _root import WORK_ROOT  # noqa: E402
from no_to_token import no_to_token  # noqa: E402
from paths import topic_paths  # noqa: E402
from validate_spec import COVER_LABELS  # noqa: E402

OLD_OBJ = "จุดประสงค์ประจำหน่วยการเรียน"
OLD_COMP = "ผลลัพธ์การเรียนรู้ระดับหน่วยการเรียน"

#: ไฟล์ที่ใช้หน้าปกชุดเดียวกัน
KEYS = ("content_c1_json", "content_c2_json", "plan_l1_json", "plan_l2_json")


def _as_list(v):
    return v if isinstance(v, list) else ([v] if v else [])


def migrate_rows(rows: list, meta: dict) -> tuple[list, list[str]]:
    """คืน (rows ใหม่, รายการสิ่งที่เปลี่ยน) — เรียกซ้ำได้ ถ้าใหม่อยู่แล้วจะไม่เปลี่ยนอะไร"""
    notes: list[str] = []
    out = [list(r) for r in rows]
    labels = [r[0] for r in out if r]

    # 1) ป้ายชื่อสองแถวท้าย
    for r in out:
        if r and r[0] == OLD_OBJ:
            r[0] = "จุดประสงค์ประจำหน่วย"
            notes.append("เปลี่ยนป้าย -> จุดประสงค์ประจำหน่วย")
        elif r and r[0] == OLD_COMP:
            r[0] = "สาระสำคัญ / จุดประสงค์ประจำคาบ"
            notes.append("เปลี่ยนป้าย -> สาระสำคัญ / จุดประสงค์ประจำคาบ")

    # 2) ค่าของแถว COMP ต้องเป็นของคาบ ไม่ใช่ของหน่วย
    comp = _as_list(meta.get("comp"))
    for r in out:
        if r and r[0] == "สาระสำคัญ / จุดประสงค์ประจำคาบ":
            if comp and r[1] != comp and _as_list(r[1]) != comp:
                r[1] = comp if len(comp) > 1 else comp[0]
                notes.append("แทนค่าด้วย COMP ของคาบ (%s)" % meta.get("comp_source"))

    # 3) แทรกแถวตัวชี้วัดต่อจากแถวหน่วย
    if "ตัวชี้วัด" not in labels:
        ind = _as_list(meta.get("indicator"))
        val = (ind if len(ind) > 1 else (ind[0] if ind else "—"))
        pos = next((i for i, r in enumerate(out) if r and r[0] == "หน่วย"), None)
        if pos is None:
            notes.append("!! ไม่พบแถว 'หน่วย' — แทรกตัวชี้วัดไม่ได้")
        else:
            out.insert(pos + 1, ["ตัวชี้วัด", val])
            notes.append("แทรกแถวตัวชี้วัด (%s)" % ("มีค่า" if ind else "ว่าง -> —"))

    got = [r[0] for r in out if r]
    if got != COVER_LABELS:
        notes.append("!! ลำดับป้ายยังไม่ตรงมาตรฐาน: %s" % got)
    return out, notes


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    apply_ = "--apply" in argv
    if len(args) != 3:
        print("usage: migrate_cover.py <gradeSlug> <subjectSlug> <No> [--apply]",
              file=sys.stderr)
        return 2
    meta = no_to_token(args[0], args[1], int(args[2]))
    paths = topic_paths(meta)
    rc = 0
    for key in KEYS:
        rel = paths[key]
        f = Path(WORK_ROOT) / rel
        if not f.is_file():
            print(f"ข้าม (ไม่มีไฟล์): {rel}")
            continue
        data = json.loads(f.read_text(encoding="utf-8-sig"))
        cover = data.get("cover") or {}
        rows, notes = migrate_rows(cover.get("rows") or [], meta)
        if data.get("header") != meta["header"]:
            notes.append("เขียน header ใหม่")
        if not notes:
            print(f"ไม่ต้องแก้: {rel}")
            continue
        print(f"{rel}")
        for n in notes:
            print(f"    - {n}")
            if n.startswith("!!"):
                rc = 1
        if apply_:
            cover["rows"] = rows
            data["cover"] = cover
            data["header"] = meta["header"]
            f.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8", newline="\n")
    if not apply_:
        print("\n--- ดูอย่างเดียว · เติม --apply เพื่อเขียนจริง แล้ว build .docx ใหม่")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
