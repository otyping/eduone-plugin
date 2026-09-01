# -*- coding: utf-8 -*-
"""
embed_fonts_pptx.py — ฝังฟอนต์ลงไฟล์ .pptx ด้วย PowerPoint COM (EDU ONE)

ทำไมต้องใช้ COM: ฟอนต์ที่ฝังใน pptx เก็บเป็น `ppt/fonts/*.fntdata` รูปแบบ **EOT**
(ไม่ใช่ .ttf ดิบ) ซึ่งเขียนเองแล้วเสี่ยง PowerPoint ขอ repair — ให้ PowerPoint
ทำให้เองปลอดภัยกว่า และได้ตรวจไปในตัวว่าไฟล์เปิดได้จริงไม่ต้องซ่อม

  EmbedTrueTypeFonts = True   -> ฝังฟอนต์
  SaveSubsetFonts    = False  -> ขอชุดอักขระเต็ม (PowerPoint จะ subset ให้เท่าที่ใช้จริง
                                 ซึ่งพอสำหรับเปิด/นำเสนอเครื่องอื่น — ครบทั้ง regular/bold/italic)

ต้อง early binding (gencache) เท่านั้น late binding ตั้ง property ของ Presentation ไม่ได้

ใช้:
  embed_fonts_pptx.py <pptx> [<pptx> ...]        ฝังฟอนต์
  embed_fonts_pptx.py --png <pptx> <out_dir>     export ทุกหน้าเป็น PNG (ไว้ตรวจด้วยตา)

exit 0 = สำเร็จ / 1 = ไม่มี PowerPoint หรือสั่งไม่สำเร็จ
"""
from __future__ import annotations

import os
import sys

PP_SAVE_AS_OPEN_XML = 24  # ppSaveAsOpenXMLPresentation
MSO_TRUE, MSO_FALSE = -1, 0


def _app():
    """early binding (gencache) ก่อน — late binding ตั้ง property ของ Presentation ไม่ได้

    (Dispatch ธรรมดาจะฟ้อง "Property 'Open.SaveSubsetFonts' can not be set.")
    """
    import win32com.client
    try:
        from win32com.client import gencache
        return gencache.EnsureDispatch("PowerPoint.Application")
    except Exception:
        return win32com.client.Dispatch("PowerPoint.Application")


def embed(path: str) -> int:
    """เปิดไฟล์ใน PowerPoint แล้วบันทึกใหม่พร้อมฝังฟอนต์ — คืน 0 เมื่อสำเร็จ"""
    path = os.path.abspath(path)
    if not os.path.exists(path):
        print("ไม่พบไฟล์: %s" % path, file=sys.stderr)
        return 1
    app = pres = None
    try:
        app = _app()
        pres = app.Presentations.Open(path, ReadOnly=MSO_FALSE, Untitled=MSO_FALSE,
                                      WithWindow=MSO_FALSE)
        # ตั้งก่อนบันทึก: ฝังฟอนต์ + ขอชุดอักขระเต็ม (PowerPoint อาจ subset ให้เท่าที่ใช้จริง
        # ซึ่งเพียงพอกับการเปิด/นำเสนอเครื่องอื่นอยู่แล้ว)
        for prop, val in (("SaveSubsetFonts", MSO_FALSE), ("EmbedTrueTypeFonts", MSO_TRUE)):
            try:
                setattr(pres, prop, val)
            except Exception:
                pass
        pres.SaveAs(path, PP_SAVE_AS_OPEN_XML, MSO_TRUE)
        pres.Close()
        pres = None
        print("ฝังฟอนต์แล้ว: %s" % path)
        return 0
    except Exception as e:  # ไม่มี Office / COM ใช้ไม่ได้ / ไฟล์ถูกเปิดค้าง
        print("ฝังฟอนต์ไม่สำเร็จ (%s) — ต้องมี Microsoft PowerPoint + pywin32 "
              "และไฟล์ต้องไม่ถูกเปิดค้างอยู่" % e, file=sys.stderr)
        try:
            if pres is not None:
                pres.Close()
        except Exception:
            pass
        return 1
    finally:
        try:
            if app is not None:
                app.Quit()
        except Exception:
            pass


def export_png(path: str, out_dir: str, width: int = 1600) -> int:
    """export ทุกสไลด์เป็น PNG (ไว้ตรวจด้วยตาว่าฟอนต์/การตัดคำ/การจัดวางถูกจริง)"""
    path, out_dir = os.path.abspath(path), os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    app = pres = None
    try:
        app = _app()
        pres = app.Presentations.Open(path, ReadOnly=MSO_TRUE, Untitled=MSO_FALSE,
                                      WithWindow=MSO_FALSE)
        h = int(width * pres.PageSetup.SlideHeight / pres.PageSetup.SlideWidth)
        for i in range(1, pres.Slides.Count + 1):
            out = os.path.join(out_dir, "slide%02d.png" % i)
            pres.Slides(i).Export(out, "PNG", width, h)
        n = pres.Slides.Count
        pres.Close()
        pres = None
        print("export %d หน้า -> %s" % (n, out_dir))
        return 0
    except Exception as e:
        print("export PNG ไม่สำเร็จ: %s" % e, file=sys.stderr)
        try:
            if pres is not None:
                pres.Close()
        except Exception:
            pass
        return 1
    finally:
        try:
            if app is not None:
                app.Quit()
        except Exception:
            pass


def main(argv):
    if len(argv) >= 2 and argv[1] == "--png":
        if len(argv) != 4:
            print("usage: embed_fonts_pptx.py --png <pptx> <out_dir>", file=sys.stderr)
            return 2
        return export_png(argv[2], argv[3])
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    rc = 0
    for p in argv[1:]:
        rc |= embed(p)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
