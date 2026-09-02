"""paths.py — single source of truth ของ path ผลผลิตทุกชนิด (EDU ONE)

โครงสร้าง Output (ผู้ใช้กำหนด):
  Output/<GradeToken>/<SubjectToken>/<G-S>_U<unit>/<G-S>_U<unit>_<topic>/<BASE>/
  (หลักสูตรที่ยังไม่ละเอียดถึงคาบ ไม่มีชั้น <topic> — <BASE> อยู่ใต้ _U<unit> เลย)
     1. Content/      {BASE}_C1.json + _C1.docx · {BASE}_C2.json + _C2.docx
     2. LessonPlan/   {BASE}_L1.json + _L1.docx · {BASE}_L2.json + _L2.docx
     3. Exercise/     {BASE}_ex.json (โจทย์+เฉลย+วิธีคิด+สื่อ ไฟล์เดียว) + {BASE}_ex.docx
                      + {BASE}_media-brief.md · {BASE}_audio-src.json · {BASE}_media/
     4. Slides/       {BASE}_slides_{C1,C2,L1,L2}.json + .pptx
                      + (ถ้ามีรูป) {BASE}_slides_<src>_media-brief.md · {BASE}_slides_<src>_media/
     5. Video/        {BASE}_video.json + _video.mp4 + {BASE}_video_audio/
     6. Song/         {BASE}_song.json + _song.mp3 + _song.txt (เนื้อเพลง)
     7. Activity/     {BASE}_game.json   (อ่าน {BASE}_ex.json จาก 3. Exercise/)

spec JSON วางคู่กับไฟล์ render ในแต่ละ product folder (track git);
ไฟล์ render (.docx/.pptx/.mp3/.mp4/.PENDING) gitignored

CLI: python paths.py <gradeSlug> <subjectSlug> <no>   → พิมพ์ JSON ของ path ทุกผลผลิต
ใช้เป็นไลบรารี: from paths import topic_paths ; p = topic_paths(meta_dict)
"""
from __future__ import annotations

import json
import os
import sys

# ป้ายโฟลเดอร์ผลผลิตตายตัว (ลำดับแสดงผล ไม่ใช่เลข agent)
FOLDERS = {
    "content": "1. Content",
    "lesson_plan": "2. LessonPlan",
    "exercise": "3. Exercise",
    "slides": "4. Slides",
    "video": "5. Video",
    "song": "6. Song",
    "activity": "7. Activity",
}
SLIDE_SOURCES = ("C1", "C2", "L1", "L2")


