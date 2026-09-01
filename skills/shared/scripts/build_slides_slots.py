# -*- coding: utf-8 -*-
"""
build_slides_slots.py — สร้างสไลด์จาก **เทมเพลตแบบสเปก LAYOUT** (EDU ONE — agent 4)

ใช้กับเทมเพลตที่ให้มาเป็นสไลด์ตัวอย่างหนึ่งหน้าต่อหนึ่ง LAYOUT พร้อมวัตถุที่ตั้งชื่อไว้
(เช่น `Slide Master Template/Mat M1/`) — โคลนหน้าของ LAYOUT ที่ต้องการแล้วเติมข้อความลงช่องตามชื่อ
ดีไซน์ ตำแหน่ง สี ทั้งหมดเป็นของเทมเพลต เราคุมแค่ "ข้อความอะไรลงช่องไหน" กับ "ขนาดตัวอักษร"

`build_slides.py` เรียกโมดูลนี้เองเมื่อ `pptx_slots.is_slot_template()` เป็นจริง

ใช้ Python 3.12: %LOCALAPPDATA%\\Programs\\Python\\Python312\\python.exe
"""
from __future__ import annotations

import os
import sys

from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pptx_common as pc      # noqa: E402
import pptx_slots as ps       # noqa: E402

CONT = " (ต่อ)"

# section -> เลข LAYOUT ในเทมเพลต
LAYOUT_OF = {
    "cover": 1, "lesson_info": 2, "objectives": 3,
    "content": 4, "content_image": 5, "content_image_alt": 6,
    "compare": 7, "triple": 8, "steps": 9, "example": 10,
    "summary": 11, "application": 12, "vocab": 13, "formula": 14,
    "question": 4,
}


class Deck:
    """สถานะการสร้างเด็ค — ถือ prs, ดัชนี LAYOUT, สเกลตัวอักษร และตัวช่วยรูป"""

    def __init__(self, prs, spec_dir, media_dir, stem, resolve_image, image_note):
        self.prs = prs
        self.index = ps.layout_index(prs)
        self.n_samples = len(prs.slides.__iter__.__self__._sldIdLst)
        self.scale = ps.scale_for(prs)
        self.spec_dir = spec_dir
        self.media_dir = media_dir
        self.stem = stem
        self._resolve = resolve_image
        self._note = image_note
        self.made = 0
        self.missing = set()

    def page(self, section):
        """โคลนหน้าของ LAYOUT ที่ผูกกับ section นี้ (ไม่มีก็ถอยไป LAYOUT 04)"""
        code = LAYOUT_OF.get(section, 4)
        src = self.index.get(code) or self.index.get(4) or self.index[min(self.index)]
        if code not in self.index:
            self.missing.add(code)
        self.made += 1
        return ps.clone(self.prs, src)

    def txt(self, slot, items, size_key, **kw):
        if slot is None:
            return None
        return ps.set_text(slot, items, ps.SIZE[size_key], scale=self.scale, **kw)

    def txt_fit(self, slot, items, size_key, min_key="card_min", **kw):
        """เติมข้อความโดยย่อขนาดให้พอดีกรอบของช่อง (ไม่ต่ำกว่าพื้นที่กำหนด)"""
        if slot is None:
            return None
        if isinstance(items, str):
            items = [items]
        items = [x for x in items if str(x).strip()]
        if not items:
            ps.drop(slot)
            return None
        _x, _y, w, h = ps.box_in(slot)
        size = ps.fit_size(items, pc.BODY_FONT, ps.SIZE[size_key], ps.SIZE[min_key],
                           w, h, bullet=kw.get("bullet", False))
        return ps.set_text(slot, items, size, scale=self.scale, **kw)

    def title(self, slot, text):
        """หัวข้อหน้า — ย่อขนาดให้พอ 1 บรรทัดในกรอบของเทมเพลต"""
        if slot is None:
            return
        _x, _y, w, h = ps.box_in(slot)
        size = ps.fit_size(text, pc.HEAD_FONT, ps.SIZE["title"], ps.SIZE["title_min"],
                           w, h, lines_max=1)
        ps.set_text(slot, text, size, family=pc.HEAD_FONT, bold=True,
                    anchor=MSO_ANCHOR.MIDDLE, scale=self.scale)

    def image(self, slide, slot, s):
        if slot is None:
            return
        local, _want = self._resolve(s)
        ps.put_image(slide, slot, local or None, scale=self.scale)

    def notes(self, slide, s):
        ps.set_notes(slide, s.get("speaker_note", ""), self._note(s))


