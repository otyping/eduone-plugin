#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ถอดหน้าหนังสือเข้าคลังข้อความ — RAG-PLAN ข้อ 6.2 + 6.3

    eduone-py ocr_page.py plan   p4-sci-book1 92-96             # หน้าไหนมีแล้ว/ต้องถอด + ดึงภาพ + พิมพ์ prompt
    eduone-py ocr_page.py plan   p4-sci-book1 77-101 --batch 10 # ชุดใหญ่ -> แบ่งเป็นหลาย prompt
    eduone-py ocr_page.py file   .cache/rag/ocr-staging/p4-sci-book1/p092.json ...   # ตรวจ + เก็บ + ส่งขึ้นเว็บ
    eduone-py ocr_page.py status p4-sci-book1                   # manifest หน้าที่มีในคลัง (เครื่อง + เว็บ)
    eduone-py ocr_page.py pull   p4-sci-book1                   # ดึงหน้าที่คนอื่นถอดไว้แล้วมาลงเครื่อง
    eduone-py ocr_page.py push   p4-sci-book1 --all             # ส่งหน้าในเครื่องขึ้นเว็บ (ของค้าง/ของเก่า)

★ ตั้งแต่ 3.4.0 สคริปต์นี้อยู่ในปลั๊กอิน ไม่ใช่ใน repo งาน — ทุกเครื่องที่ติดตั้งปลั๊กอินถอดได้
  (เดิมอยู่ที่ `docs/rag/` ของ repo EDUONE-MCP-RAG มีเครื่องเดียวในทีมที่ถอดได้)
  path ของคลัง (`BookScan/`, `.cache/rag/`) อิง **โฟลเดอร์งาน** เสมอ ไม่ใช่ที่อยู่สคริปต์

★ **ทำงานสองโหมดเสมอ** — ต่อเว็บได้ใช้คลังกลาง ต่อไม่ได้ก็ถอดในเครื่องต่อ (RAG-PLAN 6.2 "degrade")
  ตั้ง `EDUONE_URL` + `EDUONE_TOKEN` แล้วทุกคำสั่งจะคุยกับเว็บให้เอง · `--local` = ไม่ต้องคุย

  ที่ต้องมีคลังกลางเพราะ **ถอดซ้ำ 1 หน้า = ทิ้ง ~7.6 บาท** (eval-run-005.md) พนักงานหลายคน
  ถอดขนานกัน `plan` จึงถามเว็บก่อนเสมอว่าหน้าไหนถอดไปแล้ว (ดึงมาใช้ฟรี) หน้าไหนคนอื่นจองอยู่

★ สคริปต์นี้ **ไม่อ่านภาพเอง** — มันเตรียมงานให้ sub-agent ไปอ่าน แล้วรับผลกลับมาตรวจ
  ตามกฎทองใน CLAUDE.md ("ห้ามให้ orchestrator เรียก OCR เอง — ภาพจะค้างใน context ของแม่")

★ **1 prompt = หลายหน้า** (ค่าเริ่มต้น 5 · `--batch`) — cache write ของ system prompt + tool
  จ่ายครั้งเดียวตอน agent เกิด ไม่ใช่ต่อหน้า · วัดแล้วลดค่าถอดจาก $0.707 เหลือ **$0.211/หน้า**
  (ดู `eval-run-005.md`) · ถ้า plan แบ่งออกมาหลายชุด **ให้เรียก sub-agent ทุกตัวในข้อความเดียว**

★ **กติกาการถอดอยู่ใน `PROMPT_TMPL` ท้ายไฟล์นี้ ไม่ใช่ใน .md** — `ocr-prompt.md` เลิกใช้แล้ว
  (ไฟล์ที่ agent ต้องเปิดอ่านเอง = cache write ตอนอ่าน + cache read ทุกเทิร์นหลังจากนั้น)
  แก้กติกาแล้วถ้าต้องบังคับจริง ต้องไปเพิ่มกฎใน `validate_ocr.py` ด้วย

★ แบ่งงานตามกฎ RAG-PLAN 8.3 "อะไรที่ deterministic ได้ ให้สคริปต์ทำ":

    สคริปต์เติมเอง   schema_version · book_id · grade · subject · printed_page · pdf_page
                     unit · unit_title · chapter · chapter_title · ocr_model · ocr_at
    agent ต้องตอบ    printed_page_seen · page_kind · section · text_md · definitions
                     activity · figures · vocab · math · confidence · flags

  agent จึงเดา book_id ผิดไม่ได้ และเลขหน้าที่ใช้ตรวจสอบ (printed_page_seen) ยังมาจากตาเท่านั้น

★ กฎการตรวจอยู่ที่ `webapp/app/page_schema.py` ชุดเดียว — ทั้งสคริปต์นี้และเซิร์ฟเวอร์เรียกตัวเดียวกัน
  ไม่งั้นจะเจอ "ในเครื่องผ่าน แต่เว็บปฏิเสธ" ซึ่งแปลว่าเงินที่จ่ายค่าถอดไปแล้วเก็บเข้าคลังกลางไม่ได้
