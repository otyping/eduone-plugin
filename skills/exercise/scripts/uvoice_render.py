# -*- coding: utf-8 -*-
"""
uvoice_render.py — ส่ง {BASE}_audio-src.json ไปให้ **Uvoice** สังเคราะห์เสียงของแบบฝึกหัด

ผู้ใช้กำหนดให้เสียงของสื่อการสอนผลิตที่ Uvoice เท่านั้น (ห้ามใช้ TTS เจ้าอื่น/ในเครื่อง)

API (https://www.uvoice.app/api-docs — v1.2) — **synchronous** ไม่ต้อง poll:
    POST {base}/generate
      headers: Authorization: Bearer <key> · Content-Type: application/json
      body:    {"settings": {"voiceID", "text", "outputFormat", ...}}
      200 -> ตัวไฟล์เสียงมาเป็น binary ตรง ๆ (เขียนลงไฟล์ได้เลย)
      400/401/403/429/500 -> JSON {"message": ...}
    rate limit 100 req/min

config จาก environment (key ไม่อยู่ในโค้ด/repo):
    UVOICE_API_KEY    (จำเป็น)  Bearer token
    UVOICE_API_BASE   (default https://api.uvoice.ai)
    UVOICE_VOICE_ID   (default EN-AlisaSD) — ใส่ voiceID เต็ม หรือชื่อย่อ aria/darin/panmek
                      ดูรายชื่อทั้งหมดด้วย --list-voices

## เลือกเสียงยังไง (สำคัญกับข้อสอบภาษาอังกฤษ)
**ให้เลือกจากตาราง KNOWN_GOOD ด้านล่างเท่านั้น อย่าเดาเสียงใหม่เอง** — เสียงในตารางนี้
ผู้ใช้ฟังจริงแล้วรับรอง เพราะคุณภาพเสียงตัดสินด้วยหูอย่างเดียว ดูจากชื่อ/ชั้นไม่พอ
(เคยเลือก Hazel เพราะเป็นชั้น Standard ชื่อฝรั่ง แต่พอฟังจริงอ่านคำเดี่ยวเพี้ยน)

พื้นหลัง: Uvoice เป็นแพลตฟอร์มไทย ชั้น Standard ที่ displayName เป็นชื่อฝรั่ง
(Hazel, Aria, Andrew ...) เป็นเอนจินอังกฤษเจ้าของภาษา ส่วนชั้น Natural/Premium
เป็นโมเดลเสียงไทยที่อ่านอังกฤษได้ เสียงนุ่มกว่าแต่ติดสำเนียง
-> **คำเดี่ยว/โฟนิกส์ใช้ Standard · บทยาว/บทสนทนาใช้ Premium ได้ถ้าผู้ใช้รับรองแล้ว**

## กฎของข้อสอบฟัง (บังคับ — กันนักเรียนเดาคำตอบ)
ทุกคลิปในชุดเดียวกันต้อง **เสียงเดียวกัน ความเร็วเดียวกัน ความดังเดียวกัน**
สคริปต์นี้จึงใช้ค่าเดียวกับทุกซีนเสมอ — อย่าแก้ให้สุ่มเสียงต่อซีน

ใช้:
  uvoice_render.py <audio-src.json> [--out-dir DIR] [--voice-id ID] [--speed 0.9]
                   [--volume 1.0] [--format wav|mp3] [--only ไฟล์,ไฟล์] [--force] [--dry-run]
  uvoice_render.py --list-voices [--lang en] [--type Standard]   # ไม่ต้องมี audio-src.json

ไฟล์เสียงอยู่ใต้ Output/ จึง gitignored — regenerate ใหม่ได้เสมอจาก audio-src.json (track git)

รันผ่านตัวห่อ: eduone-py <ชื่อไฟล์นี้> <args>  (หา Python 3.12 ให้เองทุก OS)  (ไม่มี requests -> urllib)
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE = "https://api.uvoice.ai"
# ── เสียงที่ผู้ใช้ฟังจริงแล้วรับรอง (อย่าเดาเสียงใหม่เอง ให้เลือกจากตารางนี้) ──────────
#
#   voiceID               ชั้น       เพศ    ชื่อ     ผลการฟัง
#   EN-AlisaSD            Standard  หญิง   Aria    ✅ ผ่าน — อ่าน "คำเดี่ยว" สะอาด (ค่าเริ่มต้น)
#   EN-DarinPremiumHD     Premium   หญิง   Darin   ✅ ผู้ใช้ชอบ (ยังไม่ได้ทดสอบกับคำเดี่ยว)
#   EN-PanmekPremiumHD    Premium   ชาย    Panmek  ✅ ผู้ใช้ชอบ (ยังไม่ได้ทดสอบกับคำเดี่ยว)
#   EN-JennySD            Standard  หญิง   Hazel   ❌ ห้ามใช้ — อ่านคำเดี่ยวเพี้ยน
#                                                     ส่ง "dish" ได้ยินเป็น "เอ-ดิช" ทุกสูตรที่ลอง
#
# Darin/Panmek เป็นชั้น Premium (โมเดลเสียงไทยอ่านอังกฤษ) เสียงนุ่มกว่า เหมาะกับ
# **บทยาว/บทสนทนา** — ถ้าจะใช้กับข้อสอบโฟนิกส์ที่เล่นคำโดด ๆ ให้ยิงทดสอบคำนั้นก่อนเสมอ
# มีคู่ชาย-หญิงแล้ว ใช้ทำบทสนทนา 2 คนได้ (คนละ voiceID ต่อบทบาท แต่ในข้อเดียวกัน
# ตัวเลือกทุกใบยังต้องเป็นเสียงเดียวกัน)
DEFAULT_VOICE = "EN-AlisaSD"
KNOWN_GOOD = {
    "aria": "EN-AlisaSD",           # Standard หญิง — ปลอดภัยสุดกับคำเดี่ยว
    "darin": "EN-DarinPremiumHD",   # Premium หญิง
    "panmek": "EN-PanmekPremiumHD",  # Premium ชาย
}
VOICE_LIST_URL = "https://www.uvoice.app/?getVoice=true&lang_selected={lang}&filter=All&source=STUDIO"
# Cloudflare บล็อก UA ของ python-urllib — ใช้ UA แบบ browser (แพทเทิร์นเดียวกับ suno_render.py)
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
MIN_TEXT = 5            # API ปฏิเสธข้อความสั้นกว่า 5 ตัวอักษร
PAUSE_PAD = "{b250}"    # ต่อท้ายคำสั้น ๆ ให้ผ่านลิมิต โดยได้แค่ความเงียบท้ายคลิป
SENT_GAP_MS = 350       # ความเงียบที่แทรกหลังจบประโยค (กันบั๊ก TLD ด้านล่าง)
RATE_SLEEP = 0.7        # วินาที ระหว่าง request (ลิมิต 100/นาที)

# บั๊กของ text normalizer ฝั่ง Uvoice: ถ้าเจอ "." ตามด้วยเว้นวรรคแล้วคำที่บังเอิญตรงกับ
# โดเมนระดับบนสุด มันจะอ่านรวมเป็นชื่อโดเมน เช่น
#     "...hot season. It is sunny."  ->  อ่านว่า "...hot season DOT IT is sunny"
# คำภาษาอังกฤษที่ชนกับ TLD มีเยอะและล้วนเป็นคำขึ้นต้นประโยคที่ใช้บ่อยที่สุด
#     It(.it) At(.at) My(.my) Is(.is) In(.in) Be(.be) Me(.me) So(.so) To(.to) No(.no) ...
# แก้โดยแทรก {b350} คั่นระหว่างจุดกับคำถัดไป -> จุดถูกตามด้วย "{" ไม่ใช่ตัวอักษร
# normalizer จึงจับเป็นโดเมนไม่ได้ และยังได้จังหวะหยุดท้ายประโยคที่เป็นธรรมชาติขึ้นด้วย
SENTENCE_BREAK_RE = re.compile(r"([.!?])(\s+)(?=[A-Za-z])")


def guard_sentence_breaks(text, gap_ms=SENT_GAP_MS):
    """แทรกตัวคั่นความเงียบหลังจุด/อัศเจรีย์/ปรัศนี ที่ตามด้วยคำ — กันบั๊ก TLD ข้างบน"""
    return SENTENCE_BREAK_RE.sub(lambda m: "%s{b%d}%s" % (m.group(1), gap_ms, m.group(2)), text)


# อัญประกาศที่ **ครอบวลี** (เช่น sing 'Auld Lang Syne') ทำให้ Uvoice ตอบ
# HTTP 403 "Error creating file" เมื่อใช้ร่วมกับตัวคั่น {b} ในข้อความยาว
# (ฝั่งเซิร์ฟเวอร์น่าจะเอาข้อความไปตั้งชื่อไฟล์แคช แล้วอักขระผสมนี้ทำให้พัง)
# อัญประกาศไม่ถูกออกเสียงอยู่แล้ว ตัดทิ้งได้โดยเสียงไม่เปลี่ยน
# แต่ต้อง **คง apostrophe ที่อยู่กลางคำ** ไว้ เช่น New Year's · It's · don't
QUOTES = "'‘’\"“”"
WRAP_QUOTE_RE = re.compile(r"(?<![A-Za-z])[%s]|[%s](?![A-Za-z])" % (QUOTES, QUOTES))


def strip_wrapping_quotes(text):
    """ตัดอัญประกาศที่ครอบวลี คง apostrophe กลางคำไว้ (Year's / It's ไม่โดนแตะ)"""
    return WRAP_QUOTE_RE.sub("", text)


def _err_message(raw):
    try:
        return json.loads(raw.decode("utf-8")).get("message") or raw[:200].decode("utf-8", "replace")
    except Exception:
        return raw[:200].decode("utf-8", "replace")


def generate(base, key, settings, timeout=120):
    """POST /generate -> (ok, payload) ; payload = bytes เสียง หรือข้อความ error"""
    body = json.dumps({"settings": settings}).encode("utf-8")
    req = urllib.request.Request(base.rstrip("/") + "/generate", data=body, method="POST",
                                 headers={
                                     "Authorization": "Bearer " + key,
                                     "Content-Type": "application/json",
                                     "User-Agent": USER_AGENT,
                                 })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, r.read()
    except urllib.error.HTTPError as e:
        return False, "HTTP %s — %s" % (e.code, _err_message(e.read()))
    except Exception as e:
        return False, str(e)


def pad_choices_equal(out_dir, fmt):
    """เติมความเงียบท้ายคลิป **ตัวเลือก** ของข้อเดียวกันให้ยาวเท่ากันทุกใบ

    Uvoice คืนความยาวไม่เท่ากันเป๊ะ ถ้าตัวเลือก 2 ใบสั้นกว่าเพื่อนชัด ๆ นักเรียนตัดทิ้งได้
    โดยไม่ต้องฟังเนื้อหา -> ผิดกฎกันเดาของข้อสอบฟัง จึงต้องปรับให้เท่ากัน
    (ทำได้เฉพาะ wav เพราะเป็น PCM ดิบ ต่อ frame เงียบได้ตรง ๆ ไม่ต้อง re-encode)
    """
    if fmt != "wav":
        print("  (ข้ามการปรับความยาวให้เท่ากัน — ทำได้เฉพาะ wav)")
        return []
    import collections
    import wave

    groups = collections.defaultdict(list)
    for fn in sorted(os.listdir(out_dir)):
        if not fn.lower().endswith(".wav"):
            continue
        stem = os.path.splitext(fn)[0]
        parts = stem.rsplit("_", 2)          # {BASE}_{NN}_{slot}
        if len(parts) != 3 or not parts[2].startswith("A"):
            continue                          # เอาเฉพาะตัวเลือก A1-A4 (โจทย์ Q ไม่ต้องเท่ากัน)
        groups[parts[1]].append(os.path.join(out_dir, fn))

    changed = []
    for qno, paths in sorted(groups.items()):
        if len(paths) < 2:
            continue
        info = {}
        for p in paths:
            with wave.open(p, "rb") as w:
                info[p] = (w.getnframes(), w.getparams())
        target = max(n for n, _ in info.values())
        for p, (n, params) in info.items():
            if n >= target:
                continue
            with wave.open(p, "rb") as w:
                frames = w.readframes(n)
            silence = b"\x00" * ((target - n) * params.sampwidth * params.nchannels)
            with wave.open(p, "wb") as w:
                w.setparams(params)
                w.writeframes(frames + silence)
            changed.append((os.path.basename(p), (target - n) / float(params.framerate)))
    for name, sec in changed:
        print("  ปรับความยาว %-30s +%.2f วิ (เงียบท้ายคลิป)" % (name, sec))
    if not changed:
        print("  ความยาวตัวเลือกเท่ากันอยู่แล้วทุกข้อ")
    return changed


def fetch_voices(lang="en"):
    req = urllib.request.Request(VOICE_LIST_URL.format(lang=urllib.parse.quote(lang)),
                                 headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def cmd_list_voices(args):
    voices = fetch_voices(args.lang)
    rows = [v for v in voices if not args.type or v.get("type") == args.type]
    rows.sort(key=lambda v: (v.get("type", ""), v.get("gender", ""), str(v.get("displayName"))))
    print("เสียงภาษา %s%s — %d ตัว" % (args.lang,
                                        (" ชั้น " + args.type) if args.type else "", len(rows)))
    if args.type == "Standard" or not args.type:
        print("(ชั้น Standard = เอนจินเจ้าของภาษา เหมาะกับข้อสอบภาษาอังกฤษ)")
    for v in rows[:args.limit]:
        print("  %-9s %-7s %-26s %s" % (v.get("type"), v.get("gender"),
                                        v.get("voiceID"), v.get("displayName")))
    if len(rows) > args.limit:
        print("  ... อีก %d ตัว (ใช้ --limit เพิ่ม)" % (len(rows) - args.limit))
    return 0


def main():
    ap = argparse.ArgumentParser(description="สร้างเสียงแบบฝึกหัดผ่าน Uvoice")
    ap.add_argument("src", nargs="?", help="พาธ {BASE}_audio-src.json")
    ap.add_argument("--out-dir", default=None,
                    help="โฟลเดอร์ปลายทาง (ค่าเริ่มต้น = {BASE}_media ข้างไฟล์ src)")
    ap.add_argument("--voice-id", default=None,
                    help="voiceID เต็ม หรือชื่อย่อจากตารางเสียงที่รับรองแล้ว: %s "
                         "(default env UVOICE_VOICE_ID / %s)"
                         % ("/".join(sorted(KNOWN_GOOD)), DEFAULT_VOICE))
    ap.add_argument("--speed", type=float, default=0.9, help="0.50-1.50 (default 0.9 ช้าลงเล็กน้อย)")
    ap.add_argument("--volume", type=float, default=1.0, help="0.50-1.50 (default 1.0)")
    ap.add_argument("--format", dest="fmt", default="wav", choices=["wav", "mp3"])
    ap.add_argument("--only", default=None, help="ทำเฉพาะไฟล์ (คั่นด้วยจุลภาค)")
    ap.add_argument("--force", action="store_true", help="เขียนทับไฟล์เดิม")
    ap.add_argument("--no-pad-equal", action="store_true",
                    help="ไม่ต้องปรับความยาวคลิปตัวเลือกให้เท่ากัน (ปกติปรับให้ กันเดาคำตอบ)")
    ap.add_argument("--dry-run", action="store_true", help="แสดงรายการอย่างเดียว ไม่ยิง API")
    ap.add_argument("--list-voices", action="store_true", help="แสดงรายชื่อเสียงแล้วออก")
    ap.add_argument("--lang", default="en", help="ภาษาของรายชื่อเสียง (คู่กับ --list-voices)")
    ap.add_argument("--type", default="Standard", help="ชั้นเสียง Standard/Natural/Premium ('' = ทั้งหมด)")
    ap.add_argument("--limit", type=int, default=60, help="จำนวนแถวสูงสุดตอน --list-voices")
    args = ap.parse_args()

    if args.list_voices:
        return cmd_list_voices(args)
    if not args.src:
        ap.error("ต้องระบุ {BASE}_audio-src.json (หรือใช้ --list-voices)")

    key = os.environ.get("UVOICE_API_KEY", "").strip()
    base = os.environ.get("UVOICE_API_BASE", DEFAULT_BASE)
    voice = args.voice_id or os.environ.get("UVOICE_VOICE_ID") or DEFAULT_VOICE
    voice = KNOWN_GOOD.get(voice.strip().lower(), voice)   # รับชื่อย่อ เช่น "darin"

    with open(args.src, "r", encoding="utf-8") as f:
        data = json.load(f)
    ubase = data.get("base") or os.path.basename(args.src).replace("_audio-src.json", "")
    scenes = data.get("scenes") or []
    if not scenes:
        print("ไม่มีซีนเสียงใน %s — ไม่ต้องสร้าง" % args.src)
        return 0

    out_dir = args.out_dir or os.path.join(os.path.dirname(os.path.abspath(args.src)),
                                           "%s_media" % ubase)
    os.makedirs(out_dir, exist_ok=True)

    only = {s.strip() for s in args.only.split(",")} if args.only else None
    print("Uvoice | voiceID %s | speed %.2f | volume %.2f | %s"
          % (voice, args.speed, args.volume, args.fmt))
    print("ปลายทาง: %s" % out_dir)

    if not key and not args.dry_run:
        print("ไม่มี UVOICE_API_KEY — ตั้งด้วย  setx UVOICE_API_KEY \"xxxx\"  แล้วเปิด terminal ใหม่",
              file=sys.stderr)
        return 2

    made, skipped, failed = [], [], []
    for sc in scenes:
        name = sc.get("file")
        text = (sc.get("narration") or "").strip()
        if not name or not text:
            failed.append((name or "(ไม่มีชื่อไฟล์)", "ขาด file หรือ narration"))
            continue
        if args.fmt != os.path.splitext(name)[1].lstrip("."):
            name = os.path.splitext(name)[0] + "." + args.fmt
        if only is not None and name not in only:
            continue
        path = os.path.join(out_dir, name)
        if os.path.exists(path) and not args.force:
            skipped.append(name)
            continue

        send = strip_wrapping_quotes(text)                 # กัน 403 Error creating file
        send = guard_sentence_breaks(send)                 # กันบั๊ก TLD (". It" -> "dot it")
        if len(send) < MIN_TEXT:
            send += PAUSE_PAD                              # กันโดน 400 คำสั้นเกิน
        if args.dry_run:
            made.append((name, 0, sc.get("slot", ""), send))
            continue

        ok, payload = generate(base, key, {
            "voiceID": voice,
            "text": send,
            "outputFormat": args.fmt,
            "outputType": "binary",
            "autoBreak": False,      # อ่านตามที่พิมพ์ เร็วกว่า (autoBreak ใช้ได้กับไทยเท่านั้น)
            "speed": args.speed,
            "volume": args.volume,
        })
        if not ok:
            failed.append((name, payload))
        else:
            with open(path, "wb") as f:
                f.write(payload)
            made.append((name, len(payload), sc.get("slot", ""), send))
        time.sleep(RATE_SLEEP)

    for name, size, slot, sent in made:
        extra = "  (เติม %s กันลิมิต 5 ตัวอักษร)" % PAUSE_PAD if sent.endswith(PAUSE_PAD) else ""
        print("  ✓ %-30s %7.1f KB  %s%s" % (name, size / 1024.0, slot, extra))
    if skipped:
        print("  ข้าม (มีอยู่แล้ว ใช้ --force เพื่อทับ): %d ไฟล์" % len(skipped))
    for name, why in failed:
        print("  ✗ %-30s %s" % (name, why), file=sys.stderr)

    if not args.dry_run and not args.no_pad_equal:
        pad_choices_equal(out_dir, args.fmt)

    print("สร้าง %d ไฟล์ · ข้าม %d · ผิดพลาด %d" % (len(made), len(skipped), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
