# -*- coding: utf-8 -*-
"""แปลเหตุการณ์ดิบของ `claude --output-format stream-json` เป็นบรรทัดที่คนอ่านรู้เรื่อง

ทำไมต้องแยกเป็นไฟล์ของตัวเอง
    ตัวรับงาน (runner.py) มีทั้งโปรเซส เธรด นาฬิกา และเน็ต — ทดสอบยาก
    ส่วนไฟล์นี้เป็น **ฟังก์ชันบริสุทธิ์**: รับ dict คืน dict ไม่แตะดิสก์ ไม่แตะเน็ต
    จึงทดสอบด้วยไฟล์ตัวอย่างได้โดยไม่เสียโทเคนแม้แต่ตัวเดียว

ข้อบังคับ
    ★ event ชนิดที่ไม่รู้จักให้ข้ามเงียบ ๆ ห้ามโยน exception — Claude Code ออกรุ่นใหม่
      บ่อยกว่าปลั๊กอินมาก งานที่รันมาแล้วสองชั่วโมงต้องไม่ตายเพราะ event แปลกหน้าตัวเดียว
    ★ ส่งขึ้นเว็บเฉพาะสิ่งที่คนอ่านแล้วได้ประโยชน์ — ห้ามส่งเนื้อไฟล์ บรรทัดคำสั่งเต็ม
      (มี path ในเครื่องคนอื่น) หรือ thinking
"""
from __future__ import annotations

import json
import re

#: ตัดข้อความยาว — ช่องนี้ตอบว่า "กำลังทำอะไร" ไม่ใช่ที่เก็บผลงาน
MAX_DETAIL = 220

#: tool ที่ไม่ต้องรายงาน — เยอะมากและไม่ได้บอกอะไรที่คนไม่รู้อยู่แล้ว
QUIET_TOOLS = {"Read", "Glob", "Grep", "NotebookRead", "TodoRead", "WebFetch", "WebSearch"}

#: ชื่อ sub-agent -> คำไทย (คีย์ตรงกับ agent ในปลั๊กอิน)
AGENT_NAMES = {
    "content-research":    "ผู้ค้นคว้าแหล่งอ้างอิง",
    "content-academic":    "ผู้เขียนเนื้อหาวิชาการ (C1)",
    "content-narrative":   "ผู้เขียนเนื้อหาเล่าเรื่อง (C2)",
    "content-checkwork":   "ผู้ตรวจเนื้อหา",
    "lesson-plan-writer":  "ผู้เขียนแผนการสอน",
    "lesson-plan-checkwork": "ผู้ตรวจแผนการสอน",
    "exercise-writer":     "ผู้ออกข้อสอบ",
    "exercise-checkwork":  "ผู้ตรวจข้อสอบ",
    "slides-writer":       "ผู้ทำสไลด์",
    "slides-checkwork":    "ผู้ตรวจสไลด์",
    "song-writer":         "ผู้แต่งเพลง",
    "song-checkwork":      "ผู้ตรวจเพลง",
    "video-writer":        "ผู้เขียนสตอรีบอร์ด",
    "video-checkwork":     "ผู้ตรวจสตอรีบอร์ด",
    "game-writer":         "ผู้ทำคลังคำถามเกม",
    "game-checkwork":      "ผู้ตรวจคลังคำถามเกม",
}

#: ชื่อสคริปต์ -> งานที่มันทำ (คนอ่านไม่รู้จักชื่อไฟล์ แต่รู้ว่างานคืออะไร)
SCRIPT_JOBS = {
    "validate_spec.py":  "ตรวจกฎอัตโนมัติ",
    "build_content.py":  "สร้างเอกสารเนื้อหา",
    "build_plan.py":     "สร้างเอกสารแผนการสอน",
    "build_exercise.py": "สร้างเอกสารแบบฝึกหัด",
    "build_slides.py":   "สร้างไฟล์สไลด์",
    "verify_docx.py":    "ตรวจไฟล์เอกสารที่สร้าง",
    "verify_pptx.py":    "ตรวจไฟล์สไลด์ที่สร้าง",
    "no_to_token.py":    "อ่านหลักสูตรของคาบนี้",
    "paths.py":          "หาที่วางไฟล์ของคาบนี้",
    "read_docx_text.py": "อ่านเนื้อเอกสารเดิม",
    "check_math.py":     "ตรวจสัญลักษณ์คณิตศาสตร์",
}

_ASK = re.compile(r"<<<EDUONE_ASK\s*(\{.*?\})\s*EDUONE_ASK>>>", re.S)
_DONE = re.compile(r"<<<EDUONE_DONE\s*(\{.*?\})\s*EDUONE_DONE>>>", re.S)


def _clip(text: str, limit: int = MAX_DETAIL) -> str:
    """ย่อให้เหลือบรรทัดเดียวความยาวพอดีจอ"""
    flat = " ".join(str(text or "").split())
    return flat if len(flat) <= limit else flat[:limit - 1] + "…"


def strip_markers(text: str) -> str:
    """เอาบล็อก EDUONE_ASK / EDUONE_DONE ออกจากข้อความก่อนเอาไปแสดงให้คนอ่าน"""
    out = _ASK.sub("", str(text or ""))
    return _DONE.sub("", out).strip()


def _script_of(command: str) -> tuple[str | None, str | None]:
    """หาชื่อสคริปต์จากบรรทัดคำสั่ง — คืน (ชื่อไฟล์, งานที่มันทำ)

    ไม่ส่งบรรทัดคำสั่งเต็มขึ้นเว็บเด็ดขาด: มันมี path ในเครื่องของคนอื่น ยาว และรกจอ
    """
    for name, job in SCRIPT_JOBS.items():
        if name in (command or ""):
            return name, job
    m = re.search(r"([\w-]+\.py)", command or "")
    return (m.group(1), None) if m else (None, None)


