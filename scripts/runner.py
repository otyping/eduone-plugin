# -*- coding: utf-8 -*-
"""ตัวรับงานประจำเครื่อง — คอยถามเว็บว่ามีงานไหม แล้วรันให้เองจนจบ

    eduone-py runner.py              # เปิดค้างไว้ รับงานไปเรื่อย ๆ
    eduone-py runner.py --work <dir> # จดโฟลเดอร์งานลงไฟล์ตั้งค่า (ทำครั้งเดียวต่อเครื่อง)
    eduone-py runner.py --once       # ทำงานที่ค้างอยู่ใบเดียวแล้วออก (ไว้ทดสอบ)
    eduone-py runner.py --fake x.jsonl   # ไม่เรียก claude จริง อ่านไฟล์ตัวอย่างแทน

รับงานสองชนิดจากคิวเดียวกัน
    ใบสั่งผลิตสื่อ   /api/runs/<id>/...    (มาก่อนเสมอ — มีคนรอผลอยู่ปลายทาง)
    งานคลังหนังสือ  /api/tasks/<id>/...   (ถอดสารบัญ · ถอดเนื้อหาเป็นบท)

ทำไมต้องมีตัวนี้
    พนักงานที่ใช้ระบบนี้ไม่ได้เป็นคนสายคอม เก่งสุดคือรันตัวติดตั้งครั้งแรกได้
    ก่อนหน้านี้เขาต้องเปิดเทอร์มินัลสองหน้าต่างแล้วพิมพ์คำสั่งเอง และถ้า AI หยุดถามอะไร
    คำถามจะไปโผล่ในหน้าต่างที่ไม่มีใครเปิดดู งานค้างเงียบ ๆ ทั้งวันโดยไม่มีใครรู้

    ตัวนี้เปิดค้างไว้เฉย ๆ บนเครื่อง พนักงานกดปุ่มบนเว็บอย่างเดียว
    ที่เหลือ — รันงาน รายงานความคืบหน้าเป็นภาษาคน ส่งคำถามขึ้นเว็บ รับคำตอบกลับมาทำต่อ —
    เกิดขึ้นที่นี่ทั้งหมด

หลักการที่ห้ามละเมิด (รับมรดกจาก report.py)
    ★ ห้ามทำให้งานหลักล้ม — เว็บล่ม เน็ตหลุด โทเคนหมดอายุ เป็นเรื่องปกติ ไม่ใช่เหตุผล
      ที่จะทิ้งงานที่จ่ายค่าโทเคนไปแล้วครึ่งทาง · ทุกการคุยกับเว็บล้มแล้วเดินต่อได้
    ★ บันทึกดิบทุกบรรทัดลงดิสก์เสมอ ก่อนจะพยายามส่งขึ้นเว็บ
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Queue

HERE = Path(__file__).resolve().parent
for extra in (HERE.parent / "skills" / "shared" / "scripts",):
    if extra.is_dir():
        sys.path.insert(0, str(extra))

import eduone_web as web        # noqa: E402
import stream_reader as sr      # noqa: E402

# ★ ต้องตั้ง EDUONE_WORK_DIR *ก่อน* import _root — โมดูลนั้นคำนวณ WORK_ROOT ตอน import
#   ครั้งเดียว และสคริปต์ลูกทุกตัวก็อ่าน env ตัวเดียวกันนี้ การตั้งทีหลังจึงสายเกินไป
#   (ถ้าไม่ตั้ง _root จะเดินขึ้นหาหมุดจาก cwd — ซึ่งคือบั๊กที่ทำให้ตัวรับงานที่เปิดจาก
#    โฟลเดอร์บ้านมองไม่เห็น BookScan และอัปไฟล์ขึ้นเว็บไม่ได้ทั้งรอบ)
if not os.environ.get("EDUONE_WORK_DIR"):
    _saved = str(web.raw_config().get("work_root") or "").strip()
    if _saved:
        os.environ["EDUONE_WORK_DIR"] = _saved

from _root import WORK_ROOT     # noqa: E402

POLL_SEC = 5                    #: ถามเว็บถี่แค่ไหนตอนไม่มีงาน
IDLE_POLL_SEC = 30              #: ไม่มีงานติดกันนาน ๆ ก็ถามห่างลง (ประหยัดแบตโน้ตบุ๊ก)
IDLE_AFTER = 20                 #: กี่รอบถึงเรียกว่า "ว่างจริง"
FLUSH_SEC = 3                   #: ส่งบันทึกขึ้นเว็บทุกกี่วินาที
SILENT_KILL_SEC = 20 * 60       #: ไม่มีความเคลื่อนไหวเท่านี้ = ค้างแล้ว (เกณฑ์เดียวกับ watch.py)
WALL_KILL_SEC = 4 * 60 * 60     #: คาบหนึ่งนานสุดที่ยอมให้รัน
LOCK_PORT = 47615               #: พอร์ตที่ใช้เป็นล็อกตัวเดียว

#: กติกาสำหรับโหมดไม่มีคนนั่งเฝ้า — ต่อท้าย system prompt เฉพาะโปรเซสที่ตัวนี้เปิด
#
# ★ ทำแบบนี้แทนการแก้ SKILL.md เพราะสกิลมี 17 จุดที่สั่งให้ "ถามผู้ใช้ก่อน / หยุดรอคน"
#   ถ้าไปแก้ที่สกิล พฤติกรรมตอนคนนั่งพิมพ์เองจะเปลี่ยนตามไปด้วย ซึ่งไม่ควร
#   แฟล็กนี้มีผลเฉพาะโปรเซสที่เปิดจากที่นี่ — คนที่พิมพ์ `claude` เองไม่ได้รับผลอะไรเลย
PREAMBLE = """โหมดไม่มีคนนั่งเฝ้า (EDU ONE)
งานนี้ถูกสั่งจากหน้าเว็บ ไม่มีใครนั่งอยู่หน้าจอ ข้อความที่พิมพ์ออกเทอร์มินัลไม่มีใครอ่าน
กฎด้านล่างทับกฎ "ถามผู้ใช้ก่อน" ทุกข้อในสกิล

