# -*- coding: utf-8 -*-
"""รายงานความคืบหน้าของคาบหนึ่งขึ้นเว็บ EDU ONE — และส่งไฟล์ต้นฉบับให้ด้วย

    eduone-py report.py m1 math 2          # คาบที่ระบุ
    eduone-py report.py --auto             # คาบที่ไฟล์ขยับล่าสุด (ใช้ใน hook)
    eduone-py report.py m1 math 2 -v       # บอกว่าทำอะไรบ้าง (ปกติเงียบสนิท)

★ ทำไมรายงาน "ไฟล์" ไม่ใช่ "ขั้นตอน"
  agent รายงานตัวเองได้แค่สิ่งที่มันคิดว่าทำแล้ว ซึ่งเชื่อไม่ได้เวลามันพลาด
  ไฟล์ในดิสก์เป็นหลักฐานที่ตรวจซ้ำได้ · ฝั่งเว็บมีตารางแปลงไฟล์เป็นขั้นตอนอยู่แล้ว
  (catalog._STEP_FILES) การตัดสินว่า "ขั้นไหนเสร็จ" จึงอยู่ที่เดียว ไม่ใช่สองที่

★ ห้ามทำให้งานหลักล้มเด็ดขาด — ทุกความผิดพลาดจบที่ exit 0 และเงียบ (เว้นแต่ใส่ -v)
  สคริปต์นี้ถูกเรียกจาก hook ระหว่างที่ pipeline กำลังทำงานอยู่
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
for extra in (HERE.parent / "skills" / "shared" / "scripts",):
    if extra.is_dir():
        sys.path.insert(0, str(extra))

import eduone_web as web       # noqa: E402
from _root import WORK_ROOT    # noqa: E402

#: ส่งขึ้นเว็บเฉพาะไฟล์ต้นฉบับ — .docx/.pptx/.mp3 สร้างใหม่จาก JSON ได้ เว็บปฏิเสธอยู่แล้ว
ARTIFACT_EXT = {".json", ".md", ".txt"}

#: ส่วนหนึ่งของชื่อไฟล์ -> ผลผลิตที่มันสังกัด (เรียงจากเจาะจงไปกว้าง)
#: ต้องตรงกับ catalog._LOCAL_FILES ของเว็บ — จับคู่ไม่ได้ = ไม่ส่งไฟล์นั้น
PRODUCT_OF = [
    ("_slides_", "slides"),
    ("_C1.", "content"), ("_C2.", "content"),
    ("_research.", "content"), ("_srcpack.", "content"),
    ("_L1.", "lesson_plan"), ("_L2.", "lesson_plan"),
    ("_ex.", "exercise"), ("_media-brief.", "exercise"), ("_urls.", "exercise"),
    ("_video.", "video"),
    ("_song.", "song"), ("_audio-src.", "song"),
    ("_game.", "game"),
]

#: ยิงถี่กว่านี้ไม่มีประโยชน์ — hook ทำงานทุกครั้งที่ agent เรียก tool ซึ่งถี่มาก
MIN_INTERVAL_SEC = 30


def log(on: bool, msg: str) -> None:
    if on:
        print(msg)


def product_of(name: str) -> str | None:
    for mark, product in PRODUCT_OF:
        if mark in name:
            return product
    return None


def topic_dir_of(grade: str, subject: str, no: int) -> Path | None:
    """โฟลเดอร์คาบจากหลักสูตร — ถามปลั๊กอิน ไม่ประกอบสตริงเอง"""
    try:
        import no_to_token as ntt
        import paths as pathmod
        meta = ntt.no_to_token(grade, subject, no)
        pp = pathmod.topic_paths(meta)
        # ไม่มีคีย์ "โฟลเดอร์คาบ" ตรง ๆ — ไต่ขึ้นสองชั้นจากไฟล์ C1 (<คาบ>/1. Content/<ไฟล์>)
        p = Path(pp["content_c1_json"]).parent.parent
        return p if p.is_absolute() else WORK_ROOT / p
    except Exception:
        return None


def newest_topic_dir() -> Path | None:
    """คาบที่ไฟล์ขยับล่าสุด — ใช้ตอน --auto ที่ไม่มีใครบอกว่ากำลังทำคาบไหนอยู่

    ดูจาก artifact ที่เพิ่งเขียน แล้วไต่ขึ้นสองชั้น (<คาบ>/<n. ผลผลิต>/<ไฟล์>)
    """
    root = WORK_ROOT / "Output"
    if not root.is_dir():
        return None
    newest, newest_at = None, 0.0
    for p in root.rglob("*.json"):
        try:
            m = p.stat().st_mtime
        except OSError:
            continue
        if m > newest_at:
            newest, newest_at = p, m
    return newest.parent.parent if newest is not None else None


def inventory(topic: Path) -> dict[str, dict]:
    """{ชื่อไฟล์: {size, mtime}} ของทุกไฟล์ในโฟลเดอร์คาบ

    รวมไฟล์ render ด้วย เพราะเว็บใช้ .docx/.pptx ตัดสินขั้น "สร้างไฟล์ส่งงาน"
    """
    out: dict[str, dict] = {}
    for p in topic.rglob("*"):
        if not p.is_file():
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        out[p.name] = {"size": st.st_size, "mtime": st.st_mtime}
    return out


def agent_heartbeat() -> float | None:
    """ชีพจรของ Claude Code — เวลาที่บันทึกสนทนาถูกเขียนล่าสุด"""
    try:
        sys.path.insert(0, str(HERE))
        import watch
        td = watch.transcript_dir()
        return watch.newest_mtime(td.glob("*.jsonl")) if td else None
    except Exception:
        return None


def state_file(base: str) -> Path:
    return WORK_ROOT / ".eduone-runs" / f"{base}.push.json"


def load_state(base: str) -> dict:
    f = state_file(base)
    if f.is_file():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    return {"at": 0, "uploaded": {}}


def save_state(base: str, st: dict) -> None:
    f = state_file(base)
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def run(topic: Path, verbose: bool, do_upload: bool, force: bool) -> int:
    base = topic.name
    # ★ ไม่มีโฟลเดอร์คาบอยู่จริง = ห้ามรายงาน ไม่ใช่ "รายงานว่าไม่มีไฟล์"
    #   รายงานว่างถูกเว็บอ่านว่า "ยังไม่ได้ทำอะไรเลย" แล้วทับความคืบหน้าจริงทิ้ง
    #   เกิดจริง 2026-09-03: watch.py ถูกรันจาก C:\Users\<ชื่อ> ซึ่งไม่ใช่โฟลเดอร์งาน
    #   จึงยิง "0 ไฟล์" ขึ้นใบสั่ง #2 ทุกครึ่งนาที ทั้งที่ไฟล์ครบแล้วในเครื่อง
    #   หน้าเว็บเลยค้างที่ 0/7 · main() เช็กก่อนเรียกอยู่แล้ว แต่ watch.py เรียก run()
    #   ตรง ๆ ไม่ผ่าน main() ด่านจึงต้องอยู่ตรงนี้ ที่ทางเข้าเดียวกันของทุกคนที่เรียก
    if not topic.is_dir():
        log(verbose, f"ไม่มีโฟลเดอร์ {topic} — ไม่รายงาน (รันอยู่ผิดโฟลเดอร์หรือเปล่า)")
        return 0
    cfg = web.config()
    if not cfg:
        log(verbose, "ยังไม่ได้ตั้งค่าที่อยู่เว็บกับโทเคน — ข้ามการรายงาน")
        log(verbose, f"  ตั้งที่ {web.CONFIG_FILE} หรือ EDUONE_WEB_URL / EDUONE_WEB_TOKEN")
        return 0

    st = load_state(base)
    if not force and (time.time() - float(st.get("at") or 0)) < MIN_INTERVAL_SEC:
        log(verbose, f"เพิ่งรายงานไปไม่ถึง {MIN_INTERVAL_SEC} วินาที — ข้ามรอบนี้")
        return 0

    try:
        job = web.find_job(cfg, base)
    except web.WebError as e:
        log(verbose, f"หาใบสั่งไม่สำเร็จ: {e}")
        return 0
    if not job:
        log(verbose, f"ยังไม่มีใบสั่งของ {base} บนเว็บ — ไม่มีที่ให้รายงาน")
        return 0

    files = inventory(topic)
    try:
        web.post_json(cfg, f"/api/jobs/{job['id']}/progress",
                      {"files": files, "agent_at": agent_heartbeat()})
        log(verbose, f"รายงานแล้ว: ใบสั่ง #{job['id']} · {len(files)} ไฟล์")
    except web.WebError as e:
        log(verbose, f"รายงานไม่สำเร็จ: {e}")
        return 0

    st["at"] = time.time()
    if do_upload:
        sent = st.get("uploaded") or {}
        for p in sorted(topic.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in ARTIFACT_EXT:
                continue
            product = product_of(p.name)
            if product is None or product not in job.get("products", []):
                continue
            mtime = p.stat().st_mtime
            if abs(float(sent.get(p.name) or 0) - mtime) < 1:
                continue        # ส่งไปแล้วและยังไม่ถูกแก้
            try:
                web.post_file(cfg, f"/api/jobs/{job['id']}/files", {"product": product}, p)
                sent[p.name] = mtime
                log(verbose, f"  ส่งขึ้นเว็บแล้ว: {p.name} ({product})")
            except web.WebError as e:
                log(verbose, f"  ส่ง {p.name} ไม่สำเร็จ: {e}")
        st["uploaded"] = sent
    save_state(base, st)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="รายงานความคืบหน้าขึ้นเว็บ EDU ONE")
    ap.add_argument("grade", nargs="?")
    ap.add_argument("subject", nargs="?")
    ap.add_argument("no", nargs="?", type=int)
    ap.add_argument("--auto", action="store_true", help="เดาคาบจากไฟล์ที่ขยับล่าสุด")
    ap.add_argument("--no-upload", action="store_true", help="รายงานสถานะอย่างเดียว")
    ap.add_argument("--force", action="store_true", help="ไม่สนใจการเว้นช่วง 30 วินาที")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()

    if a.auto or not (a.grade and a.subject and a.no):
        topic = newest_topic_dir()
    else:
        topic = topic_dir_of(a.grade, a.subject, a.no)
    if topic is None or not topic.is_dir():
        log(a.verbose, "หาโฟลเดอร์ของคาบไม่เจอ — ยังไม่มีไฟล์ผลผลิตเลยหรือเปล่า")
        return 0
    return run(topic, a.verbose, not a.no_upload, a.force)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:                      # noqa: BLE001
        # hook เรียกตัวนี้ระหว่าง pipeline ทำงานอยู่ — ล้มที่นี่ต้องไม่ลามไปหยุดงานหลัก
        if os.environ.get("EDUONE_REPORT_DEBUG"):
            raise
        print(f"report.py: ข้ามการรายงานเพราะ {exc}", file=sys.stderr)
        raise SystemExit(0)
