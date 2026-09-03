# -*- coding: utf-8 -*-
"""ติดตามงานที่กำลังทำอยู่บนเครื่องตัวเอง — ตอบคำถาม "ค้างหรือเปล่า"

    eduone-py watch.py m1 math 9          # เฝ้าดู ปรับหน้าจอทุก 2 วินาที
    eduone-py watch.py m1 math 9 --json   # พิมพ์สถานะครั้งเดียวเป็น JSON

★ ทำไมต้องมีทั้งที่ Claude Code ก็พิมพ์ออกหน้าจออยู่แล้ว
  ระหว่างที่ agent คิดหรือรัน tool ยาว ๆ หน้าจอจะนิ่งเป็นสิบนาที คนดูแยกไม่ออกว่า
  "กำลังคิด" กับ "ค้างไปแล้ว" — หน้านี้ตอบด้วยหลักฐาน 2 ชั้นที่วัดได้จริง

    ชั้นที่ 1  บันทึกสนทนาของ Claude Code (~/.claude/projects/<โฟลเดอร์งาน>/*.jsonl)
               ขยับทุกครั้งที่ agent พูดหรือเรียก tool — นี่คือชีพจรตัวจริง
               เงียบเกิน 5 นาที = ผิดปกติ เพราะ agent เขียนอะไรบางอย่างตลอดเวลา
    ชั้นที่ 2  ไฟล์ผลผลิตใน Output/ — บอกว่าคืบหน้าไปถึงไหนแล้ว
               ชั้นนี้เงียบนานได้ตามปกติ (เขียน C1 ทีเดียวใช้เวลา 15-20 นาที)
               จึงใช้ดู "ทำถึงไหน" ไม่ใช่ "ตายหรือยัง"

  สองชั้นนี้ตอบคนละคำถาม ถ้าดูแค่ไฟล์ผลผลิตจะเตือนผิดตลอดตอน agent กำลังเขียนยาว ๆ

รันในหน้าต่างเทอร์มินัลที่สอง — หน้าต่างแรกให้ Claude Code ใช้ตามปกติ
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
for extra in (HERE.parent / "skills" / "shared" / "scripts",):
    if extra.is_dir():
        sys.path.insert(0, str(extra))

from _root import WORK_ROOT  # noqa: E402
import no_to_token as ntt    # noqa: E402
import paths as pathmod      # noqa: E402

POLL_SEC = 2
#: บันทึกสนทนาเงียบเกินเท่านี้ = น่าสงสัย / น่าจะค้าง
QUIET_WARN, QUIET_BAD = 5 * 60, 15 * 60

C = {"dim": "\033[2m", "red": "\033[31m", "grn": "\033[32m", "yel": "\033[33m",
     "blu": "\033[36m", "b": "\033[1m", "0": "\033[0m"}


def enable_ansi() -> bool:
    """เปิดโหมดสีของ console บน Windows — คอนโซลรุ่นเก่าไม่เปิดให้เอง"""
    if not sys.stdout.isatty():
        return False
    if os.name != "nt":
        return True
    try:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not k.GetConsoleMode(h, ctypes.byref(mode)):
            return False
        return bool(k.SetConsoleMode(h, mode.value | 0x0004))  # VIRTUAL_TERMINAL
    except Exception:
        return False


COLOR = enable_ansi()


def c(name: str, text: str) -> str:
    return f"{C[name]}{text}{C['0']}" if COLOR else text


def ago(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    s = int(seconds)
    if s < 60:
        return f"{s} วินาที"
    if s < 3600:
        return f"{s // 60} นาที {s % 60} วินาที"
    if s < 86400:
        return f"{s // 3600} ชม. {(s % 3600) // 60} นาที"
    # เกินหนึ่งวันแล้วบอกเป็นชั่วโมงต่อไปจะได้เลขสามหลักที่อ่านไม่ออก (268 ชม.)
    return f"{s // 86400} วัน {(s % 86400) // 3600} ชม."


def width(text: str) -> int:
    """ความกว้างจริงบนจอ — สระบนล่างและวรรณยุกต์ไทยเป็นอักขระประกอบ (Mn)
    ที่ซ้อนบนตัวก่อนหน้า ไม่กินที่ ถ้านับด้วย len() คอลัมน์ไทยจะเหลื่อมทุกบรรทัด

    ★ ต้องดูที่ category == 'Mn' ไม่ใช่ combining() != 0
      สระไทยหลายตัว (เช่น ั ิ ื) เป็น Mn แต่มี canonical combining class = 0
      ใช้ combining() จะนับเกิน เช่น "ใบสั่งผลิตสื่อ" ได้ 12 ทั้งที่กว้างจริง 9
    """
    return sum(0 if unicodedata.category(ch) == "Mn" else 1 for ch in text)


def pad(text: str, n: int) -> str:
    return text + " " * max(0, n - width(text))


def size_of(p: Path) -> str:
    n = p.stat().st_size
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n / 1048576:.1f} MB"


def transcript_dir() -> Path | None:
    """โฟลเดอร์บันทึกสนทนาของ Claude Code สำหรับโฟลเดอร์งานนี้

    Claude Code แปลง path เป็นชื่อโฟลเดอร์โดยแทนตัวคั่นด้วย '-'
    ตัวพิมพ์เล็ก/ใหญ่ของอักษรไดรฟ์ไม่คงที่ จึงเทียบแบบไม่สนตัวพิมพ์
    """
    root = Path.home() / ".claude" / "projects"
    if not root.is_dir():
        return None
    want = str(WORK_ROOT).replace("\\", "-").replace("/", "-").replace(":", "-")
    want = want.replace("--", "-").lower()
    for d in root.iterdir():
        if d.is_dir() and d.name.replace("--", "-").lower() == want:
            return d
    return None


def newest_mtime(paths) -> float | None:
    best = None
    for p in paths:
        try:
            m = p.stat().st_mtime
        except OSError:
            continue
        if best is None or m > best:
            best = m
    return best


#: ผลผลิต -> ไฟล์ที่ต้องมี  (คีย์ตรงกับที่ paths.py คืนมา)
WANT = {
    "เนื้อหา": [("C1 (json)", "content_c1_json"), ("C1 (docx)", "content_c1_docx"),
                ("C2 (json)", "content_c2_json"), ("C2 (docx)", "content_c2_docx"),
                ("แหล่งอ้างอิง", "content_research_md"), ("srcpack", "content_srcpack_md")],
    "แผนการสอน": [("L1 (json)", "plan_l1_json"), ("L1 (docx)", "plan_l1_docx"),
                  ("L2 (json)", "plan_l2_json"), ("L2 (docx)", "plan_l2_docx")],
    "แบบฝึกหัด": [("ข้อสอบ (json)", "ex_json"), ("ข้อสอบ (docx)", "exercise_docx"),
                  ("ใบสั่งผลิตสื่อ", "ex_brief_md")],
    "เพลง": [("เนื้อเพลง (json)", "song_json"), ("mp3", "song_mp3")],
    "วิดีโอ": [("สตอรีบอร์ด (json)", "video_json"), ("mp4", "video_mp4")],
    "เกม": [("คลังคำถาม (json)", "game_json")],
}


def scan(meta: dict, pp: dict) -> dict:
    """อ่านสถานะไฟล์ทั้งหมดของงานนี้ทีเดียว"""
    groups, files = [], []
    for label, items in WANT.items():
        rows = []
        for name, key in items:
            p = WORK_ROOT / pp[key] if not os.path.isabs(pp[key]) else Path(pp[key])
            ok = p.is_file()
            rows.append({"name": name, "path": str(p), "exists": ok,
                         "size": size_of(p) if ok else None,
                         "mtime": p.stat().st_mtime if ok else None})
            if ok:
                files.append(p)
        groups.append({"label": label, "rows": rows})
    # สไลด์ 4 ชุดวนแยก เพราะ paths.py คืนเป็น dict ต่อแหล่ง
    rows = []
    for src in ("C1", "C2", "L1", "L2"):
        for kind, d in (("json", pp["slides_json"]), ("pptx", pp["slides_pptx"])):
            p = WORK_ROOT / d[src] if not os.path.isabs(d[src]) else Path(d[src])
            ok = p.is_file()
            rows.append({"name": f"{src} ({kind})", "path": str(p), "exists": ok,
                         "size": size_of(p) if ok else None,
                         "mtime": p.stat().st_mtime if ok else None})
            if ok:
                files.append(p)
    groups.insert(4, {"label": "สไลด์", "rows": rows})

    td = transcript_dir()
    return {
        "base": meta["base"],
        "groups": groups,
        "files_mtime": newest_mtime(files),
        "agent_mtime": newest_mtime(td.glob("*.jsonl")) if td else None,
        "transcript_dir": str(td) if td else None,
    }


def health(agent_age: float | None) -> tuple[str, str]:
    """แปลอายุของบันทึกสนทนาเป็นสถานะที่คนอ่านเข้าใจ"""
    if agent_age is None:
        return "off", "ยังไม่เจอบันทึกของ Claude Code — เปิดงานในโฟลเดอร์นี้หรือยัง"
    if agent_age < QUIET_WARN:
        return "ok", f"Claude Code ทำงานอยู่ — เห็นล่าสุด {ago(agent_age)}ที่แล้ว"
    if agent_age < QUIET_BAD:
        return "warn", (f"เงียบมา {ago(agent_age)} — ปกติ agent เขียนอะไรบางอย่างตลอด "
                        "ลองดูหน้าต่าง Claude Code ว่ารออะไรอยู่หรือเปล่า")
    return "bad", (f"เงียบมา {ago(agent_age)} — น่าจะค้างหรือรอให้ตอบคำถามอยู่ "
                   "ไปดูหน้าต่าง Claude Code")


def render(st: dict, meta: dict, started: float) -> str:
    now = time.time()
    out = []
    out.append(c("b", "  AI Buddy — ติดตามงานบนเครื่องนี้"))
    out.append("  " + c("blu", st["base"]) + "   " + c("dim", meta["header"]))
    out.append("")

    kind, msg = health(now - st["agent_mtime"] if st["agent_mtime"] else None)
    dot = {"ok": c("grn", "●"), "warn": c("yel", "●"), "bad": c("red", "●"),
           "off": c("dim", "○")}[kind]
    out.append(f"  {dot} {msg}")

    fa = now - st["files_mtime"] if st["files_mtime"] else None
    out.append("  " + c("dim", f"  ไฟล์ผลผลิตเปลี่ยนล่าสุด {ago(fa)}ที่แล้ว"
                               if fa is not None else "  ยังไม่มีไฟล์ผลผลิตสักไฟล์"))
    out.append("  " + c("dim", f"  เฝ้าดูมาแล้ว {ago(now - started)}  ·  "
                               f"อัปเดตทุก {POLL_SEC} วินาที  ·  กด Ctrl+C เพื่อออก"))
    out.append("")

    for g in st["groups"]:
        done = sum(1 for r in g["rows"] if r["exists"])
        total = len(g["rows"])
        bar = "█" * done + "░" * (total - done)
        head = c("grn", bar) if done == total else (c("yel", bar) if done else c("dim", bar))
        out.append(f"  {pad(g['label'], 12)} {head}  {done}/{total}")
        for r in g["rows"]:
            if r["exists"]:
                age = ago(now - r["mtime"])
                out.append("     " + c("grn", "✓") + " " + pad(r["name"], 19)
                           + c("dim", f"{r['size']:>8}   {age}ที่แล้ว"))
            else:
                out.append("     " + c("dim", f"· {r['name']}"))
        out.append("")
    return "\n".join(out)


def push(topic) -> None:
    """ส่งสถานะเดียวกันนี้ขึ้นเว็บด้วย — เงียบ และห้ามล้มเด็ดขาด

    หน้าจอเฝ้าดูต้องไม่ดับเพราะเน็ตมีปัญหาหรือเว็บล่ม · report.py เว้นช่วงเองอยู่แล้ว
    (30 วินาที) จึงเรียกทุกรอบได้โดยไม่กลายเป็นการยิงถี่
    """
    if topic is None:
        return
    try:
        import report
        report.run(topic, verbose=False, do_upload=True, force=False)
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description="ติดตามงานที่กำลังทำบนเครื่องนี้")
    ap.add_argument("grade")
    ap.add_argument("subject")
    ap.add_argument("no", type=int)
    ap.add_argument("--json", action="store_true", help="พิมพ์สถานะครั้งเดียวเป็น JSON")
    ap.add_argument("--no-push", action="store_true",
                    help="ไม่ต้องส่งสถานะขึ้นเว็บ (ปกติส่งให้เองถ้าตั้งค่าเว็บไว้แล้ว)")
    a = ap.parse_args()

    meta = ntt.no_to_token(a.grade, a.subject, a.no)
    pp = pathmod.topic_paths(meta)

    if a.json:
        print(json.dumps(scan(meta, pp), ensure_ascii=False, indent=2))
        return 0

    topic = None
    if not a.no_push:
        try:
            import report
            topic = report.topic_dir_of(a.grade, a.subject, a.no)
        except Exception:
            topic = None

    started = time.time()
    try:
        while True:
            frame = render(scan(meta, pp), meta, started)
            # เขียนทั้งเฟรมทีเดียว ไม่ล้างจอก่อน — ล้างแล้วเขียนทำให้จอกะพริบ
            sys.stdout.write(("\033[H\033[J" if COLOR else "\n" * 3) + frame + "\n")
            sys.stdout.flush()
            push(topic)
            time.sleep(POLL_SEC)
    except KeyboardInterrupt:
        print("\n  หยุดเฝ้าดูแล้ว — งานที่รันอยู่ไม่ได้ถูกหยุดไปด้วย\n")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
