---
name: lesson-plan
description: สร้างแผนการจัดการเรียนรู้ระดับ สพฐ. 2 รูปแบบ (เชิงสำรวจ Inquiry / ผ่านกิจกรรม Activity) จากไฟล์เนื้อหา C1 ของหน่วยนั้น ออกเป็น .docx 2 ไฟล์ (_L1, _L2) พร้อมหน้าปก จุดประสงค์ K/P/A กิจกรรมตามเวลาคาบ และ Rubric. เรียกใช้เมื่อผู้ใช้พิมพ์ "ทำ lesson plan / ทำแผน <ชั้น> <วิชา> no.X".
---

# Skill: lesson-plan — แผนการจัดการเรียนรู้ (สพฐ.)

orchestrator ของ pipeline แผนการสอน. สร้างแผน 2 รูปแบบจากเนื้อหาวิชาการ (ไฟล์ C1) ของ agent content.

## Trigger
ผู้ใช้พิมพ์ทำนอง "ทำ lesson plan / ทำแผน <ชั้น> <วิชา> no.X" เช่น "ทำแผน ป.1 วิทย์ no.1".

## INPUT ที่ต้องมี
- `gradeSlug` (p1..p6, m1..m6)
- `subjectSlug` (thai/math/sci/social/health/art/career/english)
- `No` (เลขลำดับเนื้อหาในรายวิชา เริ่มที่ 1 ต่อ grade×subject)

**ถ้าผู้ใช้ไม่ระบุ ครบ → ถามก่อน** อย่าเดา. ดูโครงสร้างหลักสูตรได้ที่
`${CLAUDE_PLUGIN_ROOT}/skills/shared/reference/course-structure-<gradeSlug>-<subjectSlug>.md`

## ขั้นตอน orchestration

### 1) Lookup metadata
```bash
eduone-py no_to_token.py <gradeSlug> <subjectSlug> <No>
```
ได้ JSON: `{grade, grade_slug, subject, subject_slug, subject_code, period_minutes, lang, no, unit, unit_name, order, topic_name, obj[], comp[], base, header, grade_token, subject_token, unit_folder, topic_dir}`.
จด `BASE` (Title-case เช่น `P1-Sci_U1_1`) และ `period_minutes` (เช่น 50 นาที ประถม) — **ใช้เวลานี้แบ่งกิจกรรม ไม่ fix 60**.

**ดึง path ที่แน่นอนด้วย `paths.py`** (อย่าประกอบ path เอง):
```bash
eduone-py paths.py <gradeSlug> <subjectSlug> <No>
```
ได้ keys ที่ใช้ใน skill นี้: **`content_srcpack_md`** (source ที่อ่านก่อน), `content_c1_json`, `content_c1_docx` (C1 ฉบับเต็ม เปิดเมื่อ pack ไม่พอ), `plan_l1_json`, `plan_l1_docx`, `plan_l2_json`, `plan_l2_docx`, `topic_dir`.
ทุกไฟล์อยู่ใต้ `Output/<GradeToken>/<SubjectToken>/<GradeToken>-<SubjectToken>_U<unit>/<BASE>/2. LessonPlan/` (L1/L2 json+docx co-located). git track เฉพาะ `.json`.

### 2) เตรียมไฟล์ต้นทาง — **★ orchestrator ห้ามอ่านเนื้อหา ส่ง path อย่างเดียว**

ขั้นนี้ทำแค่ **ตรวจว่ามีไฟล์** ด้วย `ls`/`Test-Path` เท่านั้น

```bash
ls -l "<content_srcpack_md>" "<content_c1_json>"
```
- ยังไม่มี srcpack → สร้างก่อน `eduone-py srcpack.py "<content_c1_json>" "<content_srcpack_md>"`
- ยังไม่มีบัตรขอบเขตคาบ → `eduone-py scope_card.py <gradeSlug> <subjectSlug> <No> --apply`

> **ทำไมห้ามอ่านเอง**: srcpack ~2.1k โทเคน · C1 เต็ม ~8.1k โทเคน ถ้าแม่ `Read` เอง
> มันค้างใน context ตลอด pipeline **และยังถูกส่งซ้ำอีกในทุก prompt ของลูก**
> (writer 1 + checkwork 1) = จ่ายค่าเนื้อหาชุดเดิม 3 เท่า
> ลูกมี `Read` ครบอยู่แล้ว ให้ลูกอ่านเองใน context ที่ทิ้งได้

> **ถ้าลูกต้องเปิด C1 ฉบับเต็ม** (srcpack ไม่พอ) ให้ลูกอ่าน `content_c1_json` เอง —
> เนื้อความอยู่คีย์ `body[]`, สมการเป็น `$...$` · ถ้ามีแต่ `.docx` ให้ลูกรัน
> `eduone-py read_docx_text.py "<content_c1_docx>"`
> **ห้ามเขียน snippet `p.text` ของ python-docx เอง** — มันอ่านแต่ `w:t` ทำให้ **สมการหาย
> ทั้งไฟล์เงียบ ๆ** (เคยเกิดจริงกับ ม.1 คณิต 114 จุด) `read_docx_text.py` ดึง OMML ให้ด้วย

หน้าปกแผนต้อง **verbatim** เท่ากับหน้าปก C1 ทั้ง 7 แถว — ให้ writer คัดจาก `content_c1_json`
เอง (orchestrator ไม่ต้องอ่านมาแปะ) `validate_spec --ref` จะเทียบให้อีกชั้น

