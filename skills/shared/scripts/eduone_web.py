# -*- coding: utf-8 -*-
"""คุยกับเว็บ EDU ONE จากเครื่องพนักงาน — อ่านค่าตั้งค่า + ยิง HTTP

ใช้ `urllib` ล้วนโดยตั้งใจ ไม่ใช่ `requests` — สคริปต์กลุ่มนี้ต้องรันได้ตั้งแต่ก่อน
ติดตั้งแพ็กเกจ (doctor.py ก็ใช้หลักการเดียวกัน) และ CLAUDE.md ของโปรเจกต์ระบุไว้ว่า
เครื่องมาตรฐานไม่มี requests

ค่าตั้งค่า (ตัวแรกที่เจอชนะ)
    ตัวแปรสภาพแวดล้อม  EDUONE_WEB_URL / EDUONE_WEB_TOKEN
    ไฟล์               ~/.eduone/config.json  {"url": ..., "token": ..., "work_root": ...}

★ `work_root` อยู่ในไฟล์เดียวกันเพราะมันเป็นสมบัติของ *เครื่อง* เหมือนโทเคน ไม่ใช่ของ repo
  และตัวรับงานต้องรู้ค่านี้ให้ได้โดยไม่ต้องพึ่ง cwd (ดู _root.configured_work_root)

★ โทเคนเป็นของ "คน" ไม่ใช่ของเครื่อง — ออกเองที่หน้า /me/tokens ของเว็บ
  เก็บไว้นอกโฟลเดอร์งานเพื่อไม่ให้หลุดขึ้น git ของงานโดยไม่ตั้งใจ
★ ทุกฟังก์ชันในไฟล์นี้ **ห้ามทำให้งานหลักล้ม** — เว็บล่ม เน็ตหลุด โทเคนหมดอายุ
  ล้วนเป็นเรื่องปกติ และไม่ใช่เหตุผลที่จะทำให้ pipeline ผลิตสื่อหยุดกลางคัน
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

CONFIG_FILE = Path.home() / ".eduone" / "config.json"
TIMEOUT = 20

#: เหตุผลล่าสุดที่ config() คืน None — ตัวเรียกเอาไปบอกผู้ใช้ได้ว่า "ยังไม่ตั้ง" หรือ "ตั้งผิด"
#: ซึ่งเป็นคนละปัญหาที่ต้องแก้คนละทาง แต่ของเดิมคืน None เหมือนกันหมด
last_problem = ""


class WebError(RuntimeError):
    """เรียกเว็บไม่สำเร็จ — ตัวเรียกตัดสินเองว่าจะเงียบหรือจะบ่น"""


def _clean(s: str) -> str:
    """ตัดช่องว่างและเครื่องหมายคำพูดที่ติดมากับการคัดลอก"""
    return str(s).strip().strip('"').strip("'").strip()


def config() -> dict | None:
    """{'url': ..., 'token': ...} — คืน None ถ้ายังไม่ได้ตั้งค่า หรือตั้งไว้ผิดรูปแบบ

    ★ ตั้งผิดต้องไม่เงียบ — ที่อยู่เว็บที่ไม่ใช่ URL (เช่นวางทั้งบรรทัด
      `setx eduone_url "https://..."` ลงไป) เดิมหลุดไปถึง urllib แล้วโผล่เป็น
      "unknown url type: setx eduone_url ..." ในบันทึกของตัวรับงาน ซึ่งพนักงาน
      อ่านไม่ออกว่าต้องกลับมาแก้ที่ไฟล์ตั้งค่า
    """
    global last_problem
    last_problem = ""
    url = os.environ.get("EDUONE_WEB_URL", "").strip()
    token = os.environ.get("EDUONE_WEB_TOKEN", "").strip()
    from_env = bool(url)          # url มาจาก env หรือจากไฟล์ - คนละที่ต้องบอกให้ไปแก้คนละที่
    if not (url and token) and CONFIG_FILE.is_file():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            url = url or str(data.get("url", "")).strip()
            token = token or str(data.get("token", "")).strip()
        except (ValueError, OSError) as exc:
            last_problem = f"อ่านไฟล์ตั้งค่าไม่ได้: {CONFIG_FILE} ({exc})"
            return None
    if not (url and token):
        return None
    url, token = _clean(url), _clean(token)
    if not url.lower().startswith(("http://", "https://")):
        where = "ตัวแปรสภาพแวดล้อม EDUONE_WEB_URL" if from_env else f"ไฟล์ {CONFIG_FILE}"
        last_problem = (f"ที่อยู่เว็บที่ตั้งไว้ไม่ใช่ URL: {url!r} — ต้องขึ้นต้นด้วย https:// "
                        f"· แก้ที่ {where} หรือรันตัวช่วยติดตั้งอีกครั้ง (ข้อ 7/7)")
        return None
    return {"url": url.rstrip("/"), "token": token}


def raw_config() -> dict:
    """ไฟล์ตั้งค่าดิบ ๆ ทั้งก้อน — ตัวที่อยากได้ช่องอื่นนอกจาก url/token เรียกอันนี้

    คืน {} เมื่ออ่านไม่ได้ ไม่ใช่โยน error: ไฟล์เสียต้องแปลว่า "ยังไม่ได้ตั้ง"
    """
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_config(url: str, token: str, work_root: str = "") -> Path:
    """เขียนไฟล์ตั้งค่า — ★ merge ของเดิม ไม่ใช่เขียนทับทั้งไฟล์

    ของเดิมเขียนทับทั้งก้อน พอมี work_root เพิ่มเข้ามา การเรียกเพื่ออัปเดตโทเคน
    อย่างเดียวจะลบโฟลเดอร์งานทิ้งเงียบ ๆ แล้วตัวรับงานจะไม่ยอมเริ่มในวันรุ่งขึ้น
    """
    data = raw_config()
    data["url"] = url.rstrip("/")
    data["token"] = token
    if work_root:
        data["work_root"] = str(work_root)
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return CONFIG_FILE


def save_work_root(work_root: str) -> Path:
    """จดโฟลเดอร์งานไว้อย่างเดียว — ใช้ตอน `runner.py --work <path>`"""
    data = raw_config()
    data["work_root"] = str(work_root)
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return CONFIG_FILE


def _send(req: urllib.request.Request, cfg: dict) -> dict:
    req.add_header("Authorization", f"Bearer {cfg['token']}")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise WebError(f"HTTP {e.code} {e.reason} — {detail}") from None
    except (urllib.error.URLError, OSError) as e:
        raise WebError(f"ต่อเว็บไม่ได้: {e}") from None
    try:
        return json.loads(body) if body else {}
    except ValueError:
        return {"raw": body}


def get(cfg: dict, path: str, params: dict | None = None) -> dict:
    q = ("?" + urllib.parse.urlencode(params)) if params else ""
    return _send(urllib.request.Request(cfg["url"] + path + q, method="GET"), cfg)


def post_json(cfg: dict, path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        cfg["url"] + path, method="POST",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    req.add_header("Content-Type", "application/json; charset=utf-8")
    return _send(req, cfg)


def post_file(cfg: dict, path: str, fields: dict, file_path: Path) -> dict:
    """อัปโหลดไฟล์เดียวแบบ multipart — ประกอบ body เองเพราะ stdlib ไม่มีตัวช่วย"""
    boundary = uuid.uuid4().hex
    sep = f"--{boundary}\r\n".encode()
    body = bytearray()
    for k, v in fields.items():
        body += sep
        body += f'Content-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode("utf-8")
    body += sep
    body += (f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'
             f"Content-Type: application/octet-stream\r\n\r\n").encode("utf-8")
    body += file_path.read_bytes()
    body += f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(cfg["url"] + path, method="POST", data=bytes(body))
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    return _send(req, cfg)


def find_job(cfg: dict, base: str) -> dict | None:
    """ใบสั่งของคาบนี้ — None ถ้ายังไม่มีใครสั่ง (ไม่ใช่ข้อผิดพลาด)"""
    try:
        return get(cfg, "/api/jobs/find", {"base": base})
    except WebError as e:
        if "HTTP 404" in str(e):
            return None
        raise