"""

import argparse
import datetime
import glob
import io
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _root import WORK_ROOT          # noqa: E402  โฟลเดอร์งานของเครื่องนี้ (env -> ไฟล์ตั้งค่า -> cwd)

# ★ ทุก path ด้านล่างอิง "โฟลเดอร์งาน" ไม่ใช่ที่อยู่ของสคริปต์ (สคริปต์อยู่ในปลั๊กอินที่อัปเดตทับได้)
BOOKSCAN = os.path.join(WORK_ROOT, "BookScan")
CACHE = os.path.join(WORK_ROOT, ".cache", "rag")
IMG_DIR = os.path.join(CACHE, "ocr-img")
STAGING = os.path.join(CACHE, "ocr-staging")

#: หน้าที่ถอดแล้วแต่ยังส่งขึ้นเว็บไม่สำเร็จ — {book_id: [เลขหน้า]}
#: ★ ห้ามทิ้งงาน OCR ที่จ่ายเงินไปแล้วเพราะเน็ตล่ม (RAG-PLAN 6.2) · ส่งซ้ำได้ด้วย `push`
OUTBOX = os.path.join(CACHE, "ocr-outbox.json")

import eduone_api as ea              # noqa: E402  ตัวเชื่อมเว็บชุดเดียวของงานคลังหนังสือ
import page_schema as ps             # noqa: E402  กฎการตรวจชุดเดียวกับเซิร์ฟเวอร์

SCHEMA_VERSION = ps.SCHEMA_VERSION
DEFAULT_WIDTH = 1000          # RAG-PLAN ข้อ 3.2 — ลด token 49% โดยไม่เสียข้อมูล

#: ต่อเว็บไม่ได้แล้วทำอะไรต่อ — ตั้งใน main() (toc_extract.py ก็ตั้งค่านี้ ใครตั้งทีหลังทับกัน)
OFFLINE_HINT = ("ผลที่ถอดได้จะเก็บลงคลังในเครื่องตามปกติ "
                "แล้วส่งขึ้นเว็บทีหลังด้วย ocr_page.py push")

#: กี่หน้าต่อ sub-agent 1 ตัว — cache write (~42k โทเคน/agent) จ่ายครั้งเดียวต่อ agent
#: จึงหารด้วยจำนวนหน้าได้ตรง ๆ · 5 คือเลขที่วัดผลไว้ใน eval-run-005.md
DEFAULT_BATCH = 5


def _out():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def load_json(path):
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


def plugin_script(name):
    """หา script พี่น้องในปลั๊กอิน — ข้าง ๆ ตัวเองก่อน แล้วค่อยไล่ตามที่ติดตั้งไว้

    ★ ตั้งแต่สคริปต์นี้ย้ายเข้าปลั๊กอิน (3.4.0) กรณีปกติคือ "อยู่โฟลเดอร์เดียวกัน" —
      แต่ยังเก็บทางที่เหลือไว้ เผื่อมีสำเนาเก่าค้างในโฟลเดอร์งานของใครแล้วถูกรันตรง ๆ
    """
    cands = [os.path.join(HERE, name)]
    root = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.environ.get("EDUONE_PLUGIN_ROOT")
    if root:
        cands.append(os.path.join(root, "skills", "shared", "scripts", name))
    home = os.path.expanduser("~")
    cands.append(os.path.join(home, ".claude", "plugins", "marketplaces", "eduone",
                              "skills", "shared", "scripts", name))
    cands += sorted(glob.glob(os.path.join(
        home, ".claude", "plugins", "cache", "eduone", "edu-one", "*",
        "skills", "shared", "scripts", name)), reverse=True)
    for c in cands:
        if os.path.isfile(c):
            return c
    raise SystemExit(
        "หา %s ไม่เจอ — ติดตั้งปลั๊กอินก่อน (claude plugin install edu-one@eduone)\n"
        "หรือชี้ path เอง: set EDUONE_PLUGIN_ROOT=<โฟลเดอร์ปลั๊กอิน>" % name)


# ── คลัง ────────────────────────────────────────────────────────────────────

def slug_grade(g):
    return (g or "").replace(".", "").strip().lower()


def find_book(book_id):
    """book_id -> ข้อมูลเล่มจาก bookscan_index.json ที่ตรงกัน"""
    for idx_path in glob.glob(os.path.join(BOOKSCAN, "*", "*", "bookscan_index.json")):
        idx = load_json(idx_path)
        subject, grade = idx.get("subject", ""), idx.get("grade", "")
        for book in idx.get("books", []):
            bid = "%s-%s-%s" % (slug_grade(grade), subject.lower(), book.get("id", ""))
            if bid == book_id:
                return {"index_path": idx_path, "dir": os.path.dirname(idx_path),
                        "subject": subject, "grade": grade, "book": book, "book_id": bid}
    raise SystemExit(
        "ไม่รู้จัก book_id %r — ที่มีในเครื่องคือ: %s\n"
        "  เล่มที่คนอื่นอัปขึ้นเว็บแล้ว ต้องดึงสารบัญลงมาก่อน (คลังหน้าใช้ offsets จากสารบัญ\n"
        "  แปลงเลขหน้าพิมพ์เป็นหน้า PDF): eduone-py toc_extract.py pull --grade <ชั้น> --subject <วิชา>"
        % (book_id, ", ".join(sorted(all_book_ids())) or "(ไม่มีเลย)"))


def all_book_ids():
    out = []
    for idx_path in glob.glob(os.path.join(BOOKSCAN, "*", "*", "bookscan_index.json")):
        idx = load_json(idx_path)
        for book in idx.get("books", []):
            out.append("%s-%s-%s" % (slug_grade(idx.get("grade", "")),
                                     idx.get("subject", "").lower(), book.get("id", "")))
    return out


def pages_dir(info):
    return os.path.join(info["dir"], "pages", info["book_id"])


def have_page(info, printed):
    """หน้านี้อยู่ในคลัง *ในเครื่อง* แล้วหรือยัง — คลังกลางถามด้วย remote_manifest()"""
    p = os.path.join(pages_dir(info), "p%03d.json" % printed)
    return p if os.path.isfile(p) else None


def page_path(info, printed):
    return os.path.join(pages_dir(info), "p%03d.json" % printed)


def write_page(info, printed, data):
    """เขียนไฟล์หน้าเข้าคลังในเครื่องแบบ atomic — ไฟล์ครึ่ง ๆ กลาง ๆ ในคลังอันตรายกว่าไม่มีไฟล์"""
    out_path = page_path(info, printed)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp = out_path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    shutil.move(tmp, out_path)
    return out_path


def pdf_page_of(info, printed):
    """แปลงเลขหน้าพิมพ์เป็นหน้า PDF ด้วยจุดสอบเทียบใน bookscan_index.json"""
    offset = 0
    for o in sorted(info["book"].get("offsets", []), key=lambda x: x.get("fromPrinted", 0)):
        if printed >= o.get("fromPrinted", 0):
            offset = o.get("offset", 0)
    return printed + offset


def scanned_ok(info, printed):
    """หน้านี้อยู่ในช่วงที่สแกนมาจริงไหม (บทเรียนจาก q039)"""
    book = info["book"]
    if not book.get("partial"):
        return True
    for lo, hi in book.get("scannedPrinted", []):
        if lo <= printed <= hi:
            return True
    return False


def context_of(info, printed):
    """หา unit/chapter ที่หน้านี้สังกัด จากสารบัญ"""
    best = None
    for ch in info["book"].get("chapters", []):
        if ch.get("page") and int(ch["page"]) <= printed:
            if best is None or int(ch["page"]) >= int(best.get("page", 0)):
                best = ch
    if not best:
        return {}
    return {"unit": best.get("unit"), "unit_title": best.get("unitTitle"),
            "chapter": best.get("no"), "chapter_title": best.get("title")}


def parse_pages(spec):
    """แปลงเลขหน้าด้วยตัวแปลชุดเดียวกับเซิร์ฟเวอร์ — พิมพ์อย่างหนึ่งแล้วเว็บจองอีกอย่างไม่ได้"""
    try:
        return ps.parse_page_spec(spec)
    except ValueError as exc:
        raise SystemExit(str(exc))


def rel(p):
    return os.path.relpath(p, WORK_ROOT).replace("\\", "/")


# ── คลังกลางบนเว็บ ──────────────────────────────────────────────────────────
# RAG-PLAN 6.3 มี 3 เส้นทาง (get/put/manifest) + claim ที่เพิ่มเข้ามาเพื่อกันถอดซ้ำ
# ★ ทุกฟังก์ชันในหมวดนี้ต้องล้มแบบ "บอกแล้วไปต่อ" ไม่ใช่หยุดทั้งงาน — เว็บล่มไม่ควรทำให้
#   คนที่มี PDF อยู่ในเครื่องถอดต่อไม่ได้ (สิ่งที่หายไปคือการกันถอดซ้ำ ไม่ใช่ความสามารถในการถอด)

def connected(local):
    """จะคุยกับเว็บรอบนี้ไหม — เช็คครั้งเดียวตอนเริ่ม ตามกฎ 'เช็ค health ตอนเริ่ม ไม่ใช่กลางทาง'"""
    if local or not ea.configured():
        return False
    return ea.online()


def remote_manifest(book_id):
    """หน้าที่คลังกลางมีแล้ว + หน้าที่คนอื่นจองอยู่ — None = ถามไม่ได้/เว็บไม่รู้จักเล่มนี้"""
    status, body = ea.api("/api/books/%s/pages/manifest" % book_id)
    if status != 200:
        print("⚠ ถามคลังกลางไม่สำเร็จ (%s): %s" % (status, ea.why(body)))
        return None
    if not body.get("known"):
        print("⚠ เว็บยังไม่มีเล่ม %s ในทะเบียน — ถอดในเครื่องได้ แต่ส่งขึ้นคลังกลางไม่ได้\n"
              "  อัปโหลด PDF ที่ %s/upload ก่อน แล้วค่อย push" % (book_id, ea.server()))
        return None
    return body


def remote_get_page(book_id, printed):
    status, body = ea.api("/api/books/%s/pages/%d" % (book_id, printed))
    return body if status == 200 else None


def remote_claim(book_id, wanted):
    """จองหน้าที่จะถอด — คืน dict ของเว็บ หรือ None ถ้าจองไม่ได้ (ทำงานต่อในเครื่องได้)"""
    status, body = ea.api("/api/books/%s/pages/claim" % book_id, method="POST",
                          form={"pages": ",".join(str(p) for p in wanted)})
    if status == 200:
        return body
    print("⚠ จองหน้าบนเว็บไม่สำเร็จ (%s): %s" % (status, ea.why(body)))
    return None


def remote_put_page(book_id, printed, data):
    """ส่งหน้าขึ้นคลังกลาง — คืน (สำเร็จไหม, ข้อความ)"""
    status, body = ea.api("/api/books/%s/pages/%d" % (book_id, printed),
                          method="PUT", payload=data)
    if status in (200, 201):
        return True, "ทับของเดิม" if status == 200 else ""
    if status == 422:
        detail = "; ".join("%(where)s: %(msg)s" % p for p in (body.get("problems") or []))
        return False, "เว็บปฏิเสธ (ไม่ผ่านการตรวจ) %s" % detail
    return False, "%s: %s" % (status, ea.why(body))


# ── คิวของที่ยังส่งไม่ขึ้น ────────────────────────────────────────────────────

def outbox_load():
    if not os.path.isfile(OUTBOX):
        return {}
    try:
        return load_json(OUTBOX)
    except ValueError:
        return {}


def outbox_save(data):
    os.makedirs(os.path.dirname(OUTBOX), exist_ok=True)
    with io.open(OUTBOX, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")


def outbox_mark(book_id, printed, pending=True):
    data = outbox_load()
    have = set(data.get(book_id) or [])
    if pending:
        have.add(printed)
    else:
        have.discard(printed)
    if have:
        data[book_id] = sorted(have)
    else:
        data.pop(book_id, None)
    outbox_save(data)


# ── plan ────────────────────────────────────────────────────────────────────

def ensure_pdf(info, download_url=None):
    """ต้องมีไฟล์ PDF ในเครื่องถึงจะเรนเดอร์ภาพได้ — ไม่มีก็โหลดจาก MinIO ผ่านลิงก์ที่เว็บออกให้

    ★ นี่คือจุดที่ "ต่อเข้ากับ MinIO" — เว็บไม่ได้ส่งไฟล์เอง แต่ออก presigned URL อายุ 1 ชม.
      ให้เครื่องพนักงานไปดึงจาก MinIO ตรง ๆ (ไฟล์เล่มละหลายร้อย MB ไม่ควรวิ่งผ่านเว็บ)
    """
    pdf = os.path.join(info["dir"], info["book"].get("file") or "")
    if info["book"].get("file") and os.path.isfile(pdf):
        return pdf
    if not download_url:
        raise SystemExit(
            "ไม่พบไฟล์ PDF ของเล่ม %s ในเครื่อง (%s)\n"
            "  · เล่มนี้อยู่บนเว็บแล้ว: ตั้ง EDUONE_URL/EDUONE_TOKEN แล้วสั่งใหม่ จะโหลดให้เอง\n"
            "  · ยังไม่ได้อัปขึ้นเว็บ: วางไฟล์ไว้ที่ %s"
            % (info["book_id"], rel(pdf), rel(info["dir"])))
    dest = pdf if info["book"].get("file") else os.path.join(
        info["dir"], "%s.pdf" % info["book_id"])
    print("โหลด PDF จากคลังกลาง -> %s" % rel(dest))
    ea.download(download_url, dest)
    info["book"]["file"] = os.path.basename(dest)
    return dest


def pull_pages(info, printed_pages, force=False):
    """ดึงหน้าที่คนอื่นถอดไว้แล้วลงคลังในเครื่อง — ★ นี่คือส่วนที่ทำให้ไม่ต้องจ่ายค่าถอดซ้ำ

    ตรวจด้วย page_schema ก่อนเขียนเสมอ แม้ของจะมาจากเซิร์ฟเวอร์ที่ตรวจแล้ว: กฎอาจถูกทำให้
    เข้มขึ้นหลังจากหน้านั้นถูกเก็บไป — ของเก่าที่ไม่ผ่านกฎใหม่ต้องรู้ตัว ไม่ใช่ไหลเข้าคลังเงียบ ๆ
    """
    got, failed = [], []
    for p in printed_pages:
        if not force and have_page(info, p):
            continue
        data = remote_get_page(info["book_id"], p)
        if data is None:
            failed.append((p, "เว็บไม่มีหน้านี้"))
            continue
        problems = ps.check_page(data)
        if ps.has_error(problems):
            failed.append((p, "; ".join(str(x) for x in problems if x.level == ps.ERROR)))
            continue
        write_page(info, p, data)
        got.append(p)
    return got, failed


def cmd_plan(book_id, pages_spec, width, batch, local=False):
    info = find_book(book_id)
    pages = parse_pages(pages_spec)

    print("เล่ม %s (%s %s) · คลังอยู่ที่ %s"
          % (book_id, info["subject"], info["grade"], rel(pages_dir(info))))

    online = connected(local)
    manifest, download_url = None, None
    if online:
        manifest = remote_manifest(book_id)

    pulled = []
    if manifest:
        remote_have = {r["printed_page"] for r in manifest.get("pages") or []}
        want_remote = [p for p in pages if p in remote_have and not have_page(info, p)]
        if want_remote:
            pulled, failed = pull_pages(info, want_remote)
            if pulled:
                print("  ดึงจากคลังกลางมาใช้ฟรี %d หน้า (ไม่ต้องถอดซ้ำ): %s"
                      % (len(pulled), ", ".join(map(str, pulled))))
            for p, why in failed:
                print("  ⚠ ดึงหน้า %d จากคลังกลางไม่ได้: %s" % (p, why))

    have, todo, skip = [], [], []
    for p in pages:
        if have_page(info, p):
            have.append(p)
        elif not scanned_ok(info, p):
            skip.append(p)
        else:
            todo.append(p)

    if have:
        print("  มีในคลังแล้ว %d หน้า: %s" % (len(have), ", ".join(map(str, have))))
    if skip:
        print("  ⚠ ยังไม่ได้สแกน %d หน้า (อยู่นอก scannedPrinted): %s — ดึงภาพไม่ได้"
              % (len(skip), ", ".join(map(str, skip))))

    if todo and manifest:
        # จองก่อนถอดเสมอ — คนที่มาถอดบทเดียวกันพร้อมกันจะได้เห็นว่าหน้านี้มีคนทำอยู่แล้ว
        res = remote_claim(book_id, todo)
        if res:
            download_url = res.get("download_url")
            busy = {b["printed_page"]: b["holder"] for b in res.get("busy") or []}
            if busy:
                print("  ⚠ ข้าม %d หน้าที่คนอื่นกำลังถอดอยู่ (จองไว้ไม่เกิน %s ชม.): %s"
                      % (len(busy), manifest.get("lease_hours"),
                         ", ".join("%d (%s)" % (p, h) for p, h in sorted(busy.items()))))
            todo = [p for p in todo if p not in busy and p not in set(res.get("have") or [])]
            if todo:
                print("  จองไว้บนเว็บแล้ว %d หน้า — คนอื่นจะไม่ถอดซ้ำ" % len(todo))

    if not todo:
        print("  ไม่มีหน้าที่ต้องถอด")
        return 0

    ensure_pdf(info, download_url)

    img_out = os.path.join(IMG_DIR, book_id)
    stage_out = os.path.join(STAGING, book_id)
    os.makedirs(img_out, exist_ok=True)
    os.makedirs(stage_out, exist_ok=True)

    script = plugin_script("bookscan_page.py")
    cmd = [sys.executable, script, info["book"]["id"], ",".join(map(str, todo)),
           "--subject", info["subject"], "--grade", info["grade"],
           "--width", str(width), "--out", img_out]
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env)
    if r.returncode != 0:
        print(r.stdout or "", r.stderr or "", sep="\n")
        raise SystemExit("ดึงภาพไม่สำเร็จ")

    imgs = {}
    for f in sorted(os.listdir(img_out)):
        for p in todo:
            if ("_p%d." % p) in f or ("_p%03d." % p) in f or ("p%03d" % p) in f:
                imgs.setdefault(p, os.path.join(img_out, f))
    missing = [p for p in todo if p not in imgs]
    if missing:
        raise SystemExit("ไม่พบไฟล์ภาพของหน้า %s — ตรวจ bookscan_page.py"
                         % ", ".join(map(str, missing)))

    print("\n  ต้องถอด %d หน้า — ภาพอยู่ที่ %s" % (len(todo), rel(img_out)))
    chunks = [todo[i:i + batch] for i in range(0, len(todo), batch)]
    if len(chunks) > 1:
        print("  แบ่งเป็น %d ชุด ชุดละไม่เกิน %d หน้า — ★ sub-agent 1 ตัวต่อ 1 ชุด"
              " และเรียกทุกตัวใน _ข้อความเดียว_ ให้ทำงานขนานกัน" % (len(chunks), batch))

    for n, chunk in enumerate(chunks, 1):
        print("\n" + "=" * 78)
        if len(chunks) > 1:
            print("### ชุดที่ %d/%d — หน้า %s" % (n, len(chunks), ", ".join(map(str, chunk))))
            print("=" * 78)
        print(prompt_for(info, chunk, imgs, stage_out))
        print("=" * 78)

    print("\nถอดครบแล้วรัน: eduone-py ocr_page.py file %s"
          % rel(os.path.join(stage_out, "*.json")))
    return 0


def prompt_for(info, chunk, imgs, stage_out):
    """คำสั่งสำหรับ sub-agent — ★ 1 ตัวถอดหลายหน้า และฝังกติกาไว้ในนี้ทั้งหมด

    สามอย่างนี้คือการลดค่าโสหุ้ยตาม eval-run-003.md ข้อ 5 (คิวข้อ 2):

    1. **1 agent หลายหน้า** — cache write ของ system prompt + tool (~42k โทเคน) จ่ายครั้งเดียว
       ต่อ agent ไม่ใช่ต่อหน้า · ถอด 5 หน้าด้วย agent เดียวจึงหารก้อนนั้นด้วย 5
    2. **ฝัง prompt + สคีมาไว้ในคำสั่ง** ไม่ให้ agent ไปเปิด ocr-prompt.md / ocr-schema.md
       ทุกไฟล์ที่ agent อ่านคือ cache write ก้อนใหม่ และยังพอกเป็น cache read ของทุกเทิร์นถัดไป
    3. **ห้าม agent รัน validate_ocr.py เอง** — `ocr_page.py file` ตรวจให้อยู่แล้ว
       (รอบก่อน agent เสีย 6-8 เทิร์นไปกับ ls/cat/mkdir/รัน validator เอง)
    """
    lines = []
    for p in chunk:
        ctx = context_of(info, p)
        lines.append(
            "  หน้าพิมพ์ %-4d ภาพ: %s\n"
            "                 เขียนลง: %s\n"
            "                 บริบทจากสารบัญ (ไว้เทียบ ไม่ใช่ให้คัดลอก): หน่วย %s %s · บท %s %s"
            % (p, rel(imgs[p]), rel(os.path.join(stage_out, "p%03d.json" % p)),
               ctx.get("unit"), ctx.get("unit_title"), ctx.get("chapter"), ctx.get("chapter_title")))
    page_list = "\n".join(lines)

    example = json.dumps({
        "printed_page_seen": chunk[0],
        "page_kind": "activity",
        "section": "กิจกรรมที่ 1.3 ดอกของพืชทำหน้าที่อะไร",
        "text_md": "## หัวข้อบนหน้า ... ข้อความทุกย่อหน้าที่พิมพ์บนหน้านี้",
        "definitions": [{"term": "เกสรเพศผู้", "definition": "..."}],
        "activity": {"code": "1.3", "title": "...", "objective": "...",
                     "materials": ["..."], "steps": ["..."], "duration_hint": "1 ชั่วโมง"},
        "figures": [{"id": "p%03d_f1" % chunk[0], "tier": 3, "type": "photo",
                     "caption": "", "observed": "สิ่งที่เห็นในภาพ", "teaches": "...",
                     "components": ["..."], "redraw_hint": "...", "color_matters": True,
                     "crop": "figs/%s/p%03d_f1.png" % (info["book_id"], chunk[0]),
                     "needs_image": True, "why_needs_image": "...", "confidence": 0.9}],
        "vocab": ["..."],
        "math": [],
        "indicators": [],
        "confidence": 0.9,
        "flags": [],
    }, ensure_ascii=False, indent=2)

    return PROMPT_TMPL.format(
        subject=info["subject"], grade=info["grade"], book_id=info["book_id"],
        n=len(chunk), page_list=page_list, example=example)


#: ★ กติกาการถอดทั้งหมดอยู่ตรงนี้ที่เดียว — ฝังลงคำสั่งของ sub-agent โดยตรง
#: เดิมเป็นไฟล์ ocr-prompt.md + ocr-schema.md ที่ agent ต้องเปิดอ่านเองก่อนเริ่มงาน
#: ซึ่งกินทั้ง cache write ตอนอ่าน และ cache read ทุกเทิร์นหลังจากนั้น
PROMPT_TMPL = """งาน: ถอดหน้าหนังสือเรียน {subject} {grade} เล่ม {book_id} เป็น JSON เข้าคลังความรู้ RAG
**{n} หน้าในคำสั่งเดียว** — ทำทีละหน้าจนครบ

