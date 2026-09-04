#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ถอดสารบัญของเล่มที่สแกนมา -> bookscan_index.json (คิวข้อ 1 ของ next-steps.md)

    eduone-py toc_extract.py plan   m1-math-teacher1        # ดึงภาพ + สั่งงาน sub-agent
    eduone-py toc_extract.py file   <staging>.json          # ตรวจ + คำนวณ offsets + เขียนเข้า index
    eduone-py toc_extract.py status [m1-math-teacher1]      # เล่มไหนมีสารบัญแล้ว/ยัง

★ ตั้งแต่ 3.4.0 สคริปต์นี้อยู่ในปลั๊กอิน ไม่ใช่ใน repo งาน — ทุกเครื่องที่ติดตั้งปลั๊กอินถอดได้
  (เดิมอยู่ที่ `docs/rag/` ของ repo EDUONE-MCP-RAG มีเครื่องเดียวในทีมที่ถอดได้)
  path ของคลัง (`BookScan/`, `.cache/rag/`) อิง **โฟลเดอร์งาน** เสมอ ไม่ใช่ที่อยู่สคริปต์

ทำไมถึงคุ้มกว่าถอดทั้งเล่ม: วัดแล้วชั้นสารบัญให้ R@5 = 1.00 ที่ต้นทุนราว 2% ของการถอดทั้งเล่ม
(ดู next-steps.md ข้อ 3) เล่มที่เพิ่งสแกนเสร็จจึงควรได้สารบัญทันที ส่วนเนื้อในค่อยถอดเมื่อมีคนใช้

★ สคริปต์นี้ **ไม่อ่านภาพเอง** — เตรียมภาพ + พิมพ์คำสั่งให้ sub-agent ไปอ่าน แล้วรับผลกลับมาตรวจ
  ตามกฎทองใน CLAUDE.md (ภาพหน้าหนังสือห้ามค้างใน context ของ orchestrator)

★ แบ่งงานตามกฎ RAG-PLAN 8.3 "อะไรที่ deterministic ได้ ให้สคริปต์ทำ":

    สคริปต์คำนวณเอง  subject · grade · book.id/file/title/pages · **offsets** · partial
                     · scannedPrinted · scanned ของทุกบรรทัด · schema_version · extracted_at
    agent ต้องตอบ    tocPdfPages · chapters · extras · probes[].printed_seen · confidence · flags

  ★ offsets มาจาก probe เท่านั้น — คือหน้าที่ agent เปิดดูแล้วอ่านเลขที่พิมพ์บนกระดาษจริง
    ไม่ใช่ค่าที่ใครเดา · จุดสอบเทียบผิด 1 หน้า = ทุกงานที่อ้างเล่มนี้หยิบหน้าผิดทั้งหมด

