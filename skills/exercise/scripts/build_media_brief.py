# -*- coding: utf-8 -*-
"""
build_media_brief.py — สร้าง "ใบสั่งผลิตสื่อ" จาก {BASE}_ex.json

ผลลัพธ์ 2 ไฟล์
  {BASE}_media-brief.md   ใบสั่งผลิต **รูป** (กฎรวม + prompt ต่อไฟล์ + ชื่อไฟล์ที่ต้องใช้)
  {BASE}_audio-src.json   บทเสียงสำหรับ TTS: { base, note, scenes:[{no, slot, narration}] }

เลขซีนของเสียง = เลขข้อ x 10 (+1..4 = ตัวเลือก ก/ข/ค/ง)   เช่น ข้อ 4 ตัวเลือก ค -> 43
ชื่อไฟล์สื่อ: {BASE}_{NN}_Q.<ext> (โจทย์) · {BASE}_{NN}_A{1-4}.<ext> (ตัวเลือก)

ใช้:
  build_media_brief.py <ex.json> [--base BASE] [--brief OUT.md] [--audio-src OUT.json]
                       [--title "เรื่อง ..."]

ใช้ Python 3.12: %LOCALAPPDATA%\\Programs\\Python\\Python312\\python.exe
"""
import argparse
import json
import os
import sys

THAI_LETTERS = ("ก", "ข", "ค", "ง")

IMAGE_RULES = """## กฎรวมของทุกภาพ (สำคัญ — กันนักเรียนเดาคำตอบ)

- **ห้ามมีตัวหนังสือในภาพ** เว้นแต่ระบุไว้ว่าต้องมี — ตัวอักษรที่ AI สร้างมักอ่านไม่ออกและรบกวนโจทย์
- ห้ามมีโลโก้แบรนด์ ลายน้ำ หรือใบหน้าที่ระบุตัวตนบุคคลจริงได้
- **ภาพตัวเลือกในข้อเดียวกันต้องสไตล์เดียวกันทั้งหมด** (แสง มุมกล้อง ความอิ่มสี สัดส่วน ขนาด)
  ถ้าภาพเฉลยดูต่างจากพวก นักเรียนจะเดาได้จากหน้าตาโดยไม่ต้องคิด
- ภาพเชิงเรขาคณิต/กราฟ/แผนภาพ ต้องอ่านค่าได้ชัด เส้นคม พื้นหลังเรียบ ไม่มีเงารบกวน
  แกนและสเกลต้องกำกับให้ครบตามที่ระบุ และใช้สเกลเดียวกันในข้อเดียวกัน
- ส่งกลับเป็น .png หรือ .jpg ก็ได้ แต่**ชื่อไฟล์ต้องตรงตามตารางท้ายเอกสารเป๊ะ ๆ**

> **ผลิตที่ Google Nano Banana** — ใช้ **prompt ภาษาอังกฤษ** ในบล็อก `Prompt` ของแต่ละไฟล์
> (คัดลอกไปวางได้เลย) โมเดลสร้างภาพเข้าใจอังกฤษแม่นกว่าไทยมาก โดยเฉพาะคำกำกับมุมกล้อง
> สไตล์ และข้อห้าม · คำบรรยายไทยที่พับไว้ใต้ prompt มีไว้ **ตรวจว่าภาพที่ได้ตรงโจทย์**
"""

AUDIO_RULES = """## กฎรวมของทุกคลิปเสียง

- **ทุกตัวเลือกเสียงในข้อเดียวกันต้องใช้เสียงคนเดียวกัน** ความเร็ว/โทนเดียวกัน
  ให้นักเรียนตัดสินจากเนื้อหา ไม่ใช่จากน้ำเสียง
- ความดังสม่ำเสมอทุกไฟล์ · ไม่มีเสียงรบกวน · เว้นหัวท้ายสั้น ๆ ได้
"""


def asset_name(base, qno, slot, kind, url=""):
    ext = os.path.splitext((url or "").split("?")[0])[1].lower()
    if not ext:
        ext = ".png" if kind == "image" else ".wav"
    return "%s_%02d_%s%s" % (base, qno, slot, ext)


def base_from_json_path(path):
    name = os.path.basename(path)
    for suffix in ("_ex.json", ".json"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


LOCAL_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".wav", ".mp3", ".m4a")


def _produced(assets_dir, filename):
    """ไฟล์นี้ผลิตไว้แล้วในเครื่องหรือยัง (เช่น กราฟที่ gen_math_images.py วาดให้)"""
    if not assets_dir or not os.path.isdir(assets_dir):
        return False
    stem = os.path.splitext(filename)[0]
    return any(os.path.exists(os.path.join(assets_dir, stem + e)) for e in LOCAL_EXT)


