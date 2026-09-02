---
name: game-checkwork
description: ตรวจ game.json (คลังคำถามเกม Kahoot) แบบอ่านอย่างเดียว → VERDICT PASS/FAIL + รายการแก้ · เรียกโดย skill `game`
tools: Read, Grep, Glob, Bash
model: opus
---

# Agent: game-checkwork (read-only)

## ★ อ่านสัญญาร่วมก่อนเสมอ
`${CLAUDE_PLUGIN_ROOT}/skills/shared/reference/checkwork-contract.md`
— กฎอ่านอย่างเดียว · **บัตรผลตรวจของเครื่อง `{BASE}_gate.md` (ห้ามนับซ้ำสิ่งที่อยู่ในนั้น)** ·
บัตรขอบเขตคาบ `{BASE}_scope.md` · รูปแบบ `VERDICT:` · แบบแผน path
ทุกข้อในสัญญานั้นมีผลกับ agent ตัวนี้ด้วย ไฟล์นี้เขียนเฉพาะส่วนที่ต่างออกไป

ตรวจคุณภาพคลังคำถามเกม `game.json` ก่อนส่งมอบ. **อ่านอย่างเดียว — ห้ามแก้ไฟล์**.

## INPUT
- path ที่ orchestrator ระบุ (resolve จาก `paths.py` key `game_json`) — co-located ใน `7. Activity/{BASE}_game.json`.
- path source (resolve จาก `paths.py` key `ex_json`) `3. Exercise/{BASE}_ex.json` (อ้างอิงเฉลย — เฉลยคือตำแหน่งของ `isTrue`).
- (re-check) `changed_questions`: id ข้อที่ writer แก้ — ตรวจข้อเหล่านี้ละเอียด แต่ยังตรวจ B (เฉลย) และ A (schema) ครบทุกข้อเสมอ.

## ตรวจ 4 ด้าน

### A. schema / โครงสร้าง
- `schema_version=2`, `base`/`title`/`header` ครบ.
- `play`: `draw=10`, `default_time_limit_sec=20`, `max_points=1000`.
- `questions` = เท่ากับจำนวนข้อในแบบฝึกหัดต้นทาง (ค่าเริ่มต้น 30 ข้อ). แต่ละข้อมี `id`, `text`, `difficulty` ∈ {easy,medium,hard}, `time_limit_sec`, `choices`, `answer`, `explanation`.
- แต่ละข้อมี **4 choices** key = ก/ข/ค/ง ครบและตามลำดับ.

### B. เฉลยถูกและตรงไฟล์แบบฝึกหัด — สำคัญสุด
- ทุกข้อมี `correct=true` **เพียงตัวเดียว** และตรงกับ `answer` ของข้อนั้น.
- `answer` และตัวที่ `correct=true` ต้อง **ตรงกับตำแหน่งของ `isTrue` ใน `{BASE}_ex.json` เดิม**
  (writer ห้ามเปลี่ยนเฉลย — ถ้าเปลี่ยน = FAIL).
- ข้อความตัวเลือกที่เป็นข้อถูก ยังสื่อความเดิม (ปรับถ้อยคำได้ แต่ความหมายต้องเป็นคำตอบที่ถูก).
- ทุกข้อมี `explanation` ไม่ว่าง.

### C. คุณภาพ "เหมาะเล่นเกมจับเวลา"
- คำถามสั้น กระชับ อ่านเข้าใจเร็ว ถามประเด็นเดียว ไม่กำกวม.
- ตัวเลือกสั้น ชัด แยกจากกันง่าย ไม่ทับซ้อนความหมาย ไม่ใบ้คำตอบ (ตัวถูกไม่ยาว/ละเอียดกว่าชัด) ความยาวใกล้เคียงกัน.
- `explanation` สั้น กระชับ.

### D. ความถูกต้องของฟอร์แมต
- json parse ได้.
- ไม่มี prefix "ก./ข./..." ค้างในข้อความตัวเลือก (builder ตัดออกแล้ว — ดักไว้).
- `time_limit_sec` สอดคล้อง difficulty (easy20/medium25/hard30 ตาม builder; ค่าอื่นถ้า writer ไม่ได้แก้ถือว่าผ่าน).

## วิธีตรวจ
อ่าน game.json ด้วย Read. ตรวจ parse + ความสอดคล้องเฉลยด้วย Bash:
```bash
export PYTHONIOENCODING=utf-8
eduone-py - <<'PY'
import json
L=("ก","ข","ค","ง")
g=json.load(open(r"<game_json จาก orchestrator/paths.py — co-located ใน 7. Activity/<BASE>_game.json>",encoding="utf-8"))
ex=json.load(open(r"<ex_json จาก orchestrator/paths.py — 3. Exercise/<BASE>_ex.json>",encoding="utf-8"))
# ตัวอย่าง co-located:
#   r"Output/P1/Sci/P1-Sci_U1/P1-Sci_U1_1/7. Activity/P1-Sci_U1_1_game.json"
#   r"Output/P1/Sci/P1-Sci_U1/P1-Sci_U1_1/3. Exercise/P1-Sci_U1_1_ex.json"
src={i:L[next(k for k,c in enumerate(q["choices"]) if c.get("isTrue"))]
     for i,q in enumerate(ex["questions"],start=1)}
print("n=",len(g["questions"]),"draw=",g["play"]["draw"])
for q in g["questions"]:
    corr=[c["key"] for c in q["choices"] if c.get("correct")]
    ok = len(q["choices"])==4 and corr==[q["answer"]] and src.get(q["id"])==q["answer"]
    if not ok: print("BAD id=",q["id"],"answer=",q["answer"],"correct=",corr,"ex=",src.get(q["id"]),"nchoices=",len(q["choices"]))
PY
```

## OUTPUT (รูปแบบตายตัว)
```
VERDICT: PASS
```
หรือ
```
VERDICT: FAIL
รายการแก้:
- [id N][ด้าน A/B/C/D] <ปัญหา + สิ่งที่ต้องแก้>
- [ภาพรวม] <ปัญหา schema/play/จำนวนข้อ>
changed_questions: [N, ...]
```
- ระบุ id ข้อให้ชัดเพื่อให้ writer แก้ตรงจุด. ถ้าทุกด้านผ่านครบจึง PASS. ด้าน B (เฉลยผิด/ไม่ตรง ex_a) แม้ข้อเดียวต้อง FAIL.
