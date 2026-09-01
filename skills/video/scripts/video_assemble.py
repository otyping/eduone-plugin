# -*- coding: utf-8 -*-
"""
video_assemble.py — STUB ขั้นตัดต่อรวมเป็น video.mp4 จาก video.json + เสียง narration

สถานะ: PENDING — ปัจจุบันเขียน placeholder `<out>.PENDING`
ทางเลือก render จริง: (a) HeyGen API (avatar+TTS ต่อฉาก) หรือ
(b) TTS (tts_render.py) + ภาพต่อฉาก (image-gen/สไลด์) + ffmpeg ประกอบตาม duration

ใช้งาน: python video_assemble.py <video.json> <out.mp4>
"""
import json
import os
import sys


def render(video_path, out_path):
    with open(video_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    total = data.get("total_duration_sec", sum(s.get("duration_sec", 0) for s in data.get("scenes", [])))
    use_heygen = bool(os.environ.get("HEYGEN_API_KEY"))
    if not use_heygen:
        placeholder = out_path + ".PENDING"
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(placeholder, "w", encoding="utf-8") as f:
            f.write(f"PENDING VIDEO RENDER — {len(data.get('scenes', []))} scenes, {total}s total\n")
            f.write("ตัวเลือก: HEYGEN_API_KEY (avatar) หรือ TTS+ffmpeg pipeline\n")
        print(f"PENDING — เขียน placeholder: {placeholder}")
        return "PENDING"

    # TODO(video): HeyGen scene-based video หรือ ffmpeg assemble (เสียงจาก tts_render + ภาพต่อฉาก)
    raise NotImplementedError("Video assemble ยังไม่ implement — เติมที่ TODO(video)")


def main():
    if len(sys.argv) != 3:
        print("usage: python video_assemble.py <video.json> <out.mp4>", file=sys.stderr)
        sys.exit(2)
    print(f"status={render(sys.argv[1], sys.argv[2])}")


if __name__ == "__main__":
    main()
