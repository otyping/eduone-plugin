# -*- coding: utf-8 -*-
"""
gen_math_images.py — วาดรูปคณิตศาสตร์/สถิติเป็นไฟล์ PNG จาก spec JSON

สองเครื่องยนต์ ใช้ฟอนต์ TH Sarabun New เหมือนกัน ให้เข้าชุดกับเอกสาร
  - **Pillow** (สไตล์หนังสือเรียน สพฐ. — แกนมีหัวลูกศร จุดกำเนิด O ชื่อแกนไทย)
      `plane` ระนาบพิกัด/กราฟจุด/กราฟเส้นตรง · `triangle` · `rectangle`
      วาดที่ 2 เท่าแล้วย่อ เพื่อให้เส้นและตัวอักษรเรียบ
  - **matplotlib** (สิ่งที่ Pillow ทำได้ไม่ดี — เส้นโค้งต่อเนื่องและแผนภูมิสถิติ)
      `function` เส้นโค้งจากสมการ · `numberline` เส้นจำนวน
      `bar` แผนภูมิแท่ง (แท่งคู่/หลายชุดผ่าน series + hatch) · `pie` แผนภูมิวงกลม (+ leaderLines)
      `histogram` ฮิสโทแกรม · `linechart` กราฟเส้นตามหมวดหมู่
      `scatter` แผนภาพการกระจาย (+ เส้นแนวโน้ม) · `pictograph` แผนภูมิรูปภาพ (รองรับครึ่งรูป)
      `construction` รูปการสร้างทางเรขาคณิต (รังสี ส่วนโค้งวงเวียน เส้นประ เครื่องหมายมุม)
      ถ้าเครื่องไม่มี matplotlib ชนิดกลุ่มนี้จะ FAIL แต่กลุ่ม Pillow ยังทำงานปกติ

ใช้:
  gen_math_images.py <spec.json> [--out-dir DIR]

รูปแบบ spec (ดูตัวอย่างใน {BASE}_images.json):
{
  "outDir": "....../M1-Math_U8_media",
  "images": [
    { "file": "X_05_Q.png", "type": "plane",
      "xRange": [-5, 5], "yRange": [-5, 5], "xStep": 1, "yStep": 1,
      "points": [ {"x": 3, "y": 2, "label": "P"} ] },

    { "file": "X_11_Q.png", "type": "plane",
      "xRange": [0, 8], "yRange": [0, 40], "xStep": 1, "yStep": 5,
      "xTitle": "จำนวนไข่ไก่ (ฟอง)", "yTitle": "ราคา (บาท)",
      "points": [ {"x":1,"y":5}, {"x":2,"y":10} ] },

    { "type": "plane", "line": {"from": [0,0], "to": [5,200]} },      # เส้นตรง
    { "type": "plane", "polyline": [[6,24],[9,30],[12,34]] },          # เส้นหักมุม
    { "type": "plane", "xTicks": [6,9,12,15,18] },                     # กำหนดขีดเอง

    { "file": "tri.png", "type": "triangle",                           # รูปเรขาคณิต
      "base": 8, "height": 5, "baseLabel": "8 ซม.", "heightLabel": "5 ซม." },
    { "file": "rect.png", "type": "rectangle", "w": 6, "h": 4,
      "wLabel": "6 ซม.", "hLabel": "4 ซม." },

    { "file": "nl.png", "type": "numberline",                          # เส้นจำนวน
      "range": [-4, 4], "step": 1,
      "marks": [ {"x": -2.5, "label": "A"}, {"x": 0.75, "label": "B"} ] },

    { "file": "fn.png", "type": "function",                            # เส้นโค้งจากสมการ
      "xRange": [-4, 4], "yRange": [-2, 10],
      "curves": [ {"expr": "x**2", "label": "y = x²"},
                  {"expr": "2*x + 1", "label": "y = 2x + 1"} ] },

    { "file": "bar.png", "type": "bar",                                # แผนภูมิแท่ง
      "labels": ["จันทร์","อังคาร","พุธ"], "values": [12, 18, 9],
      "xTitle": "วัน", "yTitle": "จำนวน (เล่ม)", "showValues": true },

    { "file": "pie.png", "type": "pie",
      "labels": ["เดินเท้า","รถโรงเรียน"], "values": [25, 75] },

    { "file": "hist.png", "type": "histogram",
      "edges": [40,50,60,70], "freq": [3, 8, 14] },

    { "file": "line.png", "type": "linechart",
      "labels": ["ม.ค.","ก.พ."],
      "series": [ {"values": [120,145], "label": "ร้าน ก"} ] },

    { "file": "sc.png", "type": "scatter",
      "x": [1,2,3], "y": [2,3.5,3], "trendline": true },

    { "file": "picto.png", "type": "pictograph",                       # แผนภูมิรูปภาพ
      "icon": "book", "unit": 20,                                      # ไอคอนหนังสือในตัว
      "rows": [ {"label":"วันจันทร์","value":60}, {"label":"วันอังคาร","value":90} ],
      "legend": "รูปหนังสือ 1 รูป แทน 20 เล่ม" },
    { "file": "picto2.png", "type": "pictograph",
      "iconFile": "icons/apple.png",        # หรือใช้ไฟล์ PNG ของตัวเอง (พาธอิงโฟลเดอร์ผลลัพธ์)
      "unit": 10, "rows": [ {"label":"สวนที่ 1","value":25} ] },

    { "file": "bisect.png", "type": "construction",                    # การสร้างทางเรขาคณิต
      "rays":     [ {"from":[0,0], "angle":0, "length":5},
                    {"from":[0,0], "angle":68, "length":5} ],
      "arcs":     [ {"center":[0,0], "r":2.6, "start":0, "end":68},
                    {"center":[2.6,0], "r":1.7, "start":20, "end":70} ],
      "segments": [ {"from":[0,0], "to":[4.2,2.83], "style":"--"} ],
      "angleMarks":[ {"vertex":[0,0], "start":0, "end":34, "r":1.2, "label":"?"} ],
      "points":   [ {"x":0, "y":0, "label":"O", "pos":"below-left"} ] }
  ]
}

หมายเหตุ
- แกนที่ค่าเป็นจำนวนเต็มล้วน ระบบตั้งขีดเป็นจำนวนเต็มให้เอง (กัน "2.5 เล่ม")
- สีของหลายชุดข้อมูลแจกจากจานสีกลาง โดยข้ามสีที่ระบุมาเอง จึงไม่มีสองชุดสีชนกัน

รันผ่านตัวห่อ: eduone-py <ชื่อไฟล์นี้> <args>  (หา Python 3.12 ให้เองทุก OS)
"""
import argparse
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

