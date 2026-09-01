---
name: song
description: สร้างเพลงประกอบสื่อการเรียนรู้ EDU ONE (สพฐ.) จากเนื้อหา C1 — lookup token → อ่าน srcpack → song-writer เขียนเนื้อเพลง+style (≤60 วิ) → song-checkwork ตรวจ 7 STEP → suno_render → บันทึก artifact และ mp3. ใช้เมื่อผู้ใช้ขอ "ทำเพลง/แต่งเพลง/song" สำหรับ grade+subject+No ที่ระบุ
---

# SKILL: song — ผลิตเพลงประกอบสื่อการเรียนรู้

ออร์เคสเตรต Agent 3 เพื่อสร้างเพลงสั้น (≤ 60 วินาที) สำหรับหัวข้อการเรียนรู้หนึ่ง ๆ
**ภาษาเขียนทั้งหมด: ไทย** สรุปกระชับ สไตล์ OVEC

## INPUT
ต้องการ `grade_slug` (p1..p6, m1..m6), `subject_slug`, และ `No`
**ถ้าผู้ใช้ไม่ระบุครบ → ถามก่อน อย่าเดา**

## ขั้นตอน (ทำตามลำดับ)

### STEP 1 — Lookup token
```bash
export PYTHONIOENCODING=utf-8
"$LOCALAPPDATA/Programs/Python/Python312/python.exe" "${CLAUDE_PLUGIN_ROOT}/skills/shared/scripts/no_to_token.py" <gradeSlug> <subjectSlug> <No>
```
ได้ JSON: `grade, grade_slug, subject, subject_slug, period_minutes, lang, no, unit, unit_name, order, topic_name, obj[], comp[], base, header`
- เก็บค่า `base` (Title-case `<GradeToken>-<SubjectToken>_U<unit>_<order>` เช่น `P1-Sci_U1_1`), `grade_token`, `subject_token`, `topic_dir` และ `lang` ไว้ใช้ต่อ
- ถ้า lookup error → แจ้งผู้ใช้และหยุด
- เรียก `paths.py` เพื่อรับ path ที่แน่นอน (ห้ามต่อ path เอง):
```bash
export PYTHONIOENCODING=utf-8
"$LOCALAPPDATA/Programs/Python/Python312/python.exe" "${CLAUDE_PLUGIN_ROOT}/skills/shared/scripts/paths.py" <gradeSlug> <subjectSlug> <No>
```
ได้ JSON keys: `song_json`, `song_mp3`, **`content_srcpack_md`** (source ที่ใช้จริง),
`content_c1_json`, `content_c1_docx` (สำรอง), `topic_dir`, `dirs{...}` ฯลฯ

### STEP 2 — อ่าน source pack (ไม่ต้องอ่าน C1 เต็ม)
ไฟล์ INPUT: **`content_srcpack_md`** (จาก `paths.py` = `1. Content/{BASE}_srcpack.md`)
เป็นไฟล์ข้อความสั้น อ่านด้วย `Read` ได้เลย มี OBJ/COMP · โครงหัวข้อ · ข้อเท็จจริงแกน ·
ศัพท์ที่ต้องใช้ให้ตรงกับสื่ออื่น · ตัวอย่างหลัก

- **ยังไม่มี srcpack** (หัวข้อเก่า) → สร้างก่อน: `srcpack.py "<content_c1_json>" "<content_srcpack_md>"`
- srcpack ขึ้นว่า "ยังไม่มี digest" → ถอยไปอ่าน **`content_c1_json`** ด้วย `Read` (คีย์ `body[]`)
  หรือถ้ามีแต่ `.docx` ใช้ `shared/scripts/read_docx_text.py "<content_c1_docx>"`
  (**ห้ามเขียน snippet `p.text` เอง** — สมการจะหายทั้งไฟล์)
- ไม่มีทั้ง srcpack และ C1 → แจ้งผู้ใช้และหยุด

