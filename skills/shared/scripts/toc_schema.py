"""ตรวจสารบัญหนังสือสแกน (bookscan_index.json) — ★ ตัวตรวจชุดเดียวของทั้งระบบ

ใช้สองฝั่ง:
  · เซิร์ฟเวอร์  `PUT /api/books/<id>/toc` เรียกก่อนเก็บลงฐานข้อมูล
  · เครื่องพนักงาน `docs/rag/validate_toc.py` เรียกก่อนส่งขึ้นเซิร์ฟเวอร์

★ **ต้นฉบับอยู่ที่นี่ (ปลั๊กอิน) ตั้งแต่ 3.4.0** — `webapp/app/toc_schema.py` เป็น *สำเนา*
  ที่ `webapp/scripts/sync_from_plugin.py` คัดลอกมา แก้ที่นี่ที่เดียวแล้ว sync
  (ก่อนหน้านี้ webapp เป็นเจ้าของ แล้วสคริปต์ฝั่งเครื่อง import ข้ามเข้าไป —
   ซึ่งบังคับให้ทุกเครื่องที่จะถอดหนังสือต้องมี repo ของเว็บติดไปด้วย)
  `sync_from_plugin.py --check` ฟ้องทันทีถ้าสองฝั่งไม่ตรงกัน

ทำไมต้องชุดเดียว: ถ้าสองฝั่งตรวจคนละกฎ พนักงานจะเจอ "ในเครื่องผ่าน แต่เซิร์ฟเวอร์ปฏิเสธ"
โดยไม่มีทางรู้ว่ากฎไหนต่าง — เสียเวลาถอดใหม่ทั้งเล่ม

ทำไมไฟล์นี้อยู่ใน `app/`: Dockerfile คัดลอกแค่ `app/` กับ `reference/` เข้าคอนเทนเนอร์
ฝั่ง CLI จึงเป็นตัวห่อบาง ๆ ที่ import ไฟล์นี้ตาม path (ไม่ใช่กลับกัน)
เพราะเหตุนี้ไฟล์นี้ต้องเป็น **stdlib ล้วน** — ห้าม import fastapi/minio/db

สองระดับที่ตรวจ:
  check_index(data)      ไฟล์ bookscan_index.json ทั้งไฟล์ (หลายเล่ม) — ของเดิมที่ทำมือต้องผ่าน
  check_extraction(data) ผลถอดสารบัญ 1 เล่มจาก agent — เข้มกว่า เพราะบังคับจุดสอบเทียบ

★ กฎที่เข้มที่สุดคือ **offsets ต้องอธิบาย probe ได้ทุกจุด** — `printed_to_pdf(probe.printed_seen)`
  ต้องเท่ากับหน้า PDF ที่ agent เห็นเลขนั้นจริง ๆ · จุดสอบเทียบที่ไม่มีใครเห็นด้วยตา
  คือจุดที่เดามา และเดาผิด 1 หน้าแปลว่าทุกงานที่อ้างเล่มนี้หยิบหน้าผิดไปทั้งหมด
"""
from __future__ import annotations

import re

SCHEMA_VERSION = "toc-v0.1"

#: ระดับปัญหา — ERROR = ไม่รับ, WARN = รับแต่ต้องมีคนดู
ERROR = "ERROR"
WARN = "WARN"

GRADE_RE = re.compile(r"^[PM]\.[1-6]$")           # P.4 · M.1
SUBJECT_RE = re.compile(r"^[A-Z][A-Za-z]{1,15}$")  # Math · Sci · Eng (ชื่อโฟลเดอร์ BookScan)
BOOK_ID_RE = re.compile(r"^[a-z]+[0-9]+$")         # book1 · teacher2 · workbook1
KNOWN_ROLES = {"student", "teacher", "workbook", "other"}


class Problem:
    """ปัญหา 1 ข้อ — เก็บ path ไว้ด้วยเพื่อให้คนแก้รู้ว่าอยู่ตรงไหนของไฟล์"""

    __slots__ = ("level", "where", "msg")

    def __init__(self, level: str, where: str, msg: str) -> None:
        self.level, self.where, self.msg = level, where, msg

    def __str__(self) -> str:
        return f"{self.level:5s} {self.where}: {self.msg}"

    def as_dict(self) -> dict:
        return {"level": self.level, "where": self.where, "msg": self.msg}


