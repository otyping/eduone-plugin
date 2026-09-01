---
name: content
description: >-
  Orchestrator ของ Agent 1 (Content) — ผลิตเอกสารประกอบเนื้อหา 2 แบบจากหัวข้อเดียว:
  C1 เชิงวิชาการ + C2 เล่าเรื่อง (.docx, 3–5 หน้า). ใช้เมื่อผู้ใช้สั่งทำนองว่า
  "ทำ content / เนื้อหา <ระดับชั้น> <วิชา> no.X" เช่น "ทำเนื้อหา ป.1 วิทย์ no.1".
  ต้องระบุ ระดับชั้น + วิชา + No. — ถ้าไม่ครบให้ถามก่อน ห้ามเดา. Skill นี้ทำหน้าที่
  lookup metadata, เตรียมหน้าปก, เรียก content-academic เขียน C1 ก่อนตัวเดียว,
  ตรวจ C1 ด้วย content-checkwork ให้ผ่าน (★ ประตูของทั้ง pipeline) แล้วจึงเรียก
  content-narrative เขียน C2 จาก C1 ฉบับที่ผ่านแล้ว (prepend persona/canon ถ้ามี),
  ตรวจ C2 + ความสอดคล้อง C1↔C2, build เป็น .docx, verify, เก็บ JSON spec และรายงาน token.
  **ผลิตครบทั้ง C1 และ C2 ทุกครั้ง** — C2 เป็นไฟล์ส่งงานเช่นกัน ห้ามข้าม.
---

# Skill: content — ผลิตเอกสารประกอบเนื้อหา C1 + C2

## เมื่อไรใช้
ใช้เมื่อผู้ใช้สั่งทำ "content / เนื้อหา" ของหัวข้อใดหัวข้อหนึ่ง เช่น
`ทำ content ป.1 วิทย์ no.1` หรือ `เนื้อหา ม.2 คณิต no.5`

**ต้องระบุครบ 3 อย่าง:** ระดับชั้น (grade) + วิชา (subject) + No.
ถ้าผู้ใช้ระบุไม่ครบ → **ถามก่อน ห้ามเดา**

ผลผลิต 2 ไฟล์จาก **หัวข้อเดียวกัน**:
- **C1 — แบบที่ 1 เชิงวิชาการ** (`{BASE}_C1.docx`)
- **C2 — แบบที่ 2 เล่าเรื่อง** (`{BASE}_C2.docx`)
ทั้งคู่ครอบคลุมความรู้เท่ากัน ตอบ OBJ/COMP เดียวกัน ยาว **3–5 หน้า A4** (ไม่นับหน้าปก)

## ก่อนเริ่ม — แปลงเป็น slug
- `grade_slug`: `ป.1..ป.6` → `p1..p6`, `ม.1..ม.6` → `m1..m6`
- `subject_slug`: ไทย=`thai` คณิต=`math` วิทย์=`sci` สังคม=`social` สุขศึกษา=`health` ศิลปะ=`art` การงาน=`career` อังกฤษ=`english` (ดู `${CLAUDE_PLUGIN_ROOT}/skills/shared/reference/subjects.txt`)

ถ้าไม่พบ `course-structure-<grade_slug>-<subject_slug>.md` ใน `${CLAUDE_PLUGIN_ROOT}/skills/shared/reference/`
→ **STOP** แจ้งผู้ใช้ให้วางไฟล์โครงสร้างหลักสูตรก่อน (ดู fixture `course-structure-p1-sci.md` เป็นรูปแบบ)

## ขั้นตอน orchestration

> ทุกคำสั่ง Python รันผ่าน Bash tool พร้อม `export PYTHONIOENCODING=utf-8`
> และใช้ Python 3.12 เต็ม path เสมอ (ห้ามเรียก `python` เปล่า)

### (a) Lookup metadata + BASE
```bash
eduone-py no_to_token.py <grade_slug> <subject_slug> <No>
```
ได้ JSON: `grade, grade_slug, subject, subject_slug, subject_code, period_minutes,
lang, no, unit, unit_name, order, topic_name, obj[], comp[], base, header`
- `base` = BASE token (Title-case) เช่น `P1-Sci_U1_1` (GradeToken=grade_slug.upper(), SubjectToken=subject_slug.capitalize())
- ยังได้ `grade_token`, `subject_token`, `unit_folder`, `topic_dir` กลับมาด้วย
- **`prereq[]`** = หัวข้อที่ต้องรู้มาก่อน (จาก `PREREQ|` ใน course-structure) — ดูขั้น (a1)

