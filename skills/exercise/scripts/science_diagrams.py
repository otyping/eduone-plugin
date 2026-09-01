# -*- coding: utf-8 -*-
"""
science_diagrams.py — แผนภาพวิทยาศาสตร์สำหรับข้อสอบ/เนื้อหา (โมดูลเสริมของ gen_math_images.py)

ชนิดที่วาดได้
  circuit    วงจรไฟฟ้า — แบบอนุกรมและแบบขนาน (ถ่านไฟฉาย หลอดไฟ ตัวต้านทาน สวิตช์
             แอมมิเตอร์ โวลต์มิเตอร์) พร้อมป้ายกำกับค่า
  forces     แผนภาพแรง — วัตถุ + ลูกศรแรงหลายทิศพร้อมป้าย (มี/ไม่มีพื้น)
  atom       แบบจำลองอะตอมโบร์ — นิวเคลียส (โปรตอน/นิวตรอน) + วงโคจร + อิเล็กตรอน
  solid3d    รูปทรงสามมิติ — ลูกบาศก์ ทรงสี่เหลี่ยมมุมฉาก ทรงกระบอก กรวย พีระมิด ทรงกลม
             วาดแบบภาพฉายเฉียง เส้นที่ถูกบังเป็นเส้นประ พร้อมป้ายความกว้าง/ลึก/สูง
  flow       กล่อง + ลูกศร — ห่วงโซ่อาหาร วัฏจักร ขั้นตอนการทดลอง ผังความคิด

ไม่เรียกตรง ๆ — เรียกผ่าน gen_math_images.py ซึ่ง merge DRAWERS ของไฟล์นี้เข้าไป
รันผ่านตัวห่อ: eduone-py <ชื่อไฟล์นี้> <args>  (หา Python 3.12 ให้เองทุก OS)
"""
import math

LINE = "#174a96"
ACCENT = "#b71c3e"
INK = "#1e1e1e"
FILL = "#e8f0fc"


def _fig(plt, spec, default):
    fig, ax = plt.subplots(figsize=tuple(spec.get("figSize", default)),
                           dpi=spec.get("dpi", 170))
    ax.set_aspect("equal")
    ax.axis("off")
    ax.grid(False)
    return fig, ax


def _save(fig, ax, spec, out_path):
    if spec.get("title"):
        ax.set_title(spec["title"])
    ax.margins(0.14)
    fig.tight_layout()
    fig.savefig(out_path, dpi=spec.get("dpi", 170), facecolor="white")
    return out_path


# ------------------------------------------------------------------ วงจรไฟฟ้า
def _sym(ax, kind, x, y, horiz, label, gap=0.62):
    """วาดสัญลักษณ์อุปกรณ์ 1 ตัวที่จุด (x,y) — คืนช่วงที่กินพื้นที่บนสาย"""
    from matplotlib.patches import Circle, Rectangle
    h = gap / 2.0
    if kind == "battery":
        # ขีดยาว(บวก) + ขีดสั้น(ลบ)
        if horiz:
            ax.plot([x - 0.10, x - 0.10], [y - 0.30, y + 0.30], color=INK, lw=2.6)
            ax.plot([x + 0.10, x + 0.10], [y - 0.15, y + 0.15], color=INK, lw=2.6)
        else:
            ax.plot([x - 0.30, x + 0.30], [y + 0.10, y + 0.10], color=INK, lw=2.6)
            ax.plot([x - 0.15, x + 0.15], [y - 0.10, y - 0.10], color=INK, lw=2.6)
    elif kind == "lamp":
        ax.add_patch(Circle((x, y), 0.30, facecolor="#fff6d8", edgecolor=INK, lw=1.8, zorder=3))
        r = 0.30 * 0.72
        ax.plot([x - r, x + r], [y - r, y + r], color=INK, lw=1.4, zorder=4)
        ax.plot([x - r, x + r], [y + r, y - r], color=INK, lw=1.4, zorder=4)
    elif kind == "resistor":
        w, hh = (0.66, 0.26) if horiz else (0.26, 0.66)
        ax.add_patch(Rectangle((x - w / 2, y - hh / 2), w, hh, facecolor="white",
                               edgecolor=INK, lw=1.8, zorder=3))
    elif kind == "switch":
        if horiz:
            ax.plot([x - h, x - 0.16], [y, y], color=INK, lw=2.0)
            ax.plot([x + 0.16, x + h], [y, y], color=INK, lw=2.0)
            ax.plot([x - 0.16, x + 0.13], [y, y + 0.30], color=INK, lw=2.0)
        else:
            ax.plot([x, x], [y - h, y - 0.16], color=INK, lw=2.0)
            ax.plot([x, x], [y + 0.16, y + h], color=INK, lw=2.0)
            ax.plot([x, x + 0.30], [y - 0.16, y + 0.13], color=INK, lw=2.0)
        ax.plot([x - 0.16], [y], "o", color=INK, markersize=4, zorder=4)
        ax.plot([x + 0.16], [y], "o", color=INK, markersize=4, zorder=4)
    elif kind in ("ammeter", "voltmeter"):
        ax.add_patch(Circle((x, y), 0.30, facecolor="white", edgecolor=INK, lw=1.8, zorder=3))
        ax.annotate("A" if kind == "ammeter" else "V", (x, y), ha="center", va="center",
                    color=INK, zorder=4)
    if label:
        ax.annotate(label, (x, y - 0.46) if horiz else (x + 0.46, y),
                    ha="center" if horiz else "left",
                    va="top" if horiz else "center", color=INK)