def topic_paths(meta: dict) -> dict:
    """รับผลจาก no_to_token (ต้องมี base + topic_dir) คืน dict ของ path ทุกผลผลิต"""
    base = meta["base"]
    root = meta["topic_dir"]  # no_to_token ประกอบให้แล้ว ลึกกี่ชั้นก็ตามหลักสูตร

    def d(key):  # product dir
        return f"{root}/{FOLDERS[key]}"

    content = d("content")
    plan = d("lesson_plan")
    ex = d("exercise")
    slides = d("slides")
    video = d("video")
    song = d("song")
    act = d("activity")
    vaudio = f"{video}/{base}_video_audio"

    return {
        "base": base,
        "root": root,
        # 1. Content — json (track) + docx (render)
        "content_c1_json": f"{content}/{base}_C1.json",
        "content_c1_docx": f"{content}/{base}_C1.docx",
        "content_c2_json": f"{content}/{base}_C2.json",
        "content_c2_docx": f"{content}/{base}_C2.docx",
        # แหล่งค้นคว้าก่อนเขียน C1 (content-research เขียน — track git ไม่ rebuild เอง)
        "content_research_md": f"{content}/{base}_research.md",
        # source pack ที่ agent ปลายน้ำอ่านแทน C1 เต็ม (srcpack.py สร้างจาก digest ของ C1)
        "content_srcpack_md": f"{content}/{base}_srcpack.md",
        # บัตรขอบเขตคาบ — scope_card.py เขียนที่ W0 ก่อนเรียก agent ตัวแรก
        # ทุก prompt ส่งแค่ path ของไฟล์นี้ แทนการพิมพ์ข้อห้ามขอบเขตซ้ำในทุก prompt
        "scope_md": f"{root}/{base}_scope.md",
        # บัตรผลตรวจของเครื่อง — validate_spec.py --report เขียนก่อนเรียก checkwork
        # บอกว่าเครื่องนับอะไรไปแล้ว checkwork จะได้ไม่เสียแรงนับซ้ำ
        # ผลผลิตที่มีหลายไฟล์ (L1/L2 · สไลด์ 4 แหล่ง) ให้เติมท้ายเป็น
        # {base}_gate_L1.md / {base}_gate_C1.md ฯลฯ จะได้ไม่เขียนทับกัน
        # ไฟล์กลุ่มนี้สร้างใหม่ได้เสมอ จึงไม่ track git (ดู .gitignore)
        "gate_md": f"{root}/{base}_gate.md",
        # 2. LessonPlan
        "plan_l1_json": f"{plan}/{base}_L1.json",
        "plan_l1_docx": f"{plan}/{base}_L1.docx",
        "plan_l2_json": f"{plan}/{base}_L2.json",
        "plan_l2_docx": f"{plan}/{base}_L2.docx",
        # 3. Exercise — JSON ไฟล์เดียว (โจทย์+เฉลย+วิธีคิด+สื่อ) + docx + งานผลิตสื่อ
        "exercise_docx": f"{ex}/{base}_ex.docx",
        "ex_json": f"{ex}/{base}_ex.json",
        "ex_media_dir": f"{ex}/{base}_media",
        "ex_brief_md": f"{ex}/{base}_media-brief.md",
        "ex_audio_src_json": f"{ex}/{base}_audio-src.json",
        "ex_urls_txt": f"{ex}/{base}_urls.txt",
        # 4. Slides ×4 (+ งานสื่อรูปของแต่ละแหล่ง)
        "slides_json": {s: f"{slides}/{base}_slides_{s}.json" for s in SLIDE_SOURCES},
        "slides_pptx": {s: f"{slides}/{base}_slides_{s}.pptx" for s in SLIDE_SOURCES},
        "slides_brief_md": {s: f"{slides}/{base}_slides_{s}_media-brief.md"
                            for s in SLIDE_SOURCES},
        "slides_media_dir": {s: f"{slides}/{base}_slides_{s}_media" for s in SLIDE_SOURCES},
        # 5. Video
        "video_json": f"{video}/{base}_video.json",
        "video_mp4": f"{video}/{base}_video.mp4",
        "video_audio_dir": vaudio,
        # 6. Song
        "song_json": f"{song}/{base}_song.json",
        "song_mp3": f"{song}/{base}_song.mp3",
        "song_txt": f"{song}/{base}_song.txt",
        # 7. Activity (game — อ่าน {BASE}_ex.json จาก 3. Exercise)
        "game_json": f"{act}/{base}_game.json",
        # product dirs (เผื่อสร้างล่วงหน้า)
        "dirs": {
            "content": content, "lesson_plan": plan, "exercise": ex,
            "slides": slides, "video": video, "song": song,
            "activity": act, "video_audio": vaudio,
            "ex_media": f"{ex}/{base}_media",
        },
        # หัวข้อที่ต้องรู้มาก่อน (จาก PREREQ| ใน course-structure)
        # ส่ง **path** ของ srcpack ให้ writer อ่านเอง — ห้าม orchestrator อ่านเนื้อหา
        "prereq": _prereq_paths(meta),
    }


