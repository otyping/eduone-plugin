# -*- coding: utf-8 -*-
"""
plant_diagrams.py — แผนภาพพืชดอกสำหรับข้อสอบ/เนื้อหา (โมดูลเสริมของ gen_math_images.py)

ชนิดที่วาดได้
  plantwhole      ต้นพืชดอกทั้งต้น (ราก ลำต้น ใบ ดอก) พร้อมป้ายชี้ ก ข ค ง หรือชื่อไทย
  flowersection   ดอกผ่าตามยาว — กลีบเลี้ยง กลีบดอก เกสรเพศผู้ (ก้านชูอับเรณู+อับเรณู)
                  เกสรเพศเมีย (ยอด+ก้าน+รังไข่+ออวุล) บนฐานรองดอก
  dyestem         กิ่งพืชแช่ในน้ำสี — สีเดินขึ้นตามลำต้นและเส้นใบ (กิจกรรมท่อลำเลียง)
  photosynthesis  แผนภาพการสังเคราะห์ด้วยแสง — แสง/แก๊สเข้า/แก๊สออก/น้ำ/น้ำตาล
  leafstarch      ใบพืชทดสอบแป้งด้วยสารละลายไอโอดีน — ปิดกระดาษดำ / ผลการเปลี่ยนสี

ทุกชนิดล็อกกรอบภาพ (xlim/ylim) ตายตัว ตัวเลือกที่เป็นรูปในข้อเดียวกันจึงมีมาตราส่วนเท่ากัน

ป้ายในรูปห้ามใช้ตัวห้อย/ตัวยกยูนิโคด (ฟอนต์ TH Sarabun New ไม่มี glyph)
ไม่เรียกตรง ๆ — เรียกผ่าน gen_math_images.py ซึ่ง merge DRAWERS ของไฟล์นี้เข้าไป
ใช้ Python 3.12: %LOCALAPPDATA%\\Programs\\Python\\Python312\\python.exe
"""
import math

INK = "#1e1e1e"
STEM = "#5aa832"
STEM_DARK = "#3d7a20"
LEAF = "#77c043"
LEAF_EDGE = "#4a8c24"
VEIN = "#4a8c24"
ROOT = "#c39b6d"
ROOT_EDGE = "#8d6748"
SOIL = "#9c7b58"
PETAL = "#f4a7c8"
PETAL_EDGE = "#c96f9a"
SEPAL = "#69b04a"
ANTHER = "#f2c94c"
ANTHER_EDGE = "#c79b16"
DYE = "#d1345b"
WATER = "#2f80c9"
STARCH = "#2b2c46"
SUN = "#f7c948"


def _fig(plt, spec, default):
    fig, ax = plt.subplots(figsize=tuple(spec.get("figSize", default)),
                           dpi=spec.get("dpi", 170))
    ax.set_aspect("equal")
    ax.axis("off")
    ax.grid(False)
    return fig, ax


def _save(fig, ax, spec, out_path, xlim, ylim):
    ax.set_xlim(*spec.get("xLim", xlim))
    ax.set_ylim(*spec.get("yLim", ylim))
    if spec.get("title"):
        ax.set_title(spec["title"])
    fig.tight_layout(pad=0.2)
    fig.savefig(out_path, dpi=spec.get("dpi", 170), facecolor="white")
    import matplotlib.pyplot as plt          # ปิดรูปกัน memory บวมเมื่อวาดหลายไฟล์
    plt.close(fig)
    return out_path


def _rot(pts, ang, cx=0.0, cy=0.0):
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    return [(cx + x * c - y * s, cy + x * s + y * c) for x, y in pts]


def _leaf_patch(x, y, length, width, angle, face=LEAF, edge=LEAF_EDGE, lw=1.6, z=2):
    """ใบรูปหอก — โคนใบที่ (x,y) ปลายใบตามมุม angle (องศา) คืน PathPatch"""
    from matplotlib.path import Path
    from matplotlib.patches import PathPatch
    lo, w = length, width / 2.0
    local = [(0, 0),
             (lo * 0.22, w), (lo * 0.62, w * 0.95), (lo, 0),          # ขอบบน
             (lo * 0.62, -w * 0.95), (lo * 0.22, -w), (0, 0)]         # ขอบล่าง
    p = _rot(local, angle, x, y)
    verts = [p[0], p[1], p[2], p[3], p[4], p[5], p[6]]
    codes = [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4,
             Path.CURVE4, Path.CURVE4, Path.CURVE4]
    return PathPatch(Path(verts, codes), facecolor=face, edgecolor=edge, lw=lw, zorder=z)


