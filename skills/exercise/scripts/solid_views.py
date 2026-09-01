# -*- coding: utf-8 -*-
"""
solid_views.py — รูปเรขาคณิตสองมิติและสามมิติ (โมดูลเสริมของ gen_math_images.py)

ชนิดที่วาดได้
  cubestack  กองลูกบาศก์หนึ่งหน่วย วาดแบบภาพฉายเฉียง (ระบุพิกัด [x, y, z] ของแต่ละลูก)
             x = ไปทางขวา · y = ลึกเข้าไปข้างหลัง · z = สูงขึ้น
             เรียงลำดับวาดจากลูกที่อยู่หลังสุดมาหน้าสุด เส้นที่ถูกบังจึงหายไปเอง
             ใส่ "arrows": true เพื่อกำกับทิศ ด้านหน้า/ด้านข้าง/ด้านบน แบบหนังสือเรียน
  views2d    ภาพสองมิติที่ได้จากการมอง (ภาพด้านหน้า/ด้านข้าง/ด้านบน) เขียนเป็นตารางช่อง
             ระบุ "cells": [[row, col], ...] โดย row 0 = แถวล่างสุด · col 0 = คอลัมน์ซ้ายสุด
             ใส่ "panels" เพื่อวางหลายภาพพร้อมป้ายกำกับในกรอบเดียว
  section    รูปเรขาคณิตสามมิติถูกระนาบตัด — ทรงกระบอก กรวย พีระมิด ปริซึมสี่เหลี่ยมมุมฉาก
             ปริซึมสามเหลี่ยม ทรงกลม · แนวตัด horizontal (ขนานฐาน) / vertical (ตั้งฉากฐาน)
             / oblique (เฉียง)

ความสัมพันธ์ของภาพที่ได้จากการมอง (ยึดตามหนังสือเรียน สสวท. ม.1 เล่ม 1 บทที่ 5)
  ภาพด้านหน้า = ฉายลง (x, z) · ภาพด้านข้าง = ฉายลง (y, z) โดยด้านหน้าของวัตถุอยู่ทางซ้าย
  ภาพด้านบน   = ฉายลง (x, y) โดยด้านหน้าของวัตถุอยู่แถวล่าง

ไม่เรียกตรง ๆ — เรียกผ่าน gen_math_images.py ซึ่ง merge DRAWERS ของไฟล์นี้เข้าไป
รันผ่านตัวห่อ: eduone-py <ชื่อไฟล์นี้> <args>  (หา Python 3.12 ให้เองทุก OS)
"""
import math

INK = "#1e1e1e"
FACE_FRONT = "#aab7ea"
FACE_TOP = "#d8dffa"
FACE_SIDE = "#8d9cd9"
VIEW_FILL = "#9aa8e0"
PLANE = "#3f51b5"
SOLID_FILL = "#f2a0c0"
SOLID_FILL_2 = "#f7c6da"

OX, OY = 0.52, 0.42                 # เวกเตอร์ความลึกบนภาพฉายเฉียง (1 หน่วยลึก)


def _fig(plt, spec, default):
    fig, ax = plt.subplots(figsize=tuple(spec.get("figSize", default)),
                           dpi=spec.get("dpi", 170))
    ax.set_aspect("equal")
    ax.axis("off")
    ax.grid(False)
    return fig, ax


def _save(fig, ax, spec, out_path, tight=True):
    if spec.get("title"):
        ax.set_title(spec["title"], fontsize=spec.get("titleSize", 15))
    ax.margins(0.12)
    fig.tight_layout()
    fig.savefig(out_path, dpi=spec.get("dpi", 170), facecolor="white",
                bbox_inches="tight" if tight else None)
    import matplotlib.pyplot as plt
    plt.close(fig)
    return out_path


def _p(x, y, z):
    """ภาพฉายเฉียง: จุด 3 มิติ -> จุดบนภาพ"""
    return (x + y * OX, z + y * OY)