SS = 2                      # supersample factor
BG = (255, 255, 255)
GRID = (214, 222, 232)
AXIS = (40, 40, 40)
DOT = (183, 28, 62)
LINE = (23, 74, 150)
TEXT = (30, 30, 30)

FONT_CANDIDATES = [
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts", "THSarabunNew.ttf"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts", "Sarabun-Regular.ttf"),
    r"C:\Windows\Fonts\tahoma.ttf",
]
FONT_BOLD_CANDIDATES = [
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts", "THSarabunNew Bold.ttf"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts", "Sarabun-Bold.ttf"),
    r"C:\Windows\Fonts\tahomabd.ttf",
]


def _font(size, bold=False):
    for p in (FONT_BOLD_CANDIDATES if bold else FONT_CANDIDATES):
        if p and os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _text(d, xy, s, font, fill=TEXT, anchor="la"):
    d.text(xy, s, font=font, fill=fill, anchor=anchor)


def _fmt(v):
    return str(int(v)) if float(v) == int(v) else ("%g" % v)


def _arrow_right(d, x, y, size, fill):
    """หัวลูกศรชี้ขวา ปลายอยู่ที่ (x, y)"""
    d.polygon([(x, y), (x - size, y - size * 0.5), (x - size, y + size * 0.5)], fill=fill)


def _arrow_up(d, x, y, size, fill):
    """หัวลูกศรชี้ขึ้น ปลายอยู่ที่ (x, y) — y ในภาพน้อย = สูง"""
    d.polygon([(x, y), (x - size * 0.5, y + size), (x + size * 0.5, y + size)], fill=fill)


def draw_plane(spec, out_path):
    x0, x1 = spec.get("xRange", [-5, 5])
    y0, y1 = spec.get("yRange", [-5, 5])
    xstep = spec.get("xStep", 1)
    ystep = spec.get("yStep", 1)
    xtitle = spec.get("xTitle", "")
    ytitle = spec.get("yTitle", "")

    # ขนาดภาพ: ให้ 1 ช่องกริดกว้างพอสมควร แต่ไม่ใหญ่เกิน
    cols = (x1 - x0) / float(xstep)
    rows = (y1 - y0) / float(ystep)
    cell = max(40, min(84, int(560 / max(cols, 1))))
    cellY = max(32, min(70, int(430 / max(rows, 1))))

    ml = 104 if ytitle else (76 if (y0 < 0 or abs(y1) >= 100) else 60)
    mr = 54
    mt = 54                                  # เผื่อที่ให้หัวลูกศรและชื่อแกน Y เหนือขีดบนสุด
    mb = 80 if xtitle else 54

    W = int(ml + cols * cell + mr)
    H = int(mt + rows * cellY + mb)
    img = Image.new("RGB", (W * SS, H * SS), BG)
    d = ImageDraw.Draw(img)
    f_tick = _font(21 * SS)
    f_lbl = _font(24 * SS, bold=True)
    f_title = _font(23 * SS)

    def px(vx):
        return (ml + (vx - x0) / float(x1 - x0) * cols * cell) * SS

    def py(vy):
        return (mt + (1 - (vy - y0) / float(y1 - y0)) * rows * cellY) * SS

    # ---- เส้นกริด ----
    n = 0
    while True:
        v = x0 + n * xstep
        if v > x1 + 1e-9:
            break
        d.line([(px(v), py(y0)), (px(v), py(y1))], fill=GRID, width=1 * SS)
        n += 1
    n = 0
    while True:
        v = y0 + n * ystep
        if v > y1 + 1e-9:
            break
        d.line([(px(x0), py(v)), (px(x1), py(v))], fill=GRID, width=1 * SS)
        n += 1

    # ---- ตำแหน่งแกน ----
    ax_y = py(0) if y0 < 0 < y1 else py(y0)      # แกน X
    ax_x = px(0) if x0 < 0 < x1 else px(x0)      # แกน Y

    # ลากแกนเลยขีดสุดท้ายไปเล็กน้อย แล้ววางหัวลูกศรกับชื่อแกนไว้พ้นพื้นที่กราฟ
    head = 26 * SS
    d.line([(px(x0), ax_y), (px(x1) + head, ax_y)], fill=AXIS, width=2 * SS)
    d.line([(ax_x, py(y0)), (ax_x, py(y1) - head)], fill=AXIS, width=2 * SS)
    _arrow_right(d, px(x1) + head + 7 * SS, ax_y, 9 * SS, AXIS)
    _arrow_up(d, ax_x, py(y1) - head - 7 * SS, 9 * SS, AXIS)
    _text(d, (px(x1) + head + 14 * SS, ax_y + 3 * SS), spec.get("xAxisName", "X"), f_lbl, AXIS, "la")
    _text(d, (ax_x + 12 * SS, py(y1) - head - 12 * SS), spec.get("yAxisName", "Y"), f_lbl, AXIS, "la")

    # ---- ขีดและตัวเลขกำกับ ----
    xticks = spec.get("xTicks")
    if xticks is None:
        xticks, n = [], 0
        while True:
            v = x0 + n * xstep
            if v > x1 + 1e-9:
                break
            xticks.append(v); n += 1
    # จุดกำเนิดจริง = ทั้งสองแกนเริ่มที่ 0 หรือแกนตัดกันที่ 0 -> เขียน "O" แทนเลข 0
    true_origin = (x0 <= 0 <= x1) and (y0 <= 0 <= y1)

    for v in xticks:
        if abs(v) < 1e-9 and true_origin:
            continue          # ตำแหน่ง 0 ใช้ตัว O แทน ไม่ต้องมีเลข 0 ซ้ำ
        d.line([(px(v), ax_y - 4 * SS), (px(v), ax_y + 4 * SS)], fill=AXIS, width=2 * SS)
        _text(d, (px(v), ax_y + 9 * SS), _fmt(v), f_tick, TEXT, "ma")

    yticks = spec.get("yTicks")
    if yticks is None:
        yticks, n = [], 0
        while True:
            v = y0 + n * ystep
            if v > y1 + 1e-9:
                break
            yticks.append(v); n += 1
    for v in yticks:
        if abs(v) < 1e-9 and true_origin:
            continue
        d.line([(ax_x - 4 * SS, py(v)), (ax_x + 4 * SS, py(v))], fill=AXIS, width=2 * SS)
        _text(d, (ax_x - 10 * SS, py(v)), _fmt(v), f_tick, TEXT, "rm")

    # เขียน "O" เฉพาะเมื่อเป็นจุดกำเนิดจริง (แกนที่เริ่มที่ค่าอื่น เช่น 6 นาฬิกา ไม่ใช่จุดกำเนิด)
    if true_origin:
        _text(d, (ax_x - 10 * SS, ax_y + 8 * SS), "O", f_tick, TEXT, "ra")

    # ---- ชื่อแกน ----
    if xtitle:
        _text(d, ((px(x0) + px(x1)) / 2, (H - 26) * SS), xtitle, f_title, TEXT, "ma")
    if ytitle:
        band = int(34 * SS)
        t = Image.new("RGB", (int(rows * cellY * SS), band), BG)
        td = ImageDraw.Draw(t)
        _text(td, (t.width / 2, band / 2), ytitle, f_title, TEXT, "mm")
        t = t.rotate(90, expand=True)
        img.paste(t, (int(6 * SS), int(py(y1))))

    # ---- เส้นตรง / เส้นหักมุม ----
    ln = spec.get("line")
    if ln:
        d.line([(px(ln["from"][0]), py(ln["from"][1])), (px(ln["to"][0]), py(ln["to"][1]))],
               fill=LINE, width=3 * SS)
    poly = spec.get("polyline")
    if poly:
        d.line([(px(p[0]), py(p[1])) for p in poly], fill=LINE, width=3 * SS, joint="curve")

    # ---- จุด ----
    r = 6 * SS
    for pt in spec.get("points", []):
        cx, cy = px(pt["x"]), py(pt["y"])
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=DOT)
        if pt.get("label"):
            _text(d, (cx + 11 * SS, cy - 13 * SS), pt["label"], f_lbl, TEXT, "la")

    img = img.resize((W, H), Image.LANCZOS)
    img.save(out_path, "PNG")
    return out_path