# ---------------------------------------------------------------- ตัวช่วยแบ่งหน้า
def _pages(items, box, size, bullet=True):
    """แบ่งรายการเป็นหน้าตามกรอบจริงของช่องในเทมเพลต"""
    _x, _y, w, h = box
    return pc.fit_pages(items, pc.BODY_FONT, size, w, h, bullet=bullet)


# ================================================================ section builders
def build_cover(d, s):
    sl = d.page("cover")
    k = ps.slots(sl)
    d.title(k.get("TITLE_MAIN"), s.get("title", ""))
    if "TITLE_MAIN" in k:                       # หน้าปกให้ใหญ่กว่าหัวข้อหน้าทั่วไป
        _x, _y, w, h = ps.box_in(k["TITLE_MAIN"])
        size = ps.fit_size(s.get("title", ""), pc.HEAD_FONT, ps.SIZE["cover_title"],
                           ps.SIZE["title_min"], w, h, lines_max=2)
        ps.set_text(k["TITLE_MAIN"], s.get("title", ""), size, family=pc.HEAD_FONT,
                    bold=True, anchor=MSO_ANCHOR.BOTTOM, scale=d.scale)
    hook = s.get("hook_question", "")
    slot = k.get("HOOK_QUESTION")
    if slot is not None and hook:
        _x, _y, w, h = ps.box_in(slot)
        size = ps.fit_size(hook, pc.BODY_FONT, ps.SIZE["cover_hook"], 22, w, h)
        if not pc.fits([hook], pc.BODY_FONT, size, w, h, bullet=False):
            print("WARN: คำถามนำยาวเกินกรอบหน้าปกของเทมเพลต (เทมเพลตกำหนดไม่เกิน 2 บรรทัด) "
                  "— %r" % hook[:50], file=sys.stderr)
        ps.set_text(slot, hook, size, scale=d.scale)
    # บรรทัดข้อมูลใต้ชื่อเรื่องเป็น caption เล็กตามดีไซน์ — ย่อให้พอดีกรอบจริง
    d.txt_fit(k.get("META_COVER_LINE"), s.get("meta_line", ""), "cover_meta", "micro")
    d.image(sl, k.get("IMAGE_COVER_16X9"), s)
    d.notes(sl, s)
    ps.drop_unused(sl, set())
    return 1


def build_lesson_info(d, s):
    sl = d.page("lesson_info")
    k = ps.slots(sl)
    d.title(k.get("TITLE_MAIN"), s.get("title", "ข้อมูลบทเรียน"))
    for slot, key in (("META_GRADE", "grade"), ("META_SUBJECT", "subject"),
                      ("META_DURATION", "duration"), ("META_TOPIC", "topic")):
        d.txt(k.get(slot), s.get(key, ""), "meta")
    d.txt(k.get("META_OBJECTIVE"), s.get("objectives", []), "meta")
    d.notes(sl, s)
    ps.drop_unused(sl, set())
    return 1


def _slot_box(d, section, slot_name, default):
    """อ่านกรอบของช่องจาก **หน้าตัวอย่างในเทมเพลต** (ไม่ต้องโคลนหน้าจริงมาวัด)"""
    src = d.index.get(LAYOUT_OF[section])
    if src is not None:
        shp = ps.slots(src).get(slot_name)
        if shp is not None:
            return ps.box_in(shp)
    return default