def has_error(problems: list[Problem]) -> bool:
    return any(p.level == ERROR for p in problems)


# ---------------- ตัวช่วยเรื่องเลขหน้า ----------------
# สำเนาของ bookscan_common.py ในปลั๊กอิน — คัดลอกมาเพราะคอนเทนเนอร์ไม่มีปลั๊กอิน
# (ตั้งใจให้เป็นสำเนาสุดท้าย: ฝั่ง docs/rag import จากไฟล์นี้ ไม่เขียนซ้ำอีกชุด)

def printed_to_pdf(book: dict, printed: int) -> int:
    """เลขหน้าที่พิมพ์บนกระดาษ -> เลขหน้าใน PDF ตามจุดสอบเทียบที่ใกล้ที่สุดจากด้านล่าง"""
    offset = 0
    for pt in sorted(book.get("offsets") or [], key=lambda x: _int(x.get("fromPrinted"), 0)):
        if printed >= _int(pt.get("fromPrinted"), 0):
            offset = _int(pt.get("offset"), 0)
    return printed + offset


def is_scanned(book: dict, printed: int) -> bool:
    """หน้านี้มีไฟล์ให้ดึงจริงไหม — เล่มที่สแกนครบถือว่ามีทุกหน้า"""
    if not book.get("partial"):
        return True
    for rng in book.get("scannedPrinted") or []:
        lo, hi = _range(rng)
        if lo is not None and lo <= printed <= hi:
            return True
    return False


def _int(value, default=None):
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    return default


def _range(rng):
    if isinstance(rng, (list, tuple)) and len(rng) == 2:
        lo, hi = _int(rng[0]), _int(rng[1])
        if lo is not None and hi is not None:
            return lo, hi
    return None, None


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def book_id_of(subject: str, grade: str, book_key: str) -> str:
    """<grade>-<subject>-<book> ตาม RAG-PLAN ข้อ 3.8 — M.1/Math/book1 -> m1-math-book1"""
    return "%s-%s-%s" % (grade.replace(".", "").strip().lower(),
                         subject.strip().lower(), book_key)


# ---------------- ชื่อเรียกชั้น/วิชา 3 แบบที่ต้องแปลงไปมา ----------------
# เว็บใช้ subject_slug ตาม reference/subjects.txt (`english`)
# BookScan ใช้ชื่อโฟลเดอร์ Title-case (`Eng`)
# คลัง RAG ใช้ท่อนกลางของ book_id ซึ่งมาจากชื่อโฟลเดอร์ (`p4-eng-book1`)
#
# ★ `english` กับ `eng` คือคู่เดียวที่ไม่ตรงกันตรง ๆ และเป็นกับดักจริง: ถ้าเว็บออก book_id
#   เป็น `p4-english-book1` เล่มเดียวกันจะกลายเป็นคนละเล่มกับที่ทั้งคลังและ retrieval-eval.json
#   ใช้อยู่ โดยไม่มีอะไรฟ้อง — ตารางนี้จึงเป็นจุดเดียวที่ตัดสินเรื่องนี้
SUBJECT_FOLDER = {
    "thai": "Thai", "math": "Math", "sci": "Sci", "social": "Social",
    "health": "Health", "art": "Art", "career": "Career", "english": "Eng",
}
_FOLDER_SUBJECT = {v.lower(): k for k, v in SUBJECT_FOLDER.items()}


def folder_of_subject(subject_slug: str) -> str:
    """subject_slug ของเว็บ -> ชื่อโฟลเดอร์ BookScan (english -> Eng)"""
    slug = (subject_slug or "").strip().lower()
    return SUBJECT_FOLDER.get(slug, slug.capitalize())


def subject_of_folder(folder: str) -> str:
    """ชื่อโฟลเดอร์ BookScan -> subject_slug ของเว็บ (Eng -> english)"""
    key = (folder or "").strip().lower()
    return _FOLDER_SUBJECT.get(key, key)


