"""ตรวจหน้าหนังสือที่ถอดแล้ว (คลัง `pages/pNNN.json`) — ★ ตัวตรวจชุดเดียวของทั้งระบบ

ใช้สองฝั่งเหมือน `toc_schema.py`:
  · เซิร์ฟเวอร์  `PUT /api/books/<id>/pages/<หน้า>` เรียกก่อนเก็บลงฐานข้อมูล
  · เครื่องพนักงาน `docs/rag/validate_ocr.py` และ `ocr_page.py file` เรียกก่อนเก็บเข้าคลัง

★ **ต้นฉบับอยู่ที่นี่ (ปลั๊กอิน) ตั้งแต่ 3.4.0** — `webapp/app/page_schema.py` เป็น *สำเนา*
  ที่ `webapp/scripts/sync_from_plugin.py` คัดลอกมา แก้ที่นี่ที่เดียวแล้ว sync
  (ก่อนหน้านี้ webapp เป็นเจ้าของ แล้วสคริปต์ฝั่งเครื่อง import ข้ามเข้าไป —
   ซึ่งบังคับให้ทุกเครื่องที่จะถอดหนังสือต้องมี repo ของเว็บติดไปด้วย)
  `sync_from_plugin.py --check` ฟ้องทันทีถ้าสองฝั่งไม่ตรงกัน

ทำไมต้องชุดเดียว: ถ้าสองฝั่งตรวจคนละกฎ พนักงานจะเจอ "ในเครื่องผ่าน แต่เซิร์ฟเวอร์ปฏิเสธ"
โดยไม่รู้ว่ากฎไหนต่าง — และหน้าที่ถอดแล้วส่งขึ้นไม่ได้คือเงินที่จ่ายทิ้ง (~7.6 บาท/หน้า)

ทำไมไฟล์นี้อยู่ใน `app/`: Dockerfile คัดลอกแค่ `app/` กับ `reference/` เข้าคอนเทนเนอร์
ฝั่ง CLI จึงเป็นตัวห่อบาง ๆ ที่ import ไฟล์นี้ตาม path (ไม่ใช่กลับกัน)
เพราะเหตุนี้ไฟล์นี้ต้องเป็น **stdlib ล้วน** — ห้าม import fastapi/minio/db

★ กฎที่สำคัญที่สุดคือ **`printed_page` ต้องเท่ากับ `printed_page_seen`** — เลขที่สั่งถอด
  เทียบกับเลขที่ agent อ่านจากกระดาษจริง · ไม่ตรง = ภาพสลับหน้ากันตอนส่งเป็นชุด
  ปล่อยผ่าน 1 หน้าแปลว่าคลังมีเนื้อหาผูกกับเลขหน้าผิด แล้วทุกการอ้างอิงหลังจากนั้นผิดตาม
  (หน้าที่ไม่มีเลขพิมพ์บนกระดาษจึงเข้าคลังไม่ได้ — ยืนยันไม่ได้ว่าเป็นหน้าที่สั่ง)
"""
from __future__ import annotations

import re

# Problem/ERROR/WARN เป็นเครื่องรายงานผลกลาง ไม่ได้ผูกกับสารบัญ — ใช้ชุดเดียวกันเพื่อให้
# ทั้งเว็บและ CLI แสดงผลของตัวตรวจทั้งสองด้วยโค้ดเดียว (p.as_dict() / str(p))
# ★ import สองทางโดยตั้งใจ — ไฟล์นี้ถูกใช้สองบริบทและต้องเป็นไฟล์เดียวกันเป๊ะ
#   ในเว็บมันเป็น `app.page_schema` (แพ็กเกจ) · ในปลั๊กอินมันเป็นสคริปต์เดี่ยว
#   ในโฟลเดอร์แบน ๆ ที่ไม่มี __init__.py · ถ้าแยกเป็นสองไฟล์เมื่อไร กฎตรวจของ
#   เซิร์ฟเวอร์กับของเครื่องจะเริ่มไม่ตรงกัน ซึ่งคือสิ่งที่ไฟล์นี้มีไว้เพื่อกันตั้งแต่แรก
try:
    from .toc_schema import ERROR, WARN, Problem, has_error  # noqa: F401  (ส่งต่อให้ผู้เรียก)
except ImportError:                                          # noqa: F401
    from toc_schema import ERROR, WARN, Problem, has_error   # noqa: F401