def _midrib(ax, x, y, length, angle, color=VEIN, lw=1.1, z=3, width=None):
    """เส้นกลางใบ + เส้นแขนง — spread อิงครึ่งความกว้างใบ เพื่อไม่ให้เส้นทะลุขอบใบ"""
    half = (width / 2.0) if width else length * 0.11
    (x2, y2), = _rot([(length * 0.94, 0)], angle, x, y)
    ax.plot([x, x2], [y, y2], color=color, lw=lw, zorder=z)
    for t in (0.3, 0.5, 0.7):
        (bx, by), = _rot([(length * t, 0)], angle, x, y)
        te = t + 0.13
        taper = max(0.0, 1.0 - (2.0 * te - 1.0) ** 2)      # ใบสอบเข้าใกล้ปลาย
        for side in (1, -1):
            (ex, ey), = _rot([(length * te, side * half * 0.62 * taper)], angle, x, y)
            ax.plot([bx, ex], [by, ey], color=color, lw=lw * 0.7, zorder=z)


def _callout(ax, text, target, label_xy, r=0.30, fs=15):
    """ป้ายตัวอักษรในวงกลม + เส้นชี้ไปยังส่วนของพืช"""
    from matplotlib.patches import Circle
    ax.annotate("", xy=target, xytext=label_xy,
                arrowprops=dict(arrowstyle="-", color=INK, lw=1.2,
                                shrinkA=r * 34, shrinkB=1))
    ax.add_patch(Circle(label_xy, r, facecolor="white", edgecolor=INK, lw=1.5, zorder=6))
    ax.annotate(text, label_xy, ha="center", va="center", fontsize=fs, zorder=7)


def _name(ax, text, target, label_xy, fs=14, ha=None):
    ax.annotate("", xy=target, xytext=label_xy,
                arrowprops=dict(arrowstyle="-", color=INK, lw=1.1, shrinkA=6, shrinkB=1))
    if ha is None:
        ha = "right" if label_xy[0] < target[0] else "left"
    dx = -0.12 if ha == "right" else 0.12
    ax.annotate(text, (label_xy[0] + dx, label_xy[1]), ha=ha, va="center",
                fontsize=fs, color=INK, zorder=7)


# ------------------------------------------------------------------ ต้นพืชทั้งต้น
PLANT_LABEL_POINTS = {
    "flower": ((0.30, 5.05), (2.35, 5.35)),
    "leaf":   ((-1.25, 2.85), (-2.55, 3.45)),
    "stem":   ((0.16, 1.70), (2.35, 1.85)),
    "root":   ((-0.78, -1.58), (-2.55, -1.30)),
}
PLANT_NAMES = {"flower": "ดอก", "leaf": "ใบ", "stem": "ลำต้น", "root": "ราก"}


def _flower_head(ax, cx, cy, r=0.42, petals=6, z=4):
    from matplotlib.patches import Circle, Ellipse
    for i in range(petals):
        a = 360.0 / petals * i
        px, py = cx + r * 1.05 * math.cos(math.radians(a)), cy + r * 1.05 * math.sin(math.radians(a))
        ax.add_patch(Ellipse((px, py), r * 1.15, r * 0.80, angle=a,
                             facecolor=PETAL, edgecolor=PETAL_EDGE, lw=1.3, zorder=z))
    ax.add_patch(Circle((cx, cy), r * 0.52, facecolor=ANTHER, edgecolor=ANTHER_EDGE,
                        lw=1.3, zorder=z + 1))


