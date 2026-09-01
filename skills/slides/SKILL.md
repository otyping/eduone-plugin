---
name: slides
description: สร้างสไลด์นำเสนอสื่อการเรียนรู้ EDU ONE (สพฐ.) จาก 4 แหล่ง C1/C2/L1/L2 (ทำครบทุกแหล่งเสมอ) — lookup token → slides-writer เขียน artifact ทุกแหล่งพร้อมกัน (writer อ่านต้นทางเอง) → validate_spec → slides-checkwork ตรวจรวมครั้งเดียว → build .pptx จริงจากเทมเพลตผู้ใช้ → verify. ใช้เมื่อผู้ใช้ขอ "ทำสไลด์/สไลด์นำเสนอ/slides/pptx"
---

# SKILL: slides — ผลิตสไลด์นำเสนอ (4 ไฟล์ ต่อ C1/C2/L1/L2)

ออร์เคสเตรต Agent 4 สร้างสไลด์ **1 ไฟล์ต่อแหล่ง** = รวม 4 ไฟล์
**ทำครบทั้ง 4 แหล่งทุกครั้ง** — C2 และ L2 เป็นไฟล์ส่งงานเช่นเดียวกับ C1/L1 **ห้ามข้ามหรือรอให้สั่งเพิ่ม**
(ยกเว้นแหล่งที่ไม่มีไฟล์ต้นทางจริง ๆ → ข้ามแล้วแจ้งในรายงาน)

> 📄 **ก่อน build / เจอปัญหาฟอนต์-ล้นกรอบ-รูปประกอบ** อ่าน
> `${CLAUDE_PLUGIN_ROOT}/skills/slides/reference/build-notes.md` — เทมเพลต · ฟอนต์ `a:cs` · กฎ "(ต่อ)" ห้ามย่อ ·
> ใบสั่งผลิตรูป · ตารางแปลง L1/L2 → ภาษานักเรียน
> (ย้ายออกจาก CLAUDE.md มาไว้ที่นี่ **โหลดเฉพาะตอนต้องใช้จริง**)

## ★ เพดานจำนวนสไลด์ — นับหน้าที่ render จริง ไม่ใช่หน้าใน JSON
**คาบสอน 50 นาที ใช้ได้ไม่เกิน 30-40 สไลด์** (ผู้ใช้เป็นครู กำหนดมาจากการสอนจริง) →
**ตั้งเป้าที่ ≤ 36 หน้าต่อชุด**

**ต้องนับหน้าที่ render จริง** เพราะหน้าที่เนื้อหาแน่นเกินกรอบจะถูกแตกเป็นหน้า "(ต่อ)" อัตโนมัติ
(engine ไม่ย่อตัวอักษร) — วัดจริงแล้วบวมได้ถึง **+63% ถึง +81%** (27 หน้า → 49 · 38 หน้า → 62)
```bash
eduone-py build_slides.py <slides_json> <ไฟล์ชั่วคราว.pptx> --no-embed
```
บรรทัดท้ายบอก `(N สไลด์)` = จำนวนจริง · เกินเพดาน → **ลดข้อความต่อหน้าก่อนเสมอ**
(ตัดหน้าที่ถูกแตก "(ต่อ)" ได้ทีละ 2 หน้า) แล้วค่อยยุบหน้าที่ซ้ำประเด็น แล้วค่อยตัดหน้าที่คุณค่าน้อยสุด
**ภาษาเขียนทั้งหมด: ไทย** กระชับ สไตล์ OVEC

## INPUT
ต้องการ `grade_slug`, `subject_slug`, `No`
**ถ้าผู้ใช้ไม่ระบุครบ → ถามก่อน อย่าเดา**

## ขั้นตอน