def draw_triangle(spec, out_path):
    b, h = float(spec.get("base", 8)), float(spec.get("height", 5))
    unit = 46
    ml, mt, mr, mb = 70, 40, 70, 70
    W, H = int(ml + b * unit + mr), int(mt + h * unit + mb)
    img = Image.new("RGB", (W * SS, H * SS), BG)
    d = ImageDraw.Draw(img)
    f = _font(23 * SS)

    x0, y0 = ml * SS, (mt + h * unit) * SS
    x1 = (ml + b * unit) * SS
    apex = ((ml + b * unit * float(spec.get("apex", 0.35))) * SS, mt * SS)
    d.polygon([(x0, y0), (x1, y0), apex], outline=AXIS, fill=(232, 240, 252))
    d.line([(x0, y0), (x1, y0), apex, (x0, y0)], fill=AXIS, width=3 * SS)
    # เส้นความสูง (เส้นประ) + มุมฉาก
    fx = apex[0]
    for yy in range(int(mt * SS), int(y0), 12 * SS):
        d.line([(fx, yy), (fx, min(yy + 6 * SS, y0))], fill=AXIS, width=2 * SS)
    s = 10 * SS
    d.line([(fx, y0 - s), (fx + s, y0 - s), (fx + s, y0)], fill=AXIS, width=2 * SS)
    if spec.get("baseLabel"):
        _text(d, ((x0 + x1) / 2, y0 + 12 * SS), spec["baseLabel"], f, TEXT, "ma")
    if spec.get("heightLabel"):
        _text(d, (fx - 12 * SS, (mt * SS + y0) / 2), spec["heightLabel"], f, TEXT, "rm")
    img = img.resize((W, H), Image.LANCZOS)
    img.save(out_path, "PNG")
    return out_path


def draw_rectangle(spec, out_path):
    w, h = float(spec.get("w", 6)), float(spec.get("h", 4))
    unit = 46
    ml, mt, mr, mb = 80, 40, 60, 70
    W, H = int(ml + w * unit + mr), int(mt + h * unit + mb)
    img = Image.new("RGB", (W * SS, H * SS), BG)
    d = ImageDraw.Draw(img)
    f = _font(23 * SS)
    x0, y0 = ml * SS, mt * SS
    x1, y1 = (ml + w * unit) * SS, (mt + h * unit) * SS
    d.rectangle([x0, y0, x1, y1], outline=AXIS, fill=(232, 240, 252), width=3 * SS)
    s = 10 * SS
    d.line([(x0, y1 - s), (x0 + s, y1 - s), (x0 + s, y1)], fill=AXIS, width=2 * SS)
    if spec.get("wLabel"):
        _text(d, ((x0 + x1) / 2, y1 + 12 * SS), spec["wLabel"], f, TEXT, "ma")
    if spec.get("hLabel"):
        _text(d, (x0 - 12 * SS, (y0 + y1) / 2), spec["hLabel"], f, TEXT, "rm")
    img = img.resize((W, H), Image.LANCZOS)
    img.save(out_path, "PNG")
    return out_path


# ---------------------------------------------------------------- matplotlib
# ใช้กับรูปที่ Pillow ทำได้ไม่ดี: เส้นโค้งต่อเนื่อง และแผนภูมิสถิติ
_MPL_READY = None


