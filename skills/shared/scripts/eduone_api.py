#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""คุยกับเว็บ EDU ONE จากเครื่องพนักงาน — ตัวเชื่อมชุดเดียวของงานคลังหนังสือ

ตั้งค่า (env ชนะไฟล์เสมอ):
    EDUONE_URL / EDUONE_TOKEN            ตัวรับงานฉีดให้โปรเซสลูกอยู่แล้ว
    ~/.eduone/config.json {url, token}   ตัวช่วยติดตั้งจดไว้ให้ — คนพิมพ์เองก็ใช้ได้เลย

★ ทุกคำสั่งต้องทำงานต่อได้แม้ไม่มีเซิร์ฟเวอร์ (RAG-PLAN 6.2 "ต้อง degrade ได้") —
  งานที่จ่ายค่าโทเคนไปแล้วห้ามหายเพราะเน็ตล่ม จึงแยกเป็นสองระดับ:

    api()      งานที่ขาดเซิร์ฟเวอร์ไม่ได้ (จอง/ดึงคลัง) — ต่อไม่ได้ = หยุดพร้อมบอกทางออก
    online()   ถามสั้น ๆ ว่าเว็บอยู่ไหม (timeout 5 วิ) ก่อนเริ่มงานยาว แล้วเลือกทำงานในเครื่อง

  ทำไมเช็คตอนเริ่ม ไม่ใช่ตอนกลางทาง: ถ้ารู้ว่าเว็บล่มตั้งแต่แรก คนถอดจะเลือกได้ว่าจะถอดต่อ
  แบบออฟไลน์ไหม · รู้ตอนถอดเสร็จแล้วส่งไม่ขึ้น = ผลค้างอยู่ในเครื่องโดยที่คนไม่รู้ว่าต้องทำอะไรต่อ
"""

import io
import json
import os

#: ข้อความต่อท้ายตอนต่อเซิร์ฟเวอร์ไม่ได้ — แต่ละสคริปต์ตั้งเองให้บอก 'ทำอะไรต่อได้' ของตัวเอง
#: (กฎ RAG-PLAN 5.5: ข้อความ error ต้องบอกทางออก ไม่ใช่แค่บอกว่าพัง)
OFFLINE_HINT = ""

#: API ของเว็บควรตอบไว — ค่านี้ไม่ใช้กับการดาวน์โหลด PDF (ดู download())
API_TIMEOUT = 20

#: เช็คว่าเว็บอยู่ไหมต้องเร็ว ไม่งั้นเครื่องที่ออฟไลน์จะค้างรอทุกครั้งที่สั่งงาน
PING_TIMEOUT = 5


#: ไฟล์ตั้งค่าของเครื่อง — ไฟล์เดียวกับที่ตัวรับงาน/ตัวช่วยติดตั้งใช้
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".eduone", "config.json")


def _from_config(key):
    """อ่านช่องหนึ่งจากไฟล์ตั้งค่า — ไฟล์เสีย/ไม่มี = "ยังไม่ได้ตั้ง" ไม่ใช่ error

    ★ เดิมอ่านแค่ env สองตัว ซึ่งแปลว่าคนที่พิมพ์คำสั่งเองในเทอร์มินัลต้องมานั่ง
      `set EDUONE_URL=...` ทุกครั้ง ทั้งที่ตัวช่วยติดตั้งจดค่าไว้ให้แล้ว
      env ยังชนะเสมอ (ตัวรับงานฉีดค่าให้โปรเซสลูกอยู่) แค่ไม่บังคับอีกต่อไป
    """
    try:
        with io.open(CONFIG_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return ""
    return str(data.get(key) or "").strip() if isinstance(data, dict) else ""


def server():
    return (os.environ.get("EDUONE_URL") or _from_config("url")).rstrip("/")


def token():
    return os.environ.get("EDUONE_TOKEN") or _from_config("token")


def configured():
    return bool(server())


def online(verbose=True):
    """เว็บตอบไหม — เช็คครั้งเดียวตอนเริ่มงาน ไม่โยน exception (คืน True/False)"""
    import urllib.error
    import urllib.request

    base = server()
    if not base:
        return False
    try:
        with urllib.request.urlopen(base + "/healthz", timeout=PING_TIMEOUT) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError) as exc:
        if verbose:
            print("⚠ ต่อ %s ไม่ได้ (%s) — ทำงานในเครื่องต่อ%s"
                  % (base, getattr(exc, "reason", exc), (" · " + OFFLINE_HINT) if OFFLINE_HINT else ""))
        return False


def api(path, method="GET", payload=None, form=None, timeout=API_TIMEOUT):
    """เรียก API ของเว็บ — คืน (สถานะ, ข้อมูล) ไม่โยน exception เพื่อให้ผู้เรียกเลือกทางเองได้"""
    import urllib.error
    import urllib.parse
    import urllib.request

    base = server()
    if not base:
        raise SystemExit("ยังไม่ได้ตั้ง EDUONE_URL — ตั้งก่อน หรือใช้ --local ถ้าจะทำงานในเครื่องล้วน")
    tok = token()
    if not tok:
        raise SystemExit("ยังไม่ได้ตั้ง EDUONE_TOKEN — ออกโทเคนที่ %s/me/tokens" % base)

    body, ctype = None, None
    if payload is not None:
        body, ctype = json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json"
    elif form is not None:
        body, ctype = urllib.parse.urlencode(form).encode("utf-8"), "application/x-www-form-urlencoded"

    req = urllib.request.Request(base + path, data=body, method=method)
    req.add_header("Authorization", "Bearer %s" % tok)
    if ctype:
        req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, {"detail": raw[:400]}
    except urllib.error.URLError as exc:
        raise SystemExit("ต่อเซิร์ฟเวอร์ %s ไม่ได้: %s%s"
                         % (base, exc.reason, ("\n" + OFFLINE_HINT) if OFFLINE_HINT else ""))


def why(body):
    """ข้อความอธิบายความผิดพลาดจาก body ที่เว็บส่งกลับ — รูปแบบต่างกันตามชนิดของ error"""
    if not isinstance(body, dict):
        return str(body)
    return body.get("reason") or body.get("detail") or body.get("error") or json.dumps(
        body, ensure_ascii=False)[:400]


def download(url, dest, timeout=600):
    """ดึงไฟล์ใหญ่ลงไฟล์ชั่วคราวก่อนแล้วค่อยย้าย — ดาวน์โหลดค้างจะได้ไม่กลายเป็น PDF พัง"""
    import urllib.request

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    with urllib.request.urlopen(url, timeout=timeout) as resp, open(tmp, "wb") as fh:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            fh.write(chunk)
    os.replace(tmp, dest)
    return dest