# --------------------------------------------------------------- กองลูกบาศก์
def draw_cubestack(spec, out_path):
    from gen_math_images import _mpl
    plt, ok = _mpl()
    if not ok:
        raise RuntimeError("ต้องมี matplotlib")
    from matplotlib.patches import Polygon

    cubes = [tuple(int(v) for v in c) for c in spec["cubes"]]
    if not cubes:
        raise ValueError("cubestack ต้องมี cubes อย่างน้อย 1 ลูก")
    occupied = set(cubes)
    fig, ax = _fig(plt, spec, spec.get("figSize", (4.0, 3.6)))
    lw = spec.get("lineWidth", 1.5)

    def face(pts3, color, z=3):
        ax.add_patch(Polygon([_p(*q) for q in pts3], closed=True, facecolor=color,
                             edgecolor=INK, lw=lw, zorder=z, joinstyle="round"))

    # วาดจากลูกหลังสุดไปหน้าสุด — ลูกที่อยู่หน้าจะทับส่วนที่ถูกบังพอดี
    order = sorted(cubes, key=lambda c: (-c[1], c[0] + c[2], c[0]))
    for i, (x, y, z) in enumerate(order):
        zo = 3 + i * 3
        face([(x, y, z), (x + 1, y, z), (x + 1, y, z + 1), (x, y, z + 1)],
             FACE_FRONT, zo)                                   # ด้านหน้า
        if (x, y, z + 1) not in occupied:
            face([(x, y, z + 1), (x + 1, y, z + 1), (x + 1, y + 1, z + 1),
                  (x, y + 1, z + 1)], FACE_TOP, zo + 1)        # ด้านบน
        if (x + 1, y, z) not in occupied:
            face([(x + 1, y, z), (x + 1, y + 1, z), (x + 1, y + 1, z + 1),
                  (x + 1, y, z + 1)], FACE_SIDE, zo + 2)       # ด้านข้างขวา

    xs = [c[0] for c in cubes]
    ys = [c[1] for c in cubes]
    zs = [c[2] for c in cubes]
    w, d, h = max(xs) + 1, max(ys) + 1, max(zs) + 1
    if spec.get("arrows"):
        fs = spec.get("fontSize", 13)
        arrow = dict(arrowstyle="-|>", color=INK, lw=1.3, shrinkA=0, shrinkB=1)
        # เล็งลูกศรไปที่หน้าที่มองเห็นจริง ไม่ใช่กึ่งกลางกล่องครอบ (กองอาจไม่เต็มกล่อง)
        ct = min((c for c in cubes if c[2] == max(zs)), key=lambda c: (c[1], c[0]))
        cf = min((c for c in cubes if c[1] == min(ys)), key=lambda c: (c[2], c[0]))
        cs = max((c for c in cubes if c[0] == max(xs)), key=lambda c: (-c[1], -c[2]))
        tip = _p(ct[0] + 0.5, ct[1] + 0.5, ct[2] + 1)
        ax.annotate("ด้านบน", xy=tip, xytext=(tip[0], tip[1] + 1.15),
                    ha="center", va="bottom", fontsize=fs, color=INK,
                    arrowprops=arrow, zorder=100)
        tip = _p(cf[0] + 0.5, cf[1], cf[2] + 0.5)
        ax.annotate("ด้านหน้า", xy=tip, xytext=(tip[0] - 1.35, tip[1] - 1.0),
                    ha="right", va="top", fontsize=fs, color=INK,
                    arrowprops=arrow, zorder=100)
        tip = _p(cs[0] + 1, cs[1] + 0.5, cs[2] + 0.5)
        ax.annotate("ด้านข้าง", xy=tip, xytext=(tip[0] + 1.35, tip[1] - 1.0),
                    ha="left", va="top", fontsize=fs, color=INK,
                    arrowprops=arrow, zorder=100)
    return _save(fig, ax, spec, out_path)