ยังไม่ต่อเซิร์ฟเวอร์ในรอบนี้ — คิวข้อ 3 จะเพิ่ม `queue`/`pull` และการ PUT ขึ้นเว็บ
จุดที่ต้องแก้ตอนนั้นคือ resolve_book() (หา PDF จาก MinIO แทนในเครื่อง) กับท้าย cmd_file()
"""

import argparse
import copy
import datetime
import glob
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _root import WORK_ROOT          # noqa: E402  โฟลเดอร์งานของเครื่องนี้ (env -> ไฟล์ตั้งค่า -> cwd)
import eduone_api as ea              # noqa: E402  ตัวเชื่อมเว็บชุดเดียวของงานคลังหนังสือ
import ocr_page as op                # noqa: E402  ใช้ตัวช่วยร่วมกัน
import toc_schema as ts              # noqa: E402  กฎการตรวจชุดเดียวกับเซิร์ฟเวอร์

# ★ ทุก path ด้านล่างอิง "โฟลเดอร์งาน" ไม่ใช่ที่อยู่ของสคริปต์ — สคริปต์อยู่ในปลั๊กอิน
#   ที่อัปเดตทับทิ้งได้ทุกเมื่อ ส่วนคลังหนังสือกับของค้างเป็นของผู้ใช้ ห้ามหายตอนอัปเดต
BOOKSCAN = os.path.join(WORK_ROOT, "BookScan")
CACHE = os.path.join(WORK_ROOT, ".cache", "rag")
IMG_DIR = os.path.join(CACHE, "toc-img")
STAGING = os.path.join(CACHE, "toc-staging")

FRONT_PAGES = 16          # หน้าต้นเล่มที่เรนเดอร์ไว้ให้ agent หาหน้าสารบัญ
FRONT_WIDTH = 1200        # สารบัญบรรทัดถี่ ต้องใหญ่พอให้อ่านเลขหน้าออก
PROBE_WIDTH = 900         # probe ต้องการแค่เลขมุมหน้า ไม่ต้องคมเท่าสารบัญ


def load_json(path):
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


def rel(path):
    return os.path.relpath(path, WORK_ROOT).replace("\\", "/")


# ── คุยกับเซิร์ฟเวอร์ ────────────────────────────────────────────────────────
# ตัวเชื่อมอยู่ที่ eduone_api.py (ใช้ร่วมกับ ocr_page.py) — ที่นี่ตั้งแค่ข้อความ
# "ต่อไม่ได้แล้วทำอะไรต่อ" ของสคริปต์นี้เอง

#: ตั้งใน main() ไม่ใช่ตอน import — ocr_page.py ก็ตั้งค่านี้เหมือนกัน
#: ใครถูก import ทีหลังจะทับของอีกฝั่ง ถ้าตั้งตอน import
OFFLINE_HINT = ("ทำงานในเครื่องต่อได้ด้วย --local "
                "แล้วค่อยส่งขึ้นเว็บทีหลังด้วย toc_extract.py push <book_id>")

api = ea.api
download = ea.download
server = ea.server


# ── หาเล่ม ──────────────────────────────────────────────────────────────────

def ensure_book(book_id, pdf_hint=None, use_server=True):
    """หาไฟล์ PDF ของเล่มนี้ให้ได้ — ในเครื่องก่อน ไม่มีค่อยจองแล้วโหลดจากเว็บ

    จองก่อนโหลดเสมอเมื่อทำงานกับเว็บ: การถอดซ้ำเล่มเดียวกันสองเครื่องคือเงินที่จ่ายทิ้ง
    (next-steps.md ข้อ 1 ของการตัดสินใจที่เปลี่ยน)
    """
    info = resolve_book(book_id, pdf_hint, missing_ok=True)
    if info and info["pdf"]:
        if use_server and server():
            status, res = api("/api/books/%s/toc/claim" % book_id)
            if status == 200:
                print("จองเล่มนี้บนเว็บแล้ว")
            elif status == 409 and "ไม่พบเล่มนี้" in str(res.get("reason", "")):
                print("หมายเหตุ: เว็บยังไม่มีเล่มนี้ในทะเบียน — ถอดในเครื่องต่อได้ แต่ push ขึ้นเว็บไม่ได้")
            else:
                raise SystemExit("จองเล่มไม่ได้: %s" % (res.get("reason") or res))
        return info

    if not (use_server and server()):
        raise SystemExit("ไม่พบไฟล์ PDF ของเล่ม %s ในเครื่อง — ระบุเองด้วย --pdf <path> "
                         "หรือตั้ง EDUONE_URL เพื่อโหลดจากเว็บ" % book_id)

    status, res = api("/api/books/%s/toc/claim" % book_id)
    if status != 200:
        raise SystemExit("จองเล่มไม่ได้ (%s): %s" % (status, res.get("reason") or res))

    parts = book_id.split("-")
    folder = os.path.join(BOOKSCAN, ts.folder_of_subject(ts.subject_of_folder(parts[1])),
                          ts.folder_of_grade(parts[0]))
    dest = os.path.join(folder, "%s.pdf" % book_id)
    print("โหลด PDF จากเว็บ -> %s" % rel(dest))
    download(res["download_url"], dest)

    info = resolve_book(book_id, dest, missing_ok=True)
    if info and not info["pdf"]:
        info["pdf"] = dest
        info["book"]["file"] = os.path.basename(dest)
    return info


def resolve_book(book_id, pdf_hint=None, missing_ok=False):
    """book_id -> ทุกอย่างที่ต้องใช้ทำงานกับเล่มนี้

    รับได้ทั้งเล่มที่มีอยู่ใน index แล้ว (teacher1 ของ ม.1 ที่ยังไม่ได้ถอดสารบัญ)
    และเล่มที่ยังไม่มีบรรทัดใน index เลย (PDF ที่เพิ่งวางลงโฟลเดอร์ / ดาวน์โหลดจากเว็บ)
    """
    for idx_path in sorted(glob.glob(os.path.join(BOOKSCAN, "*", "*", "bookscan_index.json"))):
        idx = load_json(idx_path)
        subject, grade = idx.get("subject", ""), idx.get("grade", "")
        for book in idx.get("books", []):
            if ts.book_id_of(subject, grade, book.get("id", "")) == book_id:
                folder = os.path.dirname(idx_path)
                pdf = os.path.join(folder, book.get("file", ""))
                return {"index_path": idx_path, "dir": folder, "subject": subject,
                        "grade": grade, "book": book, "book_id": book_id,
                        "pdf": pdf if os.path.isfile(pdf) else None, "in_index": True}

    # ยังไม่มีใน index — เดาโฟลเดอร์จาก book_id แล้วหา PDF ในนั้น
    parts = book_id.split("-")
    if len(parts) != 3:
        raise SystemExit("book_id ต้องอยู่ในรูป <ชั้น>-<วิชา>-<เล่ม> เช่น m1-math-teacher1 (ได้ %r)" % book_id)
    grade = ts.folder_of_grade(parts[0])
    subject = ts.folder_of_subject(ts.subject_of_folder(parts[1]))
    folder = os.path.join(BOOKSCAN, subject, grade)
    pdf = pdf_hint if pdf_hint else None
    if pdf and not os.path.isabs(pdf):
        pdf = os.path.join(WORK_ROOT, pdf)
    if pdf and not os.path.isfile(pdf):
        raise SystemExit("ไม่พบไฟล์ %s" % pdf)
    if not pdf:
        named = os.path.join(folder, "%s.pdf" % book_id)     # ชื่อที่ดาวน์โหลดจากเว็บใช้
        cands = [named] if os.path.isfile(named) else sorted(glob.glob(os.path.join(folder, "*.pdf")))
        if len(cands) != 1:
            if missing_ok:
                return None
            raise SystemExit(
                "เล่ม %s ยังไม่มีใน bookscan_index.json และเดาไฟล์ไม่ได้ (เจอ %d ไฟล์ใน %s)\n"
                "ระบุเอง: toc_extract.py plan %s --pdf <path ของ PDF>"
                % (book_id, len(cands), rel(folder), book_id))
        pdf = cands[0]
    return {"index_path": os.path.join(folder, "bookscan_index.json"), "dir": folder,
            "subject": subject, "grade": grade, "book_id": book_id, "pdf": pdf,
            "in_index": False,
            "book": {"id": parts[2], "file": os.path.basename(pdf),
                     "title": os.path.splitext(os.path.basename(pdf))[0],
                     "role": "teacher" if parts[2].startswith("teacher") else "student"}}


def page_count(pdf_path):
    import fitz
    doc = fitz.open(pdf_path)
    try:
        return doc.page_count
    finally:
        doc.close()


# ── queue / pull / push (ต้องมีเซิร์ฟเวอร์) ─────────────────────────────────

def cmd_queue(limit):
    status, data = api("/api/toc/queue?limit=%d" % limit)
    if status != 200:
        raise SystemExit("ขอคิวไม่สำเร็จ (%s): %s" % (status, data.get("detail") or data))
    books = data.get("books") or []
    if not books:
        print("ไม่มีเล่มรอถอดสารบัญ")
        return 0
    print("เล่มที่รอถอดสารบัญ %d เล่ม (จองแล้วต้องส่งผลภายใน %s ชม. ไม่งั้นกลับเข้าคิว)\n"
          % (len(books), data.get("lease_hours")))
    print("%-22s %-10s %-34s %s" % ("book_id", "สถานะ", "ชื่อหนังสือ", "คนที่จองอยู่"))
    for b in books:
        print("%-22s %-10s %-34s %s" % (b["book_id"], b["toc_status"],
                                        (b.get("title") or "—")[:34], b.get("claimer") or "—"))
    print("\nเริ่มถอด: eduone-py toc_extract.py plan <book_id>")
    return 0


def cmd_push(book_id, model, dry_run):
    """ส่งสารบัญที่ถอดไว้แล้วขึ้นเว็บ — ใช้ตอนตอนถอดเน็ตล่ม หรือถอดแบบ --local ไว้ก่อน"""
    stage_path = os.path.join(STAGING, "%s.json" % book_id)
    if not os.path.isfile(stage_path):
        raise SystemExit("ไม่พบ %s — ยังไม่ได้ถอดเล่มนี้ในเครื่องนี้" % rel(stage_path))
    info = resolve_book(book_id)
    data = build_extraction(info, load_json(stage_path), page_count(info["pdf"]), model)
    problems = ts.check_extraction(data)
    if ts.has_error(problems):
        for p in problems:
            print("      %s" % p)
        raise SystemExit("สารบัญไม่ผ่านการตรวจ — ยังไม่ส่งขึ้นเว็บ")
    if dry_run:
        print("dry-run: จะส่ง %s ขึ้น %s" % (book_id, server()))
        return 0
    return push_result(book_id, data)


def push_result(book_id, data):
    status, body = api("/api/books/%s/toc" % book_id, method="PUT", payload=data)
    if status in (200, 201):
        print("ส่งขึ้นเว็บแล้ว: %s (%s บท %s หัวข้อ)"
              % (book_id, body.get("chapters"), body.get("sections")))
        return 0
    if status == 422:
        print("เซิร์ฟเวอร์ปฏิเสธ — สารบัญไม่ผ่านการตรวจฝั่งเซิร์ฟเวอร์:")
        for p in body.get("problems") or []:
            print("      %(level)s %(where)s: %(msg)s" % p)
    else:
        print("ส่งไม่สำเร็จ (%s): %s" % (status, body.get("reason") or body.get("detail") or body))
    print("แก้แล้วส่งซ้ำได้ด้วย: eduone-py toc_extract.py push %s" % book_id)
    return 1


def cmd_pull(grade_slug, subject_slug, dry_run):
    """ดึงสารบัญจากเว็บมาเขียนเป็น bookscan_index.json ในเครื่อง

    merge ทีละเล่ม ไม่เขียนทับทั้งไฟล์ — เล่มที่ถอดด้วยมือไว้ก่อนมีเซิร์ฟเวอร์ (เช่น
    วิทย์ ป.4) ยังไม่มีในทะเบียนเว็บ ถ้าเขียนทับทั้งไฟล์จะหายไปทั้งชุด
    """
    status, data = api("/api/toc/export?grade=%s&subject=%s" % (grade_slug, subject_slug))
    if status != 200:
        raise SystemExit("ดึงสารบัญไม่สำเร็จ (%s): %s" % (status, data.get("detail") or data))

    problems = ts.check_index(data)
    if ts.has_error(problems):
        for p in problems:
            print("      %s" % p)
        raise SystemExit("สารบัญที่ได้จากเว็บไม่ผ่านการตรวจ — ไม่เขียนลงเครื่อง")

    folder = os.path.join(BOOKSCAN, data["subject"], data["grade"])
    index_path = os.path.join(folder, "bookscan_index.json")
    incoming = {b.get("id"): b for b in data.get("books") or []}
    if not incoming:
        print("เว็บยังไม่มีสารบัญของ %s %s" % (data["grade"], data["subject"]))
        return 0

    local = load_json(index_path) if os.path.isfile(index_path) else dict(data, books=[])
    books = local.setdefault("books", [])
    added, updated = [], []
    for i, book in enumerate(books):
        new = incoming.pop(book.get("id"), None)
        if new is None:
            continue
        if json.dumps(book, sort_keys=True, ensure_ascii=False) != json.dumps(new, sort_keys=True, ensure_ascii=False):
            merged = dict(book)
            merged.update(new)
            books[i] = merged
            updated.append(book.get("id"))
    for book_id, book in incoming.items():
        books.append(book)
        added.append(book_id)
    books.sort(key=lambda b: b.get("id", ""))

    if not added and not updated:
        print("สารบัญในเครื่องตรงกับเว็บอยู่แล้ว (%s)" % rel(index_path))
        return 0
    if dry_run:
        print("dry-run: จะเพิ่ม %s · อัปเดต %s" % (added or "—", updated or "—"))
        return 0

    os.makedirs(folder, exist_ok=True)
    tmp = index_path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as fh:
        json.dump(local, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, index_path)
    print("เขียน %s — เพิ่ม %s · อัปเดต %s"
          % (rel(index_path), ", ".join(added) or "—", ", ".join(updated) or "—"))
    print("ต่อไป: python docs/rag/bm25_index.py build --fields all")
    return 0


# ── plan ────────────────────────────────────────────────────────────────────

def probe_pages(total, front, extra=False):
    """หน้า PDF ที่จะให้ agent เปิดดูเพื่ออ่าน 'เลขที่พิมพ์บนกระดาษ'

    เลือกแบบตายตัวจากจำนวนหน้า ไม่ขึ้นกับสิ่งที่ agent อ่านได้จากสารบัญ —
    ทำแบบนี้จึงจบใน sub-agent ครั้งเดียว ไม่ต้องคุยกลับไปกลับมา (ค่า cache write
    เป็นค่าใช้จ่ายก้อนใหญ่ที่สุดและจ่ายครั้งเดียวต่อ agent ดู eval-run-003.md ข้อ 5)

    ต้นเล่มกับท้ายเล่มอยู่ในชุดเสมอ เพราะสองจุดนี้คือขอบของช่วงที่สแกนมาจริง
    ส่วนจุดกลางมีไว้จับ 'หน้าแทรกกลางเล่ม' ที่ทำให้ offset ไม่คงที่ (เจอจริงในเล่ม 1 ของ ม.1)
    """
    first = min(front + 1, total)
    # ★ เอาจุดเยอะไว้ตั้งแต่รอบแรก — วัดจริงแล้วค่าใช้จ่ายเกาะอยู่กับ 'จำนวนครั้งที่เรียก agent'
    #   ไม่ใช่จำนวนภาพ: ถอดสารบัญ + 10 ภาพ = $1.06 · เรียกเพิ่มอีกรอบเพื่อดู 5 ภาพ = $0.93
    #   ภาพเพิ่มอีก 6 ใบในรอบเดิมถูกกว่าการเรียกรอบสองมาก และช่วยให้เจอ 'หน้าแทรก' ตั้งแต่รอบแรก
    fracs = [i / 16.0 for i in range(1, 16)] if extra else [i / 8.0 for i in range(1, 8)]
    pages = {first, total}
    for f in fracs:
        pages.add(max(first, min(total, int(round(total * f)))))
    return sorted(pages)


def cmd_plan(book_id, pdf_hint, front, extra_probes, width, local):
    info = ensure_book(book_id, pdf_hint, use_server=not local)
    if not info or not info["pdf"]:
        raise SystemExit("ไม่พบไฟล์ PDF ของเล่ม %s ในเครื่อง" % book_id)
    total = page_count(info["pdf"])
    front = max(1, min(front, max(1, total - 2)))     # ต้องเหลือหน้าไว้ทำ probe เสมอ
    probes = probe_pages(total, front, extra_probes)

    have = info["book"].get("chapters") or []
    if have:
        print("⚠ เล่มนี้มีสารบัญใน index อยู่แล้ว %d บท — ถอดใหม่จะเขียนทับ" % len(have))

    img_out = os.path.join(IMG_DIR, book_id)
    os.makedirs(img_out, exist_ok=True)
    os.makedirs(STAGING, exist_ok=True)
    stage_path = os.path.join(STAGING, "%s.json" % book_id)

    front_imgs = render(info, range(1, front + 1), FRONT_WIDTH if width is None else width, img_out)
    probe_imgs = render(info, probes, PROBE_WIDTH if width is None else width, img_out)

    print("\nเล่ม %s · %s %s · %s · %d หน้า PDF"
          % (book_id, info["subject"], info["grade"], os.path.basename(info["pdf"]), total))
    print("ภาพอยู่ที่ %s\n" % rel(img_out))
    print("=" * 78)
    print(prompt_for(info, total, front_imgs, probe_imgs, stage_path))
    print("=" * 78)
    print("\nถอดเสร็จแล้วรัน: eduone-py toc_extract.py file %s" % rel(stage_path))
    return 0


def render(info, pdf_pages, width, out_dir):
    """เรนเดอร์หน้า PDF เป็นภาพผ่าน bookscan_page.py -> {หน้า PDF: path ภาพ}

    ใช้ --pdf-page เสมอ เพราะตอนนี้ยังไม่รู้ offset (นั่นคือสิ่งที่กำลังจะหา) และส่ง
    'ชื่อไฟล์' แทน id ของเล่ม เพื่อให้ใช้ได้กับเล่มที่ยังไม่มีบรรทัดใน index ด้วย
    """
    pdf_pages = [p for p in pdf_pages]
    if not pdf_pages:
        return {}
    stem = os.path.splitext(os.path.basename(info["pdf"]))[0]
    cmd = [sys.executable, op.plugin_script("bookscan_page.py"), stem,
           ",".join(str(p) for p in pdf_pages), "--pdf-page",
           "--subject", info["subject"], "--grade", info["grade"],
           "--width", str(width), "--out", out_dir]
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env)
    if r.returncode != 0:
        print(r.stdout or "", r.stderr or "", sep="\n")
        raise SystemExit("ดึงภาพไม่สำเร็จ")

    out = {}
    for line in (r.stdout or "").splitlines():
        line = line.strip()
        if not line.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        base = os.path.basename(line)
        for p in pdf_pages:
            if "pdf%03d." % p in base:
                out[p] = line
    missing = [p for p in pdf_pages if p not in out]
    if missing:
        raise SystemExit("เรนเดอร์ไม่ครบ ขาดหน้า PDF: %s" % ", ".join(map(str, missing)))
    return out


def prompt_for(info, total, front_imgs, probe_imgs, stage_path):
    """คำสั่งสำหรับ sub-agent — ฝังทั้ง prompt และสคีมาไว้ในนี้

    ตั้งใจไม่ให้ agent ไปไล่อ่าน .md อื่นก่อนทำงาน: ทุกไฟล์ที่ agent อ่านจะถูกคิดเป็น
    cache write ซึ่งเป็นค่าใช้จ่ายก้อนใหญ่ที่สุด (56% ของค่า OCR — eval-run-003.md ข้อ 5)
    """
    front_list = "\n".join("    หน้า PDF %-4d %s" % (p, rel(x)) for p, x in sorted(front_imgs.items()))
    probe_list = "\n".join("    หน้า PDF %-4d %s" % (p, rel(x)) for p, x in sorted(probe_imgs.items()))
    example = json.dumps({
        "book_id": info["book_id"],
        "tocPdfPages": [7, 8],
        "chapters": [{
            "no": 1, "title": "บทที่ 1 จำนวนเต็ม", "page": 10,
            "sections": [{"no": "1.1", "title": "จำนวนเต็ม", "page": 13}],
        }],
        "extras": [{"title": "บรรณานุกรม", "page": 288}],
        "probes": [{"pdf_page": 17, "printed_seen": 5},
                   {"pdf_page": 82, "printed_seen": None}],
        "confidence": 0.9,
        "flags": [],
        "notes": "",
    }, ensure_ascii=False, indent=2)

    return """งาน: ถอด **สารบัญ** ของหนังสือเรียนจากภาพสแกน แล้วเขียนเป็น JSON ไฟล์เดียว