def draw_plantwhole(spec, out_path):
    from gen_math_images import _mpl
    from matplotlib.patches import Rectangle, FancyBboxPatch
    plt, ok = _mpl()
    if not ok:
        raise RuntimeError("ต้องมี matplotlib")
    fig, ax = _fig(plt, spec, (4.6, 5.4))

    # ดิน
    ax.add_patch(Rectangle((-3.2, -2.5), 6.4, 2.5, facecolor=SOIL, edgecolor="none", zorder=0))
    ax.plot([-3.2, 3.2], [0, 0], color="#6f5540", lw=1.6, zorder=1)

    # ราก — รากแก้ว + รากแขนง
    ax.plot([0, 0], [0, -1.95], color=ROOT, lw=6.0, solid_capstyle="round", zorder=2)
    ax.plot([0, 0], [0, -1.95], color=ROOT_EDGE, lw=1.0, zorder=3)
    for y0, dx, dy in ((-0.45, -1.05, -0.75), (-0.45, 1.05, -0.75),
                       (-1.05, -0.85, -0.60), (-1.05, 0.85, -0.60),
                       (-1.60, -0.55, -0.40), (-1.60, 0.55, -0.40)):
        ax.plot([0, dx * 0.55, dx], [y0, y0 + dy * 0.45, y0 + dy],
                color=ROOT, lw=2.6, solid_capstyle="round", zorder=2)

    # ลำต้น
    ax.add_patch(FancyBboxPatch((-0.15, 0), 0.30, 4.55, boxstyle="round,pad=0.02,rounding_size=0.12",
                                facecolor=STEM, edgecolor=STEM_DARK, lw=1.4, zorder=3))
    # ใบ
    for x0, y0, ln, wd, ang in ((-0.10, 2.75, 1.65, 0.85, 168),
                                (0.10, 3.55, 1.45, 0.75, 18),
                                (-0.10, 1.85, 1.45, 0.75, 200)):
        ax.add_patch(_leaf_patch(x0, y0, ln, wd, ang))
        _midrib(ax, x0, y0, ln, ang, width=wd)
    # ดอก
    ax.plot([0, 0.30], [4.40, 4.85], color=STEM, lw=3.0, solid_capstyle="round", zorder=3)
    _flower_head(ax, 0.42, 5.05, r=0.44)

    labels = spec.get("labels") or {}
    if spec.get("showNames"):
        for part, (target, lab) in PLANT_LABEL_POINTS.items():
            _name(ax, PLANT_NAMES[part], target, lab)
    for part, text in labels.items():
        if part in PLANT_LABEL_POINTS:
            target, lab = PLANT_LABEL_POINTS[part]
            _callout(ax, text, target, lab)
    return _save(fig, ax, spec, out_path, (-3.2, 3.2), (-2.6, 6.1))


# --------------------------------------------------------------------- ดอกผ่าซีก
FLOWER_LABEL_POINTS = {
    "sepal":  ((-1.20, -0.36), (-2.70, -0.95)),
    "petal":  ((-1.72, 1.62), (-3.00, 2.15)),
    "stamen": ((1.24, 1.72), (2.95, 2.15)),
    "pistil": ((0.16, 2.62), (1.85, 3.25)),
}
FLOWER_NAMES = {"sepal": "กลีบเลี้ยง", "petal": "กลีบดอก",
                "stamen": "เกสรเพศผู้", "pistil": "เกสรเพศเมีย"}


def _petal(ax, side, z=1):
    """กลีบดอกด้านข้าง — side = -1 ซ้าย, +1 ขวา, 0 กลีบหลัง"""
    from matplotlib.path import Path
    from matplotlib.patches import PathPatch
    if side == 0:
        verts = [(-0.78, 0.20), (-1.05, 1.40), (-0.62, 2.16), (0.0, 2.18),
                 (0.62, 2.16), (1.05, 1.40), (0.78, 0.20)]
    else:
        s = side
        verts = [(s * 0.55, 0.18), (s * 1.35, 0.55), (s * 2.05, 1.30), (s * 1.86, 1.72),
                 (s * 1.62, 2.06), (s * 0.90, 1.55), (s * 0.52, 0.95)]
    codes = [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4,
             Path.CURVE4, Path.CURVE4, Path.CURVE4]
    ax.add_patch(PathPatch(Path(verts, codes), facecolor=PETAL, edgecolor=PETAL_EDGE,
                           lw=1.5, zorder=z))


def _sepal(ax, side, z=2):
    from matplotlib.path import Path
    from matplotlib.patches import PathPatch
    s = side
    verts = [(s * 0.28, 0.06), (s * 0.75, -0.02), (s * 1.20, -0.30), (s * 1.48, -0.62),
             (s * 1.02, -0.44), (s * 0.62, -0.30), (s * 0.24, -0.18)]
    codes = [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4,
             Path.CURVE4, Path.CURVE4, Path.CURVE4]
    ax.add_patch(PathPatch(Path(verts, codes), facecolor=SEPAL, edgecolor=STEM_DARK,
                           lw=1.4, zorder=z))


