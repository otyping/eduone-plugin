# แผนที่ repo — ไฟล์อะไรอยู่ที่ไหน

> ย้ายมาจาก `CLAUDE.md` — อ่านเมื่อต้องหาสคริปต์/โมดูลที่ยังไม่รู้ path
> (path ของ **ผลผลิต** ไม่ต้องดูที่นี่ — เรียก `paths.py` เอา)

```
.claude/
  skills/
    edu-one/SKILL.md              # master orchestrator
    content/  lesson-plan/  exercise/  song/  slides/  video/  game/   # 7 skill
       SKILL.md  +  (song/slides/video/exercise) reference/prompt-master-*.md  +  scripts/<render stub>
       exercise/reference/  media-flow.md  (งานสื่อรูป/เสียงของข้อสอบ — flow เต็ม)
       slides/reference/     build-notes.md (ฟอนต์/overflow/รูปประกอบ/L1-L2 → สไลด์)
       slides/scripts/    build_slides_brief.py · fill_slides_images.py
                          (ใบสั่งผลิตรูปสไลด์ + เติม image_file อัตโนมัติ)
       exercise/scripts/  build_media_brief.py · fill_ex_urls.py · uvoice_render.py
                          · gen_math_images.py (ตัวหลัก) + โมดูล drawer: science_diagrams.py
                            · solid_views.py · plant_diagrams.py
    shared/
      scripts/  docx_common.py · read_docx_text.py (ดึงข้อความจาก .docx — ใช้ร่วมทุก skill)
                · no_to_token.py · paths.py · build_content.py
                · build_lesson_plan.py · build_exercise.py · verify_docx.py · MML2OMML.XSL
                · pptx_common.py · build_slides.py · verify_pptx.py · embed_fonts_pptx.py
                · slides_media.py (แบบแผนชื่อไฟล์รูปสไลด์ + clean_prompt)   [ทั้งหมดนี้ = สไลด์]
                · media_cache.py (โหลด/แคช/ย่อสื่อ) · migrate_ex.py (แปลงสคีมาเก่า)
                · bookscan_common.py · bookscan_index.py · bookscan_page.py
                · check_math.py (ตรวจสัญลักษณ์คณิต/วิทย์ก่อน build)
                · validate_spec.py (**gate ก่อน checkwork** — โควตาข้อสอบ/เวลาคาบ/หน้าปก
                  verbatim/คำต้องห้ามบนสไลด์ L1-L2/**สคีมา `digest` ของ C1**/frontmatter
                  ของ agent ด้วย `--agents`)
                · srcpack.py (ย่อ C1 → `{BASE}_srcpack.md` ~20% จากคีย์ `digest`
                  ให้แผนการสอน/เพลง/วิดีโอ อ่านแทน C1 เต็ม + ล็อกศัพท์ร่วมข้ามสื่อ)
      reference/  course-structure-<gradeSlug>-<subjectSlug>.md  (จาก xlsx) · grades.txt · subjects.txt
                  · thai-style-guide.md (กฎภาษาไทย 18 ข้อ — ใช้ร่วมทุก agent)
                  · math-symbols-guide.md (Equation/Symbol ใน Word — ใช้ร่วมทุก agent)
                  · naming-and-output.md (BASE token + โครงสร้าง Output)
                  · repo-map.md (ไฟล์นี้) · external-services.md · course-structures.md
      symbols.txt · fixture: course-structure-p1-sci.md (ตัวอย่างทดสอบ)
  agents/   # 16 ตัว (writer+checkwork ต่อ agent; content มี research+academic+narrative)
BookScan/   # 📚 หนังสือเรียน/คู่มือครู สสวท. (ภาพสแกน 795 MB, gitignored) — ดู BookScan/README.md
Slide Master Template/   # 🎨 เทมเพลตสไลด์ที่ผู้ใช้วางเอง แยกตาม (วิชา × ชั้นปี) — .pptx gitignored
   <Subject> <Grade>/Slide Master_<Subject>_<Grade>.pptx     เช่น `Sci P1/Slide Master_Sci_P1.pptx`
game-app/   # ✅ เกมแบบ Kahoot MVP (Node+Socket.IO, LAN) — node server.js → /host + /play
Simulation/ # ✅ เว็บซิมูเลชันอวัยวะ 3 มิติ ธีมห้องผ่าตัด (HTML+CSS+Vanilla JS+Three.js) — เปิด index.html ได้เลย
Output/     # ผลผลิตทั้งหมด — ต้นไม้เดียว (ดู naming-and-output.md)
```
