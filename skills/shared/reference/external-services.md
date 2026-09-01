# External services — ปลายทาง render ของ agent 3 (Song) และ 5 (Video)

> ย้ายมาจาก `CLAUDE.md` — โหลดเฉพาะตอนทำงาน `/song` หรือ `/video`
> (ส่วนของ Slides ย้ายไป `.claude/skills/slides/reference/build-notes.md` เพราะ build ในเครื่องแล้ว)

## Song → ✅ wired กับ Suno (sunoapi.org)
`song/scripts/suno_render.py` (generate → poll → download)
- ต้องตั้ง env **`SUNO_API_KEY`** (Windows: `setx SUNO_API_KEY "xxxx"` แล้วเปิด terminal ใหม่;
  **ห้าม commit key**)
- optional `SUNO_API_BASE` / `SUNO_MODEL` (default `V4_5`) / `SUNO_CALLBACK_URL`
- ได้ `_song.mp3` + `_song_alt.mp3` + `_song.txt` (เนื้อเพลง)
- ไม่มี key → `.PENDING` · มี `--dry-run`

## Video → ⏸ ยังเป็น stub
`video/scripts/tts_render.py` + `video_assemble.py` (HeyGen หรือ TTS+ffmpeg) — เติมที่ `TODO`

## กฎร่วมของ stub
stub ที่ยังไม่ wired เขียน `<out>.PENDING` placeholder; เติม implementation จุดเดียวเมื่อมี key