def draw_flowersection(spec, out_path):
    from gen_math_images import _mpl
    from matplotlib.patches import Ellipse, Polygon
    plt, ok = _mpl()
    if not ok:
        raise RuntimeError("ต้องมี matplotlib")
    fig, ax = _fig(plt, spec, (5.2, 4.6))

    # ก้านดอก + ฐานรองดอก
    ax.plot([0, 0], [-1.75, -0.55], color=SEPAL, lw=7.0, solid_capstyle="round", zorder=2)
    ax.add_patch(Polygon([(-0.20, -0.62), (-0.62, 0.24), (0.62, 0.24), (0.20, -0.62)],
                         closed=True, facecolor=SEPAL, edgecolor=STEM_DARK, lw=1.4, zorder=2))
    # กลีบดอก (หลังสุด)
    _petal(ax, -1, z=1)
    _petal(ax, 1, z=1)
    _petal(ax, 0, z=1)
    # กลีบเลี้ยง
    _sepal(ax, -1)
    _sepal(ax, 1)
    # เกสรเพศผู้ — ก้านชูอับเรณูโค้งออก + อับเรณูสีเหลือง
    for s, tipx, tipy in ((-1, -0.78, 1.86), (-1, -1.24, 1.62), (1, 0.78, 1.86), (1, 1.24, 1.62)):
        xs = [s * 0.16, s * 0.30, tipx]
        ys = [0.28, 1.05, tipy]
        ax.plot(xs, ys, color=SEPAL, lw=2.0, solid_capstyle="round", zorder=3)
        ax.add_patch(Ellipse((tipx, tipy + 0.14), 0.30, 0.44, angle=s * 18,
                             facecolor=ANTHER, edgecolor=ANTHER_EDGE, lw=1.3, zorder=4))
    # เกสรเพศเมีย — รังไข่ + ออวุล + ก้าน + ยอด
    ax.add_patch(Ellipse((0, 0.46), 0.80, 0.94, facecolor="#57a83c",
                         edgecolor=STEM_DARK, lw=1.5, zorder=4))
    ax.add_patch(Ellipse((0, 0.44), 0.26, 0.36, facecolor="white",
                         edgecolor=STEM_DARK, lw=1.2, zorder=5))
    ax.add_patch(Ellipse((0, 0.44), 0.11, 0.15, facecolor="#1aa7b5",
                         edgecolor="none", zorder=6))
    ax.plot([0, 0], [0.90, 2.50], color="#57a83c", lw=3.4, solid_capstyle="round", zorder=4)
    ax.add_patch(Ellipse((0, 2.62), 0.36, 0.30, facecolor="#3f8f26",
                         edgecolor=STEM_DARK, lw=1.4, zorder=5))

    labels = spec.get("labels") or {}
    if spec.get("showNames"):
        for part, (target, lab) in FLOWER_LABEL_POINTS.items():
            _name(ax, FLOWER_NAMES[part], target, lab)
    for part, text in labels.items():
        if part in FLOWER_LABEL_POINTS:
            target, lab = FLOWER_LABEL_POINTS[part]
            _callout(ax, text, target, lab)
    return _save(fig, ax, spec, out_path, (-3.6, 3.6), (-2.0, 3.9))


