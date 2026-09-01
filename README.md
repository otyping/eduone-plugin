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

## ติดตั้งแบบง่าย — คัดลอกบรรทัดเดียว (Windows)

เปิด **PowerShell** แล้ววาง:

```powershell
irm https://raw.githubusercontent.com/otyping/eduone-plugin/main/install.ps1 | iex
```

ตัวช่วยจะ **ถามทีละขั้น** ว่าจะติดตั้งอะไร กด Enter หรือ `Y` เพื่อตกลง · `N` เพื่อข้าม
ไม่มีขั้นไหนติดตั้งอะไรโดยไม่ได้รับคำตอบ และ **รันซ้ำได้** ถ้าครั้งแรกยังไม่ครบ

```
== 1/5  Claude Code ==
  [ขาด]   ยังไม่มี Claude Code - เป็นตัวหลักที่ใช้ทำงาน ขาดไม่ได้
  ติดตั้ง Claude Code เลยไหม [Y=ตกลง / N=ข้าม]: y
== 2/5  Git for Windows ==
  [มีแล้ว] git version 2.51.0
== 3/5  Python 3.12 ==
  [ขาด]   ไม่พบ Python 3.12
  ติดตั้งด้วย winget ไหม [Y=ตกลง / N=ข้าม]: y
...
```

จบแล้วมันจะรันตัวตรวจให้เองและบอกว่าพร้อมหรือยัง

> อยากอ่านสคริปต์ก่อนรันก็ได้ — เปิดดูที่ [`install.ps1`](install.ps1) ในหน้า repo นี้

---

## ติดตั้งด้วยมือ (ถ้าไม่อยากใช้ตัวช่วย หรือใช้ macOS/Linux)

> ★ **ทำตามลำดับนี้** — `requirements.txt` มากับปลั๊กอิน จึงต้องติดตั้งปลั๊กอินก่อนถึงจะ pip ได้

### 1. Claude Code + subscription ของตัวเอง

ติดตั้ง Claude Code แล้วล็อกอินด้วยบัญชีที่บริษัทเบิกให้
งานทั้งหมดรันบนเครื่องคุณด้วย subscription ของคุณเอง — เซิร์ฟเวอร์ยืมไปใช้แทนไม่ได้

```bash
claude --version          # ต้องขึ้นเลขเวอร์ชัน
```

### 2. ติดตั้งปลั๊กอิน

```bash
claude plugin marketplace add otyping/eduone-plugin
claude plugin install edu-one@eduone
claude plugin list        # ต้องเห็น edu-one · enabled
```

### 3. Python 3.12 + แพ็กเกจ

ต้องเป็น **3.12** เท่านั้น (ผลผลิตเป็นไฟล์เอกสารที่รูปแบบต้องเหมือนกันทุกเครื่อง)

```bash
python --version
```

> Windows: ถ้า `python` เปิดหน้า Microsoft Store แปลว่า alias ชี้ผิด ให้ใช้ path เต็ม
> `%LOCALAPPDATA%\Programs\Python\Python312\python.exe`

ติดตั้งแพ็กเกจจาก `requirements.txt` ที่มากับปลั๊กอิน (ได้มาจากขั้นที่ 2 แล้ว):

**Windows (PowerShell)**
```powershell
$p = (Get-ChildItem "$env:USERPROFILE\.claude\plugins\cache\eduone\edu-one" -Directory | Select-Object -Last 1).FullName
pip install -r "$p
equirements.txt"
```

**macOS / Linux**
```bash
pip install -r "$(ls -d ~/.claude/plugins/cache/eduone/edu-one/*/ | tail -1)requirements.txt"
```

### 4. สร้างโฟลเดอร์งานของตัวเอง

ผลผลิตทั้งหมดจะลงที่นี่ **แยกจากตัวปลั๊กอิน** (ปลั๊กอินอ่านอย่างเดียว อัปเดตทับได้)

```bash
mkdir eduone-work && cd eduone-work
```

อยากวางไว้ที่อื่นให้ตั้ง `EDUONE_WORK_DIR` ชี้ไปที่นั่น

---

## ตรวจว่าติดตั้งครบด้วยคำสั่งเดียว

รันจาก**โฟลเดอร์งาน**ของคุณ:

**Windows (PowerShell)**
```powershell
$p = (Get-ChildItem "$env:USERPROFILE\.claude\plugins\cache\eduone\edu-one" -Directory | Select-Object -Last 1).FullName
python "$p\scripts\doctor.py"
```

**macOS / Linux**
```bash
python "$(ls -d ~/.claude/plugins/cache/eduone/edu-one/*/ | tail -1)scripts/doctor.py"
```

ตัวตรวจจะบอกทีละข้อว่าอะไรพร้อม อะไรขาด และ**ขาดแล้วต้องพิมพ์อะไรแก้** เช่น

```
== Python ==
  [ok]  Python 3.12.10
== แพ็กเกจที่ pipeline ต้องใช้ ==
  [ok]  python-docx
  [แก้] PyMuPDF — ยังไม่ได้ติดตั้ง
== ไฟล์ของปลั๊กอิน ==
  [ok]  sub-agent ครบ 16 ตัว
  [ok]  สกิลครบ 8 ตัว
  [ok]  หลักสูตรที่มี 4 คู่: m1-math p1-sci p4-english p4-sci
== โฟลเดอร์งาน ==
  [ok]  ผลผลิตจะลงที่ ...\eduone-work\Output
```

ขึ้น **"พร้อมใช้งาน"** เมื่อไร แปลว่าเรียบร้อย · สุดท้ายเปิด Claude Code ในโฟลเดอร์งาน
แล้วพิมพ์ `/` — ต้องเห็น `/edu-one` `/content` `/exercise` ครบ

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
claude plugin update edu-one@eduone
```

> ★ ต้องใส่ `@eduone` ต่อท้าย — ถ้าพิมพ์แค่ `claude plugin update edu-one`
> จะขึ้น `Plugin "edu-one" not found` (ทดสอบแล้วเจอจริง)

**ปิด Claude Code แล้วเปิดใหม่หนึ่งครั้ง** ให้ของใหม่มีผล (ตัวอัปเดตจะบอกว่า
"Restart to apply changes")

เช็คว่าอัปเดตติดจริง:

```bash
claude plugin list        # ดูเลข Version
```

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
