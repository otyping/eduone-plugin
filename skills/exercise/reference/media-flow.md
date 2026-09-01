# แบบฝึกหัดที่มีสื่อ (รูป/เสียง) — flow ที่ต้องรู้

> ย้ายมาจาก `CLAUDE.md` เพื่อให้โหลดเฉพาะตอนทำงาน `/exercise` — เนื้อหาคงเดิมทุกตัวอักษร
> **อ่านไฟล์นี้เมื่อ**: ข้อสอบมีรูปหรือเสียง · ต้องออกใบสั่งผลิตสื่อ · ต้องเติม URL · ต้องวาดรูปเอง

`{BASE}_ex.json` เป็นไฟล์เดียวรูปแบบ `{ questions: [{ text, imageUrl, audioUrl, imageAlt, audioText,
choices: [{ contentType, content, isTrue }], difficulty, solutionSteps }] }`
- **`content` ห้ามมี prefix ก./ข./ค./ง.** — ตัวอักษรมาจากลำดับ array · เฉลยอยู่ที่ `isTrue` (ไม่มี field `answer`)
- **URL ปล่อยว่าง `""` ตอน writer เขียน** → `build_media_brief.py` ออกใบสั่งผลิต → ผู้ใช้ผลิต+อัปโหลด
  → ส่งรายการ URL กลับ → `fill_ex_urls.py` เติมให้อัตโนมัติ (จับคู่ด้วยชื่อไฟล์ `{BASE}_{NN}_{Q|A1-A4}.<ext>`)

## 🔒 ปลายทางผลิตสื่อ (ผู้ใช้กำหนด — ห้ามใช้เจ้าอื่น/TTS ในเครื่อง)

### เสียง → Uvoice
`exercise/scripts/uvoice_render.py` ✅ wired จริง (ยิง `{BASE}_audio-src.json`
เข้า `api.uvoice.ai/generate` แบบ synchronous ได้ไฟล์เสียงกลับมาเลย ไม่ต้อง poll)
ต้องตั้ง env **`UVOICE_API_KEY`** · optional `UVOICE_VOICE_ID` (default `EN-JennySD`)
- **วิชาภาษาอังกฤษต้องใช้เสียงชั้น `Standard`** (displayName เป็นชื่อฝรั่ง = เอนจินเจ้าของภาษา)
  ชั้น Natural/Premium เป็นโมเดลเสียงไทยอ่านอังกฤษ ติดสำเนียง ไม่เหมาะกับข้อสอบฟัง
- ดูรายชื่อ: `uvoice_render.py --list-voices --lang en --type Standard`
- ลิมิต text ขั้นต่ำ 5 ตัวอักษร → สคริปต์เติม `{b250}` ให้อัตโนมัติ (ได้แค่ความเงียบท้ายคลิป)
- จบงานจะ **ปรับความยาวคลิปตัวเลือกของข้อเดียวกันให้เท่ากัน** ด้วยการเติมความเงียบ (กันเดาคำตอบ)

### รูป → Google Nano Banana
ด้วย **prompt ภาษาอังกฤษ** ใน `{BASE}_image-prompts.json`
(track git · `build_media_brief.py` หยิบไปใส่ใบสั่งผลิตเป็นบล็อกคัดลอกได้เลย พร้อมพับคำบรรยายไทยไว้ตรวจ)
**`imageAlt` ใน `_ex.json` ยังเป็นภาษาไทยเหมือนเดิม** เพราะเป็นข้อความที่ครูอ่านใน .docx
ตอนนี้ผู้ใช้ก๊อป prompt ไปทำเอง — ถ้าซื้อ Google API แล้วค่อยทำ adapter ส่งอัตโนมัติ

## รูปคณิต/สถิติวาดเองได้ ไม่ต้องรอผู้ใช้
`exercise/scripts/gen_math_images.py` (ฟอนต์ TH Sarabun New) ขับด้วย spec `{BASE}_images.json`

- **Pillow** (สไตล์หนังสือเรียน): `plane` ระนาบพิกัด/กราฟเส้น/กราฟจุด · `triangle` · `rectangle`
- **matplotlib**: `numberline` · `function` · `bar` (แท่งคู่+hatch) · `pie` (+เส้นชี้ป้าย) · `histogram`
  · `linechart` · `scatter` · `pictograph` แผนภูมิรูปภาพ · **`construction` รูปการสร้างทางเรขาคณิต**
  (รังสี · ส่วนโค้งวงเวียน · เส้นประ · เครื่องหมายมุม → แบ่งครึ่งมุม/สร้างมุม 60°/คัดลอกส่วนของเส้นตรง)
- **วิทยาศาสตร์** (`science_diagrams.py` เรียกผ่านคำสั่งเดียวกัน): `circuit` วงจรไฟฟ้าอนุกรม/ขนาน ·
  `forces` แผนภาพแรง · `atom` แบบจำลองอะตอมโบร์ · `solid3d` รูปทรง 3 มิติ (เส้นบัง=เส้นประ) · `flow` ห่วงโซ่/วัฏจักร