### STEP 1 — Lookup token
```bash
export PYTHONIOENCODING=utf-8
eduone-py no_to_token.py <gradeSlug> <subjectSlug> <No>
```
เก็บ `base` (Title-case เช่น `P1-Sci_U1_1`), `header`, `lang`, `topic_name`, `obj[]`, `comp[]`, `topic_dir`, ระดับชั้น
เรียก `paths.py` เพื่อรับ path ที่แน่นอน (ห้ามต่อ path เอง):
```bash
export PYTHONIOENCODING=utf-8
eduone-py paths.py <gradeSlug> <subjectSlug> <No>
```
ได้ JSON keys: `slides_json{C1,C2,L1,L2}`, `slides_pptx{C1,C2,L1,L2}`,
**`content_c1_json`, `content_c2_json`, `plan_l1_json`, `plan_l2_json`** (ต้นทาง 4 แหล่ง),
`topic_dir`, `dirs{...}` ฯลฯ

### STEP 2 — ✋ **เช็คว่าไฟล์ต้นทางมีจริง — ห้ามอ่านเนื้อหาเอง**
```bash
ls -l "<content_c1_json>" "<content_c2_json>" "<plan_l1_json>" "<plan_l2_json>"
```
- แหล่งใดไม่มีไฟล์ → ข้ามแหล่งนั้น และแจ้งในรายงาน
- **orchestrator ไม่อ่านเนื้อหาต้นทางเด็ดขาด** — ส่ง path ให้ writer ไปอ่านเอง (ดูกฎทองใน CLAUDE.md)
  ต้นทาง 4 แหล่งรวมกัน ~16-24k token ถ้าแม่อ่านเอง จะค้างใน context ตลอด pipeline
  และยังถูกส่งซ้ำอีกใน prompt ของ writer ทั้ง 4 ตัว

> **ทำไมเป็น `.json` ไม่ใช่ `.docx`**: JSON เป็น source of truth และ **เก็บสมการไว้ครบเป็น
> `$...$` LaTeX** ส่วน `.docx` เก็บสมการเป็น Word Equation ที่ python-docx อ่านไม่เห็น —
> เคยทำสมการหายเงียบ ๆ ทั้งไฟล์ในวิชาคณิต · หัวข้อเก่าที่มีแต่ `.docx` ให้ writer ใช้
> `shared/scripts/read_docx_text.py <docx>` แทน

### STEP 3 — เขียน artifact **ทุกแหล่งพร้อมกัน** (ทำครบทั้ง 4 แหล่งเสมอ)

**3.0) ดึงข้อจำกัดของเทมเพลต — ครั้งเดียว ใช้ผลร่วมกันทุกแหล่ง** (เทมเพลตแบบสเปก LAYOUT เท่านั้น)
```bash
eduone-py pptx_slots.py --limits "<เทมเพลตของวิชา×ชั้น>"
```
ได้ตารางทุก LAYOUT: ชื่อช่อง · ขนาดกรอบ · **จำนวนตัวอักษรที่ใส่ได้จริง**
**แนบผลลัพธ์นี้เข้า prompt ของ slides-writer ทุกตัว** — writer ที่รู้ข้อจำกัดตั้งแต่ต้น
เขียนพอดีกรอบ ไม่ต้องถอย layout (วัดจริงแล้ว: ไม่แนบ = ถอย 6 หน้า · แนบ = ถอย 0 หน้า)

**3.1) ยิง `slides-writer` ทุกแหล่งพร้อมกันใน _ข้อความเดียว_** (1 แหล่ง = 1 agent)
ส่งให้แต่ละตัว: `base`, `header`, `lang`, `src`, ระดับชั้น, **`src_path`** = path ของต้นทาง
**แหล่งนั้นเท่านั้น** (`content_c1_json` / `content_c2_json` / `plan_l1_json` / `plan_l2_json`)
และผลจาก 3.0 · slides-writer ต้อง **อ่าน `${CLAUDE_PLUGIN_ROOT}/skills/slides/reference/prompt-master-powerpoint.md` ก่อน**
แล้วเขียนที่ key `slides_json[<src>]` = `.../<BASE>/4. Slides/{BASE}_slides_<src>.json`

> **ส่ง path ไม่ส่งเนื้อหา** — writer เป็นคน `Read` ต้นทางเอง เนื้อหาหนักจึงอยู่ใน context
> ของลูกที่ทิ้งได้ · ผลจาก 3.0 ยังส่งเป็นข้อความเพราะเล็กและ writer ทั้ง 4 ตัวใช้ชุดเดียวกัน

