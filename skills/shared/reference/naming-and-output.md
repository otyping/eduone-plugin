# ระบบชื่อไฟล์ (BASE token) + โครงสร้าง Output

> ย้ายมาจาก `CLAUDE.md` — **ปกติไม่ต้องอ่านไฟล์นี้** เพราะ `paths.py` คืน path ทุกผลผลิตให้ครบแล้ว
> อ่านเมื่อ: ต้องเข้าใจที่มาของชื่อ · ต้องเพิ่มผลผลิตชนิดใหม่ · debug ว่าทำไมไฟล์ไปโผล่ผิดที่

## BASE token
**slug ภายใน (lookup) ตัวเล็ก** `p1`,`sci` แต่ **path/ชื่อไฟล์ output เป็น Title-case**:
`GradeToken = grade_slug.upper()` (P1..M6) · `SubjectToken = subject_slug.capitalize()`
(Sci/Math/English/Social/Health/Art/Career/Thai)

**BASE = `<GradeToken>-<SubjectToken>_U<unit>_<order>`** เช่น `P1-Sci_U1_1`

## โครงสร้าง Output
ทุกผลผลิตของหัวข้อหนึ่งอยู่ใน **โฟลเดอร์เดียว** (ครูได้ครบจบในที่เดียว):
```
Output/<GradeToken>/<SubjectToken>/<GradeToken>-<SubjectToken>_U<unit>/<BASE>/
   1. Content/      {BASE}_C1.json + _C1.docx · {BASE}_C2.json + _C2.docx
                    + {BASE}_research.md (แหล่งอ้างอิงจาก content-research — track git)
                    + {BASE}_srcpack.md   (ย่อจาก digest ของ C1 ด้วย srcpack.py)
   2. LessonPlan/   {BASE}_L1.json + _L1.docx · {BASE}_L2.json + _L2.docx
   3. Exercise/     {BASE}_ex.json (ไฟล์เดียว: โจทย์+เฉลย+วิธีคิด+สื่อ) + {BASE}_ex.docx
                    + (ถ้ามีสื่อ) {BASE}_media-brief.md · {BASE}_audio-src.json · {BASE}_urls.txt
   4. Slides/       {BASE}_slides_{C1,C2,L1,L2}.json + .pptx
                    + (ถ้ามีรูป) {BASE}_slides_<src>_media-brief.md · {BASE}_slides_<src>_media/
   5. Video/        {BASE}_video.json + _video.mp4(.PENDING) + {BASE}_video_audio/
   6. Song/         {BASE}_song.json + _song.mp3(.PENDING)
   7. Activity/     {BASE}_game.json   (อ่าน {BASE}_ex.json จาก 3. Exercise/)
```
- **spec JSON วางคู่กับไฟล์ render** ในแต่ละ product folder (เช่น `1. Content/` มีทั้ง `_C1.json` + `_C1.docx`)
- ป้ายโฟลเดอร์ผลผลิต **ตายตัว** "1. Content"…"7. Activity"
  (ลำดับแสดงผล ไม่ใช่เลข agent: Exercise=3, Song=6, game→7. Activity)
- โฟลเดอร์หน่วยคั่น `<GradeToken>-<SubjectToken>_U<unit>` (เช่น `P1-Sci_U1`)

## API ที่ต้องใช้แทนการต่อ path เอง
**ห้าม hard-code path เอง** — เรียก `paths.py <gradeSlug> <subjectSlug> <No>` ได้ path ทุกผลผลิตครบ
keys: `content_c1_json/_docx`, `content_srcpack_md`, `plan_l1_json/_docx`, `exercise_docx`, `ex_json`,
`ex_media_dir`, `ex_brief_md`, `ex_audio_src_json`, `ex_urls_txt`, `slides_json{...}`,
`video_json/_mp4`, `song_json/_mp3`, `game_json`, `topic_dir`, `dirs{...}`
\+ `ensure_dirs()` สร้างโฟลเดอร์ให้

`no_to_token.py` คืน metadata + `base`/`grade_token`/`subject_token`/`unit_folder`/`topic_dir`

**ระดับบท/หน่วย**: `paths.py <g> <s> <No> --unit` → `unit_paths()` ให้ไฟล์ที่โฟลเดอร์หน่วย
