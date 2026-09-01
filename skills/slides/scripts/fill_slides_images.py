# -*- coding: utf-8 -*-
"""
fill_slides_images.py — เติม image_file เข้า {BASE}_slides_<SRC>.json อัตโนมัติ

รับรูปที่ผลิตเสร็จแล้วได้ 2 ทาง แล้วจับคู่เข้าหน้าด้วย **ชื่อไฟล์** ตามแบบแผน
    {BASE}_slides_{SRC}_{NN}.<ext>     NN = ลำดับหน้าใน slides[]
  1) โฟลเดอร์รูปในเครื่อง (ค่าเริ่มต้น {BASE}_slides_<SRC>_media/) -> เขียนเป็นพาธสัมพัทธ์
  2) ไฟล์ข้อความรายการ URL (บรรทัดละ 1 URL)                      -> เขียน URL ตรง ๆ
     (build_slides.py จะโหลด+แคชรูปให้เองผ่าน media_cache)

หลักการ (ยกมาจาก fill_ex_urls.py ของ /exercise)
- **ตรวจให้ผ่านก่อนแล้วค่อยเขียน** — เจอปัญหาพิมพ์ออกมาแล้ว **ไม่แตะไฟล์เดิม**
- คงค่าที่เติมไว้แล้ว (รันซ้ำได้) — ทับของเดิมต้องสั่ง --force
- ข้ามไฟล์ขยะ Thumbs.db / desktop.ini / .DS_Store

ใช้:
  fill_slides_images.py <slides.json> [<โฟลเดอร์รูป | urls.txt>] [--dry-run] [--force]

exit 0 = เขียนสำเร็จ / 1 = มีปัญหา ไม่เขียน / 2 = usage
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "shared", "scripts"))
import slides_media as sm  # noqa: E402  (แบบแผนชื่อไฟล์ + clean_prompt อยู่ที่ shared)


def collect_from_dir(folder, stem, problems):
    """คืน {no: ชื่อไฟล์} จากโฟลเดอร์รูป"""
    rx = sm.asset_re(stem)
    found, unknown = {}, []
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if not os.path.isfile(path) or name.lower() in sm.SKIP_NAMES or name.startswith("."):
            continue
        m = rx.search(name.replace("\\", "/"))
        if not m:
            unknown.append(name)
            continue
        no, ext = int(m.group(1)), m.group(2).lower()
        if ext not in sm.IMAGE_EXT:
            problems.append("ไฟล์ %s ไม่ใช่ชนิดรูปที่รองรับ (%s)" % (name, ext))
            continue
        if no in found:
            problems.append("หน้า %d มีรูปซ้ำ 2 ไฟล์: %s / %s" % (no, found[no], name))
            continue
        found[no] = name
    return found, unknown


def collect_from_urls(urls_file, stem, problems):
    """คืน {no: url} จากไฟล์รายการ URL"""
    rx = sm.asset_re(stem)
    found, unknown = {}, []
    with open(urls_file, "r", encoding="utf-8-sig") as f:
        text = f.read()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not line.lower().startswith(("http://", "https://")):
            unknown.append(line)
            continue
        clean = line.split("?", 1)[0].split("#", 1)[0]
        m = rx.search(clean)
        if not m:
            unknown.append(line)
            continue
        no, ext = int(m.group(1)), m.group(2).lower()
        if ext not in sm.IMAGE_EXT:
            problems.append("URL %s ไม่ใช่ชนิดรูปที่รองรับ (%s)" % (line, ext))
            continue
        if no in found:
            problems.append("หน้า %d มี URL ซ้ำ 2 รายการ" % no)
            continue
        found[no] = line
    return found, unknown


def fill(spec_path, source=None, dry_run=False, force=False):
    spec = sm.load_spec(spec_path)
    stem = sm.stem_of(spec_path)
    slots = dict(sm.image_slots(spec))
    if not slots:
        print("ไฟล์นี้ไม่มีหน้าที่ต้องใช้รูป (ไม่มี image_prompt)")
        return 0

    source = source or sm.media_dir_of(spec_path)
    problems = []
    if os.path.isdir(source):
        found, unknown = collect_from_dir(source, stem, problems)
        rel_base = os.path.dirname(os.path.abspath(spec_path))
        values = {no: os.path.relpath(os.path.join(source, name), rel_base).replace("\\", "/")
                  for no, name in found.items()}
        origin = "โฟลเดอร์ %s" % source
    elif os.path.isfile(source):
        found, unknown = collect_from_urls(source, stem, problems)
        values = dict(found)
        origin = "รายการ URL %s" % source
    else:
        print("ไม่พบที่มาของรูป: %s\n"
              "  วางไฟล์รูปไว้ที่โฟลเดอร์นี้ หรือส่งไฟล์รายการ URL มาเป็นอาร์กิวเมนต์ที่สอง"
              % source, file=sys.stderr)
        return 1

    for no in sorted(values):
        if no not in slots:
            problems.append("ไม่มีหน้า %d ที่ต้องใช้รูปในไฟล์นี้ (ชื่อไฟล์เลขผิด?)" % no)

    if problems:
        print("FAIL — พบ %d ปัญหา จึงไม่เขียนไฟล์:" % len(problems), file=sys.stderr)
        for i, p in enumerate(problems, 1):
            print("  %d. %s" % (i, p), file=sys.stderr)
        return 1

    filled, kept, missing = [], [], []
    for no, slide in sorted(slots.items()):
        val = values.get(no)
        if val is None:
            (kept if slide.get("image_file") else missing).append(no)
            continue
        if slide.get("image_file") and not force:
            kept.append(no)
            continue
        slide["image_file"] = val
        filled.append((no, val))

    print("ที่มา: %s" % origin)
    print("  เติมใหม่ %d · คงของเดิม %d · ยังไม่มีรูป %d" % (len(filled), len(kept), len(missing)))
    for no, val in filled:
        print("    หน้า %-3d <- %s" % (no, val))
    if missing:
        print("    ยังขาดรูปของหน้า: %s" % ", ".join(str(n) for n in missing))
    if unknown:
        print("    จับคู่ไม่ได้ (ข้ามไป) %d รายการ: %s"
              % (len(unknown), ", ".join(str(u) for u in unknown[:5])))

    if dry_run:
        print("(--dry-run: ไม่ได้เขียนไฟล์)")
        return 0
    if not filled:
        print("ไม่มีอะไรต้องเปลี่ยน — ไม่ได้เขียนไฟล์")
        return 0
    sm.save_spec(spec_path, spec)
    print("เขียนแล้ว: %s" % spec_path)
    return 0


def main():
    ap = argparse.ArgumentParser(description="เติม image_file เข้าไฟล์สไลด์ json")
    ap.add_argument("spec", help="{BASE}_slides_<SRC>.json")
    ap.add_argument("source", nargs="?",
                    help="โฟลเดอร์รูป หรือไฟล์รายการ URL (ค่าเริ่มต้น: {BASE}_slides_<SRC>_media/)")
    ap.add_argument("--dry-run", action="store_true", help="ดูผลอย่างเดียว ไม่เขียนไฟล์")
    ap.add_argument("--force", action="store_true", help="ทับ image_file เดิมด้วย")
    a = ap.parse_args()
    if not os.path.exists(a.spec):
        print("ไม่พบไฟล์: %s" % a.spec, file=sys.stderr)
        return 2
    return fill(a.spec, a.source, a.dry_run, a.force)


if __name__ == "__main__":
    raise SystemExit(main())