### (a1) หัวข้อต่อยอด — เตรียม path ของ prereq (ข้ามได้ถ้า `prereq[]` ว่าง)
`paths.py` เติม `srcpack_md` / `c1_json` / `ready` / `has_c1` ให้ทุกตัวใน `prereq[]`

| สถานะ | ทำอย่างไร |
|---|---|
| `ready: true` | ส่ง **path ของ `srcpack_md`** ต่อให้ writer — จบ |
| `ready: false` แต่ `has_c1: true` | สร้าง srcpack ก่อน แล้วค่อยส่ง path:<br>`srcpack.py "<c1_json>" "<srcpack_md>"` |
| ทั้งคู่ false | หัวข้อนั้นยังไม่ได้ผลิต → **ข้ามไป ไม่ใช่ error** แต่ **ต้องแจ้งในรายงาน**<br>ว่าเขียนหัวข้อนี้โดยไม่มีฐานจากหัวข้อก่อนหน้า |

- **ส่ง path ไม่ส่งเนื้อหา** (กฎทองใน CLAUDE.md) — srcpack ตัวละ ~2.5k token
  ถ้า orchestrator อ่านเองจะค้างใน context ตลอด pipeline
- ความต่อเนื่องอยู่ใน **ไฟล์** ไม่ใช่ในประวัติแชท → `/clear` ระหว่างหัวข้อไม่ทำให้เสียอะไร
- `header` = `"ระดับชั้น... > วิชา... > หน่วย... > เรื่อง..."` (ใส่ลง field `header` ของทั้ง C1/C2)

**ดึง path ที่แน่นอนด้วย `paths.py`** (อย่าประกอบ path เอง):
```bash
eduone-py paths.py <grade_slug> <subject_slug> <No>
```
ได้ JSON keys ที่ใช้ใน skill นี้: `content_c1_json`, `content_c1_docx`, `content_c2_json`, `content_c2_docx`, `topic_dir`, `dirs{...}`
ทุกไฟล์อยู่ใต้ต้นไม้เดียว:
```
Output/<GradeToken>/<SubjectToken>/<GradeToken>-<SubjectToken>_U<unit>/<BASE>/1. Content/
   {BASE}_C1.json + _C1.docx · {BASE}_C2.json + _C2.docx   (spec co-located กับ render)
```
git track เฉพาะ `.json`; `.docx` gitignored (rebuild ได้)

### (a2) ค้นคว้าแหล่งอ้างอิงก่อนเขียน — sub-agent `content-research`
เรียก **`content-research`** ส่ง metadata + path ปลายทาง `content_research_md`
(จาก `paths.py` = `1. Content/{BASE}_research.md`)

agent จะเปิด **BookScan ก่อนเสมอ** → ไม่พอค่อยค้นเน็ต → คืน fact pack ที่ **ทุกข้อมีที่มากำกับ**
- **ห้าม orchestrator เปิดหน้า BookScan เป็นภาพเอง** — ภาพสแกนจะค้างใน context ตลอดทั้ง pipeline
  ทำให้ทุกขั้นหลังจากนั้นแพงขึ้น ปล่อยให้ sub-agent อ่านแล้วคืนข้อความสรุปมา
- agent จะรายงานว่า **OBJ/COMP ข้อไหนยังไม่มีแหล่งรองรับ** — ส่งต่อให้ writer รู้ด้วย
- ไม่มีเล่มในคลังและค้นเน็ตไม่ได้ผล → ยังเขียน C1 ต่อได้ แต่ **บันทึกในรายงานว่าเขียนจากความรู้ทั่วไป**