def _prereq_paths(meta: dict) -> list:
    """เติม path ของ srcpack/C1 ให้หัวข้อ prereq + บอกว่าไฟล์มีอยู่จริงไหม

    `ready` = มี srcpack แล้ว (พร้อมให้ writer อ่าน)
    ยังไม่ ready แต่มี C1 -> สร้าง srcpack ก่อนด้วย srcpack.py
    ไม่มีทั้งคู่ = ยังไม่ได้ผลิตหัวข้อนั้น -> ข้ามไป (ไม่ใช่ error)
    """
    out = []
    for p in meta.get("prereq", []):
        c = f"{p['topic_dir']}/{FOLDERS['content']}"
        srcpack = f"{c}/{p['base']}_srcpack.md"
        c1_json = f"{c}/{p['base']}_C1.json"
        out.append({
            **p,
            "srcpack_md": srcpack,
            "c1_json": c1_json,
            "ready": os.path.isfile(srcpack),
            "has_c1": os.path.isfile(c1_json),
        })
    return out


def ensure_dirs(p: dict) -> None:
    """สร้างโฟลเดอร์ผลผลิตทั้งหมดของหัวข้อ"""
    for path in p["dirs"].values():
        os.makedirs(path, exist_ok=True)


def unit_paths(meta: dict) -> dict:
    """path ของผลผลิต **ระดับหน่วย/บท** (ข้อสอบรวมทั้งบท ไม่ผูกกับหัวข้อใดหัวข้อหนึ่ง)

    วางไว้ที่โฟลเดอร์หน่วย ซึ่งเป็นชั้นเหนือโฟลเดอร์หัวข้อ:
      Output/<G>/<S>/<G-S_Uu>/<G-S_Uu>_ex.json      (+ _ex.docx, _media-brief.md ฯลฯ)

    UBASE = unit_folder เช่น `M1-Math_U4` -> ไฟล์ `M1-Math_U4_ex.json`
    ใช้กับ /exercise เมื่อผู้ใช้สั่ง "ข้อสอบบทที่ N" (ทั้งบท) แทนที่จะสั่งเป็นราย No.
    """
    ubase = meta["unit_folder"]                      # M1-Math_U4
    # ★ ห้ามหาโฟลเดอร์หน่วยด้วยการถอยขึ้นหนึ่งชั้นจาก topic_dir
    #   หลักสูตรรายคาบลึกกว่าหนึ่งชั้น (.../M1-Math_U1/M1-Math_U1_4/M1-Math_U1_4_1)
    #   ถอยชั้นเดียวจะได้โฟลเดอร์ "หัวข้อ" ไม่ใช่ "หน่วย" แล้วข้อสอบระดับบทไปตกผิดที่
    #   ประกอบจากส่วนที่รู้แน่ ๆ แทน ถูกต้องไม่ว่าโครงจะลึกกี่ชั้น
    unit_dir = f"Output/{meta['grade_token']}/{meta['subject_token']}/{ubase}"
    ex = f"{unit_dir}/{FOLDERS['exercise']}"

    return {
        "ubase": ubase,
        "unit_dir": unit_dir,
        "exercise_docx": f"{ex}/{ubase}_ex.docx",
        "ex_json": f"{ex}/{ubase}_ex.json",
        "ex_media_dir": f"{ex}/{ubase}_media",
        "ex_brief_md": f"{ex}/{ubase}_media-brief.md",
        "ex_audio_src_json": f"{ex}/{ubase}_audio-src.json",
        "ex_urls_txt": f"{ex}/{ubase}_urls.txt",
        "dirs": {"exercise": ex, "ex_media": f"{ex}/{ubase}_media"},
    }


def main(argv: list[str]) -> int:
    if len(argv) not in (4, 5) or (len(argv) == 5 and argv[4] != "--unit"):
        print("usage: paths.py <gradeSlug> <subjectSlug> <no> [--unit]", file=sys.stderr)
        return 2
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, here)
    from no_to_token import no_to_token
    meta = no_to_token(argv[1], argv[2], int(argv[3]))
    out = unit_paths(meta) if len(argv) == 5 else topic_paths(meta)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