เล่ม: {book_id} — {title}
ไฟล์ PDF มี {total} หน้า (เป็นภาพสแกนล้วน ไม่มี text layer จึงต้องดูเป็นภาพเท่านั้น)

## ขั้นที่ 1 — หาหน้าสารบัญ แล้วถอดให้ครบ

ภาพหน้าต้นเล่ม (เปิดด้วย Read ทีละภาพ **เท่าที่จำเป็น** — สารบัญมักอยู่ช่วงหน้า 5-12
ให้เปิดไล่จนเจอแล้วหยุด ไม่ต้องเปิดหมดทุกภาพ ทุกภาพที่เปิดคือค่าใช้จ่าย):
{front_list}

ถอดออกมาให้ครบทุกบรรทัดที่สารบัญมี — ห้ามข้าม ห้ามสรุป ห้ามเรียงใหม่
- **คัดข้อความไทยมาตรง ๆ ทุกตัวอักษร** ตามที่พิมพ์ในสารบัญ (ไม่แก้คำ ไม่ตัดคำ ไม่เติมคำ)
- `page` = **เลขหน้าที่พิมพ์ในสารบัญ** ไม่ใช่ลำดับหน้าใน PDF
- บทใหญ่อยู่ใน `chapters` · หัวข้อย่อยของบทอยู่ใน `sections` ของบทนั้น
- ถ้าเล่มนี้จัดบทเป็น "หน่วย" ให้ใส่ `unit` (เลข) กับ `unitTitle` (ชื่อหน่วย) ในบทนั้นด้วย
- รายการที่ไม่ใช่บทเรียน (คำนำ · บรรณานุกรม · อภิธานศัพท์ · ภาคผนวก · คณะผู้จัดทำ)
  ให้อยู่ใน `extras` · ถ้าสารบัญไม่พิมพ์เลขหน้าไว้ ใส่ `"page": null` แล้วเขียน `note` บอกเหตุผล