### (b) เตรียม cover.rows (6 แถว) จาก metadata
ใช้กับทั้ง C1 และ C2 (เหมือนกัน):
```
["รหัสวิชา", subject_code]
["วิชา", subject]
["หน่วย", unit_name]
["เรื่อง", topic_name]
["จุดประสงค์ประจำหน่วยการเรียน", obj[]]            # = obj จาก metadata
["ผลลัพธ์การเรียนรู้ระดับหน่วยการเรียน", comp[]]    # = comp จาก metadata
```
- `cover.title` = `"เอกสารประกอบเนื้อหา"`
- `cover.grade_line` = `"ระดับชั้น" + grade` (เช่น `"ระดับชั้นประถมศึกษาปีที่ 1"`)
- **ถ้า `obj[]` หรือ `comp[]` ว่าง** → สั่งให้ writer ร่าง OBJ/COMP เองจากหัวข้อ + ระดับชั้น
  (3–4 ข้อ เชิงพฤติกรรมวัดได้) แล้วใส่กลับใน cover.rows; C1 กับ C2 ต้องใช้ชุดเดียวกัน

### (c) ขั้นที่ 1 — เขียน **C1 ก่อนตัวเดียว**
เรียก sub-agent **`content-academic`** → เขียน `{BASE}_C1.json` (`mode_label: "แบบที่ 1 - เชิงวิชาการ"`)

> **ห้ามเรียก `content-narrative` ในขั้นนี้.** C1 เป็นแกนของทั้งระบบ — C2, L1/L2, ข้อสอบ,
> เพลง, วิดีโอ และสไลด์ทุกชุด derive จาก C1 ทั้งหมด ถ้าปล่อยให้เขียนขนานกันตั้งแต่ C1
> ยังไม่ผ่าน พอ C1 ถูกแก้ ต้องรื้องานที่ derive ไปแล้วถึง 8 ชิ้น —
> **ตรวจ C1 ให้จบก่อนค่อยแตกแขนง ทั้งถูกกว่าและเร็วกว่า**

ส่งให้ writer: header, cover ที่เตรียมไว้, metadata เต็ม (โดยเฉพาะ obj/comp, topic_name,
unit_name, grade เพื่อปรับระดับภาษา), path ไฟล์โครงสร้างหลักสูตร,
**path ของ `content_research_md` จากขั้น (a2)** (ถ้ามี — พร้อมย้ำว่าให้ยึดเป็นแหล่งหลัก),
**path ของ `srcpack_md` ทุกตัวใน `prereq[]` จากขั้น (a1)** (ถ้ามี — พร้อมชื่อหัวข้อกำกับ
เช่น "No.2 การบวกจำนวนเต็ม → <path>"),
และ path ที่ให้เขียน JSON
(ใช้ `content_c1_json` / `content_c2_json` จาก `paths.py` — อยู่ใน `1. Content/` co-located กับ render)

**Persona/canon (lazy — optional สำหรับ สพฐ.):**
ก่อนเรียก writer ถ้ามีไฟล์เหล่านี้ให้ prepend เนื้อความเข้าไปใน prompt ของ writer:
- `${CLAUDE_PLUGIN_ROOT}/skills/content/personas/<subject_slug>/<subject_code>-academic.md` (ให้ C1)
- `${CLAUDE_PLUGIN_ROOT}/skills/content/personas/<subject_slug>/<subject_code>-narrative.md` (ให้ C2)
- `${CLAUDE_PLUGIN_ROOT}/skills/content/personas/<subject_slug>/<subject_code>-canon.md` (ให้ทั้งคู่ — ศัพท์/ข้อตกลงร่วม)

ถ้าไม่มี persona → **ไม่ต้องสร้าง** เพียงบันทึกหมายเหตุว่า "persona ไม่มี — ร่างจากความรู้ทั่วไปตามระดับชั้น"
แล้วให้ writer ใช้ความรู้พื้นฐานวิชานั้น ปรับความลึกตามระดับชั้น (ประถม=ง่าย, มัธยม=ลึกขึ้น)

### (c2) Gate อัตโนมัติของ C1 (บังคับ)
```bash
export PYTHONIOENCODING=utf-8
eduone-py validate_spec.py content "<content_c1_json>"
```
ตรวจ: หน้าปก 6 แถวเรียงถูก · `mode_label` · ชนิด block · ตารางคอลัมน์เท่ากัน ·
สัญลักษณ์คณิต (เรียก `check_math` ให้ในตัว) · ไม่มี emoji/ZWSP ค้าง
**exit ≠ 0 → ส่งรายการกลับให้ `content-academic` แก้ก่อน ยังไม่ต้องเรียก checkwork**
(C2 มี gate ของตัวเองที่ขั้น (d3) ซึ่งเทียบหน้าปกกับ C1 ด้วย `--ref`)

