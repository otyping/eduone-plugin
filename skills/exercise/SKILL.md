---
name: exercise
description: สร้างแบบฝึกหัดปรนัย 20 ข้อ (4 ตัวเลือก) ระดับ สพฐ. พร้อมหน้าเฉลย+วิธีคิดทุกข้อ จากไฟล์เนื้อหา C1 ของหน่วยนั้น ออกเป็น JSON ไฟล์เดียว {BASE}_ex.json + .docx. รองรับโจทย์และตัวเลือกที่เป็นข้อความ รูป หรือเสียง (รูปฝังใน docx ให้อัตโนมัติ · บทเสียงเป็นข้อความสีน้ำเงิน · เฉลยสีแดง). ความยาก 10 easy/5 medium/5 hard, ≥30% สถานการณ์จริง. เรียกใช้เมื่อผู้ใช้พิมพ์ "ทำ exercise / ทำแบบฝึกหัด <ชั้น> <วิชา> no.X". ใช้ "เติม url แบบฝึกหัด <ชั้น> <วิชา> no.X" เพื่อเติม URL สื่อที่ผลิตเสร็จแล้ว.
---

# Skill: exercise — แบบฝึกหัดปรนัย (สพฐ.)

orchestrator ของ pipeline แบบฝึกหัด. ออกข้อสอบปรนัย 20 ข้อ + เฉลย + วิธีคิด จากเนื้อหาวิชาการ (C1)
ลง **JSON ไฟล์เดียว** แล้ว build เป็น .docx ฉบับผู้ตรวจ

> 📄 **ข้อสอบมีรูป/เสียง?** อ่าน `${CLAUDE_PLUGIN_ROOT}/skills/exercise/reference/media-flow.md` ก่อน —
> สคีมาสื่อ · ใบสั่งผลิต · Uvoice/Nano Banana · drawer ที่วาดรูปเองได้ทั้งหมด · กฎ build/verify
> (ย้ายออกจาก CLAUDE.md มาไว้ที่นี่ **โหลดเฉพาะตอนต้องใช้จริง**)

## Trigger
"ทำ exercise / ทำแบบฝึกหัด / ออกข้อสอบ `<ระดับชั้น> <วิชา> no.X`"
ต้องมี **ระดับชั้น + วิชา + No.** ครบ — **ถ้าไม่ครบให้ถามก่อน ห้ามเดา**

## ค่าคงที่
```
$PY = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
$env:PYTHONIOENCODING = "utf-8"
```
`gradeSlug` ∈ p1..p6, m1..m6 · `subjectSlug` ∈ thai/math/sci/social/health/art/career/english

---

## ขั้นตอน (ทำตามลำดับ)

### 1. Lookup metadata
```powershell
& $PY .claude\skills\shared\scripts\no_to_token.py <gradeSlug> <subjectSlug> <No>
& $PY .claude\skills\shared\scripts\paths.py <gradeSlug> <subjectSlug> <No>
```
บันทึก `BASE`, `header`, `topic_name`, `obj`, `comp`
**อย่าประกอบ path เอง** — ใช้คีย์จาก `paths.py`: **`content_c1_json`** (ต้นทางข้อสอบ),
`content_c1_docx` (สำรอง), `ex_json`, `exercise_docx`,
`ex_brief_md`, `ex_audio_src_json`, `ex_media_dir`, `ex_urls_txt`

### 2. ✋ **เช็คว่า C1 มีจริง — ห้ามอ่านเนื้อหาเอง**
```powershell
Test-Path "<content_c1_json>"; Test-Path "<content_c1_docx>"
```
- ไม่มีทั้งคู่ → **หยุด** แจ้งผู้ใช้ให้รัน `/content` ก่อน
- **orchestrator ไม่อ่าน C1 เด็ดขาด** — ส่ง path ให้ `exercise-writer` และ `exercise-checkwork`
  ไปอ่านเอง (ดูกฎทองใน CLAUDE.md) C1 เต็ม 3-5 หน้า ถ้าแม่อ่านเองจะค้างใน context
  **และถูกส่งซ้ำอีก 2 รอบ** (เข้า writer แล้วเข้า checkwork) = จ่ายค่าเนื้อหาชุดเดิม 3 เท่า