# --------------------------------------------------- กิ่งพืชแช่น้ำสี (ท่อลำเลียง)
def draw_dyestem(spec, out_path):
    from gen_math_images import _mpl
    from matplotlib.patches import Rectangle, FancyBboxPatch
    plt, ok = _mpl()
    if not ok:
        raise RuntimeError("ต้องมี matplotlib")
    fig, ax = _fig(plt, spec, (4.4, 5.0))

    level = float(spec.get("level", 1.30))          # ระดับน้ำในแก้ว
    rise = float(spec.get("rise", 4.30))            # สีเดินขึ้นถึงความสูงเท่าใด
    dye_on = bool(spec.get("dyed", True))
    stem_col = DYE if dye_on else STEM
    liquid = DYE if dye_on else WATER

    # แก้วน้ำ
    ax.add_patch(Rectangle((-1.15, 0), 2.30, level, facecolor=liquid, alpha=0.32,
                           edgecolor="none", zorder=1))
    ax.plot([-1.15, -1.15, 1.15, 1.15], [2.15, 0, 0, 2.15],
            color="#7b8794", lw=2.2, zorder=3)
    ax.plot([-1.15, 1.15], [level, level], color=liquid, lw=2.0, zorder=3)

    # ลำต้น
    ax.add_patch(FancyBboxPatch((-0.13, 0.22), 0.26, 4.25,
                                boxstyle="round,pad=0.02,rounding_size=0.10",
                                facecolor=STEM, edgecolor=STEM_DARK, lw=1.4, zorder=4))
    # แนวสีที่เดินขึ้นในท่อลำเลียง
    ax.plot([0, 0], [0.28, rise], color=stem_col, lw=2.6, solid_capstyle="round", zorder=5)

    # ใบ + เส้นใบ (ย้อมสีถ้าสีเดินถึง)
    for x0, y0, ln, wd, ang in ((-0.09, 3.05, 1.55, 0.80, 166),
                                (0.09, 3.85, 1.40, 0.72, 20),
                                (-0.09, 2.35, 1.40, 0.72, 198)):
        ax.add_patch(_leaf_patch(x0, y0, ln, wd, ang))
        _midrib(ax, x0, y0, ln, ang, width=wd,
                color=stem_col if (dye_on and y0 <= rise) else VEIN,
                lw=1.4 if dye_on else 1.1)
    if spec.get("caption"):
        ax.annotate(spec["caption"], (0, -0.62), ha="center", va="top", fontsize=14, color=INK)
    return _save(fig, ax, spec, out_path, (-2.6, 2.6), (-1.15, 5.35))


# ------------------------------------------------------- การสังเคราะห์ด้วยแสง
def draw_photosynthesis(spec, out_path):
    from gen_math_images import _mpl
    from matplotlib.patches import Rectangle, Circle, FancyBboxPatch
    plt, ok = _mpl()
    if not ok:
        raise RuntimeError("ต้องมี matplotlib")
    fig, ax = _fig(plt, spec, (6.4, 4.6))
    lb = dict(spec.get("labels") or {})

    # ดวงอาทิตย์
    sx, sy = -3.55, 3.95
    ax.add_patch(Circle((sx, sy), 0.50, facecolor=SUN, edgecolor="#d9a400",
                        lw=1.4, zorder=3))
    for i in range(12):
        a = math.radians(30 * i)
        ax.plot([sx + 0.62 * math.cos(a), sx + 0.84 * math.cos(a)],
                [sy + 0.62 * math.sin(a), sy + 0.84 * math.sin(a)],
                color="#d9a400", lw=1.6, zorder=3)

    # ดิน + ราก + ลำต้น + ใบ
    ax.add_patch(Rectangle((-4.7, -1.7), 9.4, 1.7, facecolor=SOIL, edgecolor="none", zorder=0))
    ax.plot([-4.7, 4.7], [0, 0], color="#6f5540", lw=1.6, zorder=1)
    ax.plot([0, 0], [0, -1.30], color=ROOT, lw=5.0, solid_capstyle="round", zorder=2)
    for y0, dx, dy in ((-0.32, -0.85, -0.52), (-0.32, 0.85, -0.52),
                       (-0.80, -0.60, -0.40), (-0.80, 0.60, -0.40)):
        ax.plot([0, dx * 0.55, dx], [y0, y0 + dy * 0.45, y0 + dy],
                color=ROOT, lw=2.2, solid_capstyle="round", zorder=2)
    ax.add_patch(FancyBboxPatch((-0.13, 0), 0.26, 3.05,
                                boxstyle="round,pad=0.02,rounding_size=0.10",
                                facecolor=STEM, edgecolor=STEM_DARK, lw=1.4, zorder=3))
    for x0, y0, ln, wd, ang in ((-0.09, 3.00, 1.62, 0.80, 162),
                                (0.09, 2.62, 1.62, 0.80, 16)):
        ax.add_patch(_leaf_patch(x0, y0, ln, wd, ang))
        _midrib(ax, x0, y0, ln, ang, width=wd)

    def arrow(p0, p1, color, text, tx, ty, ha="center"):
        ax.annotate("", xy=p1, xytext=p0,
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=2.2,
                                    mutation_scale=18, shrinkA=2, shrinkB=2))
        if text:
            ax.annotate(text, (tx, ty), ha=ha, va="center", fontsize=15, color=INK, zorder=7)

    # แสงจากดวงอาทิตย์ -> ใบซ้าย
    arrow((-2.95, 3.62), (-1.30, 3.42), SUN, lb.get("light", "แสง"), -2.15, 4.02)
    # แก๊สเข้าทางใบ (ขวาบน)
    arrow((3.30, 3.60), (1.62, 3.18), "#7b8794", lb.get("gasIn", "ก"), 3.55, 3.68, ha="left")
    # แก๊สออกจากใบ (ขวาล่าง)
    arrow((1.18, 2.52), (3.30, 2.02), "#7b8794", lb.get("gasOut", "ข"), 3.55, 1.94, ha="left")
    # น้ำจากราก -> ขึ้นลำต้น
    ax.annotate("", xy=(0, 2.35), xytext=(0, -0.95),
                arrowprops=dict(arrowstyle="-|>", color=WATER, lw=2.4,
                                mutation_scale=18, shrinkA=2, shrinkB=2))
    ax.annotate(lb.get("water", "น้ำ"), (0.34, 1.15), ha="left", va="center",
                fontsize=15, color=INK, zorder=7)
    if lb.get("sugar"):
        ax.annotate(lb["sugar"], (1.35, 1.95), ha="left", va="center", fontsize=15,
                    color=INK, zorder=7)
        ax.annotate("", xy=(1.25, 2.05), xytext=(0.45, 2.60),
                    arrowprops=dict(arrowstyle="-|>", color="#c98b2e", lw=2.0,
                                    mutation_scale=15, shrinkA=2, shrinkB=2))
    return _save(fig, ax, spec, out_path, (-4.7, 4.7), (-1.7, 5.05))


