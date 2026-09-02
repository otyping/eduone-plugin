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
  บล็อกระดับหน่วย (option):
    ### หน่วย <unitNum> (No.<a>-<b>)
    - OBJ|     ...   จุดประสงค์ประจำหน่วย        (xlsx คอลัมน์ E)
    - IND|     ...   ตัวชี้วัด เช่น 'ค 1.1 ม.1/1'  (xlsx คอลัมน์ F)
    - OUTCOME| ...   ผลลัพธ์/สมรรถนะระดับหน่วย ที่เขียนขึ้นเอง (ไม่มีในหลักสูตร)
  บล็อกระดับคาบ (option — มีเฉพาะหลักสูตรที่ละเอียดถึงคาบ):
    - COMP|     <No.> | สาระสำคัญ/จุดประสงค์ประจำคาบ  (xlsx คอลัมน์ I)
    - SKILLS8C| <No.> | C1 | C5                      (xlsx คอลัมน์ J)
    - POBJ|     <No.> | 1, 2                          เลขข้อ OBJ ของหน่วยที่คาบนี้รับ

  ★ นิยามที่เจ้าของโปรเจกต์กำหนด — OBJ = ระดับหน่วย · COMP = **ระดับคาบ**
    (สิ่งที่นักเรียนได้เมื่อจบคาบนั้น) ไฟล์รุ่นเก่าเขียน `COMP|` เป็นระดับหน่วย
    ตัวอ่านยังรับได้แต่จะจัดเป็น `outcome` ให้อัตโนมัติ
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
# คอลัมน์ที่ 4 (คาบ) เป็นตัวเลือก — ไฟล์เก่าที่มี 3 คอลัมน์ยังอ่านได้เหมือนเดิม
ROW_RE = re.compile(
    r"^\|\s*(\d+)\s*\|\s*(\d+)\.\s*(.+?)\s*\|\s*(\d+)\.\s*(.+?)\s*\|"
    r"(?:\s*(\d+)\.\s*(.+?)\s*\|)?\s*$"
)
UNITBLK_RE = re.compile(r"^###\s*หน่วย\s*(\d+)\b.*?No\.(\d+)\s*[-–]\s*(\d+)")
OBJ_RE = re.compile(r"^[-*]\s*OBJ\|\s*(.+?)\s*$")
IND_RE = re.compile(r"^[-*]\s*IND\|\s*(.+?)\s*$")
OUTCOME_RE = re.compile(r"^[-*]\s*OUTCOME\|\s*(.+?)\s*$")
# ระดับคาบ — ต้องมีเลข No. คั่นด้วย | เสมอ จึงไม่ชนกับ COMP| รุ่นเก่าที่ไม่มีเลขคีย์
COMP_RE = re.compile(r"^[-*]\s*COMP\|\s*(\d+)\s*\|\s*(.+?)\s*$")
SKILLS8C_RE = re.compile(r"^[-*]\s*SKILLS8C\|\s*(\d+)\s*\|\s*(.+?)\s*$")
POBJ_RE = re.compile(r"^[-*]\s*POBJ\|\s*(\d+)\s*\|\s*([\d\s,]*?)\s*$")
# COMP| รุ่นเก่า (ระดับหน่วย ไม่มีเลขคีย์) — รับไว้เพื่อไม่ให้ไฟล์ที่ยังไม่ย้ายพัง
LEGACY_COMP_RE = re.compile(r"^[-*]\s*COMP\|\s*(?!\d+\s*\|)(.+?)\s*$")
# - PREREQ| 4 <- 2, 3   (รับ <- , ← , : เป็นตัวคั่นได้)
PREREQ_RE = re.compile(r"^[-*]\s*PREREQ\|\s*(\d+)\s*(?:<-|←|:)\s*([\d\s,]+?)\s*$")


def _md_path(grade_slug: str, subject_slug: str) -> Path:
    return REFERENCE_DIR / f"course-structure-{grade_slug}-{subject_slug}.md"