> **ทำไมต้องมีขั้นนี้**: กฎเชิงตัวเลข/โครงสร้างเครื่องตรวจได้ในเสี้ยววินาที การปล่อยให้
> checkwork (LLM) ตรวจแทนทำให้เสียรอบแก้ไปกับเรื่องที่ไม่ต้องใช้วิจารณญาณ —
> **checkwork มีไว้ตรวจความถูกต้องของเนื้อหา ความสอดคล้องภายใน และคุณภาพเชิงการสอน**

### (d) ★ ประตูของทั้งระบบ — ตรวจ C1 ด้วย content-checkwork (loop ≤ 2 รอบ)
เรียก sub-agent **`content-checkwork`** ส่ง **เฉพาะ `content_c1_json`** + metadata
และระบุในคำสั่งให้ชัดว่า **"ตรวจ C1 อย่างเดียว ยังไม่มี C2"** (agent รองรับโหมดไฟล์เดียว)
- `CHECKWORK: ALL-PASS` → **ปลดล็อก** ไปขั้น (d2) และแจ้ง orchestrator ว่า C1 พร้อมให้ผลผลิตอื่น derive
- `CHECKWORK: FAIL (...)` → ส่งรายการแก้กลับ `content-academic` แล้วตรวจซ้ำ (≤ 2 รอบ)
- ครบ 2 รอบยังไม่ผ่าน → **หยุด ห้ามปล่อย C2 หรือผลผลิตอื่น** รายงานให้ผู้ใช้ตัดสินใจ

### (d1) สร้าง source pack ทันทีที่ C1 ผ่าน (สคริปต์ ไม่ใช้โมเดล)
```bash
eduone-py srcpack.py "<content_c1_json>" "<content_srcpack_md>"
```
ย่อ C1 เหลือ ~20% จาก `digest` ที่ `content-academic` เขียนไว้ (ไม่ต้องเรียกโมเดลใหม่)
→ **แผนการสอน · เพลง · วิดีโอ อ่านไฟล์นี้แทน C1 เต็ม** และทุกสื่อยึดศัพท์/ตัวเลขชุดเดียวกัน
- ถ้าขึ้น `WARN: C1 ไม่มี digest` (artifact เก่า) → ยังใช้ได้ แต่ pack จะมีแค่หน้าปก+โครงหัวข้อ
  ให้แจ้ง agent ปลายน้ำว่าต้องอ่าน C1 เต็มแทน

### (d2) ขั้นที่ 2 — เขียน C2 จาก C1 ฉบับที่ผ่านแล้ว
เรียก sub-agent **`content-narrative`** → `{BASE}_C2.json` (`mode_label: "แบบที่ 2 - เล่าเรื่อง"`)
ส่งเพิ่มจากที่ระบุในขั้น (c): **path ของ `content_c1_json` ที่ผ่าน checkwork แล้ว** พร้อมสั่งว่า
_"ใช้ศัพท์เทคนิค/ตัวเลข/ตัวอย่างหลักชุดเดียวกับ C1 · ความรู้ต้องครบเท่า C1 · cover เหมือน C1 ทุกตัวอักษร"_

> **C2 ไม่ได้ถูกลดความสำคัญ** — ยังผลิตครบทุกครั้ง เป็นไฟล์ส่งงานเช่นเดียวกับ C1
> การทำทีหลังทำให้ C2 **ลอกศัพท์/ตัวเลขจากเนื้อหาที่ผ่านการตรวจแล้วจริง ๆ** แทนที่จะเดา
> ให้ตรงกันเอง → ความสอดคล้อง C1↔C2 ดีขึ้น ไม่ใช่แย่ลง

### (d3) Gate + ตรวจ C2 (loop ≤ 2 รอบ)
```bash
eduone-py validate_spec.py content "<content_c2_json>" --ref "<content_c1_json>"
```
`--ref` บังคับให้หน้าปกของ C2 ตรงกับ C1 ทุกตัวอักษร — **exit ≠ 0 → ให้ `content-narrative` แก้ก่อน**