{page_list}

## วิธีทำ (ต่อ 1 หน้า)

1. เปิดภาพด้วย Read **ครั้งเดียว** แล้วถอดให้ครบในรอบเดียว
2. เขียนผลด้วย Write ลง path "เขียนลง" ของหน้านั้น — JSON ล้วน ไม่มี code fence
3. ทำหน้าถัดไป

**ห้ามทำสิ่งเหล่านี้** (สคริปต์แม่ทำให้แล้ว ทำซ้ำ = จ่ายค่าโทเคนเปล่า):
- ห้ามเปิดไฟล์อื่นในรีโป (ocr-prompt.md · ocr-schema.md · validate_ocr.py · หน้าที่ถอดไว้แล้ว)
  กติกาทั้งหมดอยู่ในคำสั่งนี้แล้ว
- ห้ามรัน validate_ocr.py เอง · ห้าม ls/cat/mkdir · ห้ามเขียนไฟล์ด้วย Bash heredoc
- ห้ามใส่คีย์ที่สคริปต์เติมเอง: schema_version · book_id · grade · subject · printed_page
  · pdf_page · unit · chapter · ocr_model · ocr_at

## ฟิลด์ที่ต้องตอบ

{example}

| ฟิลด์ | กติกา |
|---|---|
| `printed_page_seen` | **เลขที่พิมพ์บนหน้ากระดาษจริง** (คัดตามที่ตาเห็น ห้ามเดา ห้ามคำนวณจากลำดับ) · ไม่มีเลขพิมพ์บนหน้า = `null` |
| `page_kind` | หนึ่งใน `content` `activity` `concept_map` `exercise` `front_matter` |
| `section` | หัวข้อที่พิมพ์บนหน้านั้น |
| `text_md` | **ข้อความที่พิมพ์บนหน้าจริงเท่านั้น** เป็น Markdown · 200-8,000 ตัวอักษร (ยกเว้น `concept_map`/`front_matter` ที่สั้นได้) |
| `definitions` | กล่องนิยาม / กรอบสีในหนังสือ |
| `activity` | ถ้าหน้ามีกิจกรรม: `code` `title` `objective` `materials` `steps` `duration_hint` |
| `vocab` | ศัพท์เฉพาะที่ปรากฏบนหน้า |
| `math` | สูตรคณิต **ต้องครอบด้วย $...$** ทุกตัว |
| `indicators` | ตัวชี้วัดที่**พิมพ์บนหน้า** — ไม่มีพิมพ์ = `[]` |
| `confidence` | 0-1 ระดับหน้า |
| `flags` | เช่น `["ไม่มีตัวชี้วัดพิมพ์บนหน้า"]` |