def build_objectives(d, s):
    title = s.get("title", "หัวข้อการเรียนรู้")
    box = _slot_box(d, "objectives", "TOPIC_LIST", (0, 0, 10.8, 3.5))
    pages = _pages(s.get("items", []), box, ps.SIZE["body"], bullet=False)
    for i, page in enumerate(pages):
        sl = d.page("objectives")
        k = ps.slots(sl)
        d.title(k.get("TITLE_MAIN"), title if i == 0 else title + CONT)
        d.txt(k.get("TOPIC_LIST"), page, "body")
        d.notes(sl, s)
        ps.drop_unused(sl, set())
    return len(pages)


def _content_layout(d, s, alt):
    has_img = bool(s.get("image_prompt") or s.get("image_file"))
    if not has_img:
        return "content"
    return "content_image_alt" if alt else "content_image"


def build_content(d, s, alt=False):
    title = s.get("title", "")
    bullets = s.get("bullets", [])
    section = _content_layout(d, s, alt)
    code = LAYOUT_OF[section]
    src = d.index.get(code)
    box = _slot_box(d, section, "BODY_MAIN", (0, 0, 11.5, 3.5))
    pages = _pages(bullets, box, ps.SIZE["body"])
    for i, page in enumerate(pages):
        sl = d.page(section if i == 0 else "content")
        k = ps.slots(sl)
        d.title(k.get("TITLE_MAIN"), title if i == 0 else title + CONT)
        d.txt(k.get("BODY_MAIN"), page, "body", bullet=True)
        if i == 0:
            d.image(sl, k.get("IMAGE_MAIN_4X3"), s)
            d.txt(k.get("IMAGE_CAPTION"), s.get("caption", ""), "caption")
        d.notes(sl, s)
        ps.drop_unused(sl, set())
    return len(pages)


def build_question(d, s):
    sl = d.page("question")
    k = ps.slots(sl)
    text = s.get("question", "")
    d.title(k.get("TITLE_MAIN"), s.get("title", "ชวนคิด"))
    slot = k.get("BODY_MAIN")
    if slot is not None:
        _x, _y, w, h = ps.box_in(slot)
        size = ps.fit_size(text, pc.BODY_FONT, ps.SIZE["formula"], ps.SIZE["body_min"], w, h)
        ps.set_text(slot, text, size, align=PP_ALIGN.CENTER,
                    anchor=MSO_ANCHOR.MIDDLE, scale=d.scale)
    d.notes(sl, s)
    ps.drop_unused(sl, set())
    return 1


def _cards_fit(d, s, section, prefix, count):
    """การ์ดของ LAYOUT นี้รับข้อความไหวไหม (วัดที่ขนาดพื้นของการ์ด)"""
    src = d.index.get(LAYOUT_OF[section])
    if src is None:
        return False
    k = ps.slots(src)
    items = s.get("cards") or s.get("steps") or s.get("situations") or []
    for i, it in enumerate(items[:count], 1):
        slot = k.get("%s_%d_BODY" % (prefix, i))
        if slot is not None:
            _x, _y, bw, bh = ps.box_in(slot)
            if not pc.fits([it.get("body", "")], pc.BODY_FONT, ps.SIZE["card_min"],
                           bw, bh, bullet=False):
                return False
        head = k.get("%s_%d_TITLE" % (prefix, i))
        if head is not None and it.get("title"):
            _x, _y, hw, hh = ps.box_in(head)
            n = pc.wrap_count(it["title"], pc.HEAD_FONT, ps.SIZE["card_min"],
                              pc.usable_width_pt(hw, bullet=False), True)
            if n > 1 or not pc.fits([it["title"]], pc.HEAD_FONT, ps.SIZE["card_min"],
                                    hw, hh, bullet=False):
                return False
    return True


