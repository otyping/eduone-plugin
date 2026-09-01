# -*- coding: utf-8 -*-
"""
bookscan_index.py — สารบัญค้นได้ของหนังสือสแกน (BookScan)

ไฟล์ BookScan เป็นภาพสแกนล้วน ไม่มี text layer จึงค้นด้วยข้อความไม่ได้
สคริปต์นี้ใช้ index ที่ถอดจาก **หน้าสารบัญ** (bookscan_index.json) เป็นทางลัด
ให้คนเขียนเนื้อหา/ออกข้อสอบ **หาหน้าที่ต้องการได้โดยไม่ต้องเปิดอ่านทุกหน้า**

คำสั่ง
  bookscan_index.py show                      แสดงสารบัญทั้งหมด
  bookscan_index.py books                     แสดงรายชื่อเล่ม + จำนวนหน้า + จุดสอบเทียบ
  bookscan_index.py find <คำค้น>              ค้นบท/หัวข้อ -> เลขหน้าพิมพ์ + หน้า PDF + คำสั่งดึงหน้า
  bookscan_index.py init                      สร้างโครง index จาก PDF ที่มี (ให้เติมสารบัญเอง)
  bookscan_index.py calibrate <book> <พิมพ์> <pdf>   เพิ่มจุดสอบเทียบ offset

ตัวเลือกร่วม: --subject Math --grade M.1

หมายเหตุเรื่อง offset: หนังสือชุดนี้ **มีหน้าแทรกกลางเล่ม** offset จึงไม่คงที่
index เก็บเป็นจุดสอบเทียบหลายจุด (`offsets`) ถ้าเจอหน้าคลาดเคลื่อน ±1
ให้ดึงหน้าข้างเคียงเพิ่ม แล้ว `calibrate` บันทึกค่าที่ถูกไว้

รันผ่านตัวห่อ: eduone-py <ชื่อไฟล์นี้> <args>  (หา Python 3.12 ให้เองทุก OS)
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bookscan_common as bc  # noqa: E402


def iter_entries(index):
    """ไล่ทุกบท/หัวข้อ -> (book, kind, label, printed_page)"""
    for book in index.get("books") or []:
        for ch in book.get("chapters") or []:
            yield book, "บท", ch.get("title", ""), ch.get("page")
            for s in ch.get("sections") or []:
                yield book, "หัวข้อ", "%s %s" % (s.get("no", ""), s.get("title", "")), s.get("page")
        for extra in book.get("extras") or []:
            yield book, "อื่น ๆ", extra.get("title", ""), extra.get("page")


def fmt_hit(book, kind, label, printed, subject, grade):
    if not bc.is_scanned(book, printed):
        return (
            "  [%s] %-6s %-58s หน้าพิมพ์ %-4s -> ⚠ ไม่ได้สแกนมา\n"
            "        เล่มนี้มีเฉพาะหน้าพิมพ์ %s"
            % (book.get("id", "?"), kind, label.strip(), printed,
               bc.scanned_summary(book))
        )
    pdf = bc.printed_to_pdf(book, printed)
    exact = bc.offset_is_exact(book, printed)
    mark = "" if exact else "  (offset ประมาณ ±1)"
    return (
        "  [%s] %-6s %-58s หน้าพิมพ์ %-4s -> PDF %-4s%s\n"
        "        ดึงหน้า: bookscan_page.py %s %s-%s --subject %s --grade %s"
        % (book.get("id", "?"), kind, label.strip(), printed, pdf, mark,
           book.get("id", "?"), printed, int(printed) + 2, subject, grade)
    )


def cmd_show(index, args):
    print("# %s %s — สารบัญ" % (index.get("subject", ""), index.get("grade", "")))
    for book in index.get("books") or []:
        print("\n## %s — %s  (%d หน้า PDF)"
              % (book.get("id"), book.get("title", book.get("file", "")), book.get("pages", 0)))
        summary = bc.scanned_summary(book)
        if summary:
            print("   ⚠ สแกนไม่เต็มเล่ม — มีเฉพาะหน้าพิมพ์ %s (บรรทัดที่ขึ้น ✗ คือไม่มีไฟล์)"
                  % summary)

        def mark(page):
            if not summary or page is None:
                return " "
            return "✓" if bc.is_scanned(book, page) else "✗"

        for ch in book.get("chapters") or []:
            print("%s %-52s หน้า %s" % (mark(ch.get("page")), ch.get("title", ""), ch.get("page")))
            for s in ch.get("sections") or []:
                print("%s     %-6s %-42s หน้า %s"
                      % (mark(s.get("page")), s.get("no", ""), s.get("title", ""), s.get("page")))
        for extra in book.get("extras") or []:
            print("%s %-52s หน้า %s" % (mark(extra.get("page")), extra.get("title", ""), extra.get("page")))
    return 0


def cmd_books(index, args):
    for book in index.get("books") or []:
        print("%s  %-46s  %d หน้า" % (book.get("id"), book.get("file", "")[:46], book.get("pages", 0)))
        for pt in book.get("offsets") or []:
            print("      offset %+d ตั้งแต่หน้าพิมพ์ %s" % (pt.get("offset", 0), pt.get("fromPrinted")))
        if book.get("offsetNote"):
            print("      หมายเหตุ: %s" % book["offsetNote"])
    return 0


def cmd_find(index, args):
    q = args.query.strip().lower()
    if not q:
        print("ต้องระบุคำค้น", file=sys.stderr)
        return 2
    hits = []
    for book, kind, label, page in iter_entries(index):
        if page is None:
            continue
        if q in label.lower():
            hits.append((book, kind, label, page))
    if not hits:
        print("ไม่พบ %r ในสารบัญ — ลองคำสั้นลง หรือ `show` เพื่อดูทั้งหมด" % args.query)
        return 1
    print("พบ %d รายการสำหรับ %r:\n" % (len(hits), args.query))
    for book, kind, label, page in hits:
        print(fmt_hit(book, kind, label, page, index.get("subject"), index.get("grade")))
    return 0


def cmd_init(args):
    pdfs = bc.list_pdfs(args.subject, args.grade)
    if not pdfs:
        print("ไม่พบ PDF ใน %s" % bc.scan_dir(args.subject, args.grade), file=sys.stderr)
        return 1
    try:
        import fitz
    except ImportError:
        print("ต้องมี PyMuPDF", file=sys.stderr)
        return 2
    books = []
    for i, p in enumerate(pdfs, start=1):
        d = fitz.open(p)
        books.append({
            "id": "book%d" % i,
            "file": os.path.basename(p),
            "title": os.path.splitext(os.path.basename(p))[0],
            "pages": d.page_count,
            "offsets": [{"fromPrinted": 1, "offset": 0}],
            "offsetNote": "ยังไม่ได้สอบเทียบ — ดึงหน้าด้วย --pdf-page แล้วรัน calibrate",
            "chapters": [],
            "extras": [],
        })
        d.close()
    data = {"subject": args.subject, "grade": args.grade,
            "note": "สารบัญถอดจากหน้าสารบัญของหนังสือ (ไฟล์เป็นภาพสแกน ไม่มี text layer)",
            "books": books}
    p = bc.save_index(args.subject, args.grade, data)
    print("เขียนโครง index -> %s (เติมสารบัญเองต่อ)" % p)
    return 0


def cmd_calibrate(index, args):
    book = bc.find_book(index, args.book)
    offset = int(args.pdf_page) - int(args.printed_page)
    pts = book.setdefault("offsets", [])
    for pt in pts:
        if int(pt.get("fromPrinted", 1)) == int(args.printed_page):
            pt["offset"] = offset
            break
    else:
        pts.append({"fromPrinted": int(args.printed_page), "offset": offset})
    pts.sort(key=lambda x: int(x.get("fromPrinted", 1)))
    bc.save_index(index["subject"], index["grade"], index)
    print("บันทึก: หน้าพิมพ์ %s = PDF %s -> offset %+d (เล่ม %s)"
          % (args.printed_page, args.pdf_page, offset, book.get("id")))
    return 0


def main():
    ap = argparse.ArgumentParser(description="สารบัญค้นได้ของหนังสือสแกน")
    ap.add_argument("command", choices=["show", "books", "find", "init", "calibrate"])
    ap.add_argument("query", nargs="?", default="")
    ap.add_argument("printed_page", nargs="?", default=None)
    ap.add_argument("pdf_page", nargs="?", default=None)
    ap.add_argument("--subject", default="Math")
    ap.add_argument("--grade", default="M.1")
    args = ap.parse_args()

    if args.command == "init":
        return cmd_init(args)

    try:
        index = bc.load_index(args.subject, args.grade)
    except FileNotFoundError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1

    if args.command == "show":
        return cmd_show(index, args)
    if args.command == "books":
        return cmd_books(index, args)
    if args.command == "find":
        return cmd_find(index, args)
    if args.command == "calibrate":
        if not (args.query and args.printed_page and args.pdf_page):
            print("ใช้: bookscan_index.py calibrate <book> <หน้าพิมพ์> <หน้าPDF>", file=sys.stderr)
            return 2
        args.book = args.query
        return cmd_calibrate(index, args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