## ★ กติกาที่ทำให้ไฟล์ถูกตีกลับบ่อยที่สุด

- **`text_md` ห้ามมีคำบรรยายของคุณเอง** — ห้ามเขียนทำนอง "(หน้านี้เป็นหน้าเปิดบท เต็มหน้าเป็นภาพ…)"
  ลงไปเพื่อให้ยาวพอเกณฑ์ · หน้าที่ข้อความจริงสั้น ให้ตั้ง `page_kind` ตามจริงแล้วปล่อยให้สั้น
  คำบรรยายภาพเป็นของ `figures[].observed` ไม่ใช่ของ `text_md`
- **ห้ามเดาสิ่งที่หน้าไม่ได้พิมพ์** — กิจกรรมที่ขึ้นกลางคันโดยไม่มีรหัส/ชื่อ ให้ `code`/`title` เป็น `null`
  แล้วใส่ `continues_from_page` · รูปที่ติดป้าย (ก)(ข)(ค) โดยไม่มีชื่อกำกับ ห้ามเติมชื่อให้
- **แผนภาพ/ผัง** ถอดเป็น `graph.nodes` + `graph.edges` และป้ายกำกับเส้นทุกเส้น
  ทุก `edges[].from` / `to` ต้องเป็น `id` ที่มีอยู่ใน `nodes` จริง