1. ห้ามหยุดรอคำตอบในเทอร์มินัล และห้ามใช้เครื่องมือ AskUserQuestion
2. ถ้าจำเป็นต้องถามจริง ๆ ให้ปิดท้ายข้อความด้วยบล็อกนี้แล้วหยุด
   <<<EDUONE_ASK
   {"q":"<คำถามภาษาไทยที่ครูอ่านรู้เรื่อง ไม่เกิน 300 ตัวอักษร>","options":["<ตัวเลือกที่ใช้ทำงานต่อได้ทันที>","<อีกตัวเลือก>"]}
   EDUONE_ASK>>>
   ระบบจะเอาไปถามคนบนเว็บ แล้วเรียกคุณกลับมาทำต่อพร้อมคำตอบในเซสชันเดิม
3. ทำจนจบแล้วปิดท้ายด้วย
   <<<EDUONE_DONE {"ok":true,"summary":"<สรุปหนึ่งประโยค>"} EDUONE_DONE>>>
   ไปต่อไม่ได้จริง ๆ ใช้ {"ok":false,"summary":"<เหตุผลหนึ่งประโยค>"}
4. ห้ามถามสิ่งที่หาเองได้จากหลักสูตร ไฟล์ในเครื่อง หรือใบสั่ง — ถามได้ไม่เกิน 3 ครั้งต่อคาบ
5. ผลผลิตที่ถูกพักไว้ (วิดีโอ เกม) ให้ข้ามไปเงียบ ๆ ห้ามถามยืนยัน แล้วบอกไว้ในสรุป
6. เซสชันนี้เป็นเซสชันใหม่ที่เปิดให้งานนี้โดยเฉพาะ ข้อ Preflight ผ่านแล้ว เริ่มงานได้เลย
7. ทำได้ทุกอย่างในโฟลเดอร์งานโดยไม่ต้องขออนุญาต แต่ห้ามแตะไฟล์นอกโฟลเดอร์งาน
   และห้าม commit หรือ push git