def _fallback_body(d, s, title, bullets):
    """ถอยไป LAYOUT 04 เมื่อเนื้อหายาวเกินกรอบของ LAYOUT ที่ตั้งใจไว้"""
    box = _slot_box(d, "content", "BODY_MAIN", (0, 0, 11.5, 3.5))
    pages = _pages(bullets, box, ps.SIZE["body"])
    for i, page in enumerate(pages):
        sl = d.page("content")
        k = ps.slots(sl)
        d.title(k.get("TITLE_MAIN"), title if i == 0 else title + CONT)
        d.txt(k.get("BODY_MAIN"), page, "body", bullet=True)
        d.notes(sl, s)
        ps.drop_unused(sl, set())
    return len(pages)


def _cards_or_body(d, s, section, prefix, count):
    """ใช้ LAYOUT การ์ดถ้าข้อความพอดี ไม่งั้นถอยไปหน้าเนื้อหาธรรมดา"""
    if _cards_fit(d, s, section, prefix, count):
        return _cards(d, s, section, prefix, count)
    print("WARN: ข้อความของ %r ยาวเกินการ์ดของ LAYOUT %02d — ใช้ LAYOUT 04 แทน"
          % (s.get("title", "")[:30], LAYOUT_OF[section]), file=sys.stderr)
    items = s.get("cards") or s.get("steps") or s.get("situations") or []
    bullets = [((it.get("title", "") + " — " if it.get("title") else "")
                + it.get("body", "")).strip() for it in items]
    return _fallback_body(d, s, s.get("title", ""), bullets)


def _cards(d, s, section, prefix, count, title_key="title"):
    """LAYOUT 07/08/09/12 — การ์ดหลายใบที่มีหัวข้อ+คำอธิบาย(+ภาพ)"""
    sl = d.page(section)
    k = ps.slots(sl)
    d.title(k.get("TITLE_MAIN"), s.get(title_key, ""))
    items = s.get("cards") or s.get("steps") or s.get("situations") or []
    used = {"TITLE_MAIN"}
    for i in range(1, count + 1):
        it = items[i - 1] if i <= len(items) else None
        for suffix, key, size_key in (("TITLE", "title", "card_title"),
                                      ("BODY", "body", "card"),
                                      ("EXAMPLE", "example", "card")):
            name = "%s_%d_%s" % (prefix, i, suffix)
            slot = k.get(name)
            if slot is None:
                continue
            if it is None:
                ps.drop(slot)
                continue
            _x, _y, bw, bh = ps.box_in(slot)
            fam = pc.HEAD_FONT if suffix == "TITLE" else pc.BODY_FONT
            sz = ps.fit_size(it.get(key, ""), fam, ps.SIZE[size_key],
                             ps.SIZE["card_min"], bw, bh,
                             lines_max=1 if suffix == "TITLE" else None)
            ps.set_text(slot, it.get(key, ""), sz, family=fam,
                        bold=(suffix == "TITLE"), scale=d.scale)
            used.add(name)
        # ชื่อช่องภาพต่าง LAYOUT ใช้คนละแบบ — เอาชื่อแรกที่มีจริงในหน้านี้
        for img in dict.fromkeys(("%s_%d_IMAGE_1X1" % (prefix, i), "IMAGE_%d_1X1" % i)):
            slot = k.get(img)
            if slot is None:
                continue
            if it is None:
                ps.drop(slot)
            else:
                d.image(sl, slot, it)
                used.add(img)
            break
    d.notes(sl, s)
    ps.drop_unused(sl, used)
    return 1


