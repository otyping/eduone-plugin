---
name: game
description: สร้างคลังคำถามเกมตอบคำถามแบบ Kahoot (game.json) ระดับ สพฐ. จากแบบฝึกหัด 20 ข้อ ({BASE}_ex.json ของ Agent 6) — เก็บครบ 20 ข้อ เกมสุ่มเล่นครั้งละ 10 ข้อ คะแนน = ความถูก + ความเร็ว. ลำดับงาน lookup token → ตรวจมี {BASE}_ex.json → build_game_json.py → game-writer/game-checkwork ตรวจคุณภาพให้เหมาะเล่นจับเวลา. เรียกใช้เมื่อผู้ใช้พิมพ์ "ทำ game / ทำเกม <ชั้น> <วิชา> no.X".
---

# Skill: game — คลังคำถามเกม Kahoot (สพฐ.)

orchestrator ของ Agent 7. แปลงแบบฝึกหัดปรนัย 20 ข้อ (ผลผลิตของ Agent 6 /exercise) เป็นคลังคำถามเกม `game.json` เหมาะเล่นแข่งจับเวลา. เกมเก็บครบ 20 ข้อ แต่ game-app จะสุ่มเล่นครั้งละ `play.draw` (=10) ข้อ. **Agent 7 ผลิตเฉพาะ JSON** — ตัว game web-app เป็นเฟสถัดไป (ดู `game-app/README.md`).

## Trigger
ผู้ใช้พิมพ์ทำนอง "ทำ game / ทำเกม <ชั้น> <วิชา> no.X" เช่น "ทำเกม ป.1 วิทย์ no.1".

## INPUT ที่ต้องมี
- `gradeSlug` (p1..p6, m1..m6)
- `subjectSlug` (thai/math/sci/social/health/art/career/english)
- `No`

**ถ้าผู้ใช้ไม่ระบุครบ → ถามก่อน** อย่าเดา.

## ขั้นตอน orchestration

### 1) Lookup metadata
```bash
export PYTHONIOENCODING=utf-8
"$LOCALAPPDATA/Programs/Python/Python312/python.exe" \
  "${CLAUDE_PLUGIN_ROOT}/skills/shared/scripts/no_to_token.py" <gradeSlug> <subjectSlug> <No>
```
จด `base` (Title-case เช่น `P1-Sci_U1_1`), `header`, `grade_token`, `subject_token`, `topic_dir`. (ไฟล์ args ดึงจาก paths.py ในขั้นถัดไป.)

### 2) Resolve paths + ตรวจว่ามีไฟล์แบบฝึกหัด (input ของเกม)
รัน paths.py เพื่อได้ path เต็มของไฟล์ (อยู่ใต้ `7. Activity/`):
```bash
export PYTHONIOENCODING=utf-8
"$LOCALAPPDATA/Programs/Python/Python312/python.exe" \
  "${CLAUDE_PLUGIN_ROOT}/skills/shared/scripts/paths.py" <gradeSlug> <subjectSlug> <No>
```
จด key `ex_json` (อยู่ใน `3. Exercise/` คู่กับ ex.docx) และ `game_json` (อยู่ใน `7. Activity/`) — ทั้งหมดใต้ `Output/<GradeToken>/<SubjectToken>/<GradeToken>-<SubjectToken>_U<unit>/<BASE>/`.
ต้องมีไฟล์นี้ (จาก paths.py key `ex_json`):
- `<ex_json>` = `.../3. Exercise/{BASE}_ex.json` (ไฟล์เดียว มีทั้งโจทย์ เฉลย วิธีคิด และสื่อ)
```bash
ls "<ex_json>"
```
**ถ้าไม่มี → หยุด แล้วแจ้งผู้ใช้ให้รัน `/exercise <ชั้น> <วิชา> no.X` ก่อน** (เกมกินผลผลิตจาก /exercise).

### 3) Build game.json
```bash
export PYTHONIOENCODING=utf-8
PY="$LOCALAPPDATA/Programs/Python/Python312/python.exe"
"$PY" .claude/skills/game/scripts/build_game_json.py \
  "<ex_json>" "<game_json>" \
  --base "<BASE>" --header "<header>" --title "เรื่อง<topic_name>"
```
(`<ex_json>`, `<game_json>` = key จาก paths.py; `<BASE>`/`<header>`/`<topic_name>` = จาก no_to_token.) ผลลัพธ์ `<game_json>` = `.../7. Activity/{BASE}_game.json` (schema_version 2, 20 questions, play.draw=10). builder ดึงคำถาม/ตัวเลือกจาก `questions[]`, หาเฉลยจากตำแหน่งของ `isTrue`, และ explanation จาก `solutionSteps` อัตโนมัติ; ฟิลด์สื่อ (`image_url`/`audio_url`/`content_type`/`media_url`) ส่งต่อไปด้วยเผื่อ Stage 2.

### 4) เรียก sub-agent `game-writer`
ส่ง path `<game_json>` (`.../7. Activity/{BASE}_game.json`) + path `<ex_json>`. ให้ writer review/ปรับ `game.json` ให้เหมาะเล่นเกมจับเวลา: คำถาม/ตัวเลือกกระชับ ชัด ไม่กำกวม, explanation สั้น. **คงเฉลย (answer/correct) ให้ตรงกับ `isTrue` ใน `{BASE}_ex.json` เดิม**. แก้ที่ game.json เท่านั้น.

### 5) เรียก `game-checkwork` (loop ≤ 2)
ส่ง path game.json + `<ex_json>`. checkwork อ่านอย่างเดียว ออก `VERDICT: PASS/FAIL` + รายการแก้ (ระบุ id ข้อ).
- PASS → ไปข้อ 6.
- FAIL → ส่งรายการแก้ + `changed_questions` กลับให้ writer แก้เฉพาะข้อ แล้ว check ซ้ำ. **วนได้ไม่เกิน 2 รอบ**.

### 6) รายงาน
- ไฟล์ที่ได้: `<game_json>` = `Output/<GradeToken>/<SubjectToken>/<GradeToken>-<SubjectToken>_U<unit>/<BASE>/7. Activity/{BASE}_game.json` (20 ข้อ, สุ่มเล่นครั้งละ 10).
- หมายเหตุ: เกม web-app ยังไม่สร้าง (ดู `game-app/README.md`) — ผลผลิตเฟสนี้คือ JSON.
- ตาราง token usage ต่อ sub-agent.

## ข้อกำหนดผลลัพธ์
- `game.json` schema_version 2, base/title/header ครบ, `play.draw=10`, `default_time_limit_sec=20`, `max_points=1000`.
- 20 questions — ทุกข้อมี 4 choices (ก/ข/ค/ง), `correct=true` ข้อเดียวตรงกับ `answer`, มี `explanation` (สั้น).
- คำถาม/ตัวเลือกกระชับ ชัด ไม่กำกวมเมื่อจับเวลา. เฉลยตรงกับ `{BASE}_ex.json` เดิมทุกข้อ. ภาษาไทย สไตล์ OVEC.
