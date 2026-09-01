# -*- coding: utf-8 -*-
"""
fill_ex_urls.py — เติม URL สื่อ (รูป/เสียง) เข้า {BASE}_ex.json อัตโนมัติ

รับไฟล์รายการ URL (ผู้ใช้อัปโหลดสื่อขึ้น CDN แล้ว copy path list มาวาง) แล้วจับคู่เข้าช่อง
ด้วย **ชื่อไฟล์** ตามแบบแผน:
    {BASE}_{NN}_Q.<ext>       -> โจทย์ข้อ NN
    {BASE}_{NN}_A{1-4}.<ext>  -> ตัวเลือก ก/ข/ค/ง ของข้อ NN

หลักการ (ยกมาจาก fill_exall_urls.py ของ AI_Course)
- **ตรวจให้ผ่านก่อนแล้วค่อยเขียน** — ถ้าเจอปัญหา พิมพ์ออกมาแล้ว **ไม่แตะไฟล์เดิม**
- คง URL เดิมที่เติมไว้แล้ว (รันซ้ำได้)
- ข้ามไฟล์ขยะ Thumbs.db / desktop.ini / .DS_Store / *.ai
- ชนิดต้องตรงช่อง: ช่องรูปต้องได้ URL รูป, ช่องเสียงต้องได้ URL เสียง

ใช้:
  fill_ex_urls.py <urls.txt> <ex.json> [--base BASE] [--dry-run] [--allow-partial]

exit 0 = เขียนสำเร็จ / 1 = มีปัญหา ไม่เขียน / 2 = usage
"""
import argparse
import json
import os
import re
import sys

THAI_LETTERS = ("ก", "ข", "ค", "ง")
SKIP_NAMES = {"thumbs.db", "desktop.ini", ".ds_store"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".ogg", ".aac"}


