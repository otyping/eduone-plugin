---
name: edu-one
description: MASTER orchestrator ของ EDU ONE (สพฐ.) — รับ (ระดับชั้น, วิชา, No., ผลผลิตที่เลือก 1-7 หรือทั้งหมด) แล้วสั่งงาน agent ทั้ง 7 เป็นระลอก (wave) รัน /content จนถึง "C1 ผ่าน checkwork" ก่อนเสมอ แล้วจึง fan-out C2 + /lesson-plan /exercise /song /video พร้อมกัน → /slides (ครบ 4 แหล่ง) → /game หลัง /exercise. รวบรวมรายงานตาราง token รวมทุก agent. เรียกใช้เมื่อผู้ใช้พิมพ์ "ทำสื่อ / edu one <ชั้น> <วิชา> no.X" หรือเลือกผลผลิตที่ต้องการ.
---

# Skill: edu-one — Master Orchestrator (สพฐ.)

ตัวสั่งงานระดับบนสุดของ EDU ONE. รับหัวข้อเดียว (grade × subject × No.) แล้วสั่ง agent ย่อยทั้ง 7 ตัวให้ผลิตสื่อตามที่ผู้ใช้เลือก โดยรักษาลำดับ dependency. **skill นี้ทำหน้าที่ประสานงานเท่านั้น — รายละเอียดแต่ละขั้นอยู่ใน SKILL.md ของแต่ละ skill ย่อย (อย่าทำซ้ำ).**

## Trigger
ผู้ใช้พิมพ์ทำนอง "ทำสื่อ / edu one <ชั้น> <วิชา> no.X" เช่น "ทำสื่อ ป.1 วิทย์ no.1" หรือระบุเลือกผลผลิต เช่น "ทำสื่อ ม.1 คณิต no.2 เอาแผน+แบบฝึกหัด+เกม".

## INPUT ที่ต้องมี
- `gradeSlug` (p1..p6, m1..m6)
- `subjectSlug` (thai/math/sci/social/health/art/career/english)
- `No`
- `เลือกผลผลิต` 1-7 หรือ "ทั้งหมด" (ถ้าไม่ระบุ → ทำทั้งหมด)

**ถ้าผู้ใช้ไม่ระบุชั้น/วิชา/No → ถามก่อน** อย่าเดา.

## ผลผลิต 7 อย่าง (agent ↔ slash command)
| # | Agent | คำสั่ง | ผลผลิต |
|---|-------|--------|--------|
| 1 | content | `/content` | เอกสารเนื้อหา C1 (วิชาการ) + C2 (เล่าเรื่อง) |
| 2 | lesson-plan | `/lesson-plan` | แผนการสอน L1 (Inquiry) + L2 (Activity) .docx |
| 3 | song | `/song` | เพลงประกอบ (เนื้อ+style; render เป็น stub) |
| 4 | slides | `/slides` | สไลด์นำเสนอ (render เป็น stub) |
| 5 | video | `/video` | วิดีโอ (script/asset; render เป็น stub) |
| 6 | exercise | `/exercise` | แบบฝึกหัดปรนัย 20 ข้อ + เฉลย + สื่อรูป/เสียง ({BASE}_ex.json ไฟล์เดียว + .docx) |
| 7 | game | `/game` | คลังคำถามเกม Kahoot game.json (สุ่มเล่น 10/20 ข้อ) |

## Dependency graph — เดินเป็น "ระลอก" (wave)
**ประตูเดียวของทั้งระบบคือ C1 ผ่าน checkwork** ก่อนหน้านั้นห้ามให้ผลผลิตใดเริ่ม
หลังจากนั้นทุกอย่างที่ไม่ผูกกันให้เดินพร้อมกัน

| ระลอก | ทำอะไร | ยิงพร้อมกันได้ | ปลดล็อกเมื่อ |
|---|---|---|---|
| **W0** | `no_to_token.py` + `paths.py` (สคริปต์ ไม่ใช้โมเดล) | — | — |
| **W1** | `/content` เดินถึงขั้น **C1 ผ่าน checkwork** | เดี่ยว | — |
| **W2** | `/content` ต่อ (C2) · `/lesson-plan` (L1+L2) · `/exercise` · `/song` · `/video` | **writer ทั้ง 5 ยิงพร้อมกัน** | W1 ผ่าน |
| **W3** | gate สคริปต์ทุกไฟล์ → checkwork ของ W2 | checkwork ยิงพร้อมกัน | W2 เขียนเสร็จ |
| **W4** | `/slides` **ครบ 4 แหล่ง C1/C2/L1/L2** | writer 4 ตัวพร้อมกัน → ตรวจรวมครั้งเดียว | W3 ผ่าน (ต้องมี L1/L2 แล้ว) |
| **W5** | `/game` | เดี่ยว | `{BASE}_ex.json` ผ่าน W3 |
| **W6** | build + verify + รายงาน token + git | สคริปต์ | — |