def folder_of_grade(grade_slug: str) -> str:
    """m1 -> M.1"""
    slug = (grade_slug or "").strip().lower()
    return "%s.%s" % (slug[:1].upper(), slug[1:]) if len(slug) >= 2 else slug.upper()


def grade_of_folder(grade: str) -> str:
    """M.1 -> m1"""
    return (grade or "").replace(".", "").strip().lower()


# ---------------- ตรวจไฟล์ index ทั้งไฟล์ ----------------

def check_index(data) -> list[Problem]:
    """ตรวจ bookscan_index.json ทั้งไฟล์ (มีได้หลายเล่ม)

    เล่มที่ยังไม่ได้ถอดสารบัญ (`chapters: []`) ถือว่าผ่าน — teacher1/teacher2 ของ ม.1
    อยู่ในสภาพนั้นมาตั้งแต่ต้น ตัวตรวจนี้ต้องไม่ไปบังคับให้ถอดก่อนถึงจะบันทึกไฟล์ได้
    """
    problems: list[Problem] = []
    if not isinstance(data, dict):
        return [Problem(ERROR, "(ราก)", "ต้องเป็นอ็อบเจกต์ JSON")]

    subject, grade = _text(data.get("subject")), _text(data.get("grade"))
    if not SUBJECT_RE.match(subject):
        problems.append(Problem(ERROR, "subject",
                                "ต้องเป็นชื่อโฟลเดอร์ BookScan เช่น Math/Sci/Eng (ได้ %r)" % data.get("subject")))
    if not GRADE_RE.match(grade):
        problems.append(Problem(ERROR, "grade",
                                "ต้องอยู่ในรูป P.4 หรือ M.1 (ได้ %r)" % data.get("grade")))

    books = data.get("books")
    if not isinstance(books, list) or not books:
        problems.append(Problem(ERROR, "books", "ต้องมีอย่างน้อย 1 เล่ม"))
        return problems

    seen: set[str] = set()
    for i, book in enumerate(books):
        where = "books[%d]" % i
        if not isinstance(book, dict):
            problems.append(Problem(ERROR, where, "ต้องเป็นอ็อบเจกต์"))
            continue
        key = _text(book.get("id"))
        if key:
            where = "books[%s]" % key
            if key in seen:
                problems.append(Problem(ERROR, where, "id ซ้ำกับเล่มก่อนหน้าในไฟล์เดียวกัน"))
            seen.add(key)
        problems += check_book(book, where)
    return problems


def check_book(book: dict, where: str) -> list[Problem]:
    """ตรวจ 1 เล่มในไฟล์ index — ใช้ร่วมกันทั้งสองระดับ"""
    problems: list[Problem] = []

    key = _text(book.get("id"))
    if not BOOK_ID_RE.match(key):
        problems.append(Problem(ERROR, where + ".id",
                                "ต้องเป็น <ประเภท><เล่ม> เช่น book1/teacher2 (ได้ %r)" % book.get("id")))
    if not _text(book.get("file")):
        problems.append(Problem(ERROR, where + ".file", "ต้องมีชื่อไฟล์ PDF"))
    if not _text(book.get("title")):
        problems.append(Problem(WARN, where + ".title", "ไม่มีชื่อหนังสือ — หน้าเว็บจะแสดงเป็นช่องว่าง"))

    role = _text(book.get("role"))
    if role and role not in KNOWN_ROLES:
        problems.append(Problem(WARN, where + ".role",
                                "role ไม่รู้จัก %r (ที่ใช้กันคือ %s)" % (role, "/".join(sorted(KNOWN_ROLES)))))

    pages = _int(book.get("pages"))
    if pages is None or pages < 1:
        problems.append(Problem(ERROR, where + ".pages", "จำนวนหน้า PDF ต้องเป็นจำนวนเต็ม ≥ 1"))

    problems += _check_offsets(book, where)
    problems += _check_scanned_ranges(book, where)
    problems += _check_entries(book, where, pages)
    return problems