> **ทำไมเป็น `content_c1_json` ไม่ใช่ `.docx`**: JSON เป็น source of truth และ **เก็บสมการไว้ครบ
> เป็น `$...$` LaTeX** ส่วน `.docx` เก็บสมการเป็น Word Equation ที่ python-docx อ่านไม่เห็น —
> วิธีเดิมทำสมการหายทั้งไฟล์ในวิชาคณิต (ออกข้อสอบจากเนื้อหาที่ตัวเลขหายไปหมด)
> · หัวข้อเก่าที่มีแต่ `.docx` ให้ลูกใช้ `shared/scripts/read_docx_text.py <docx>` แทน

**(ถ้ามี BookScan ของวิชานี้)** ใช้เป็นข้อมูลประกอบได้:
```powershell
& $PY .claude\skills\shared\scripts\bookscan_index.py find "<คำค้น>" --subject <Subject> --grade <M.x>
& $PY .claude\skills\shared\scripts\bookscan_page.py <book> <ช่วงหน้า> --subject <Subject> --grade <M.x>
```
แล้ว `Read` ไฟล์ภาพที่ได้ ส่งสาระให้ writer (อย่าส่ง path ภาพดิบให้ writer เดาเอง)

### 3. เรียก sub-agent `exercise-writer`
ส่ง: metadata + **`content_c1_json` (path — ให้ writer อ่านเอง)** + `ex_json` (path ปลายทาง)
\+ (ถ้ามี) สาระจาก BookScan
→ writer เขียน `{BASE}_ex.json` ไฟล์เดียว (URL สื่อว่างทั้งหมด)

### 3.5 Gate อัตโนมัติก่อนส่ง checkwork (บังคับ)
```powershell
& $PY .claude\skills\shared\scripts\validate_spec.py exercise "<ex_json>"
```
ตรวจ: โควตา easy/medium/hard ตามจำนวนข้อ · 4 ตัวเลือก/ข้อ · `isTrue` ข้อละ 1 ·
ไม่มี prefix ก./ข./ค./ง. · ไม่มี "ถูกทุกข้อ/ไม่มีข้อถูก" · `solutionSteps` ครบ ·
ไม่มี field `answer` · ตำแหน่งเฉลยไม่กระจุก/ไม่วนซ้ำ (WARN) · สัญลักษณ์คณิต
**exit ≠ 0 → ส่งกลับ writer แก้ก่อน ไม่นับเป็นรอบ checkwork**

> **ทำไมต้องมีขั้นนี้**: กฎเชิงตัวเลข/โครงสร้างเครื่องตรวจได้ในเสี้ยววินาที การปล่อยให้
> checkwork (LLM) ตรวจแทนทำให้เสียรอบแก้ไปกับเรื่องที่ไม่ต้องใช้วิจารณญาณ —
> **checkwork มีไว้ตรวจความถูกต้องของเนื้อหา ความสอดคล้องภายใน และคุณภาพเชิงการสอน**

### 4. เรียก `exercise-checkwork` (loop ≤ 2 รอบ)
ส่ง: `ex_json` (path) + **`content_c1_json` (path — ให้ checkwork อ่านเอง)** + (รอบ 2) `changed_questions`
- `VERDICT: PASS` → ไปขั้น 5
- `VERDICT: FAIL` → ส่งรายการแก้ + `changed_questions` กลับให้ writer แก้ **เฉพาะข้อที่ระบุ** → ตรวจซ้ำ
- **สูงสุด 2 รอบ**

### 5. สร้างใบสั่งผลิตสื่อ (ข้ามได้ถ้าข้อสอบเป็นข้อความล้วน)
```powershell
& $PY .claude\skills\exercise\scripts\build_media_brief.py "<ex_json>" --base "<BASE>" --title "เรื่อง<topic_name>"
```
ได้ `{BASE}_media-brief.md` (ใบสั่งผลิตรูป) + `{BASE}_audio-src.json` (บทเสียงสำหรับ TTS)
ถ้าไม่มีสื่อจะพิมพ์ว่าไม่ต้องสร้าง — ถือว่าปกติ

### 6. Build .docx
```powershell
& $PY .claude\skills\shared\scripts\build_exercise.py "<ex_json>" "<exercise_docx>" --header "<header>" --base "<BASE>"
```
ช่องสื่อที่ยังไม่มี URL จะแสดงเป็นบรรทัดสั่งผลิต `[รูปภาพ] {BASE}_01_Q.png — คำบรรยาย`