สรุปกฎ:
- **1 (/content) รันก่อนเสมอ** — ถ้ามี C1 ที่ผ่านแล้วอยู่ ข้าม W1 ได้ (บันทึกว่า "skipped").
- **ผลผลิตทั้ง 7 ผลิตครบทุกครั้ง** — C2 และ L2 เป็นไฟล์ส่งงานเช่นกัน **ห้ามตัดออกหรือรอให้สั่งเพิ่ม**
  เช่นเดียวกับสไลด์ที่ต้องครบทั้ง 4 แหล่ง (C1/C2/L1/L2)
- **7 (/game) ต้องรันหลัง 6 (/exercise)** — กิน `{BASE}_ex.json` (อยู่ใต้ `3. Exercise/`; resolve ผ่าน paths.py key `ex_json`). ถ้าผู้ใช้เลือก 7 แต่ไม่เลือก 6 และยังไม่มี `{BASE}_ex.json` → ต้องรัน 6 ให้ก่อน (หรือแจ้งผู้ใช้).
- **4 (/slides) ใช้ C1/C2/L1/L2** — ต้องรันหลัง 1 และ 2.

### กฎการยิงงาน (ที่ทำให้ระลอกมีผลจริง)
1. **ขนาน = เรียก sub-agent หลายตัวใน _ข้อความเดียว_** — ถ้าเรียกทีละข้อความ มันคือการรันเรียงกัน
   ไม่ได้ประหยัดเวลาเลย. ภายในระลอกให้ยิง writer ของทุก skill ในระลอกนั้นพร้อมกัน
   แล้วค่อยไล่รัน gate/build ของแต่ละ skill ตามลำดับ (สคริปต์เร็ว ไม่ใช่คอขวด)
2. **★ ส่ง path ไม่ส่งเนื้อหา — อ่านของหนักในลูก ไม่ใช่ในแม่**
   ของหนัก = ภาพสแกน BookScan · `.docx`/`.json` ฉบับเต็มของ C1/C2/L1/L2 · `_ex.json`
   ถ้า orchestrator `Read` เอง มัน **ค้างใน context ตลอดทั้งงาน** ทุกขั้นหลังจากนั้นแพงขึ้น
   **และยังถูกส่งซ้ำอีกในทุก prompt ของลูก** (slides = ซ้ำ 4 ตัว · exercise = ซ้ำ writer+checkwork)
   → ส่ง **path** ให้ลูก แล้วให้ลูกเปิดอ่านเอง · ทุก sub-agent มี `Read` + `Bash` ครบ
   → ต้นทางที่เป็น `.json` ให้ `Read` ตรง ๆ (สมการเก็บครบเป็น `$...$`)
     ส่วน `.docx` ใช้ `shared/scripts/read_docx_text.py`
   → เฉพาะภาพ BookScan ที่คืนกลับมาเป็น **ข้อความสรุป** ได้ (เพราะแม่ส่ง path ภาพต่อไม่ได้)
3. **★ orchestrator ห้ามสรุปเนื้อหาด้วยคำของตัวเอง** — ถ้าจำเป็นต้องแปะข้อความจริง ๆ
   ให้ **ยกจาก srcpack/C1 มาตรง ๆ ในเครื่องหมายคำพูด** เท่านั้น (ปกติใช้วิธีส่ง path ในข้อ 2 พอ)
   เหตุผล: เคยเกิดจริง — orchestrator เขียนคำว่า "กิ่งเทียนแช่น้ำสีแดง" ลง prompt โดยหยิบคำ
   มาจากคำอธิบาย drawer `dyestem` (ตอนนี้อยู่ที่ `skills/exercise/reference/media-flow.md`)
   ทั้งที่ทุกชั้นของแหล่ง (หนังสือ น.82 → research → C1 → srcpack) เขียนตรงกันว่า
   **"แช่รากและลำต้นของต้นเทียน"** — กิ่งไม่มีราก ผลคือคำผิดไหลลงผลผลิต 2 ชิ้นพร้อมกัน
   และไปขัดกับสิ่งที่สอนไว้เองว่ารากเป็นตัวดูดน้ำ
   **writer ทำตาม prompt ของแม่อย่างซื่อสัตย์เสมอ — แม่พิมพ์ผิด ลูกก็ผิดตาม และผิดพร้อมกันหลายตัว**
4. **งานที่เครื่องตรวจได้ ห้ามให้ LLM ตรวจ** — `validate_spec.py` / `check_math.py` /
   `verify_*.py` รันก่อนเสมอ; checkwork มีไว้ตรวจสิ่งที่ต้องใช้วิจารณญาณเท่านั้น

## ขั้นตอน orchestration