def draw_circuit(spec, out_path):
    from gen_math_images import _mpl
    plt, ok = _mpl()
    if not ok:
        raise RuntimeError("ต้องมี matplotlib")
    W = float(spec.get("w", 6.0))
    H = float(spec.get("h", 3.4))
    fig, ax = _fig(plt, spec, (W * 0.95, H * 1.05))

    def wire(p1, p2):
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=INK, lw=2.0,
                solid_capstyle="round", zorder=2)

    sides = {"bottom": ((0, 0), (W, 0)), "top": ((0, H), (W, H)),
             "left": ((0, 0), (0, H)), "right": ((W, 0), (W, H))}
    comps = spec.get("components", [])
    bysid = {}
    for c in comps:
        bysid.setdefault(c.get("side", "top"), []).append(c)

    # ลากสายรอบวง โดยเว้นช่องตรงตำแหน่งอุปกรณ์
    for side, (a, b) in sides.items():
        horiz = a[1] == b[1]
        items = sorted(bysid.get(side, []), key=lambda c: c.get("pos", 0.5))
        cuts = []
        for c in items:
            t = c.get("pos", 0.5)
            gap = c.get("gap", 0.62)
            cx = a[0] + (b[0] - a[0]) * t
            cy = a[1] + (b[1] - a[1]) * t
            cuts.append((t, gap, cx, cy, c))
        cur = 0.0
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        for t, gap, cx, cy, c in cuts:
            t0 = t - (gap / 2.0) / L
            p_end = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
            p_start = (a[0] + (b[0] - a[0]) * cur, a[1] + (b[1] - a[1]) * cur)
            wire(p_start, p_end)
            _sym(ax, c.get("kind", "resistor"), cx, cy, horiz, c.get("label"), gap)
            cur = t + (gap / 2.0) / L
        wire((a[0] + (b[0] - a[0]) * cur, a[1] + (b[1] - a[1]) * cur), b)

    # กิ่งขนานภายใน (แนวตั้ง) — สำหรับวงจรขนาน
    for br in spec.get("branches", []):
        x = W * br.get("x", 0.5)
        items = sorted(br.get("components", []), key=lambda c: c.get("pos", 0.5))
        cur = 0.0
        for c in items:
            t = c.get("pos", 0.5)
            gap = c.get("gap", 0.62)
            wire((x, H * cur), (x, H * t - gap / 2.0))
            _sym(ax, c.get("kind", "lamp"), x, H * t, False, c.get("label"), gap)
            cur = t + (gap / 2.0) / H
        wire((x, H * cur), (x, H))
    return _save(fig, ax, spec, out_path)