def _mpl():
    """เตรียม matplotlib + ฟอนต์ไทย (เรียกครั้งแรกครั้งเดียว) คืน (plt, ok)"""
    global _MPL_READY
    if _MPL_READY is not None:
        return _MPL_READY
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib import font_manager as fm
        name = None
        for p in FONT_CANDIDATES:
            if p and os.path.exists(p):
                fm.fontManager.addfont(p)
                name = fm.FontProperties(fname=p).get_name()
                break
        if name:
            plt.rcParams["font.family"] = name
        plt.rcParams["axes.unicode_minus"] = False      # ให้เครื่องหมายลบใช้ฟอนต์เดียวกัน
        plt.rcParams["axes.grid"] = True
        plt.rcParams["grid.color"] = "#d6dee8"
        plt.rcParams["grid.linewidth"] = 0.8
        _MPL_READY = (plt, True)
    except Exception as exc:
        print("WARN: ใช้ matplotlib ไม่ได้ (%s)" % exc, file=sys.stderr)
        _MPL_READY = (None, False)
    return _MPL_READY


def _hex(rgb):
    return "#%02x%02x%02x" % rgb


def math_radians_mid(wedge):
    import math
    return math.radians((wedge.theta2 + wedge.theta1) / 2.0)


def math_cos(a):
    import math
    return math.cos(a)


def math_sin(a):
    import math
    return math.sin(a)


# จานสีสำหรับแผนภูมิ — โทนสุภาพ พิมพ์ขาวดำแล้วยังแยกออก เข้าชุดกับสีในเอกสาร
PALETTE = ["#b71c3e", "#174a96", "#2e7d5b", "#d98b28", "#6a4c93", "#4a7ba7", "#8d6e3a"]


def _assign_colors(items):
    """แจกสีให้แต่ละชุดข้อมูล โดยข้ามสีที่ผู้ใช้ระบุมาเอง เพื่อไม่ให้สองชุดสีชนกัน"""
    taken = {(it.get("color") or "").lower() for it in items if it.get("color")}
    pool = [c for c in PALETTE if c.lower() not in taken]
    out, k = [], 0
    for it in items:
        if it.get("color"):
            out.append(it["color"])
        else:
            out.append(pool[k % len(pool)] if pool else PALETTE[k % len(PALETTE)])
            k += 1
    return out


def _int_axis(ax, values, axis="y"):
    """ถ้าข้อมูลเป็นจำนวนเต็มล้วน ให้ขีดแกนเป็นจำนวนเต็ม (กัน 2.5 เล่ม / 7.5 คน)"""
    try:
        from matplotlib.ticker import MaxNLocator
    except Exception:
        return
    flat = []
    for v in values:
        flat.extend(v if isinstance(v, (list, tuple)) else [v])
    if flat and all(float(v) == int(v) for v in flat):
        getattr(ax, "%saxis" % axis).set_major_locator(MaxNLocator(integer=True))


def _finish(fig, ax, spec, out_path):
    if spec.get("title"):
        ax.set_title(spec["title"])
    if spec.get("xTitle"):
        ax.set_xlabel(spec["xTitle"])
    if spec.get("yTitle"):
        ax.set_ylabel(spec["yTitle"])
    fig.tight_layout()
    fig.savefig(out_path, dpi=spec.get("dpi", 150), facecolor="white")
    return out_path


def _figsize(spec, default=(5.2, 3.4)):
    return tuple(spec.get("figSize", default))


def draw_function(spec, out_path):
    """กราฟฟังก์ชันต่อเนื่อง เช่น y = x^2 - 2x  (ระบุด้วย expr ของ x)"""
    plt, ok = _mpl()
    if not ok:
        raise RuntimeError("ต้องมี matplotlib")
    import numpy as np
    x0, x1 = spec.get("xRange", [-5, 5])
    xs = np.linspace(x0, x1, spec.get("samples", 400))
    fig, ax = plt.subplots(figsize=_figsize(spec), dpi=spec.get("dpi", 150))
    curves = spec.get("curves", [{"expr": spec.get("expr", "x**2")}])
    for cur, col in zip(curves, _assign_colors(curves)):
        ys = eval(cur["expr"], {"__builtins__": {}, "np": np, "x": xs,
                                "sin": np.sin, "cos": np.cos, "tan": np.tan,
                                "sqrt": np.sqrt, "abs": np.abs, "pi": np.pi})
        ax.plot(xs, ys, linewidth=2.2, color=col, label=cur.get("label"))
    if spec.get("yRange"):
        ax.set_ylim(*spec["yRange"])
    ax.set_xlim(x0, x1)
    ax.axhline(0, color=_hex(AXIS), linewidth=1.4)
    ax.axvline(0, color=_hex(AXIS), linewidth=1.4)
    for pt in spec.get("points", []):
        ax.plot(pt["x"], pt["y"], "o", color=_hex(DOT), markersize=8)
        if pt.get("label"):
            ax.annotate(pt["label"], (pt["x"], pt["y"]),
                        textcoords="offset points", xytext=(8, 8))
    if any(c.get("label") for c in curves):
        ax.legend(loc=spec.get("legendLoc", "best"))
    return _finish(fig, ax, spec, out_path)


def draw_bar(spec, out_path):
    """แผนภูมิแท่ง — ใช้กับสถิติ/ความถี่"""
    plt, ok = _mpl()
    if not ok:
        raise RuntimeError("ต้องมี matplotlib")
    import numpy as np
    fig, ax = plt.subplots(figsize=_figsize(spec), dpi=spec.get("dpi", 150))
    labels = spec["labels"]
    # รองรับทั้งชุดเดียว (values) และหลายชุดวางคู่กัน (series) เช่น ชาย/หญิง
    series = spec.get("series") or [{"values": spec["values"]}]
    colors = _assign_colors(series)
    idx = np.arange(len(labels))
    total_w = spec.get("width", 0.72)
    bw = total_w / len(series)
    for k, (s, col) in enumerate(zip(series, colors)):
        off = (k - (len(series) - 1) / 2.0) * bw
        ax.bar(idx + off, s["values"], width=bw * 0.92, color=col, zorder=3,
               label=s.get("label"), hatch=s.get("hatch"),
               edgecolor="white" if s.get("hatch") else "none",
               linewidth=1.0 if s.get("hatch") else 0)
        if spec.get("showValues"):
            for i, v in enumerate(s["values"]):
                ax.annotate(_fmt(v), (i + off, v), ha="center", va="bottom",
                            textcoords="offset points", xytext=(0, 3))
    ax.set_xticks(idx)
    ax.set_xticklabels(labels)
    ax.set_axisbelow(True)
    ax.grid(axis="x", visible=False)
    _int_axis(ax, [s["values"] for s in series])
    if any(s.get("label") for s in series):
        ax.legend(loc=spec.get("legendLoc", "best"))
    if spec.get("yRange"):
        ax.set_ylim(*spec["yRange"])
    return _finish(fig, ax, spec, out_path)