SCHEMA_VERSION = "v0.1"

#: ฟิลด์ที่ขาดไม่ได้ — ครึ่งหนึ่งสคริปต์เติมให้ (envelope) อีกครึ่งมาจาก agent
REQUIRED = ("schema_version", "book_id", "grade", "subject",
            "printed_page", "printed_page_seen", "page_kind", "text_md", "confidence")

PAGE_KINDS = {"content", "activity", "concept_map", "exercise", "front_matter"}

#: <ชั้น>-<วิชา>-<เล่ม> — กัน `book1` ชนกันข้ามวิชา (RAG-PLAN ข้อ 8.1)
BOOK_ID_RE = re.compile(r"^[a-z0-9]+-[a-z0-9]+-(book|teacher|workbook|other)\d+$")

#: หน้าที่เนื้อหาอยู่ในโครงสร้าง ไม่ใช่ในข้อความ → ยกเว้นกฎความยาว
#  front_matter เพิ่มเมื่อ 2026-09-02: หน้าเปิดบทมีข้อความพิมพ์จริงไม่ถึง 200 ตัวอักษรตามธรรมชาติ
#  กฎเดิมบังคับให้ผู้ถอด "เติมน้ำ" ลง text_md ซึ่งทำให้คลังเพี้ยน — เจอจริงตอนถอด p4-sci-book1 p077
TEXT_LEN_EXEMPT = {"concept_map", "front_matter"}
TEXT_MIN, TEXT_MAX = 200, 8000

#: ต่ำกว่านี้ = ควรมีคนเปิดหน้าจริงไปตรวจ (RAG-PLAN ข้อ 8.8 "ระบบต้องรู้ตัวว่ามันไม่รู้อะไร")
LOW_CONFIDENCE = 0.8

_FIG_KEYS = ("graph", "chart", "facts", "pictograph", "table")


#: กันคนพิมพ์ 1-99999 แล้วเซิร์ฟเวอร์ต้องกางลิสต์เป็นแสนช่อง
MAX_SPEC_PAGES = 2000