- **สองมิติ–สามมิติ** (`solid_views.py` เรียกผ่านคำสั่งเดียวกัน): `cubestack` กองลูกบาศก์ภาพฉายเฉียง
  (`cubes` = `[x,y,z]` · `arrows` กำกับด้านหน้า/ด้านข้าง/ด้านบน) · `views2d` ภาพจากการมองเป็นตารางช่อง
  (`cells` = `[row,col]` row 0 = ล่างสุด · `panels` หลายภาพในกรอบเดียว · **`canvas` ล็อกมาตราส่วนให้ตัวเลือกทุกใบเท่ากัน**)
  · `section` รูปทรงถูกระนาบตัด (`shape` cuboid/prism3/cylinder/cone/pyramid/sphere × `cut` horizontal/vertical/oblique)
- **ชีววิทยา–พืชดอก** (`plant_diagrams.py` เรียกผ่านคำสั่งเดียวกัน): `plantwhole` ต้นพืชทั้งต้น ·
  `flowersection` ดอกผ่าตามยาว (กลีบเลี้ยง/กลีบดอก/เกสรเพศผู้/เกสรเพศเมีย+รังไข่+ออวุล) ·
  `dyestem` กิ่งพืชแช่น้ำสีให้เห็นท่อลำเลียง · `photosynthesis` แผนภาพสังเคราะห์ด้วยแสง ·
  `leafstarch` ใบทดสอบแป้งด้วยไอโอดีน (`cover` แถบกระดาษดำ × `stain` none/all/outside/inside)
  — `plantwhole`/`flowersection` ใส่ป้ายด้วย `labels` (**ใช้เลข 1-4 ไม่ใช่ ก-ง** กันสับสนกับตัวอักษรของตัวเลือก)
  หรือ `showNames: true` เพื่อขึ้นชื่อไทย · ทุกชนิดล็อกกรอบภาพ ตัวเลือกที่เป็นรูปจึงมาตราส่วนเท่ากันเอง
- ดูตัวอย่างครบทุกชนิด: `gen_math_images.py ${CLAUDE_PLUGIN_ROOT}/skills/exercise/reference/sample-images.json --out-dir tmp/sample-images`
- **ป้ายในรูปห้ามใช้ตัวห้อย/ตัวยกยูนิโคด** (₁ ²) — ฟอนต์ TH Sarabun New ไม่มี glyph ใช้ `L1` `cm3` แทน

> ⚠️ **ชื่อ drawer ไม่ใช่คำอธิบายเนื้อหาวิชา** — `dyestem` เขียนว่า "กิ่งพืช" แต่การทดลองจริงในหนังสือ
> คือ **"แช่รากและลำต้นของต้นเทียน"** เคยมีเคสที่หยิบคำจากบรรทัดนี้ไปใส่ prompt แล้วผิดลงผลผลิต 2 ชิ้น
> **ยึดถ้อยคำจาก srcpack/C1/หนังสือเสมอ ไม่ใช่จากตารางนี้**

ไฟล์ออกที่ `{BASE}_media/` แล้ว `build_exercise.py` **หยิบไปฝัง .docx เองอัตโนมัติ** แม้ `imageUrl` ยังว่าง
- spec เป็น source of truth (track git) · PNG regenerate ได้ (gitignored)
- ที่วาดไม่ได้: ภาพถ่ายจริง · การ์ตูน · แผนภาพวิทย์ที่ยังไม่มี drawer · แผนที่ · ภาพหน้าจอ (ใช้ใบสั่งผลิตตามเดิม)
- **ต้องการแผนภาพวิทย์ชนิดใหม่ ให้เพิ่ม drawer ในโมดูลข้างต้นก่อน** แล้วค่อยออกใบสั่งผลิตถ้าวาดไม่ไหวจริง

## กฎ build / verify ของข้อสอบ
- **.docx เป็นฉบับผู้ตรวจ**: ฝังรูปอัตโนมัติ · บทเสียง = ข้อความ**สีน้ำเงิน** · ตัวเลือกที่ถูก = **สีแดง** · หน้าเฉลยมี "วิธีคิด:"
- `build_exercise.py` ต้องส่ง `--header` (สคีมาใหม่ไม่เก็บ header ใน JSON) — `verify_docx.py exercise` ก็รับ `--header`
  · `--expect N` เตือนถ้าจำนวนข้อไม่ตรง (ไม่ระบุ = ไม่ตรวจ)
- **จำนวนข้อยืดหยุ่น** สัดส่วนความยาก 50/25/25 — 20 ข้อ = 10/5/5 · 30 ข้อ = 15/8/7 · 40 ข้อ = 20/10/10
- **ข้อสอบระดับบท/หน่วย** ใช้ `paths.py <g> <s> <No> --unit` → `unit_paths()` ให้ไฟล์ที่โฟลเดอร์หน่วย
  เช่น `Output/M1/Math/M1-Math_U4/3. Exercise/M1-Math_U4_ex.json` (ครอบคลุมทุกหัวข้อย่อยในบท)