# ------------------------------------------------------------------ แผนภาพแรง
def draw_forces(spec, out_path):
    from gen_math_images import _mpl
    plt, ok = _mpl()
    if not ok:
        raise RuntimeError("ต้องมี matplotlib")
    from matplotlib.patches import Circle, Rectangle
    fig, ax = _fig(plt, spec, (4.6, 4.0))
    shape = spec.get("shape", "box")
    s = float(spec.get("size", 1.2))
    if shape == "circle":
        ax.add_patch(Circle((0, 0), s / 2.0, facecolor=FILL, edgecolor=INK, lw=2, zorder=3))
    else:
        ax.add_patch(Rectangle((-s / 2, -s / 2), s, s, facecolor=FILL,
                               edgecolor=INK, lw=2, zorder=3))
    if spec.get("label"):
        ax.annotate(spec["label"], (0, 0), ha="center", va="center", color=INK, zorder=4)
    if spec.get("surface"):
        y = -s / 2
        ax.plot([-2.4, 2.4], [y, y], color=INK, lw=2.2)
        for k in range(-11, 12):
            x0 = k * 0.2
            ax.plot([x0, x0 - 0.14], [y, y - 0.20], color="#8a8a8a", lw=1.2)
    for f in spec.get("arrows", []):
        a = math.radians(f.get("angle", 0))
        L = f.get("length", 1.7)
        r0 = s / 2.0 * 1.02
        x0, y0 = r0 * math.cos(a), r0 * math.sin(a)
        x1, y1 = x0 + L * math.cos(a), y0 + L * math.sin(a)
        col = f.get("color", ACCENT)
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", color=col, lw=2.4,
                                    mutation_scale=18))
        ax.plot([x0, x1], [y0, y1], color=col, lw=0.1)   # ให้ autoscale เห็นลูกศร
        if f.get("label"):
            ax.annotate(f["label"], (x1 + 0.16 * math.cos(a), y1 + 0.16 * math.sin(a)),
                        ha="left" if math.cos(a) >= -0.3 else "right",
                        va="bottom" if math.sin(a) >= 0 else "top", color=col)
    return _save(fig, ax, spec, out_path)


# ------------------------------------------------------------------- อะตอม
def draw_atom(spec, out_path):
    from gen_math_images import _mpl
    plt, ok = _mpl()
    if not ok:
        raise RuntimeError("ต้องมี matplotlib")
    from matplotlib.patches import Circle
    fig, ax = _fig(plt, spec, (4.4, 4.2))
    shells = spec.get("shells", [2, 8, 1])
    ax.add_patch(Circle((0, 0), 0.42, facecolor="#f7d9e0", edgecolor=ACCENT, lw=1.8, zorder=4))
    p, n = spec.get("protons"), spec.get("neutrons")
    if p is not None:
        txt = "%dp" % p + (("\n%dn" % n) if n is not None else "")
        ax.annotate(txt, (0, 0), ha="center", va="center", color=ACCENT, zorder=5)
    for i, cnt in enumerate(shells, start=1):
        r = 0.42 + i * 0.62
        ax.add_patch(Circle((0, 0), r, facecolor="none", edgecolor="#9aa7b6",
                            lw=1.2, linestyle=(0, (4, 3)), zorder=2))
        for k in range(cnt):
            a = 2 * math.pi * k / cnt + (math.pi / 6 if i % 2 else 0)
            ax.plot(r * math.cos(a), r * math.sin(a), "o", color=LINE,
                    markersize=9, zorder=3)
    if spec.get("label"):
        ax.annotate(spec["label"], (0, -(0.42 + len(shells) * 0.62) - 0.42),
                    ha="center", va="top", color=INK)
    return _save(fig, ax, spec, out_path)


