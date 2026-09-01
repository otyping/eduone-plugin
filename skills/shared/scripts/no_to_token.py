"""Map (grade, subject, No.) -> metadata + BASE token  สำหรับ EDU ONE (สพฐ.)

อ่าน ${CLAUDE_PLUGIN_ROOT}/skills/shared/reference/course-structure-<gradeSlug>-<subject>.md
ที่ถอดจาก xlsx โครงสร้างหลักสูตรของแต่ละ (ระดับชั้น × วิชา).

Namespace: No. แยกต่อ (ระดับชั้น × วิชา) เริ่มที่ 1 ใหม่
BASE token (Title-case): <GradeToken>-<SubjectToken>_U<unit>_<order>  เช่น  P1-Sci_U1_1
  (GradeToken=gradeSlug.upper(), SubjectToken=subjectSlug.capitalize(); args ยังเป็น slug ตัวเล็ก)

โครงสร้าง markdown ที่อ่าน (รอไฟล์จริง — fixture เป็นตัวอย่าง):
  front matter (เริ่มไฟล์):
    GRADE| ป.1
    GRADE_SLUG| p1
    SUBJECT| วิทยาศาสตร์และเทคโนโลยี
    SUBJECT_SLUG| sci
    SUBJECT_CODE| ว11101
    PERIOD_MINUTES| 50
    LANG| th
  ตารางหัวข้อ:
    | No. | <unitNum>. <unitName> | <orderNum>. <topic> |
  บล็อกระดับหน่วย (option — OBJ/COMP):
    ### หน่วย <unitNum> (No.<a>-<b>)
    - OBJ| ...
    - COMP| ...
  หัวข้อที่ต่อยอดจากหัวข้ออื่น (option — PREREQ) วางไว้ที่ไหนก็ได้ในไฟล์:
    - PREREQ| 4 <- 2, 3        # No.4 ต้องรู้ No.2 และ No.3 มาก่อน
    ไม่ระบุ = ไม่มี prereq (ค่าเริ่มต้นที่ปลอดภัย) — ระบุเฉพาะหัวข้อที่ต่อยอดกันจริง
    ข้อบังคับ: No. ต้องมีอยู่จริง · ห้ามอ้างตัวเอง · ต้องอ้างหัวข้อที่มาก่อน (prereq < no)

CLI: python no_to_token.py <gradeSlug> <subjectSlug> <no>
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _root import REFERENCE_DIR  # noqa: E402

FRONT_RE = re.compile(r"^([A-Z_]+)\|\s*(.+?)\s*$")
ROW_RE = re.compile(
    r"^\|\s*(\d+)\s*\|\s*(\d+)\.\s*(.+?)\s*\|\s*(\d+)\.\s*(.+?)\s*\|\s*$"
)
UNITBLK_RE = re.compile(r"^###\s*หน่วย\s*(\d+)\b.*?No\.(\d+)\s*[-–]\s*(\d+)")
OBJ_RE = re.compile(r"^[-*]\s*OBJ\|\s*(.+?)\s*$")
COMP_RE = re.compile(r"^[-*]\s*COMP\|\s*(.+?)\s*$")
# - PREREQ| 4 <- 2, 3   (รับ <- , ← , : เป็นตัวคั่นได้)
PREREQ_RE = re.compile(r"^[-*]\s*PREREQ\|\s*(\d+)\s*(?:<-|←|:)\s*([\d\s,]+?)\s*$")


def _md_path(grade_slug: str, subject_slug: str) -> Path:
    return REFERENCE_DIR / f"course-structure-{grade_slug}-{subject_slug}.md"


def _parse(grade_slug: str, subject_slug: str) -> dict:
    path = _md_path(grade_slug, subject_slug)
    if not path.exists():
        raise FileNotFoundError(
            f"ไม่พบ {path.name} — ต้องวางไฟล์โครงสร้างหลักสูตร (ถอดจาก xlsx) ของ "
            f"{grade_slug}/{subject_slug} ก่อน (ดู fixture เป็นตัวอย่างรูปแบบ)"
        )
    text = path.read_text(encoding="utf-8")
    front: dict[str, str] = {}
    rows: dict[int, dict] = {}
    unit_meta: dict[int, dict] = {}   # unitNum -> {obj:[], comp:[], range:(a,b)}
    prereq: dict[int, list[int]] = {}  # no -> [no ที่ต้องรู้ก่อน]
    cur_unit = None
    in_table = False
    for line in text.splitlines():
        m = PREREQ_RE.match(line)
        if m:
            target = int(m.group(1))
            deps = [int(x) for x in re.split(r"[,\s]+", m.group(2)) if x]
            if target in prereq:
                raise RuntimeError(f"duplicate PREREQ for No.{target} in {path.name}")
            prereq[target] = deps
            continue
        m = FRONT_RE.match(line)
        if m and not in_table:
            front[m.group(1)] = m.group(2)
            continue
        m = UNITBLK_RE.match(line)
        if m:
            cur_unit = int(m.group(1))
            unit_meta.setdefault(cur_unit, {"obj": [], "comp": [],
                                            "range": (int(m.group(2)), int(m.group(3)))})
            continue
        m = OBJ_RE.match(line)
        if m and cur_unit is not None:
            unit_meta[cur_unit]["obj"].append(m.group(1))
            continue
        m = COMP_RE.match(line)
        if m and cur_unit is not None:
            unit_meta[cur_unit]["comp"].append(m.group(1))
            continue
        m = ROW_RE.match(line)
        if m:
            in_table = True
            no = int(m.group(1))
            if no in rows:
                raise RuntimeError(f"duplicate No.{no} in {path.name}")
            rows[no] = {
                "unit": int(m.group(2)),
                "unit_name": m.group(3).strip(),
                "order": int(m.group(4)),
                "topic_name": m.group(5).strip().rstrip("/").strip(),
            }
    # ตรวจ PREREQ หลังอ่านตารางครบ (ต้องรู้ว่ามี No. ไหนบ้าง)
    for target, deps in prereq.items():
        if target not in rows:
            raise RuntimeError(f"PREREQ อ้าง No.{target} ที่ไม่มีในตาราง ({path.name})")
        for d in deps:
            if d not in rows:
                raise RuntimeError(
                    f"PREREQ| {target} <- {d} : ไม่มี No.{d} ในตาราง ({path.name})")
            if d == target:
                raise RuntimeError(f"PREREQ| {target} <- {d} : อ้างตัวเอง ({path.name})")
            if d > target:
                raise RuntimeError(
                    f"PREREQ| {target} <- {d} : ต้องอ้างหัวข้อที่มาก่อน "
                    f"(No.{d} อยู่หลัง No.{target}) ({path.name})")
    return {"front": front, "rows": rows, "unit_meta": unit_meta, "prereq": prereq}


def no_to_token(grade_slug: str, subject_slug: str, no: int) -> dict:
    parsed = _parse(grade_slug, subject_slug)
    rows = parsed["rows"]
    if no not in rows:
        raise KeyError(
            f"No.{no} not found in course-structure-{grade_slug}-{subject_slug}.md"
        )
    front = parsed["front"]
    row = dict(rows[no])
    unit = row["unit"]
    um = parsed["unit_meta"].get(unit, {})
    # Title-case tokens สำหรับ path/ชื่อไฟล์ output (slug ตัวเล็ก = internal lookup)
    grade_token = grade_slug.upper()            # p1 -> P1
    subject_token = subject_slug.capitalize()   # sci -> Sci
    unit_folder = f"{grade_token}-{subject_token}_U{unit}"     # P1-Sci_U1
    base = f"{grade_token}-{subject_token}_U{unit}_{row['order']}"  # P1-Sci_U1_1
    topic_dir = f"Output/{grade_token}/{subject_token}/{unit_folder}/{base}"

    # หัวข้อที่ต้องรู้มาก่อน — คืน metadata พอให้ประกอบ path ได้ (paths.py เติม path ให้)
    prereq = []
    for d in parsed["prereq"].get(no, []):
        r = rows[d]
        d_unit_folder = f"{grade_token}-{subject_token}_U{r['unit']}"
        d_base = f"{grade_token}-{subject_token}_U{r['unit']}_{r['order']}"
        prereq.append({
            "no": d,
            "topic_name": r["topic_name"],
            "unit": r["unit"],
            "base": d_base,
            "topic_dir": (
                f"Output/{grade_token}/{subject_token}/{d_unit_folder}/{d_base}"),
        })

    return {
        "grade": front.get("GRADE", ""),
        "grade_slug": grade_slug,
        "grade_token": grade_token,
        "subject": front.get("SUBJECT", ""),
        "subject_slug": subject_slug,
        "subject_token": subject_token,
        "subject_code": front.get("SUBJECT_CODE", ""),
        "period_minutes": front.get("PERIOD_MINUTES", ""),
        "lang": front.get("LANG", "th"),
        "no": no,
        "unit": unit,
        "unit_name": row["unit_name"],
        "order": row["order"],
        "topic_name": row["topic_name"],
        "obj": um.get("obj", []),
        "comp": um.get("comp", []),
        "unit_folder": unit_folder,
        "base": base,
        "topic_dir": topic_dir,
        "prereq": prereq,
        "header": (
            f"ระดับชั้น{front.get('GRADE','')} > วิชา{front.get('SUBJECT','')} > "
            f"หน่วย{row['unit_name']} > เรื่อง{row['topic_name']}"
        ),
    }


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("usage: no_to_token.py <gradeSlug> <subjectSlug> <no>", file=sys.stderr)
        return 2
    try:
        no = int(argv[3])
    except ValueError:
        print(f"invalid No.: {argv[3]!r}", file=sys.stderr)
        return 2
    try:
        result = no_to_token(argv[1], argv[2], no)
    except (ValueError, KeyError, RuntimeError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