def _num(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def parse_page_spec(spec: str) -> list[int]:
    """`92` · `92-96` · `77,80,86-88` -> รายการเลขหน้าเรียงแล้วไม่ซ้ำ

    อยู่ที่นี่เพราะทั้ง CLI (`ocr_page.py`) และเซิร์ฟเวอร์ (`POST .../pages/claim`) ต้องแปล
    ข้อความเดียวกัน — คนละตัวแปล = พนักงานพิมพ์อย่างหนึ่งแล้วเซิร์ฟเวอร์จองอีกอย่าง
    """
    out: set[int] = set()
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            if "-" in part.lstrip("-"):
                lo, hi = (int(x) for x in part.split("-", 1))
            else:
                lo = hi = int(part)
        except ValueError:
            raise ValueError("อ่านช่วงหน้า %r ไม่ออก — ใช้รูปแบบ 92 หรือ 92-96 หรือ 92,94" % part)
        if lo < 1 or hi < lo:
            raise ValueError("ช่วงหน้า %r ไม่ถูกต้อง — ต้องเริ่มที่ 1 ขึ้นไปและเรียงจากน้อยไปมาก"
                             % part)
        if hi - lo + 1 > MAX_SPEC_PAGES or len(out) > MAX_SPEC_PAGES:
            raise ValueError("ขอทีเดียวเกิน %d หน้า — แบ่งเป็นหลายรอบ" % MAX_SPEC_PAGES)
        out.update(range(lo, hi + 1))
    if not out:
        raise ValueError("ไม่ได้ระบุเลขหน้า")
    return sorted(out)


def check_page(data) -> list[Problem]:
    """ตรวจหน้าที่ถอดแล้ว 1 หน้า — คืนรายการปัญหา (ว่าง = ผ่านสะอาด)"""
    out: list[Problem] = []
    if not isinstance(data, dict):
        return [Problem(ERROR, "(ไฟล์)", "ต้องเป็นออบเจกต์ JSON")]

    missing = [k for k in REQUIRED if k not in data]
    if missing:
        # ขาดฟิลด์บังคับแล้วตรวจข้ออื่นต่อไม่ได้ — บอกให้ครบทีเดียวดีกว่าไล่ทีละรอบ
        return [Problem(ERROR, k, "ขาดฟิลด์บังคับ") for k in missing]

    printed, seen = data["printed_page"], data["printed_page_seen"]
    if not isinstance(printed, int) or isinstance(printed, bool) or printed < 1:
        out.append(Problem(ERROR, "printed_page", "ต้องเป็นจำนวนเต็มบวก (ได้ %r)" % (printed,)))
    if seen is None:
        out.append(Problem(ERROR, "printed_page_seen",
                           "หน้านี้ไม่มีเลขพิมพ์บนกระดาษ จึงยืนยันไม่ได้ว่าเป็นหน้าที่สั่งถอด"))
    elif printed != seen:
        out.append(Problem(ERROR, "printed_page_seen",
                           "★ เลขหน้าไม่ตรง: สั่ง %s แต่เห็นบนกระดาษ %s — ภาพสลับหน้ากัน"
                           % (printed, seen)))

    if not BOOK_ID_RE.match(str(data["book_id"])):
        out.append(Problem(ERROR, "book_id",
                           "%r ผิดรูปแบบ — ต้องเป็น <ชั้น>-<วิชา>-<เล่ม> เช่น p4-sci-book1"
                           % (data["book_id"],)))
    for key in ("grade", "subject"):
        if not str(data.get(key) or "").strip():
            out.append(Problem(ERROR, key, "ต้องไม่ว่าง"))

    kind = data["page_kind"]
    if kind not in PAGE_KINDS:
        out.append(Problem(ERROR, "page_kind", "%r ไม่อยู่ใน %s" % (kind, sorted(PAGE_KINDS))))

    if data["schema_version"] != SCHEMA_VERSION:
        out.append(Problem(ERROR, "schema_version",
                           "%r != %r — ต้องถอดใหม่ด้วยสคีมาปัจจุบัน"
                           % (data["schema_version"], SCHEMA_VERSION)))

    text = data["text_md"]
    if not isinstance(text, str):
        out.append(Problem(ERROR, "text_md", "ต้องเป็นข้อความ"))
    elif kind not in TEXT_LEN_EXEMPT:
        if len(text) < TEXT_MIN:
            out.append(Problem(ERROR, "text_md",
                               "สั้นเกิน (%d ตัวอักษร) — น่าจะอ่านไม่ออก" % len(text)))
        elif len(text) > TEXT_MAX:
            out.append(Problem(ERROR, "text_md", "ยาวเกิน (%d ตัวอักษร) — น่าจะมั่ว" % len(text)))

    conf = _num(data["confidence"])
    if conf is None or not 0 <= conf <= 1:
        out.append(Problem(ERROR, "confidence", "%r ต้องเป็นตัวเลข 0-1" % (data["confidence"],)))
    elif conf < LOW_CONFIDENCE:
        out.append(Problem(WARN, "confidence",
                           "%.2f ต่ำกว่า %.1f — ควรมีคนเปิดหน้าจริงไปตรวจ"
                           % (conf, LOW_CONFIDENCE)))

    pdf_page = data.get("pdf_page")
    if pdf_page is not None and (not isinstance(pdf_page, int) or isinstance(pdf_page, bool)
                                 or pdf_page < 1):
        out.append(Problem(ERROR, "pdf_page", "ต้องเป็นจำนวนเต็มบวก (ได้ %r)" % (pdf_page,)))

    out.extend(_check_figures(data))

    for i, m in enumerate(data.get("math") or []):
        s = str(m).strip()
        if not (s.startswith("$") and s.endswith("$")):
            out.append(Problem(ERROR, "math[%d]" % i,
                               "%r ต้องครอบด้วย $...$ (ดู math-symbols-guide.md)" % (m,)))

    # ตั้งใจไม่รายงาน flags[] เป็น WARN: มันคือบันทึกของผู้ถอด ("ไม่มีตัวชี้วัดพิมพ์บนหน้า")
    # ไม่ใช่ข้อบกพร่อง — ถอด 13 หน้าจริงมี flags 30 ข้อ ถ้าพ่นออกมาหมด ปัญหาจริงจะจมหาย
    # ตัวมันเองเก็บอยู่ในทะเบียน (คอลัมน์ flags) และแสดงใน manifest อยู่แล้ว
    return out


def _check_figures(data) -> list[Problem]:
    out, seen_ids = [], set()
    for i, fig in enumerate(data.get("figures") or []):
        tag = "figures[%d]" % i
        if not isinstance(fig, dict):
            out.append(Problem(ERROR, tag, "ต้องเป็นออบเจกต์"))
            continue

        fid = fig.get("id")
        if not fid:
            out.append(Problem(ERROR, tag, "ขาด id"))
        elif fid in seen_ids:
            out.append(Problem(ERROR, tag, "id ซ้ำ: %s" % fid))
        else:
            seen_ids.add(fid)

        tier = fig.get("tier")
        if isinstance(tier, bool) or tier not in (0, 1, 2, 3):
            out.append(Problem(ERROR, tag, "tier %r ต้องเป็น 0/1/2/3" % (tier,)))
            continue

        fc = _num(fig.get("confidence"))
        if fc is None or not 0 <= fc <= 1:
            out.append(Problem(ERROR, tag, "confidence %r ต้องเป็นตัวเลข 0-1"
                               % (fig.get("confidence"),)))

        has_crop = bool(fig.get("crop"))
        if tier >= 2 and not has_crop:
            out.append(Problem(ERROR, tag, "tier %d ต้องมี crop" % tier))
        if tier == 0 and has_crop:
            out.append(Problem(ERROR, tag, "tier 0 (ตกแต่ง) ต้องไม่มี crop — เปลืองพื้นที่เปล่า"))

        if fig.get("needs_image") and not fig.get("why_needs_image"):
            out.append(Problem(ERROR, tag, "needs_image=true ต้องบอก why_needs_image"))

        # tier 2 ต้องมีข้อมูลโครงสร้างจริง ไม่ใช่แค่ประกาศว่าถอดได้
        if tier == 2 and not any(k in fig for k in _FIG_KEYS):
            out.append(Problem(ERROR, tag, "tier 2 ต้องมีอย่างน้อยหนึ่งใน %s"
                               % "/".join(_FIG_KEYS)))

        graph = fig.get("graph")
        if isinstance(graph, dict):
            if not graph.get("nodes"):
                out.append(Problem(ERROR, tag + ".graph", "ขาด nodes"))
            else:
                ids = {n.get("id") for n in graph["nodes"] if isinstance(n, dict)}
                for e in graph.get("edges") or []:
                    for side in ("from", "to"):
                        if e.get(side) not in ids:
                            out.append(Problem(ERROR, tag + ".graph",
                                               "edge ชี้ไป node ที่ไม่มีอยู่: %r" % (e.get(side),)))
        elif graph is not None:
            out.append(Problem(ERROR, tag + ".graph", "ต้องเป็นออบเจกต์"))

        # ปี พ.ศ. ห้ามหลุดเข้าฟิลด์วันที่ (RAG-PLAN กฎ 3.2 / 8.5)
        retrieved = (fig.get("source") or {}).get("retrieved")
        if retrieved and re.match(r"^25\d\d-", str(retrieved)):
            out.append(Problem(ERROR, tag + ".source.retrieved",
                               "%r เป็น พ.ศ. — ต้องเก็บเป็น ค.ศ." % (retrieved,)))
    return out


def summary(data: dict) -> dict:
    """คอลัมน์ที่ทะเบียนฝั่งเซิร์ฟเวอร์เก็บไว้ให้ query ได้โดยไม่ต้องแกะ JSON ทุกแถว

    ★ คำนวณที่นี่ที่เดียว เพื่อให้ manifest ของเซิร์ฟเวอร์กับ `ocr_page.py status`
      ในเครื่องนับเลขเดียวกัน (คนละสูตร = คนละยอด แล้วไม่มีใครรู้ว่าฝั่งไหนถูก)
    """
    figs = [f for f in (data.get("figures") or []) if isinstance(f, dict)]
    return {
        "printed_page": data.get("printed_page"),
        "pdf_page": data.get("pdf_page"),
        "page_kind": data.get("page_kind"),
        "schema_version": data.get("schema_version"),
        "model": data.get("ocr_model"),
        "confidence": _num(data.get("confidence")),
        "chars": len(data["text_md"]) if isinstance(data.get("text_md"), str) else 0,
        "figures": len(figs),
        "needs_image": sum(1 for f in figs if f.get("needs_image")),
        "flags": ",".join(str(f) for f in (data.get("flags") or [])),
    }