> ไม่มีแหล่งไหนกินผลของอีกแหล่ง — ยิงทีละตัวได้ผลเหมือนกันแต่ช้ากว่า 4 เท่า

**3.2) Gate อัตโนมัติ (บังคับ) — รันทีละไฟล์ เร็ว ไม่ใช้โมเดล**
```bash
eduone-py validate_spec.py slides <slides_json[src]>
```
ตรวจ: ลำดับ 6 ส่วนบังคับ · vocab ≤ 6 คำ/หน้า 4 คอลัมน์ · `image_prompt` ไม่มีอักษรไทย
และยาวพอ · **ถ้า src เป็น L1/L2: ไม่มีคำสั่งครู/ศัพท์แผนขึ้นจอ และหน้ากิจกรรมมี `speaker_note`**
**exit ≠ 0 → ให้ writer ของแหล่งนั้นแก้ก่อน ยังไม่ต้องส่ง checkwork**

> **ทำไมต้องมีขั้นนี้**: กฎเชิงตัวเลข/โครงสร้างเครื่องตรวจได้ในเสี้ยววินาที การปล่อยให้
> checkwork (LLM) ตรวจแทนทำให้เสียรอบแก้ไปกับเรื่องที่ไม่ต้องใช้วิจารณญาณ —
> **checkwork มีไว้ตรวจความถูกต้องของเนื้อหา ความสอดคล้องภายใน และคุณภาพเชิงการสอน**

### STEP 4 — `slides-checkwork` **ครั้งเดียว ตรวจทุกแหล่งรวมกัน** (loop ≤ 2 รอบ)
ส่ง path ของ artifact ที่ผ่าน gate **ทั้งหมดในการเรียกครั้งเดียว** (ไม่ใช่ 4 ครั้ง)
- agent อ่าน Master Prompt (~22 KB) **รอบเดียว** แล้วเดิน RUBRIC กับทุกไฟล์ — เดิมอ่านซ้ำ 4 รอบ
- ได้ผลรายแหล่ง (`C1: PASS` / `L1: FAIL (2)`) แล้วปิดท้ายด้วย `VERDICT` รวม
- **FAIL** → ส่งรายการแก้ที่นำหน้าด้วย `[<src>]` กลับ **เฉพาะ writer ของแหล่งที่ FAIL**
  (ยิงพร้อมกันได้อีก) แล้วเรียก checkwork รอบสอง **ส่งเฉพาะไฟล์ที่แก้** (≤ 2 รอบ)
- **แหล่งที่ PASS แล้วเดินหน้า STEP 5 ได้ทันที ไม่ต้องรอแหล่งอื่น**

### STEP 5 — Build เป็น .pptx จริง (ต่อแหล่ง)
```bash
export PYTHONIOENCODING=utf-8
eduone-py check_math.py  <slides_json[src]>          # gate สัญลักษณ์
eduone-py build_slides.py <slides_json[src]> <slides_pptx[src]>
eduone-py verify_pptx.py  <slides_pptx[src]>         # ต้อง exit 0
```
(`<slides_json[src]>`, `<slides_pptx[src]>` = ค่าจาก `paths.py`; pptx อยู่ใน `4. Slides/` ร่วมกับ json)

`build_slides.py` หยิบเทมเพลตของ **วิชา × ชั้นปี** มาเป็นฐานเอง แล้ววางเนื้อหาตามกติกา:
- เทมเพลต `Slide Master Template/<Subject> <Grade>/Slide Master_<Subject>_<Grade>.pptx`
  (ไม่มีของชั้นนั้น -> ถอยไปวิชาเดียวกันชั้นอื่น พร้อม `WARN` — เห็น WARN ให้แจ้งผู้ใช้ในรายงาน)