def _check_offsets(book: dict, where: str) -> list[Problem]:
    problems: list[Problem] = []
    offsets = book.get("offsets")
    if not isinstance(offsets, list) or not offsets:
        problems.append(Problem(ERROR, where + ".offsets",
                                "ต้องมีจุดสอบเทียบอย่างน้อย 1 จุด — ไม่งั้นแปลงเลขหน้าพิมพ์เป็นหน้า PDF ไม่ได้"))
        return problems

    seen_from: set[int] = set()
    for i, pt in enumerate(offsets):
        at = "%s.offsets[%d]" % (where, i)
        if not isinstance(pt, dict):
            problems.append(Problem(ERROR, at, "ต้องเป็นอ็อบเจกต์ {fromPrinted, offset}"))
            continue
        frm, off = _int(pt.get("fromPrinted")), _int(pt.get("offset"))
        if frm is None or frm < 1:
            problems.append(Problem(ERROR, at + ".fromPrinted", "ต้องเป็นจำนวนเต็ม ≥ 1"))
        elif frm in seen_from:
            problems.append(Problem(ERROR, at + ".fromPrinted",
                                    "หน้าพิมพ์ %d มีจุดสอบเทียบซ้ำ — ค่าไหนถูกไม่มีทางรู้" % frm))
        else:
            seen_from.add(frm)
        if off is None:
            problems.append(Problem(ERROR, at + ".offset", "ต้องเป็นจำนวนเต็ม"))
    return problems


def _check_scanned_ranges(book: dict, where: str) -> list[Problem]:
    problems: list[Problem] = []
    partial = book.get("partial")
    ranges = book.get("scannedPrinted")

    if not partial:
        if ranges:
            problems.append(Problem(WARN, where + ".scannedPrinted",
                                    "มีช่วงที่สแกนทั้งที่ไม่ได้ตั้ง partial — เครื่องมือจะถือว่าเล่มนี้ครบทั้งเล่ม"))
        return problems

    if not isinstance(ranges, list) or not ranges:
        problems.append(Problem(ERROR, where + ".scannedPrinted",
                                "เล่ม partial ต้องบอกช่วงหน้าพิมพ์ที่สแกนมาจริง เช่น [[77, 101]]"))
        return problems

    spans = []
    for i, rng in enumerate(ranges):
        lo, hi = _range(rng)
        if lo is None:
            problems.append(Problem(ERROR, "%s.scannedPrinted[%d]" % (where, i),
                                    "ต้องเป็น [หน้าเริ่ม, หน้าจบ] ที่เป็นจำนวนเต็มทั้งคู่"))
            continue
        if lo > hi:
            problems.append(Problem(ERROR, "%s.scannedPrinted[%d]" % (where, i),
                                    "หน้าเริ่ม %d มากกว่าหน้าจบ %d" % (lo, hi)))
            continue
        spans.append((lo, hi, i))

    for (lo, hi, i), (lo2, hi2, j) in zip(sorted(spans), sorted(spans)[1:]):
        if lo2 <= hi:
            problems.append(Problem(WARN, "%s.scannedPrinted[%d]" % (where, j),
                                    "ช่วง %d-%d ทับกับช่วง %d-%d" % (lo2, hi2, lo, hi)))
    return problems


#: ชนิดรายการในสารบัญ -> ชื่อไทยที่ใช้ในข้อความแจ้งปัญหา
KINDS = {"chapter": "บท", "section": "หัวข้อ", "extra": "รายการท้ายเล่ม"}


def _iter_entries(book: dict):
    """ไล่ทุกบท/หัวข้อ/รายการท้ายเล่ม -> (where, entry, kind, effective_scanned)

    `scanned` ของหัวข้อสืบทอดจากบทถ้าไม่ได้ระบุเอง — ตรงกับที่ bm25_index.py อ่าน
    (`sec.get("scanned", ch.get("scanned"))`) ถ้าตรงนี้ตีความต่างกัน ดัชนีจะบอกสถานะหน้าผิด
    """
    for ci, ch in enumerate(book.get("chapters") or []):
        if not isinstance(ch, dict):
            yield "chapters[%d]" % ci, ch, "chapter", None
            continue
        ch_scanned = ch.get("scanned")
        yield "chapters[%d]" % ci, ch, "chapter", ch_scanned
        for si, sec in enumerate(ch.get("sections") or []):
            scanned = sec.get("scanned", ch_scanned) if isinstance(sec, dict) else None
            yield "chapters[%d].sections[%d]" % (ci, si), sec, "section", scanned
    for ei, extra in enumerate(book.get("extras") or []):
        scanned = extra.get("scanned") if isinstance(extra, dict) else None
        yield "extras[%d]" % ei, extra, "extra", scanned