"""

#: ถามได้กี่ครั้งต่อการรันหนึ่งใบ — กันวงจรถาม-ตอบไม่รู้จบ
MAX_ASKS = 3

#: จบเทิร์นโดยไม่บอกว่าจบหรือติด สะกิดได้กี่ครั้งก่อนยอมแพ้
MAX_NUDGE = 2


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str) -> None:
    """บันทึกฝั่งเครื่อง — ที่เดียวที่ตอบได้ว่าเมื่อวานมันทำอะไรตอนไม่มีใครดู"""
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  {msg}"
    print(line, flush=True)
    try:
        d = WORK_ROOT / ".eduone-runs"
        d.mkdir(parents=True, exist_ok=True)
        f = d / "runner.log"
        if f.exists() and f.stat().st_size > 5 * 1024 * 1024:
            f.replace(f.with_suffix(".log.1"))
        with f.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


#: ตัวนับข้อความซ้ำของ log_quiet — เว็บล่มทีเดียวได้บรรทัดเดิมวันละพันบรรทัด
_repeat: dict[str, int] = {}


def log_quiet(msg: str, every: int = 20) -> None:
    """ข้อความเดิมซ้ำ ๆ พิมพ์ครั้งแรกครั้งเดียว แล้วย้ำทุก `every` ครั้ง

    เว็บล่มหรือโทเคนหมดอายุ = ตัวรับงานพูดประโยคเดิมทุก 30 วินาทีไม่หยุด บันทึกจริง
    จมหายไปกับมัน และพนักงานที่เปิดหน้าต่างที่ย่อไว้ขึ้นมาดูก็อ่านไม่ออกว่าเกิดอะไรขึ้น
    """
    n = _repeat.get(msg, 0)
    _repeat[msg] = n + 1
    if n == 0:
        log(msg)
    elif n % every == 0:
        log(f"{msg}  (ซ้ำครั้งที่ {n + 1})")


def take_lock() -> socket.socket | None:
    """ล็อกตัวเดียวด้วยพอร์ต ไม่ใช่ไฟล์

    ★ ไฟล์ล็อกจะค้างเสมอเมื่อเครื่องดับกลางคัน แล้วต้องมีโค้ดเดาว่า "ล็อกนี้ตายหรือยัง"
      ส่วนพอร์ตนั้นระบบปฏิบัติการปล่อยคืนให้เองทันทีที่โปรเซสตาย ไม่ต้องเดาอะไรเลย
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", LOCK_PORT))
        s.listen(1)
        return s
    except OSError:
        s.close()
        return None


def kill_tree(proc: subprocess.Popen) -> None:
    """ฆ่าทั้งต้นไม้ ไม่ใช่แค่ตัวแม่

    claude เปิดโปรเซสลูกอีกหลายตัว ถ้าฆ่าแต่ตัวแม่ ลูกจะกลายเป็นผีที่ยังกินโทเคนต่อ
    """
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, timeout=30)
        else:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
    except Exception as exc:                       # noqa: BLE001
        log(f"ฆ่าโปรเซสไม่สำเร็จ: {exc}")


class Web:
    """ตัวคุยกับเว็บที่ล้มแล้วไม่ทำให้งานหลักตาย"""

    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.machine_id = 0
        self.last_error = ""      #: ตัวเรียกต้องแยกให้ออกว่า "เน็ตสะดุด" หรือ "โทเคนตาย"

    def call(self, fn, *a, **kw):
        try:
            return fn(self.cfg, *a, **kw)
        except web.WebError as exc:
            self.last_error = str(exc)
            log_quiet(f"เว็บไม่ตอบ: {exc}")
            return None
        except Exception as exc:                   # noqa: BLE001
            self.last_error = str(exc)
            log_quiet(f"คุยกับเว็บพลาด: {exc}")
            return None

    def hello(self) -> bool:
        got = self.call(web.post_json, "/api/runner/hello", {
            "name": platform.node(), "work_root": str(WORK_ROOT),
            "version": plugin_version(),
        })
        if got and got.get("machine_id"):
            self.machine_id = got["machine_id"]
            return True
        return False

    def next_run(self):
        got = self.call(web.get, "/api/runner/next", {"machine_id": self.machine_id})
        return (got or {}).get("run")

    # ★ ทุกเส้นรับ `ep` ("/api/runs/12" หรือ "/api/tasks/12") ไม่ใช่ run_id เปล่า —
    #   เว็บมีกระดานงานสองชุด (ใบสั่งผลิตสื่อ · งานคลังหนังสือ) ที่เลข id คนละชุดกัน
    #   ถ้าประกอบ path จาก id อย่างเดียว งานถอดสารบัญใบที่ 12 จะไปปิดใบสั่งที่ 12 แทน

    def events(self, ep: str, rows: list) -> str:
        got = self.call(web.post_json, f"{ep}/events", {"events": rows})
        return (got or {}).get("status", "")

    def ask(self, ep: str, payload: dict):
        return self.call(web.post_json, f"{ep}/ask", payload)

    def advance(self, ep: str, cmd_index: int, session_id):
        return self.call(web.post_json, f"{ep}/advance",
                         {"cmd_index": cmd_index, "session_id": session_id})

    def finish(self, ep: str, status: str, reason: str, usage: dict):
        return self.call(web.post_json, f"{ep}/finish",
                         {"status": status, "reason": reason, "usage": usage})