# --------------------------------------------------------------- รูปทรง 3 มิติ
def draw_solid3d(spec, out_path):
    from gen_math_images import _mpl
    plt, ok = _mpl()
    if not ok:
        raise RuntimeError("ต้องมี matplotlib")
    from matplotlib.patches import Polygon, Ellipse
    shape = spec.get("shape", "cuboid")
    w = float(spec.get("w", 3.0))
    h = float(spec.get("h", 2.2))
    d = float(spec.get("d", 1.4))
    fig, ax = _fig(plt, spec, (4.6, 3.8))
    ox, oy = d * 0.55, d * 0.42          # ภาพฉายเฉียง
    lab = spec.get("labels", {})

    def poly(pts, fc=FILL, alpha=1.0, z=3):
        ax.add_patch(Polygon(pts, closed=True, facecolor=fc, edgecolor=INK,
                             lw=1.9, alpha=alpha, zorder=z))

    def dash(p1, p2):
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=INK, lw=1.4,
                linestyle=(0, (4, 3)), zorder=2)

    def solid(p1, p2):
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=INK, lw=1.9, zorder=5)

    if shape in ("cuboid", "cube"):
        if shape == "cube":
            h = d = w
            ox, oy = d * 0.55, d * 0.42
        front = [(0, 0), (w, 0), (w, h), (0, h)]
        back = [(x + ox, y + oy) for x, y in front]
        # หน้าหลัง: เติมสีอย่างเดียว ไม่ตีเส้น เพื่อไม่ให้ทับเส้นประ
        ax.add_patch(Polygon(back, closed=True, facecolor="#f2f6fd",
                             edgecolor="none", zorder=1))
        # มุมหลังซ้ายล่างถูกบัง -> เส้นประ 3 เส้น
        dash(back[0], back[1]); dash(back[0], back[3]); dash(back[0], front[0])
        solid(back[1], back[2]); solid(back[2], back[3])
        for i in (1, 2, 3):
            solid(front[i], back[i])
        poly(front, FILL, z=4)
        if lab.get("w"):
            ax.annotate(lab["w"], (w / 2, -0.22), ha="center", va="top", color=INK)
        if lab.get("h"):
            ax.annotate(lab["h"], (-0.18, h / 2), ha="right", va="center", color=INK)
        if lab.get("d"):
            ax.annotate(lab["d"], (w + ox / 2 + 0.16, oy / 2 - 0.10), ha="left",
                        va="top", color=INK)
    elif shape == "cylinder":
        from matplotlib.patches import Arc
        rx = w / 2.0
        # ลำตัว: เติมสีก่อน แล้วค่อยตีเฉพาะเส้นข้าง (ไม่เอาเส้นบน-ล่างของสี่เหลี่ยม)
        ax.add_patch(Polygon([(0, 0), (w, 0), (w, h), (0, h)], closed=True,
                             facecolor=FILL, edgecolor="none", zorder=2))
        # ฐานล่าง: ครึ่งหลังถูกบัง -> เส้นประ / ครึ่งหน้า -> เส้นทึบ
        ax.add_patch(Ellipse((rx, 0), w, d, facecolor="none", edgecolor=INK,
                             lw=1.3, linestyle=(0, (4, 3)), zorder=3))
        ax.add_patch(Arc((rx, 0), w, d, theta1=180, theta2=360,
                         edgecolor=INK, lw=1.9, zorder=5))
        ax.add_patch(Ellipse((rx, h), w, d, facecolor="#f2f6fd", edgecolor=INK,
                             lw=1.9, zorder=6))
        solid((0, 0), (0, h)); solid((w, 0), (w, h))
        if lab.get("h"):
            ax.annotate(lab["h"], (-0.18, h / 2), ha="right", va="center", color=INK)
        if lab.get("r"):
            ax.plot([rx, w], [h, h], color=ACCENT, lw=1.8, zorder=7)
            ax.plot([rx], [h], "o", color=ACCENT, markersize=4, zorder=8)
            ax.annotate(lab["r"], (rx + rx / 2, h + d * 0.45), ha="center",
                        va="bottom", color=ACCENT, zorder=8)
    elif shape in ("cone", "pyramid"):
        if shape == "cone":
            ax.add_patch(Ellipse((w / 2, 0), w, d, facecolor=FILL, edgecolor=INK,
                                 lw=1.9, zorder=3))
            ax.plot([0, w / 2], [0, h], color=INK, lw=1.9, zorder=4)
            ax.plot([w, w / 2], [0, h], color=INK, lw=1.9, zorder=4)
        else:
            base = [(0, 0), (w, 0), (w + ox, oy), (ox, oy)]
            poly(base, "#f2f6fd", z=2)
            apex = (w / 2 + ox / 2, h)
            for b in base:
                ax.plot([b[0], apex[0]], [b[1], apex[1]], color=INK, lw=1.9, zorder=3)
        if lab.get("h"):
            ax.plot([w / 2, w / 2], [0, h], color=ACCENT, lw=1.4,
                    linestyle=(0, (4, 3)), zorder=5)
            ax.annotate(lab["h"], (w / 2 + 0.12, h / 2), ha="left", va="center", color=ACCENT)
    elif shape == "sphere":
        from matplotlib.patches import Circle
        r = w / 2.0
        ax.add_patch(Circle((0, 0), r, facecolor=FILL, edgecolor=INK, lw=1.9, zorder=3))
        ax.add_patch(Ellipse((0, 0), 2 * r, r * 0.62, facecolor="none",
                             edgecolor=INK, lw=1.3, linestyle=(0, (4, 3)), zorder=4))
        if lab.get("r"):
            ax.plot([0, r], [0, 0], color=ACCENT, lw=1.6, zorder=5)
            ax.annotate(lab["r"], (r / 2, 0.12), ha="center", va="bottom", color=ACCENT)
    return _save(fig, ax, spec, out_path)