> เพลงยาว ≤ 60 วินาที ใช้แค่แกนของเรื่อง — การอ่าน C1 เต็ม 3-5 หน้าเพื่อเขียน 4 บรรทัด
> คือจ่ายค่า input ทิ้งเปล่า และทำให้ศัพท์ในเพลงเพี้ยนจากสื่ออื่นได้ด้วย

### STEP 3 — เรียก song-writer (sub-agent)
ส่งให้ song-writer: `base`, `header`, `lang`, `topic_name`, `obj[]`, `comp[]`, ระดับชั้น,
และ **เนื้อความจาก srcpack** (ย้ำให้ใช้ศัพท์ตามตารางศัพท์เป๊ะ ๆ เพื่อให้ตรงกับสื่ออื่น)
song-writer ต้อง **อ่าน `${CLAUDE_PLUGIN_ROOT}/skills/song/reference/prompt-master-music.md` ก่อน** แล้วเขียน artifact ที่ key `song_json` (ใน `6. Song/`):
`song_json` = `.../<BASE>/6. Song/{BASE}_song.json`  (รูปแบบ `{"lyrics":"...","style":"..."}`)

### STEP 4 — song-checkwork loop (≤ 2 รอบ)
เรียก song-checkwork (read-only) ตรวจตาม 7 STEP จาก master prompt
- ถ้า **PASS** → ไป STEP 5
- ถ้า **FAIL** → ส่งรายการแก้กลับให้ song-writer แก้ artifact แล้วตรวจซ้ำ
- ทำซ้ำได้ไม่เกิน 2 รอบ ถ้ายังไม่ผ่าน → รายงานปัญหาที่เหลือแต่ดำเนินต่อด้วยฉบับล่าสุด

### STEP 5 — Render เป็น mp3 ด้วย Suno (sunoapi.org)
> 📄 env key · optional flag · ไฟล์ที่ได้ · พฤติกรรมเมื่อไม่มี key — ดู
> `${CLAUDE_PLUGIN_ROOT}/skills/shared/reference/external-services.md`
```bash
export PYTHONIOENCODING=utf-8
# ต้องมี SUNO_API_KEY ใน env (อย่าเขียน key ลงไฟล์/commit)
"$LOCALAPPDATA/Programs/Python/Python312/python.exe" "${CLAUDE_PLUGIN_ROOT}/skills/song/scripts/suno_render.py" <song_json> <song_mp3>
```
(`<song_json>`, `<song_mp3>` = ค่าจาก `paths.py`; ผลลัพธ์อยู่ใน `6. Song/` ร่วมกับ json)
- เรียก `POST /api/v1/generate` → poll `record-info` จนสำเร็จ (~30–90 วิ, **ใช้เครดิต**) → ดาวน์โหลด mp3
- ได้ `{BASE}_song.mp3` (เพลงแรก) + `{BASE}_song_alt.mp3` (เพลงสำรอง) + **`{BASE}_song.txt` (เนื้อเพลงอ่านง่าย)**
- config env: `SUNO_API_KEY` (จำเป็น) · `SUNO_API_BASE` (default sunoapi.org) · `SUNO_MODEL` (default V4_5)
- **ถ้าไม่มี `SUNO_API_KEY`** → เขียน `<out>.PENDING` แทน (ไม่ error) แต่ยังได้ `.txt` เนื้อเพลง
- ตรวจ mapping ก่อนใช้เครดิตได้ด้วย `--dry-run` (พิมพ์ payload ไม่ยิงจริง)
- ถ้า error (เครดิตหมด/timeout/`SENSITIVE_WORD_ERROR`) → แจ้งผู้ใช้พร้อมข้อความจาก script

### STEP 6 — รายงาน
สรุปกระชับ (ไทย):
- artifact: `song_json` (`.../<BASE>/6. Song/{BASE}_song.json`) + `song_txt` (เนื้อเพลง)
- media token: `song_mp3` (`.../<BASE>/6. Song/{BASE}_song.mp3` + `_alt.mp3`, หรือ `.PENDING` ถ้าไม่มี key)
- ผลตรวจ checkwork (PASS/FAIL + ข้อที่แก้)