### 1) Lookup metadata (ครั้งเดียว ใช้ร่วมกัน)
```bash
export PYTHONIOENCODING=utf-8
"$LOCALAPPDATA/Programs/Python/Python312/python.exe" \
  "${CLAUDE_PLUGIN_ROOT}/skills/shared/scripts/no_to_token.py" <gradeSlug> <subjectSlug> <No>
```
จด `base` (Title-case เช่น `P1-Sci_U1_1`), `header`, `grade_token`, `subject_token`, `topic_dir`. ใช้กับทุก agent (BASE/header เดียวกัน). **แต่ละ sub-skill resolve path ของตัวเองผ่าน `paths.py <gradeSlug> <subjectSlug> <No>`** — orchestrator ไม่ต้องประกอบ path เอง.

### 2) W1 — รัน /content จนถึง "C1 ผ่าน" ก่อนเสมอ
- ตรวจว่ามี C1 แล้วหรือยัง: เรียก `paths.py` แล้วเช็ค key `content_c1_docx` (อยู่ใต้ `Output/<GradeToken>/<SubjectToken>/<GradeToken>-<SubjectToken>_U<unit>/<BASE>/1. Content/`).
  - มีแล้ว → ข้ามได้ (บันทึกว่า "skipped, ใช้ของเดิม").
  - ยังไม่มี → เรียก skill `content` ซึ่งจะหยุดรอที่ **ขั้น (d) — C1 ผ่าน checkwork** ก่อนเขียน C2
- **ห้ามเริ่มระลอก W2 จนกว่า C1 จะ ALL-PASS** ถ้า C1 ไม่ผ่านใน 2 รอบ → หยุดทั้ง pipeline แล้วถามผู้ใช้

### 3) W2–W3 — Fan-out (เคารพ dependency graph)
- **ยิงพร้อมกันในข้อความเดียว**: `/content` ขั้น C2 · `/lesson-plan` · `/exercise` · `/song` · `/video`
  (ทั้งหมดกิน C1 ที่ผ่านแล้ว ไม่มีตัวไหนกินผลของกันเอง)
- จากนั้นไล่ gate สคริปต์ของแต่ละไฟล์ แล้วยิง checkwork ของแต่ละ skill พร้อมกันอีกครั้ง
- **W4 — /slides ต้องรันหลัง L1/L2 ผ่านแล้ว** เพราะใช้ครบทั้ง 4 แหล่ง (C1/C2/L1/L2)
- **W5 — ถ้าเลือก 7 (/game): รัน 6 (/exercise) ให้ได้ `{BASE}_ex.json` ก่อน** แล้วจึงเรียก /game.
- ถ้า 6 (/exercise) ออกข้อสอบที่มีรูป/เสียง จะได้ `{BASE}_media-brief.md` มาด้วย — **แจ้งผู้ใช้ให้ผลิตสื่อและส่ง URL กลับ** (สื่อยังไม่มีก็ build .docx ได้ โดยแสดงบรรทัดสั่งผลิตแทนรูป).
- ส่ง grade/subject/No เดียวกันให้ทุก skill. แต่ละ skill จัดการ writer/checkwork/build/verify **และ resolve path ของตนเองผ่าน paths.py** (อย่าทำซ้ำที่นี่).

### 4) รวบรวมรายงาน
- สรุปไฟล์ที่ได้ของแต่ละผลผลิต (path เต็ม) + สถานะ (สำเร็จ/skipped/stub/.PENDING).
- ผลผลิตทั้งหมดอยู่ใต้ **topic folder เดียว**: `Output/<GradeToken>/<SubjectToken>/<GradeToken>-<SubjectToken>_U<unit>/<BASE>/` โดยแยกเป็น product subfolder เลข 1–7 (`1. Content/` … `7. Activity/`) — ครูได้ **หนึ่งโฟลเดอร์ต่อหนึ่งหัวข้อ** ครบทุกผลผลิต.
- **ตาราง token รวม**: หนึ่งแถวต่อไฟล์ผลผลิต (หรือต่อ skill) + แถวรวมท้ายตาราง.

## หมายเหตุสถานะผลผลิต
- **3 (song) / 4 (slides) / 5 (video)**: ขั้น render เป็น **stub** — ผลผลิตเป็นไฟล์ `.PENDING` จนกว่าจะใส่ API key (artifact JSON/script ผลิตครบ แต่สื่อจริงรอ render).
- **7 (game)**: ผลิต **JSON** (`game.json`) เท่านั้น — เกม web-app ยังไม่สร้าง (ดู `game-app/README.md`).
- **1, 2, 6**: ผลิต .docx/.json ครบสมบูรณ์.

## ข้อกำหนด
- รัน /content ก่อนเสมอ (หรือยืนยันว่ามี C1 อยู่แล้ว). เคารพ dependency: 7 หลัง 6; 4 หลัง 1,2.
- ไม่ทำซ้ำรายละเอียด step ของ skill ย่อย — ชี้ไปที่ SKILL.md ของแต่ละ skill.
- รายงานตาราง token รวมทุก agent ที่รัน (ต่อไฟล์ + แถวรวม). ภาษาไทย สไตล์ OVEC.