def _from_tool(block: dict) -> dict | None:
    name = block.get("name") or ""
    args = block.get("input") or {}
    if name in QUIET_TOOLS:
        return None
    if name == "Task":
        sub = args.get("subagent_type") or ""
        who = AGENT_NAMES.get(sub.split(":")[-1], sub or "ผู้ช่วย")
        return {"kind": "agent", "actor": who, "detail": _clip(args.get("description"))}
    if name == "Bash":
        script, job = _script_of(args.get("command", ""))
        return {"kind": "tool", "actor": script,
                "detail": _clip(job or args.get("description") or "")}
    if name in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        path = str(args.get("file_path") or "").replace("\\", "/")
        return {"kind": "file", "actor": path.rsplit("/", 1)[-1], "detail": ""}
    if name == "TodoWrite":
        # รายการที่กำลังทำอยู่คือประโยคที่บอกความคืบหน้าได้ดีที่สุดในทั้งสตรีม
        for t in (args.get("todos") or []):
            if isinstance(t, dict) and t.get("status") == "in_progress":
                return {"kind": "step", "actor": None,
                        "detail": _clip(t.get("activeForm") or t.get("content"))}
        return None
    if name == "Skill":
        return {"kind": "step", "actor": None,
                "detail": _clip("เริ่มขั้น " + str(args.get("skill") or ""))}
    return {"kind": "tool", "actor": name, "detail": _clip(args.get("description") or "")}


def to_event(ev) -> dict | None:
    """event ดิบหนึ่งตัว -> {kind, actor, detail} หรือ None ถ้าไม่ต้องแสดง

    ห่อทั้งก้อนด้วย try/except โดยตั้งใจ — ดูเหตุผลในหัวไฟล์
    """
    try:
        if not isinstance(ev, dict):
            return None
        kind = ev.get("type")
        if kind == "system":
            if ev.get("subtype") == "init":
                return {"kind": "step", "actor": None,
                        "detail": "เริ่มเซสชันใหม่ · โมเดล %s" % (ev.get("model") or "-")}
            return None                      # thinking_tokens ฯลฯ — เยอะและไม่มีความหมายต่อคน
        if kind == "assistant":
            for block in (ev.get("message") or {}).get("content") or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    return _from_tool(block)
                if block.get("type") == "text":
                    # ตัดบล็อกคำสั่งที่เราตกลงกับ AI ไว้ออกก่อน — มันเป็นช่องทางสื่อสาร
                    # ระหว่างเครื่องกับเครื่อง ครูที่นั่งอ่านบันทึกไม่ควรต้องเห็น JSON ดิบ
                    text = _clip(strip_markers(block.get("text")))
                    return {"kind": "say", "actor": None, "detail": text} if text else None
            return None
        if kind == "user":
            for block in (ev.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("is_error"):
                    body = block.get("content")
                    if isinstance(body, list):
                        body = " ".join(b.get("text", "") for b in body
                                        if isinstance(b, dict))
                    return {"kind": "warn", "actor": None, "detail": _clip(body)}
            return None
        return None
    except Exception:                        # noqa: BLE001 — ห้ามล้มงานที่รันมาแล้วเป็นชั่วโมง
        return None


def assistant_text(ev) -> str:
    """ข้อความล้วนที่ AI พูดใน event นี้ — ใช้ค้นบล็อก ASK/DONE"""
    try:
        if not isinstance(ev, dict) or ev.get("type") != "assistant":
            return ""
        parts = []
        for block in (ev.get("message") or {}).get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text") or "")
        return "\n".join(parts)
    except Exception:                        # noqa: BLE001
        return ""


def find_ask(text: str) -> dict | None:
    """หาบล็อกที่ AI ใช้ถามกลับ — คืน {question, options} หรือ None

    ใช้บล็อกข้อความที่ตกลงกันไว้ ไม่ดักเครื่องมือ AskUserQuestion เพราะข้อความ
    ทำงานเหมือนกันทุกเวอร์ชันของ CLI และคำตอบกลับไปเป็นข้อความ user ธรรมดา
    ซึ่งเป็นสิ่งที่สกิลถูกออกแบบมาให้รับอยู่แล้ว
    """
    m = _ASK.search(text or "")
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except ValueError:
        return None
    q = str(data.get("q") or data.get("question") or "").strip()
    if not q:
        return None
    opts = data.get("options") or []
    return {"question": q,
            "options": [str(o) for o in opts if str(o).strip()][:4]}


def find_done(text: str) -> dict | None:
    """หาบล็อกที่ AI ใช้บอกว่าจบแล้ว — คืน {ok, summary} หรือ None"""
    m = _DONE.search(text or "")
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except ValueError:
        return None
    return {"ok": bool(data.get("ok", True)),
            "summary": _clip(data.get("summary") or "", 400)}


def usage_of(ev) -> dict | None:
    """ดึงตัวเลขจาก event `result` ตัวสุดท้าย — ชื่อช่องตรงกับที่เว็บรอรับ"""
    if not isinstance(ev, dict) or ev.get("type") != "result":
        return None
    u = ev.get("usage") or {}
    out = {k: u.get(k) for k in ("input_tokens", "output_tokens",
                                 "cache_read_input_tokens", "cache_creation_input_tokens")}
    out["total_cost_usd"] = ev.get("total_cost_usd")
    out["is_error"] = bool(ev.get("is_error"))
    out["denials"] = len(ev.get("permission_denials") or [])
    out["session_id"] = ev.get("session_id")
    return out
