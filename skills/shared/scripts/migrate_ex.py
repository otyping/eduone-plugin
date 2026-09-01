# -*- coding: utf-8 -*-
"""
migrate_ex.py — แปลงแบบฝึกหัดสคีมาเก่า (2 ไฟล์) เป็นสคีมาใหม่ (ไฟล์เดียว)

เก่า: {BASE}_ex_q.json  { header, title, quiz:[{question,choices:["ก. ..",..],answer:"ข",difficulty}], validation }
      {BASE}_ex_a.json  { no, answers:[{question:1, answer:"ข", solution_steps:".."}] }

ใหม่: {BASE}_ex.json    { questions:[{ text, imageUrl, audioUrl, imageAlt, audioText,
                                       choices:[{contentType,content,isTrue}],
                                       difficulty, solutionSteps }] }

การแปลง
- ตัด prefix "ก. " / "ข." / "a." / "A)" ฯลฯ ออกจากข้อความตัวเลือก (ตัวอักษรมาจากลำดับ array)
- answer "ข" -> isTrue = true ที่ index 1
- solution_steps จาก ex_a (จับคู่ด้วยเลขข้อ) -> solutionSteps
- ช่องสื่อทั้งหมดตั้งเป็น "" (ข้อสอบเก่าเป็นข้อความล้วน)

ใช้:
  migrate_ex.py <โฟลเดอร์ 3. Exercise>        # หาไฟล์ _ex_q/_ex_a เอง
  migrate_ex.py <ex_q.json> <ex_a.json> <out_ex.json>
  เพิ่ม --delete-old เพื่อลบไฟล์เก่าหลังแปลงสำเร็จ

รันผ่านตัวห่อ: eduone-py <ชื่อไฟล์นี้> <args>  (หา Python 3.12 ให้เองทุก OS)
"""
import argparse
import glob
import json
import os
import re
import sys

THAI_LETTERS = ("ก", "ข", "ค", "ง")
# prefix ตัวเลือกที่ต้องตัดทิ้ง: ก. ข) A. a) 1. (ก) ฯลฯ
_PREFIX_RE = re.compile(r"^\s*[\(\[]?\s*(?:[ก-ฮ]|[A-Za-z]|\d{1,2})\s*[\)\].:、]\s*")


def strip_choice_prefix(text):
    """ตัดชื่อตัวเลือกนำหน้าออก — ทำครั้งเดียวพอ (กันตัดเนื้อหาจริงที่ขึ้นต้นด้วยเลข)"""
    return _PREFIX_RE.sub("", (text or "").strip(), count=1).strip()


def convert(exq, exa):
    quiz = exq.get("quiz")
    if not isinstance(quiz, list) or not quiz:
        raise ValueError("ex_q.json ไม่มีคีย์ 'quiz' ที่เป็น list")

    steps_by_no = {}
    for a in (exa or {}).get("answers", []) or []:
        try:
            steps_by_no[int(a.get("question"))] = (a.get("solution_steps") or "").strip()
        except (TypeError, ValueError):
            continue

    problems = []
    questions = []
    for idx, item in enumerate(quiz, start=1):
        answer = (item.get("answer") or "").strip()
        if answer not in THAI_LETTERS:
            problems.append("ข้อ %d: answer '%s' ไม่อยู่ใน ก/ข/ค/ง" % (idx, answer))
        correct = THAI_LETTERS.index(answer) if answer in THAI_LETTERS else -1

        raw_choices = item.get("choices") or []
        if len(raw_choices) != 4:
            problems.append("ข้อ %d: มี %d ตัวเลือก (คาดหวัง 4)" % (idx, len(raw_choices)))

        choices = []
        for ci, raw in enumerate(raw_choices):
            content = strip_choice_prefix(raw)
            if not content:
                problems.append("ข้อ %d ตัวเลือกที่ %d: ว่างหลังตัด prefix" % (idx, ci + 1))
            choices.append({
                "contentType": "text",
                "content": content,
                "isTrue": ci == correct,
            })

        steps = steps_by_no.get(idx, "")
        if not steps:
            problems.append("ข้อ %d: ไม่มี solution_steps ใน ex_a.json" % idx)

        # ตรวจว่า ex_a เห็นตรงกับ ex_q
        a_ans = next((a.get("answer") for a in (exa or {}).get("answers", []) or []
                      if str(a.get("question")) == str(idx)), None)
        if a_ans and a_ans.strip() != answer:
            problems.append("ข้อ %d: เฉลยไม่ตรงกัน ex_q='%s' ex_a='%s'" % (idx, answer, a_ans))

        questions.append({
            "text": (item.get("question") or "").strip(),
            "imageUrl": "",
            "audioUrl": "",
            "imageAlt": "",
            "audioText": "",
            "choices": choices,
            "difficulty": (item.get("difficulty") or "easy").strip(),
            "solutionSteps": steps,
        })

    return {"questions": questions}, problems


def find_pair(folder):
    q = glob.glob(os.path.join(folder, "*_ex_q.json"))
    a = glob.glob(os.path.join(folder, "*_ex_a.json"))
    if not q:
        raise FileNotFoundError("ไม่พบ *_ex_q.json ใน %s" % folder)
    exq = q[0]
    exa = a[0] if a else None
    out = exq[: -len("_ex_q.json")] + "_ex.json"
    return exq, exa, out


def main():
    ap = argparse.ArgumentParser(description="แปลงแบบฝึกหัด 2 ไฟล์ -> ไฟล์เดียว")
    ap.add_argument("args", nargs="+")
    ap.add_argument("--delete-old", action="store_true", help="ลบ _ex_q/_ex_a หลังแปลงสำเร็จ")
    ns = ap.parse_args()

    if len(ns.args) == 1:
        exq_path, exa_path, out_path = find_pair(ns.args[0])
    elif len(ns.args) == 3:
        exq_path, exa_path, out_path = ns.args
    else:
        print("ใช้: migrate_ex.py <folder> | <ex_q.json> <ex_a.json> <out.json>", file=sys.stderr)
        return 2

    with open(exq_path, "r", encoding="utf-8-sig") as f:
        exq = json.load(f)
    exa = None
    if exa_path and os.path.exists(exa_path):
        with open(exa_path, "r", encoding="utf-8-sig") as f:
            exa = json.load(f)

    data, problems = convert(exq, exa)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("เขียน %s (%d ข้อ)" % (out_path, len(data["questions"])))
    if exq.get("header"):
        print("header เดิม (ส่งให้ build_exercise --header): %s" % exq["header"])
    for p in problems:
        print("WARN: %s" % p, file=sys.stderr)

    if ns.delete_old and not problems:
        for old in (exq_path, exa_path):
            if old and os.path.exists(old):
                os.remove(old)
                print("ลบ %s" % old)
    elif ns.delete_old:
        print("ไม่ลบไฟล์เก่า เพราะยังมีปัญหาค้างอยู่ %d รายการ" % len(problems), file=sys.stderr)

    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