def _check_entries(book: dict, where: str, pages: int | None) -> list[Problem]:
    problems: list[Problem] = []
    partial = bool(book.get("partial"))

    for sub, entry, kind, scanned in _iter_entries(book):
        at = "%s.%s" % (where, sub)
        label = KINDS[kind]
        if not isinstance(entry, dict):
            problems.append(Problem(ERROR, at, "ต้องเป็นอ็อบเจกต์"))
            continue
        if not _text(entry.get("title")):
            problems.append(Problem(ERROR, at + ".title", "%s ไม่มีชื่อ — ค้นไม่เจอแน่นอน" % label))

        page = _int(entry.get("page"))
        if page is None or page < 1:
            # สารบัญจริงบางเล่มมีบรรทัดท้ายเล่มที่ไม่พิมพ์เลขหน้าไว้ (เช่น 'คณะผู้จัดทำ')
            # ยอมให้ page เป็น null เฉพาะ extras — เครื่องมือค้นข้ามรายการที่ไม่มีหน้าอยู่แล้ว
            # แต่บท/หัวข้อไม่มีเลขหน้า = สารบัญใช้ไม่ได้ตามวัตถุประสงค์
            if kind == "extra" and entry.get("page") is None:
                if not _text(entry.get("note")):
                    problems.append(Problem(WARN, at,
                                            "ไม่มีเลขหน้าและไม่ได้บอกเหตุผล — ใส่ note ว่าทำไมถึงไม่มี"))
            else:
                problems.append(Problem(ERROR, at + ".page",
                                        "เลขหน้าพิมพ์ต้องเป็นจำนวนเต็ม ≥ 1 (ได้ %r)" % entry.get("page")))
            continue

        if scanned is True and partial and not is_scanned(book, page):
            problems.append(Problem(ERROR, at,
                                    "ตั้ง scanned: true แต่หน้า %d อยู่นอก scannedPrinted" % page))
        if scanned is False and partial and is_scanned(book, page):
            problems.append(Problem(ERROR, at,
                                    "ตั้ง scanned: false แต่หน้า %d อยู่ใน scannedPrinted" % page))
        if partial and scanned is None:
            problems.append(Problem(WARN, at,
                                    "เล่ม partial แต่ %s นี้ไม่ได้บอกว่าสแกนมาหรือยัง" % label))

        # หน้าที่สแกนมาแล้วต้องแปลงเป็นหน้า PDF ที่มีอยู่จริง — หน้าที่ยังไม่ได้สแกน
        # ปล่อยผ่าน เพราะสารบัญเก็บครบทั้งเล่มไว้อ้างอิงโครงสร้างโดยตั้งใจ
        if pages and is_scanned(book, page):
            pdf = printed_to_pdf(book, page)
            if not (1 <= pdf <= pages):
                problems.append(Problem(ERROR, at,
                                        "หน้าพิมพ์ %d -> หน้า PDF %d ซึ่งอยู่นอกช่วง 1-%d ของไฟล์"
                                        % (page, pdf, pages)))

    problems += _check_order(book, where)
    return problems


def _check_order(book: dict, where: str) -> list[Problem]:
    """เลขหน้าของบท/หัวข้อต้องเดินหน้าเสมอ

    ไม่ตรวจ extras ด้วยเจตนา — สารบัญต้นฉบับบางเล่มพิมพ์เลขหน้าท้ายเล่มสลับกันจริง
    (ดู `แบบทดสอบท้ายเล่ม` ของวิทย์ ป.4) ถ้าบังคับเรียง จะกลายเป็นบังคับให้แก้ข้อมูลให้ผิด
    """
    problems: list[Problem] = []
    prev_page, prev_label = None, None
    for ci, ch in enumerate(book.get("chapters") or []):
        if not isinstance(ch, dict):
            continue
        items = [("chapters[%d]" % ci, ch)]
        items += [("chapters[%d].sections[%d]" % (ci, si), s)
                  for si, s in enumerate(ch.get("sections") or []) if isinstance(s, dict)]
        for sub, entry in items:
            page = _int(entry.get("page"))
            if page is None:
                continue
            if prev_page is not None and page < prev_page:
                problems.append(Problem(WARN, "%s.%s" % (where, sub),
                                        "หน้า %d ย้อนกลับก่อน %s (หน้า %d) — สารบัญอาจอ่านผิดบรรทัด"
                                        % (page, prev_label, prev_page)))
            prev_page, prev_label = page, sub
    return problems