- อ่านไม่ออกจริง ๆ ให้ลด `confidence` และเขียนไว้ใน `notes` — **ห้ามเดาตัวเลขหรือชื่อ**

## ขั้นที่ 2 — อ่านเลขหน้าที่พิมพ์บนกระดาษ (จุดสอบเทียบ)

เลขหน้าที่พิมพ์ในหนังสือ ไม่เท่ากับลำดับหน้าใน PDF (มีปก/คำนำ/หน้าแทรกคั่น)
เปิดภาพต่อไปนี้ **ทุกภาพ** แล้วตอบว่ามุมหน้ากระดาษพิมพ์เลขอะไรไว้:
{probe_list}

- ตอบเป็นตัวเลขที่ **เห็นด้วยตา** เท่านั้น — ห้ามคำนวณจากลำดับหน้า PDF
- หน้าที่ไม่มีเลขพิมพ์ (หน้าเปิดบท ปก หน้าเปล่า) ให้ตอบ `"printed_seen": null`
- ถ้าระหว่างเปิดหน้าต้นเล่มในขั้นที่ 1 บังเอิญเห็นหน้าที่มีเลขพิมพ์ ให้เพิ่มเข้า `probes` ด้วย
  (ยิ่งมีจุดมาก ยิ่งรู้ว่าช่วงไหนของเล่มมีหน้าแทรก)