### รูป — 4 ระดับ

| tier | คืออะไร | ต้องมี |
|---|---|---|
| 0 | ภาพตกแต่ง ไม่มีสาระการเรียนรู้ | caption อย่างเดียว · **ห้ามมี `crop`** |
| 1 | ตาราง/ข้อความที่เป็นภาพ | ถอดเป็นข้อความ/ตาราง |
| 2 | ถอดเป็นข้อมูลได้ (กราฟ ผังมโนทัศน์ แผนภูมิ) | **ต้องมี `crop`** + อย่างน้อยหนึ่งใน `graph`/`chart`/`facts`/`pictograph`/`table` |
| 3 | ภาพคือสาระ (อุปกรณ์ทดลอง ตัวอย่างจริง แบบทางเทคนิค) | **ต้องมี `crop`** + `teaches` + `redraw_hint` |

- ทุกรูปต้องมี `id` (ไม่ซ้ำกันในหน้า) · `tier` · `confidence`
- `crop` ตั้งเป็น `figs/{book_id}/p<NNN>_f<k>.png` (ยังไม่ต้องครอปภาพจริง)
- `needs_image: true` ต้องมี `why_needs_image` บอกว่าทำไมข้อความแทนไม่ได้

จบแล้วรายงานสั้น ๆ ว่าเขียนไฟล์ไหนบ้าง · หน้าไหน `printed_page_seen` เท่าไร · หน้าไหนน่าห่วง
"""


# ── file ────────────────────────────────────────────────────────────────────

def envelope(info, printed, model):
    ctx = context_of(info, printed)
    env = {
        "schema_version": SCHEMA_VERSION,
        "book_id": info["book_id"],
        "grade": info["grade"],
        "subject": info["subject"],
        "printed_page": printed,
        "pdf_page": pdf_page_of(info, printed),
    }
    for k in ("unit", "unit_title", "chapter", "chapter_title"):
        if ctx.get(k) is not None:
            env[k] = ctx[k]
    env["ocr_model"] = model
    env["ocr_at"] = datetime.date.today().isoformat()
    env["verified_by"] = None
    env["verified_at"] = None
    return env


def cmd_file(paths, model, dry_run, local=False, no_push=False):
    staged, failed = [], []
    for path in paths:
        if not os.path.isfile(path):
            failed.append((path, "ไม่พบไฟล์"))
            continue
        raw = load_json(path)
        book_id = raw.get("book_id") or os.path.basename(os.path.dirname(path))
        try:
            info = find_book(book_id)
        except SystemExit as e:
            failed.append((path, str(e).splitlines()[0]))
            continue

        printed = raw.get("printed_page")
        if printed is None:
            base = os.path.splitext(os.path.basename(path))[0]
            printed = int("".join(c for c in base if c.isdigit()) or 0)
        printed = int(printed)

        # เลขที่ agent "เห็น" ต้องมาจาก agent เท่านั้น — ห้ามสคริปต์เติมให้
        if "printed_page_seen" not in raw:
            failed.append((path, "ไม่มี printed_page_seen — agent ต้องคัดเลขหน้าที่เห็นบนกระดาษมา"))
            continue

        merged = dict(raw)
        merged.update(envelope(info, printed, model))   # ★ ของ deterministic ทับของ agent เสมอ

        problems = ps.check_page(merged)
        if ps.has_error(problems):
            failed.append((path, "\n        ".join(str(x) for x in problems)))
            continue

        if dry_run:
            staged.append((info, printed, path, page_path(info, printed),
                           "(dry-run ไม่ได้เขียนจริง)", merged))
            continue
        out_path = write_page(info, printed, merged)
        staged.append((info, printed, path, out_path,
                       " · ".join(str(x) for x in problems), merged))

    for info, printed, src, dst, note, _ in staged:
        print("ok    %s -> %s %s" % (os.path.basename(src), rel(dst), note))
    for src, why in failed:
        print("FAIL  %s\n        %s" % (os.path.basename(src), why))
    print("\n%d/%d เข้าคลังในเครื่อง" % (len(staged), len(staged) + len(failed)))

    if staged and not dry_run and not no_push:
        push_staged(staged, local)
    return 1 if failed else 0


def push_staged(staged, local):
    """ส่งหน้าที่เพิ่งเก็บเข้าคลังขึ้นเว็บ — ส่งไม่ขึ้นก็ไม่ถือว่างานเสีย แค่เข้าคิวไว้ push ทีหลัง

    ★ ห้าม `file` ล้มเหลวเพราะส่งไม่ขึ้น: ไฟล์อยู่ในคลังในเครื่องเรียบร้อยแล้ว และค่าถอด
      จ่ายไปแล้ว · สิ่งที่ยังขาดคือการแบ่งให้คนอื่น ซึ่งทำทีหลังได้ (RAG-PLAN 6.2)
    """
    online = connected(local)
    sent, pending = [], []
    for info, printed, _src, _dst, _note, data in staged:
        if not online:
            pending.append((info["book_id"], printed, "ยังไม่ได้ต่อเว็บ"))
            continue
        ok, why = remote_put_page(info["book_id"], printed, data)
        if ok:
            sent.append(printed)
            outbox_mark(info["book_id"], printed, pending=False)
        else:
            pending.append((info["book_id"], printed, why))

    if sent:
        print("ส่งขึ้นคลังกลางแล้ว %d หน้า: %s" % (len(sent), ", ".join(map(str, sorted(sent)))))
    if pending:
        for book_id, printed, why in pending:
            outbox_mark(book_id, printed, pending=True)
        print("ยังไม่ได้ส่งขึ้นเว็บ %d หน้า — เก็บเข้าคิวไว้แล้ว (%s)" % (len(pending), rel(OUTBOX)))
        for book_id, printed, why in pending:
            print("        %s p%03d — %s" % (book_id, printed, why))
        print("  ส่งซ้ำเมื่อไรก็ได้ด้วย: eduone-py ocr_page.py push")


# ── push / pull ─────────────────────────────────────────────────────────────

def cmd_push(book_id, all_pages, dry_run):
    """ส่งหน้าในเครื่องขึ้นคลังกลาง — ของที่ค้างคิว หรือ (--all) ทุกหน้าที่ถอดไว้ก่อนมีเว็บ"""
    if not connected(False):
        raise SystemExit("ต้องต่อเว็บถึงจะส่งได้ — ตั้ง EDUONE_URL/EDUONE_TOKEN แล้วลองใหม่")

    jobs = {}
    if all_pages:
        if not book_id:
            raise SystemExit("--all ต้องระบุ book_id ด้วย")
        info = find_book(book_id)
        d = pages_dir(info)
        jobs[book_id] = sorted(
            int(os.path.basename(f)[1:4])
            for f in glob.glob(os.path.join(d, "p*.json"))) if os.path.isdir(d) else []
    else:
        for bid, pages in outbox_load().items():
            if book_id in (None, bid):
                jobs[bid] = list(pages)

    if not any(jobs.values()):
        print("ไม่มีหน้าที่ต้องส่ง" if not all_pages else "เล่มนี้ยังไม่มีหน้าในคลังในเครื่อง")
        return 0

    rc = 0
    for bid, wanted in sorted(jobs.items()):
        info = find_book(bid)
        print("เล่ม %s — จะส่ง %d หน้า" % (bid, len(wanted)))
        if dry_run:
            print("  dry-run: %s" % ", ".join(map(str, wanted)))
            continue
        sent, failed = [], []
        for p in wanted:
            path = have_page(info, p)
            if not path:
                failed.append((p, "ไม่มีไฟล์หน้านี้ในคลังในเครื่องแล้ว"))
                outbox_mark(bid, p, pending=False)
                continue
            ok, why = remote_put_page(bid, p, load_json(path))
            if ok:
                sent.append(p)
                outbox_mark(bid, p, pending=False)
            else:
                failed.append((p, why))
                outbox_mark(bid, p, pending=True)
        if sent:
            print("  ส่งแล้ว %d หน้า: %s" % (len(sent), ", ".join(map(str, sent))))
        for p, why in failed:
            print("  FAIL p%03d — %s" % (p, why))
        rc = rc or (1 if failed else 0)
    return rc


def cmd_pull(book_id, pages_spec, force):
    """ดึงหน้าที่คนอื่นถอดไว้แล้วลงคลังในเครื่อง — ก่อนเริ่มงานบทใหม่ควรรันอันนี้ก่อน"""
    if not connected(False):
        raise SystemExit("ต้องต่อเว็บถึงจะดึงได้ — ตั้ง EDUONE_URL/EDUONE_TOKEN แล้วลองใหม่")
    info = find_book(book_id)
    manifest = remote_manifest(book_id)
    if not manifest:
        return 1
    remote_have = [r["printed_page"] for r in manifest.get("pages") or []]
    wanted = [p for p in parse_pages(pages_spec) if p in remote_have] if pages_spec else remote_have
    if not wanted:
        print("คลังกลางยังไม่มีหน้าของเล่มนี้ตามที่ขอ")
        return 0

    got, failed = pull_pages(info, wanted, force)
    print("ดึงลงเครื่อง %d หน้า%s"
          % (len(got), (": " + ", ".join(map(str, got))) if got else " (มีครบอยู่แล้ว)"))
    for p, why in failed:
        print("  FAIL p%03d — %s" % (p, why))
    if got:
        print("ต่อไป: python docs/rag/bm25_index.py build --fields all")
    return 1 if failed else 0


# ── status ──────────────────────────────────────────────────────────────────

def cmd_status(book_id, local=False):
    info = find_book(book_id)
    d = pages_dir(info)
    files = sorted(glob.glob(os.path.join(d, "p*.json"))) if os.path.isdir(d) else []
    book = info["book"]
    print("เล่ม %s (%s %s)" % (book_id, info["subject"], info["grade"]))
    if book.get("partial"):
        print("  สแกนมาเฉพาะหน้าพิมพ์: %s"
              % ", ".join("%d-%d" % (a, b) for a, b in book.get("scannedPrinted", [])))
    print("  ในเครื่อง: ถอดแล้ว %d หน้า" % len(files))
    local_pages = set()
    if files:
        low = []
        for f in files:
            d2 = load_json(f)
            local_pages.add(d2.get("printed_page"))
            if (d2.get("confidence") or 1) < ps.LOW_CONFIDENCE or d2.get("verified_by") is None:
                low.append((d2.get("printed_page"), d2.get("confidence")))
        print("  หน้า: %s" % ", ".join(str(p) for p in sorted(x for x in local_pages if x)))
        if low:
            print("  ยังไม่มีคนตรวจ / confidence ต่ำ %d หน้า: %s"
                  % (len(low), ", ".join("p%s(%.2f)" % (p, c or 0) for p, c in sorted(low))))

    pending = outbox_load().get(book_id) or []
    if pending:
        print("  ⚠ ค้างคิวส่งขึ้นเว็บ %d หน้า: %s — ส่งด้วย ocr_page.py push %s"
              % (len(pending), ", ".join(map(str, pending)), book_id))

    if connected(local):
        manifest = remote_manifest(book_id)
        if manifest:
            remote_pages = {r["printed_page"] for r in manifest.get("pages") or []}
            only_remote = sorted(remote_pages - local_pages)
            only_local = sorted(p for p in local_pages if p and p not in remote_pages)
            print("  คลังกลาง: ถอดแล้ว %d หน้า" % len(remote_pages))
            if only_remote:
                print("    มีบนเว็บแต่ยังไม่ได้ลงเครื่อง %d หน้า: %s — ดึงด้วย ocr_page.py pull %s"
                      % (len(only_remote), ", ".join(map(str, only_remote)), book_id))
            if only_local:
                print("    มีในเครื่องแต่ยังไม่ขึ้นเว็บ %d หน้า: %s — ส่งด้วย ocr_page.py push %s --all"
                      % (len(only_local), ", ".join(map(str, only_local)), book_id))
            for c in manifest.get("claims") or []:
                print("    p%03d %s กำลังถอดอยู่ (จองเมื่อ %s)"
                      % (c["printed_page"], c.get("holder") or "อีกคน", c.get("claimed_at")))
    return 0


def main():
    _out()
    ea.OFFLINE_HINT = OFFLINE_HINT
    ap = argparse.ArgumentParser(description="ถอดหน้าหนังสือเข้าคลังข้อความ (RAG-PLAN 6.2/6.3)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_local(parser):
        parser.add_argument("--local", action="store_true",
                            help="ไม่ต้องคุยกับเว็บรอบนี้ (ทำงานกับคลังในเครื่องล้วน)")

    p = sub.add_parser("plan", help="เช็คว่ามีในคลังยัง + จอง + ดึงภาพ + พิมพ์งานให้ sub-agent")
    p.add_argument("book_id")
    p.add_argument("pages", help="เช่น 80 หรือ 77-81 หรือ 77,80,86")
    p.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    p.add_argument("--batch", type=int, default=DEFAULT_BATCH,
                   help="กี่หน้าต่อ sub-agent 1 ตัว (ค่าเริ่มต้น %d) — ยิ่งมาก ยิ่งหารค่า"
                        " cache write ได้มาก แต่ context ของ agent ก็ยิ่งพอก" % DEFAULT_BATCH)
    add_local(p)

    f = sub.add_parser("file", help="ตรวจผลที่ agent เขียน + เก็บเข้าคลัง + ส่งขึ้นเว็บ")
    f.add_argument("paths", nargs="+")
    f.add_argument("--model", default="claude-opus-5")
    f.add_argument("--dry-run", action="store_true")
    f.add_argument("--no-push", action="store_true", help="เก็บเข้าคลังในเครื่องอย่างเดียว")
    add_local(f)

    s = sub.add_parser("status", help="หน้าที่มีในคลัง (เครื่อง + เว็บ)")
    s.add_argument("book_id")
    add_local(s)

    pu = sub.add_parser("pull", help="ดึงหน้าที่คนอื่นถอดไว้แล้วลงเครื่อง")
    pu.add_argument("book_id")
    pu.add_argument("pages", nargs="?", default=None, help="เว้นว่าง = ทุกหน้าที่เว็บมี")
    pu.add_argument("--force", action="store_true", help="ทับหน้าที่มีในเครื่องแล้ว")

    ph = sub.add_parser("push", help="ส่งหน้าในเครื่องขึ้นเว็บ (ของค้างคิว หรือ --all)")
    ph.add_argument("book_id", nargs="?", default=None)
    ph.add_argument("--all", action="store_true", dest="all_pages",
                    help="ส่งทุกหน้าที่ถอดไว้ในเครื่อง ไม่ใช่แค่ที่ค้างคิว")
    ph.add_argument("--dry-run", action="store_true")

    a = ap.parse_args()
    if a.cmd == "plan":
        return cmd_plan(a.book_id, a.pages, a.width, a.batch, a.local)
    if a.cmd == "file":
        return cmd_file(a.paths, a.model, a.dry_run, a.local, a.no_push)
    if a.cmd == "pull":
        return cmd_pull(a.book_id, a.pages, a.force)
    if a.cmd == "push":
        return cmd_push(a.book_id, a.all_pages, a.dry_run)
    return cmd_status(a.book_id, a.local)


if __name__ == "__main__":
    sys.exit(main())