def collect(ex, base, assets_dir=None):
    """คืน (image_slots, audio_scenes) — เฉพาะช่องที่ยังไม่มี URL

    ช่องที่มีไฟล์อยู่ในเครื่องแล้วจะติดธง done=True (ผลิตแล้ว เหลือแค่อัปโหลด)
    """
    images, audios = [], []
    for qi, q in enumerate(ex.get("questions") or [], start=1):
        img_url = (q.get("imageUrl") or "").strip()
        img_alt = (q.get("imageAlt") or "").strip()
        if img_alt and not img_url:
            fn = asset_name(base, qi, "Q", "image")
            images.append({
                "file": fn, "qno": qi, "slot": "โจทย์", "brief": img_alt, "correct": False,
                "question": (q.get("text") or "").strip(),
                "done": _produced(assets_dir, fn),
            })
        aud_url = (q.get("audioUrl") or "").strip()
        aud_text = (q.get("audioText") or "").strip()
        if aud_text and not aud_url:
            fn = asset_name(base, qi, "Q", "audio")
            audios.append({
                "no": qi * 10, "slot": "ข้อ %d โจทย์" % qi,
                "narration": aud_text, "file": fn,
                "done": _produced(assets_dir, fn),
            })

        for ci, c in enumerate(q.get("choices") or []):
            ctype = (c.get("contentType") or "text").strip()
            content = (c.get("content") or "").strip()
            alt = (c.get("alt") or "").strip()
            letter = THAI_LETTERS[ci] if ci < 4 else "?"
            slot = "A%d" % (ci + 1)
            if content or not alt:
                continue  # มี URL แล้ว หรือไม่มีคำบรรยายให้ผลิต
            if ctype == "image":
                fn = asset_name(base, qi, slot, "image")
                images.append({
                    "file": fn, "qno": qi, "slot": "ตัวเลือก %s" % letter, "brief": alt,
                    "correct": bool(c.get("isTrue")),
                    "question": (q.get("text") or "").strip(),
                    "done": _produced(assets_dir, fn),
                })
            elif ctype == "audio":
                fn = asset_name(base, qi, slot, "audio")
                audios.append({
                    "no": qi * 10 + ci + 1,
                    "slot": "ข้อ %d ตัวเลือก %s%s" % (qi, letter, " (คำตอบที่ถูก)" if c.get("isTrue") else ""),
                    "narration": alt, "file": fn,
                    "done": _produced(assets_dir, fn),
                })
    return images, audios


def load_image_prompts(folder, base):
    """อ่าน {BASE}_image-prompts.json (ถ้ามี) -> {ชื่อไฟล์รูป: prompt ภาษาอังกฤษ}

    รูปผลิตที่ **Google Nano Banana** ซึ่งรับ prompt ภาษาอังกฤษเท่านั้นถึงจะตรง
    ไฟล์นี้จึงเป็น source of truth ของ prompt (track git) แยกจาก imageAlt ภาษาไทย
    ที่ยังต้องคงไว้เพราะเป็นข้อความที่ครูอ่านใน .docx
    """
    p = os.path.join(folder, "%s_image-prompts.json" % base)
    if not os.path.exists(p):
        return {}
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("prompts") or {}


