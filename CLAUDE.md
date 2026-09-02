# CLAUDE.md — repo ปลั๊กอิน EDU ONE

repo นี้คือ **ความฉลาด** ของระบบ EDU ONE — สกิล 8 ตัว · agent 16 ตัว · สคริปต์ pipeline
ส่วน **งาน** (Output/ · BookScan/ · webapp/) อยู่คนละ repo คือ `otyping/EDUONE-MCP-RAG`

> ไฟล์นี้เคยมีอยู่แค่ใน repo งาน ทำให้คนที่ clone ปลั๊กอินเดี่ยว ๆ ไม่เห็นกฎเลย
> โดยเฉพาะข้อ 8 เรื่องโมเดล — จึงคัดข้อที่ผูกกับ repo นี้มาไว้ที่นี่ด้วย

## 🔒 นโยบายโมเดล (ห้ามเปลี่ยนเอง)

agent ทุกตัว (writer + checkwork ทั้ง 16) ใช้ **`model: opus`** เป็นมาตรฐาน
**ห้ามเปลี่ยน `model:` ของ agent ใด ๆ เป็น sonnet/haiku/อื่น จนกว่า manager `otyping`
(เจ้าของ repo บน GitHub) จะแจ้งให้เปลี่ยน** เท่านั้น

มีประตูตรวจให้แล้ว — `validate_spec.py --agents` FAIL ทันทีถ้ามีตัวไหนไม่ใช่ opus

เหตุผลจากตัวเลขจริง (วัด 1 คาบเต็ม): checkwork ที่ดู "งานเบา" ทั้งสองตัว
(song $0.72 · video $1.40) รวมกันแค่ **0.7% ของค่าใช้จ่าย** ต่อให้ลดเป็น Haiku
ก็ได้คืน ~$1.70 ต่อคาบ เทียบกับการเริ่มงานในเซสชันใหม่ที่ได้คืน $80–100
**คันโยกที่เสี่ยงที่สุดกลับให้ผลน้อยที่สุด** และ checkwork เชิงวิจารณญาณจับของเสียได้
5 ครั้งในรอบนั้น ซึ่ง **ทุกครั้งผ่าน `validate_spec` มาก่อนแล้ว**

## ★ นิยามที่ห้ามตีความใหม่

| ตัวย่อ | ระดับ | คอลัมน์ใน xlsx หลักสูตร | ความหมาย |
|---|---|---|---|
| `OBJ` | **หน่วย** | E `จุดประสงค์ประจำหน่วย` | เป้าของทั้งหน่วยซึ่งกินหลายคาบ |
| `IND` | **หน่วย** | F `ตัวชี้วัด` | รหัสตัวชี้วัดแกนกลาง เช่น `ค 1.1 ม.1/1` |
| `COMP` | **คาบ** | I `สาระสำคัญ / จุดประสงค์ประจำคาบ` | **สิ่งที่นักเรียนได้เมื่อจบคาบนั้น** |
| `OUTCOME` | หน่วย | — ไม่มีในหลักสูตร | ผลลัพธ์ที่ทีมเขียนเสริมเอง ใช้เป็นตัวสำรองเมื่อยังไม่มี COMP รายคาบ |

**ผลผลิตของคาบเดียวไม่ต้องรับ OBJ ครบทั้งหน่วย** — ต้องส่งมอบ COMP ของคาบครบ 100%
และมีส่วนช่วย OBJ ตามที่ `POBJ` ระบุเท่านั้น การเข้าใจผิดข้อนี้เคยทำให้ต้องเขียน C1
ใหม่ทั้งฉบับมาแล้ว

## ข้อบังคับที่ผูกกับ repo นี้

1. **Python 3.12** ที่ `%LOCALAPPDATA%\Programs\Python\Python312\python.exe`
   (มี `python-docx`, `python-pptx`, `pythainlp`, `Pillow`, `matplotlib`, `PyMuPDF`,
   `pywin32`, `latex2mathml`; **ไม่มี `requests`** ใช้ `urllib`)
   อย่าเรียก `python`/`python3` เปล่า · เรียกผ่าน `bin/eduone-py` จะหาให้เองทุก OS
   · ตั้ง `PYTHONIOENCODING=utf-8` ก่อนรันเสมอ
2. **ห้าม hard-code path** — `paths.py` และ `no_to_token.py` เป็นแหล่งเดียวของ path
   และ metadata ทั้งหมด
3. **writer เขียน JSON เท่านั้น** ห้ามเขียน XML/docx เอง · build/verify เป็นงานของสคริปต์
4. **แก้ที่ repo นี้แล้วออกเวอร์ชันใหม่** — แก้ในโฟลเดอร์ `~/.claude/plugins/` โดยตรงไม่ได้
   เพราะการอัปเดตครั้งถัดไปจะทับทิ้ง · ตอนพัฒนาใช้ `claude --plugin-dir ../eduone-plugin`

## ก่อน commit

```bash
export PYTHONIOENCODING=utf-8
eduone-py ../eduone-plugin/skills/shared/scripts/validate_spec.py --agents
python scripts/smoke.py     # โครง pipeline ต่อกันติด (ไม่เรียก agent จริง)
python scripts/doctor.py    # สภาพแวดล้อมครบ
```

## แผนที่ไฟล์

| อยากรู้เรื่อง | อ่าน |
|---|---|
| นิยาม OBJ/IND/COMP/OUTCOME · รูปแบบไฟล์หลักสูตร · วิธีเพิ่มวิชา | `skills/shared/reference/course-structures.md` |
| สัญญาร่วมของ checkwork ทั้ง 7 ตัว | `skills/shared/reference/checkwork-contract.md` |
| ชื่อทางการของทักษะ 8C | `skills/shared/reference/skills-8c.txt` |
| หาสคริปต์/โมดูลไม่เจอ | `skills/shared/reference/repo-map.md` |
| กฎภาษาไทย 18 ข้อ | `skills/shared/reference/thai-style-guide.md` |
| สูตร/สัญลักษณ์คณิต — อันไหนเป็น Equation อันไหนเป็นข้อความ | `skills/shared/scripts/math_policy.py` |
