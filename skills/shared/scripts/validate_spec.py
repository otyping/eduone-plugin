# -*- coding: utf-8 -*-
"""
validate_spec.py — ตรวจ artifact JSON ให้ตรงสเปก **ก่อนส่งให้ checkwork** (EDU ONE)

ทำไมต้องมี: กฎเชิงตัวเลข/โครงสร้างของโปรเจกต์ (โควตาความยาก · เวลากิจกรรมรวมเท่ากับคาบ ·
หน้าปก verbatim · ห้าม prefix ก./ข. · คำต้องห้ามบนสไลด์ L1/L2 ฯลฯ) เคยเขียนไว้เป็นร้อยแก้ว
ในสเปกเฉย ๆ แล้วให้ checkwork (LLM) นั่งอ่านตรวจเอง ทำให้เสียรอบแก้ไปกับเรื่องที่เครื่อง
ตรวจได้ในเสี้ยววินาที — ไฟล์นี้ย้ายกฎกลุ่มนั้นมาเป็นสคริปต์ เพื่อให้ checkwork เหลือเวลา
ไปตรวจสิ่งที่ต้องใช้วิจารณญาณจริง (ความถูกต้องของเนื้อหา ความสอดคล้องภายใน ระดับความยาก)

ใช้:
  validate_spec.py content     <json> [--ref <C1.json>]
  validate_spec.py lesson_plan <json> [--ref <C1.json>] [--minutes 50] [--peer <อีกแผน>]
  validate_spec.py exercise    <json>
  validate_spec.py slides      <json>
  validate_spec.py song        <json>
  validate_spec.py video       <json>
  validate_spec.py game        <json> [--ref <{BASE}_ex.json>]   # เทียบเฉลยกับต้นทาง
  validate_spec.py --agents                 # ตรวจ frontmatter ของ .claude/agents/*.md

exit 0 = ผ่าน / 1 = พบปัญหา / 2 = usage      (`--strict` นับ WARN เป็นปัญหาด้วย)

รันผ่านตัวห่อ: eduone-py <ชื่อไฟล์นี้> <args>  (หา Python 3.12 ให้เองทุก OS)
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")
JUNK_RE = re.compile("[�]")
THAI_RE = re.compile(r"[฀-๿]")
# รับทั้ง "(8 นาที)" และ "(ทฤษฎี - 8 นาที)" — ชื่อขั้นแบบใหม่มีคำนำหน้าในวงเล็บ
MINUTE_RE = re.compile(r"\((?:[^()]*?)?(\d+)\s*นาที\)")
CHOICE_PREFIX_RE = re.compile(r"^\s*[กขคง][.)]\s")

# โควตาความยากตามตารางใน prompt-master-exercise (50/25/25)
QUOTA = {20: (10, 5, 5), 30: (15, 8, 7), 40: (20, 10, 10)}

# ศัพท์ของแผนการสอน — ห้ามขึ้นจอในสไลด์ L1/L2 (อยู่ใน speaker_note ได้)
PLAN_WORDS = ["ขั้นนำ", "ขั้นสอน", "ขั้นสรุป", "ขั้นวัดผลการเรียนรู้", "สมรรถนะ",
              "Rubric", "รูบริก", "การวัดและประเมินผล", "วัสดุและอุปกรณ์",
              "ด้านความรู้ (K)", "ด้านทักษะ (P)", "ด้านคุณลักษณะ (A)"]

# โครงแผนการสอน L1/L2 — 8 หัวข้อ ชื่อและลำดับตายตัว
# ★ ทุกที่ที่อ้างแถวต้องอ้างผ่านดัชนีข้างล่างนี้ ห้ามอ้างด้วย "แถวสุดท้าย" หรือ
#   startswith("<เลข>.") อีก — ของเดิมทำแบบนั้นแล้วประตูตรวจเวลาหลุดเงียบเมื่อเลขเปลี่ยน
PLAN_HEADS = [
    "1. ชื่อแผนการจัดการเรียนรู้",
    "2. วัตถุประสงค์การเรียนรู้",
    "3. ทักษะ 8C",
    "4. กิจกรรมการเรียนรู้",
    "5. วัสดุและอุปกรณ์",
    "6. การวัดและประเมินผล",
    "7. เกณฑ์การประเมิน (Rubric)",
    "8. การนำไปใช้ในชีวิตประจำวัน",
]
PLAN_KPA_IDX = 1
PLAN_8C_IDX = 2
PLAN_ACT_IDX = 3
PLAN_RUBRIC_IDX = 6
SKILLS_8C_CODES = ["C%d" % i for i in range(1, 9)]
ACT_STAGES = ["ขั้นนำ", "ขั้นสอน", "ขั้นสรุป", "ขั้นวัดผลการเรียนรู้"]

# หัวข้อ 2 ต้องมี 3 บรรทัดนี้เท่านั้น ตามชื่อนี้เป๊ะ
# ★ "ต้องกระชับ ไม่อธิบายยาว" เป็นข้อกำหนดของผู้ใช้ — ถ้าไม่มีเพดานเชิงตัวเลข
#   writer จะเขียนยาวขึ้นเรื่อย ๆ และเอาสาระสำคัญ/ขอบเขตที่ตัดออกไปแล้วกลับเข้ามาอีก
#   (เกิดจริงรอบแรกหลังเปลี่ยนโครง: หัวข้อ 2 บวมเป็น 16 บรรทัด บรรทัดละ ~250 อักษร)
PLAN_KPA_LABELS = ["ด้านความรู้ (K)", "ด้านทักษะ (P)", "ด้านคุณลักษณะ (A)"]
PLAN_KPA_MAX = 300
PLAN_8C_MAX = 240

PLAN_TITLE_IDX = 0
PLAN_MATERIAL_IDX = 4
PLAN_ASSESS_IDX = 5
#: แถว 1 = **ชื่อกิจกรรม** ไม่ใช่ชื่อเอกสาร — คำพวกนี้แปลว่า writer ใส่ชื่อเอกสารมา
#: (เกิดจริง: "แผนการจัดการเรียนรู้ที่ 1 เรื่อง ... (การเรียนรู้เชิงสำรวจ 50 นาที)")
PLAN_TITLE_BAN = ["แผนการจัดการเรียนรู้", "แผนการสอน", "แบบที่ 1", "แบบที่ 2",
                  "Inquiry-Based", "Activity-Based"]
PLAN_TITLE_MAX = 60
#: ขั้นวัดผลต้องอ้างแบบฝึกหัดชุดจริงของคาบ ไม่ใช่ใบงานที่แต่งขึ้นใหม่
PLAN_EXERCISE_HINTS = ["แบบฝึกหัด", "_ex.json", "ข้อ"]
#: หัวข้อ 6 ห้ามชี้ระดับ "ข้อที่เท่าไร" — ครูเลือกข้อเอง
PLAN_ASSESS_BAN_RE = re.compile(r"(ใบงาน|แบบฝึกหัด|ใบกิจกรรม)\s*(ข้อ(ที่)?\s*\d|ตอนที่\s*\d)")
TEACHER_RE = re.compile(r"(^|[\s\"'(])ครู|ให้นักเรียน")

# ป้ายชื่อ 7 แถวของตารางหน้าปก (C1 C2 L1 L2 ใช้ชุดเดียวกัน ต้องตรงกันตัวต่อตัว)
# ★ ชื่อสองแถวท้ายตรงกับชื่อคอลัมน์ในโครงสร้างหลักสูตรของ สสวท. พอดี
#   แถว "จุดประสงค์ประจำหน่วย" = คอลัมน์ E (OBJ ระดับหน่วย)
#   แถว "สาระสำคัญ / จุดประสงค์ประจำคาบ" = คอลัมน์ I (COMP ระดับคาบ)
#   เดิมสองแถวนี้ชื่อ "...ระดับหน่วยการเรียน" ทั้งคู่ และแถวท้ายใส่ COMP ระดับหน่วย
#   ซึ่งไม่มีอยู่ในหลักสูตร — เปิดหลักสูตรเทียบหน้าปกแล้วหาที่มาไม่เจอ
COVER_LABELS = ["รหัสวิชา", "วิชา", "หน่วย", "ตัวชี้วัด", "เรื่อง",
                "จุดประสงค์ประจำหน่วย", "สาระสำคัญ / จุดประสงค์ประจำคาบ"]

#: นโยบายโมเดลของโปรเจกต์ (CLAUDE.md ข้อ 8) — agent ทุกตัวต้องเป็นรุ่นนี้
REQUIRED_MODEL = "opus"

SLIDE_ANCHORS = ["cover", "objectives", "summary", "application", "vocab"]
SLIDE_MIDDLE = {"content", "question", "example", "formula", "steps",
                "compare", "triple", "lesson_info"}


class Report:
    def __init__(self):
        self.problems: list[str] = []
        self.warns: list[str] = []
        #: สิ่งที่ "เครื่องวัดไปแล้ว" พร้อมค่าที่วัดได้ — ใช้เขียน {BASE}_gate.md
        #: เพื่อบอก checkwork ว่าอย่าเสียแรงนับซ้ำ ให้ไปตรวจสิ่งที่เครื่องตรวจไม่ได้แทน
        self.notes: list[tuple[str, str]] = []

    def fail(self, msg):
        self.problems.append(msg)

    def warn(self, msg):
        self.warns.append(msg)

    def note(self, what, value):
        self.notes.append((what, str(value)))

    def done(self, what, strict=False):
        for w in self.warns:
            print("  WARN: %s" % w)
        if self.problems or (strict and self.warns):
            n = len(self.problems) + (len(self.warns) if strict else 0)
            print("\nFAIL — %s พบ %d ปัญหา:" % (what, n))
            for i, p in enumerate(self.problems, 1):
                print("  %d. %s" % (i, p))
            if strict and self.warns and not self.problems:
                print("  (โหมด strict: นับ WARN เป็นปัญหา)")
            return 1
        print("OK — %s ผ่านทุก check" % what)
        return 0


# ---------------------------------------------------------------- ตัวช่วยร่วม
def load(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def walk_strings(node, where=""):
    """ไล่ทุก string ใน JSON พร้อมตำแหน่ง"""
    if isinstance(node, str):
        yield where, node
    elif isinstance(node, list):
        for i, x in enumerate(node):
            yield from walk_strings(x, "%s[%d]" % (where, i))
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from walk_strings(v, "%s.%s" % (where, k) if where else k)


def common_checks(data, rep):
    """กฎที่ใช้กับทุกผลผลิต"""
    for where, text in walk_strings(data):
        if EMOJI_RE.search(text):
            rep.fail("มี emoji ที่ %s: %r" % (where, text[:40]))
        if JUNK_RE.search(text):
            rep.fail("มีอักขระเสีย (U+FFFD) ที่ %s: %r" % (where, text[:40]))
        if "​" in text:
            rep.fail("มี ZWSP ค้างใน artifact ที่ %s (ต้องแทรกตอน build เท่านั้น)" % where)
    header = data.get("header")
    if header is not None and header.count(">") < 2:
        rep.warn("header ควรมีรูปแบบ 'ระดับชั้น... > วิชา... > เรื่อง...' — ได้ %r" % header[:60])


def run_check_math(path, rep):
    """เรียกตัวตรวจสัญลักษณ์คณิตที่มีอยู่แล้ว ไม่เขียนกฎซ้ำ"""
    try:
        import check_math
    except Exception as exc:
        rep.warn("เรียก check_math ไม่ได้ (%s)" % exc)
        return
    argv = sys.argv
    try:
        sys.argv = ["check_math.py", path]
        import io as _io
        import contextlib
        buf = _io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = check_math.main()
        if rc != 0:
            rep.fail("check_math ไม่ผ่าน — รัน `check_math.py %s` เพื่อดูรายละเอียด" % path)
    except SystemExit as exc:
        if exc.code:
            rep.fail("check_math ไม่ผ่าน (exit %s)" % exc.code)
    finally:
        sys.argv = argv


def cover_of(data):
    return json.dumps(data.get("cover", {}).get("rows", []), ensure_ascii=False,
                      sort_keys=True)


# ---------------------------------------------------------------- content
# ขอบเขตของ digest — ต้องพอใช้แทน C1 ได้ แต่ต้องสั้นพอที่จะประหยัดจริง
DIGEST_KEYS = {"facts", "vocab", "examples", "cautions"}
DIGEST_BOUNDS = {"facts": (6, 15), "vocab": (3, 15), "examples": (1, 8), "cautions": (1, 8)}
DIGEST_MAX_CHARS = 4500


def check_digest(data, rep):
    """`digest` = สรุปแกนของ C1 ที่ srcpack.py เอาไปทำ source pack ให้ agent ปลายน้ำ

    ไม่มี = WARN (artifact เก่ายังใช้ได้ ปลายน้ำถอยไปอ่าน C1 เต็ม)
    มีแต่ผิดรูป = FAIL (ปลายน้ำจะได้ข้อมูลเพี้ยนโดยไม่มีใครรู้)
    """
    dg = data.get("digest")
    is_c1 = str(data.get("mode_label", "")).startswith("แบบที่ 1")
    if dg is None:
        if is_c1:
            rep.warn("C1 ไม่มี `digest` — agent ปลายน้ำจะต้องอ่าน C1 เต็มแทน "
                     "(artifact เก่า: ให้ content-academic เติมเมื่อแก้ไขครั้งต่อไป)")
        return
    if not is_c1:
        rep.warn("`digest` ควรมีเฉพาะใน C1 — C2 ไม่ต้องมี")
    if not isinstance(dg, dict):
        rep.fail("`digest` ต้องเป็น object ที่มีคีย์ %s" % "/".join(sorted(DIGEST_KEYS)))
        return

    unknown = set(dg) - DIGEST_KEYS
    if unknown:
        rep.fail("`digest` มีคีย์ที่ไม่รองรับ: %s (รองรับเฉพาะ %s)"
                 % (sorted(unknown), "/".join(sorted(DIGEST_KEYS))))
    for key in sorted(DIGEST_KEYS):
        val = dg.get(key)
        if val is None:
            rep.fail("`digest.%s` ขาดหาย" % key)
            continue
        if not isinstance(val, list):
            rep.fail("`digest.%s` ต้องเป็น list" % key)
            continue
        lo, hi = DIGEST_BOUNDS[key]
        if not (lo <= len(val) <= hi):
            rep.fail("`digest.%s` ต้องมี %d-%d รายการ — พบ %d" % (key, lo, hi, len(val)))
        if key == "vocab":
            for i, v in enumerate(val, 1):
                if not (isinstance(v, list) and len(v) == 3
                        and all(isinstance(c, str) and c.strip() for c in v)):
                    rep.fail("`digest.vocab[%d]` ต้องเป็น [คำ, คำอ่าน, ความหมาย] "
                             "ที่เป็นสตริงไม่ว่างครบ 3 ช่อง — พบ %r" % (i, v))
        else:
            for i, s in enumerate(val, 1):
                if not isinstance(s, str) or len(s.strip()) < 10:
                    rep.fail("`digest.%s[%d]` ต้องเป็นประโยคยาวอย่างน้อย 10 อักษร — พบ %r"
                             % (key, i, s))

    total = len(json.dumps(dg, ensure_ascii=False))
    if total > DIGEST_MAX_CHARS:
        rep.fail("`digest` ยาว %d อักษร เกิน %d — ย่อให้สั้นลง มิฉะนั้นไม่ประหยัดกว่าอ่าน C1 เต็ม"
                 % (total, DIGEST_MAX_CHARS))


#: หัวข้อสรุปที่ C1/C2 ไม่ต้องมี — รับทั้งที่มีเลขนำหน้าและไม่มี
SUMMARY_HEAD_RE = re.compile(r"^\s*(?:\d+[.)]\s*)?(สรุป|บทสรุป|สรุปท้ายบท|สรุปเนื้อหา)\b")

#: เซลล์ที่ยาวเกินนี้แปลว่าเป็นย่อหน้าที่ถูกยัดลงช่อง ไม่ใช่ข้อมูลตาราง
TABLE_CELL_MAX = 160


def check_table(block, idx, rep):
    """ตารางไม่บังคับว่าต้องมี — แต่ถ้ามีต้องเป็นตารางจริง ไม่ใช่ย่อหน้าที่จัดเป็นช่อง"""
    header = block.get("header") or []
    rows = block.get("rows") or []
    widths = {len(r) for r in rows}
    if len(widths) > 1:
        rep.fail("body[%d] ตารางมีจำนวนคอลัมน์ไม่เท่ากัน: %s" % (idx, sorted(widths)))
    if not header or any(not str(h).strip() for h in header):
        rep.fail("body[%d] ตารางต้องมี header ครบทุกคอลัมน์" % idx)
    ncol = len(header) or (max(widths) if widths else 0)
    if ncol < 2:
        rep.fail("body[%d] ตารางต้องมีอย่างน้อย 2 คอลัมน์ — พบ %d" % (idx, ncol))
    if len(rows) < 2:
        rep.fail("body[%d] ตารางต้องมีอย่างน้อย 2 แถวข้อมูล — พบ %d "
                 "(น้อยกว่านี้เขียนเป็นย่อหน้าอ่านง่ายกว่า)" % (idx, len(rows)))
    if header and widths and max(widths) != len(header):
        rep.fail("body[%d] จำนวนคอลัมน์ของ rows (%d) ไม่ตรงกับ header (%d)"
                 % (idx, max(widths), len(header)))
    for r, row in enumerate(rows, 1):
        for c, cell in enumerate(row, 1):
            if len(str(cell)) > TABLE_CELL_MAX:
                rep.fail("body[%d] ตารางแถว %d ช่อง %d ยาว %d อักษร — "
                         "เกิน %d แปลว่าเป็นย่อหน้าที่ถูกยัดลงตาราง"
                         % (idx, r, c, len(str(cell)), TABLE_CELL_MAX))
    for c in range(ncol):
        if rows and all(not str(row[c]).strip() for row in rows if c < len(row)):
            rep.fail("body[%d] ตารางคอลัมน์ที่ %d ว่างทุกแถว" % (idx, c + 1))


def check_content(data, rep, ref=None):
    cover = data.get("cover") or {}
    rows = cover.get("rows") or []
    want = COVER_LABELS
    if len(rows) != len(want):
        rep.fail("cover.rows ต้องมี %d แถว — พบ %d" % (len(want), len(rows)))
    else:
        for i, (row, label) in enumerate(zip(rows, want), 1):
            if not row or row[0] != label:
                rep.fail("cover.rows แถวที่ %d ต้องเป็น %r — พบ %r" % (i, label, row[0] if row else None))
    if not data.get("mode_label", "").startswith("แบบที่"):
        rep.fail("mode_label ต้องขึ้นต้นด้วย 'แบบที่ ...' — พบ %r" % data.get("mode_label"))
    ok_types = {"h", "p", "table", "ep", "eq"}
    for i, b in enumerate(data.get("body", []), 1):
        t = b.get("type")
        if t not in ok_types:
            rep.fail("body[%d] ชนิด %r ไม่รองรับ (ต้องเป็น %s)" % (i, t, "/".join(sorted(ok_types))))
        if t == "table":
            check_table(b, i, rep)
        if t == "h" and SUMMARY_HEAD_RE.match(str(b.get("text") or "")):
            # เอกสารนี้เป็นสื่อประกอบการสอน ครูสรุปเองในคาบ และแบบฝึกหัดทบทวนอยู่แล้ว
            rep.fail("body[%d] มีหัวข้อสรุป (%r) — C1/C2 ไม่ต้องมีหัวข้อสรุป"
                     % (i, b.get("text")))
    if ref is not None and cover_of(data) != cover_of(ref):
        rep.fail("cover.rows ไม่ตรงกับไฟล์อ้างอิง (C1↔C2 ต้องเหมือนกันทุกตัวอักษร)")
    body = data.get("body", [])
    kinds = {}
    for b in body:
        kinds[b.get("type")] = kinds.get(b.get("type"), 0) + 1
    rep.note("หน้าปก", "%d แถว ชื่อและลำดับตรงมาตรฐาน" % len(rows))
    rep.note("ชนิด block", " · ".join("%s=%d" % kv for kv in sorted(kinds.items())))
    rep.note("หัวข้อสรุป", "ไม่มี (ตรวจแล้ว)")
    rep.note("ตาราง", "%d ตาราง — header/คอลัมน์/ความยาวเซลล์ ตรวจแล้ว" % kinds.get("table", 0))
    if ref is not None:
        rep.note("หน้าปกตรงไฟล์อ้างอิง", "ตรวจแล้ว verbatim")
    check_digest(data, rep)


# ---------------------------------------------------------------- lesson_plan
def check_plan_pair(data, peer, rep):
    """L1 กับ L2 ต้องเป็นคนละกิจกรรมจริง ไม่ใช่แผนเดียวกันเปลี่ยนคำ

    ตรวจข้ามไฟล์จึงต้องรับคู่ของมันมาด้วย (`--peer`) — ของที่ต้องต่างกัน:
    ชื่อกิจกรรม · plan_title · และ **skill ใน Rubric** ซึ่งเคยเหมือนกันเป๊ะ
    ทำให้ตาราง Rubric ของสองแผนออกมาตัวอักษรเดียวกันทั้งที่กิจกรรมต่างกันมาก
    """
    a = (data.get("plan") or {}).get("rows") or []
    b = (peer.get("plan") or {}).get("rows") or []
    if not a or not b:
        return
    if data.get("plan_title") == peer.get("plan_title"):
        rep.fail("plan_title ของ L1 กับ L2 เหมือนกัน — ต้องระบุแบบที่ 1 / แบบที่ 2 ให้ต่างกัน")
    if len(a) > PLAN_TITLE_IDX and len(b) > PLAN_TITLE_IDX:
        if str(a[PLAN_TITLE_IDX][1]).strip() == str(b[PLAN_TITLE_IDX][1]).strip():
            rep.fail("ชื่อกิจกรรม (หัวข้อ 1) ของ L1 กับ L2 เหมือนกัน — เป็นคนละกิจกรรม "
                     "ต้องคนละชื่อ")
    if len(a) > PLAN_RUBRIC_IDX and len(b) > PLAN_RUBRIC_IDX:
        ra, rb = a[PLAN_RUBRIC_IDX][1], b[PLAN_RUBRIC_IDX][1]
        if isinstance(ra, dict) and isinstance(rb, dict):
            for key in ("skill", "topic"):
                if str(ra.get(key, "")).strip() and ra.get(key) == rb.get(key):
                    rep.fail("Rubric `%s` ของ L1 กับ L2 เหมือนกัน (%r) — ตาราง Rubric "
                             "จะออกมาตัวอักษรเดียวกันทั้งที่คนละกิจกรรม "
                             "ให้เขียนตามสิ่งที่แผนของตัวเองให้นักเรียนทำจริง"
                             % (key, str(ra.get(key))[:40]))


def check_lesson_plan(data, rep, ref=None, minutes=None):
    rows = (data.get("plan") or {}).get("rows") or []
    if len(rows) != len(PLAN_HEADS):
        rep.fail("plan.rows ต้องมี %d แถว — พบ %d" % (len(PLAN_HEADS), len(rows)))
    heads = [r[0] for r in rows if r]
    for i, want in enumerate(PLAN_HEADS):
        if i < len(heads) and heads[i].strip() != want:
            rep.fail("plan.rows แถวที่ %d ต้องเป็น %r — พบ %r" % (i + 1, want, heads[i][:40]))
    # Rubric อ้างด้วยดัชนีที่ระบุ ไม่ใช่ "แถวสุดท้าย" — ตอนนี้ Rubric อยู่แถว 7
    # ไม่ใช่แถวท้ายอีกแล้ว การอ้างตำแหน่งสุดท้ายจะพังเงียบเมื่อลำดับเปลี่ยน
    rub = rows[PLAN_RUBRIC_IDX][1] if len(rows) > PLAN_RUBRIC_IDX else None
    if len(rows) > PLAN_RUBRIC_IDX and not isinstance(rub, dict):
        rep.fail("แถว %d (Rubric) ต้องเป็น dict {template, topic, skill, codes}"
                 % (PLAN_RUBRIC_IDX + 1))
    elif isinstance(rub, dict):
        # ตรวจที่นี่ด้วย ไม่รอให้ไปพังตอน build — Rubric ต้องวัดจากมิติของ 8C
        # และใช้เฉพาะสองข้อที่หลักสูตรระบุว่าคาบนี้เน้น
        try:
            from build_lesson_plan import expand_rubric_template
            expand_rubric_template(rub)
        except ImportError:
            rep.warn("เรียก expand_rubric_template ไม่ได้ — ข้ามการตรวจ Rubric")
        except ValueError as exc:
            rep.fail("Rubric: %s" % exc)
    for i, r in enumerate(rows, 1):
        if len(r) != 2 or not isinstance(r[1], (str, list, dict)):
            rep.fail("plan.rows แถวที่ %d ต้องเป็น [หัวข้อ, str|list|dict]" % i)

    # หัวข้อ 1 — ชื่อ**กิจกรรม** ไม่ใช่ชื่อเอกสาร
    title = rows[PLAN_TITLE_IDX][1] if len(rows) > PLAN_TITLE_IDX else None
    if isinstance(title, str):
        for bad in PLAN_TITLE_BAN:
            if bad in title:
                rep.fail("หัวข้อ 1 ต้องเป็น **ชื่อกิจกรรม** (เช่น \"เดินทางไปกับเส้นจำนวน\") "
                         "ไม่ใช่ชื่อเอกสาร — พบคำว่า %r" % bad)
                break
        if len(title) > PLAN_TITLE_MAX:
            rep.fail("หัวข้อ 1 ยาว %d อักษร (เพดาน %d) — ชื่อกิจกรรมควรสั้นและจำง่าย"
                     % (len(title), PLAN_TITLE_MAX))

    # หัวข้อ 5 — วัสดุและอุปกรณ์ ต้องเป็น bullet รายการละบรรทัด
    mat = rows[PLAN_MATERIAL_IDX][1] if len(rows) > PLAN_MATERIAL_IDX else None
    if len(rows) > PLAN_MATERIAL_IDX and not isinstance(mat, list):
        rep.fail("หัวข้อ 5 วัสดุและอุปกรณ์ ต้องเป็น list (1 รายการ = 1 bullet)")
    elif isinstance(mat, list):
        for x in mat:
            if str(x).count(" · ") or str(x).count(", ") > 1:
                rep.warn("หัวข้อ 5 บรรทัด %r ดูเหมือนยัดหลายรายการไว้บรรทัดเดียว "
                         "— แยกเป็น bullet ละรายการ" % str(x)[:40])

    # หัวข้อ 6 — ห้ามชี้ว่าวัดจากใบงาน/แบบฝึกหัด "ข้อไหน" (ครูเลือกข้อเอง)
    assess = rows[PLAN_ASSESS_IDX][1] if len(rows) > PLAN_ASSESS_IDX else None
    for x in (assess if isinstance(assess, list) else [assess or ""]):
        m = PLAN_ASSESS_BAN_RE.search(str(x))
        if m:
            rep.fail("หัวข้อ 6 ระบุละเอียดถึงข้อที่วัด (%r) — บอกแค่วิธีวัด เครื่องมือ "
                     "และเกณฑ์ผ่านพอ ครูเป็นคนเลือกข้อเอง" % m.group(0))

    # หัวข้อ 2 — K/P/A เท่านั้น 3 บรรทัด และต้องกระชับ
    kpa = rows[PLAN_KPA_IDX][1] if len(rows) > PLAN_KPA_IDX else None
    if isinstance(kpa, list):
        if len(kpa) != 3:
            rep.fail("หัวข้อ 2 ต้องมี 3 บรรทัด (K/P/A) — พบ %d บรรทัด "
                     "ห้ามใส่สาระสำคัญ/ขอบเขต/ความเชื่อมโยงกลับเข้ามา" % len(kpa))
        for i, want in enumerate(PLAN_KPA_LABELS):
            if i >= len(kpa):
                break
            line = str(kpa[i])
            if want not in line.split(":", 1)[0]:
                rep.fail("หัวข้อ 2 บรรทัดที่ %d ต้องขึ้นต้นด้วย %r — พบ %r"
                         % (i + 1, want, line[:40]))
            if len(line) > PLAN_KPA_MAX:
                rep.fail("หัวข้อ 2 บรรทัด %s ยาว %d อักษร (เพดาน %d) — ต้องกระชับ "
                         "ไม่อธิบายยาว ไม่เล่ากิจกรรมซ้ำกับหัวข้อ 4"
                         % (want, len(line), PLAN_KPA_MAX))
    elif len(rows) > PLAN_KPA_IDX:
        rep.fail("หัวข้อ 2 ต้องเป็น list 3 บรรทัด (K/P/A)")

    # ทักษะ 8C ต้องครบทั้ง 8 ข้อ มีเนื้อจริง และกระชับ
    sk = rows[PLAN_8C_IDX][1] if len(rows) > PLAN_8C_IDX else None
    if isinstance(sk, list):
        if len(sk) != 8:
            rep.fail("หัวข้อ 3 ต้องมี 8 บรรทัด (C1-C8) — พบ %d" % len(sk))
        for code in SKILLS_8C_CODES:
            if not any(str(x).lstrip("*").strip().startswith(code) for x in sk):
                rep.fail("หัวข้อ 3 ทักษะ 8C ขาด %s" % code)
        for x in sk:
            body = str(x).split(":", 1)[-1].replace("*", "").strip()
            if len(body) < 10:
                rep.fail("หัวข้อ 3 ทักษะ 8C มีข้อที่เว้นว่าง/สั้นเกินไป: %r" % str(x)[:40])
            if len(str(x)) > PLAN_8C_MAX:
                rep.fail("หัวข้อ 3 %r ยาว %d อักษร (เพดาน %d) — เขียน 1 ประโยคพอ"
                         % (str(x)[:12], len(str(x)), PLAN_8C_MAX))
    elif len(rows) > PLAN_8C_IDX:
        rep.fail("หัวข้อ 3 ทักษะ 8C ต้องเป็น list 8 บรรทัด")

    # เวลารวมของขั้นกิจกรรม ต้องเท่ากับเวลาคาบ
    # ★ ถ้าหาแถวกิจกรรมไม่เจอต้องดังทันที — ของเดิมค้นด้วย startswith("6.") แล้วถ้า
    #   ไม่เจอจะได้ None แล้ว guard ข้างล่างข้ามการตรวจเวลาไปเงียบ ๆ โดยไม่มี error
    #   พอเปลี่ยนเลขหัวข้อทีเดียวประตูนี้ก็หลุดทั้งบานโดยไม่มีใครรู้
    act = rows[PLAN_ACT_IDX][1] if len(rows) > PLAN_ACT_IDX else None
    if minutes and not isinstance(act, list):
        rep.fail("หาแถวกิจกรรม (%s) ไม่เจอ หรือไม่ใช่ list — ตรวจเวลาคาบไม่ได้"
                 % PLAN_HEADS[PLAN_ACT_IDX])
    if minutes and isinstance(act, list):
        for stage in ACT_STAGES:
            if not any(stage in str(x) for x in act):
                rep.fail("หัวข้อ 4 กิจกรรม ขาดขั้น %r" % stage)
        # ขั้นวัดผลต้องให้นักเรียนทำแบบฝึกหัดชุดจริงของคาบ ({BASE}_ex.json 30 ข้อ)
        # ไม่ใช่ใบงานที่แต่งขึ้นใหม่ — ผลิตแบบฝึกหัดไปแล้วแต่ไม่ได้ใช้ = เสียของ
        last = next((str(x) for x in act if "ขั้นวัดผลการเรียนรู้" in str(x)), "")
        # ตัดหัวบรรทัด "**ขั้นวัดผลการเรียนรู้ (แบบฝึกหัด - X นาที):**" ออกก่อน
        # ไม่งั้นคำว่า "แบบฝึกหัด" ในชื่อขั้นเองจะทำให้ผ่านทั้งที่เนื้อไม่ได้พูดถึงเลย
        body = last.split(":**", 1)[-1] if ":**" in last else last
        if last and not any(h in body for h in PLAN_EXERCISE_HINTS):
            rep.fail("ขั้นวัดผลการเรียนรู้ ต้องระบุว่าให้นักเรียนทำ **แบบฝึกหัดของคาบนี้** "
                     "(ครูเลือกจาก 30 ข้อ เช่น 10 ข้อ) — ไม่ใช่ใบงานที่แต่งขึ้นใหม่")
        stages = [x for x in act if str(x).strip().startswith("**")]
        pool = stages or act
        # นับ "เวลาแรก" ของแต่ละขั้นหลักเท่านั้น — เวลาที่โผล่ถัดไปในบรรทัดเดียวกัน
        # คือเวลาของขั้นย่อย (ซึ่งเป็นส่วนหนึ่งของเวลาขั้นหลักอยู่แล้ว) ถ้าบวกด้วยจะนับซ้ำ
        # และบังคับให้ writer ต้องเลี่ยงการเขียนเวลาขั้นย่อยโดยไม่จำเป็น
        found = [MINUTE_RE.findall(str(x)) for x in pool]
        total = sum(int(m[0]) for m in found if m)
        if not stages:
            rep.warn("ไม่พบบรรทัดขั้นหลัก (ขึ้นต้นด้วย **) — รวมเวลาจากทุกบรรทัดแทน")
        if total != minutes:
            rep.fail("เวลากิจกรรมรวม %d นาที ไม่เท่ากับเวลาคาบ %d นาที (ขั้นหลัก: %s)"
                     % (total, minutes, [MINUTE_RE.findall(str(x)) for x in pool]))
    if ref is not None and cover_of(data) != cover_of(ref):
        rep.fail("cover.rows ไม่ตรงกับ C1 (ต้อง verbatim)")
    rep.note("โครงแผน", "%d หัวข้อ ชื่อและลำดับตรงมาตรฐาน" % len(rows))
    if isinstance(sk, list):
        rep.note("ทักษะ 8C", "ครบ C1-C8 และไม่มีข้อว่าง")
    if minutes and isinstance(act, list):
        rep.note("เวลากิจกรรม", "%d/%d นาที · ครบ 4 ขั้นตามชื่อที่กำหนด" % (total, minutes))
    if ref is not None:
        rep.note("หน้าปกตรง C1", "ตรวจแล้ว verbatim")


# ---------------------------------------------------------------- exercise
def check_exercise(data, rep):
    qs = data.get("questions")
    if not isinstance(qs, list) or not qs:
        rep.fail("ไม่มีคีย์ 'questions' ที่เป็น list")
        return
    n = len(qs)
    diff = Counter(q.get("difficulty") for q in qs)
    if n in QUOTA:
        want = QUOTA[n]
        got = (diff.get("easy", 0), diff.get("medium", 0), diff.get("hard", 0))
        if got != want:
            rep.fail("โควตาความยากของข้อสอบ %d ข้อ ต้องเป็น easy/medium/hard = %s — พบ %s"
                     % (n, "/".join(map(str, want)), "/".join(map(str, got))))
    else:
        if abs(diff.get("easy", 0) - round(n * 0.5)) > 1:
            rep.warn("สัดส่วน easy ควรราว 50%% ของ %d ข้อ — พบ %d" % (n, diff.get("easy", 0)))

    letters = []
    for i, q in enumerate(qs, 1):
        if "answer" in q:
            rep.fail("ข้อ %d มี field 'answer' ที่เลิกใช้แล้ว (เฉลยอยู่ที่ isTrue)" % i)
        ch = q.get("choices") or []
        if len(ch) != 4:
            rep.fail("ข้อ %d มี %d ตัวเลือก (ต้องมี 4)" % (i, len(ch)))
        trues = [j for j, c in enumerate(ch) if c.get("isTrue")]
        if len(trues) != 1:
            rep.fail("ข้อ %d มีเฉลย %d ตัว (ต้องมี 1)" % (i, len(trues)))
        else:
            letters.append("กขคง"[trues[0]] if trues[0] < 4 else "?")
        for c in ch:
            text = str(c.get("content", ""))
            if CHOICE_PREFIX_RE.match(text):
                rep.fail("ข้อ %d ตัวเลือกมี prefix ก./ข./ค./ง. ในเนื้อความ: %r" % (i, text[:30]))
            if "ถูกทุกข้อ" in text or "ไม่มีข้อถูก" in text:
                rep.fail("ข้อ %d มีตัวเลือกต้องห้าม %r" % (i, text[:30]))
        if not q.get("solutionSteps"):
            rep.fail("ข้อ %d ไม่มี solutionSteps" % i)
        for key in ("imageUrl", "audioUrl", "imageAlt", "audioText"):
            if key in q and not isinstance(q[key], str):
                rep.fail("ข้อ %d ฟิลด์ %s ต้องเป็น string (ว่างได้)" % (i, key))

    spread = Counter(letters)
    if letters and max(spread.values()) > len(letters) * 0.4:
        rep.warn("ตำแหน่งเฉลยกระจุก: %s" % dict(spread))
    joined = "".join(letters)
    for size in (4, 5):
        for start in range(0, max(0, len(joined) - size * 2 + 1)):
            block = joined[start:start + size]
            if len(set(block)) == size and joined[start + size:start + size * 2] == block:
                rep.warn("ตำแหน่งเฉลยเป็นรูปแบบวนซ้ำที่ข้อ %d-%d (%s)"
                         % (start + 1, start + size * 2, block))
                break

    n_img = sum(1 for q in qs if str(q.get("imageAlt") or "").strip())
    n_aud = sum(1 for q in qs if str(q.get("audioText") or "").strip())
    rep.note("จำนวนข้อ", n)
    rep.note("โควตาความยาก", "easy %d / medium %d / hard %d" %
             (diff.get("easy", 0), diff.get("medium", 0), diff.get("hard", 0)))
    rep.note("การกระจายเฉลย", " ".join("%s%d" % (k, spread[k]) for k in "กขคง"))
    rep.note("ตัวเลือก", "ทุกข้อมี 4 ตัวเลือกและมีเฉลยเดียว")
    rep.note("prefix ก./ข. ในเนื้อความ", "ไม่มี")
    rep.note('ตัวเลือกต้องห้าม "ถูกทุกข้อ"/"ไม่มีข้อถูก"', "ไม่มี")
    rep.note("solutionSteps", "ครบทุกข้อ")
    rep.note("ช่องสื่อ", "รูป %d ข้อ · เสียง %d ข้อ (ไม่มีโควตา — ไม่ต้องสั่งเพิ่ม)"
             % (n_img, n_aud))


# ---------------------------------------------------------------- song
#: โครงบล็อกที่เนื้อเพลงต้องมี (Master Prompt music)
SONG_BLOCKS = ["[Intro]", "[Verse", "[Chorus]", "[Outro]"]
#: ~80-100 BPM ร้องได้ราว 2.2 พยางค์/วินาที — ใช้ประมาณความยาวเพื่อกันเพลงเกิน 60 วิ
SYLLABLES_PER_SEC = 2.2
SONG_MAX_SEC = 60


def check_song(data, rep):
    """งานนับล้วนของเพลง — ย้ายมาจาก LLM

    ก่อนหน้านี้ song ไม่มีประตูเชิงเครื่องเลย song-checkwork จึงต้องนั่งนับบรรทัด
    นับพยางค์ เช็กอักขระต้องห้ามเอง ทั้งที่เป็นงานที่เครื่องทำได้ในเสี้ยววินาที
    """
    lyrics = data.get("lyrics")
    if not isinstance(lyrics, str) or not lyrics.strip():
        rep.fail("ไม่มีคีย์ 'lyrics' ที่เป็นข้อความ")
        return
    if not str(data.get("style") or "").strip():
        rep.fail("ไม่มีคีย์ 'style' (คำสั่งแนวเพลงสำหรับ Suno)")

    # ★ เจอจริงในไฟล์ที่ผลิตแล้วทั้ง 3 ไฟล์: writer เขียน "/n" (ทับหน้า) แทนการขึ้น
    #   บรรทัดจริง Suno จะได้ตัวอักษร "/n" ไปร้องด้วย และไม่มีใครเห็นจนกว่าจะฟังไฟล์เสียง
    for bad, why in (("/n", 'ทับหน้า+n ("/n")'), ("\\n", "backslash+n ที่ยังไม่ถูกแปลง")):
        if bad in lyrics:
            rep.fail("เนื้อเพลงใช้ %s แทนการขึ้นบรรทัดจริง %d ที่ — "
                     "ต้องเป็นการขึ้นบรรทัดจริงใน JSON" % (why, lyrics.count(bad)))
    for blk in SONG_BLOCKS:
        if blk not in lyrics:
            rep.fail("เนื้อเพลงขาดบล็อก %s" % blk)
    lines = [ln.strip() for ln in lyrics.splitlines() if ln.strip()]
    body = [ln for ln in lines if not ln.startswith("[")]
    if not body:
        rep.fail("มีแต่หัวบล็อก ไม่มีเนื้อร้อง")
        return
    # ตรวจเฉพาะบรรทัดที่ร้องจริง — หัวบล็อกอย่าง [Verse 1] มีเลขได้ เป็นสัญลักษณ์ของ Suno
    sung = "\n".join(body)
    if re.search(r"[0-9]", sung):
        rep.fail("เนื้อร้องมีเลขอารบิก — ต้องเขียนเป็นคำอ่าน (ร้องตามไม่ได้)")
    if "-" in sung:
        rep.fail('เนื้อร้องมีเครื่องหมาย "-" — ห้ามใช้ในเนื้อร้อง')

    # ไทยเขียนเว้นวรรคทีละคำเพื่อให้ร้องตรงจังหวะ -> นับพยางค์จากจำนวนคำ
    words = sum(len(ln.split()) for ln in body)
    est = words / SYLLABLES_PER_SEC
    if est > SONG_MAX_SEC:
        rep.fail("เนื้อเพลงยาวเกิน ~%d วินาที (ประมาณ %.0f วิ จาก %d พยางค์)"
                 % (SONG_MAX_SEC, est, words))
    rep.note("โครงบล็อก", "ครบ %s" % " ".join(SONG_BLOCKS))
    rep.note("จำนวนบรรทัดร้อง", len(body))
    rep.note("ความยาวโดยประมาณ", "%.0f วินาที จาก %d พยางค์ (เพดาน %d)"
             % (est, words, SONG_MAX_SEC))
    rep.note("เลขอารบิก / เครื่องหมาย -", "ไม่มี")


# ---------------------------------------------------------------- video
VIDEO_SCENES = (9, 12)
VIDEO_TOTAL = (150, 180)
VIDEO_SCENE_SEC = (15, 20)
VIDEO_SCENE_KEYS = ("number", "title", "duration_sec", "visual", "vo", "on_screen_text")


def check_video(data, rep):
    """งานนับล้วนของ storyboard — จำนวนฉาก ผลรวมเวลา ช่องครบ"""
    for k in ("header", "lang", "style_guide", "scenes", "total_duration_sec"):
        if k not in data:
            rep.fail("ขาดคีย์ '%s'" % k)
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        rep.fail("ไม่มีคีย์ 'scenes' ที่เป็น list")
        return
    n = len(scenes)
    if not (VIDEO_SCENES[0] <= n <= VIDEO_SCENES[1]):
        rep.fail("จำนวนฉากต้องอยู่ %d-%d — พบ %d" % (*VIDEO_SCENES, n))
    total = 0
    for i, sc in enumerate(scenes, 1):
        for k in VIDEO_SCENE_KEYS:
            if not str(sc.get(k, "")).strip():
                rep.fail("ฉาก %d ขาดช่อง '%s'" % (i, k))
        if sc.get("number") != i:
            rep.fail("ฉากที่ %d มี number = %r (ต้องเรียงต่อเนื่องจาก 1)" % (i, sc.get("number")))
        d = sc.get("duration_sec")
        if not isinstance(d, (int, float)):
            rep.fail("ฉาก %d duration_sec ไม่ใช่ตัวเลข" % i)
            continue
        total += d
        if not (VIDEO_SCENE_SEC[0] <= d <= VIDEO_SCENE_SEC[1]):
            rep.fail("ฉาก %d ยาว %s วิ (ต้องอยู่ %d-%d)" % (i, d, *VIDEO_SCENE_SEC))
    declared = data.get("total_duration_sec")
    if declared != total:
        rep.fail("total_duration_sec = %r แต่ผลรวมของทุกฉาก = %s" % (declared, total))
    if not (VIDEO_TOTAL[0] <= total <= VIDEO_TOTAL[1]):
        rep.fail("เวลารวม %s วิ ต้องอยู่ %d-%d" % (total, *VIDEO_TOTAL))
    rep.note("จำนวนฉาก", "%d (ต้อง %d-%d)" % (n, *VIDEO_SCENES))
    rep.note("เวลารวม", "%s วิ = ผลรวมของทุกฉาก และอยู่ในช่วง %d-%d"
             % (total, *VIDEO_TOTAL))
    rep.note("ช่องของทุกฉาก", "ครบ %s" % " · ".join(VIDEO_SCENE_KEYS))


# ---------------------------------------------------------------- game
GAME_PLAY = {"draw": 10, "default_time_limit_sec": 20, "max_points": 1000}


def check_game(data, rep, ref=None):
    """โครงเกม + **เฉลยต้องตรงกับ {BASE}_ex.json เป๊ะ**

    กฎเทียบเฉลยเคยเป็น heredoc Python ฝังอยู่ใน prompt ของ game-checkwork —
    เท่ากับมีสคริปต์อยู่แล้วแต่ไปวางไว้ในที่ที่รันไม่อัตโนมัติ ย้ายมาเป็นประตูจริง
    """
    if data.get("schema_version") != 2:
        rep.fail("schema_version ต้องเป็น 2 — พบ %r" % data.get("schema_version"))
    for k in ("base", "title", "header"):
        if not str(data.get(k) or "").strip():
            rep.fail("ขาดคีย์ '%s'" % k)
    play = data.get("play") or {}
    for k, want in GAME_PLAY.items():
        if play.get(k) != want:
            rep.fail("play.%s ต้องเป็น %r — พบ %r" % (k, want, play.get(k)))
    qs = data.get("questions")
    if not isinstance(qs, list) or not qs:
        rep.fail("ไม่มีคีย์ 'questions' ที่เป็น list")
        return
    src = (ref or {}).get("questions") if isinstance(ref, dict) else None
    if src is not None and len(src) != len(qs):
        rep.fail("จำนวนข้อ %d ไม่เท่าแบบฝึกหัดต้นทาง %d" % (len(qs), len(src)))
    mismatch = 0
    for i, q in enumerate(qs, 1):
        for k in ("id", "text", "difficulty", "time_limit_sec", "choices", "answer"):
            if k not in q:
                rep.fail("ข้อ %d ขาดคีย์ '%s'" % (i, k))
        ch = q.get("choices") or {}
        keys = list(ch) if isinstance(ch, dict) else []
        if keys != list("กขคง"):
            rep.fail("ข้อ %d ตัวเลือกต้องเป็น ก/ข/ค/ง ตามลำดับ — พบ %r" % (i, keys))
        if q.get("answer") not in ("ก", "ข", "ค", "ง"):
            rep.fail("ข้อ %d answer = %r (ต้องเป็น ก/ข/ค/ง)" % (i, q.get("answer")))
        if src and i <= len(src):
            idx = next((j for j, c in enumerate(src[i - 1].get("choices") or [])
                        if c.get("isTrue")), None)
            want = "กขคง"[idx] if idx is not None and idx < 4 else None
            if want and q.get("answer") != want:
                mismatch += 1
                rep.fail("ข้อ %d เฉลย %r ไม่ตรงแบบฝึกหัดต้นทาง (%r) — writer ห้ามเปลี่ยนเฉลย"
                         % (i, q.get("answer"), want))
    rep.note("โครงเกม", "schema_version=2 · draw=%d · เวลา %d วิ · เต็ม %d คะแนน"
             % (GAME_PLAY["draw"], GAME_PLAY["default_time_limit_sec"],
                GAME_PLAY["max_points"]))
    rep.note("จำนวนข้อ", len(qs))
    if src is not None:
        rep.note("เฉลยเทียบกับแบบฝึกหัดต้นทาง",
                 "ตรงทุกข้อ" if not mismatch else "ไม่ตรง %d ข้อ" % mismatch)


# ---------------------------------------------------------------- slides
def _shown_text(s):
    """ข้อความที่ 'ขึ้นจอ' ของสไลด์หนึ่งหน้า (speaker_note ไม่นับ)"""
    out = [s.get("title", ""), s.get("hook_question", ""), s.get("question", ""),
           s.get("prompt", ""), s.get("answer", ""), s.get("formula", ""),
           s.get("memory_trick", ""), s.get("meta_line", ""), s.get("caption", "")]
    out += s.get("bullets", []) + s.get("items", []) + s.get("explanation", [])
    for card in (s.get("cards") or []) + (s.get("steps") or []) + (s.get("situations") or []):
        out += [card.get("title", ""), card.get("body", ""), card.get("example", "")]
    for row in s.get("table", []):
        out += list(row)
    return [str(x) for x in out if str(x).strip()]


def check_slides(data, rep):
    slides = data.get("slides") or []
    if not slides:
        rep.fail("ไม่มี slides")
        return
    src = data.get("source", "")
    seq = [s.get("section") for s in slides]

    if seq[0] != "cover":
        rep.fail("หน้าแรกต้องเป็น cover — พบ %r" % seq[0])
    pos = {a: [i for i, x in enumerate(seq) if x == a] for a in SLIDE_ANCHORS}
    for a in SLIDE_ANCHORS:
        if not pos[a]:
            rep.fail("ขาดส่วนบังคับ: %s" % a)
    if all(pos[a] for a in SLIDE_ANCHORS):
        order = [pos["objectives"][0], pos["summary"][0], pos["application"][0], pos["vocab"][0]]
        if order != sorted(order):
            rep.fail("ลำดับส่วนบังคับผิด (objectives -> summary -> application -> vocab): %s" % order)
        for i in range(pos["objectives"][0] + 1, pos["summary"][0]):
            if seq[i] not in SLIDE_MIDDLE:
                rep.fail("หน้า %d เป็น %r ซึ่งไม่ควรอยู่ช่วงกิจกรรม" % (i + 1, seq[i]))

    for i, s in enumerate(slides, 1):
        sec = s.get("section")
        if sec == "vocab":
            tb = s.get("table") or []
            if tb and len(tb[0]) != 4:
                rep.fail("หน้า %d ตารางคำศัพท์ต้องมี 4 คอลัมน์ — พบ %d" % (i, len(tb[0])))
            if len(tb) - 1 > 6:
                rep.fail("หน้า %d มีคำศัพท์ %d คำ (สูงสุด 6 ต่อหน้า)" % (i, len(tb) - 1))
        prompt = s.get("image_prompt")
        if prompt:
            if THAI_RE.search(prompt):
                rep.fail("หน้า %d image_prompt มีอักษรไทย (โมเดลสร้างภาพเขียนไทยไม่ได้)" % i)
            if len(prompt) < 200:
                rep.warn("หน้า %d image_prompt สั้นเกินไป (%d ตัวอักษร) — ต้องครบ 6 องค์ประกอบ"
                         % (i, len(prompt)))

        if src in ("L1", "L2"):
            if sec in ("content", "question", "steps", "example") and not s.get("speaker_note"):
                rep.fail("หน้า %d (%s) ไม่มี speaker_note — คำสั่งครูต้องอยู่ตรงนี้" % (i, sec))
            for text in _shown_text(s):
                if TEACHER_RE.search(text):
                    rep.fail("หน้า %d มีคำสั่งครูขึ้นจอ: %r" % (i, text[:50]))
                for w in PLAN_WORDS:
                    if w in text:
                        rep.fail("หน้า %d มีศัพท์ของแผนขึ้นจอ (%s): %r" % (i, w, text[:50]))


# ---------------------------------------------------------------- agents
def check_agents(rep):
    try:
        import yaml
    except ImportError:
        rep.warn("ไม่มี pyyaml — ข้ามการตรวจ frontmatter")
        return
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "agents")
    files = sorted(glob.glob(os.path.join(root, "*.md")))
    if not files:
        rep.warn("ไม่พบไฟล์ agent")
        return
    for p in files:
        name = os.path.basename(p)
        with open(p, encoding="utf-8") as f:
            parts = f.read().split("---")
        if len(parts) < 3:
            rep.fail("%s ไม่มี frontmatter" % name)
            continue
        try:
            fm = yaml.safe_load(parts[1])
        except Exception as exc:
            rep.fail("%s frontmatter parse ไม่ได้ (%s) — มักเกิดจากมี ': ' ในสตริงที่ไม่ได้ครอบ "
                     "quote ให้ใช้ block scalar `>-`" % (name, str(exc).splitlines()[0]))
            continue
        if not isinstance(fm, dict):
            rep.fail("%s frontmatter ไม่ใช่ mapping" % name)
            continue
        for key in ("name", "description", "model"):
            if not fm.get(key):
                rep.fail("%s ขาด frontmatter '%s'" % (name, key))
        if fm.get("name") and fm["name"] != name[:-3]:
            rep.fail("%s ชื่อใน frontmatter (%r) ไม่ตรงชื่อไฟล์" % (name, fm["name"]))
        # นโยบายโมเดล (CLAUDE.md ข้อ 8) — ห้ามเปลี่ยนจนกว่าเจ้าของ repo จะแจ้ง
        # เดิม lint แค่ว่ามีคีย์ model ทำให้เปลี่ยนเป็นรุ่นอื่นได้โดยไม่มีอะไรทัก
        if fm.get("model") and fm["model"] != REQUIRED_MODEL:
            rep.fail("%s ใช้ model: %r — นโยบายกำหนดให้ทุก agent เป็น %r "
                     "(CLAUDE.md ข้อ 8 · เปลี่ยนได้เมื่อเจ้าของ repo แจ้งเท่านั้น)"
                     % (name, fm["model"], REQUIRED_MODEL))
    print("ตรวจ frontmatter ของ agent %d ไฟล์" % len(files))


# ---------------------------------------------------------------- main
def write_gate_card(path, kind, json_file, rep, rc):
    """เขียนบัตร "เครื่องตรวจอะไรไปแล้ว" ให้ checkwork อ่านก่อนลงมือ

    เหตุผลที่ต้องเป็นไฟล์ ไม่ใช่ข้อความใน prompt: ถ้าเขียนใน prompt แม่ต้องนึกเอง
    ทุกครั้งและพิมพ์ซ้ำในทุก prompt ของลูก (รอบก่อนพิมพ์ชุดเดียวกันซ้ำ 11 ที่)
    เป็นไฟล์แล้วเขียนครั้งเดียว ส่ง path อ่านกี่ตัวก็ได้ และตัวเลขไม่มีทางพิมพ์ผิด
    """
    L = ["# ผลตรวจของเครื่อง — %s" % os.path.basename(json_file), "",
         "> `validate_spec.py %s` รันแล้ว **ผลด้านล่างนี้ไม่ต้องตรวจซ้ำ**" % kind,
         "> เอาแรงไปตรวจสิ่งที่เครื่องตรวจไม่ได้: ความถูกต้องของเนื้อหา · ความสอดคล้อง"
         "ภายใน · ความเหมาะกับระดับชั้น · คุณภาพเชิงการสอน", "",
         "**สรุป: %s**" % ("ผ่านทุก check" if rc == 0 else
                           "ไม่ผ่าน %d ข้อ (ดูรายการท้ายไฟล์)" % len(rep.problems)), ""]
    if rep.notes:
        L += ["## เครื่องวัดไปแล้ว", "", "| สิ่งที่ตรวจ | ค่าที่วัดได้ |", "|---|---|"]
        L += ["| %s | %s |" % (k, v) for k, v in rep.notes]
        L.append("")
    if rep.warns:
        L += ["## เตือน (ไม่ถึงกับผิด)", ""] + ["- %s" % w for w in rep.warns] + [""]
    if rep.problems:
        L += ["## ยังไม่ผ่าน — ต้องแก้ก่อน", ""]
        L += ["%d. %s" % (i, p) for i, p in enumerate(rep.problems, 1)]
        L.append("")
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L))


def main():
    ap = argparse.ArgumentParser(description="ตรวจ artifact JSON ให้ตรงสเปกก่อนส่ง checkwork")
    ap.add_argument("kind", nargs="?", choices=["content", "lesson_plan", "exercise",
                                                "slides", "song", "video", "game"])
    ap.add_argument("json_file", nargs="?")
    ap.add_argument("--ref", help="ไฟล์อ้างอิง — หน้าปก (C1.json) หรือแบบฝึกหัดต้นทางของ game")
    ap.add_argument("--minutes", type=int, help="เวลาคาบ (period_minutes) สำหรับ lesson_plan")
    ap.add_argument("--peer", metavar="PATH",
                    help="แผนคู่ของมัน (L1 ใส่ L2 / L2 ใส่ L1) — ตรวจว่าเป็นคนละกิจกรรมจริง")
    ap.add_argument("--agents", action="store_true", help="ตรวจ frontmatter ของ .claude/agents/*.md")
    ap.add_argument("--strict", action="store_true", help="นับ WARN เป็นปัญหาด้วย")
    ap.add_argument("--report", metavar="PATH",
                    help="เขียนบัตร 'เครื่องตรวจอะไรไปแล้ว' (ปกติคือ {BASE}_gate.md) "
                         "เพื่อส่ง path ให้ checkwork อ่าน จะได้ไม่นับซ้ำ")
    a = ap.parse_args()

    rep = Report()
    if a.agents:
        check_agents(rep)
        return rep.done("frontmatter ของ agent", a.strict)

    if not a.kind or not a.json_file:
        ap.print_help()
        return 2
    if not os.path.exists(a.json_file):
        print("ไม่พบไฟล์: %s" % a.json_file, file=sys.stderr)
        return 2

    data = load(a.json_file)
    ref = load(a.ref) if a.ref and os.path.exists(a.ref) else None
    common_checks(data, rep)
    run_check_math(a.json_file, rep)
    if a.kind == "content":
        check_content(data, rep, ref)
    elif a.kind == "lesson_plan":
        check_lesson_plan(data, rep, ref, a.minutes)
        if a.peer and os.path.exists(a.peer):
            check_plan_pair(data, load(a.peer), rep)
        elif a.peer:
            rep.warn("ไม่พบไฟล์แผนคู่: %s — ข้ามการตรวจว่า L1/L2 ต่างกันจริง" % a.peer)
    elif a.kind == "exercise":
        check_exercise(data, rep)
    elif a.kind == "song":
        check_song(data, rep)
    elif a.kind == "video":
        check_video(data, rep)
    elif a.kind == "game":
        check_game(data, rep, ref)
    else:
        check_slides(data, rep)
    rc = rep.done("%s (%s)" % (a.kind, os.path.basename(a.json_file)), a.strict)
    if a.report:
        write_gate_card(a.report, a.kind, a.json_file, rep, rc)
        print("บัตรผลตรวจของเครื่อง -> %s" % a.report)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