def plugin_version() -> str:
    try:
        data = json.loads((HERE.parent / ".claude-plugin" / "plugin.json")
                          .read_text(encoding="utf-8"))
        return str(data.get("version") or "")
    except Exception:                              # noqa: BLE001
        return ""


def build_cmd(prompt: str, resume: str | None) -> list[str]:
    """คำสั่ง claude ที่จะรันจริง

    ★ --permission-mode bypassPermissions เพราะไม่มีใครนั่งกดอนุญาต — ทดสอบแล้วว่า
      แฟล็กตัวเดียวนี้พอ ไม่ต้องใส่ --dangerously-skip-permissions ซ้ำ
    ★ --model opus ระบุตรง ๆ ตามนโยบายโมเดลของโปรเจกต์ ไม่ปล่อยให้ค่าเริ่มต้นของ
      เครื่องแต่ละคนเป็นคนตัดสิน
    ★ ไม่ใส่ --add-dir: cwd คือโฟลเดอร์งานอยู่แล้ว การเพิ่มไดเรกทอรีอื่นคือการขยาย
      ขอบเขตที่สิทธิ์เต็มเอื้อมถึง ซึ่งขัดกับข้อตกลงว่า "ทำได้ทุกอย่างในโฟลเดอร์งาน"
    """
    exe = "claude"
    cmd = [exe, "-p", prompt, "--output-format", "stream-json", "--verbose",
           "--permission-mode", "bypassPermissions", "--model", "opus",
           "--append-system-prompt", PREAMBLE,
           "--disallowed-tools", "AskUserQuestion"]
    if resume:
        cmd += ["--resume", resume]
    return cmd