## ผลลัพธ์

เขียนไฟล์เดียวด้วย Write ที่ **{stage_path}** ตามรูปนี้ (คีย์อื่นไม่ต้องมี — สคริปต์เติมเอง):

{example}

- `tocPdfPages` = เลขหน้า **PDF** ของภาพที่ใช้ถอดสารบัญ (ไว้ย้อนตรวจ)
- `confidence` = 0-1 ความมั่นใจว่าถอดถูกครบ
- `flags` = ใส่ `"needs_review"` ถ้ามีอะไรที่คนควรมาดูซ้ำ
- **ห้ามคำนวณ offset / ห้ามเดาว่าเล่มนี้สแกนครบหรือไม่** — สคริปต์คำนวณจาก probes เอง
- ห้ามแก้ไฟล์อื่นใด ๆ ในรีโป นอกจากไฟล์ staging ไฟล์นี้
""".format(book_id=info["book_id"], title=info["book"].get("title", ""), total=total,
           front_list=front_list, probe_list=probe_list,
           stage_path=rel(stage_path), example=example)


# ── calibrate ───────────────────────────────────────────────────────────────

def uncertain_windows(probes):
    """ช่วงหน้า PDF ที่ยัง 'ไม่รู้ว่า offset เปลี่ยนตรงไหน' -> [(pdf_ก่อน, pdf_หลัง), ...]

    ระหว่างสอง probe ที่ให้ offset ต่างกัน มีหน้าแทรกอยู่ที่ไหนสักแห่ง แต่ไม่รู้ว่าตรงไหน
    ทุกหน้าในช่วงนั้นจึงคลาดได้ ±1 — ยิ่งช่วงกว้าง ยิ่งมีหน้าที่หยิบผิด
    """
    pts = sorted((p["printed_seen"], p["pdf_page"]) for p in probes
                 if isinstance(p.get("printed_seen"), int) and p["printed_seen"] >= 1)
    out = []
    for (p1, f1), (p2, f2) in zip(pts, pts[1:]):
        if (f1 - p1) != (f2 - p2) and f2 - f1 > 2:
            out.append((f1, f2))
    return out


def cmd_calibrate(book_id, pages_spec, count, width):
    info = resolve_book(book_id)
    stage_path = os.path.join(STAGING, "%s.json" % book_id)
    if not os.path.isfile(stage_path):
        raise SystemExit("ไม่พบไฟล์ staging %s — ต้องรัน plan + ให้ agent ถอดก่อน" % rel(stage_path))
    raw = load_json(stage_path)
    probes = [p for p in (raw.get("probes") or []) if isinstance(p, dict)]

    if pages_spec:
        want = op.parse_pages(pages_spec)
    else:
        windows = uncertain_windows(probes)
        if not windows:
            print("offset คงที่ตลอดเท่าที่ probe มา — ไม่ต้องสอบเทียบเพิ่ม")
            return 0
        picked = set()
        for lo, hi in windows:
            step = (hi - lo) / float(count + 1)
            for i in range(count):
                page = int(round(lo + step * (i + 1)))
                if lo < page < hi:
                    picked.add(page)
        want = sorted(picked)
        print("ช่วงที่ยังคลาด: %s"
              % ", ".join("PDF %d-%d (%d หน้า)" % (a, b, b - a - 1) for a, b in windows))

    have = {p.get("pdf_page") for p in probes}
    want = [p for p in want if p not in have]
    if not want:
        print("หน้าที่ขอมา probe ไปแล้วทั้งหมด")
        return 0

    img_out = os.path.join(IMG_DIR, book_id)
    os.makedirs(img_out, exist_ok=True)
    imgs = render(info, want, width or PROBE_WIDTH, img_out)

    print("\nสอบเทียบเพิ่ม %d จุด — เล่ม %s" % (len(want), book_id))
    print("=" * 78)
    print("""งาน: อ่าน **เลขหน้าที่พิมพ์บนกระดาษ** จากภาพต่อไปนี้ แล้วเติมลงไฟล์ที่มีอยู่แล้ว

เล่มนี้มีหน้าแทรกกลางเล่ม ทำให้เลขหน้าพิมพ์กับลำดับหน้า PDF เหลื่อมกันไม่เท่ากันทั้งเล่ม
ต้องรู้ว่า 'เหลื่อมเพิ่มตรงไหน' ไม่งั้นทุกหน้าในช่วงนี้จะถูกหยิบผิดไป 1 หน้า

