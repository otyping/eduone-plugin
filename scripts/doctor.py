# -*- coding: utf-8 -*-
"""doctor.py — ตรวจว่าเครื่องนี้พร้อมผลิตสื่อ EDU ONE หรือยัง

    python "<โฟลเดอร์ปลั๊กอิน>/scripts/doctor.py"

ออกแบบให้ **ใช้ได้ก่อนติดตั้งแพ็กเกจ** — จึงใช้ stdlib ล้วน ไม่ import อะไรที่
ยังไม่มี ถ้าขาดอะไรจะบอกคำสั่งแก้ให้ตรงจุด ไม่ใช่แค่บอกว่าพัง

exit 0 = พร้อมใช้งาน · exit 1 = มีบางอย่างต้องแก้
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SHARED = PLUGIN_ROOT / "skills" / "shared"

OK, WARN, BAD = "  [ok]  ", "  [!]   ", "  [แก้] "
problems: list[str] = []


def head(t: str) -> None:
    print(f"\n== {t} ==")


def need(cond: bool, ok_msg: str, fix_msg: str, fatal: bool = True) -> bool:
    if cond:
        print(OK + ok_msg)
        return True
    print((BAD if fatal else WARN) + fix_msg)
    if fatal:
        problems.append(fix_msg)
    return False


# ---------------------------------------------------------------- Python
head("Python")
v = sys.version_info
need(v[:2] == (3, 12),
     f"Python {v.major}.{v.minor}.{v.micro}",
     f"ต้องใช้ Python 3.12 (เครื่องนี้ {v.major}.{v.minor}) — "
     "Windows ให้ใช้ path เต็ม %LOCALAPPDATA%/Programs/Python/Python312/python.exe")
print(f"         ที่อยู่: {sys.executable}")

# ---------------------------------------------------------------- แพ็กเกจ
head("แพ็กเกจที่ pipeline ต้องใช้")
MODULES = [
    ("docx", "python-docx", True), ("pptx", "python-pptx", True),
    ("fitz", "PyMuPDF", True), ("PIL", "Pillow", True),
    ("pythainlp", "pythainlp", True), ("matplotlib", "matplotlib", True),
    ("numpy", "numpy", True), ("lxml", "lxml", True),
    ("yaml", "PyYAML", True), ("latex2mathml", "latex2mathml", True),
    ("win32com", "pywin32", False),
]
missing = []
for mod, dist, required in MODULES:
    found = importlib.util.find_spec(mod) is not None
    if found:
        print(OK + f"{dist}")
    elif required:
        print(BAD + f"{dist} — ยังไม่ได้ติดตั้ง")
        missing.append(dist)
    else:
        # pywin32 ใช้วัดจำนวนหน้า A4 จริงด้วย Word COM — ไม่มีก็ทำงานได้ แค่ข้ามการนับหน้า
        print(WARN + f"{dist} — ไม่มีก็ได้ (เฉพาะ Windows · ใช้ตรวจจำนวนหน้า .docx)")
if missing:
    problems.append("ติดตั้งแพ็กเกจที่ขาด")
    print(f'\n         แก้ด้วย:  pip install -r "{PLUGIN_ROOT / "requirements.txt"}"')

# ---------------------------------------------------------------- ตัวปลั๊กอิน
head("ไฟล์ของปลั๊กอิน")
need((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").is_file(),
     f"ปลั๊กอินอยู่ที่ {PLUGIN_ROOT}",
     f"ไม่พบ plugin.json ที่ {PLUGIN_ROOT} — สคริปต์นี้ถูกย้ายออกมาจากปลั๊กอินหรือเปล่า")

n_agents = len(list((PLUGIN_ROOT / "agents").glob("*.md"))) if (PLUGIN_ROOT / "agents").is_dir() else 0
need(n_agents == 16, f"sub-agent ครบ 16 ตัว",
     f"sub-agent มี {n_agents} ตัว (ควรเป็น 16) — ลอง claude plugin update edu-one")

skills = sorted(d.name for d in (PLUGIN_ROOT / "skills").iterdir()
                if d.is_dir() and (d / "SKILL.md").is_file()) if (PLUGIN_ROOT / "skills").is_dir() else []
need(len(skills) == 8, f"สกิลครบ 8 ตัว: {' '.join(skills)}",
     f"สกิลมี {len(skills)} ตัว (ควรเป็น 8): {' '.join(skills) or 'ไม่พบเลย'}")

need((SHARED / "scripts" / "paths.py").is_file() and (SHARED / "symbols.txt").is_file(),
     "สคริปต์และไฟล์ประกอบครบ",
     "ไฟล์ใน skills/shared/ ไม่ครบ — ลอง claude plugin update edu-one")

courses = sorted(f.stem.replace("course-structure-", "")
                 for f in (SHARED / "reference").glob("course-structure-*.md"))
need(bool(courses), f"หลักสูตรที่มี {len(courses)} คู่: {' '.join(courses)}",
     "ไม่พบไฟล์หลักสูตรเลยใน skills/shared/reference/")

# ---------------------------------------------------------------- Claude Code
head("Claude Code")
claude = shutil.which("claude")
if need(bool(claude), f"พบที่ {claude}", "ไม่พบคำสั่ง claude — ยังไม่ได้ติดตั้ง Claude Code"):
    try:
        # บังคับ utf-8 — console ไทยเป็น cp874 อ่าน output ที่มีอักษรไทยไม่ได้
        out = subprocess.run([claude, "plugin", "list"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace",
                             timeout=30).stdout or ""
        need("edu-one" in out, "ปลั๊กอิน edu-one ติดตั้งแล้ว",
             "ยังไม่ได้ติดตั้งปลั๊กอิน — claude plugin install edu-one@eduone")
    except Exception as exc:
        print(WARN + f"เรียก claude plugin list ไม่สำเร็จ: {exc}")

# ---------------------------------------------------------------- ที่ทำงาน
head("โฟลเดอร์งาน")
sys.path.insert(0, str(SHARED / "scripts"))
try:
    os.environ.setdefault("CLAUDE_PLUGIN_ROOT", str(PLUGIN_ROOT))
    import _root  # noqa: E402
    print(OK + f"ผลผลิตจะลงที่ {_root.OUTPUT_ROOT}")
    print(f"         อ่านหลักสูตรจาก {_root.REFERENCE_DIR}")
    if _root.WORK_ROOT == Path.cwd() and not (Path.cwd() / "Output").exists():
        print(WARN + "ยังไม่มีโฟลเดอร์ Output/ ที่นี่ — ถ้านี่ไม่ใช่โฟลเดอร์งานของคุณ "
                     "ให้ cd ไปที่โฟลเดอร์งานก่อน หรือตั้ง EDUONE_WORK_DIR")
except Exception as exc:
    print(BAD + f"หา path ไม่ได้: {exc}")
    problems.append("path")

# ---------------------------------------------------------------- สรุป
print()
if problems:
    print(f"ยังไม่พร้อม — ต้องแก้ {len(problems)} เรื่อง (ดูบรรทัด [แก้] ข้างบน)")
    sys.exit(1)
print("พร้อมใช้งาน — เปิด Claude Code ในโฟลเดอร์งานแล้วพิมพ์ /edu-one ได้เลย")
sys.exit(0)