def draw_pie(spec, out_path):
    """แผนภูมิวงกลม — ใช้กับร้อยละ/สัดส่วน"""
    plt, ok = _mpl()
    if not ok:
        raise RuntimeError("ต้องมี matplotlib")
    fig, ax = plt.subplots(figsize=_figsize(spec, (4.4, 4.0)), dpi=spec.get("dpi", 150))
    colors = spec.get("colors") or PALETTE[:len(spec["values"])]
    values, labels = spec["values"], spec.get("labels") or []

    if spec.get("leaderLines"):
        # ป้ายอยู่นอกวง มีเส้นชี้ — อ่านง่ายเมื่อชื่อยาวหรือชิ้นเล็ก
        import numpy as np
        wedges, _ = ax.pie(values, startangle=spec.get("startAngle", 90),
                           colors=colors, counterclock=False,
                           wedgeprops={"edgecolor": "white", "linewidth": 1.6})
        total = float(sum(values))
        for w, lab, v in zip(wedges, labels, values):
            ang = math_radians_mid(w)
            x, y = math_cos(ang), math_sin(ang)
            ha = "left" if x >= 0 else "right"
            ax.annotate("%s\n%s%%" % (lab, _fmt(round(v / total * 100))),
                        xy=(x * 0.98, y * 0.98), xytext=(x * 1.32, y * 1.22),
                        ha=ha, va="center",
                        arrowprops=dict(arrowstyle="-", color="#8a8a8a",
                                        connectionstyle="angle,angleA=0,angleB=%d" % (90 if y >= 0 else -90)))
    else:
        ax.pie(values, labels=labels or None,
               autopct=spec.get("autopct", "%1.0f%%"),
               startangle=spec.get("startAngle", 90),
               colors=colors, counterclock=False,
               textprops={"color": "#1e1e1e"},
               wedgeprops={"edgecolor": "white", "linewidth": 1.6})
    ax.set_aspect("equal")
    ax.grid(False)
    if spec.get("title"):
        ax.set_title(spec["title"])
    fig.tight_layout()
    fig.savefig(out_path, dpi=spec.get("dpi", 150), facecolor="white")
    return out_path


def draw_linechart(spec, out_path):
    """กราฟเส้นตามหมวดหมู่ (เช่น ยอดขายรายเดือน) — ต่างจาก plane ที่เป็นระนาบพิกัด"""
    plt, ok = _mpl()
    if not ok:
        raise RuntimeError("ต้องมี matplotlib")
    fig, ax = plt.subplots(figsize=_figsize(spec), dpi=spec.get("dpi", 150))
    series = spec.get("series", [{"values": spec.get("values", [])}])
    colors = _assign_colors(series)
    for s, col in zip(series, colors):
        ax.plot(spec["labels"], s["values"], marker="o", linewidth=2.2,
                markersize=7, color=col, label=s.get("label"))
    if any(s.get("label") for s in series):
        ax.legend()
    if spec.get("yRange"):
        ax.set_ylim(*spec["yRange"])
    _int_axis(ax, [s["values"] for s in series])
    return _finish(fig, ax, spec, out_path)


def draw_histogram(spec, out_path):
    """ฮิสโทแกรมจากอันตรภาคชั้น (ระบุ edges + freq) หรือจากข้อมูลดิบ (data + bins)"""
    plt, ok = _mpl()
    if not ok:
        raise RuntimeError("ต้องมี matplotlib")
    fig, ax = plt.subplots(figsize=_figsize(spec), dpi=spec.get("dpi", 150))
    if spec.get("edges") and spec.get("freq"):
        edges, freq = spec["edges"], spec["freq"]
        widths = [edges[i + 1] - edges[i] for i in range(len(freq))]
        ax.bar(edges[:-1], freq, width=widths, align="edge",
               color=spec.get("color", _hex(DOT)), edgecolor="white", zorder=3)
        ax.set_xticks(edges)
    else:
        ax.hist(spec["data"], bins=spec.get("bins", 8),
                color=spec.get("color", _hex(DOT)), edgecolor="white", zorder=3)
    ax.set_axisbelow(True)
    ax.grid(axis="x", visible=False)
    if spec.get("freq"):
        _int_axis(ax, spec["freq"])
    return _finish(fig, ax, spec, out_path)


def draw_scatter(spec, out_path):
    """แผนภาพการกระจาย (+ เส้นแนวโน้มถ้าสั่ง)"""
    plt, ok = _mpl()
    if not ok:
        raise RuntimeError("ต้องมี matplotlib")
    import numpy as np
    fig, ax = plt.subplots(figsize=_figsize(spec), dpi=spec.get("dpi", 150))
    xs, ys = spec["x"], spec["y"]
    ax.scatter(xs, ys, s=spec.get("size", 60), color=_hex(DOT), zorder=3)
    if spec.get("trendline"):
        m, b = np.polyfit(xs, ys, 1)
        gx = np.array([min(xs), max(xs)])
        ax.plot(gx, m * gx + b, linewidth=2, color=_hex(LINE))
    ax.set_axisbelow(True)
    return _finish(fig, ax, spec, out_path)