# ---------------- ตรวจผลถอดสารบัญ 1 เล่ม ----------------

def check_extraction(data) -> list[Problem]:
    """ตรวจสิ่งที่ agent ถอดมา ก่อนเก็บเข้าคลัง/ส่งขึ้นเซิร์ฟเวอร์

    เข้มกว่า check_index 3 เรื่อง เพราะเป็นของใหม่ที่ยังไม่มีใครตรวจด้วยตา:
      1. ต้องมีสารบัญจริง (chapters ว่างไม่ได้)
      2. ต้องบอกว่าอ่านมาจากหน้า PDF ไหน (ย้อนตรวจได้)
      3. ★ ต้องมี probe ≥ 2 จุด และ offsets ต้องอธิบายทุก probe ได้พอดี
    """
    problems: list[Problem] = []
    if not isinstance(data, dict):
        return [Problem(ERROR, "(ราก)", "ต้องเป็นอ็อบเจกต์ JSON")]

    version = _text(data.get("schema_version"))
    if version != SCHEMA_VERSION:
        problems.append(Problem(ERROR, "schema_version",
                                "ต้องเป็น %r (ได้ %r)" % (SCHEMA_VERSION, data.get("schema_version"))))

    subject, grade = _text(data.get("subject")), _text(data.get("grade"))
    if not SUBJECT_RE.match(subject):
        problems.append(Problem(ERROR, "subject", "ต้องเป็นชื่อโฟลเดอร์ BookScan (ได้ %r)" % data.get("subject")))
    if not GRADE_RE.match(grade):
        problems.append(Problem(ERROR, "grade", "ต้องอยู่ในรูป P.4 หรือ M.1 (ได้ %r)" % data.get("grade")))

    book = data.get("book")
    if not isinstance(book, dict):
        return problems + [Problem(ERROR, "book", "ต้องมีอ็อบเจกต์ book (รายการเล่มที่จะ merge เข้า index)")]

    problems += check_book(book, "book")

    expected = book_id_of(subject, grade, _text(book.get("id")))
    if _text(data.get("book_id")) != expected:
        problems.append(Problem(ERROR, "book_id",
                                "ต้องเป็น %r ให้ตรงกับ subject/grade/book.id (ได้ %r)"
                                % (expected, data.get("book_id"))))

    if not (book.get("chapters") or []):
        problems.append(Problem(ERROR, "book.chapters",
                                "ถอดสารบัญแล้วต้องได้อย่างน้อย 1 บท — ถ้าเล่มนี้ไม่มีหน้าสารบัญ "
                                "ให้รายงานเป็น fail พร้อมเหตุผล ไม่ใช่ส่งสารบัญว่าง"))

    problems += _check_toc_pages(data, book)
    problems += _check_probes(data, book)

    conf = data.get("confidence")
    if not isinstance(conf, (int, float)) or isinstance(conf, bool) or not 0 <= conf <= 1:
        problems.append(Problem(ERROR, "confidence", "ต้องเป็นตัวเลข 0-1 ที่ agent ให้มา"))
    elif conf < 0.6:
        problems.append(Problem(WARN, "confidence",
                                "agent ไม่มั่นใจ (%.2f) — ควรมีคนเปิดหน้าสารบัญดูเทียบ" % conf))

    flags = data.get("flags")
    if flags is not None and not isinstance(flags, list):
        problems.append(Problem(ERROR, "flags", "ต้องเป็น list ของข้อความ"))
    elif isinstance(flags, list) and "needs_review" in flags:
        problems.append(Problem(WARN, "flags",
                                "agent ตั้ง needs_review — เก็บได้ แต่ต้องมีคนตามดู"))
    return problems