### 3) เรียก sub-agent `lesson-plan-writer`
ส่ง **path เท่านั้น**: `content_srcpack_md`, `content_c1_json`, `scope_md` (บัตรขอบเขตคาบ),
metadata JSON (เล็ก), `period_minutes`, BASE, path output spec.
**ห้ามแปะเนื้อความ C1 ลงใน prompt**
ให้ writer เขียน 2 ไฟล์ spec (path จาก `paths.py`, co-located ใน `2. LessonPlan/`):
- `plan_l1_json`  = `…/<BASE>/2. LessonPlan/{BASE}_L1.json` (แบบที่ 1 เชิงสำรวจ Inquiry-Based)
- `plan_l2_json`  = `…/<BASE>/2. LessonPlan/{BASE}_L2.json` (แบบที่ 2 ผ่านกิจกรรม Activity-Based)

### 3.5) Gate อัตโนมัติก่อนส่ง checkwork (บังคับ)
```bash
export PYTHONIOENCODING=utf-8
for F in "<plan_l1_json>" "<plan_l2_json>"; do
  eduone-py validate_spec.py lesson_plan "$F" --ref "<content_c1_json>" --minutes <period_minutes>
done
```
ตรวจ: `plan.rows` 8 หัวข้อตามชื่อและลำดับที่กำหนด · แถว 7 เป็น dict Rubric ·
ทักษะ 8C ครบ C1–C8 · กิจกรรมครบ 4 ขั้น · เซลล์เป็น str/list/dict ·
**ผลรวมนาทีของขั้นกิจกรรม = `period_minutes`** · **หน้าปกตรง C1 verbatim** · สัญลักษณ์คณิต
**exit ≠ 0 → ให้ writer แก้ก่อน**

> **ทำไมต้องมีขั้นนี้**: กฎเชิงตัวเลข/โครงสร้างเครื่องตรวจได้ในเสี้ยววินาที การปล่อยให้
> checkwork (LLM) ตรวจแทนทำให้เสียรอบแก้ไปกับเรื่องที่ไม่ต้องใช้วิจารณญาณ —
> **checkwork มีไว้ตรวจความถูกต้องของเนื้อหา ความสอดคล้องภายใน และคุณภาพเชิงการสอน**

### 4) เรียก `lesson-plan-checkwork` (loop ≤ 2)
ส่ง **path เท่านั้น**: json 2 ไฟล์ + `content_srcpack_md` + `scope_md` + metadata
(**ห้ามแปะเนื้อความ C1**) checkwork อ่านอย่างเดียว ออก `VERDICT: PASS/FAIL` + รายการแก้.
- PASS → ไปข้อ 5
- FAIL → ส่งรายการแก้กลับให้ writer แก้เฉพาะจุด แล้ว check ซ้ำ. **วนได้ไม่เกิน 2 รอบ** ถ้ายัง FAIL ให้รายงานปัญหาที่เหลือ.

### 5) Build docx ×2
ใช้ path จาก `paths.py` (`plan_l1_json`/`plan_l1_docx` และ L2). โฟลเดอร์ปลายทางถูกสร้างโดย `paths.py`/`ensure_dirs(topic_paths(meta))` แล้ว — build script รับ `<json> <out>` ตรง ๆ (signature ไม่เปลี่ยน).
```bash
export PYTHONIOENCODING=utf-8
eduone-py build_lesson_plan.py "<plan_l1_json>" "<plan_l1_docx>"
eduone-py build_lesson_plan.py "<plan_l2_json>" "<plan_l2_docx>"
```

### 6) Verify ×2 (ต้อง exit 0)
```bash
eduone-py verify_docx.py lesson_plan "<plan_l1_json>" "<plan_l1_docx>"
eduone-py verify_docx.py lesson_plan "<plan_l2_json>" "<plan_l2_docx>"
```
ถ้า exit ≠ 0 → อ่าน error, ส่งกลับ writer แก้ แล้ว build/verify ใหม่ (อยู่ในงบ loop ≤ 2).

### 7) รายงาน
- ยืนยันไฟล์ที่ได้: `plan_l1_docx`, `plan_l2_docx` (ใน `2. LessonPlan/`) และ spec json 2 ไฟล์ (co-located).
- ผลรอบ checkwork (PASS/FAIL, แก้กี่จุด).
- ตาราง token usage ต่อ sub-agent.

## ข้อกำหนดผลลัพธ์
- spec json ตรง schema ของ `build_lesson_plan.py` (header, cover.rows 7 แถว verbatim, plan_title, plan.rows).
- cell รับ str / list[str] / dict `{"template":"8c_standard","codes":["C1","C4"],"topic":"...","skill":"..."}`
  โดย `codes` = ทักษะ 8C สองข้อที่หลักสูตรระบุว่าคาบนี้เน้น (`skills_8c` จาก metadata).
- กิจกรรมแบ่งตาม `period_minutes` (เช่น 50 นาที: ขั้นนำ (ทฤษฎี) / ขั้นสอน (กิจกรรม) /
  ขั้นสรุป / ขั้นวัดผลการเรียนรู้ (แบบฝึกหัด) — รวมเวลาพอดี).
- ความยาวแผนแต่ละไฟล์ 4–5 หน้า. ภาษาไทย สไตล์ OVEC.