- หัวข้อ **Prompt** · เนื้อหา/ตาราง **TH Sarabun New** · ฝังฟอนต์ลงไฟล์อัตโนมัติ (PowerPoint COM)
- ตัวอักษรใหญ่พออ่านจากหลังห้อง (หัวข้อ 32pt · บุลเล็ต 28pt · พื้นต่ำสุด 24pt)
- **เนื้อหาไม่พอ 1 หน้า -> ขึ้นหน้าใหม่ต่อท้ายชื่อว่า "(ต่อ)" โดยคงเนื้อหาเดิม ไม่ย่อตัวอักษร**
- ตัดคำไทยตามขอบคำจริง · สมการ `$...$` เป็นยกกำลัง/ตัวห้อยจริง (เศษส่วน/กรณฑ์เป็นสมการ Office)
- หน้า `content` ที่มี `image_prompt` จะเว้นกรอบ "ภาพประกอบ" ไว้ให้ + เก็บ prompt ลง speaker note
  ถ้า JSON มี `image_file` (path รูปเทียบกับโฟลเดอร์ของ JSON) จะฝังรูปจริงแทนกรอบว่าง

ตัวเลือกที่ใช้บ่อย: `--template <path>` ระบุเทมเพลตเอง · `--no-embed` ข้ามการฝังฟอนต์
(ใช้เมื่อไม่มี PowerPoint ในเครื่อง — ตอน verify ให้ใส่ `--no-embed-check` ด้วย)

### STEP 5.1 — ใบสั่งผลิตรูป (เมื่อแหล่งนั้นมี `image_prompt`)
```bash
eduone-py build_slides_brief.py <slides_json[src]>
```
ได้ `slides_brief_md[src]` = `{BASE}_slides_<src>_media-brief.md` (จาก `paths.py`) —
prompt ภาษาอังกฤษพร้อมคัดลอกไปวาง **Google Nano Banana** (ตัดประโยคสั่งใส่ป้ายไทยออกให้แล้ว
และต่อท้ายข้อห้ามมาตรฐาน) + ตารางชื่อไฟล์ที่ต้องส่งกลับ
**รายงานให้ผู้ใช้ทราบว่ามีรูปกี่ไฟล์ที่ต้องผลิต และไฟล์ใบสั่งผลิตอยู่ที่ไหน**

### STEP 5.2 — เติมรูปที่ผลิตเสร็จ ("เติมรูปสไลด์ <ชั้น> <วิชา> no.X")
ผู้ใช้วางไฟล์รูปลง `slides_media_dir[src]` (`{BASE}_slides_<src>_media/`) หรือส่งรายการ URL มา
```bash
eduone-py fill_slides_images.py <slides_json[src]> [<โฟลเดอร์|urls.txt>]
eduone-py build_slides.py <slides_json[src]> <slides_pptx[src]>
```
- จับคู่ด้วยชื่อไฟล์ `{BASE}_slides_<src>_<NN>.png` (NN = ลำดับหน้าใน `slides[]`)
- **ตรวจให้ผ่านก่อนแล้วค่อยเขียน** — ชื่อไฟล์เลขผิด/ซ้ำ/ชนิดไม่ใช่รูป = ไม่แตะ json เลย
- รันซ้ำได้ ไม่ทับของเดิม (ทับต้อง `--force`) · `--dry-run` ดูผลก่อน
- หน้าไหนยังไม่มีรูป ยังเป็นกรอบ "ภาพประกอบ" ตามเดิม — build ได้ปกติ ไม่ต้องรอครบ

**ตรวจด้วยตาเมื่อทำหัวข้อ/วิชาใหม่ครั้งแรก** (ไม่ต้องทำทุกครั้ง):
```bash
eduone-py embed_fonts_pptx.py --png <slides_pptx[src]> <โฟลเดอร์ png>
```
แล้ว `Read` ไฟล์ png ดูว่าข้อความไม่ทับกรอบตกแต่ง · ตัดคำถูก · สระ/วรรณยุกต์ไม่โดนตัด

> `slides/scripts/gamma_render.py` (Gamma/Canva ออนไลน์) ยังเก็บไว้เป็นทางเลือก ไม่ใช่ทางหลักแล้ว

### STEP 6 — รายงาน
สรุป (ไทย) ต่อแหล่ง: artifact `slides_json[src]` (`4. Slides/`), ไฟล์ `slides_pptx[src]` + จำนวนสไลด์,
ผลตรวจ checkwork และ `verify_pptx`, แหล่งที่ข้ามเพราะไม่มี docx, และ WARN เรื่องเทมเพลต/กรอบภาพ (ถ้ามี)