def load_8c() -> dict[str, dict]:
    """คืน {'C1': {'code','en','th'}, ...} จาก skills-8c.txt (ชื่อทางการของ 8C)

    แผน L1/L2 ต้องมีครบทั้ง 8 ข้อทุกแผน — ชื่ออังกฤษคือชื่อที่พิมพ์ลงเอกสาร
    """
    path = REFERENCE_DIR / "skills-8c.txt"
    out: dict[str, dict] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = [c.strip() for c in line.split("	") if c.strip()]
        if len(parts) >= 3:
            out[parts[0]] = {"code": parts[0], "en": parts[1], "th": parts[2]}
    return out


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
    unit_meta: dict[int, dict] = {}   # unitNum -> {obj:[], ind:[], outcome:[], range:(a,b)}
    period_meta: dict[int, dict] = {}  # No. -> {comp:str, skills_8c:[], pobj:[]}
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
            unit_meta.setdefault(cur_unit, {"obj": [], "ind": [], "outcome": [],
                                            "range": (int(m.group(2)), int(m.group(3)))})
            continue
        # --- ระดับคาบ: ต้องเช็กก่อนระดับหน่วย เพราะ COMP| มีสองรูปแบบ ---
        m = COMP_RE.match(line)
        if m:
            period_meta.setdefault(int(m.group(1)), {})["comp"] = m.group(2)
            continue
        m = SKILLS8C_RE.match(line)
        if m:
            codes = [c.strip().upper() for c in re.split(r"[|,]", m.group(2)) if c.strip()]
            period_meta.setdefault(int(m.group(1)), {})["skills_8c"] = codes
            continue
        m = POBJ_RE.match(line)
        if m:
            nums = [int(x) for x in re.split(r"[,\s]+", m.group(2)) if x]
            period_meta.setdefault(int(m.group(1)), {})["pobj"] = nums
            continue
        # --- ระดับหน่วย ---
        m = OBJ_RE.match(line)
        if m and cur_unit is not None:
            unit_meta[cur_unit]["obj"].append(m.group(1))
            continue
        m = IND_RE.match(line)
        if m and cur_unit is not None:
            unit_meta[cur_unit]["ind"].append(m.group(1))
            continue
        m = OUTCOME_RE.match(line)
        if m and cur_unit is not None:
            unit_meta[cur_unit]["outcome"].append(m.group(1))
            continue
        m = LEGACY_COMP_RE.match(line)
        if m and cur_unit is not None:
            unit_meta[cur_unit]["outcome"].append(m.group(1))
            continue
        m = ROW_RE.match(line)
        if m:
            in_table = True
            no = int(m.group(1))
            if no in rows:
                raise RuntimeError(f"duplicate No.{no} in {path.name}")
            clean = lambda g: m.group(g).strip().rstrip("/").strip()  # noqa: E731
            rows[no] = {
                "unit": int(m.group(2)),
                "unit_name": m.group(3).strip(),
                "order": int(m.group(4)),
                "topic_name": clean(5),
                # มีค่าเฉพาะหลักสูตรที่ละเอียดถึงระดับคาบ — None = หลักสูตรแบบเดิม
                "period": int(m.group(6)) if m.group(6) else None,
                "period_name": clean(7) if m.group(6) else None,
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
    return {"front": front, "rows": rows, "unit_meta": unit_meta,
            "period_meta": period_meta, "prereq": prereq}


def _locate(grade_token: str, subject_token: str, row: dict) -> tuple[str, str, str]:
    """คืน (base, topic_dir, topic_folder) จากแถวหนึ่งของตารางหลักสูตร

    หลักสูตรระดับคาบซ้อนโฟลเดอร์คาบไว้ใต้หัวข้อหลัก ไม่วางเรียงกันแบนใต้หน่วย —
    หน่วยหนึ่งมีได้ถึง 17 คาบ ถ้าวางแบนจะเปิดหน่วยแล้วเจอ 17 โฟลเดอร์ที่มองไม่ออกว่า
    เรื่องไหนคู่กับเรื่องไหน · และโฟลเดอร์ระดับหัวข้อหลักที่ทำไว้ก่อนหน้านี้กลายเป็น
    "พ่อ" ของคาบพอดี ไม่ต้องย้ายงานเดิมเลย

        3 คอลัมน์  P1-Sci_U1_1        Output/P1/Sci/P1-Sci_U1/P1-Sci_U1_1/
        4 คอลัมน์  M1-Math_U1_4_1     Output/M1/Math/M1-Math_U1/M1-Math_U1_4/M1-Math_U1_4_1/
    """
    prefix = f"{grade_token}-{subject_token}_U{row['unit']}"
    unit_folder = prefix
    topic_folder = f"{prefix}_{row['order']}"
    root = f"Output/{grade_token}/{subject_token}/{unit_folder}"
    if row.get("period") is None:
        return topic_folder, f"{root}/{topic_folder}", topic_folder
    base = f"{topic_folder}_{row['period']}"
    return base, f"{root}/{topic_folder}/{base}", topic_folder


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
    pm = parsed["period_meta"].get(no, {})
    # Title-case tokens สำหรับ path/ชื่อไฟล์ output (slug ตัวเล็ก = internal lookup)
    grade_token = grade_slug.upper()            # p1 -> P1
    subject_token = subject_slug.capitalize()   # sci -> Sci
    unit_folder = f"{grade_token}-{subject_token}_U{unit}"     # P1-Sci_U1
    base, topic_dir, topic_folder = _locate(grade_token, subject_token, row)

    # COMP ของคาบ — ถ้าหลักสูตรยังไม่มีข้อมูลรายคาบ ถอยไปใช้ OUTCOME ระดับหน่วย
    if pm.get("comp"):
        comp, comp_source = [pm["comp"]], "period"
    elif um.get("outcome"):
        comp, comp_source = list(um["outcome"]), "unit_outcome"
    else:
        comp, comp_source = [], "none"

    # ทักษะ 8C ที่คาบนี้เน้น — เติมชื่อทางการจาก skills-8c.txt ให้เลย
    table8c = load_8c()
    skills_8c = [table8c.get(c, {"code": c, "en": "", "th": ""})
                 for c in pm.get("skills_8c", [])]

    # OBJ ระดับหน่วยที่คาบนี้รับ — ไม่ระบุ = ว่าง (orchestrator ต้องถาม ห้ามเดา)
    obj_all = um.get("obj", [])
    period_obj = [obj_all[i - 1] for i in pm.get("pobj", []) if 1 <= i <= len(obj_all)]

    # หัวข้อที่ต้องรู้มาก่อน — คืน metadata พอให้ประกอบ path ได้ (paths.py เติม path ให้)
    prereq = []
    for d in parsed["prereq"].get(no, []):
        r = rows[d]
        d_base, d_dir, _ = _locate(grade_token, subject_token, r)
        prereq.append({
            "no": d,
            "topic_name": r["period_name"] or r["topic_name"],
            "unit": r["unit"],
            "base": d_base,
            "topic_dir": d_dir,
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
        # หลักสูตรระดับคาบ: topic_name = ชื่อคาบ (สิ่งที่ผลิตจริง)
        # ส่วนชื่อหัวข้อหลักที่คาบนี้สังกัดอยู่ที่ main_topic_name
        "topic_name": row["period_name"] or row["topic_name"],
        "main_topic_name": row["topic_name"],
        "period": row["period"],
        "topic_folder": topic_folder,
        "obj": um.get("obj", []),
        # ★ COMP = ระดับ **คาบ** (สาระสำคัญ/จุดประสงค์ประจำคาบ — xlsx คอลัมน์ I)
        #   หลักสูตรที่ยังไม่มีข้อมูลรายคาบจะถอยไปใช้ OUTCOME ระดับหน่วย
        #   ดู comp_source เพื่อรู้ว่าได้ของจริงหรือของสำรอง
        "comp": comp,
        "comp_source": comp_source,
        "indicator": um.get("ind", []),
        "outcome": um.get("outcome", []),
        "skills_8c": skills_8c,
        "period_obj": period_obj,
        "unit_folder": unit_folder,
        "base": base,
        "topic_dir": topic_dir,
        "prereq": prereq,
        # หัวกระดาษของทุกเอกสาร — แหล่งเดียว ใช้ทั้ง .docx และหน้าปก .pptx
        #   หลักสูตรรายคาบ: ... > หน่วยX > หัวข้อY > เรื่องZ
        #   หลักสูตรเดิม:   ... > หน่วยX > เรื่องY
        "header": (
            f"ระดับชั้น{front.get('GRADE','')} > วิชา{front.get('SUBJECT','')} > "
            f"หน่วย{row['unit_name']} > "
            + (f"หัวข้อ{row['topic_name']} > เรื่อง{row['period_name']}"
               if row["period"] else f"เรื่อง{row['topic_name']}")
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
