# -*- coding: utf-8 -*-
"""_root.py — หา "ที่อยู่ของความฉลาด" กับ "ที่อยู่ของงาน" แยกจากกัน

ทำไมต้องมีไฟล์นี้
    เดิมสคริปต์คำนวณ REPO_ROOT เองด้วยการนับโฟลเดอร์ขึ้นไป (parents[4]) แล้วใช้
    ค่าเดียวกันนั้นทั้งหา "ข้อมูลอ้างอิงหลักสูตร" และ "ที่วาง Output/BookScan"
    ซึ่งใช้ได้เฉพาะตอนที่ทุกอย่างอยู่ใน repo เดียวกัน

    พอแจกเป็น Claude Code plugin สองอย่างนี้จะอยู่คนละที่:
        ความฉลาด -> ~/.claude/plugins/edu-one/    (อ่านอย่างเดียว อัปเดตทับได้)
        งาน       -> โฟลเดอร์งานของพนักงานแต่ละคน  (เขียนผลผลิตลงที่นี่)
    การนับ parents จะชี้ผิดทันที และที่แย่กว่าคือมัน "เงียบ" ไม่ error

ลำดับการหา (ตัวแรกที่เจอชนะ)
    REFERENCE_DIR : EDUONE_REFERENCE_DIR -> CLAUDE_PLUGIN_ROOT -> เดินขึ้นหา .claude/
    WORK_ROOT     : EDUONE_WORK_DIR -> CLAUDE_PROJECT_DIR -> เดินขึ้นหาหมุดของ repo -> cwd

ยังเข้ากันได้กับโครงเดิม 100% — ถ้าไม่ตั้ง env อะไรเลย จะได้ค่าเท่าที่เคยเป็น
"""
from __future__ import annotations

import os
from pathlib import Path

# หมุดที่บอกว่า "ตรงนี้คือรากของที่ทำงาน" — เรียงตามความเฉพาะเจาะจง
WORK_MARKERS = ("CLAUDE.md", "Output", ".git")


def _env_path(name: str) -> Path | None:
    v = os.environ.get(name)
    if not v:
        return None
    p = Path(v).expanduser()
    return p if p.exists() else None


def _walk_up(start: Path, test) -> Path | None:
    """เดินขึ้นจาก start จนกว่า test(dir) จะเป็นจริง — คืน None ถ้าถึงรากแล้วไม่เจอ"""
    for d in (start, *start.parents):
        if test(d):
            return d
    return None


def find_reference_dir() -> Path:
    """โฟลเดอร์ข้อมูลอ้างอิง (course-structure-*.md, grades.txt, subjects.txt)"""
    p = _env_path("EDUONE_REFERENCE_DIR")
    if p:
        return p

    plugin = _env_path("CLAUDE_PLUGIN_ROOT")
    if plugin:
        # โครงของ plugin: <plugin>/skills/shared/reference
        cand = plugin / "skills" / "shared" / "reference"
        if cand.is_dir():
            return cand
        cand = plugin / "reference"
        if cand.is_dir():
            return cand

    # โครงเดิมใน repo: เดินขึ้นหา .claude/skills/shared/reference
    here = Path(__file__).resolve().parent
    root = _walk_up(here, lambda d: (d / ".claude" / "skills" / "shared" / "reference").is_dir())
    if root:
        return root / ".claude" / "skills" / "shared" / "reference"

    # ทางสุดท้าย: ข้าง ๆ ตัวเอง (กรณีสคริปต์ถูกคัดลอกไปวางเดี่ยว ๆ)
    return here.parent / "reference"


def find_work_root() -> Path:
    """รากของที่ทำงาน — ที่วาง Output/ และ BookScan/"""
    for name in ("EDUONE_WORK_DIR", "CLAUDE_PROJECT_DIR"):
        p = _env_path(name)
        if p:
            return p

    cwd = Path.cwd().resolve()
    root = _walk_up(cwd, lambda d: any((d / m).exists() for m in WORK_MARKERS))
    if root:
        return root

    return cwd


REFERENCE_DIR = find_reference_dir()
WORK_ROOT = find_work_root()
OUTPUT_ROOT = WORK_ROOT / "Output"
BOOKSCAN_ROOT = WORK_ROOT / "BookScan"


def describe() -> str:
    """ใช้ตอน debug ว่าสคริปต์กำลังอ่าน/เขียนที่ไหน"""
    return (
        f"REFERENCE_DIR = {REFERENCE_DIR}  ({'มี' if REFERENCE_DIR.is_dir() else 'ไม่พบ'})\n"
        f"WORK_ROOT     = {WORK_ROOT}\n"
        f"OUTPUT_ROOT   = {OUTPUT_ROOT}  ({'มี' if OUTPUT_ROOT.is_dir() else 'ยังไม่มี'})\n"
        f"BOOKSCAN_ROOT = {BOOKSCAN_ROOT}  ({'มี' if BOOKSCAN_ROOT.is_dir() else 'ยังไม่มี'})"
    )


if __name__ == "__main__":
    print(describe())
