# -*- coding: utf-8 -*-
"""
media_cache.py — resolve URL/พาธไฟล์สื่อ (รูป/เสียง) ให้เป็นไฟล์ในเครื่อง สำหรับฝังลง .docx

ใช้โดย build_exercise.py เมื่อ {BASE}_ex.json มี imageUrl / audioUrl หรือ choices[].content
ที่เป็น URL ของรูป

หลักการสำคัญ
- **ห้าม build พัง** ถ้าโหลดไม่ได้ (ออฟไลน์/404/URL ว่าง) -> คืน None ให้ผู้เรียกไปแสดง placeholder แทน
- ใช้ urllib.request (stdlib) เพราะเครื่องนี้ **ไม่มี requests**
- แคชด้วย sha1 ของ URL -> โหลดซ้ำครั้งต่อไปไม่ต้องต่อเน็ต (build ซ้ำได้แบบออฟไลน์)
- Word ฝัง .webp ไม่ได้ -> แปลงเป็น .png ให้อัตโนมัติ (Pillow)

ใช้ Python 3.12: %LOCALAPPDATA%\\Programs\\Python\\Python312\\python.exe
"""
import hashlib
import os
import sys
import urllib.error
import urllib.request

try:
    from PIL import Image
except Exception:  # ไม่มี Pillow ก็ยังฝังรูปตรง ๆ ได้ แค่ไม่ย่อ/ไม่แปลงชนิด
    Image = None

# นามสกุลที่ Word ฝังได้ตรง ๆ
DOCX_SAFE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff"}
IMAGE_EXT = DOCX_SAFE_EXT | {".webp"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".ogg", ".aac"}

TIMEOUT_SEC = 20
# ความละเอียดเป้าหมายตอนฝังลงเอกสาร (px ต่อ mm ที่ ~200 dpi)
PX_PER_MM = 200.0 / 25.4

_UA = "Mozilla/5.0 (EDU-ONE media_cache)"


def is_url(value):
    return isinstance(value, str) and value.strip().lower().startswith(("http://", "https://"))


def ext_of(value):
    """นามสกุลไฟล์ (พิมพ์เล็ก) จาก URL หรือพาธ — ตัด query string ทิ้ง"""
    if not value:
        return ""
    name = value.split("?", 1)[0].split("#", 1)[0]
    return os.path.splitext(name)[1].lower()


def kind_of(value):
    """เดาชนิดสื่อจากนามสกุล -> 'image' | 'audio' | ''"""
    e = ext_of(value)
    if e in IMAGE_EXT:
        return "image"
    if e in AUDIO_EXT:
        return "audio"
    return ""


def download(url, cache_dir, force=False):
    """โหลด URL ลงแคช คืนพาธไฟล์ในเครื่อง; คืน None ถ้าโหลดไม่ได้ (ไม่ raise)"""
    if not is_url(url):
        return None
    os.makedirs(cache_dir, exist_ok=True)
    ext = ext_of(url) or ".bin"
    key = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    dest = os.path.join(cache_dir, key + ext)
    if os.path.exists(dest) and os.path.getsize(dest) > 0 and not force:
        return dest
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            data = resp.read()
        if not data:
            return None
        with open(dest, "wb") as f:
            f.write(data)
        return dest
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as exc:
        print("WARN: โหลดสื่อไม่ได้ %s (%s)" % (url, exc), file=sys.stderr)
        return None


def resolve(value, cache_dir, base_dir=None):
    """คืนพาธไฟล์ในเครื่องของสื่อชิ้นหนึ่ง หรือ None

    value เป็นได้ทั้ง URL (โหลด+แคช) หรือพาธไฟล์ (สัมพัทธ์กับ base_dir ก็ได้)
    """
    if not value or not str(value).strip():
        return None
    value = str(value).strip()
    if is_url(value):
        return download(value, cache_dir)
    # พาธไฟล์ในเครื่อง
    for cand in ([value] if os.path.isabs(value) else
                 [value] + ([os.path.join(base_dir, value)] if base_dir else [])):
        if os.path.exists(cand) and os.path.getsize(cand) > 0:
            return cand
    print("WARN: ไม่พบไฟล์สื่อ %s" % value, file=sys.stderr)
    return None


def fit_image(path, width_mm, cache_dir):
    """เตรียมรูปให้พร้อมฝัง docx — แปลงชนิดที่ Word ไม่รองรับ + ย่อรูปที่ใหญ่เกิน

    คืนพาธที่ฝังได้ หรือ None ถ้ารูปเสีย/เปิดไม่ได้
    """
    if not path or not os.path.exists(path):
        return None
    ext = os.path.splitext(path)[1].lower()
    if Image is None:
        return path if ext in DOCX_SAFE_EXT else None

    target_px = max(320, int(width_mm * PX_PER_MM))
    try:
        with Image.open(path) as im:
            im.load()
            needs_convert = ext not in DOCX_SAFE_EXT
            needs_resize = im.width > target_px
            if not needs_convert and not needs_resize:
                return path

            out = im
            if needs_resize:
                ratio = target_px / float(im.width)
                out = im.resize((target_px, max(1, int(im.height * ratio))), Image.LANCZOS)
            if out.mode not in ("RGB", "L"):
                out = out.convert("RGB")

            os.makedirs(cache_dir, exist_ok=True)
            key = hashlib.sha1(("%s|%d" % (os.path.abspath(path), target_px)).encode("utf-8"))
            dest = os.path.join(cache_dir, "fit_%s.png" % key.hexdigest()[:16])
            out.save(dest, "PNG")
            return dest
    except Exception as exc:  # รูปเสีย/รูปแบบแปลก -> ให้ผู้เรียกไปแสดง placeholder
        print("WARN: เปิดรูปไม่ได้ %s (%s)" % (path, exc), file=sys.stderr)
        return None


def resolve_image(value, width_mm, cache_dir, base_dir=None):
    """resolve + fit ในขั้นตอนเดียว — ทางลัดที่ build_exercise.py ใช้"""
    local = resolve(value, cache_dir, base_dir=base_dir)
    if local is None:
        return None
    return fit_image(local, width_mm, cache_dir)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("ใช้: media_cache.py <url|path> <cache_dir> [width_mm]", file=sys.stderr)
        raise SystemExit(2)
    w = float(sys.argv[3]) if len(sys.argv) > 3 else 110.0
    got = resolve_image(sys.argv[1], w, sys.argv[2])
    print(got if got else "(resolve ไม่สำเร็จ)")
    raise SystemExit(0 if got else 1)