เปิดภาพทุกภาพด้วย Read แล้วดูเลขที่พิมพ์ไว้ที่มุมหน้ากระดาษ:
{img_list}

- ตอบเฉพาะเลขที่ **เห็นด้วยตา** — ห้ามคำนวณจากลำดับหน้า PDF
- หน้าที่ไม่มีเลขพิมพ์ (หน้าเปิดบท หน้าเปล่า) ตอบ null

จากนั้น **แก้ไฟล์ {stage}** ด้วย Edit: เพิ่มรายการเหล่านี้เข้าไปใน `probes` ที่มีอยู่แล้ว
(ห้ามลบของเดิม ห้ามแก้ส่วนอื่นของไฟล์ ห้ามแตะไฟล์อื่นในรีโป):

    {{"pdf_page": <หน้า PDF>, "printed_seen": <เลขที่เห็น หรือ null>}}
""".format(img_list="\n".join("    หน้า PDF %-4d %s" % (p, rel(x)) for p, x in sorted(imgs.items())),
           stage=rel(stage_path)))
    print("=" * 78)
    print("\nเสร็จแล้วรัน: eduone-py toc_extract.py file %s" % rel(stage_path))
    return 0


# ── file ────────────────────────────────────────────────────────────────────

def offsets_from_probes(probes, partial_hint=False):
    """(หน้า PDF, เลขที่เห็น) -> ตาราง offsets แบบเดียวกับที่ calibrate ด้วยมือเขียนไว้

    จุดแรกยืดกลับไปถึงหน้าพิมพ์ที่ 1 เมื่อเล่มสแกนครบ — ไม่งั้นบทที่อยู่ก่อน probe แรก
    จะถูกแปลงด้วย offset 0 แบบเงียบ ๆ แล้วชี้ไปหน้าผิด
    """
    pts = sorted((p["printed_seen"], p["pdf_page"]) for p in probes
                 if isinstance(p.get("printed_seen"), int) and p["printed_seen"] >= 1)
    out = []
    for printed, pdf in pts:
        offset = pdf - printed
        if not out or out[-1]["offset"] != offset:
            out.append({"fromPrinted": printed, "offset": offset})
    if out and not partial_hint:
        out[0]["fromPrinted"] = 1
    return out


def mark_scanned(book):
    """เติม/แก้ฟิลด์ scanned ของทุกบรรทัดให้ตรงกับ scannedPrinted — สคริปต์เป็นเจ้าของฟิลด์นี้

    หัวข้อย่อยใส่เฉพาะตัวที่ต่างจากบทของมัน (bm25_index.py อ่านแบบสืบทอดอยู่แล้ว)
    เขียนครบทุกบรรทัดจะทำให้ไฟล์ยาวขึ้นเท่าตัวโดยไม่ได้ข้อมูลเพิ่ม
    """
    if not book.get("partial"):
        for ch in book.get("chapters") or []:
            ch.pop("scanned", None)
            for sec in ch.get("sections") or []:
                sec.pop("scanned", None)
        for extra in book.get("extras") or []:
            extra.pop("scanned", None)
        return

    for ch in book.get("chapters") or []:
        ch_scanned = ts.is_scanned(book, ch.get("page")) if ch.get("page") else False
        ch["scanned"] = ch_scanned
        for sec in ch.get("sections") or []:
            if not sec.get("page"):
                continue
            val = ts.is_scanned(book, sec["page"])
            if val == ch_scanned:
                sec.pop("scanned", None)
            else:
                sec["scanned"] = val
    for extra in book.get("extras") or []:
        extra["scanned"] = ts.is_scanned(book, extra["page"]) if extra.get("page") else False


def max_printed(book):
    pages = []
    for ch in book.get("chapters") or []:
        if isinstance(ch.get("page"), int):
            pages.append(ch["page"])
        for sec in ch.get("sections") or []:
            if isinstance(sec.get("page"), int):
                pages.append(sec["page"])
    for extra in book.get("extras") or []:
        if isinstance(extra.get("page"), int):
            pages.append(extra["page"])
    return max(pages) if pages else 0


def build_extraction(info, raw, total, model):
    """รวมของที่ agent ตอบ + ของที่สคริปต์คำนวณ -> ผลถอด 1 เล่มที่พร้อมตรวจ"""
    book = copy.deepcopy(info["book"])
    book.update({
        "file": os.path.basename(info["pdf"]),
        "pages": total,
        "chapters": raw.get("chapters") or [],
        "extras": raw.get("extras") or [],
    })
    book.setdefault("title", os.path.splitext(os.path.basename(info["pdf"]))[0])
    book.setdefault("role", "teacher" if book.get("id", "").startswith("teacher") else "student")

    probes = [p for p in (raw.get("probes") or []) if isinstance(p, dict)]
    readable = [p for p in probes
                if isinstance(p.get("printed_seen"), int) and p["printed_seen"] >= 1]
    seen = sorted(p["printed_seen"] for p in readable)

    # ── เล่มนี้สแกนมาครบทั้งเล่มหรือเปล่า ──────────────────────────────────
    # ตัดสินจาก "หน้าสุดท้ายในสารบัญยังอยู่ในไฟล์ไหม" โดยแปลงด้วย offset ที่เพิ่งสอบเทียบ
    #
    # ★ ห้ามตัดสินจาก 'probe ที่อ่านได้ตัวท้ายสุด < หน้าสูงสุดในสารบัญ' เฉย ๆ —
    #   ปกหลังกับหน้าเปล่าไม่มีเลขพิมพ์ (เจอจริงกับคู่มือครู ม.1: probe หน้า PDF สุดท้าย
    #   ตอบ null) เล่มที่ครบทั้งเล่มจะถูกตีตราว่า partial แล้วเครื่องมือจะปฏิเสธหน้าที่มีอยู่จริง
    top = max_printed(book)
    book["offsets"] = offsets_from_probes(probes, partial_hint=False)
    last_pdf_probe = max(probes, key=lambda p: p.get("pdf_page") or 0) if probes else None
    tail_readable = (last_pdf_probe is not None
                     and last_pdf_probe.get("pdf_page") == total
                     and isinstance(last_pdf_probe.get("printed_seen"), int))

    partial = bool(top and (ts.printed_to_pdf(book, top) > total
                            or (tail_readable and last_pdf_probe["printed_seen"] < top)))

    if partial:
        book["partial"] = True
        book["scannedPrinted"] = [[seen[0], seen[-1]]] if seen else []
        # จุดสอบเทียบจุดแรกต้องไม่ยืดกลับไปหน้า 1 ในเล่มที่ต้นเล่มไม่ได้สแกนมา
        book["offsets"] = offsets_from_probes(probes, partial_hint=True)
    else:
        book.pop("partial", None)
        book.pop("scannedPrinted", None)
    mark_scanned(book)

    flags = list(raw.get("flags") or [])
    notes = []
    if book["offsets"]:
        notes.append("สอบเทียบจาก %d จุดที่ agent อ่านเลขหน้าจากภาพ: %s"
                     % (len(seen), ", ".join("พิมพ์%d=PDF%d" % (p["printed_seen"], p["pdf_page"])
                                             for p in probes
                                             if isinstance(p.get("printed_seen"), int))))
    # เล่มที่มีหน้าแทรกกลางเล่มยังใช้ได้ ถ้ารู้ว่าหน้าแทรกอยู่ตรงไหน — สิ่งที่ต้องรายงาน
    # คือ 'ยังเหลือกี่หน้าที่ไม่แน่ใจ' ไม่ใช่ 'offset ไม่คงที่' เฉย ๆ
    # (ธงที่ขึ้นทุกครั้งที่มีหน้าแทรก จะกลายเป็นธงที่ไม่มีใครสนใจ)
    windows = uncertain_windows(probes)
    if windows:
        at_pdf = {p.get("pdf_page"): p.get("printed_seen") for p in probes}
        spans, widest = [], 0
        for lo, hi in windows:
            first, last = at_pdf[lo] + 1, at_pdf[hi] - 1      # หน้าพิมพ์ที่ยังไม่มีใครเห็น
            widest = max(widest, last - first + 1)
            spans.append("พิมพ์ %d" % first if first == last else "พิมพ์ %d-%d" % (first, last))
        notes.append("⚠ มีหน้าแทรกกลางเล่ม — ยังไม่รู้ว่าแทรกตรงไหนพอดี หน้า %s จึงอาจคลาด ±1 "
                     "(%d หน้า) · บีบให้แคบลงได้ด้วย toc_extract.py calibrate"
                     % (", ".join(spans), widest))
        if widest > 2 and "needs_review" not in flags:
            flags.append("needs_review")
    if partial and seen:
        notes.append("⚠ สแกนไม่เต็มเล่ม — ช่วง %d-%d มาจาก probe หัว/ท้ายไฟล์ ไม่ใช่การไล่ดูทุกหน้า "
                     "ถ้ามีหน้าขาดกลางเล่มจะยังไม่รู้" % (seen[0], seen[-1]))
        if not tail_readable:
            notes.append("⚠ หน้าสุดท้ายของไฟล์ไม่มีเลขพิมพ์ให้อ่าน ขอบบนของช่วงจึงเป็นค่าต่ำสุด"
                         "ที่ยืนยันได้ (อาจสแกนมามากกว่านี้)")
            if "needs_review" not in flags:
                flags.append("needs_review")
    lowest = min(seen) if seen else None
    if lowest and lowest > 1 and not partial:
        notes.append("หน้าพิมพ์ %d เป็นจุดต่ำสุดที่มีคนเห็นเลขจริง — หน้าก่อนหน้านั้นใช้ offset "
                     "เดียวกันโดยอนุมาน (ต้นเล่มมักไม่พิมพ์เลขหน้า)" % lowest)
    book["offsetNote"] = " · ".join(notes)

    # โน้ตของ agent แยกช่องไว้ — offsetNote ต้องอ่านแล้วเห็นเรื่องเลขหน้าอย่างเดียว
    # (bookscan_index.py books พิมพ์ฟิลด์นี้ออกมาให้คนอ่าน ถ้ายัดทุกอย่างลงไปจะไม่มีใครอ่าน)
    if raw.get("notes"):
        book["extractNote"] = str(raw["notes"])

    return {
        "schema_version": ts.SCHEMA_VERSION,
        "book_id": info["book_id"],
        "subject": info["subject"],
        "grade": info["grade"],
        "book": book,
        "tocPdfPages": raw.get("tocPdfPages"),
        "probes": probes,
        "confidence": raw.get("confidence"),
        "flags": flags,
        "model": model,
        "extracted_at": datetime.date.today().isoformat(),
    }


def merge_into_index(info, book):
    """เขียนเล่มนี้ลง bookscan_index.json โดยไม่แตะเล่มอื่นในไฟล์เดียวกัน"""
    if os.path.isfile(info["index_path"]):
        idx = load_json(info["index_path"])
    else:
        idx = {"subject": info["subject"], "grade": info["grade"],
               "note": "สารบัญถอดจากหน้าสารบัญของหนังสือ (ไฟล์เป็นภาพสแกนล้วน ไม่มี text layer "
                       "จึงค้นด้วยข้อความไม่ได้). page = เลขหน้าที่พิมพ์บนหน้ากระดาษ; "
                       "แปลงเป็นหน้า PDF ด้วย offsets",
               "books": []}

    books = idx.setdefault("books", [])
    for i, existing in enumerate(books):
        if existing.get("id") == book.get("id"):
            # ฟิลด์ที่คนเขียนไว้เองและสคริปต์ไม่ได้เป็นเจ้าของ ต้องอยู่ต่อ
            merged = dict(existing)
            merged.update(book)
            books[i] = merged
            break
    else:
        books.append(book)
    books.sort(key=lambda b: b.get("id", ""))

    tmp = info["index_path"] + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as fh:
        json.dump(idx, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, info["index_path"])
    return info["index_path"]


def cmd_file(paths, model, dry_run, local):
    rc = 0
    for path in paths:
        if not os.path.isfile(path):
            print("FAIL  %s\n        ไม่พบไฟล์" % path)
            rc = 1
            continue
        raw = load_json(path)
        book_id = raw.get("book_id") or os.path.splitext(os.path.basename(path))[0]
        info = resolve_book(book_id)
        if not info or not info["pdf"]:
            print("FAIL  %s\n        ไม่พบไฟล์ PDF ของเล่ม %s" % (path, book_id))
            rc = 1
            continue

        data = build_extraction(info, raw, page_count(info["pdf"]), model)
        problems = ts.check_extraction(data)
        for p in problems:
            print("      %s" % p)
        if ts.has_error(problems):
            print("FAIL  %s — ไม่เขียนเข้า index (แก้ไฟล์ staging แล้วรันซ้ำได้)" % rel(path))
            rc = 1
            continue

        book = data["book"]
        n_ch = len(book.get("chapters") or [])
        n_sec = sum(len(c.get("sections") or []) for c in book.get("chapters") or [])
        if dry_run:
            print("ok    %s (dry-run ไม่ได้เขียน) — %d บท %d หัวข้อ" % (rel(path), n_ch, n_sec))
            continue

        out = merge_into_index(info, book)
        print("ok    %s -> %s" % (rel(path), rel(out)))
        print("      %d บท · %d หัวข้อ · %d รายการท้ายเล่ม · offsets %s%s"
              % (n_ch, n_sec, len(book.get("extras") or []),
                 ", ".join("พิมพ์%d ขึ้นไป %+d" % (o["fromPrinted"], o["offset"])
                           for o in book.get("offsets") or []),
                 " · partial %s" % book.get("scannedPrinted") if book.get("partial") else ""))
        if not local and server():
            rc = push_result(book_id, data) or rc
        print("      ต่อไป: python docs/rag/bm25_index.py build --fields all")
    return rc


# ── status ──────────────────────────────────────────────────────────────────

def cmd_status(book_id):
    rows = []
    for idx_path in sorted(glob.glob(os.path.join(BOOKSCAN, "*", "*", "bookscan_index.json"))):
        idx = load_json(idx_path)
        for book in idx.get("books", []):
            bid = ts.book_id_of(idx.get("subject", ""), idx.get("grade", ""), book.get("id", ""))
            if book_id and bid != book_id:
                continue
            n_ch = len(book.get("chapters") or [])
            n_sec = sum(len(c.get("sections") or []) for c in book.get("chapters") or [])
            rows.append((bid, book.get("pages"), n_ch, n_sec,
                         "partial" if book.get("partial") else "เต็มเล่ม",
                         len(book.get("offsets") or [])))
    if not rows:
        print("ไม่พบเล่ม%s" % (" %s" % book_id if book_id else "ใดเลย"))
        return 1
    print("%-22s %6s %6s %8s %-10s %s" % ("book_id", "หน้า", "บท", "หัวข้อ", "ความครบ", "จุดสอบเทียบ"))
    for bid, pages, n_ch, n_sec, kind, n_off in rows:
        mark = "  " if n_ch else "⚠ "
        print("%s%-20s %6s %6d %8d %-10s %d" % (mark, bid, pages, n_ch, n_sec, kind, n_off))
    if any(not r[2] for r in rows):
        print("\n⚠ = ยังไม่มีสารบัญ — ถอดด้วย: eduone-py toc_extract.py plan <book_id>")
    return 0


def main():
    op._out()
    ea.OFFLINE_HINT = OFFLINE_HINT
    ap = argparse.ArgumentParser(description="ถอดสารบัญหนังสือสแกนเข้า bookscan_index.json")
    sub = ap.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("queue", help="เล่มที่รอถอดสารบัญบนเว็บ")
    q.add_argument("--limit", type=int, default=50)

    p = sub.add_parser("plan", help="ดึงภาพหน้าต้นเล่ม + probe แล้วพิมพ์คำสั่งให้ sub-agent")
    p.add_argument("book_id")
    p.add_argument("--pdf", default=None, help="ระบุไฟล์ PDF เอง (เล่มที่ยังไม่มีใน index)")
    p.add_argument("--front", type=int, default=FRONT_PAGES, help="จำนวนหน้าต้นเล่มที่เรนเดอร์")
    p.add_argument("--probe-more", action="store_true",
                   help="เพิ่มจุดสอบเทียบ (ใช้เมื่อ offset ไม่คงที่ หรือสงสัยว่าสแกนขาดกลางเล่ม)")
    p.add_argument("--width", type=int, default=None)
    p.add_argument("--local", action="store_true", help="ไม่แตะเซิร์ฟเวอร์ (ทำงานในเครื่องล้วน)")

    c = sub.add_parser("calibrate", help="สอบเทียบเพิ่มในช่วงที่ offset ยังคลาด (มีหน้าแทรก)")
    c.add_argument("book_id")
    c.add_argument("--pages", default="", help="ระบุหน้า PDF เอง เช่น 100,120,140")
    c.add_argument("--count", type=int, default=5, help="จำนวนจุดต่อช่วงที่คลาด")
    c.add_argument("--width", type=int, default=None)

    f = sub.add_parser("file", help="ตรวจผลที่ agent เขียน แล้วเขียนเข้า index (+ ส่งขึ้นเว็บ)")
    f.add_argument("paths", nargs="+")
    f.add_argument("--model", default="claude-opus-5")
    f.add_argument("--dry-run", action="store_true")
    f.add_argument("--local", action="store_true", help="ไม่ส่งขึ้นเว็บ (ส่งทีหลังด้วย push)")

    u = sub.add_parser("push", help="ส่งสารบัญที่ถอดไว้แล้วขึ้นเว็บ (ใช้ตอนส่งไม่สำเร็จ)")
    u.add_argument("book_id")
    u.add_argument("--model", default="claude-opus-5")
    u.add_argument("--dry-run", action="store_true")

    l = sub.add_parser("pull", help="ดึงสารบัญจากเว็บมาเขียน bookscan_index.json ในเครื่อง")
    l.add_argument("--grade", required=True, help="slug เช่น m1")
    l.add_argument("--subject", required=True, help="slug เช่น math")
    l.add_argument("--dry-run", action="store_true")

    s = sub.add_parser("status", help="เล่มไหนมีสารบัญแล้ว/ยัง")
    s.add_argument("book_id", nargs="?", default="")

    a = ap.parse_args()
    if a.cmd == "queue":
        return cmd_queue(a.limit)
    if a.cmd == "plan":
        return cmd_plan(a.book_id, a.pdf, a.front, a.probe_more, a.width, a.local)
    if a.cmd == "calibrate":
        return cmd_calibrate(a.book_id, a.pages, a.count, a.width)
    if a.cmd == "file":
        return cmd_file(a.paths, a.model, a.dry_run, a.local)
    if a.cmd == "push":
        return cmd_push(a.book_id, a.model, a.dry_run)
    if a.cmd == "pull":
        return cmd_pull(a.grade, a.subject, a.dry_run)
    return cmd_status(a.book_id)


if __name__ == "__main__":
    sys.exit(main())
