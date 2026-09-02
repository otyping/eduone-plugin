# -*- coding: utf-8 -*-
"""สรุปโทเคนที่ใช้จริงของการรันหนึ่งคาบ -> {BASE}_usage.json + ตารางอ่านคน

    python usage_report.py <run.jsonl|run.json> <gradeSlug> <subjectSlug> <No>
    python usage_report.py <run.jsonl> --out <path.json>       # ระบุปลายทางเอง

ทำไมต้องมี
    `webapp/app/tokens.py` เขียนไว้ตรง ๆ ว่า "รายงานถูกพิมพ์ในแชทแล้วหายไปกับ session
    ตรวจ Output/ ทั้งหมด 310 ไฟล์ ไม่มีเก็บไว้สักไฟล์" — ที่ผ่านมาต้องพิมพ์มือใส่ฟอร์มเว็บ
    ซึ่งไม่มีใครทำจริง และเลขที่ agent รายงานเองก็เป็นของรอบสุดท้ายรอบเดียว ไม่รวมรอบแก้

    ตัวเลขในไฟล์นี้มาจาก event `result` ของ CLI โดยตรง จึงเป็นยอดจริงทั้งการรัน
    รวมทุก sub-agent และทุกรอบแก้

รับได้ทั้ง
    stream-json (.jsonl)  — หา event ที่ `type == "result"`
    json ก้อนเดียว (.json) — ใช้ทั้งก้อนเลย
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

#: ราคาต่อล้านโทเคน — ต้องตรงกับ webapp/app/tokens.py
PRICE = {
    "opus":   {"input": 5.00, "cache_write": 6.25, "cache_read": 0.50, "output": 25.00},
    "sonnet": {"input": 2.00, "cache_write": 2.50, "cache_read": 0.20, "output": 10.00},
    "haiku":  {"input": 1.00, "cache_write": 1.25, "cache_read": 0.10, "output": 5.00},
}


def find_result(path):
    """คืน event ผลลัพธ์สุดท้าย — รองรับทั้ง .jsonl (stream) และ .json (ก้อนเดียว)"""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    try:
        d = json.loads(text)
        if isinstance(d, dict) and "usage" in d:
            return d
    except json.JSONDecodeError:
        pass
    last = None
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("type") == "result" or "usage" in d:
            last = d
    return last


def normalize(ev):
    u = ev.get("usage") or {}
    return {
        "session_id": ev.get("session_id"),
        "num_turns": ev.get("num_turns"),
        "duration_api_ms": ev.get("duration_api_ms"),
        "is_error": ev.get("is_error"),
        "tokens": {
            "input": u.get("input_tokens", 0),
            "cache_write": u.get("cache_creation_input_tokens", 0),
            "cache_read": u.get("cache_read_input_tokens", 0),
            "output": u.get("output_tokens", 0),
        },
        # ราคาที่ CLI คิดให้ = ยอดจริงตามสัญญาที่ใช้อยู่ เชื่อค่านี้ก่อนเสมอ
        "total_cost_usd": ev.get("total_cost_usd"),
    }


def cost_of(tokens, model="opus"):
    p = PRICE.get(model, PRICE["opus"])
    return sum(tokens[k] / 1_000_000 * p[k] for k in tokens)


def fmt(n):
    return "{:,}".format(int(n or 0))


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    out = None
    if "--out" in argv:
        out = argv[argv.index("--out") + 1]
    if not args:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    run = args[0]
    if not os.path.exists(run):
        print("ไม่พบไฟล์: %s" % run, file=sys.stderr)
        return 2

    ev = find_result(run)
    if ev is None:
        print("ไม่พบ event ผลลัพธ์ใน %s — การรันอาจถูกตัดกลางคัน" % run, file=sys.stderr)
        return 1
    rec = normalize(ev)
    t = rec["tokens"]
    est = cost_of(t)

    if out is None and len(args) == 4:
        from no_to_token import no_to_token
        from paths import topic_paths
        from _root import WORK_ROOT
        meta = no_to_token(args[1], args[2], int(args[3]))
        rel = topic_paths(meta)["usage_json"]
        rec["base"] = meta["base"]
        out = os.path.join(str(WORK_ROOT), rel)
        shown = rel
    else:
        shown = out
    if out:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rec, ensure_ascii=False, indent=2) + "\n")

    print("| รายการ | จำนวนโทเคน |")
    print("|---|---:|")
    print("| input | %s |" % fmt(t["input"]))
    print("| cache write | %s |" % fmt(t["cache_write"]))
    print("| cache read | %s |" % fmt(t["cache_read"]))
    print("| output | %s |" % fmt(t["output"]))
    print("| **รวม** | **%s** |" % fmt(sum(t.values())))
    print()
    if rec["total_cost_usd"] is not None:
        print("ราคาที่ CLI คิดให้: $%.2f" % rec["total_cost_usd"])
    print("ประมาณจากราคา Opus: $%.2f  ·  %s turn  ·  %.1f นาที"
          % (est, rec["num_turns"], (rec["duration_api_ms"] or 0) / 60000))
    if out:
        print("บันทึกแล้ว -> %s" % shown)
    return 1 if rec["is_error"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
