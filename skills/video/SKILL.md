---
name: video
description: สร้างวิดีโอสื่อการเรียนรู้ EDU ONE (สพฐ.) 2:30-3:00 นาที จากเนื้อหา C1 — lookup token → อ่าน srcpack → video-writer เขียน storyboard 9-12 ฉาก → video-checkwork ตรวจ → tts_render + video_assemble (STUB) → บันทึก. ใช้เมื่อผู้ใช้ขอ "ทำวิดีโอ/storyboard/video/mp4"
---

# SKILL: video — ผลิตวิดีโอสื่อการเรียนรู้

ออร์เคสเตรต Agent 5 สร้าง Style Guide + Storyboard 9–12 ฉาก (รวม 150–180 วินาที)
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
ได้ JSON keys: `video_json`, `video_mp4`, `video_audio_dir`, **`content_srcpack_md`** (source ที่ใช้จริง),
`content_c1_json`, `content_c1_docx` (สำรอง), `topic_dir`, `dirs{...}` ฯลฯ

### STEP 2 — อ่าน source pack (ไม่ต้องอ่าน C1 เต็ม)
**`content_srcpack_md`** (จาก `paths.py` = `1. Content/{BASE}_srcpack.md`) — ไฟล์ข้อความสั้น
อ่านด้วย `Read` ได้เลย มี OBJ/COMP · โครงหัวข้อ · ข้อเท็จจริงแกน · ศัพท์ร่วม · ตัวอย่างหลัก
(storyboard 9-12 ฉากใช้แกนของเรื่องเป็นหลัก ไม่ได้ลอกย่อหน้าจาก C1)

- ยังไม่มี srcpack → สร้างก่อน: `srcpack.py "<content_c1_json>" "<content_srcpack_md>"`
- srcpack ขึ้นว่า "ยังไม่มี digest" หรือฉากไหนต้องการรายละเอียดเพิ่ม → เปิด
  **`content_c1_json`** ด้วย `Read` (คีย์ `body[]`) หรือถ้ามีแต่ `.docx` ใช้
  `shared/scripts/read_docx_text.py "<content_c1_docx>"` (**ห้ามเขียน snippet `p.text` เอง** — สมการจะหาย)
- ไม่มีทั้งคู่ → แจ้งผู้ใช้และหยุด

### STEP 3 — เรียก video-writer
ส่ง: `base`, `header`, `lang`, `topic_name`, `obj[]`, `comp[]`, ระดับชั้น, เนื้อความจาก srcpack
(ย้ำให้ใช้ศัพท์ตามตารางศัพท์ให้ตรงกับสื่ออื่น)
video-writer ต้อง **อ่าน `${CLAUDE_PLUGIN_ROOT}/skills/video/reference/prompt-master-video.md` ก่อน** แล้วเขียนที่ key `video_json` (ใน `5. Video/`):
`video_json` = `.../<BASE>/5. Video/{BASE}_video.json`

### STEP 4 — video-checkwork loop (≤ 2 รอบ)
ตรวจ จำนวนฉาก 9–12 / รวมเวลา 150–180 วิ / ทุกฉากครบ / ภาษา / เหมาะระดับชั้น
- PASS → STEP 5
- FAIL → ส่งรายการแก้กลับ video-writer แก้ artifact แล้วตรวจซ้ำ (≤ 2 รอบ)

### STEP 5 — Render (STUB)
> 📄 ปลายทางจริง (HeyGen / TTS+ffmpeg) + พฤติกรรม `.PENDING` — ดู
> `${CLAUDE_PLUGIN_ROOT}/skills/shared/reference/external-services.md`
```bash
export PYTHONIOENCODING=utf-8
eduone-py tts_render.py <video_json> <video_audio_dir>
eduone-py video_assemble.py <video_json> <video_mp4>
```
(`<video_json>`, `<video_audio_dir>`, `<video_mp4>` = ค่าจาก `paths.py`; ไฟล์ narration อยู่ใน `5. Video/{BASE}_video_audio/`, mp4 อยู่ใน `5. Video/` ร่วมกับ json)
**STUB**: ยังไม่มี API/asset จริง จะเขียน `<out>.PENDING` placeholder

### STEP 6 — รายงาน
สรุป (ไทย): artifact `video_json` (`5. Video/`), media token `video_mp4` (`.../<BASE>/5. Video/{BASE}_video.mp4`, หรือ `.PENDING`), narration `video_audio_dir`, จำนวนฉาก/เวลารวม, ผลตรวจ checkwork
