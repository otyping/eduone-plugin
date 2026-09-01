# -*- coding: utf-8 -*-
"""
bookscan_page.py — ดึงหน้าจากหนังสือสแกนออกมาเป็นภาพ ให้ agent เอาไป Read ต่อ

ไฟล์ BookScan เป็นภาพสแกนล้วน (ไม่มี text layer) จึงอ่านได้ทางเดียวคือดูเป็นภาพ
สคริปต์นี้ดึงเฉพาะหน้าที่ต้องการ (ไม่ต้องแตกทั้งเล่ม) แล้วย่อให้พอดีกับการอ่าน

ใช้:
  bookscan_page.py <book> <ช่วงหน้าพิมพ์> [--subject Math] [--grade M.1]
                   [--pdf-page] [--width 1400] [--out DIR]

  bookscan_page.py book1 122-124                 # หน้าพิมพ์ 122-124 (แปลง offset ให้เอง)
  bookscan_page.py book1 8 --pdf-page            # หน้า PDF ที่ 8 ตรง ๆ (ใช้ตอนหาสารบัญ)
  bookscan_page.py teacher1 55,60-62

พิมพ์ path ไฟล์ภาพออกมาบรรทัดละ 1 ไฟล์ -> เอาไป Read เป็นภาพได้เลย

ใช้ Python 3.12: %LOCALAPPDATA%\\Programs\\Python\\Python312\\python.exe
"""
import argparse
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bookscan_common as bc  # noqa: E402

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ต้องมี PyMuPDF — ติดตั้ง: python -m pip install pymupdf", file=sys.stderr)
    raise SystemExit(2)

try:
    from PIL import Image
except ImportError:
    Image = None

DEFAULT_WIDTH = 1400


def extract_page(doc, pdf_page, out_path, width):
    """ดึง 1 หน้า -> ไฟล์ภาพ. ถ้าหน้านั้นเป็นภาพเต็มหน้าภาพเดียว ใช้ต้นฉบับเลย (ไม่ re-render)"""
    page = doc[pdf_page - 1]
    imgs = page.get_images(full=True)
    raw = None
    if len(imgs) == 1:
        try:
            raw = doc.extract_image(imgs[0][0])
        except Exception:
            raw = None

    if raw is not None and Image is not None:
        import io
        with Image.open(io.BytesIO(raw["image"])) as im:
            im.load()
            if im.width > width:
                ratio = width / float(im.width)
                im = im.resize((width, max(1, int(im.height * ratio))), Image.LANCZOS)
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            im.save(out_path, "JPEG", quality=82)
        return out_path

    # fallback: render ทั้งหน้า
    zoom = width / max(1.0, page.rect.width)
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    pix.save(out_path)
    return out_path


def main():
    ap = argparse.ArgumentParser(description="ดึงหน้าหนังสือสแกนออกมาเป็นภาพ")
    ap.add_argument("book", help="id ของเล่ม (เช่น book1) หรือบางส่วนของชื่อไฟล์")
    ap.add_argument("pages", help="เลขหน้า เช่น 122 หรือ 122-125 หรือ 3,7,10-12")
    ap.add_argument("--subject", default="Math")
    ap.add_argument("--grade", default="M.1")
    ap.add_argument("--pdf-page", action="store_true",
                    help="ตีความเลขหน้าเป็นเลขหน้า PDF ดิบ (ไม่แปลง offset)")
    ap.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    ap.add_argument("--out", default=None, help="โฟลเดอร์ปลายทาง (ค่าเริ่มต้น = .cache ของชั้นนั้น)")
    args = ap.parse_args()

    # ถ้ายังไม่มี index (ตอน bootstrap หาสารบัญ) ให้ยอมทำงานด้วย --pdf-page
    book = None
    try:
        index = bc.load_index(args.subject, args.grade)
        book = bc.find_book(index, args.book)
        pdf_path = os.path.join(bc.scan_dir(args.subject, args.grade), book["file"])
    except (FileNotFoundError, KeyError) as exc:
        if not args.pdf_page:
            print("ERROR: %s" % exc, file=sys.stderr)
            print("ยังไม่มี index -> ใช้ --pdf-page พร้อมระบุชื่อไฟล์บางส่วนแทนได้", file=sys.stderr)
            return 1
        cands = [p for p in bc.list_pdfs(args.subject, args.grade)
                 if args.book.lower() in os.path.basename(p).lower()]
        if len(cands) != 1:
            print("ERROR: ระบุเล่มไม่ชัด (%d ไฟล์ตรง) — ไฟล์ที่มี:" % len(cands), file=sys.stderr)
            for p in bc.list_pdfs(args.subject, args.grade):
                print("   %s" % os.path.basename(p), file=sys.stderr)
            return 1
        pdf_path = cands[0]

    if not os.path.exists(pdf_path):
        print("ERROR: ไม่พบไฟล์ %s" % pdf_path, file=sys.stderr)
        return 1

    out_dir = args.out or bc.cache_dir(args.subject, args.grade)
    os.makedirs(out_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    # tag ต้องไม่ชนกันข้ามเล่ม — ชื่อไฟล์ไทยหลายเล่มขึ้นต้นเหมือนกัน จึงต่อ hash สั้นไว้
    if book and book.get("id"):
        tag = book["id"]
    else:
        stem = os.path.splitext(os.path.basename(pdf_path))[0]
        digest = hashlib.sha1(stem.encode("utf-8")).hexdigest()[:6]
        tag = "%s-%s" % (stem[:12].strip().replace(" ", "_"), digest)
    written = []
    for n in bc.parse_page_range(args.pages):
        if not args.pdf_page and not bc.is_scanned(book, n):
            print("WARN: ข้ามหน้าพิมพ์ %s — เล่มนี้สแกนมาไม่เต็ม มีเฉพาะหน้า %s"
                  % (n, bc.scanned_summary(book)), file=sys.stderr)
            continue
        pdf_page = n if args.pdf_page else bc.printed_to_pdf(book, n)
        if not (1 <= pdf_page <= doc.page_count):
            print("WARN: ข้ามหน้า %s (หน้า PDF %d อยู่นอกช่วง 1-%d)"
                  % (n, pdf_page, doc.page_count), file=sys.stderr)
            continue
        label = "pdf%03d" % pdf_page if args.pdf_page else "p%03d" % n
        out_path = os.path.join(out_dir, "%s_%s.jpg" % (tag, label))
        extract_page(doc, pdf_page, out_path, args.width)
        written.append(out_path)
    doc.close()

    if not written:
        print("ไม่ได้ดึงหน้าใดเลย", file=sys.stderr)
        return 1
    for p in written:
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
