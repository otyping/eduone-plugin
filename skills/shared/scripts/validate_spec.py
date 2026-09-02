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
  validate_spec.py lesson_plan <json> [--ref <C1.json>] [--minutes 50]
  validate_spec.py exercise    <json>
  validate_spec.py slides      <json>
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
PLAN_8C_IDX = 2
PLAN_ACT_IDX = 3
PLAN_RUBRIC_IDX = 6
SKILLS_8C_CODES = ["C%d" % i for i in range(1, 9)]
ACT_STAGES = ["ขั้นนำ", "ขั้นสอน", "ขั้นสรุป", "ขั้นวัดผลการเรียนรู้"]
TEACHER_RE = re.compile(r"(^|[\s\"'(])ครู|ให้นักเรียน")

# ป้ายชื่อ 7 แถวของตารางหน้าปก (C1 C2 L1 L2 ใช้ชุดเดียวกัน ต้องตรงกันตัวต่อตัว)
# ★ ชื่อสองแถวท้ายตรงกับชื่อคอลัมน์ในโครงสร้างหลักสูตรของ สสวท. พอดี
#   แถว "จุดประสงค์ประจำหน่วย" = คอลัมน์ E (OBJ ระดับหน่วย)
#   แถว "สาระสำคัญ / จุดประสงค์ประจำคาบ" = คอลัมน์ I (COMP ระดับคาบ)
#   เดิมสองแถวนี้ชื่อ "...ระดับหน่วยการเรียน" ทั้งคู่ และแถวท้ายใส่ COMP ระดับหน่วย
#   ซึ่งไม่มีอยู่ในหลักสูตร — เปิดหลักสูตรเทียบหน้าปกแล้วหาที่มาไม่เจอ
COVER_LABELS = ["รหัสวิชา", "วิชา", "หน่วย", "ตัวชี้วัด", "เรื่อง",
                "จุดประสงค์ประจำหน่วย", "สาระสำคัญ / จุดประสงค์ประจำคาบ"]

SLIDE_ANCHORS = ["cover", "objectives", "summary", "application", "vocab"]
SLIDE_MIDDLE = {"content", "question", "example", "formula", "steps",
                "compare", "triple", "lesson_info"}


class Report:
    def __init__(self):
        self.problems: list[str] = []
        self.warns: list[str] = []

    def fail(self, msg):
        self.problems.append(msg)

    def warn(self, msg):
        self.warns.append(msg)

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
    check_digest(data, rep)


# ---------------------------------------------------------------- lesson_plan
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
    if len(rows) > PLAN_RUBRIC_IDX and not isinstance(rows[PLAN_RUBRIC_IDX][1], dict):
        rep.fail("แถว %d (Rubric) ต้องเป็น dict {template, topic, skill}" % (PLAN_RUBRIC_IDX + 1))
    for i, r in enumerate(rows, 1):
        if len(r) != 2 or not isinstance(r[1], (str, list, dict)):
            rep.fail("plan.rows แถวที่ %d ต้องเป็น [หัวข้อ, str|list|dict]" % i)

    # ทักษะ 8C ต้องครบทั้ง 8 ข้อ และมีเนื้อจริง
    sk = rows[PLAN_8C_IDX][1] if len(rows) > PLAN_8C_IDX else None
    if isinstance(sk, list):
        for code in SKILLS_8C_CODES:
            if not any(str(x).lstrip("*").strip().startswith(code) for x in sk):
                rep.fail("หัวข้อ 3 ทักษะ 8C ขาด %s" % code)
        for x in sk:
            body = str(x).split(":", 1)[-1].replace("*", "").strip()
            if len(body) < 10:
                rep.fail("หัวข้อ 3 ทักษะ 8C มีข้อที่เว้นว่าง/สั้นเกินไป: %r" % str(x)[:40])
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
    print("ตรวจ frontmatter ของ agent %d ไฟล์" % len(files))


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="ตรวจ artifact JSON ให้ตรงสเปกก่อนส่ง checkwork")
    ap.add_argument("kind", nargs="?", choices=["content", "lesson_plan", "exercise", "slides"])
    ap.add_argument("json_file", nargs="?")
    ap.add_argument("--ref", help="ไฟล์อ้างอิงหน้าปก (ปกติคือ C1.json)")
    ap.add_argument("--minutes", type=int, help="เวลาคาบ (period_minutes) สำหรับ lesson_plan")
    ap.add_argument("--agents", action="store_true", help="ตรวจ frontmatter ของ .claude/agents/*.md")
    ap.add_argument("--strict", action="store_true", help="นับ WARN เป็นปัญหาด้วย")
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
    elif a.kind == "exercise":
        check_exercise(data, rep)
    else:
        check_slides(data, rep)
    return rep.done("%s (%s)" % (a.kind, os.path.basename(a.json_file)), a.strict)


if __name__ == "__main__":
    raise SystemExit(main())