def base_from_json_path(path):
    name = os.path.basename(path)
    for suffix in ("_ex.json", ".json"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def kind_of_ext(ext):
    if ext in IMAGE_EXT:
        return "image"
    if ext in AUDIO_EXT:
        return "audio"
    return ""


def parse_urls(text, base):
    """คืน (found, skipped, unknown) — found: {(qno, slot): {url, kind}}"""
    pattern = re.compile(
        r"(?:^|/)" + re.escape(base) + r"_(\d{2})_(Q|A[1-4])(\.[A-Za-z0-9]+)$")
    found, skipped, unknown, dupes = {}, [], [], []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not (line.startswith("http://") or line.startswith("https://")):
            continue
        clean = line.split("?", 1)[0].split("#", 1)[0]
        name = clean.rsplit("/", 1)[-1]
        if name.lower() in SKIP_NAMES:
            skipped.append(name)
            continue
        m = pattern.search(clean)
        if not m:
            unknown.append(line)
            continue
        qno, slot, ext = int(m.group(1)), m.group(2), m.group(3).lower()
        kind = kind_of_ext(ext)
        if not kind:
            unknown.append(line)
            continue
        key = (qno, slot)
        if key in found and found[key]["url"] != line:
            dupes.append("%s_%02d_%s มีหลาย URL" % (base, qno, slot))
            continue
        found[key] = {"url": line, "kind": kind}
    return found, skipped, unknown, dupes


def expected_slots(ex):
    """ช่องสื่อทั้งหมดที่ต้องมี URL -> {(qno, slot): kind}; และช่องที่มี URL แล้ว"""
    need, already = {}, {}
    for qi, q in enumerate(ex.get("questions") or [], start=1):
        if (q.get("imageAlt") or "").strip() or (q.get("imageUrl") or "").strip():
            key = (qi, "Q")
            (already if (q.get("imageUrl") or "").strip() else need)[key] = "image"
        if (q.get("audioText") or "").strip() or (q.get("audioUrl") or "").strip():
            key = (qi, "Q_AUDIO")
            (already if (q.get("audioUrl") or "").strip() else need)[key] = "audio"
        for ci, c in enumerate(q.get("choices") or []):
            ctype = (c.get("contentType") or "text").strip()
            if ctype not in ("image", "audio"):
                continue
            key = (qi, "A%d" % (ci + 1))
            (already if (c.get("content") or "").strip() else need)[key] = ctype
    return need, already


def apply_urls(ex, found):
    """เติม URL ลง ex (in place) คืนจำนวนช่องที่เติม"""
    filled = 0
    for qi, q in enumerate(ex.get("questions") or [], start=1):
        hit = found.get((qi, "Q"))
        if hit:
            if hit["kind"] == "image" and not (q.get("imageUrl") or "").strip():
                q["imageUrl"] = hit["url"]; filled += 1
            elif hit["kind"] == "audio" and not (q.get("audioUrl") or "").strip():
                q["audioUrl"] = hit["url"]; filled += 1
        for ci, c in enumerate(q.get("choices") or []):
            hit = found.get((qi, "A%d" % (ci + 1)))
            if hit and not (c.get("content") or "").strip():
                c["content"] = hit["url"]; filled += 1
    return filled


def main():
    ap = argparse.ArgumentParser(description="เติม URL สื่อเข้า {BASE}_ex.json")
    ap.add_argument("urls_txt")
    ap.add_argument("ex_json")
    ap.add_argument("--base", default=None)
    ap.add_argument("--dry-run", action="store_true", help="ตรวจอย่างเดียว ไม่เขียนไฟล์")
    ap.add_argument("--allow-partial", action="store_true",
                    help="ยอมเขียนแม้ยังเติมไม่ครบทุกช่อง")
    args = ap.parse_args()

    base = args.base or base_from_json_path(args.ex_json)
    with open(args.ex_json, "r", encoding="utf-8-sig") as f:
        ex = json.load(f)
    with open(args.urls_txt, "r", encoding="utf-8") as f:
        text = f.read()

    found, skipped, unknown, dupes = parse_urls(text, base)
    need, already = expected_slots(ex)

    problems = list(dupes)

    # ช่องโจทย์แยก image/audio: (qi,"Q") ในไฟล์ URL ใช้ชื่อเดียวกัน ต่างกันที่นามสกุล
    need_norm = {}
    for (qi, slot), kind in need.items():
        need_norm[(qi, "Q" if slot == "Q_AUDIO" else slot)] = kind if slot != "Q_AUDIO" else "audio"
    # ถ้าข้อเดียวมีทั้งรูปโจทย์และเสียงโจทย์ จะมี 2 ช่องชื่อ Q -> แยกด้วย kind
    need_pairs = []
    for (qi, slot), kind in need.items():
        need_pairs.append((qi, "Q" if slot == "Q_AUDIO" else slot, kind))

    matched = set()
    for qi, slot, kind in need_pairs:
        hit = found.get((qi, slot))
        if hit is None:
            problems.append("ยังไม่มี URL สำหรับ %s_%02d_%s (%s)" % (base, qi, slot, kind))
        elif hit["kind"] != kind:
            problems.append("ชนิดไม่ตรง %s_%02d_%s: ต้องการ %s แต่ได้ %s"
                            % (base, qi, slot, kind, hit["kind"]))
        else:
            matched.add((qi, slot))

    orphans = [k for k in found if k not in matched
               and k not in {(q, "Q" if s == "Q_AUDIO" else s) for q, s in already}]
    for qi, slot in sorted(orphans):
        problems.append("URL เกินมา ไม่มีช่องรองรับ: %s_%02d_%s" % (base, qi, slot))

    print("พบ URL ที่ชื่อตรงแบบแผน: %d | ช่องที่รอเติม: %d | ช่องที่มีอยู่แล้ว: %d"
          % (len(found), len(need), len(already)))
    if skipped:
        print("ข้ามไฟล์ขยะ: %s" % ", ".join(sorted(set(skipped))))
    if unknown:
        print("ข้าม URL ที่ชื่อไม่ตรงแบบแผน %d รายการ (เช่น %s)"
              % (len(unknown), unknown[0][:80]))

    if problems and not args.allow_partial:
        print("\nFAIL — พบ %d ปัญหา จึง **ไม่เขียนไฟล์**:" % len(problems))
        for i, p in enumerate(problems, 1):
            print("  %d. %s" % (i, p))
        return 1
    for p in problems:
        print("WARN: %s" % p, file=sys.stderr)

    filled = apply_urls(ex, found)
    if args.dry_run:
        print("\n[dry-run] จะเติม %d ช่อง (ไม่เขียนไฟล์)" % filled)
        return 0

    with open(args.ex_json, "w", encoding="utf-8") as f:
        json.dump(ex, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("\nOK — เติม %d ช่อง เขียน %s แล้ว" % (filled, args.ex_json))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