def draw_numberline(spec, out_path):
    """เส้นจำนวน — จำนวนเต็ม ทศนิยม เศษส่วน (ทำเครื่องหมายจุด/ช่วงได้)"""
    plt, ok = _mpl()
    if not ok:
        raise RuntimeError("ต้องมี matplotlib")
    import numpy as np
    x0, x1 = spec.get("range", [-5, 5])
    step = spec.get("step", 1)
    fig, ax = plt.subplots(figsize=_figsize(spec, (7.2, 1.5)), dpi=spec.get("dpi", 150))
    ax.axhline(0, color=_hex(AXIS), linewidth=1.8)
    ticks = np.arange(x0, x1 + step / 2.0, step)
    for t in ticks:
        ax.plot([t, t], [-0.09, 0.09], color=_hex(AXIS), linewidth=1.6)
    labels = spec.get("tickLabels")
    for i, t in enumerate(ticks):
        lab = labels[i] if labels and i < len(labels) else _fmt(t)
        if lab != "":
            ax.annotate(lab, (t, -0.16), ha="center", va="top")
    for m in spec.get("marks", []):
        ax.plot(m["x"], 0, "o", color=_hex(DOT), markersize=11, zorder=4)
        if m.get("label"):
            ax.annotate(m["label"], (m["x"], 0.16), ha="center", va="bottom",
                        color=_hex(DOT))
    ax.annotate("", xy=(x1 + step * 0.6, 0), xytext=(x1, 0),
                arrowprops=dict(arrowstyle="-|>", color=_hex(AXIS), lw=1.8))
    ax.annotate("", xy=(x0 - step * 0.6, 0), xytext=(x0, 0),
                arrowprops=dict(arrowstyle="-|>", color=_hex(AXIS), lw=1.8))
    ax.set_xlim(x0 - step * 0.9, x1 + step * 0.9)
    ax.set_ylim(-0.55, 0.5)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(out_path, dpi=spec.get("dpi", 150), facecolor="white")
    return out_path


def draw_construction(spec, out_path):
    """รูปการสร้างทางเรขาคณิต — รังสี ส่วนของเส้นตรง ส่วนโค้งวงเวียน เส้นประ มุม

    ใช้กับหน่วย "การสร้างทางเรขาคณิต" (แบ่งครึ่งมุม · สร้างมุม 60 องศา ·
    สร้างส่วนของเส้นตรงเท่าที่กำหนด · เส้นตั้งฉาก ฯลฯ)
    พิกัดเป็นระบบของผู้เขียนเอง (หน่วยอิสระ) ไม่มีการแสดงแกน
    """
    plt, ok = _mpl()
    if not ok:
        raise RuntimeError("ต้องมี matplotlib")
    import math
    from matplotlib.patches import Arc

    col_line = spec.get("lineColor", _hex(LINE))
    col_arc = spec.get("arcColor", _hex(DOT))
    fig, ax = plt.subplots(figsize=_figsize(spec, (4.6, 3.2)), dpi=spec.get("dpi", 170))
    ax.set_aspect("equal")
    ax.axis("off")
    ax.grid(False)

    def _place(ax, x, y, text, pos, color="#1e1e1e", size=None):
        dx, dy, ha, va = {
            "above": (0, 9, "center", "bottom"), "below": (0, -9, "center", "top"),
            "left": (-9, 0, "right", "center"), "right": (9, 0, "left", "center"),
            "above-left": (-8, 8, "right", "bottom"), "above-right": (8, 8, "left", "bottom"),
            "below-left": (-8, -8, "right", "top"), "below-right": (8, -8, "left", "top"),
        }.get(pos, (8, 8, "left", "bottom"))
        ax.annotate(text, (x, y), textcoords="offset points", xytext=(dx, dy),
                    ha=ha, va=va, color=color, fontsize=size)

    # ---- รังสี (มีหัวลูกศร) ----
    # ต้องวาดลำตัวด้วย ax.plot ไม่ใช่ annotate อย่างเดียว เพราะ annotate ไม่นับเข้า
    # ขอบเขตข้อมูล ทำให้รังสีที่ยาวเกินส่วนโค้งถูกตัดหายไปตอน autoscale
    for r in spec.get("rays", []):
        x, y = r["from"]
        a = math.radians(r.get("angle", 0))
        L = r.get("length", 5)
        x2, y2 = x + L * math.cos(a), y + L * math.sin(a)
        col = r.get("color", col_line)
        lw = r.get("width", 2.2)
        ax.plot([x, x2], [y, y2], color=col, lw=lw,
                linestyle=r.get("style", "-"), solid_capstyle="round", zorder=2)
        if r.get("arrow", True):
            back = 0.06 * L
            ax.annotate("", xy=(x2, y2),
                        xytext=(x2 - back * math.cos(a), y2 - back * math.sin(a)),
                        arrowprops=dict(arrowstyle="-|>", color=col, lw=lw))
    # ---- ส่วนของเส้นตรง ----
    for s in spec.get("segments", []):
        (x1, y1), (x2, y2) = s["from"], s["to"]
        ax.plot([x1, x2], [y1, y2], color=s.get("color", col_line),
                lw=s.get("width", 2.2), linestyle=s.get("style", "-"),
                solid_capstyle="round", zorder=2)
        if s.get("endpoints"):
            ax.plot([x1, x2], [y1, y2], "o", color=s.get("color", col_line),
                    markersize=6, zorder=3)
        if s.get("label"):
            ax.annotate(s["label"], ((x1 + x2) / 2.0, (y1 + y2) / 2.0),
                        textcoords="offset points", xytext=(0, 8),
                        ha="center", color=s.get("labelColor", "#1e1e1e"))
    # ---- ส่วนโค้งจากวงเวียน ----
    for a in spec.get("arcs", []):
        cx, cy = a["center"]
        r = a["r"]
        ax.add_patch(Arc((cx, cy), 2 * r, 2 * r,
                         theta1=a.get("start", 0), theta2=a.get("end", 360),
                         edgecolor=a.get("color", col_arc),
                         lw=a.get("width", 1.7), zorder=2))
    # ---- เครื่องหมายมุม (ส่วนโค้งเล็ก + ป้าย) ----
    for m in spec.get("angleMarks", []):
        cx, cy = m["vertex"]
        r = m.get("r", 1.0)
        ax.add_patch(Arc((cx, cy), 2 * r, 2 * r,
                         theta1=m["start"], theta2=m["end"],
                         edgecolor=m.get("color", "#5a5a5a"), lw=1.3, zorder=2))
        if m.get("label"):
            mid = math.radians((m["start"] + m["end"]) / 2.0)
            ax.annotate(m["label"], (cx + r * 1.28 * math.cos(mid),
                                     cy + r * 1.28 * math.sin(mid)),
                        ha="center", va="center", color=m.get("labelColor", "#5a5a5a"))
    # ---- จุดและป้ายกำกับ ----
    for p in spec.get("points", []):
        if p.get("dot", True):
            ax.plot(p["x"], p["y"], "o", color=p.get("color", col_line),
                    markersize=p.get("size", 7), zorder=4)
        if p.get("label"):
            _place(ax, p["x"], p["y"], p["label"], p.get("pos", "above-right"),
                   p.get("labelColor", "#1e1e1e"))
    # ---- ข้อความอิสระ ----
    for t in spec.get("texts", []):
        ax.annotate(t["text"], (t["x"], t["y"]), ha=t.get("ha", "center"),
                    va=t.get("va", "center"), color=t.get("color", "#1e1e1e"))

    if spec.get("xRange"):
        ax.set_xlim(*spec["xRange"])
    if spec.get("yRange"):
        ax.set_ylim(*spec["yRange"])
    ax.margins(0.12)
    if spec.get("title"):
        ax.set_title(spec["title"])
    fig.tight_layout()
    fig.savefig(out_path, dpi=spec.get("dpi", 170), facecolor="white")
    return out_path