def build_example(d, s):
    """LAYOUT 10 โจทย์ + คำตอบ + วิธีคิด — เนื้อหายาวเกินกรอบให้ถอยไป LAYOUT 04"""
    box = _slot_box(d, "example", "EXPLANATION", (0, 0, 5.62, 1.21))
    steps = s.get("explanation", [])
    if steps and not pc.fits(steps, pc.BODY_FONT, ps.SIZE["card_min"], box[2], box[3]):
        print("WARN: วิธีคิดของ %r ยาวเกินกรอบ LAYOUT 10 — ใช้ LAYOUT 04 แทน"
              % s.get("title", "")[:30], file=sys.stderr)
        bullets = [s.get("prompt", ""), "คำตอบ: " + s.get("answer", "")] + list(steps)
        return _fallback_body(d, s, s.get("title", "ตัวอย่าง"), bullets)
    sl = d.page("example")
    k = ps.slots(sl)
    d.title(k.get("TITLE_MAIN"), s.get("title", "ตัวอย่าง"))
    d.txt_fit(k.get("EXAMPLE_PROMPT"), s.get("prompt", ""), "body")
    d.txt_fit(k.get("ANSWER"), s.get("answer", ""), "body", bold=True)
    d.txt_fit(k.get("EXPLANATION"), steps, "card", bullet=True)
    d.image(sl, k.get("VISUAL_4X3"), s)
    d.notes(sl, s)
    ps.drop_unused(sl, set())
    return 1


