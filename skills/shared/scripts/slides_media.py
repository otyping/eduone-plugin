# -*- coding: utf-8 -*-
"""
slides_media.py — ของใช้ร่วมของงานรูปประกอบสไลด์ (EDU ONE — agent 4)

แบบแผนชื่อไฟล์รูป (สัญญาระหว่างใบสั่งผลิตกับตัวเติมอัตโนมัติ):
    {BASE}_slides_{SRC}_{NN}.png       NN = ลำดับหน้าใน slides[] (1-based, 2 หลัก)

เช่น หน้าที่ 3 ของ P1-Sci_U1_1_slides_C1.json -> `P1-Sci_U1_1_slides_C1_03.png`
โฟลเดอร์รูปเริ่มต้น: `{BASE}_slides_{SRC}_media/` (วางข้าง ๆ ไฟล์ json)

**เจ้าของ prompt สั่งวาดภาพ** — `clean_prompt()` ต้องเป็นจุดเดียวที่แปลง `image_prompt` ดิบ
ให้เป็นข้อความที่คัดลอกไปวางโมเดลสร้างภาพได้ เพราะข้อความนี้ออกไปสองทาง
(ใบสั่งผลิต .md และ speaker note ใน .pptx) — ถ้าแยกกันเขียนจะไม่ตรงกันแล้วครูสับสน

อยู่ที่ shared/ เพราะทั้ง `build_slides.py` (shared) และสคริปต์ใน `slides/scripts/` ต้องใช้ร่วมกัน

ใช้ Python 3.12: %LOCALAPPDATA%\\Programs\\Python\\Python312\\python.exe
"""
from __future__ import annotations

import json
import os
import re

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
SKIP_NAMES = {"thumbs.db", "desktop.ini", ".ds_store"}

# ประโยคสั่งใส่ป้ายกำกับ (writer เขียนตาม Master Prompt) — ต้องตัดออกก่อนส่งให้โมเดลสร้างภาพ
# เพราะโมเดลเขียนอักษรไทยเป็นตัวอ่านไม่ออก และสไลด์มีข้อความอธิบายอยู่แล้ว
_LABEL_RE = re.compile(
    r"[,;]?\s*(?:with\s+)?(?:labell?ed\s+components?\s+in\s+Thai|Thai\s+labell?e?d?s?)\b[^.]*",
    re.IGNORECASE)
# ต่อท้ายเฉพาะข้อบังคับที่มาจาก "กรอบภาพในสไลด์" กับ "โมเดลเขียนตัวหนังสือไม่ได้"
# ส่วนพื้นหลัง/แสง/มุมกล้อง เป็นหน้าที่ของ writer ที่ต้องเขียนมาใน prompt เอง (Master Prompt 1.2)
PROMPT_SUFFIX = ("no text, no letters, no labels, no watermark or logo anywhere in the image, "
                 "roughly square 1:1 framing with the subject fully inside the frame")


def clean_prompt(prompt: str):
    """คืน (prompt ที่คัดลอกไปวางโมเดลสร้างภาพได้เลย, ตัดประโยคป้ายกำกับออกหรือไม่)

    ใช้ร่วมกันระหว่างใบสั่งผลิต (.md) กับ speaker note ใน .pptx — ต้องได้ข้อความเดียวกันเสมอ
    """
    text = (prompt or "").strip().rstrip(".")
    if not text:
        return "", False
    cleaned = _LABEL_RE.sub("", text).strip().rstrip(",").strip()
    return "%s, %s" % (cleaned, PROMPT_SUFFIX), cleaned != text


def stem_of(spec_path: str) -> str:
    """`.../P1-Sci_U1_1_slides_C1.json` -> `P1-Sci_U1_1_slides_C1`"""
    name = os.path.basename(spec_path)
    return name[:-5] if name.lower().endswith(".json") else name


def media_dir_of(spec_path: str) -> str:
    """โฟลเดอร์รูปเริ่มต้นของสไลด์ชุดนี้ (ข้าง ๆ ไฟล์ json)"""
    return os.path.join(os.path.dirname(os.path.abspath(spec_path)),
                        stem_of(spec_path) + "_media")


def brief_path_of(spec_path: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(spec_path)),
                        stem_of(spec_path) + "_media-brief.md")


def asset_name(stem: str, no: int, ext: str = ".png") -> str:
    return "%s_%02d%s" % (stem, no, ext)


def asset_re(stem: str):
    """regex จับชื่อไฟล์ของสไลด์ชุดนี้ (ใช้ได้ทั้งชื่อไฟล์และ URL)"""
    return re.compile(r"(?:^|/)" + re.escape(stem) + r"_(\d{2})(\.[A-Za-z0-9]+)$")


def load_spec(spec_path: str) -> dict:
    with open(spec_path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_spec(spec_path: str, spec: dict) -> None:
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)
        f.write("\n")


def image_slots(spec: dict):
    """หน้าที่ต้องมีรูป -> [(no, slide)] โดย no = ลำดับใน slides[] (1-based)

    นับหน้า `content` และ `question` ที่มี `image_prompt` (หน้าที่ writer ตั้งใจให้มีภาพประกอบ)
    — หน้า `question` ของ L1/L2 คือขั้นนำที่ต้องโชว์ภาพให้เด็กดูแล้วตอบ ห้ามตกหล่น
    """
    out = []
    for i, s in enumerate(spec.get("slides", []), 1):
        if (s.get("section") in ("content", "question")
                and (s.get("image_prompt") or s.get("image_file"))):
            out.append((i, s))
    return out
