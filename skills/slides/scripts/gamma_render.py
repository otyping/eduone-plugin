# -*- coding: utf-8 -*-
"""
gamma_render.py — STUB ขั้นเรียก Gamma (หรือ Canva) สร้าง pptx จาก slides.json

สถานะ: PENDING — ปัจจุบันเขียน placeholder `<out>.PENDING`
Gamma MCP เชื่อมในเครื่องแล้ว (tools: generate, generate_from_template) — เมื่อพร้อม
ให้ orchestrator เรียก MCP โดยตรง หรือเติม HTTP call ที่ TODO(gamma)

input slides.json: ดู reference/prompt-master-powerpoint.md (6 ส่วน)
ใช้งาน: python gamma_render.py <slides.json> <out.pptx>
"""
import json
import os
import sys


def slides_to_markdown(slides):
    """แปลง slides.json -> markdown outline ที่ Gamma generate กินได้ (--- คั่นการ์ด)"""
    cards = []
    for s in slides:
        sec = s.get("section")
        if sec == "cover":
            cards.append(f"# {s.get('title','')}\n\n> {s.get('hook_question','')}")
        elif sec == "objectives":
            body = "\n".join(s.get("items", []))
            cards.append(f"## {s.get('title','หัวข้อการเรียนรู้')}\n\n{body}")
        elif sec == "vocab":
            tbl = s.get("table", [])
            md = "\n".join("| " + " | ".join(r) + " |" for r in tbl)
            cards.append(f"## {s.get('title','คำศัพท์')}\n\n{md}")
        else:
            bullets = "\n".join(f"- {b}" for b in s.get("bullets", []))
            img = f"\n\n[IMAGE: {s['image_prompt']}]" if s.get("image_prompt") else ""
            cards.append(f"## {s.get('title','')}\n\n{bullets}{img}")
    return "\n\n---\n\n".join(cards)


def render(slides_path, out_path):
    with open(slides_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    md = slides_to_markdown(data.get("slides", []))
    api_key = os.environ.get("GAMMA_API_KEY")
    if not api_key:
        placeholder = out_path + ".PENDING"
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(placeholder, "w", encoding="utf-8") as f:
            f.write("PENDING GAMMA/CANVA RENDER\n\n# Outline (markdown) พร้อมป้อน Gamma generate:\n\n")
            f.write(md)
        print(f"PENDING — เขียน outline placeholder: {placeholder}")
        return "PENDING"

    # TODO(gamma): เรียก Gamma generate ด้วย inputText=md, format='presentation',
    #   export='pptx' -> ดาวน์โหลดไป out_path. (หรือใช้ Gamma MCP tool โดยตรงจาก orchestrator)
    raise NotImplementedError("Gamma render ยังไม่ implement — เติมที่ TODO(gamma)")


def main():
    if len(sys.argv) != 3:
        print("usage: python gamma_render.py <slides.json> <out.pptx>", file=sys.stderr)
        sys.exit(2)
    print(f"status={render(sys.argv[1], sys.argv[2])}")


if __name__ == "__main__":
    main()