def build_formula(d, s):
    """LAYOUT 14 สมการเด่น + คำอธิบายตัวแปร"""
    box = _slot_box(d, "formula", "FORMULA_EXPLANATION", (0, 0, 7.29, 1.81))
    expl = s.get("explanation", [])
    if expl and not pc.fits(expl, pc.BODY_FONT, ps.SIZE["card_min"], box[2], box[3]):
        print("WARN: คำอธิบายสมการของ %r ยาวเกินกรอบ LAYOUT 14 — ใช้ LAYOUT 04 แทน"
              % s.get("title", "")[:30], file=sys.stderr)
        return _fallback_body(d, s, s.get("title", ""),
                              [s.get("formula", "")] + list(expl))
    sl = d.page("formula")
    k = ps.slots(sl)
    d.title(k.get("TITLE_MAIN"), s.get("title", ""))
    d.txt_fit(k.get("FORMULA_MAIN"), s.get("formula", ""), "formula", "body_min",
              align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    d.txt_fit(k.get("FORMULA_EXPLANATION"), expl, "body", bullet=True)
    d.image(sl, k.get("DIAGRAM_4X3"), s)
    d.notes(sl, s)
    ps.drop_unused(sl, set())
    return 1


def build_summary(d, s):
    title = s.get("title", "สรุป")
    box = _slot_box(d, "summary", "SUMMARY_LIST", (0, 0, 7.6, 3.4))
    pages = _pages(s.get("bullets", []), box, ps.SIZE["body"])
    for i, page in enumerate(pages):
        sl = d.page("summary")
        k = ps.slots(sl)
        d.title(k.get("TITLE_MAIN"), title if i == 0 else title + CONT)
        d.txt(k.get("SUMMARY_LIST"), page, "body", bullet=True)
        if i == 0:
            d.txt(k.get("MEMORY_TRICK"), s.get("memory_trick", ""), "card")
            d.image(sl, k.get("SUMMARY_IMAGE_1X1"), s)
        d.notes(sl, s)
        ps.drop_unused(sl, set())
    return len(pages)


def build_application(d, s):
    """LAYOUT 12 รับ 3 สถานการณ์สั้น ๆ — ถ้าข้อความยาวเกินการ์ด ให้ถอยไปใช้ LAYOUT 04

    เทมเพลตเขียนกำกับไว้ว่าการ์ดรับ "การนำไปใช้ 2-3 บรรทัด" การยัดบุลเล็ตยาวลงไป
    จะล้นกรอบและผิดเจตนาของดีไซน์ — เลือก layout ตามความยาวเนื้อหาจริง
    """
    title = s.get("title", "การนำไปใช้ในชีวิตประจำวัน")
    items = s.get("situations")
    if items:
        box = _slot_box(d, "application", "SITUATION_1_BODY", (0, 0, 3.67, 1.21))
        fits_all = all(pc.fits([it.get("body", "")], pc.BODY_FONT, ps.SIZE["card"],
                               box[2], box[3], bullet=False) for it in items)
        if fits_all:
            made = 0
            for i in range(0, len(items), 3):
                s2 = dict(s)
                s2["situations"] = items[i:i + 3]
                s2["title"] = title + (CONT if i else "")
                made += _cards(d, s2, "application", "SITUATION", 3)
            return made
        print("WARN: ข้อความ 'การนำไปใช้' ยาวเกินการ์ดของ LAYOUT 12 — ใช้ LAYOUT 04 แทน",
              file=sys.stderr)
        bullets = [(it.get("title", "") + " " + it.get("body", "")).strip() for it in items]
    else:
        bullets = s.get("bullets", [])

    box = _slot_box(d, "content", "BODY_MAIN", (0, 0, 11.5, 3.5))
    pages = _pages(bullets, box, ps.SIZE["body"])
    for i, page in enumerate(pages):
        sl = d.page("content")
        k = ps.slots(sl)
        d.title(k.get("TITLE_MAIN"), title if i == 0 else title + CONT)
        d.txt(k.get("BODY_MAIN"), page, "body", bullet=True)
        d.notes(sl, s)
        ps.drop_unused(sl, set())
    return len(pages)


def build_vocab(d, s):
    table = s.get("table", [])
    if not table:
        return 0
    head, rows = table[0], table[1:]
    title = s.get("title", "คำศัพท์ภาษาอังกฤษน่ารู้")
    per = 6
    chunks = [rows[i:i + per] for i in range(0, len(rows), per)] or [[]]
    for i, chunk in enumerate(chunks):
        sl = d.page("vocab")
        k = ps.slots(sl)
        d.title(k.get("TITLE_MAIN"), title if i == 0 else title + CONT)
        frame = next((shp for shp in sl.shapes if shp.has_table), None)
        if frame is not None:
            ps.fill_table(sl, frame, [head] + chunk, scale=d.scale)
        d.notes(sl, s)
        ps.drop_unused(sl, set())
    return len(chunks)


BUILDERS = {
    "cover": build_cover,
    "lesson_info": build_lesson_info,
    "objectives": build_objectives,
    "content": build_content,
    "question": build_question,
    "example": build_example,
    "formula": build_formula,
    "summary": build_summary,
    "application": build_application,
    "vocab": build_vocab,
    "compare": lambda d, s: _cards_or_body(d, s, "compare", "CARD", 2),
    "triple": lambda d, s: _cards_or_body(d, s, "triple", "CARD", 3),
    "steps": lambda d, s: _cards_or_body(d, s, "steps", "STEP", 4),
}


def build(prs, spec, spec_path, resolve_image, image_note):
    """สร้างทุกหน้าลง prs แล้วลบสไลด์ตัวอย่างของเทมเพลตทิ้ง"""
    stem = os.path.basename(spec_path)[:-5]
    d = Deck(prs, os.path.dirname(os.path.abspath(spec_path)),
             os.path.join(os.path.dirname(os.path.abspath(spec_path)), stem + "_media"),
             stem, resolve_image, image_note)
    n_samples = d.n_samples
    alt = False
    for s in spec.get("slides", []):
        fn = BUILDERS.get(s.get("section"))
        if fn is None:
            print("WARN: ข้าม section ที่ไม่รู้จัก: %r" % s.get("section"), file=sys.stderr)
            continue
        before = d.made
        if s.get("section") == "content":
            n = build_content(d, s, alt=alt)
            if s.get("image_prompt") or s.get("image_file"):
                alt = not alt                      # สลับ ภาพซ้าย/ภาพขวา ให้จังหวะไม่ซ้ำ
        else:
            n = fn(d, s)
        print("  %-12s -> %d หน้า : %s" % (s.get("section"), d.made - before,
                                           (s.get("title") or s.get("question") or "")[:38]))
    ps.drop_samples(prs, n_samples)
    if d.missing:
        print("WARN: เทมเพลตไม่มี LAYOUT %s — ใช้ LAYOUT 04 แทน"
              % ", ".join("%02d" % c for c in sorted(d.missing)), file=sys.stderr)
    return d.made
