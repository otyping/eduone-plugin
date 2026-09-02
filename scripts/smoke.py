# -*- coding: utf-8 -*-
"""ทดสอบว่าโครงของ pipeline ยังต่อกันติด โดยไม่เรียก agent และไม่กินโควตา

    eduone-py smoke.py

ใช้เมื่อไร
  · หลังติดตั้ง/อัปเดตปลั๊กอิน — พิสูจน์ว่าใช้งานได้จริงก่อนสั่งงานยาว ๆ
  · หลังแก้อะไรที่แตะ path · BASE · หรือกฎตรวจ spec

★ ทำไมต้องมีทั้งที่มี doctor.py แล้ว
  `doctor.py` ตอบว่า "เครื่องพร้อมไหม" (มี python · มีแพ็กเกจ · มีปลั๊กอิน)
  ไฟล์นี้ตอบว่า "ตรรกะยังถูกไหม" — คำถามคนละข้อ และข้อหลังคือข้อที่พังเงียบ ๆ
  ตอนเปลี่ยนโครงสร้าง เช่นตอนหลักสูตรเพิ่มชั้น "คาบ" เข้ามา

เทียบหลักสูตร 2 แบบทุกข้อเสมอ
  รายคาบ (m1 math)   BASE 4 ท่อน โฟลเดอร์ซ้อน 1 ชั้น
  แบบเดิม (p4 sci)   BASE 3 ท่อน — **ต้องไม่เปลี่ยนอะไรเลย**
เพราะบั๊กส่วนใหญ่ตอนเพิ่มชั้นใหม่ ไม่ได้ทำให้ของใหม่พัง แต่ทำให้ของเดิมพันแทน
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "skills" / "shared" / "scripts"
sys.path.insert(0, str(SCRIPTS))

WORK = Path(tempfile.gettempdir()) / "eduone_smoke"
if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)
WORK.mkdir(parents=True, exist_ok=True)
os.environ["EDUONE_WORK_DIR"] = str(WORK)     # ต้องตั้งก่อน import _root

import no_to_token as ntt   # noqa: E402
import paths as pathmod     # noqa: E402

PY = sys.executable
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}
fails: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    if not ok:
        fails.append(label)
    print(f"  {'ผ่าน ' if ok else '★ ตก'} {label}" + (f"   {detail}" if detail else ""))


def head(n: int, title: str) -> None:
    print(f"\n{n}. {title}\n" + "-" * 70)


def run(*args: str) -> tuple[int, str]:
    r = subprocess.run([PY, *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=ENV)
    return r.returncode, (r.stdout + r.stderr).strip()


def last(text: str) -> str:
    return text.splitlines()[-1][:90] if text else ""


CASES = [("m1", "math", 9, "รายคาบ"), ("p4", "sci", 3, "แบบเดิม")]
loaded: dict[tuple[str, str], tuple[dict, dict]] = {}

head(1, "โฟลเดอร์ผลผลิตซ้อนถูกชั้น")
for g, s, no, kind in CASES:
    try:
        meta = ntt.no_to_token(g, s, no)
    except Exception as exc:                  # หลักสูตรหาย = จบตั้งแต่ต้น บอกให้ชัด
        check(f"{g} {s} — อ่านหลักสูตรได้", False, f"{type(exc).__name__}: {exc}")
        continue
    pp = pathmod.topic_paths(meta)
    loaded[(g, s)] = (meta, pp)
    for d in pp["dirs"].values():
        (WORK / d).mkdir(parents=True, exist_ok=True)

    tdir = WORK / meta["topic_dir"]
    want = 7 if meta["period"] else 6         # Output/G/S/หน่วย/[หัวข้อ/]BASE/หมวด/ไฟล์
    check(f"{g} {s} ({kind}) — ความลึกของ path",
          pp["content_c1_json"].count("/") == want, meta["base"])
    check(f"{g} {s} — สร้างโฟลเดอร์หมวดครบ", len(list(tdir.iterdir())) >= 7)
    if meta["period"]:
        check("โฟลเดอร์คาบอยู่ใต้โฟลเดอร์หัวข้อหลัก",
              tdir.parent.name == meta["topic_folder"], tdir.parent.name)
        check("โฟลเดอร์หัวข้อหลักอยู่ใต้โฟลเดอร์หน่วย",
              tdir.parent.parent.name == meta["unit_folder"], tdir.parent.parent.name)

head(2, "ผลผลิตระดับหน่วยไม่หลุดไปอยู่ในโฟลเดอร์หัวข้อ")
for (g, s), (meta, _) in loaded.items():
    up = pathmod.unit_paths(meta)
    exp = f"Output/{meta['grade_token']}/{meta['subject_token']}/{meta['unit_folder']}"
    check(f"{g} {s} — unit_dir คือโฟลเดอร์หน่วยจริง", up["unit_dir"] == exp, up["unit_dir"])

head(3, "ชื่อไฟล์ทุกผลผลิตขึ้นต้นด้วย BASE")
SKIP = {"base", "dirs", "prereq"}
for (g, s), (meta, pp) in loaded.items():
    bad = [f"{k}={x.rsplit('/', 1)[-1]}"
           for k, v in pp.items() if k not in SKIP
           for x in (v.values() if isinstance(v, dict) else [v])
           if not x.rsplit("/", 1)[-1].startswith(meta["base"])]
    check(f"{g} {s} — ทุกไฟล์ขึ้นต้นด้วย {meta['base']}", not bad, "; ".join(bad[:2]))

head(4, "metadata ที่ writer/checkwork ต้องใช้")
NEED = ("grade", "subject", "subject_code", "no", "unit", "unit_name", "order",
        "topic_name", "main_topic_name", "period", "obj", "comp", "base",
        "topic_dir", "topic_folder", "unit_folder", "header")
for (g, s), (meta, _) in loaded.items():
    miss = [k for k in NEED if k not in meta]
    check(f"{g} {s} — คีย์ครบ {len(NEED)} ตัว", not miss, "ขาด " + ", ".join(miss))
    check(f"{g} {s} — OBJ ของหน่วย + COMP ของคาบไม่ว่าง",
          bool(meta["obj"] and meta["comp"]))
    check(f"{g} {s} — comp_source บอกที่มาของ COMP",
          meta.get("comp_source") in ("period", "unit_outcome"),
          str(meta.get("comp_source")))

# ---------------------------------------------------------------- ประตูตรวจ
def question(i: int, diff: str) -> dict:
    return {"text": f"ข้อ {i} — ผลคูณของ (-3) กับ {i} เท่ากับเท่าใด",
            "imageUrl": "", "audioUrl": "", "imageAlt": "", "audioText": "",
            "choices": [{"contentType": "text", "content": str(-3 * i), "isTrue": True},
                        {"contentType": "text", "content": str(3 * i), "isTrue": False},
                        {"contentType": "text", "content": str(-3 - i), "isTrue": False},
                        {"contentType": "text", "content": str(3 + i), "isTrue": False}],
            "difficulty": diff,
            "solutionSteps": f"ลบคูณบวกได้ลบ · 3 x {i} = {3 * i} จึงได้ {-3 * i}"}


def spec(counts: tuple[int, int, int]) -> dict:
    qs, i = [], 1
    for diff, n in zip(("easy", "medium", "hard"), counts):
        for _ in range(n):
            qs.append(question(i, diff))
            i += 1
    return {"questions": qs}


def write(name: str, counts: tuple[int, int, int]) -> Path:
    p = WORK / name
    p.write_text(json.dumps(spec(counts), ensure_ascii=False, indent=2), encoding="utf-8")
    return p


head(5, "ประตูตรวจโควตาความยาก — ต้องปล่อยที่ถูกและจับที่ผิด")
VS = str(SCRIPTS / "validate_spec.py")
rc, out = run(VS, "exercise", str(write("ok30.json", (15, 8, 7))))
check("30 ข้อ 15/8/7 ผ่าน", rc == 0, last(out))
rc, out = run(VS, "exercise", str(write("ok20.json", (10, 5, 5))))
check("20 ข้อ 10/5/5 ยังผ่าน (ของเดิมไม่พัง)", rc == 0, last(out))
rc, out = run(VS, "exercise", str(write("bad30.json", (10, 10, 10))))
check("30 ข้อ 10/10/10 ถูกจับ", rc != 0,
      next((l.strip() for l in out.splitlines() if "โควตา" in l), "ไม่มีข้อความเตือน")[:80])

head(6, "สร้าง .docx จริงที่ path ซ้อนลึก แล้วตรวจกลับ")
if ("m1", "math") in loaded:
    meta, pp = loaded[("m1", "math")]
    ex_json, ex_docx = WORK / pp["ex_json"], WORK / pp["exercise_docx"]
    shutil.copy(WORK / "ok30.json", ex_json)
    rc, out = run(str(SCRIPTS / "build_exercise.py"), str(ex_json), str(ex_docx),
                  "--header", meta["header"], "--expect", "30")
    check("build_exercise.py สร้างไฟล์ได้", rc == 0 and ex_docx.is_file(),
          f"{ex_docx.stat().st_size // 1024} KB" if ex_docx.is_file() else last(out))
    if ex_docx.is_file():
        rc, out = run(str(SCRIPTS / "verify_docx.py"), "exercise", str(ex_json),
                      str(ex_docx), "--header", meta["header"])
        check("verify_docx.py ตรวจผ่าน", rc == 0, last(out))

shutil.rmtree(WORK, ignore_errors=True)
print("\n" + "=" * 70)
if fails:
    print(f"★ ไม่ผ่าน {len(fails)} ข้อ")
    for f in fails:
        print(f"    {f}")
    print("\nอย่าเพิ่งสั่งงานยาว ๆ — แก้ให้ผ่านก่อน")
else:
    print("ผ่านทุกข้อ — โครงของ pipeline ต่อกันติด พร้อมสั่งงานจริง")
sys.exit(1 if fails else 0)
