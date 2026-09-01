# -*- coding: utf-8 -*-
"""
build_slides_script.py — เอกสาร "สคริปต์สไลด์" ให้ครูตรวจก่อนสอน (EDU ONE — agent 4)

รวมสไลด์ทั้ง 4 แหล่ง (C1/C2/L1/L2) ของหัวข้อเดียว เป็นตาราง 3 คอลัมน์ต่อแหล่ง
  1) เลขสไลด์   2) ข้อความที่ปรากฏบนสไลด์   3) ภาพประกอบ + รายละเอียด

ทำไมต้องมี: ครูตรวจสคริปต์จากเอกสารได้เร็วกว่าเปิด .pptx ทีละไฟล์ และเห็นภาพรวมทั้ง 4 ชุด
พร้อมกัน — ที่สำคัญคือ **บอกได้ว่าหน้าไหนข้อความแน่นเกินมาตรฐาน** ก่อนเอาไปสอนจริง

มาตรฐานข้อความต่อสไลด์มาจากการ **วัดความจุจริงของ engine** (ไม่ใช่ตัวเลขที่ตั้งขึ้นเอง)
ดู LIMITS ด้านล่างและฟังก์ชัน measure_capacity()

ออก 2 ไฟล์จากข้อมูลชุดเดียวกัน:
  * .docx — ตาราง Word จริง (มีเส้น หัวตารางซ้ำทุกหน้า) สำหรับอ่าน/พิมพ์
  * .md   — ตาราง markdown ดิบ สำหรับคัดลอกไปวางที่อื่น

ใช้:
  build_slides_script.py <gradeSlug> <subjectSlug> <No> [--name "ชื่อไฟล์"]

รันผ่านตัวห่อ: eduone-py <ชื่อไฟล์นี้> <args>  (หา Python 3.12 ให้เองทุก OS)
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "shared", "scripts"))
import docx_common as dc  # noqa: E402
import pptx_common as pc  # noqa: E402
import slides_media as sm  # noqa: E402

SOURCES = ("C1", "C2", "L1", "L2")
SRC_LABEL = {
    "C1": "สไลด์จากเอกสารเนื้อหา แบบที่ 1 เชิงวิชาการ (C1)",
    "C2": "สไลด์จากเอกสารเนื้อหา แบบที่ 2 เล่าเรื่อง (C2)",
    "L1": "สไลด์จากแผนการจัดการเรียนรู้ แบบเชิงสำรวจ (L1)",
    "L2": "สไลด์จากแผนการจัดการเรียนรู้ แบบผ่านกิจกรรม (L2)",
}
BOTTOM_IN = 4.87          # ขอบล่างของพื้นที่เนื้อหา (ตรงกับ build_slides.py)

# ---------------------------------------------------------------- มาตรฐานข้อความต่อสไลด์
# **2 ระดับ** เพราะเกณฑ์เดียวหยาบเกินไป:
#   ok   = เกณฑ์แนะนำ — อยู่ในนี้แล้วหน้าดูโปร่ง อ่านสบาย
#   hard = เพดานจริงของ engine — เกินแล้ว "หน้าจะถูกแตกเป็น (ต่อ) อัตโนมัติ" (ไม่ย่อตัวอักษร)
# ค่า hard มาจากการวัด: ~6 บรรทัด/หน้า x จำนวนอักษรต่อบรรทัดที่วัดได้จริง
# (เต็มความกว้าง ~47 อักษร -> ~280 · คอลัมน์แคบที่มีรูป ~25 อักษร -> ~150)
LIMITS = {
    "content_plain": (250, 280),   # หน้าเนื้อหาเต็มความกว้าง (ไม่มีรูป)
    "content_image": (130, 150),   # หน้าเนื้อหาที่มีรูป (ข้อความอยู่คอลัมน์แคบครึ่งจอ)
    "question_plain": (120, 160),  # หน้าคำถามเดี่ยว (ตัวอักษร 40pt — ไม่แตกหน้า แต่จะถูกย่อขนาด)
    "question_image": (90, 120),   # หน้าคำถามที่มีรูป (34pt)
}
TITLE_MAX = 40            # หัวข้อหน้า — เกินนี้ต้องลดขนาดหรือขึ้น 2 บรรทัด แล้วดันเนื้อหาลง
BULLETS_PLAIN = 5         # จำนวนบุลเล็ตแนะนำสูงสุดต่อหน้า
BULLETS_IMAGE = 3
VOCAB_WORDS = 6           # คำศัพท์ต่อหน้า (ตาม Master Prompt)


def measure_capacity():
    """วัดความจุจริงของสไลด์จาก engine — ใช้พิมพ์ลงเอกสารเป็นที่มาของมาตรฐาน"""
    top = pc.title_metrics("ตัวอย่างหัวข้อความยาวปานกลางของสไลด์")[2]
    h = BOTTOM_IN - top
    line_in = pc.line_h_pt(pc.BODY_FONT, pc.SIZE["bullet"]) / 72
    out = {"lines": h / line_in, "size": pc.SIZE["bullet"]}
    for key, w in (("plain", pc.BODY_BOX[2]), ("image", pc.COL_L_BOX[2])):
        wp = pc.usable_width_pt(w, True)
        n = 1
        while n < 400 and pc.wrap_count("ก" * n, pc.BODY_FONT,
                                        pc.SIZE["bullet"], wp, False) == 1:
            n += 1
        out[key] = {"width_in": w, "chars": n - 1}
    return out


# ---------------------------------------------------------------- อ่านสไลด์
def _items_of(s):
    """ข้อความที่ 'ขึ้นจอ' ของหน้านั้น (ไม่รวมหัวข้อ) — คืน list ของบรรทัด"""
    if s.get("bullets"):
        return list(s["bullets"])
    if s.get("items"):
        return list(s["items"])
    if s.get("question"):
        return [s["question"]]
    if s.get("hook_question"):
        return [s["hook_question"]]
    return []


def _limit_for(s):
    """คืน ((เกณฑ์แนะนำ, เพดานจริง), ป้ายชนิดหน้า) — (None, ...) ถ้าหน้านั้นไม่คิดเกณฑ์"""
    has_img = bool(s.get("image_prompt") or s.get("image_file"))
    sec = s.get("section")
    if sec == "question":
        return (LIMITS["question_image"] if has_img else LIMITS["question_plain"],
                "คำถาม" + ("+รูป" if has_img else ""))
    if sec in ("vocab", "cover"):
        return (None, "ตารางศัพท์" if sec == "vocab" else "หน้าปก")
    return (LIMITS["content_image"] if has_img else LIMITS["content_plain"],
            "เนื้อหา" + ("+รูป" if has_img else ""))


def _grade(s):
    """จัดระดับหน้า: 'ok' | 'tight' (แน่นแต่ยังไม่แตกหน้า) | 'over' (เกินเพดาน จะถูกแตกหน้า)

    คืน (ระดับ, จำนวนอักษร, (แนะนำ, เพดาน) หรือ None, ป้ายชนิดหน้า)
    """
    lim, kind = _limit_for(s)
    if lim is None:
        return "ok", 0, None, kind
    n = sum(len(x) for x in _items_of(s))
    ok, hard = lim
    return ("over" if n > hard else "tight" if n > ok else "ok"), n, lim, kind


def _pages_of(s):
    """จำนวนหน้าที่ engine จะ render จริง (หน้าที่แน่นเกินจะถูกแตกเป็น '(ต่อ)')"""
    sec = s.get("section")
    if sec == "vocab":
        rows = max(0, len(s.get("table", [])) - 1)
        return max(1, -(-rows // VOCAB_WORDS))
    if sec in ("cover", "question"):
        return 1
    items = _items_of(s)
    if not items:
        return 1
    title = s.get("title", "")
    top = max(pc.title_metrics(title)[2], pc.title_metrics(title + " (ต่อ)")[2])
    h = BOTTOM_IN - top
    has_img = bool(s.get("image_prompt") or s.get("image_file"))
    if has_img:
        first = pc.fit_pages(items, pc.BODY_FONT, pc.SIZE["bullet"],
                             pc.COL_L_BOX[2], h)[0]
        rest = items[len(first):]
        return 1 + (len(pc.fit_pages(rest, pc.BODY_FONT, pc.SIZE["bullet"],
                                     pc.BODY_BOX[2], h)) if rest else 0)
    return len(pc.fit_pages(items, pc.BODY_FONT, pc.SIZE["bullet"],
                            pc.BODY_BOX[2], h))


def _text_cell(s):
    """คอลัมน์ 2 — ข้อความที่ปรากฏบนสไลด์ (หัวข้อตัวหนา + บรรทัดเนื้อหา + ป้ายเตือนถ้าเกิน)"""
    lines = []
    title = (s.get("title") or "").strip()
    if title:
        mark = "" if len(title) <= TITLE_MAX else \
            "  [หัวข้อยาว %d อักษร เกณฑ์ %d]" % (len(title), TITLE_MAX)
        lines.append("**%s**%s" % (title, mark))
    if s.get("hook_question"):
        lines.append("(คำถามชวนคิดบนหน้าปก) %s" % s["hook_question"])
    elif s.get("question"):
        lines.append(s["question"])
    for x in (s.get("bullets") or s.get("items") or []):
        lines.append("• %s" % x)
    if s.get("section") == "vocab":
        tb = s.get("table") or []
        for row in tb[1:]:
            lines.append("• %s" % " / ".join(str(c) for c in row))

    g, n, lim, kind = _grade(s)
    if lim is not None:
        ok, hard = lim
        if g == "over":
            lines.append("**[เกินเพดาน %d อักษร — หน้า%s รับได้ %d จะถูกแตกเป็นหน้า (ต่อ)]**"
                         % (n, kind, hard))
        elif g == "tight":
            lines.append("**[แน่น %d อักษร — เกณฑ์แนะนำ %d (ยังไม่แตกหน้า)]**" % (n, ok))
        else:
            lines.append("(%d อักษร / เกณฑ์แนะนำ %d)" % (n, ok))
    return lines or ["(ไม่มีข้อความบนจอ)"]


def _image_cell(s, stem, no, desc):
    """คอลัมน์ 3 — ภาพประกอบ: ชื่อไฟล์ที่ต้องใส่ + คำบรรยายไทย + prompt อังกฤษเต็ม"""
    if not (s.get("image_prompt") or s.get("image_file")):
        return ["-"]
    out = ["**ใส่รูปประกอบ 1 รูป**", "ชื่อไฟล์: %s" % sm.asset_name(stem, no)]
    if desc:
        out.append("รายละเอียด: %s" % desc)
    if s.get("image_prompt"):
        prompt, _trimmed = sm.clean_prompt(s["image_prompt"])
        out.append("prompt (คัดลอกไปวาง Google Nano Banana):")
        out.append(prompt)
    if s.get("image_file"):
        out.append("ไฟล์ที่ใส่แล้ว: %s" % s["image_file"])
    return out


# ---------------------------------------------------------------- ประกอบเอกสาร
def collect(slides_dir, base, imgdesc):
    """อ่านสไลด์ทั้ง 4 แหล่ง -> โครงข้อมูลกลางที่ใช้สร้างได้ทั้ง .docx และ .md"""
    decks = []
    for src in SOURCES:
        path = os.path.join(slides_dir, "%s_slides_%s.json" % (base, src))
        if not os.path.exists(path):
            print("WARN: ไม่พบ %s — ข้ามแหล่งนี้" % os.path.basename(path), file=sys.stderr)
            continue
        with io.open(path, encoding="utf-8-sig") as f:
            spec = json.load(f)
        stem = "%s_slides_%s" % (base, src)
        rows, pages, imgs, over, tight = [], 0, 0, 0, 0
        for i, s in enumerate(spec.get("slides", []), 1):
            p = _pages_of(s)
            pages += p
            has_img = bool(s.get("image_prompt") or s.get("image_file"))
            imgs += 1 if has_img else 0
            g = _grade(s)[0]
            over += 1 if g == "over" else 0
            tight += 1 if g == "tight" else 0
            no_cell = str(i) if p == 1 else "%d\n(render %d หน้า)" % (i, p)
            rows.append([no_cell, _text_cell(s),
                         _image_cell(s, stem, i, (imgdesc.get(src) or {}).get(str(i), ""))])
        decks.append({"src": src, "rows": rows, "authored": len(spec.get("slides", [])),
                      "pages": pages, "images": imgs, "over": over, "tight": tight,
                      "header": spec.get("header", "")})
    return decks


def _std_rows(cap):
    cp, ci = LIMITS["content_plain"], LIMITS["content_image"]
    qp, qi = LIMITS["question_plain"], LIMITS["question_image"]
    return [
        ["หน้าเนื้อหา ไม่มีรูป (เต็มความกว้าง)", "**%d อักษร**" % cp[0],
         "เพดาน %d · บุลเล็ต 3-%d ข้อ" % (cp[1], BULLETS_PLAIN)],
        ["หน้าเนื้อหา มีรูป (ข้อความอยู่ครึ่งจอ)", "**%d อักษร**" % ci[0],
         "เพดาน %d · บุลเล็ต 2-%d ข้อ" % (ci[1], BULLETS_IMAGE)],
        ["หน้าคำถาม ไม่มีรูป", "**%d อักษร**" % qp[0],
         "เพดาน %d · ตัวอักษร %dpt" % (qp[1], pc.SIZE["question_solo"])],
        ["หน้าคำถาม มีรูป", "**%d อักษร**" % qi[0],
         "เพดาน %d · ตัวอักษร %dpt" % (qi[1], pc.SIZE["question"])],
        ["หัวข้อของหน้า", "**%d อักษร**" % TITLE_MAX,
         "พอดี 1 บรรทัดที่ %dpt — ยาวกว่านี้ต้องขึ้น 2 บรรทัดแล้วดันเนื้อหาลง" % pc.SIZE["title"]],
        ["ตารางคำศัพท์", "**%d คำต่อหน้า**" % VOCAB_WORDS, "ตาม Master Prompt"],
        ["ต่อบุลเล็ต 1 ข้อ", "ไม่เกิน **2 บรรทัด**",
         "~%d อักษรเต็มกว้าง · ~%d อักษรคอลัมน์แคบ"
         % (cap["plain"]["chars"] * 2, cap["image"]["chars"] * 2)],
    ]


def build_docx(out_path, title, header, cap, decks):
    doc = dc.new_document(header)
    dc.add_heading(doc, title, size=dc.COVER_TITLE_SIZE, space_after=4)
    dc.add_paragraph(doc, "สคริปต์ข้อความบนสไลด์ทั้ง 4 แหล่ง สำหรับตรวจก่อนนำไปสอน",
                     align="center", space_after=10)

    dc.add_heading(doc, "มาตรฐานข้อความต่อสไลด์", size=dc.HEADING_SIZE)
    dc.add_paragraph(doc,
                     "ตัวเลขด้านล่างมาจากการวัดความจุจริงของสไลด์ ไม่ใช่การกะเอา: ตัวอักษรเนื้อหา "
                     "%dpt บนพื้นที่ %.2f นิ้ว ใส่ได้ประมาณ **%.0f บรรทัดต่อหน้า** โดยเต็มความกว้าง "
                     "ได้ราว **%d อักษรไทยต่อบรรทัด** ส่วนหน้าที่มีรูปข้อความเหลือครึ่งจอจึงได้ราว "
                     "**%d อักษรต่อบรรทัด** เกณฑ์ที่ตั้งไว้อยู่ที่ประมาณ 85%% ของความจุจริง "
                     "เพื่อให้เหลือที่ว่างหายใจ ไม่ใช่ใส่จนเต็มพอดี"
                     % (cap["size"], pc.BODY_BOX[3], cap["lines"],
                        cap["plain"]["chars"], cap["image"]["chars"]))
    dc.add_content_table(doc, ["รายการ", "เกณฑ์แนะนำ", "หมายเหตุ"], _std_rows(cap))
    dc.add_paragraph(doc, "", space_after=4)
    dc.add_paragraph(doc,
                     "**เกณฑ์แนะนำ** คือระดับที่หน้าดูโปร่ง อ่านสบาย ส่วน **เพดาน** คือความจุจริง "
                     "ของกรอบ เกินเพดานเมื่อไรโปรแกรมจะแตกเป็นหน้า \"(ต่อ)\" ให้อัตโนมัติ "
                     "(ไม่ย่อตัวอักษร) จึงไม่พัง แต่จำนวนหน้าจะบานและจังหวะการสอนสะดุด "
                     "ในตารางแต่ละแหล่ง หน้าที่อยู่ระหว่างสองค่าจะมีป้าย [แน่น] "
                     "ส่วนหน้าที่เกินเพดานจะมีป้าย [เกินเพดาน] กำกับไว้")

    dc.add_paragraph(doc, "", space_after=4)
    dc.add_content_table(doc, ["แหล่ง", "หน้าที่เขียน", "render จริง", "รูป", "แน่น", "เกินเพดาน"],
                         [[d["src"], str(d["authored"]), str(d["pages"]), str(d["images"]),
                           str(d["tight"]), str(d["over"])] for d in decks])

    for d in decks:
        doc.add_page_break()
        dc.add_heading(doc, SRC_LABEL[d["src"]], size=dc.HEADING_SIZE)
        dc.add_paragraph(doc, "เขียนไว้ %d หน้า · render จริง %d หน้า · มีรูป %d หน้า · "
                              "แน่น %d หน้า · เกินเพดาน %d หน้า"
                         % (d["authored"], d["pages"], d["images"], d["tight"], d["over"]),
                         align="left", space_after=6)
        dc.add_content_table(doc, ["สไลด์", "ข้อความที่ปรากฏบนสไลด์", "ภาพประกอบ"], d["rows"])
    dc.save(doc, out_path)
    return out_path


def _md_cell(lines):
    """เซลล์ markdown — ขึ้นบรรทัดใหม่ในเซลล์ต้องใช้ <br> และต้อง escape ท่อ"""
    return "<br>".join(str(x).replace("|", "\\|") for x in lines)


def build_md(out_path, title, header, cap, decks):
    L = ["# %s" % title, "", "> %s" % header, "",
         "## มาตรฐานข้อความต่อสไลด์", "",
         "วัดจากความจุจริง: ตัวอักษร %dpt · ~%.0f บรรทัด/หน้า · เต็มความกว้าง ~%d อักษร/บรรทัด · "
         "หน้ามีรูป ~%d อักษร/บรรทัด (เกณฑ์ตั้งไว้ ~85%% ของความจุ)"
         % (cap["size"], cap["lines"], cap["plain"]["chars"], cap["image"]["chars"]), "",
         "| รายการ | เกณฑ์แนะนำ | หมายเหตุ |", "|---|---|---|"]
    L += ["| %s | %s | %s |" % (a, b, c) for a, b, c in _std_rows(cap)]
    L += ["", "| แหล่ง | หน้าที่เขียน | render จริง | รูป | แน่น | เกินเพดาน |",
          "|---|---|---|---|---|---|"]
    L += ["| %s | %d | %d | %d | %d | %d |" % (d["src"], d["authored"], d["pages"],
                                               d["images"], d["tight"], d["over"])
          for d in decks]
    for d in decks:
        L += ["", "## %s" % SRC_LABEL[d["src"]], "",
              "| สไลด์ | ข้อความที่ปรากฏบนสไลด์ | ภาพประกอบ |", "|---|---|---|"]
        for no, text, img in d["rows"]:
            L.append("| %s | %s | %s |" % (str(no).replace("\n", " "),
                                           _md_cell(text), _md_cell(img)))
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    io.open(out_path, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    return out_path


def main():
    ap = argparse.ArgumentParser(description="สร้างเอกสารสคริปต์สไลด์ 4 แหล่ง (.docx + .md)")
    ap.add_argument("grade")
    ap.add_argument("subject")
    ap.add_argument("no")
    ap.add_argument("--name", default="Script pptx 4 อัน", help="ชื่อไฟล์/หัวเรื่องของเอกสาร")
    a = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    paths_py = os.path.join(here, "..", "..", "shared", "scripts", "paths.py")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = json.loads(subprocess.run([sys.executable, paths_py, a.grade, a.subject, str(a.no)],
                                  capture_output=True, text=True, encoding="utf-8",
                                  env=env, check=True).stdout)
    base, slides_dir = p["base"], p["dirs"]["slides"]

    desc_path = os.path.join(slides_dir, "%s_slides_imgdesc.json" % base)
    imgdesc = {}
    if os.path.exists(desc_path):
        with io.open(desc_path, encoding="utf-8-sig") as f:
            imgdesc = json.load(f)
    else:
        print("WARN: ไม่พบ %s — คอลัมน์ภาพจะมีแต่ prompt อังกฤษ ไม่มีคำบรรยายไทย"
              % os.path.basename(desc_path), file=sys.stderr)

    cap = measure_capacity()
    decks = collect(slides_dir, base, imgdesc)
    if not decks:
        print("ไม่พบไฟล์สไลด์แม้แต่แหล่งเดียว", file=sys.stderr)
        return 1
    header = decks[0]["header"]

    docx_out = os.path.join(slides_dir, a.name + ".docx")
    md_out = os.path.join(slides_dir, a.name + ".md")
    build_docx(docx_out, a.name, header, cap, decks)
    build_md(md_out, a.name, header, cap, decks)
    print("OK -> %s" % docx_out)
    print("OK -> %s" % md_out)
    print("รวม %d แหล่ง · %d หน้าที่เขียน · render %d หน้า · รูป %d · แน่น %d · เกินเพดาน %d"
          % (len(decks), sum(d["authored"] for d in decks), sum(d["pages"] for d in decks),
             sum(d["images"] for d in decks), sum(d["tight"] for d in decks),
             sum(d["over"] for d in decks)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
