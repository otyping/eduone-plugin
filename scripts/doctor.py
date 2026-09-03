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

# ---------------------------------------------------------------- เทอร์มินัลของพนักงานเอง
head("คำสั่ง eduone-py ในเทอร์มินัลของคุณ")
# Claude Code เติม bin/ ของปลั๊กอินเข้า PATH ให้เฉพาะตอนที่ตัวมันเองรันคำสั่ง — หน้าต่าง
# เทอร์มินัลที่พนักงานเปิดเอง (หน้าต่างที่ใช้รัน watch.py ตามที่เว็บบอก) จึงไม่รู้จัก
# ต้องถามเชลล์จริง ๆ โดย **ตัด bin ของปลั๊กอินออกจาก PATH ก่อน** ไม่งั้นตอนรันผ่าน
# eduone-py เองจะผ่านแบบหลอก ๆ ทุกครั้ง ทั้งที่หน้าต่างของพนักงานยังใช้ไม่ได้


def own_shell_knows_eduone_py() -> tuple[bool, str]:
    """คืน (เชลล์ของผู้ใช้รู้จักไหม, ExecutionPolicy)

    ตัวหลังจำเป็น เพราะสาเหตุที่พบบ่อยที่สุดไม่ใช่ "ยังไม่ได้ตั้ง" แต่คือ **ตั้งแล้วแต่
    Windows ไม่ยอมโหลด profile** (ExecutionPolicy = Restricted ซึ่งเป็นค่าเริ่มต้น)
    ซึ่งมองจากภายนอกเหมือนกันเป๊ะ แต่แก้คนละวิธี
    """
    if os.name == "nt":
        env = dict(os.environ)
        env["PATH"] = os.pathsep.join(
            d for d in env.get("PATH", "").split(os.pathsep)
            if not ("eduone" in d.lower() and "plugins" in d.lower()))
        # ใช้ single quote ล้วนในฝั่ง PowerShell — double quote ในอาร์กิวเมนต์จะโดน
        # กฎ quoting ของ Windows แปลงจนเพี้ยน
        ps = ("$c = if (Get-Command eduone-py -ErrorAction SilentlyContinue) "
              "{ 'yes' } else { 'no' }; "
              "'cmd=' + $c + ' policy=' + (Get-ExecutionPolicy)")
        try:
            # ไม่ใส่ -NoProfile โดยตั้งใจ — ที่อยากรู้คือ "profile ตั้งให้แล้วหรือยัง"
            r = subprocess.run(["powershell", "-NoLogo", "-NonInteractive", "-Command", ps],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", env=env, timeout=60)
            for line in (r.stdout or "").splitlines():
                if line.startswith("cmd="):
                    return "cmd=yes" in line, line.split("policy=")[-1].strip()
        except Exception:
            pass
        return False, ""
    home = Path.home()
    found = any(f.is_file() and "eduone-py" in f.read_text(encoding="utf-8", errors="replace")
                for f in (home / ".zshrc", home / ".bashrc",
                          home / ".bash_profile", home / ".profile"))
    return found, ""


own_ok, own_policy = own_shell_knows_eduone_py()
if own_policy in ("Restricted", "AllSigned"):
    fix_own = (f"PowerShell ไม่ยอมโหลด profile เลย (ExecutionPolicy = {own_policy}) — "
               "แก้ด้วย  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned  "
               "(ไม่ต้องใช้สิทธิ์ผู้ดูแล) แล้วเปิดหน้าต่างใหม่")
elif os.name == "nt":
    fix_own = ("รันตัวช่วยติดตั้งซ้ำ (ข้อ 6/6 จะเพิ่มให้):  "
               "irm https://raw.githubusercontent.com/otyping/eduone-plugin/main/install.ps1 | iex")
else:
    fix_own = "เพิ่มฟังก์ชัน eduone-py ใน ~/.zshrc — ดูขั้นที่ 5 ใน README ของปลั๊กอิน"

need(own_ok,
     "เทอร์มินัลของคุณรู้จัก eduone-py แล้ว — รัน watch.py ระหว่างรองานได้",
     f"หน้าต่างเทอร์มินัลที่คุณเปิดเองยังไม่รู้จัก eduone-py (ใน Claude Code ใช้ได้อยู่แล้ว) · {fix_own}",
     fatal=False)

# ---------------------------------------------------------------- เชื่อมกับเว็บ
head("การเชื่อมกับเว็บ EDU ONE")
# ไม่ตั้งก็ผลิตสื่อได้ตามปกติ — แค่เว็บไม่รู้ว่างานเดินถึงไหน จึงเป็น WARN ไม่ใช่ FAIL
try:
    sys.path.insert(0, str(SHARED / "scripts"))
    import eduone_web as _web
    _cfg = _web.config()
except Exception as exc:                                  # noqa: BLE001
    _cfg, _web = None, None
    print(WARN + f"อ่านตัวเชื่อมเว็บไม่ได้: {exc}")

if _web is not None:
    if need(bool(_cfg),
            f"ตั้งค่าไว้แล้ว: {_cfg['url']}" if _cfg else "",
            "ยังไม่ได้ตั้งค่า — เว็บจะขึ้นว่า 'ยังไม่ได้เชื่อมเครื่อง' ตลอด และไฟล์ไม่ถูกส่งขึ้นใบสั่ง "
            f"· ตั้งด้วยตัวช่วยติดตั้ง (ข้อ 7/7) หรือเขียน {_web.CONFIG_FILE} เอง",
            fatal=False):
        try:
            _me = _web.get(_cfg, "/api/jobs/find", {"base": "__probe__"})
            print(OK + "เว็บตอบกลับแล้ว")
        except Exception as exc:                          # noqa: BLE001
            # 404 = โทเคนใช้ได้ แค่ไม่มีใบสั่งชื่อนี้ ซึ่งเป็นคำตอบที่ถูกต้องของการทดสอบ
            msg = str(exc)
            if "HTTP 404" in msg:
                print(OK + "โทเคนใช้ได้ (เว็บตอบว่าไม่มีใบสั่งทดสอบชื่อนี้ ซึ่งถูกแล้ว)")
            elif "HTTP 401" in msg or "HTTP 403" in msg:
                print(BAD + "โทเคนใช้ไม่ได้แล้ว — ออกใบใหม่ที่หน้า /me/tokens ของเว็บ")
            else:
                print(WARN + f"ต่อเว็บไม่ได้ตอนนี้: {msg}")

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

# ---------------------------------------------------------------- ตัวรับงาน
head("ตัวรับงาน (รับงานจากเว็บมาทำเอง)")
# ★ ด่านนี้ตอบคำถามที่พนักงานถามบ่อยที่สุด: "กดสั่งงานบนเว็บแล้วทำไมไม่มีอะไรเกิดขึ้น"
#   คำตอบเกือบทุกครั้งคือไม่มีตัวรับงานเปิดอยู่ — ซึ่งมองจากเว็บแยกไม่ออกจาก
#   "เครื่องปิดอยู่" เพราะทั้งสองกรณีเว็บเห็นเหมือนกันหมดคือเงียบ
_runner_py = PLUGIN_ROOT / "scripts" / "runner.py"
if need(_runner_py.is_file(),
        "มีตัวรับงานในปลั๊กอินแล้ว",
        "ปลั๊กอินเวอร์ชันนี้ยังไม่มีตัวรับงาน — อัปเดตก่อน: "
        "claude plugin marketplace update eduone && claude plugin update edu-one@eduone",
        fatal=False):
    import socket
    _s = socket.socket()
    _s.settimeout(0.5)
    try:
        # พอร์ต 47615 คือล็อกที่ตัวรับงานจองไว้ (ดู take_lock ใน runner.py)
        # ต่อติด = มีตัวเปิดอยู่จริง ไม่ใช่แค่มีไฟล์อยู่ในเครื่อง
        _s.connect(("127.0.0.1", 47615))
        print(OK + "เปิดอยู่ — กดสั่งงานจากเว็บได้เลย")
    except OSError:
        print(WARN + "ยังไม่ได้เปิด — เว็บจะขึ้นว่า 'รอเครื่องของคุณออนไลน์' ค้างไว้ตลอด")
        print("         เปิดเดี๋ยวนี้:  eduone-py runner.py   (cd เข้าโฟลเดอร์งานก่อน)")
        print("         ให้เปิดเองทุกครั้งที่เปิดเครื่อง: รันตัวช่วยติดตั้งซ้ำอีกหนึ่งรอบ")
    finally:
        _s.close()

# ---------------------------------------------------------------- สรุป
print()
if problems:
    print(f"ยังไม่พร้อม — ต้องแก้ {len(problems)} เรื่อง (ดูบรรทัด [แก้] ข้างบน)")
    sys.exit(1)
print("พร้อมใช้งาน — เปิด Claude Code ในโฟลเดอร์งานแล้วพิมพ์ /edu-one ได้เลย")
sys.exit(0)