# สีของไอคอนหนังสือ (ดีไซน์แบน — ปกแดง ริบบิ้นเหลือง ป้ายขาว สันหนังสือเข้ม)
BOOK_DARK = "#C0303D"
BOOK_RED = "#D8434F"
BOOK_PAPER = "#DCE3E8"
BOOK_RIBBON = "#F5D74E"
BOOK_RULE = "#6B5F63"


def _rrect(ax, x, y, w, h, r, fc, ec="none", lw=0, z=3):
    from matplotlib.patches import FancyBboxPatch
    ax.add_patch(FancyBboxPatch((x + r, y + r), max(w - 2 * r, 1e-6), max(h - 2 * r, 1e-6),
                                boxstyle="round,pad=%f,rounding_size=%f" % (r, r),
                                facecolor=fc, edgecolor=ec, linewidth=lw, zorder=z,
                                mutation_aspect=1))


def _icon_book(ax, x, y, w, h, frac=1.0):
    """ไอคอนหนังสือแบบแบน — วาดเป็นสัดส่วนของกล่อง (x, y, w, h)

    frac < 1 = แสดงเพียงบางส่วนของรูปตามแนวนอน (ครึ่งรูป = 0.5)
    ใช้ clip box ตัด แทนการย่อรูป เพื่อให้สัดส่วนหนังสือไม่บิดเบี้ยว
    """
    from matplotlib.transforms import Bbox, TransformedBbox
    clip = TransformedBbox(Bbox.from_bounds(x, y, w * frac, h), ax.transData)
    parts = []

    def keep(p):
        parts.append(p)
        return p

    # สันหนังสือ/ขอบเข้ม
    _rrect(ax, x + 0.02 * w, y, 0.96 * w, h, 0.07 * w, BOOK_DARK, z=3)
    parts.append(ax.patches[-1])
    # ขอบกระดาษด้านล่าง
    _rrect(ax, x + 0.06 * w, y + 0.02 * h, 0.92 * w, 0.11 * h, 0.045 * w, BOOK_PAPER, z=4)
    parts.append(ax.patches[-1])
    # ปกหน้า
    _rrect(ax, x + 0.11 * w, y + 0.14 * h, 0.87 * w, 0.86 * h, 0.06 * w, BOOK_RED, z=5)
    parts.append(ax.patches[-1])
    # ริบบิ้นคั่นหนังสือ
    from matplotlib.patches import Polygon
    rb = [(0.30, 1.00), (0.30, 0.78), (0.375, 0.855), (0.45, 0.78), (0.45, 1.00)]
    parts.append(ax.add_patch(Polygon([(x + a * w, y + b * h) for a, b in rb],
                                      closed=True, facecolor=BOOK_RIBBON,
                                      edgecolor="none", zorder=6)))
    # ป้ายชื่อบนปก
    _rrect(ax, x + 0.26 * w, y + 0.42 * h, 0.50 * w, 0.29 * h, 0.055 * w,
           BOOK_PAPER, ec=BOOK_DARK, lw=2.4, z=7)
    parts.append(ax.patches[-1])
    for fy in (0.508, 0.635):
        parts.append(ax.plot([x + 0.345 * w, x + 0.675 * w], [y + fy * h, y + fy * h],
                             color=BOOK_RULE, lw=2.0, solid_capstyle="round", zorder=8)[0])
    if frac < 1.0:
        for p in parts:
            p.set_clip_box(clip)
            p.set_clip_on(True)


def _icon_image(ax, x, y, w, h, img, frac=1.0):
    """วางไฟล์รูปเป็นไอคอน 1 ตัว (ตัดตามแนวนอนเมื่อ frac < 1)"""
    if frac <= 0:
        return
    cols = max(1, int(round(img.shape[1] * frac)))
    ax.imshow(img[:, :cols], extent=(x, x + w * frac, y, y + h),
              zorder=3, interpolation="antialiased", aspect="auto")


def _icon(ax, x, y, w, h, kind, frac=1.0, color="#2f6fb5", img=None):
    """วาดไอคอน 1 ตัวสำหรับแผนภูมิรูปภาพ; frac<1 = วาดแค่บางส่วน (ครึ่งรูป)"""
    from matplotlib.patches import Rectangle
    if frac <= 0:
        return
    if img is not None:
        return _icon_image(ax, x, y, w, h, img, frac)
    if kind == "book":
        return _icon_book(ax, x, y, w, h, frac)
    ax.add_patch(Rectangle((x, y), w * frac, h, facecolor=color,
                           edgecolor="none", zorder=3))