def write_brief(path, base, title, images, audios, prompts=None):
    prompts = prompts or {}
    lines = ["# ใบสั่งผลิตสื่อ — %s" % base]
    if title:
        lines.append("")
        lines.append("> %s" % title)
    todo_img = [i for i in images if not i.get("done")]
    todo_aud = [a for a in audios if not a.get("done")]
    done_all = [m for m in list(images) + list(audios) if m.get("done")]

    lines += ["",
              "**ยังต้องผลิต: รูป %d ไฟล์ · เสียง %d ไฟล์** (รวม %d)"
              % (len(todo_img), len(todo_aud), len(todo_img) + len(todo_aud))]
    if done_all:
        n_img = sum(1 for m in done_all if m in images)
        kinds = " · ".join(x for x in ["รูป %d" % n_img if n_img else "",
                                       "เสียง %d" % (len(done_all) - n_img)
                                       if len(done_all) - n_img else ""] if x)
        how = []
        if n_img:
            how.append("รูปที่ระบบวาดเองถูกฝังใน .docx ให้แล้ว")
        if len(done_all) - n_img:
            how.append("เสียงสร้างจาก `%s_audio-src.json`" % base)
        lines += ["",
                  "**ผลิตไว้แล้วในเครื่อง %d ไฟล์ (%s)** — อยู่ใน `%s_media/`"
                  % (len(done_all), kinds, base),
                  "(%s)" % " · ".join(how),
                  "→ เหลือแค่ **อัปโหลดขึ้น CDN** แล้วส่ง URL กลับมา ไม่ต้องผลิตใหม่"]
    lines += ["",
              "อัปโหลดเสร็จแล้วส่ง **รายการ URL** กลับมา",
              "ระบบจะเติม URL เข้า `%s_ex.json` ให้อัตโนมัติด้วย `fill_ex_urls.py`" % base,
              ""]
    # ใส่เฉพาะกฎของสื่อที่ยังต้องผลิตจริง
    if todo_img:
        lines.append(IMAGE_RULES)
    if todo_aud:
        lines.append(AUDIO_RULES)

    if todo_img:
        lines += ["---", "", "## รูปภาพที่ต้องผลิต", ""]
        current_q = None
        for it in todo_img:
            if it["qno"] != current_q:
                current_q = it["qno"]
                lines += ["### ข้อ %d — %s" % (it["qno"], it["question"]), ""]
            star = " ★ **เฉลย**" if it["correct"] else ""
            lines += ["#### `%s` — %s%s" % (it["file"], it["slot"], star), ""]
            en = prompts.get(it["file"])
            if en:
                lines += ["**Prompt (คัดลอกไปวางใน Nano Banana ได้เลย)**", "",
                          "```text", en.strip(), "```", "",
                          "<details><summary>คำบรรยายภาษาไทย (สำหรับตรวจว่าภาพตรงโจทย์)</summary>",
                          "", "```", it["brief"], "```", "", "</details>", ""]
            else:
                lines += ["```", it["brief"], "```", ""]

    if done_all:
        lines += ["---", "", "## ไฟล์ที่ระบบผลิตให้แล้ว (รออัปโหลดอย่างเดียว)", "",
                  "| ไฟล์ | ตำแหน่ง |", "|---|---|"]
        for m in done_all:
            lines.append("| `%s` | %s |" % (m["file"], m.get("slot", "")))
        lines.append("")

    if todo_aud:
        lines += ["---", "", "## คลิปเสียงที่ต้องผลิต", "",
                  "บทเสียงฉบับเครื่องอ่านอยู่ใน `%s_audio-src.json` (ใช้กับ TTS ได้เลย)" % base, "",
                  "| ไฟล์ | ตำแหน่ง | บทพูด |", "|---|---|---|"]
        for a in todo_aud:
            narration = a["narration"].replace("|", "\\|")
            lines.append("| `%s` | %s | %s |" % (a["file"], a["slot"], narration))
        lines.append("")

    lines += ["---", "", "## ตารางรายการไฟล์ที่ต้องส่งกลับ (ชื่อต้องตรงเป๊ะ)", "",
              "| # | ไฟล์ | ชนิด |", "|---|---|---|"]
    for i, it in enumerate(todo_img, start=1):
        lines.append("| %d | `%s` | รูป |" % (i, it["file"]))
    for j, a in enumerate(todo_aud, start=len(todo_img) + 1):
        lines.append("| %d | `%s` | เสียง |" % (j, a["file"]))
    if not todo_img and not todo_aud:
        lines.append("| - | (ไม่มี — ผลิตครบแล้ว) | - |")
    lines += ["", "รวมที่ต้องผลิต %d ไฟล์ — รูป %d · เสียง %d"
              % (len(todo_img) + len(todo_aud), len(todo_img), len(todo_aud)), ""]

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def write_audio_src(path, base, audios):
    data = {
        "base": base,
        "note": ("บทเสียงแบบฝึกหัด %s — เลขซีน = เลขข้อ x10 (+1..4 = ตัวเลือก ก/ข/ค/ง). "
                 "ตัวเลือกเสียงในข้อเดียวกันต้องใช้เสียงคนเดียวกัน" % base),
        "scenes": [{"no": a["no"], "slot": a["slot"], "narration": a["narration"],
                    "file": a["file"]} for a in sorted(audios, key=lambda x: x["no"])],
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main():
    ap = argparse.ArgumentParser(description="สร้างใบสั่งผลิตสื่อจาก {BASE}_ex.json")
    ap.add_argument("ex_json")
    ap.add_argument("--base", default=None)
    ap.add_argument("--title", default="")
    ap.add_argument("--brief", default=None)
    ap.add_argument("--audio-src", dest="audio_src", default=None)
    args = ap.parse_args()

    with open(args.ex_json, "r", encoding="utf-8-sig") as f:
        ex = json.load(f)

    base = args.base or base_from_json_path(args.ex_json)
    folder = os.path.dirname(os.path.abspath(args.ex_json))
    brief_path = args.brief or os.path.join(folder, "%s_media-brief.md" % base)
    audio_path = args.audio_src or os.path.join(folder, "%s_audio-src.json" % base)

    assets_dir = os.path.join(folder, "%s_media" % base)
    images, audios = collect(ex, base, assets_dir=assets_dir)
    if not images and not audios:
        print("ไม่มีสื่อที่ต้องผลิต (ไม่มีช่องรูป/เสียงที่ยังว่าง URL) — ไม่สร้างไฟล์")
        return 0

    prompts = load_image_prompts(folder, base)
    write_brief(brief_path, base, args.title, images, audios, prompts)
    ti = sum(1 for i in images if not i.get("done"))
    ta = sum(1 for a in audios if not a.get("done"))
    print("เขียน %s (ต้องผลิต: รูป %d · เสียง %d | ผลิตแล้ว %d)"
          % (brief_path, ti, ta, len(images) + len(audios) - ti - ta))
    if audios:
        write_audio_src(audio_path, base, audios)
        print("เขียน %s (%d ซีน)" % (audio_path, len(audios)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
