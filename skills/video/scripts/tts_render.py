# -*- coding: utf-8 -*-
"""
tts_render.py — STUB ขั้นสร้างไฟล์เสียงบรรยาย (narration) จาก video.json

สถานะ: PENDING — ปัจจุบันเขียน script ต่อฉาก + placeholder
เมื่อมี TTS service (ElevenLabs/Azure/Google) เติมที่ TODO(tts) สร้าง wav/mp3 ต่อฉากแล้วคืน list path

ใช้งาน: python tts_render.py <video.json> <out_dir>
"""
import json
import os
import sys


def render(video_path, out_dir):
    with open(video_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    os.makedirs(out_dir, exist_ok=True)
    if not os.environ.get("TTS_API_KEY"):
        placeholder = os.path.join(out_dir, "narration.PENDING.txt")
        with open(placeholder, "w", encoding="utf-8") as f:
            f.write(f"PENDING TTS — lang={data.get('lang','th')}\n\n")
            for sc in data.get("scenes", []):
                f.write(f"[Scene {sc['number']} | {sc['duration_sec']}s] {sc['vo']}\n")
        print(f"PENDING — เขียน narration script: {placeholder}")
        return "PENDING"

    # TODO(tts): loop scenes -> สังเคราะห์เสียง vo ต่อฉาก -> scene_{n}.mp3 ใน out_dir
    raise NotImplementedError("TTS render ยังไม่ implement — เติมที่ TODO(tts)")


def main():
    if len(sys.argv) != 3:
        print("usage: python tts_render.py <video.json> <out_dir>", file=sys.stderr)
        sys.exit(2)
    print(f"status={render(sys.argv[1], sys.argv[2])}")


if __name__ == "__main__":
    main()