def draw_pictograph(spec, out_path):
    """แผนภูมิรูปภาพ — 1 รูปแทนค่าที่กำหนด รองรับครึ่งรูป/เศษของรูป"""
    plt, ok = _mpl()
    if not ok:
        raise RuntimeError("ต้องมี matplotlib")
    unit = float(spec.get("unit", 1))
    rows = spec["rows"]
    icon = spec.get("icon", "book")
    color = spec.get("color", "#2f6fb5")
    iw, ih, gap = 0.70, 0.78, 0.26
    maxn = max(r["value"] / unit for r in rows)

    img = None
    if spec.get("iconFile"):
        p = spec["iconFile"]
        if not os.path.isabs(p):
            p = os.path.join(os.path.dirname(os.path.abspath(out_path)), p)
        img = plt.imread(p)

    fig, ax = plt.subplots(
        figsize=_figsize(spec, (max(5.0, 2.2 + maxn * (iw + gap)), 0.66 * len(rows) + 1.4)),
        dpi=spec.get("dpi", 160))
    ax.axis("off")
    ax.grid(False)
    ax.set_aspect("equal")          # ไม่งั้นสัดส่วนไอคอนหนังสือจะบิดเบี้ยว

    for i, r in enumerate(rows):
        y = (len(rows) - 1 - i) * 1.0
        ax.annotate(r["label"], (-0.24, y + ih / 2.0), ha="right", va="center")
        n = r["value"] / unit
        full, frac = int(n), n - int(n)
        for k in range(full):
            _icon(ax, k * (iw + gap), y, iw, ih, icon, 1.0, color, img)
        if frac > 1e-9:
            _icon(ax, full * (iw + gap), y, iw, ih, icon, frac, color, img)
            ax.add_patch(plt.Rectangle((full * (iw + gap), y), iw, ih, fill=False,
                                       edgecolor="#b8b8b8", lw=0.9,
                                       linestyle=(0, (3, 2)), zorder=9))
    ax.set_xlim(-0.30, maxn * (iw + gap) + 0.35)
    ax.set_ylim(-1.15, len(rows) * 1.0)
    if spec.get("title"):
        ax.set_title(spec["title"])
    legend = spec.get("legend")
    if legend:
        lw_, lh_ = iw * 0.62, ih * 0.62
        _icon(ax, 0, -1.02, lw_, lh_, icon, 1.0, color, img)
        ax.annotate(legend, (lw_ + 0.18, -1.02 + lh_ / 2.0), va="center")
    # bbox_inches="tight" เพื่อไม่ให้ป้ายชื่อแถวที่ยื่นออกนอกแกนถูกตัด
    fig.savefig(out_path, dpi=spec.get("dpi", 160), facecolor="white", bbox_inches="tight")
    return out_path


DRAWERS = {
    # Pillow — สไตล์หนังสือเรียน (แกนมีหัวลูกศร, จุดกำเนิด O, ชื่อแกนไทย)
    "plane": draw_plane, "grid": draw_plane,
    "triangle": draw_triangle, "rectangle": draw_rectangle,
    # matplotlib — เส้นโค้งต่อเนื่อง + แผนภูมิสถิติ
    "function": draw_function, "bar": draw_bar, "pie": draw_pie,
    "linechart": draw_linechart, "histogram": draw_histogram,
    "scatter": draw_scatter, "numberline": draw_numberline,
    "pictograph": draw_pictograph, "construction": draw_construction,
}

# แผนภาพวิทยาศาสตร์อยู่คนละไฟล์ (science_diagrams.py) เพื่อไม่ให้ไฟล์นี้ยาวเกินไป
try:
    from science_diagrams import SCIENCE_DRAWERS
    DRAWERS.update(SCIENCE_DRAWERS)
except ImportError:                                   # noqa: BLE001
    pass

# รูปสองมิติ/สามมิติ (กองลูกบาศก์ · ภาพจากการมอง · หน้าตัด) อยู่ที่ solid_views.py
try:
    from solid_views import SOLID_DRAWERS
    DRAWERS.update(SOLID_DRAWERS)
except ImportError:                                   # noqa: BLE001
    pass

# แผนภาพพืชดอก (ต้นพืช · ดอกผ่าซีก · ท่อลำเลียง · สังเคราะห์ด้วยแสง) อยู่ที่ plant_diagrams.py
try:
    from plant_diagrams import PLANT_DRAWERS
    DRAWERS.update(PLANT_DRAWERS)
except ImportError:                                   # noqa: BLE001
    pass


def main():
    ap = argparse.ArgumentParser(description="วาดรูปคณิตศาสตร์เป็น PNG จากไฟล์ spec")
    ap.add_argument("spec_json")
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    with open(args.spec_json, "r", encoding="utf-8-sig") as f:
        spec = json.load(f)

    spec_dir = os.path.dirname(os.path.abspath(args.spec_json))
    if args.out_dir:
        # --out-dir มาจากบรรทัดคำสั่ง -> อิงโฟลเดอร์ปัจจุบัน (เจตนาของผู้สั่ง)
        out_dir = os.path.abspath(args.out_dir)
    else:
        # outDir ในไฟล์ spec -> อิงตำแหน่งของไฟล์ spec (ให้วางคู่กับ {BASE}_ex.json ได้)
        out_dir = spec.get("outDir") or spec_dir
        if not os.path.isabs(out_dir):
            out_dir = os.path.join(spec_dir, out_dir)
    os.makedirs(out_dir, exist_ok=True)

    made, failed = [], []
    for item in spec.get("images", []):
        kind = item.get("type", "plane")
        drawer = DRAWERS.get(kind)
        name = item.get("file")
        if not name:
            failed.append("(ไม่มีคีย์ file)"); continue
        if drawer is None:
            failed.append("%s: ไม่รู้จัก type '%s'" % (name, kind)); continue
        try:
            drawer(item, os.path.join(out_dir, name))
            made.append(name)
        except Exception as exc:
            failed.append("%s: %s" % (name, exc))

    for n in made:
        print("  วาดแล้ว %s" % n)
    for n in failed:
        print("  FAIL %s" % n, file=sys.stderr)
    print("สร้างรูป %d ไฟล์ -> %s" % (len(made), out_dir))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