# ------------------------------------------- ใบพืชทดสอบแป้งด้วยสารละลายไอโอดีน
def draw_leafstarch(spec, out_path):
    """ใบพืชแบนยาว (แบบใบข้าวโพด) วางแนวนอน

    cover  [a, b]  สัดส่วนตามความยาวใบที่ถูกปิดด้วยกระดาษสีดำ (แสดงเป็นแถบดำ)
    stain  none | all | outside | inside
           none=ไม่เปลี่ยนสี · all=เข้มทั้งใบ · outside=เข้มเฉพาะนอกแถบ · inside=เข้มเฉพาะในแถบ
    """
    from gen_math_images import _mpl
    from matplotlib.patches import Rectangle
    plt, ok = _mpl()
    if not ok:
        raise RuntimeError("ต้องมี matplotlib")
    fig, ax = _fig(plt, spec, (3.6, 1.5))

    L, W = 5.2, 1.05
    x0, y0 = -2.6, 0.0
    leaf = _leaf_patch(x0, y0, L, W, 0, face=LEAF, edge=LEAF_EDGE, lw=1.6, z=2)
    ax.add_patch(leaf)
    # เส้นใบวาดก่อนชั้นย้อมสี — บริเวณที่ติดสีจึงเข้มทึบเหมือนผลจริง
    _midrib(ax, x0, y0, L, 0, color=VEIN, lw=1.0, z=2.5, width=W)
    if spec.get("stalk", True):
        ax.plot([x0 - 0.42, x0], [y0, y0], color=STEM, lw=3.0,
                solid_capstyle="round", zorder=1)

    cover = spec.get("cover")
    stain = spec.get("stain", "none")
    ca, cb = (float(cover[0]), float(cover[1])) if cover else (0.42, 0.58)
    xa, xb = x0 + L * ca, x0 + L * cb

    def band(xs, xe, color, z, alpha=1.0):
        r = Rectangle((xs, y0 - W), xe - xs, W * 2, facecolor=color,
                      edgecolor="none", zorder=z, alpha=alpha)
        ax.add_patch(r)
        r.set_clip_path(leaf)

    if stain == "all":
        band(x0 - 0.1, x0 + L + 0.1, STARCH, 3)
    elif stain == "outside":
        band(x0 - 0.1, xa, STARCH, 3)
        band(xb, x0 + L + 0.1, STARCH, 3)
    elif stain == "inside":
        band(xa, xb, STARCH, 3)

    if spec.get("coverVisible"):
        band(xa, xb, "#1c1c1c", 4)
    if spec.get("caption"):
        ax.annotate(spec["caption"], (x0 + L / 2, -0.92), ha="center", va="top",
                    fontsize=14, color=INK)
    return _save(fig, ax, spec, out_path, (-3.0, 3.0), (-1.05, 1.05))


PLANT_DRAWERS = {
    "plantwhole": draw_plantwhole,
    "flowersection": draw_flowersection,
    "dyestem": draw_dyestem,
    "photosynthesis": draw_photosynthesis,
    "leafstarch": draw_leafstarch,
}