# ------------------------------------------------------- ภาพสองมิติจากการมอง
def _panel(ax, cells, x0, y0, cell=1.0, fill=VIEW_FILL, lw_in=1.1, lw_out=2.3):
    """วาดภาพสองมิติ 1 ภาพจากรายการช่อง [row, col] (row 0 = ล่างสุด)"""
    from matplotlib.patches import Rectangle
    pts = {(int(r), int(c)) for r, c in cells}
    edges = {}
    for r, c in pts:
        ax.add_patch(Rectangle((x0 + c * cell, y0 + r * cell), cell, cell,
                               facecolor=fill, edgecolor=INK, lw=lw_in, zorder=3))
        for e in (((c, r), (c + 1, r)), ((c + 1, r), (c + 1, r + 1)),
                  ((c + 1, r + 1), (c, r + 1)), ((c, r + 1), (c, r))):
            key = tuple(sorted(e))
            edges[key] = edges.get(key, 0) + 1
    for (a, b), n in edges.items():                 # เส้นขอบนอก = ขอบที่ไม่มีช่องติดกัน
        if n == 1:
            ax.plot([x0 + a[0] * cell, x0 + b[0] * cell],
                    [y0 + a[1] * cell, y0 + b[1] * cell],
                    color=INK, lw=lw_out, zorder=4, solid_capstyle="round")
    cols = max(c for _, c in pts) + 1
    rows = max(r for r, _ in pts) + 1
    return cols * cell, rows * cell


def draw_views2d(spec, out_path):
    from gen_math_images import _mpl
    plt, ok = _mpl()
    if not ok:
        raise RuntimeError("ต้องมี matplotlib")
    panels = spec.get("panels")
    if not panels:
        panels = [{"cells": spec["cells"], "label": spec.get("label", "")}]
    cell = float(spec.get("cell", 1.0))
    gap = float(spec.get("gap", 1.1))
    per_row = int(spec.get("perRow", len(panels)))
    fs = spec.get("fontSize", 14)

    sizes = [(max(int(c[1]) for c in p["cells"]) + 1,
              max(int(c[0]) for c in p["cells"]) + 1) for p in panels]
    rows_of = [sizes[i:i + per_row] for i in range(0, len(sizes), per_row)]
    row_h = [max(s[1] for s in r) * cell + (1.0 if any(p.get("label") for p in panels) else 0.0)
             for r in rows_of]
    total_w = max(sum(s[0] * cell for s in r) + gap * (len(r) - 1) for r in rows_of)
    total_h = sum(row_h) + gap * (len(rows_of) - 1)
    # canvas = กรอบขนาดคงที่ ทำให้ทุกตัวเลือกในข้อเดียวกันมีมาตราส่วนเท่ากันเป๊ะ (กันเดาจากขนาดรูป)
    canvas = spec.get("canvas")
    if canvas:
        default_size = (float(canvas[0]) * 0.62 + 0.25, float(canvas[1]) * 0.62 + 0.25)
    else:
        default_size = (max(1.7, total_w * 0.72), max(1.7, total_h * 0.72))
    fig, ax = _fig(plt, spec, spec.get("figSize", default_size))

    y = total_h
    k = 0
    for ri, r in enumerate(rows_of):
        row_w = sum(s[0] * cell for s in r) + gap * (len(r) - 1)
        x = (total_w - row_w) / 2.0
        top = y
        for s in r:
            p = panels[k]; k += 1
            base = top - row_h[ri]
            lab = p.get("label", "")
            y0 = base + (1.0 if lab else 0.0)
            _panel(ax, p["cells"], x, y0, cell,
                   fill=p.get("fill", spec.get("fill", VIEW_FILL)))
            if lab:
                ax.annotate(lab, (x + s[0] * cell / 2.0, base + 0.75),
                            ha="center", va="top", fontsize=fs, color=INK)
            x += s[0] * cell + gap
        y -= row_h[ri] + gap
    if spec.get("frame"):
        from matplotlib.patches import Rectangle
        ax.add_patch(Rectangle((-0.45, -0.45), total_w + 0.9, total_h + 0.9,
                               facecolor="none", edgecolor="#b71c3e", lw=1.2, zorder=1))
    ax.autoscale_view()
    if canvas:
        cw, ch = float(canvas[0]) * cell, float(canvas[1]) * cell
        cx, cy = total_w / 2.0, total_h / 2.0
        ax.set_xlim(cx - cw / 2.0 - 0.25, cx + cw / 2.0 + 0.25)
        ax.set_ylim(cy - ch / 2.0 - 0.25, cy + ch / 2.0 + 0.25)
    return _save(fig, ax, spec, out_path, tight=not canvas)


