# -*- coding: utf-8 -*-
"""เขียน "บัตรขอบเขตคาบ" {BASE}_scope.md — ที่กลางสำหรับ prompt ทุกตัวของคาบนั้น

    python scope_card.py <gradeSlug> <subjectSlug> <No>            # พิมพ์ดูอย่างเดียว
    python scope_card.py <gradeSlug> <subjectSlug> <No> --apply    # เขียนไฟล์จริง

ทำไมต้องมีไฟล์นี้
    การผลิต 1 คาบเรียก sub-agent ~11 ตัว (writer 7 + checkwork 4) และทุกตัวต้องรู้
    เรื่องเดียวกัน: คาบนี้ต้องส่งมอบอะไร · คาบก่อนสอนอะไรไปแล้ว · อะไรยังไม่ถึงคิว
    ถ้าไม่มีที่กลาง orchestrator ต้องพิมพ์ข้อความชุดเดิมซ้ำใน 11 prompt (เคยเกิดจริง
    ~40 บรรทัด × 11) ซึ่งเปลืองทั้งบริบทของแม่และ input ของลูก — และที่แย่กว่านั้นคือ
    แม่พิมพ์ผิดคำเดียว ลูกผิดตามพร้อมกันหลายตัว

    บัตรนี้ประกอบจากหลักสูตรล้วน ๆ ไม่มีการตีความ — ส่ง path ให้ลูกไปอ่านเอง

ขอบเขตของไฟล์นี้ = ข้อมูลหลักสูตร ไม่ใช่เนื้อหาวิชา
    เนื้อหาที่ต้องใช้เขียนงานอยู่ใน {BASE}_srcpack.md (สร้างจาก C1) คนละไฟล์กัน
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _root import WORK_ROOT  # noqa: E402
from no_to_token import _parse, load_8c, no_to_token  # noqa: E402
from paths import topic_paths  # noqa: E402

#: ความยาวสูงสุดของ COMP คาบอื่นที่ยกมาเทียบ — พอให้รู้ว่าเรื่องนั้นอยู่ตรงไหน
#: แต่ไม่ยาวจนกลายเป็นการสอนคาบอื่นไปด้วย
NEIGHBOUR_CHARS = 90


def _short(text: str, n: int = NEIGHBOUR_CHARS) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _unit_periods(parsed: dict, unit: int) -> list[int]:
    return sorted(no for no, r in parsed["rows"].items() if r["unit"] == unit)


def build_card(grade_slug: str, subject_slug: str, no: int) -> str:
    meta = no_to_token(grade_slug, subject_slug, no)
    parsed = _parse(grade_slug, subject_slug)
    pmeta = parsed["period_meta"]
    rows = parsed["rows"]
    table8c = load_8c()

    L: list[str] = []
    add = L.append

    add(f"# บัตรขอบเขตคาบ — {meta['base']}")
    add("")
    add("> สร้างด้วย `scope_card.py` จากไฟล์หลักสูตรโดยตรง — ไม่มีการตีความ")
    add("> **ห้ามแก้ด้วยมือ** แก้ที่ xlsx แล้ว import/export ใหม่")
    add("")
    add(f"`{meta['header']}`")
    add("")

    add("## คาบนี้คืออะไร")
    add("")
    add("| ช่อง | ค่า |")
    add("|---|---|")
    add(f"| No. | {no} |")
    add(f"| หน่วย | {meta['unit']}. {meta['unit_name']} |")
    if meta.get("period"):
        add(f"| หัวข้อหลัก | {meta['order']}. {meta['main_topic_name']} |")
        add(f"| เรื่อง (คาบที่ {meta['period']} ของหัวข้อ) | {meta['topic_name']} |")
    else:
        add(f"| เรื่อง | {meta['topic_name']} |")
    add(f"| เวลาต่อคาบ | {meta.get('period_minutes') or '-'} นาที |")
    ind = meta.get("indicator") or []
    add(f"| ตัวชี้วัด | {' · '.join(ind) if ind else '— (หลักสูตรยังไม่มีข้อมูล)'} |")
    add("")

    add("## ★ สิ่งที่คาบนี้ต้องส่งมอบ — COMP (สาระสำคัญ / จุดประสงค์ประจำคาบ)")
    add("")
    comp = meta.get("comp") or []
    if not comp:
        add("**ไม่มีข้อมูลในหลักสูตร** — orchestrator ต้องถามผู้ใช้ ห้ามเดาเอง")
    else:
        for c in comp:
            add(f"- {c}")
    src = meta.get("comp_source")
    if src == "unit_outcome":
        add("")
        add("> ⚠ หลักสูตรของวิชานี้ยังไม่มี COMP รายคาบ — ข้อความข้างบนเป็น "
            "**ผลลัพธ์ระดับหน่วย (OUTCOME)** ที่ใช้แทนชั่วคราว")
        add("> จึงกว้างกว่าที่คาบเดียวจะสอนได้ ให้ยึดชื่อเรื่องของคาบเป็นขอบเขตจริง")
    add("")

    add("## จุดประสงค์ประจำหน่วย — OBJ (ระดับหน่วย ไม่ใช่ของคาบนี้ทั้งหมด)")
    add("")
    obj = meta.get("obj") or []
    if not obj:
        add("— (หลักสูตรยังไม่มีข้อมูล)")
    else:
        for o in obj:
            add(f"- {o}")
    pobj = meta.get("period_obj") or []
    add("")
    if pobj:
        add("**คาบนี้รับผิดชอบเฉพาะข้อเหล่านี้**")
        for o in pobj:
            add(f"- {o}")
    else:
        add("> หลักสูตรยังไม่ระบุว่าคาบนี้รับ OBJ ข้อไหน (`POBJ|`) — "
            "**ห้ามสมมติว่าคาบนี้ต้องตอบ OBJ ครบทุกข้อ**")
        add("> OBJ เป็นเป้าของทั้งหน่วยซึ่งกินหลายคาบ ให้ยึด COMP ของคาบเป็นตัวตั้ง")
    add("")

    skills = meta.get("skills_8c") or []
    add("## ทักษะ 8C ที่คาบนี้เน้น")
    add("")
    if skills:
        for s in skills:
            add(f"- **{s['code']} {s['en']}** — {s['th']}")
        add("")
        add("> แผน L1/L2 ต้องเขียนครบทั้ง 8 ข้อ แต่สองข้อข้างบนคือข้อที่ต้องมีเนื้อจริง")
        add(f"> ชื่อทางการของทั้ง 8 ข้ออยู่ที่ `skills-8c.txt` ({len(table8c)} ข้อ)")
    else:
        add("— หลักสูตรของวิชานี้ยังไม่ระบุ (ใช้ `skills-8c.txt` เป็นรายการตั้งต้นได้)")
    add("")

    # --- เพื่อนบ้านในหน่วยเดียวกัน: กันสอนซ้ำและกันสอนล้ำ ---
    unit_nos = _unit_periods(parsed, meta["unit"])
    before = [n for n in unit_nos if n < no]
    after = [n for n in unit_nos if n > no]

    def line(n: int) -> str:
        r = rows[n]
        name = r["period_name"] or r["topic_name"]
        c = (pmeta.get(n) or {}).get("comp") or ""
        return f"- No.{n} {name}" + (f" — {_short(c)}" if c else "")

    add("## เรียนไปแล้วในหน่วยนี้ (อ้างอิงได้ ไม่ต้องสอนใหม่)")
    add("")
    if before:
        for n in before:
            add(line(n))
    else:
        add("— คาบนี้เป็นคาบแรกของหน่วย")
    add("")

    add("## ★ ยังไม่สอนในคาบนี้ — ห้ามล้ำ")
    add("")
    if after:
        for n in after:
            add(line(n))
        add("")
        add("> ห้ามใช้แนวคิด/สัญลักษณ์/วิธีคิดของคาบข้างบนนี้ในเนื้อหา ตัวอย่าง ข้อสอบ "
            "หรือสไลด์ของคาบนี้ แม้จะ 'ช่วยให้เข้าใจง่ายขึ้น'")
        add("> นักเรียนยังไม่ได้เรียน — ใช้แล้วเท่ากับสอนผิดลำดับ")
    else:
        add("— คาบนี้เป็นคาบสุดท้ายของหน่วย")
    add("")

    pre = meta.get("prereq") or []
    add("## หัวข้อที่ต้องรู้มาก่อน (PREREQ)")
    add("")
    if pre:
        for p in pre:
            sp = topic_paths({"base": p["base"], "topic_dir": p["topic_dir"]})
            add(f"- No.{p['no']} {p['topic_name']} → `{sp['content_srcpack_md']}`")
        add("")
        add("> อ่าน srcpack ของคาบก่อนเพื่อใช้ศัพท์/สัญกรณ์ชุดเดียวกัน และเปิดเรื่อง"
            "ด้วยการต่อยอด ไม่ใช่เริ่มใหม่")
    else:
        add("— ไม่ระบุ")
    add("")
    return "\n".join(L) + "\n"


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    apply_ = "--apply" in argv
    if len(args) != 3:
        print("usage: scope_card.py <gradeSlug> <subjectSlug> <No> [--apply]",
              file=sys.stderr)
        return 2
    try:
        no = int(args[2])
    except ValueError:
        print(f"invalid No.: {args[2]!r}", file=sys.stderr)
        return 2
    try:
        meta = no_to_token(args[0], args[1], no)
        card = build_card(args[0], args[1], no)
    except (ValueError, KeyError, RuntimeError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    rel = topic_paths(meta)["scope_md"]
    if not apply_:
        print(card)
        print(f"--- ดูอย่างเดียว · เติม --apply เพื่อเขียน {rel}")
        return 0
    out = Path(WORK_ROOT) / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(card, encoding="utf-8", newline="\n")
    print(rel)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