แล้วเรียก **`content-checkwork`** อีกครั้ง ส่ง **ทั้ง C1 + C2** เพื่อตรวจ **สไตล์ของ C2
และความสอดคล้อง C1↔C2** (ระบุให้ชัดว่า C1 ผ่านแล้ว ไม่ต้องรื้อตรวจเนื้อหา C1 ซ้ำ)
- FAIL → แก้ที่ **C2 เท่านั้น**
- ถ้า checkwork ชี้ว่า **C1 ผิดจริง** → แก้ C1 ได้ แต่ต้อง **แจ้ง orchestrator ทันที**
  เพราะผลผลิตที่ derive จาก C1 ไปแล้ว (L1/L2, ข้อสอบ, เพลง, วิดีโอ, สไลด์) อาจต้องรื้อตาม

### (e) Build เป็น .docx
ใช้ path ที่ได้จาก `paths.py` (`content_c1_json`/`content_c1_docx` และ C2). โฟลเดอร์ปลายทางถูกสร้างโดย `paths.py`/`ensure_dirs(topic_paths(meta))` แล้ว — build/verify script รับ `<json> <out>` ตรง ๆ (signature ไม่เปลี่ยน).
```bash
export PYTHONIOENCODING=utf-8
eduone-py build_content.py "<content_c1_json>" "<content_c1_docx>"
eduone-py build_content.py "<content_c2_json>" "<content_c2_docx>"
```
(ทั้ง `_C1.json/_C1.docx` และ `_C2.json/_C2.docx` อยู่ใน `1. Content/` โฟลเดอร์เดียวกัน — spec co-located กับ render)

### (f) Verify (tester)
```bash
eduone-py verify_docx.py content "<content_c1_json>" "<content_c1_docx>"
# ทำซ้ำกับ _C2: "<content_c2_json>" "<content_c2_docx>"
```
ตรวจ A4 / ฟอนต์ / header / footer / page-break + นับหน้า (3–5) ถ้ามี `pywin32`
ถ้าไม่มี pywin32 → จะ **WARN** ข้ามการนับหน้า ต้องตรวจความยาวเองคร่าว ๆ จากปริมาณ body
- exit 0 = ผ่าน; exit 1 = ไม่ผ่าน → ดู error, แก้ JSON, build+verify ใหม่

### (g) เก็บ JSON spec (source of truth — track git)
JSON อยู่ co-located กับ render ใน `1. Content/` (path จาก `paths.py`):
```
<content_c1_json>   # …/<BASE>/1. Content/{BASE}_C1.json
<content_c2_json>   # …/<BASE>/1. Content/{BASE}_C2.json
```
git track เฉพาะ `.json`; `.docx` (`content_c1_docx`/`content_c2_docx` ในโฟลเดอร์เดียวกัน) = gitignored, rebuild ได้

### (h) รายงาน token
ดึงเลขจริงจาก `<usage>` ของแต่ละ sub-agent (academic / narrative / checkwork)
รายงานเป็นตาราง: แถวต่อ sub-agent (input/output/total) + แถวรวม

## กฎรูปแบบเอกสาร (อ้าง CLAUDE.md ข้อ 4–5)
- **ความยาว 3–5 หน้า A4 จริง** ไม่นับหน้าปก
- ฟอนต์ **TH Sarabun New 14pt สีดำ**; เนื้อหา alignment **thaiDistribute**
- **หน้าปก** (หน้า 1): หัวเรื่อง 18pt + บรรทัดระดับชั้น 18pt + ตาราง **6 แถว** แล้ว page break
- หน้า 2+: `mode_label` + `title` (18pt กึ่งกลาง) แล้ว body blocks (14pt)
- body block types: `h` (หัวข้อหนา) · `p` (ย่อหน้า) · `table` · `eq` (สมการกึ่งกลาง) · `ep` (บรรทัดว่าง)
  inline ในข้อความ: `**ตัวหนา**` · `^{ยกกำลัง}` · `_{ตัวห้อย}` · `\alias` (เช่น `\Omega`) · สมการ `$...$`
