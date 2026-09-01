# -*- coding: utf-8 -*-
"""
bookscan_common.py — โครงสร้างร่วมของระบบ BookScan (หนังสือเรียน/คู่มือครู สสวท. ที่เป็นภาพสแกน)

โครงสร้างโฟลเดอร์
    BookScan/<Subject>/<Grade>/<ชื่อไฟล์>.pdf     เช่น BookScan/Math/M.1/หนังสือเรียน....pdf
    BookScan/<Subject>/<Grade>/bookscan_index.json   (track git — ไฟล์เล็ก)
    BookScan/<Subject>/<Grade>/.cache/               (gitignored — หน้าที่ดึงมาแล้ว)

ข้อเท็จจริงสำคัญของไฟล์ชุดนี้ (ตรวจด้วย PyMuPDF แล้ว)
    - เป็น **ภาพสแกนล้วน** — ไม่มี text layer และไม่มี TOC ฝังใน PDF
    - 1 หน้า = 1 ภาพ JPEG เต็มหน้า -> ดึงด้วย extract_image() ได้ไฟล์ต้นฉบับ ไม่ต้อง re-render
    - จึงต้อง index จาก **หน้าสารบัญ** (อ่านด้วยสายตา/vision) แล้วเก็บ pageOffset ไว้แปลง
      เลขหน้าพิมพ์ <-> เลขหน้า PDF

ใช้ Python 3.12: %LOCALAPPDATA%\\Programs\\Python\\Python312\\python.exe
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _root import BOOKSCAN_ROOT as _BOOKSCAN_ROOT  # noqa: E402

BOOKSCAN_ROOT = str(_BOOKSCAN_ROOT)
INDEX_NAME = "bookscan_index.json"
CACHE_DIR = ".cache"


def scan_dir(subject, grade):
    """โฟลเดอร์ของ (วิชา, ระดับชั้น) เช่น scan_dir('Math', 'M.1')"""
    return os.path.join(BOOKSCAN_ROOT, subject, grade)


def index_path(subject, grade):
    return os.path.join(scan_dir(subject, grade), INDEX_NAME)


def cache_dir(subject, grade):
    return os.path.join(scan_dir(subject, grade), CACHE_DIR)


def load_index(subject, grade):
    p = index_path(subject, grade)
    if not os.path.exists(p):
        raise FileNotFoundError(
            "ยังไม่มี %s — รัน bookscan_index.py build ก่อน" % p)
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def save_index(subject, grade, data):
    p = index_path(subject, grade)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return p


def list_pdfs(subject, grade):
    d = scan_dir(subject, grade)
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith(".pdf"))


def find_book(index, book_id):
    """หาเล่มจาก id (เช่น 'book1') หรือจากบางส่วนของชื่อไฟล์"""
    books = index.get("books") or []
    for b in books:
        if b.get("id") == book_id:
            return b
    low = (book_id or "").lower()
    for b in books:
        if low and low in (b.get("file") or "").lower():
            return b
    raise KeyError("ไม่พบเล่ม %r — เล่มที่มี: %s"
                   % (book_id, ", ".join(b.get("id", "?") for b in books)))


def offset_for(book, printed_page):
    """offset ที่ใช้กับหน้าพิมพ์นี้

    offset **ไม่คงที่ทั้งเล่ม** (มีหน้าแทรกกลางเล่ม) จึงเก็บเป็นจุดสอบเทียบหลายจุด:
        "offsets": [ {"fromPrinted": 1, "offset": 0}, {"fromPrinted": 150, "offset": 1} ]
    ใช้จุดที่ fromPrinted มากที่สุดที่ยังไม่เกินหน้าที่ขอ
    (รองรับ "pageOffset" ตัวเลขเดี่ยวแบบเก่าด้วย)
    """
    pts = book.get("offsets")
    if not pts:
        return int(book.get("pageOffset", 0))
    p = int(printed_page)
    best = None
    for pt in sorted(pts, key=lambda x: int(x.get("fromPrinted", 1))):
        if int(pt.get("fromPrinted", 1)) <= p:
            best = pt
        else:
            break
    return int((best or pts[0]).get("offset", 0))


def offset_is_exact(book, printed_page):
    """True ถ้าหน้าที่ขออยู่ในช่วงที่สอบเทียบไว้แล้วจริง (ไม่ได้เดาจากช่วงถัดไป)"""
    pts = book.get("offsets") or []
    if not pts:
        return "pageOffset" in book
    p = int(printed_page)
    return any(int(pt.get("fromPrinted", 1)) <= p for pt in pts)


def printed_to_pdf(book, printed_page):
    """เลขหน้าที่พิมพ์บนหน้ากระดาษ -> เลขหน้าใน PDF (1-based)"""
    return int(printed_page) + offset_for(book, printed_page)


def pdf_to_printed(book, pdf_page):
    """ประมาณเลขหน้าพิมพ์จากเลขหน้า PDF (ใช้ offset ของช่วงที่ใกล้ที่สุด)"""
    guess = int(pdf_page)
    for _ in range(3):  # ลู่เข้าเร็วมากเพราะ offset ต่างกันแค่ 1-2
        guess = int(pdf_page) - offset_for(book, guess)
    return guess


def parse_page_range(spec):
    """'122' | '122-125' | '3,7,10-12' -> [122] / [122..125] / [3,7,10,11,12]"""
    out = []
    for part in str(spec).replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part[1:]:
            i = part.index("-", 1)
            a, b = int(part[:i]), int(part[i + 1:])
            step = 1 if b >= a else -1
            out.extend(range(a, b + step, step))
        else:
            out.append(int(part))
    return out


def is_scanned(book, printed_page):
    """หน้าพิมพ์นี้อยู่ในไฟล์ที่สแกนมาจริงหรือไม่

    บางเล่มสแกนมาไม่เต็ม (`"partial": true`) index จึงเก็บช่วงหน้าพิมพ์ที่มีจริงไว้ที่
        "scannedPrinted": [[77, 101]]
    เล่มที่ไม่ระบุ = ถือว่าสแกนครบทั้งเล่ม
    """
    ranges = book.get("scannedPrinted")
    if not ranges:
        return True
    p = int(printed_page)
    return any(int(a) <= p <= int(b) for a, b in ranges)


def scanned_summary(book):
    """ข้อความสั้นบอกช่วงหน้าพิมพ์ที่สแกนมา ('' ถ้าครบทั้งเล่ม)"""
    ranges = book.get("scannedPrinted")
    if not ranges:
        return ""
    return ", ".join("%s-%s" % (a, b) for a, b in ranges)