# ------------------------------------------- รูปสามมิติที่ถูกระนาบตัด (หน้าตัด)
def _plane_pts(kind, w, h, d, at, m=0.55):
    """คืนพิกัด 3 มิติ 4 มุมของแผ่นระนาบที่ตัดผ่านรูปทรง"""
    if kind == "horizontal":                 # ขนานกับฐาน
        z = h * at
        return [(-m, -m, z), (w + m, -m, z), (w + m, d + m, z), (-m, d + m, z)]
    if kind == "vertical":                   # ตั้งฉากกับฐาน
        x = w * at
        return [(x, -m, -m), (x, d + m, -m), (x, d + m, h + m), (x, -m, h + m)]
    z1, z2 = h * (at - 0.28), h * (at + 0.28)   # เฉียง
    return [(-m, -m, z1), (w + m, -m, z2), (w + m, d + m, z2), (-m, d + m, z1)]


def draw_section(spec, out_path):
    from gen_math_images import _mpl
    plt, ok = _mpl()
    if not ok:
        raise RuntimeError("ต้องมี matplotlib")
    from matplotlib.patches import Polygon, Ellipse, Arc, Circle

    shape = spec.get("shape", "cuboid")
    w = float(spec.get("w", 2.6))
    h = float(spec.get("h", 2.6))
    d = float(spec.get("d", 1.5))
    fig, ax = _fig(plt, spec, spec.get("figSize", (3.9, 3.4)))
    lw = 1.8

    def poly(pts3, fc, z=3, ec=INK, alpha=1.0):
        ax.add_patch(Polygon([_p(*q) for q in pts3], closed=True, facecolor=fc,
                             edgecolor=ec, lw=lw, zorder=z, alpha=alpha))

    def seg(a, b, style="-", z=4, width=lw):
        pa, pb = _p(*a), _p(*b)
        ax.plot([pa[0], pb[0]], [pa[1], pb[1]], color=INK, lw=width,
                linestyle=(0, (4, 3)) if style == "--" else "-", zorder=z)

    if shape in ("cuboid", "cube", "prism4"):
        if shape == "cube":
            h = d = w
        front = [(0, 0, 0), (w, 0, 0), (w, 0, h), (0, 0, h)]
        back = [(x, d, z) for x, _, z in front]
        poly(back, SOLID_FILL_2, z=2)
        seg(back[0], (0, 0, 0), "--", z=2, width=1.3)
        seg(back[0], back[1], "--", z=2, width=1.3)
        seg(back[0], back[3], "--", z=2, width=1.3)
        poly([(0, 0, h), (w, 0, h), (w, d, h), (0, d, h)], SOLID_FILL_2, z=3)   # ด้านบน
        poly([(w, 0, 0), (w, d, 0), (w, d, h), (w, 0, h)], SOLID_FILL_2, z=3)   # ด้านข้าง
        poly(front, SOLID_FILL, z=4)
    elif shape == "prism3":                      # ปริซึมสามเหลี่ยม (ฐานสามเหลี่ยมอยู่หน้า-หลัง)
        front = [(0, 0, 0), (w, 0, 0), (w / 2.0, 0, h)]
        back = [(x, d, z) for x, _, z in front]
        poly(back, SOLID_FILL_2, z=2)
        poly([(w, 0, 0), (w, d, 0), (w / 2.0, d, h), (w / 2.0, 0, h)],
             SOLID_FILL_2, z=3)                                                  # หน้าลาดขวา
        poly(front, SOLID_FILL, z=4)
    elif shape == "cylinder":
        rx = w / 2.0
        ax.add_patch(Ellipse(_p(rx, 0, 0), w, d, facecolor=SOLID_FILL,
                             edgecolor="none", zorder=2))
        ax.add_patch(Polygon([_p(0, 0, 0), _p(w, 0, 0), _p(w, 0, h), _p(0, 0, h)],
                             closed=True, facecolor=SOLID_FILL, edgecolor="none", zorder=3))
        ax.add_patch(Ellipse(_p(rx, 0, 0), w, d, facecolor="none", edgecolor=INK,
                             lw=1.3, linestyle=(0, (4, 3)), zorder=3))
        ax.add_patch(Arc(_p(rx, 0, 0), w, d, theta1=180, theta2=360,
                         edgecolor=INK, lw=lw, zorder=5))
        ax.add_patch(Ellipse(_p(rx, 0, h), w, d, facecolor=SOLID_FILL_2,
                             edgecolor=INK, lw=lw, zorder=5))
        seg((0, 0, 0), (0, 0, h), "-", z=5)
        seg((w, 0, 0), (w, 0, h), "-", z=5)
    elif shape == "cone":
        rx = w / 2.0
        ax.add_patch(Polygon([_p(0, 0, 0), _p(w, 0, 0), _p(rx, 0, h)], closed=True,
                             facecolor=SOLID_FILL, edgecolor="none", zorder=3))
        ax.add_patch(Ellipse(_p(rx, 0, 0), w, d, facecolor=SOLID_FILL,
                             edgecolor=INK, lw=lw, zorder=4))
        seg((0, 0, 0), (rx, 0, h), "-", z=5)
        seg((w, 0, 0), (rx, 0, h), "-", z=5)
    elif shape == "pyramid":
        base = [(0, 0, 0), (w, 0, 0), (w, d, 0), (0, d, 0)]
        apex = (w / 2.0, d / 2.0, h)
        poly(base, SOLID_FILL, z=3)
        poly([base[1], base[2], apex], SOLID_FILL_2, z=4)      # หน้าข้างขวา
        poly([base[0], base[1], apex], SOLID_FILL, z=5)        # หน้าด้านหน้า
        seg(base[3], apex, "--", z=2, width=1.3)
    elif shape == "sphere":
        r = w / 2.0
        ax.add_patch(Circle(_p(r, 0, r), r, facecolor=SOLID_FILL, edgecolor=INK,
                            lw=lw, zorder=3))
        ax.add_patch(Ellipse(_p(r, 0, r), 2 * r, r * 0.55, facecolor="none",
                             edgecolor=INK, lw=1.2, linestyle=(0, (4, 3)), zorder=4))
        h = 2 * r
        d = 2 * r
    else:
        raise ValueError("section: ไม่รู้จัก shape '%s'" % shape)

    cut = spec.get("cut", "horizontal")
    at = float(spec.get("at", 0.5))
    default_m = 1.05 if cut == "vertical" else 0.55   # แนวตั้งฉากมองเห็นแคบ ต้องยื่นออกมากกว่า
    pts = _plane_pts(cut, w, h, d, at, m=float(spec.get("margin", default_m)))
    ax.add_patch(Polygon([_p(*q) for q in pts], closed=True, facecolor=PLANE,
                         edgecolor=PLANE, lw=1.2, alpha=0.42, zorder=8))
    if spec.get("planeLabel"):
        p0 = _p(*pts[0])
        ax.annotate(spec["planeLabel"], (p0[0] - 0.25, p0[1]), ha="right",
                    va="center", fontsize=spec.get("fontSize", 13), color=PLANE)
    ax.autoscale_view()
    return _save(fig, ax, spec, out_path)


SOLID_DRAWERS = {
    "cubestack": draw_cubestack,
    "views2d": draw_views2d,
    "section": draw_section,
}