# ------------------------------------------------------- กล่อง + ลูกศร (ห่วงโซ่)
def draw_flow(spec, out_path):
    from gen_math_images import _mpl
    plt, ok = _mpl()
    if not ok:
        raise RuntimeError("ต้องมี matplotlib")
    from matplotlib.patches import FancyBboxPatch
    nodes = spec["nodes"]
    down = spec.get("direction", "right") == "down"
    bw, bh, gap = spec.get("boxW", 2.0), spec.get("boxH", 0.9), spec.get("gap", 1.0)
    n = len(nodes)
    # คุมสัดส่วนไม่ให้ภาพยืดจนกล่องแบนและตัวอักษรเล็กเกินอ่าน
    unit = spec.get("unitIn", 0.62)          # นิ้วต่อ 1 หน่วยข้อมูล
    if down:
        size = (bw * unit + 1.0, (n * bh + (n - 1) * gap) * unit + 1.0)
    else:
        size = ((n * bw + (n - 1) * gap) * unit + 0.6, bh * unit + 1.4)
    fig, ax = _fig(plt, spec, size)
    ax.set_aspect("auto")
    fs = spec.get("fontSize", 11)

    pos = []
    for i, nd in enumerate(nodes):
        x, y = (0, -i * (bh + gap)) if down else (i * (bw + gap), 0)
        ax.add_patch(FancyBboxPatch((x, y), bw, bh,
                                    boxstyle="round,pad=0.02,rounding_size=0.12",
                                    facecolor=nd.get("color", FILL),
                                    edgecolor=INK, lw=1.8, zorder=3))
        ax.annotate(nd["text"], (x + bw / 2, y + bh / 2), ha="center", va="center",
                    color=INK, zorder=4, fontsize=fs)
        pos.append((x, y))
    for i in range(n - 1):
        x, y = pos[i]
        if down:
            p1, p2 = (x + bw / 2, y), (x + bw / 2, y - gap)
        else:
            p1, p2 = (x + bw, y + bh / 2), (x + bw + gap, y + bh / 2)
        ax.annotate("", xy=p2, xytext=p1,
                    arrowprops=dict(arrowstyle="-|>", color=ACCENT, lw=2.2,
                                    mutation_scale=18))
        lab = nodes[i].get("arrowLabel") or spec.get("arrowLabel")
        if lab:
            ax.annotate(lab, ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2 + 0.10),
                        ha="center", va="bottom", color=ACCENT, fontsize=fs - 2)
    if down:
        ax.set_xlim(-0.3, bw + 0.3)
        ax.set_ylim(-(n - 1) * (bh + gap) - 0.4, bh + 0.4)
    else:
        ax.set_xlim(-0.3, (n - 1) * (bw + gap) + bw + 0.3)
        ax.set_ylim(-0.5, bh + 0.7)
    return _save(fig, ax, spec, out_path)


SCIENCE_DRAWERS = {
    "circuit": draw_circuit,
    "forces": draw_forces,
    "atom": draw_atom,
    "solid3d": draw_solid3d,
    "flow": draw_flow,
}
