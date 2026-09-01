# -*- coding: utf-8 -*-
"""
suno_render.py — สร้างเพลง mp3 จาก song.json ผ่าน Suno gateway (ค่าเริ่มต้น: sunoapi.org)

ใช้งาน:
    python suno_render.py [--dry-run] <song.json> <out.mp3>

อ่าน config จาก environment variable (key ไม่อยู่ในโค้ด/repo):
    SUNO_API_KEY        (จำเป็น)  Bearer token จาก gateway
    SUNO_API_BASE       (default https://api.sunoapi.org)
    SUNO_MODEL          (default V4_5; รับ V4/V4_5/V4_5PLUS/V4_5ALL/V5/V5_5)
    SUNO_CALLBACK_URL   (default https://example.com/callback — placeholder; เรา poll เอง)

schema sunoapi.org:
    POST {base}/api/v1/generate            body custom-mode -> {code,data:{taskId}}
    GET  {base}/api/v1/generate/record-info?taskId=...
         -> data.status (PENDING/TEXT_SUCCESS/FIRST_SUCCESS/SUCCESS/*_FAILED/SENSITIVE_WORD_ERROR)
            data.response.sunoData[] แต่ละตัวมี audioUrl

input song.json: {"lyrics": "...(/n ขึ้นบรรทัด)...", "style": "..."}
- เขียน mp3 -> out_path (เพลงแรก) + _alt.mp3 (เพลงสอง ถ้ามี)
- เขียนเนื้อเพลง -> <out ที่เปลี่ยนเป็น>.txt  (อ่านง่าย) ทุกครั้ง (ทั้ง render จริงและ PENDING)
- ไม่มี SUNO_API_KEY -> เขียน <out>.PENDING (ไม่ error)
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

GENERATE_PATH = "/api/v1/generate"
QUERY_PATH = "/api/v1/generate/record-info"
# Cloudflare บล็อก UA ของ python-urllib (error 1010) — ใช้ UA แบบ browser
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
# ลิมิตอักษรตาม model (เผื่อ V4 เข้มสุด) — กันยิงแล้ว reject
LIMITS = {"prompt": 4900, "style": 990, "title": 78}
POLL_EVERY = 5          # วินาที
POLL_TIMEOUT = 240      # วินาที (เผื่อ V5/คิวยาว)
DONE_OK = {"SUCCESS"}
DONE_PARTIAL = {"FIRST_SUCCESS"}   # เพลงแรกพร้อม (ใช้ได้)
FAILED = {"CREATE_TASK_FAILED", "GENERATE_AUDIO_FAILED", "CALLBACK_EXCEPTION",
          "SENSITIVE_WORD_ERROR"}


def _lyrics_text(song):
    return song.get("lyrics", "").replace("/n", "\n")


def _write_lyrics_txt(song, out_path):
    """เขียนไฟล์เนื้อเพลง <BASE>_song.txt คู่กับ mp3 (อ่านง่าย)"""
    txt_path = os.path.splitext(out_path)[0] + ".txt"
    os.makedirs(os.path.dirname(txt_path) or ".", exist_ok=True)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(_lyrics_text(song).rstrip() + "\n\n")
        f.write(f"style: {song.get('style','')}\n")
    return txt_path


def _post_json(url, payload, key):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def _get_json(url, key):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {key}", "Accept": "application/json",
        "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def _download(url, out_path):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r, open(out_path, "wb") as f:
        f.write(r.read())


def _build_payload(song):
    model = os.environ.get("SUNO_MODEL", "V4_5")
    return {
        "customMode": True,
        "instrumental": False,
        "model": model,
        "style": song.get("style", "")[:LIMITS["style"]],
        "title": song.get("_title", "song")[:LIMITS["title"]],
        "prompt": _lyrics_text(song)[:LIMITS["prompt"]],
        "callBackUrl": os.environ.get("SUNO_CALLBACK_URL", "https://example.com/callback"),
    }


def render(song_path, out_path, dry_run=False):
    """คืน 'OK' | 'PENDING' | 'DRYRUN'."""
    with open(song_path, "r", encoding="utf-8") as f:
        song = json.load(f)
    # ใช้ชื่อไฟล์ (BASE) เป็น title
    base = os.path.splitext(os.path.basename(out_path))[0].replace("_song", "")
    song.setdefault("_title", base)

    _write_lyrics_txt(song, out_path)   # เขียนเนื้อเพลงเสมอ

    base_url = os.environ.get("SUNO_API_BASE", "https://api.sunoapi.org").rstrip("/")
    key = os.environ.get("SUNO_API_KEY")
    payload = _build_payload(song)

    if dry_run:
        print("DRY-RUN — จะยิง:")
        print(f"  POST {base_url}{GENERATE_PATH}")
        print(f"  poll GET {base_url}{QUERY_PATH}?taskId=<id>")
        safe = dict(payload); safe["prompt"] = safe["prompt"][:60] + "..."
        print("  payload:", json.dumps(safe, ensure_ascii=False))
        print(f"  key set: {'yes' if key else 'NO (จะเขียน .PENDING)'}")
        return "DRYRUN"

    if not key:
        placeholder = out_path + ".PENDING"
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(placeholder, "w", encoding="utf-8") as f:
            f.write("PENDING SUNO API (ยังไม่ตั้ง SUNO_API_KEY)\n")
            f.write(f"style: {song.get('style','')}\n")
        print(f"PENDING — เขียน {placeholder} (ตั้ง SUNO_API_KEY เพื่อ render จริง)")
        return "PENDING"

    # 1) generate
    try:
        res = _post_json(f"{base_url}{GENERATE_PATH}", payload, key)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"generate HTTP {e.code}: {body[:300]}")
    if res.get("code") != 200 or not res.get("data", {}).get("taskId"):
        raise RuntimeError(f"generate ไม่สำเร็จ: {json.dumps(res, ensure_ascii=False)[:300]}")
    task_id = res["data"]["taskId"]
    print(f"taskId={task_id} — กำลังสร้างเพลง (poll ทุก {POLL_EVERY}s)...")

    # 2) poll
    deadline = None  # ใช้ตัวนับรอบแทน time.time() (เลี่ยงปัญหา sandbox)
    waited = 0
    audio_urls = []
    while waited <= POLL_TIMEOUT:
        time.sleep(POLL_EVERY)
        waited += POLL_EVERY
        q = _get_json(f"{base_url}{QUERY_PATH}?taskId={task_id}", key)
        data = q.get("data") or {}
        status = data.get("status", "")
        if status in FAILED:
            raise RuntimeError(f"Suno สร้างเพลงล้มเหลว: status={status} (taskId={task_id})")
        if status in DONE_OK or status in DONE_PARTIAL:
            clips = ((data.get("response") or {}).get("sunoData")) or []
            audio_urls = [c.get("audioUrl") for c in clips if c.get("audioUrl")]
            if audio_urls:
                print(f"  status={status} — ได้ {len(audio_urls)} เพลง")
                break
        print(f"  ...status={status} ({waited}s)")
    if not audio_urls:
        raise RuntimeError(f"timeout {POLL_TIMEOUT}s — ยังไม่ได้เพลง (taskId={task_id})")

    # 3) download
    _download(audio_urls[0], out_path)
    print(f"OK -> {out_path}")
    if len(audio_urls) > 1:
        alt = os.path.splitext(out_path)[0] + "_alt.mp3"
        try:
            _download(audio_urls[1], alt)
            print(f"     (เพลงสำรอง) -> {alt}")
        except Exception:
            pass
    return "OK"


def main():
    args = [a for a in sys.argv[1:]]
    dry = False
    if "--dry-run" in args:
        dry = True
        args.remove("--dry-run")
    if len(args) != 2:
        print("usage: python suno_render.py [--dry-run] <song.json> <out.mp3>", file=sys.stderr)
        sys.exit(2)
    status = render(args[0], args[1], dry_run=dry)
    print(f"status={status}")


if __name__ == "__main__":
    main()