def _check_toc_pages(data: dict, book: dict) -> list[Problem]:
    problems: list[Problem] = []
    pages = _int(book.get("pages"))
    toc_pages = data.get("tocPdfPages")
    if not isinstance(toc_pages, list) or not toc_pages:
        problems.append(Problem(ERROR, "tocPdfPages",
                                "ต้องบอกว่าถอดมาจากหน้า PDF ไหนบ้าง — ไม่งั้นย้อนตรวจไม่ได้"))
        return problems
    for i, p in enumerate(toc_pages):
        n = _int(p)
        if n is None or n < 1 or (pages and n > pages):
            problems.append(Problem(ERROR, "tocPdfPages[%d]" % i,
                                    "หน้า PDF ต้องอยู่ในช่วง 1-%s (ได้ %r)" % (pages or "?", p)))
    return problems


def _check_probes(data: dict, book: dict) -> list[Problem]:
    """★ หัวใจของการสอบเทียบ — offsets ต้องอธิบายทุกหน้าที่ agent เห็นเลขจริงได้พอดี"""
    problems: list[Problem] = []
    pages = _int(book.get("pages"))
    probes = data.get("probes")
    if not isinstance(probes, list) or len(probes) < 2:
        problems.append(Problem(ERROR, "probes",
                                "ต้องมีจุดที่ agent อ่านเลขหน้าจากกระดาษอย่างน้อย 2 จุด "
                                "(1 จุดแยกไม่ออกว่า offset คงที่หรือเปล่า)"))
        return problems

    for i, probe in enumerate(probes):
        at = "probes[%d]" % i
        if not isinstance(probe, dict):
            problems.append(Problem(ERROR, at, "ต้องเป็นอ็อบเจกต์ {pdf_page, printed_seen}"))
            continue
        pdf = _int(probe.get("pdf_page"))
        seen = _int(probe.get("printed_seen"))
        if pdf is None or pdf < 1 or (pages and pdf > pages):
            problems.append(Problem(ERROR, at + ".pdf_page",
                                    "ต้องอยู่ในช่วง 1-%s (ได้ %r)" % (pages or "?", probe.get("pdf_page"))))
            continue
        if seen is None:
            # หน้าที่ไม่มีเลขพิมพ์ (หน้าเปิดบท/หน้าเปล่า) เป็นเรื่องปกติ — ข้ามไป ไม่ใช่ความผิด
            if "printed_seen" not in probe:
                problems.append(Problem(ERROR, at + ".printed_seen",
                                        "ต้องตอบ — ถ้าหน้านั้นไม่มีเลขพิมพ์ให้ตอบ null"))
            continue
        if seen < 1:
            problems.append(Problem(ERROR, at + ".printed_seen", "เลขหน้าพิมพ์ต้อง ≥ 1 (ได้ %r)" % seen))
            continue

        got = printed_to_pdf(book, seen)
        if got != pdf:
            problems.append(Problem(ERROR, at,
                                    "agent เห็นเลข %d บนหน้า PDF %d แต่ offsets บอกว่าหน้า %d อยู่ที่ PDF %d "
                                    "— จุดสอบเทียบไม่ตรงกับของจริง" % (seen, pdf, seen, got)))
        if bool(book.get("partial")) and not is_scanned(book, seen):
            problems.append(Problem(ERROR, at,
                                    "หน้าพิมพ์ %d เห็นด้วยตาแล้วว่ามีอยู่ แต่กลับอยู่นอก scannedPrinted" % seen))

    readable = sum(1 for p in probes
                   if isinstance(p, dict) and (_int(p.get("printed_seen")) or 0) >= 1)
    if readable < 2:
        problems.append(Problem(ERROR, "probes",
                                "อ่านเลขหน้าจากกระดาษได้ %d จุด — ต้องได้ ≥ 2 จุดถึงจะรู้ว่า offset "
                                "คงที่ทั้งเล่มหรือมีหน้าแทรก (หน้าที่ไม่มีเลขพิมพ์ไม่นับ "
                                "ให้สุ่มหน้าเพิ่มด้วย plan --probe-more)" % readable))
    return problems
