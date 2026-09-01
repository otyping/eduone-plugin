# -*- coding: utf-8 -*-
"""
build_exercise.py — สร้าง .docx แบบฝึกหัด จาก {BASE}_ex.json ไฟล์เดียว

สคีมา (ดู ${CLAUDE_PLUGIN_ROOT}/skills/exercise/reference/prompt-master-exercise.md):
  { "questions": [ { text, imageUrl, audioUrl, imageAlt, audioText,
                     choices: [ { contentType, content, isTrue, alt } ],
                     difficulty, solutionSteps } ] }

เอกสารที่ได้เป็น **ฉบับผู้ตรวจ/ครู**:
  - โจทย์/ตัวเลือกที่เป็นรูป -> ฝังรูปให้อัตโนมัติ (ถ้ายังไม่มี URL แสดงบรรทัดสั่งผลิตแทน)
  - บทเสียง                 -> ข้อความ **สีน้ำเงิน** (คนตรวจจะได้รู้ว่าเสียงพูดว่าอะไร)
  - ตัวเลือกที่เป็นคำตอบถูก  -> **สีแดง**
  - หน้าเฉลย                -> เลขข้อ + ตัวอักษร + "วิธีคิด:"

กติกาเมื่อสีชนกัน: ตัวเลือกเสียงที่เป็นคำตอบถูก ใช้ **สีแดง** (ป้าย [เสียง] ยังบอกว่าเป็นเสียงอยู่แล้ว)

ใช้:
  build_exercise.py <ex.json> <out.docx> --header "<header>" [--base BASE] [--media-dir DIR]

ใช้ Python 3.12: %LOCALAPPDATA%\\Programs\\Python\\Python312\\python.exe
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import docx_common as dc  # noqa: E402
import media_cache as mc  # noqa: E402

THAI_LETTERS = ("ก", "ข", "ค", "ง")
STEM_IMAGE_MM = 105.0
CHOICE_IMAGE_MM = 60.0      # 4 ใบต่อข้อ — ต้องพอดีหน้าเดียวกับตัวโจทย์
CHOICE_INDENT_MM = 10
DEFAULT_EXT = {"image": ".png", "audio": ".wav"}
MEDIA_LABEL = {"image": "รูปภาพ", "audio": "เสียง"}


def _legend(questions):
    """คำอธิบายสัญลักษณ์ — ใส่เฉพาะส่วนที่เอกสารนี้มีจริง"""
    parts = []
    has_audio = any(
        (q.get("audioUrl") or "").strip() or (q.get("audioText") or "").strip()
        or any((c.get("contentType") or "") == "audio" for c in q.get("choices") or [])
        for q in questions
    )
    if has_audio:
        parts.append("ข้อความสีน้ำเงิน = บทเสียงที่นักเรียนจะได้ยิน")
    parts.append("ตัวเลือกสีแดง = คำตอบที่ถูก")
    return "(%s)" % " · ".join(parts)


def asset_name(base, qno, slot, kind, url=""):
    """ชื่อไฟล์สื่อตามแบบแผน: {BASE}_{NN}_Q.ext / {BASE}_{NN}_A{1-4}.ext"""
    ext = mc.ext_of(url) or DEFAULT_EXT.get(kind, "")
    return "%s_%02d_%s%s" % (base, qno, slot, ext)


LOCAL_IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif")


def local_asset(assets_dir, filename):
    """หาไฟล์สื่อที่ผลิตไว้แล้วในเครื่อง (ยังไม่ได้อัปโหลดขึ้น CDN)

    ตั้งชื่อตามแบบแผน {BASE}_{NN}_{Q|A1-A4}.<ext> ในโฟลเดอร์ {BASE}_media/
    ทำให้ build เอกสารเห็นรูปทันทีโดยไม่ต้องรอ URL — และ JSON ยังว่างไว้รอ CDN ได้
    """
    if not assets_dir or not os.path.isdir(assets_dir):
        return None
    stem = os.path.splitext(filename)[0]
    for ext in LOCAL_IMAGE_EXT:
        p = os.path.join(assets_dir, stem + ext)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            return p
    return None


def base_from_json_path(path):
    name = os.path.basename(path)
    for suffix in ("_ex.json", ".json"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def letter_of(index):
    return THAI_LETTERS[index] if 0 <= index < len(THAI_LETTERS) else "?"


def _has_math(text):
    """มีสูตรใน $...$ หรือไม่ — ใช้เผื่อระยะบรรทัดให้เศษส่วนซ้อนไม่ชนกัน"""
    return isinstance(text, str) and text.count("$") >= 2


def _math_spacing(text):
    """คืน (space_after, line_spacing) ที่เหมาะกับย่อหน้าที่มี/ไม่มีสมการ

    สมการอย่างเศษส่วนสูง 2 บรรทัด ถ้าใช้ระยะปกติจะซ้อนทับตัวเลือกถัดไป
    """
    return (7, 1.45) if _has_math(text) else (0, 1.15)


def correct_index(question):
    for i, c in enumerate(question.get("choices") or []):
        if c.get("isTrue"):
            return i
    return -1


def _media_placeholder(doc, kind, filename, alt, indent=0):
    """บรรทัดสั่งผลิตสื่อ (ใช้เมื่อยังไม่มี URL หรือโหลดรูปไม่ได้)"""
    text = "[%s] %s" % (MEDIA_LABEL[kind], filename)
    if alt:
        text += " — %s" % alt
    return dc.add_paragraph(doc, text, align="left", space_before=0, space_after=2,
                            indent_left=indent, math=False,
                            color=dc.BLUE if kind == "audio" else None)


def _audio_line(doc, alt, filename, has_url, indent=0, color=None):
    """บรรทัดบทเสียง — สีน้ำเงินเสมอ ยกเว้นถูกสั่งให้เป็นสีอื่น (ตัวเลือกที่ถูก = แดง)"""
    body = '"%s"' % alt if alt else "(ยังไม่มีบทเสียง)"
    text = "[เสียง] %s" % body if has_url else "[เสียง] %s — %s" % (filename, body)
    return dc.add_paragraph(doc, text, align="left", space_before=0, space_after=2,
                            indent_left=indent, math=False,
                            color=dc.BLUE if color is None else color, italic=True)


def render_question(doc, idx, q, base, cache_dir, base_dir, warnings, assets_dir=None):
    """เรนเดอร์ 1 ข้อ: โจทย์ + สื่อของโจทย์ + 4 ตัวเลือก"""
    q_text = "%d. %s" % (idx, q.get("text", ""))
    q_after, q_ls = _math_spacing(q_text)
    dc.add_paragraph(doc, q_text, size=dc.BODY_SIZE,
                     align="thaiDistribute", space_before=4,
                     space_after=max(2, q_after), line_spacing=q_ls)

    # --- สื่อของโจทย์ ---
    image_url = (q.get("imageUrl") or "").strip()
    image_alt = (q.get("imageAlt") or "").strip()
    if image_url or image_alt:
        fname = asset_name(base, idx, "Q", "image", image_url)
        local = mc.resolve_image(image_url, STEM_IMAGE_MM, cache_dir, base_dir=base_dir) if image_url else None
        if local is None:
            produced = local_asset(assets_dir, fname)
            if produced:
                local = mc.fit_image(produced, STEM_IMAGE_MM, cache_dir)
        if local:
            dc.add_image_paragraph(doc, local, STEM_IMAGE_MM)
        else:
            if image_url:
                warnings.append("ข้อ %d: โหลดรูปโจทย์ไม่ได้ ใช้ placeholder แทน" % idx)
            _media_placeholder(doc, "image", fname, image_alt)

    audio_url = (q.get("audioUrl") or "").strip()
    audio_text = (q.get("audioText") or "").strip()
    if audio_url or audio_text:
        fname = asset_name(base, idx, "Q", "audio", audio_url)
        _audio_line(doc, audio_text, fname, bool(audio_url))

    # --- ตัวเลือก ---
    for ci, choice in enumerate(q.get("choices") or []):
        letter = letter_of(ci)
        ctype = (choice.get("contentType") or "text").strip()
        content = (choice.get("content") or "").strip()
        alt = (choice.get("alt") or "").strip()
        colour = dc.RED if choice.get("isTrue") else None
        slot = "A%d" % (ci + 1)

        if ctype == "text":
            line = "%s. %s" % (letter, content)
            c_after, c_ls = _math_spacing(line)
            dc.add_paragraph(doc, line, size=dc.BODY_SIZE,
                             align="left", space_before=0, space_after=c_after,
                             line_spacing=c_ls,
                             indent_left=CHOICE_INDENT_MM, color=colour)

        elif ctype == "image":
            fname = asset_name(base, idx, slot, "image", content)
            dc.add_paragraph(doc, "%s." % letter, align="left", space_before=0, space_after=0,
                             indent_left=CHOICE_INDENT_MM, math=False, color=colour)
            local = mc.resolve_image(content, CHOICE_IMAGE_MM, cache_dir, base_dir=base_dir) if content else None
            if local is None:
                produced = local_asset(assets_dir, fname)
                if produced:
                    local = mc.fit_image(produced, CHOICE_IMAGE_MM, cache_dir)
            if local:
                dc.add_image_paragraph(doc, local, CHOICE_IMAGE_MM, align="left",
                                       indent_left=CHOICE_INDENT_MM)
            else:
                if content:
                    warnings.append("ข้อ %d ตัวเลือก %s: โหลดรูปไม่ได้ ใช้ placeholder แทน" % (idx, letter))
                _media_placeholder(doc, "image", fname, alt, indent=CHOICE_INDENT_MM)

        elif ctype == "audio":
            fname = asset_name(base, idx, slot, "audio", content)
            dc.add_paragraph(doc, "%s." % letter, align="left", space_before=0, space_after=0,
                             indent_left=CHOICE_INDENT_MM, math=False, color=colour)
            _audio_line(doc, alt, fname, bool(content), indent=CHOICE_INDENT_MM, color=colour)

        else:
            warnings.append("ข้อ %d ตัวเลือก %s: contentType '%s' ไม่รู้จัก" % (idx, letter, ctype))
            dc.add_paragraph(doc, "%s. %s" % (letter, content), align="left",
                             space_before=0, space_after=0,
                             indent_left=CHOICE_INDENT_MM, color=colour)

    dc.add_paragraph(doc, "", space_before=0, space_after=4)


def build(data, out_path, header, base, media_dir=None, base_dir=None, expect=None):
    questions = data.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ValueError("ex.json ต้องมีคีย์ 'questions' เป็น list ที่ไม่ว่าง")

    # โฟลเดอร์สื่อที่ผลิตไว้แล้วในเครื่อง + ที่เก็บแคชของไฟล์ที่โหลดจาก URL
    assets_dir = media_dir or os.path.join(base_dir or os.path.dirname(os.path.abspath(out_path)),
                                           "%s_media" % base)
    cache_dir = os.path.join(assets_dir, ".cache")
    warnings = []
    if expect is not None and len(questions) != expect:
        warnings.append("คาดหวัง %d ข้อ แต่พบ %d ข้อ" % (expect, len(questions)))

    doc = dc.new_document(header)
    dc.add_heading(doc, "แบบฝึกหัด")
    dc.add_paragraph(doc, _legend(questions), align="center", space_before=0, space_after=8,
                     math=False, color=dc.BLUE, italic=True)

    for idx, q in enumerate(questions, start=1):
        ci = correct_index(q)
        if ci < 0:
            warnings.append("ข้อ %d: ไม่มีตัวเลือกที่ isTrue = true" % idx)
        elif sum(1 for c in q.get("choices") or [] if c.get("isTrue")) > 1:
            warnings.append("ข้อ %d: มีตัวเลือก isTrue = true มากกว่า 1 ตัว" % idx)
        first = len(doc.paragraphs)
        render_question(doc, idx, q, base, cache_dir, base_dir, warnings, assets_dir=assets_dir)
        # ไม่ให้ข้อเดียวถูกตัดข้ามหน้า — ผูกทุกย่อหน้าของข้อไว้ด้วยกัน ยกเว้นย่อหน้าสุดท้าย
        block = doc.paragraphs[first:]
        for p in block[:-1]:
            p.paragraph_format.keep_with_next = True
            p.paragraph_format.keep_together = True

    doc.add_page_break()
    dc.add_heading(doc, "หน้าเฉลย")
    for idx, q in enumerate(questions, start=1):
        dc.add_paragraph(doc, "%d. %s" % (idx, letter_of(correct_index(q))),
                         size=dc.BODY_SIZE, align="left",
                         space_before=2, space_after=0, math=False)
        steps = (q.get("solutionSteps") or "").strip()
        if steps:
            s_after, s_ls = _math_spacing(steps)
            dc.add_paragraph(doc, "วิธีคิด: %s" % steps, size=dc.BODY_SIZE,
                             align="thaiDistribute", space_before=0,
                             space_after=max(2, s_after), line_spacing=s_ls,
                             indent_left=CHOICE_INDENT_MM)
        else:
            warnings.append("ข้อ %d: ไม่มี solutionSteps" % idx)

    dc.save(doc, out_path)
    return warnings


def main():
    ap = argparse.ArgumentParser(description="สร้าง .docx แบบฝึกหัดจาก {BASE}_ex.json")
    ap.add_argument("ex_json")
    ap.add_argument("out_docx")
    ap.add_argument("--header", required=True, help="ข้อความ header มุมขวา (จาก no_to_token.py)")
    ap.add_argument("--base", default=None, help="BASE สำหรับตั้งชื่อไฟล์สื่อ (ค่าเริ่มต้น: เดาจากชื่อไฟล์ json)")
    ap.add_argument("--media-dir", default=None, help="โฟลเดอร์แคชสื่อ")
    ap.add_argument("--expect", type=int, default=None,
                    help="จำนวนข้อที่คาดหวัง (เตือนถ้าไม่ตรง) — ไม่ระบุ = ไม่ตรวจ")
    args = ap.parse_args()

    with open(args.ex_json, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    base = args.base or base_from_json_path(args.ex_json)
    warnings = build(data, args.out_docx, args.header, base,
                     media_dir=args.media_dir,
                     base_dir=os.path.dirname(os.path.abspath(args.ex_json)),
                     expect=args.expect)

    for w in warnings:
        print("WARN: %s" % w, file=sys.stderr)
    print("OK — สร้าง %s แล้ว (%d ข้อ)" % (args.out_docx, len(data["questions"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
