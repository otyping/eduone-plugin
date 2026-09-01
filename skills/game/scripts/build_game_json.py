# -*- coding: utf-8 -*-
"""
build_game_json.py — แปลงแบบฝึกหัด {BASE}_ex.json (ไฟล์เดียว) -> game.json
รูปแบบคลังคำถามสำหรับเกมตอบคำถามแบบ Kahoot (host สร้างห้อง, นักเรียน join, สุ่ม 10 ข้อ)

ใช้งาน:
    python build_game_json.py <ex.json> <game.json> [--base BASE] [--header HEADER] [--title TITLE]

อินพุต {BASE}_ex.json:
{ "questions": [ { text, imageUrl, audioUrl, imageAlt, audioText,
                   choices: [ { contentType, content, isTrue, alt } ],
                   difficulty, solutionSteps } ] }
- ตัวอักษร ก/ข/ค/ง มาจาก **ลำดับใน array** (content ไม่มี prefix แล้ว)
- คำตอบถูกมาจาก isTrue (ไม่มีฟิลด์ answer ในไฟล์ต้นทาง)

schema ผลลัพธ์ game.json (คงเดิม + เพิ่มฟิลด์สื่อ):
{
  "schema_version": 2,
  "base": "P1-Sci_U1_1",
  "title": "เรื่อง...",
  "header": "ระดับชั้น... > วิชา... > เรื่อง...",
  "play": {"draw": 10, "default_time_limit_sec": 20, "max_points": 1000},
  "questions": [
    {"id": 1, "text": "...", "difficulty": "easy", "time_limit_sec": 20,
     "image_url": "", "audio_url": "",
     "choices": [{"key": "ก", "text": "...", "content_type": "text",
                  "media_url": "", "correct": true}, ...],
     "answer": "ก", "explanation": "..."}
  ]
}
- เกมจะสุ่ม play.draw (=10) ข้อจาก questions ทั้งหมด (20) ตอนเล่นจริง
- คะแนนคิดตามความถูก + ความเร็ว (สูงสุด max_points/ข้อ) — logic อยู่ที่ game-app
- ฟิลด์สื่อ (image_url/audio_url/content_type/media_url) game-app ยังไม่ใช้ เก็บไว้ให้ Stage 2
"""
import json
import os
import sys

CHOICE_KEYS = ("ก", "ข", "ค", "ง")
TIME_BY_DIFFICULTY = {"easy": 20, "medium": 25, "hard": 30}


def build(ex, base, header, title):
    questions_in = ex.get("questions")
    if not isinstance(questions_in, list) or not questions_in:
        raise ValueError("ex.json ต้องมีคีย์ 'questions' เป็น list ที่ไม่ว่าง")

    problems = []
    questions = []
    for i, item in enumerate(questions_in, start=1):
        raw_choices = item.get("choices") or []
        if len(raw_choices) != len(CHOICE_KEYS):
            problems.append("ข้อ %d: มี %d ตัวเลือก (คาดหวัง 4)" % (i, len(raw_choices)))

        correct_idx = -1
        n_true = 0
        for ci, c in enumerate(raw_choices):
            if c.get("isTrue"):
                n_true += 1
                if correct_idx < 0:
                    correct_idx = ci
        if n_true != 1:
            problems.append("ข้อ %d: มีตัวเลือก isTrue = true %d ตัว (ต้องมี 1)" % (i, n_true))

        diff = (item.get("difficulty") or "easy").strip()
        choices = []
        for ci, key in enumerate(CHOICE_KEYS):
            src = raw_choices[ci] if ci < len(raw_choices) else {}
            ctype = (src.get("contentType") or "text").strip()
            content = (src.get("content") or "").strip()
            # ตัวเลือกที่เป็นสื่อ: content = URL, ข้อความที่โชว์คือคำบรรยาย (alt)
            is_media = ctype in ("image", "audio")
            choices.append({
                "key": key,
                "text": (src.get("alt") or "").strip() if is_media else content,
                "content_type": ctype,
                "media_url": content if is_media else "",
                "correct": ci == correct_idx,
            })

        questions.append({
            "id": i,
            "text": (item.get("text") or "").strip(),
            "difficulty": diff,
            "time_limit_sec": TIME_BY_DIFFICULTY.get(diff, 20),
            "image_url": (item.get("imageUrl") or "").strip(),
            "audio_url": (item.get("audioUrl") or "").strip(),
            "choices": choices,
            "answer": CHOICE_KEYS[correct_idx] if 0 <= correct_idx < len(CHOICE_KEYS) else "",
            "explanation": (item.get("solutionSteps") or "").strip(),
        })

    game = {
        "schema_version": 2,
        "base": base or "",
        "title": title or "",
        "header": header or "",
        "play": {"draw": 10, "default_time_limit_sec": 20, "max_points": 1000},
        "questions": questions,
    }
    return game, problems


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print("usage: build_game_json.py <ex.json> <game.json> "
              "[--base B] [--header H] [--title T]", file=sys.stderr)
        return 2
    ex_path, out_path = args[0], args[1]
    base = header = title = None
    i = 2
    while i < len(args):
        if args[i] == "--base" and i + 1 < len(args):
            base = args[i + 1]; i += 2
        elif args[i] == "--header" and i + 1 < len(args):
            header = args[i + 1]; i += 2
        elif args[i] == "--title" and i + 1 < len(args):
            title = args[i + 1]; i += 2
        else:
            i += 1

    with open(ex_path, "r", encoding="utf-8-sig") as f:
        ex = json.load(f)
    game, problems = build(ex, base, header, title)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(game, f, ensure_ascii=False, indent=2)
        f.write("\n")

    for p in problems:
        print("WARN: %s" % p, file=sys.stderr)
    print("OK -> %s (%d questions)" % (out_path, len(game["questions"])))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