class Job:
    """รันใบสั่งหนึ่งใบจนจบ หรือจนกว่าจะติดคำถาม"""

    def __init__(self, wb: Web, run: dict, fake: str | None = None) -> None:
        self.wb = wb
        self.run = run
        self.fake = fake
        self.run_id = run["run_id"]
        # งานคลังหนังสือ (ถอดสารบัญ/ถอดเนื้อหา) เดินท่อเดียวกันหมด ต่างแค่ปลายทาง
        self.is_task = run.get("kind") == "task"
        self.ep = f"/api/{'tasks' if self.is_task else 'runs'}/{self.run_id}"
        self.base = run.get("base") or f"run{self.run_id}"
        self.prompts = run.get("prompts") or []
        # นับต่อจากที่เว็บมีอยู่แล้ว ไม่เริ่มหนึ่งใหม่ — ใบที่ถูกพักไว้รอคำตอบจะถูกหยิบ
        # ไปทำต่อโดยโปรเซสใหม่ ถ้านับซ้ำเลขเดิม บันทึกรอบสองจะถูกกลืนหายทั้งชุด
        self.seq = int(run.get("last_seq") or 0)
        self.asks = 0
        self.pending: list[dict] = []
        self.session_id = run.get("session_id")
        self.raw = WORK_ROOT / ".eduone-runs" / f"{self.base}-run{self.run_id}.jsonl"

    # ---------- บันทึก ----------

    def add(self, kind: str, actor, detail: str) -> None:
        self.seq += 1
        self.pending.append({"seq": self.seq, "at": now_utc(), "kind": kind,
                             "actor": actor, "detail": detail})

    def flush(self) -> str:
        if not self.pending:
            return ""
        rows, self.pending = self.pending, []
        status = self.wb.events(self.ep, rows)
        if status == "":
            # ส่งไม่ผ่าน — เอากลับเข้าคิวไว้ลองใหม่รอบหน้า ห้ามทิ้ง
            self.pending = rows + self.pending
        return status

    def write_raw(self, line: str) -> None:
        try:
            self.raw.parent.mkdir(parents=True, exist_ok=True)
            with self.raw.open("a", encoding="utf-8") as fh:
                fh.write(line if line.endswith("\n") else line + "\n")
        except OSError:
            pass

    # ---------- รันหนึ่งคำสั่ง ----------

    def spawn(self, prompt: str, resume):
        if self.fake:
            return None
        cmd = build_cmd(prompt, resume)
        env = dict(os.environ, PYTHONIOENCODING="utf-8", EDUONE_UNATTENDED="1",
                   # ★ ตอกโฟลเดอร์งานลง env ให้สคริปต์ลูกทุกตัวเห็นค่าเดียวกับที่ตรวจไปแล้ว
                   #   ไม่ปล่อยให้แต่ละตัวเดาจาก cwd เอง
                   EDUONE_WORK_DIR=str(WORK_ROOT),
                   # ★ docs/rag/eduone_api.py อ่านเฉพาะ EDUONE_URL/EDUONE_TOKEN (ไม่รู้จัก
                   #   ~/.eduone/config.json) — ไม่ส่งให้ งานถอดสารบัญจะตายที่ "ยังไม่ได้ตั้ง
                   #   EDUONE_URL" ทั้งที่เครื่องต่อเว็บได้อยู่แล้ว
                   EDUONE_URL=self.wb.cfg["url"], EDUONE_TOKEN=self.wb.cfg["token"])
        log(f"รัน: {prompt[:80]}" + (f" (ต่อจากเซสชันเดิม {resume[:8]})" if resume else ""))
        return subprocess.Popen(
            cmd, cwd=str(WORK_ROOT), env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1)

    def read_lines(self, proc, out: Queue) -> None:
        """เธรดอ่านอย่างเดียว — ห้ามยิงเน็ตในนี้ ไม่งั้น buffer เต็มแล้วโปรเซสลูกค้าง"""
        try:
            src = (open(self.fake, encoding="utf-8") if self.fake else proc.stdout)
            for line in src:
                out.put(line)
                if self.fake:
                    time.sleep(0.02)
            if self.fake:
                src.close()
        except Exception as exc:                   # noqa: BLE001
            log(f"อ่านสตรีมพลาด: {exc}")
        finally:
            out.put(None)

    def one(self, prompt: str, resume) -> dict:
        """รันคำสั่งเดียวจนจบ — คืน {outcome: done|ask|fail, ...}"""
        proc = self.spawn(prompt, resume)
        q: Queue = Queue()
        threading.Thread(target=self.read_lines, args=(proc, q), daemon=True).start()

        said: list[str] = []
        usage: dict = {}
        started = last_move = time.time()
        last_flush = 0.0
        result_seen = False

        while True:
            try:
                line = q.get(timeout=1)
            except Empty:
                line = ""
            if line is None:
                break
            if line:
                last_move = time.time()
                self.write_raw(line)
                text = line.strip()
                if text.startswith("{"):
                    try:
                        ev = json.loads(text)
                    except ValueError:
                        ev = None
                    if ev is not None:
                        self.handle(ev, said)
                        u = sr.usage_of(ev)
                        if u:
                            usage, result_seen = u, True
                        if (ev.get("type") == "system"
                                and ev.get("subtype") == "init" and ev.get("session_id")):
                            self.session_id = ev["session_id"]

            now = time.time()
            if now - last_flush > FLUSH_SEC:
                last_flush = now
                state = self.flush()
                if state in ("cancelled", "failed"):
                    log("เว็บบอกว่างานนี้ถูกปิดไปแล้ว — หยุดโปรเซส")
                    if proc:
                        kill_tree(proc)
                    return {"outcome": "fail", "reason": "ถูกสั่งหยุดจากเว็บ", "usage": usage}
            if now - last_move > SILENT_KILL_SEC:
                if proc:
                    kill_tree(proc)
                return {"outcome": "fail", "usage": usage,
                        "reason": f"ไม่มีความเคลื่อนไหว {SILENT_KILL_SEC // 60} นาที — หยุดให้แล้ว"}
            if now - started > WALL_KILL_SEC:
                if proc:
                    kill_tree(proc)
                return {"outcome": "fail", "usage": usage,
                        "reason": f"งานเกิน {WALL_KILL_SEC // 3600} ชั่วโมง — หยุดให้แล้ว"}

        code = proc.wait() if proc else 0
        self.flush()
        blob = "\n".join(said)
        ask = sr.find_ask(blob)
        done = sr.find_done(blob)
        if ask:
            return {"outcome": "ask", "ask": ask, "usage": usage}
        if done and not done["ok"]:
            return {"outcome": "fail", "reason": done["summary"] or "AI แจ้งว่าไปต่อไม่ได้",
                    "usage": usage}
        if code not in (0, None):
            return {"outcome": "fail", "usage": usage,
                    "reason": f"คำสั่งจบด้วยรหัสข้อผิดพลาด {code}"}
        if usage.get("denials"):
            # tool ถูกปฏิเสธสิทธิ์ = งานเดินต่อแบบพิการ ซึ่งมองจากเว็บแยกไม่ออกจากงานที่สำเร็จ
            return {"outcome": "fail", "usage": usage,
                    "reason": "มีคำสั่งถูกปฏิเสธสิทธิ์ระหว่างทาง — ผลงานอาจไม่ครบ"}
        if usage.get("is_error"):
            return {"outcome": "fail", "usage": usage, "reason": "รอบนี้จบแบบผิดพลาด"}
        if not result_seen and not self.fake:
            return {"outcome": "fail", "usage": usage,
                    "reason": "โปรเซสจบโดยไม่มีผลสรุป — ดูบันทึกดิบในเครื่อง"}
        return {"outcome": "done", "summary": (done or {}).get("summary", ""),
                "usage": usage}

    def handle(self, ev: dict, said: list) -> None:
        row = sr.to_event(ev)
        if row:
            self.add(row["kind"], row["actor"], row["detail"])
        text = sr.assistant_text(ev)
        if text:
            said.append(text)

    # ---------- รันทั้งใบ ----------

    def go(self) -> None:
        total = len(self.prompts)
        idx = int(self.run.get("cmd_index") or 0)
        resume = self.session_id if self.run.get("answer") else None
        answer = self.run.get("answer")
        spent: dict = {}          #: usage ของคำสั่งล่าสุด — ต้องส่งขึ้นเว็บตอนจบด้วย

        while idx < total:
            prompt = self.prompts[idx]
            if answer:
                # ตอบคำถามแล้วกลับเข้าเซสชันเดิม ไม่เริ่มคาบใหม่
                prompt = (f"ตอบคำถามที่ถามไว้: {answer}\n\n"
                          "ทำงานต่อจากจุดเดิม ห้ามเริ่มใหม่ และห้ามทำสิ่งที่ทำไปแล้วซ้ำ")
                self.add("say", None, f"ได้รับคำตอบจากเว็บ: {answer[:120]}")
            else:
                resume = None
            out = self.one(prompt, resume)
            answer, resume = None, None
            spent = out.get("usage") or spent

            if out["outcome"] == "ask":
                # งานคลังหนังสือไม่มีที่ให้ค้างรอคำตอบบนเว็บ (ไม่มีหน้าใบสั่งให้ตอบ)
                # และคำถามระหว่างถอดแปลว่าติดจริง — ปิดงานพร้อมคำถามเป็นเหตุผลให้คนอ่าน
                if self.is_task:
                    reason = "AI ถามกลับ: " + out["ask"]["question"]
                    self.add("error", None, reason)
                    self.flush()
                    self.wb.finish(self.ep, "failed", reason, out["usage"])
                    log(f"งานถอดไม่จบ: {reason}")
                    return
                self.asks += 1
                if self.asks > MAX_ASKS:
                    self.wb.finish(self.ep, "failed",
                                   f"ถามเกิน {MAX_ASKS} ครั้งในการรันเดียว", out["usage"])
                    return
                self.add("ask", None, out["ask"]["question"])
                self.flush()
                self.wb.ask(self.ep, {
                    "question": out["ask"]["question"], "options": out["ask"]["options"],
                    "session_id": self.session_id, "cmd_index": idx})
                log("AI ถามคำถาม — พักใบนี้ไว้รอคนตอบบนเว็บ")
                return

            if out["outcome"] == "fail":
                self.add("error", None, out.get("reason", ""))
                self.flush()
                self.wb.finish(self.ep, "failed", out.get("reason", ""), out["usage"])
                log(f"งานไม่จบ: {out.get('reason')}")
                return

            idx += 1
            if idx < total:
                self.wb.advance(self.ep, idx, None)
                self.session_id = None

        self.add("result", None, "ทำครบทุกคำสั่งของใบสั่งนี้แล้ว")
        self.flush()
        # ★ ต้องส่ง usage จริง ไม่ใช่ {} — ของเดิมส่งก้อนว่างเฉพาะทางที่ "สำเร็จ"
        #   ค่าโทเคนของงานที่ทำเสร็จจึงหายทุกใบ (ทางที่ล้มเหลวส่งถูกมาตลอด)
        #   และ CLAUDE.md ข้อ 6 บังคับว่าต้องรายงาน token ทุกครั้งที่จบงาน
        self.wb.finish(self.ep, "done", "", spent)
        log("งานจบเรียบร้อย")
        if not self.is_task:
            self.upload()

    def upload(self) -> None:
        """ส่งไฟล์ต้นฉบับขึ้นใบสั่งด้วยตัวเดิม — ไม่เขียนตรรกะการอัปซ้ำ"""
        try:
            import report
            topic = report.topic_dir_of(self.run.get("grade"), self.run.get("subject"),
                                        self.run.get("no"))
            if topic:
                report.run(topic, verbose=False, do_upload=True, force=True)
        except Exception as exc:                   # noqa: BLE001
            log(f"ส่งไฟล์ขึ้นเว็บไม่สำเร็จ (ไฟล์ยังอยู่ในเครื่อง): {exc}")