### 7. Verify (tester — ต้อง exit 0)
```powershell
& $PY .claude\skills\shared\scripts\verify_docx.py exercise "<ex_json>" "<exercise_docx>" --header "<header>"
```
exit ≠ 0 → อ่านรายการปัญหา: ปัญหา JSON ส่งกลับ writer (อยู่ในโควตา ≤ 2 รอบเดิม) ·
ปัญหาการเรนเดอร์แก้ที่ script

### 8. รายงาน + ส่งมอบใบสั่งผลิตสื่อ
รายงาน: path ไฟล์ที่ได้ · สัดส่วนความยาก 10/5/5 · % สถานการณ์จริง · ผล checkwork · ผล verify
· **ถ้ามีสื่อ: บอกผู้ใช้ว่าต้องผลิตกี่ไฟล์ ชี้ไปที่ `{BASE}_media-brief.md` และบอกว่าอัปโหลดเสร็จ
ให้ส่งรายการ URL กลับมา** · ตาราง token ต่อ sub-agent

### 9. (ภายหลัง) เติม URL สื่อ แล้ว build ซ้ำ
เมื่อผู้ใช้ส่งรายการ URL มา → บันทึกลง `ex_urls_txt` แล้ว
```powershell
& $PY .claude\skills\exercise\scripts\fill_ex_urls.py "<ex_urls_txt>" "<ex_json>" --base "<BASE>"
& $PY .claude\skills\shared\scripts\build_exercise.py "<ex_json>" "<exercise_docx>" --header "<header>" --base "<BASE>"
& $PY .claude\skills\shared\scripts\verify_docx.py exercise "<ex_json>" "<exercise_docx>" --header "<header>"
```
`fill_ex_urls.py` จะ **ตรวจให้ครบก่อนแล้วค่อยเขียน** — ถ้าไฟล์ขาด/ชนิดไม่ตรง จะไม่แตะไฟล์เดิม
รันซ้ำได้ (URL ที่เติมแล้วคงอยู่)

### 10. git
```powershell
git add -A ; git commit -m "feat(exercise): แบบฝึกหัด <ระดับชั้น> <วิชา> No.<N>"
```

---

## Output ที่ได้ (ใน `3. Exercise/`)

| ไฟล์ | git | คำอธิบาย |
|---|---|---|
| `{BASE}_ex.json` | ✅ track | **source of truth** — โจทย์ + ตัวเลือก + เฉลย + วิธีคิด + สื่อ |
| `{BASE}_ex.docx` | ignored | ฉบับผู้ตรวจ (rebuild ได้) |
| `{BASE}_media-brief.md` | ✅ track | ใบสั่งผลิตรูป (มีเฉพาะเมื่อมีสื่อ) |
| `{BASE}_audio-src.json` | ✅ track | บทเสียงสำหรับ TTS (มีเฉพาะเมื่อมีเสียง) |
| `{BASE}_urls.txt` | ✅ track | รายการ URL ที่ผู้ใช้ส่งกลับมา |

## สเปกข้อสอบ (ย่อ — ฉบับเต็มที่ `reference/prompt-master-exercise.md`)

- 20 ข้อ 4 ตัวเลือก · easy 10 / medium 5 / hard 5 เป๊ะ · สถานการณ์จริง ≥ 6 ข้อ
- ห้าม "ถูกทุกข้อ / ไม่มีข้อถูก" · ห้ามระบุระดับความยากในตัวคำถาม
- `content` ของตัวเลือก **ห้ามมี prefix ก./ข./ค./ง.** — ตัวอักษรมาจากลำดับ array
- คำตอบถูกระบุด้วย `isTrue: true` ข้อละ 1 ตัว (ไม่มี field `answer`)
- ทุกข้อต้องมี `solutionSteps`
- ทุกช่องสื่อต้องมีคำบรรยาย (`imageAlt` / `audioText` / `alt`)

## หมายเหตุ
- `{BASE}_ex.docx` เป็น **ฉบับผู้ตรวจ/ครู** โดยตั้งใจ (เฉลยสีแดง + บทเสียงสีน้ำเงิน + หน้าเฉลย)
- ทุก sub-agent ใช้ `model: opus` — **ห้ามเปลี่ยน** (CLAUDE.md ข้อ 8)
- เตือนผู้ใช้เปิดไฟล์ใน Word 1 ครั้งก่อนใช้จริง (กัน font fallback)
- `/game` อ่าน `{BASE}_ex.json` ไฟล์นี้โดยตรง (ไม่ใช้ ex_q/ex_a แล้ว)
