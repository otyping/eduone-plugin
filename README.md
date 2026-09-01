# EDU ONE — ปลั๊กอินผลิตสื่อการเรียนการสอน สพฐ.

7 AI agents ที่ทำงานต่อกันเป็นสายพาน ผลิตสื่อครบชุดจาก **หัวข้อเดียว**

| ผลผลิต | คำสั่ง |
|---|---|
| เนื้อหา C1 เชิงวิชาการ + C2 เล่าเรื่อง | `/content` |
| แผนการสอน L1 เชิงสำรวจ + L2 ผ่านกิจกรรม | `/lesson-plan` |
| แบบฝึกหัด 20 ข้อ พร้อมเฉลยและวิธีคิด | `/exercise` |
| สไลด์ 4 ชุด (จาก C1/C2/L1/L2) | `/slides` |
| เพลง ≤ 60 วินาที | `/song` |
| วิดีโอ 2:30–3:00 นาที | `/video` |
| เกมตอบคำถามแบบ Kahoot | `/game` |
| **ทำครบทุกอย่างในคำสั่งเดียว** | `/edu-one` |

---

## ติดตั้ง (ครั้งเดียว ~15 นาที)

### 1. Claude Code + subscription ของตัวเอง

ติดตั้ง Claude Code แล้วล็อกอินด้วยบัญชีที่บริษัทเบิกให้
งานทั้งหมดรันบนเครื่องคุณด้วย subscription ของคุณเอง — เซิร์ฟเวอร์ยืมไปใช้แทนไม่ได้

### 2. Python 3.12 + แพ็กเกจ

```bash
python --version          # ต้องเป็น 3.12.x
pip install -r requirements.txt
```

> Windows: ถ้า `python` เปิดหน้า Microsoft Store แปลว่า alias ชี้ผิด
> ให้ใช้ path เต็มแทน — โดยปกติคือ `%LOCALAPPDATA%\Programs\Python\Python312\python.exe`

### 3. ติดตั้งปลั๊กอิน

```bash
claude plugin marketplace add otyping/eduone-plugin
claude plugin install edu-one@eduone
```

### 4. สร้างโฟลเดอร์งานของตัวเอง

ผลผลิตทั้งหมดจะลงที่นี่ **แยกจากตัวปลั๊กอิน** (ปลั๊กอินอ่านอย่างเดียว อัปเดตทับได้)

```bash
mkdir eduone-work && cd eduone-work
```

ถ้าอยากวางไว้ที่อื่น ตั้ง `EDUONE_WORK_DIR` ชี้ไปที่นั่น

---

## ตรวจว่าติดตั้งครบ

```bash
claude plugin list                                    # ต้องเห็น edu-one
python -c "import docx, pptx, fitz, pythainlp, lxml, numpy, yaml, PIL, matplotlib, latex2mathml"
```

แล้วเปิด Claude Code ในโฟลเดอร์งาน พิมพ์ `/` — ต้องเห็น `/edu-one` `/content` `/exercise` ครบ

อยากรู้ว่าปลั๊กอินกำลังอ่าน/เขียนที่ไหน:

```bash
python "$CLAUDE_PLUGIN_ROOT/skills/shared/scripts/_root.py"
```

---

## ใช้งาน

1. เปิด https://eduone.ovecaicenter.com → ดูใบสั่งงานของตัวเองบนกระดานงาน
2. เปิด Claude Code ในโฟลเดอร์งาน แล้วพิมพ์คำสั่งตามที่ใบสั่งบอก เช่น
   ```
   /edu-one ป.4 วิทย์ no.3
   ```
3. เสร็จแล้วส่ง artifact (`.json`) กลับขึ้นเว็บ พร้อมกรอกจำนวน token ที่ใช้

---

## อัปเดตเมื่อมีของใหม่

ปลั๊กอิน **ไม่อัปเดตเอง** ต้องสั่งเอง:

```bash
claude plugin marketplace update eduone
claude plugin update edu-one
```

ปิด Claude Code แล้วเปิดใหม่หนึ่งครั้งให้ของใหม่มีผล

---

## ที่เก็บของสองส่วน แยกหน้าที่กันชัด

```
~/.claude/plugins/.../edu-one/     ความฉลาด — จากมาสเตอร์ · อ่านอย่างเดียว · อัปเดตทับได้
   agents/    16 sub-agent (writer + checkwork)
   skills/    9 สกิล + shared/ (สคริปต์ 30 ไฟล์ + ข้อมูลหลักสูตร)

<โฟลเดอร์งานของคุณ>/               งาน — ของคุณเอง
   Output/    ผลผลิตทุกชิ้น
   BookScan/  หนังสือสแกน (ถ้ามี)
```

**อย่าแก้ไฟล์ในโฟลเดอร์ปลั๊กอิน** — การอัปเดตครั้งถัดไปจะทับทิ้ง
ถ้าเจอปัญหาหรืออยากให้ปรับ ให้แจ้งผู้ดูแลเพื่อแก้ที่ต้นทาง

### ตัวแปรที่ปรับได้

| ตัวแปร | ใช้ทำอะไร |
|---|---|
| `EDUONE_WORK_DIR` | ที่วาง `Output/` และ `BookScan/` (ไม่ตั้ง = เดินขึ้นหา `CLAUDE.md`/`Output`/`.git` จากที่อยู่ปัจจุบัน) |
| `EDUONE_REFERENCE_DIR` | ทับที่อยู่ข้อมูลหลักสูตร (ปกติไม่ต้องตั้ง) |
| `SUNO_API_KEY` | ทำเพลงจริง — ไม่มีก็ได้ไฟล์ `.PENDING` ไว้ render ทีหลัง |

---

## สำหรับทีมพัฒนา (R&D)

แก้ปลั๊กอินแล้วอยากลองก่อน publish:

```bash
claude --plugin-dir /path/to/eduone-plugin
```

ก่อน push ทุกครั้ง:

```bash
claude plugin validate . --strict
```