def check_work_root() -> str:
    """โฟลเดอร์งานใช้ได้ไหม — คืน "" ถ้าผ่าน หรือข้อความบอกวิธีแก้ถ้าไม่ผ่าน

    ★ ทำไมต้อง "ไม่ผ่านไม่รัน" ไม่ใช่แค่เตือน: การรันผิดโฟลเดอร์ไม่ทำให้อะไรพังตรง ๆ
      มันแค่ทำงานผิดที่แบบเงียบสนิท — AI ไล่หา BookScan ไม่เจอแล้วเดาเอง · report.py
      อัปไฟล์ขึ้นเว็บไม่ได้เพราะหา Output ไม่เจอ · หน้าใบสั่งค้างที่ 3/5 ทั้งที่ไฟล์ครบ
      แล้วในเครื่อง กว่าจะรู้ตัวก็จ่ายค่าโทเคนไปทั้งรอบแล้ว (เกิดจริง 2026-09-04)
    """
    home = Path.home().resolve()
    root = WORK_ROOT.resolve()
    fix = (f'ตั้งครั้งเดียวด้วย  eduone-py runner.py --work "<โฟลเดอร์งานของคุณ>"\n'
           f'  แล้วเปิดใหม่ · หรือรันตัวช่วยติดตั้งอีกครั้งก็ตั้งให้เหมือนกัน\n'
           f'  (ค่าที่จดไว้อยู่ในช่อง work_root ของ {web.CONFIG_FILE})')
    # "เลือกไว้" = มีคนบอกมาตรง ๆ (ไฟล์ตั้งค่า หรือ env) ต่างจาก "เดามาจาก cwd"
    chosen = bool(str(web.raw_config().get("work_root") or "").strip()
                  or os.environ.get("EDUONE_WORK_DIR"))
    if not root.is_dir():
        return f"โฟลเดอร์งานที่ตั้งไว้ไม่มีอยู่จริง: {root}\n  {fix}"
    if root == home:
        # โฟลเดอร์บ้านไม่เคยเป็นโฟลเดอร์งาน — มันคือค่าที่ได้มาตอน "หาไม่เจอเลย"
        return (f"โฟลเดอร์บ้าน ({root}) ไม่ใช่โฟลเดอร์งาน — ตัวรับงานถูกเปิดจากที่นี่\n"
                f"  {fix}")
    if not chosen and not any((root / m).exists() for m in ("Output", "BookScan", "CLAUDE.md")):
        # เดามาจาก cwd และที่นั่นก็ไม่มีเค้าโครงของโฟลเดอร์งานเลย = เดาผิดแน่ ๆ
        # (โฟลเดอร์งานที่ *เลือกไว้* ยังว่างได้ตามปกติ — เพิ่งสร้าง ยังไม่เคยทำงานสักใบ)
        return (f"ยังไม่ได้บอกว่าโฟลเดอร์งานอยู่ที่ไหน — ที่เดาได้ตอนนี้คือ {root}\n"
                f"  ซึ่งไม่มี Output/ หรือ BookScan/ อยู่เลย จึงไม่เริ่มงานให้\n  {fix}")
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="ตัวรับงานประจำเครื่องของ EDU ONE")
    ap.add_argument("--once", action="store_true", help="ทำงานที่ค้างอยู่ใบเดียวแล้วออก")
    ap.add_argument("--fake", help="ไฟล์ .jsonl ตัวอย่าง — ไม่เรียก claude จริง (ไว้ทดสอบ)")
    ap.add_argument("--work", help="จดโฟลเดอร์งานลงไฟล์ตั้งค่าแล้วใช้ค่านี้ตั้งแต่ครั้งนี้")
    a = ap.parse_args()

    if a.work:
        p = Path(a.work).expanduser()
        if not p.is_dir():
            print(f"ไม่มีโฟลเดอร์ {p} — สร้างก่อนแล้วสั่งใหม่")
            return 2
        print(f"จดโฟลเดอร์งานไว้ที่ {web.save_work_root(str(p.resolve()))}")
        # ตั้ง env ให้รอบนี้ด้วย แต่ WORK_ROOT ถูกคำนวณไปตั้งแต่ตอน import แล้ว
        # จึงต้องให้ผู้ใช้เปิดใหม่ ไม่ใช่แกล้งเดินต่อด้วยค่าเก่า
        print("ตั้งค่าแล้ว — เปิดตัวรับงานใหม่อีกครั้งได้เลย")
        return 0

    lock = take_lock()
    if not lock:
        print("มีตัวรับงานเปิดอยู่แล้วบนเครื่องนี้ — ไม่เปิดซ้ำ")
        return 1

    problem = check_work_root()
    if problem:
        log("ไม่เริ่มงาน — โฟลเดอร์งานยังไม่ถูกต้อง:\n  " + problem)
        return 2

    log(f"ตัวรับงานเริ่มทำงาน · โฟลเดอร์งาน {WORK_ROOT}")
    idle = 0
    down = 0                      #: ทักเว็บไม่ติดติดกันกี่รอบแล้ว
    while True:
        cfg = web.config()
        if not cfg:
            log_quiet(web.last_problem or
                      "ยังไม่ได้ตั้งค่าที่อยู่เว็บกับโทเคน — รอไปก่อน (รันตัวช่วยติดตั้งข้อ 7)")
            time.sleep(60)
            continue
        wb = Web(cfg)
        if not wb.hello():
            # ★ 401/403 = โทเคนตาย ไม่ใช่เน็ตสะดุด — รอไปอีกกี่ชั่วโมงก็ไม่หายเอง
            #   ต้องบอกให้ชัดว่าไปกดตรงไหน ไม่ใช่พ่น "HTTP 401 Unauthorized" ซ้ำ ๆ
            #   ให้พนักงานที่ไม่ได้เป็นคนสายคอมนั่งอ่าน (เกิดจริงกับเครื่องแรกที่ติดตั้ง)
            if "HTTP 401" in wb.last_error or "HTTP 403" in wb.last_error:
                log_quiet(f"โทเคนใช้ไม่ได้แล้ว — เปิด {cfg['url']}/me/tokens ออกใบใหม่ "
                          f"แล้ววางทับใน {web.CONFIG_FILE} (หรือรันตัวช่วยติดตั้งซ้ำ ข้อ 7/7)")
            down += 1
            time.sleep(30)
            continue
        if down:
            _repeat.clear()       # พังใหม่คราวหน้าจะได้พิมพ์เต็มอีกครั้ง ไม่ถูกกลืนหายไป
            log(f"ต่อเว็บได้แล้ว (พลาดไป {down} รอบ)")
            down = 0

        run = wb.next_run()
        if not run:
            idle += 1
            if a.once:
                log("ไม่มีงานค้าง")
                return 0
            time.sleep(IDLE_POLL_SEC if idle > IDLE_AFTER else POLL_SEC)
            continue

        idle = 0
        if run.get("kind") == "task":
            log(f"รับงานคลังหนังสือ: {run.get('label') or run.get('base')}")
        else:
            log(f"รับงาน: ใบสั่ง #{run.get('job_id')} · {run.get('base')}")
        try:
            Job(wb, run, fake=a.fake).go()
        except Exception as exc:                   # noqa: BLE001
            # งานใบเดียวล้มต้องไม่ทำให้ตัวรับงานหยุดทั้งวัน
            log(f"งานใบนี้พังกลางคัน: {exc}")
            ep = f"/api/{'tasks' if run.get('kind') == 'task' else 'runs'}/{run['run_id']}"
            wb.finish(ep, "failed", f"ตัวรับงานพลาด: {exc}", {})
        if a.once:
            return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nปิดตัวรับงานแล้ว — งานที่รันอยู่บนเครื่องไม่ได้ถูกหยุดไปด้วย")
        raise SystemExit(0)
