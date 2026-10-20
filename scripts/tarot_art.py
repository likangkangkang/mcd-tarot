"""麦麦塔罗牌 · 牌面图形元件库（纯 SVG，无第三方依赖）。

设计原则
--------
1. **真的像塔罗牌**：深靛夜空、金线、星点、月相、罗马数字、双线框、四角鸢尾。
2. **汉堡是主角，不是贴图**：`burger_idol()` 把一份汉堡画成「披着生菜披风、
   头顶光环、张臂托着法器」的圣像——有手臂、有底座、有仪轨感，
   而不是一张商品照贴进画框。
3. **小阿卡纳用正宗塔罗语法**：权杖=薯条、圣杯=可乐、宝剑=餐刀、星币=汉堡圆章，
   按张数排布符号，和韦特牌的小阿卡纳构图同源。
4. 所有函数返回 SVG 片段，坐标以 (cx, cy) 为中心，方便组合、缩放与复用。

只画形状不写文案，文案排版交给 tarot_card.py。
"""

from __future__ import annotations

import math
import random
from typing import Optional

# --- 调色板：深靛夜空 + 旧金 + 象牙，塔罗经典三色 ---------------------------
NIGHT = "#0b0e2a"
NIGHT_DEEP = "#04050f"
NIGHT_SOFT = "#141a3d"
GOLD = "#e8c46a"
GOLD_DEEP = "#a97c2c"
CREAM = "#f4e8cf"
RED = "#c0392b"
TEAL = "#3f8b93"
PLUM = "#5a2f63"


def esc(s: object) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _diamond(x: float, y: float, r: float = 5, color: str = GOLD, op: float = 0.8) -> str:
    """菱形分隔符，塔罗牌里常用的节拍点。"""
    return (f'<path d="M{x} {y - r} L{x + r} {y} L{x} {y + r} L{x - r} {y} Z" '
            f'fill="{color}" opacity="{op}"/>')


# ---------------------------------------------------------------------------
# 天空与背景
# ---------------------------------------------------------------------------
def stars(cx: float, cy: float, w: float, h: float, n: int = 46, seed: int = 0) -> str:
    """星点：小的用点，大的用四芒星，避免整片一样大小。"""
    rng = random.Random(seed * 7919 + 13)
    out = []
    for _ in range(n):
        x = cx + rng.uniform(-w / 2, w / 2)
        y = cy + rng.uniform(-h / 2, h / 2)
        r = rng.choice([0.9, 1.2, 1.5, 2.0, 2.6])
        op = round(rng.uniform(0.25, 0.9), 2)
        if r > 2.2:
            out.append(
                f'<path d="M{x} {y - 5} L{x + 1.1} {y - 1.1} L{x + 5} {y} L{x + 1.1} {y + 1.1} '
                f'L{x} {y + 5} L{x - 1.1} {y + 1.1} L{x - 5} {y} L{x - 1.1} {y - 1.1} Z" '
                f'fill="{CREAM}" opacity="{op}"/>')
        else:
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{CREAM}" opacity="{op}"/>')
    return "".join(out)


def moon(cx: float, cy: float, s: float = 1.0, color: str = GOLD) -> str:
    """满月 + 月晕 + 环形山，塔罗牌天空里的常客。"""
    r = 30 * s
    craters = "".join(
        f'<circle cx="{cx + dx * r}" cy="{cy + dy * r}" r="{cr * r}" fill="{NIGHT_DEEP}" '
        f'opacity="0.16"/>'
        for dx, dy, cr in ((-0.34, -0.22, 0.13), (0.28, 0.1, 0.16), (-0.06, 0.38, 0.1),
                           (0.12, -0.42, 0.08)))
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r * 2.2}" fill="{color}" opacity="0.07"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r * 1.5}" fill="{color}" opacity="0.09"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}" opacity="0.9"/>'
        f'{craters}'
    )


def sun(cx: float, cy: float, s: float = 1.0, color: str = GOLD) -> str:
    """带交替长短光芒的太阳。"""
    r = 26 * s
    rays = []
    for i in range(16):
        a = i * math.pi / 8
        long = i % 2 == 0
        r1, r2 = r * 1.35, r * (2.05 if long else 1.72)
        rays.append(
            f'<line x1="{cx + math.cos(a) * r1:.1f}" y1="{cy + math.sin(a) * r1:.1f}" '
            f'x2="{cx + math.cos(a) * r2:.1f}" y2="{cy + math.sin(a) * r2:.1f}" '
            f'stroke="{color}" stroke-width="{2.4 if long else 1.6}" '
            f'stroke-linecap="round" opacity="{0.85 if long else 0.55}"/>')
    return (f'<circle cx="{cx}" cy="{cy}" r="{r * 1.7}" fill="{color}" opacity="0.10"/>'
            + "".join(rays)
            + f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}" opacity="0.92"/>')


def arches(cx: float, base_y: float, w: float = 92, color: str = GOLD, op: float = 0.95) -> str:
    """金拱门：麦当劳的双弧，也是牌面上的「麦门」印记。"""
    h = w * 0.62
    left = cx - w / 2
    return (
        f'<path d="M{left} {base_y} C{left} {base_y - h} {cx - w * 0.17} {base_y - h * 1.25} '
        f'{cx} {base_y - h * 0.34} C{cx + w * 0.17} {base_y - h * 1.25} {cx + w / 2} {base_y - h} '
        f'{cx + w / 2} {base_y} Z" fill="{color}" opacity="{op}"/>'
    )


# ---------------------------------------------------------------------------
# 主角：汉堡圣像
# ---------------------------------------------------------------------------
def burger_idol(cx: float, cy: float, w: float = 190, halo: str = "arch",
                arms: bool = True, cape: bool = True, crown: bool = False,
                base: str = "cloud", seed: int = 0, glow: bool = True) -> str:
    """把一份汉堡画成塔罗里的圣像。

    构图（(cx, cy) 是汉堡正中）::

            ✦ 光环 ✦
          ╭─────────╮     面包顶（扁穹顶 + 芝麻）
         │ ●  ●  ●  ● │
        ├─────────────┤   生菜（波浪边，略宽出面包）
       ├───────────────┤  芝士（两片垂角）
        ├─────────────┤   肉饼
          ╰─────────╯     面包底
        ╱             ╲   披风（从两侧展开）
      ──┴─────────────┴──  地平线 / 托盘 / 云

    拟人化靠三处：头顶光环、两侧手臂（末端有手）、两侧展开的披风。
    不画脸——塔罗人物多半是背影或侧影，留白比画表情更耐看。
    """
    hw = w / 2
    top_h = w * 0.34
    lettuce_h = w * 0.13
    cheese_h = w * 0.13
    patty_h = w * 0.17
    bun_h = w * 0.16
    total = top_h + lettuce_h + cheese_h + patty_h + bun_h

    y_top = cy - total / 2                 # 面包顶弧线的底边
    y_lettuce = y_top + top_h
    y_cheese = y_lettuce + lettuce_h
    y_patty = y_cheese + cheese_h
    y_bun = y_patty + patty_h
    y_base = y_bun + bun_h

    parts = []

    # --- 背后的柔光 ---
    if glow:
        parts.append(
            f'<ellipse cx="{cx}" cy="{cy}" rx="{hw * 1.95}" ry="{hw * 1.8}" '
            f'fill="{GOLD}" opacity="0.05"/>')

    # --- 背后的杏仁形光背（mandorla）：塔罗/宗教画里圣像的经典构图 ---
    if cape:
        mh = total * 0.82 + w * 0.20
        mw = w * 0.40
        parts.append(
            f'<path d="M{cx} {cy - mh} A{mw} {mh} 0 0 1 {cx} {cy + mh} '
            f'A{mw} {mh} 0 0 1 {cx} {cy - mh} Z" fill="{GOLD}" fill-opacity="0.08" '
            f'stroke="{GOLD}" stroke-opacity="0.62" stroke-width="1.8"/>')
        parts.append(
            f'<path d="M{cx} {cy - mh * 0.82} A{mw * 0.78} {mh * 0.82} 0 0 1 {cx} {cy + mh * 0.82} '
            f'A{mw * 0.72} {mh * 0.84} 0 0 1 {cx} {cy - mh * 0.84} Z" fill="none" '
            f'stroke="{GOLD}" stroke-opacity="0.28" stroke-width="1"/>')

    # --- 手臂：从两侧伸出，末端一个小圆当手 ---
    if arms:
        for sign in (-1, 1):
            sx = cx + sign * hw * 0.88
            sy = y_patty + patty_h * 0.45
            ex = cx + sign * hw * 1.48
            ey = y_bun + bun_h * 0.55
            parts.append(
                f'<path d="M{sx} {sy} C{cx + sign * hw * 1.20} {sy + w * 0.06} '
                f'{ex} {ey - w * 0.10} {ex} {ey}" fill="none" stroke="{GOLD}" '
                f'stroke-opacity="0.85" stroke-width="4.0" stroke-linecap="round"/>')
            parts.append(f'<circle cx="{ex}" cy="{ey}" r="{w * 0.042}" fill="{GOLD}" '
                         f'opacity="0.95"/>')

    # --- 面包底 ---
    parts.append(
        f'<path d="M{cx - hw * 0.97} {y_bun} Q{cx} {y_bun + bun_h * 1.75} '
        f'{cx + hw * 0.97} {y_bun} Z" fill="{GOLD}" fill-opacity="0.88" '
        f'stroke="{GOLD_DEEP}" stroke-width="1.4"/>')

    # --- 肉饼 ---
    parts.append(
        f'<rect x="{cx - hw * 0.99}" y="{y_patty}" width="{hw * 1.98}" height="{patty_h}" '
        f'rx="{patty_h * 0.38}" fill="#6b3410" stroke="{GOLD_DEEP}" stroke-opacity="0.75" '
        f'stroke-width="1.2"/>')
    parts.append(
        f'<rect x="{cx - hw * 0.9}" y="{y_patty + patty_h * 0.20}" width="{hw * 1.8}" '
        f'height="{patty_h * 0.16}" rx="{patty_h * 0.08}" fill="#9a5527" opacity="0.7"/>')

    # --- 芝士：一片方角 + 两片垂角 ---
    parts.append(
        f'<rect x="{cx - hw * 1.01}" y="{y_cheese}" width="{hw * 2.02}" height="{cheese_h * 0.52}" '
        f'fill="#f0b429" stroke="{GOLD_DEEP}" stroke-opacity="0.6" stroke-width="1.1"/>')
    for sign, frac in ((-1, 0.52), (1, 0.26)):
        x0 = cx + sign * hw * frac
        parts.append(
            f'<path d="M{x0} {y_cheese + cheese_h * 0.4} L{x0 + sign * hw * 0.46} '
            f'{y_cheese + cheese_h * 0.4} L{x0 + sign * hw * 0.16} {y_cheese + cheese_h * 1.22} Z" '
            f'fill="#f0b429" opacity="0.95"/>')

    # --- 生菜：波浪边，略宽出面包 ---
    wave = [f"M{cx - hw * 1.08} {y_cheese}"]
    seg = 8
    for i in range(seg):
        x0 = cx - hw * 1.08 + (hw * 2.16) * i / seg
        x1 = cx - hw * 1.08 + (hw * 2.16) * (i + 1) / seg
        wave.append(f"Q{(x0 + x1) / 2:.1f} {y_lettuce + lettuce_h * 0.05:.1f} {x1:.1f} {y_cheese}")
    parts.append(
        f'<path d="{" ".join(wave)} L{cx + hw * 1.08} {y_lettuce} '
        f'L{cx - hw * 1.08} {y_lettuce} Z" fill="#6f9b4a" fill-opacity="0.92" '
        f'stroke="#3f6b2a" stroke-width="1.2"/>')

    # --- 面包顶 ---
    parts.append(
        f'<path d="M{cx - hw} {y_lettuce} A{hw} {top_h} 0 0 1 {cx + hw} {y_lettuce} Z" '
        f'fill="{GOLD}" fill-opacity="0.95" stroke="{GOLD_DEEP}" stroke-width="1.6"/>')
    parts.append(
        f'<path d="M{cx - hw * 0.70} {y_lettuce - top_h * 0.44} A{hw * 0.72} {top_h * 0.66} 0 0 1 '
        f'{cx + hw * 0.48} {y_lettuce - top_h * 0.70}" fill="none" stroke="{CREAM}" '
        f'stroke-opacity="0.55" stroke-width="2.6" stroke-linecap="round"/>')
    rng = random.Random(seed * 104729 + 7)
    for _ in range(11):
        ang = rng.uniform(0.16, 0.84) * math.pi
        rad = rng.uniform(0.18, 0.78)
        sx = cx - math.cos(ang) * hw * rad
        sy = y_lettuce - math.sin(ang) * top_h * rad
        rot = rng.uniform(-40, 40)
        parts.append(
            f'<ellipse cx="{sx:.1f}" cy="{sy:.1f}" rx="{w * 0.022}" ry="{w * 0.012}" '
            f'fill="{CREAM}" opacity="0.92" transform="rotate({rot:.0f} {sx:.1f} {sy:.1f})"/>')

    if crown:
        cw = w * 0.24
        cy0 = y_lettuce - top_h * 0.92
        parts.append(
            f'<path d="M{cx - cw} {cy0} L{cx - cw} {cy0 - w * 0.09} '
            f'L{cx - cw * 0.52} {cy0 - w * 0.035} L{cx} {cy0 - w * 0.15} '
            f'L{cx + cw * 0.52} {cy0 - w * 0.035} L{cx + cw} {cy0 - w * 0.09} '
            f'L{cx + cw} {cy0} Z" fill="{GOLD}" stroke="{GOLD_DEEP}" stroke-width="1.3"/>')
        for dx, dy in ((-cw, -w * 0.09), (0, -w * 0.15), (cw, -w * 0.09)):
            parts.append(f'<circle cx="{cx + dx}" cy="{cy0 + dy}" r="{w * 0.016}" '
                         f'fill="{CREAM}" opacity="0.9"/>')
        parts.append(f'<rect x="{cx - cw}" y="{cy0 - w * 0.012}" width="{cw * 2}" '
                     f'height="{w * 0.022}" fill="{GOLD_DEEP}" opacity="0.8"/>')

    # --- 光环 ---
    if halo in ("arch", "rays"):
        # arch 复用放射光芒：金拱门只留在牌冠上，画面里再来一个 M 形色块会很脏
        for i in range(13):
            a = math.pi + i * math.pi / 12
            x1 = cx + math.cos(a) * w * 0.38
            y1 = cy + math.sin(a) * w * 0.46
            x2 = cx + math.cos(a) * w * 0.62
            y2 = cy + math.sin(a) * w * 0.80
            parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                         f'stroke="{GOLD}" stroke-width="1.8" stroke-linecap="round" '
                         f'opacity="{0.5 if i % 2 == 0 else 0.26}"/>')
    elif halo == "ring":
        parts.append(
            f'<ellipse cx="{cx}" cy="{y_top - w * 0.20}" rx="{w * 0.40}" ry="{w * 0.10}" '
            f'fill="none" stroke="{GOLD}" stroke-width="2.6" opacity="0.9"/>')
        parts.append(
            f'<ellipse cx="{cx}" cy="{y_top - w * 0.20}" rx="{w * 0.46}" ry="{w * 0.13}" '
            f'fill="none" stroke="{GOLD}" stroke-width="1" opacity="0.4"/>')
    elif halo == "rays":
        for i in range(11):
            a = math.pi + i * math.pi / 10
            x1 = cx + math.cos(a) * w * 0.40
            y1 = y_top - w * 0.08 + math.sin(a) * w * 0.24
            x2 = cx + math.cos(a) * w * 0.56
            y2 = y_top - w * 0.08 + math.sin(a) * w * 0.42
            parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                         f'stroke="{GOLD}" stroke-width="2" stroke-linecap="round" '
                         f'opacity="{0.75 if i % 2 == 0 else 0.42}"/>')

    # --- 底座 ---
    if base:
        parts.append(_pedestal(cx, y_base + bun_h * 0.55, w, base))
    return "".join(parts)


def _pedestal(cx: float, y: float, w: float, kind: str) -> str:
    hw = w / 2
    if kind == "tray":
        return (f'<rect x="{cx - hw * 1.18}" y="{y}" width="{hw * 2.36}" height="{w * 0.055}" '
                f'rx="{w * 0.027}" fill="{GOLD_DEEP}" opacity="0.55"/>'
                f'<rect x="{cx - hw * 1.0}" y="{y - w * 0.022}" width="{hw * 2.0}" '
                f'height="{w * 0.03}" rx="{w * 0.015}" fill="{GOLD}" opacity="0.35"/>')
    if kind == "altar":
        return (f'<path d="M{cx - hw * 1.1} {y} L{cx + hw * 1.1} {y} L{cx + hw * 0.9} '
                f'{y + w * 0.14} L{cx - hw * 0.9} {y + w * 0.14} Z" fill="{GOLD_DEEP}" opacity="0.45"/>'
                f'<line x1="{cx - hw * 1.15}" y1="{y}" x2="{cx + hw * 1.15}" y2="{y}" '
                f'stroke="{GOLD}" stroke-width="2" opacity="0.7"/>')
    if kind == "cliff":
        return (f'<path d="M{cx - hw * 1.5} {y + w * 0.20} L{cx - hw * 0.5} {y} '
                f'L{cx + hw * 0.2} {y + w * 0.05} L{cx + hw * 1.4} {y - w * 0.02} '
                f'L{cx + hw * 1.5} {y + w * 0.24} Z" fill="{PLUM}" opacity="0.55"/>')
    if kind == "wave":
        return (f'<path d="M{cx - hw * 1.6} {y + w * 0.10} Q{cx - hw * 0.8} {y - w * 0.04} '
                f'{cx} {y + w * 0.07} Q{cx + hw * 0.8} {y + w * 0.17} {cx + hw * 1.6} '
                f'{y + w * 0.05} L{cx + hw * 1.6} {y + w * 0.2} L{cx - hw * 1.6} {y + w * 0.2} Z" '
                f'fill="{TEAL}" opacity="0.30"/>')
    # cloud（默认）：地平线 + 三层柔云，压住画面底部
    out = [f'<line x1="{cx - hw * 1.55}" y1="{y + w * 0.10}" x2="{cx + hw * 1.55}" '
           f'y2="{y + w * 0.10}" stroke="{GOLD}" stroke-opacity="0.32" stroke-width="1.3"/>']
    for dx, dy, rx, ry, op in ((-0.58, 0.005, 0.40, 0.072, 0.13),
                               (0.54, 0.035, 0.36, 0.062, 0.11),
                               (0.0, 0.055, 0.62, 0.082, 0.16)):
        out.append(f'<ellipse cx="{cx + hw * dx}" cy="{y + w * dy}" rx="{hw * rx}" '
                   f'ry="{w * ry}" fill="{CREAM}" opacity="{op}" stroke="{GOLD}" '
                   f'stroke-opacity="0.22" stroke-width="1"/>')
    return "".join(out)


# ---------------------------------------------------------------------------
# 四个花色：把餐具画成塔罗的法器
# ---------------------------------------------------------------------------
def fries(x: float, y: float, s: float = 1.0, color: str = GOLD, op: float = 1.0) -> str:
    """薯条 = 权杖：一束薯条从红盒里立起来，顶端有火星。"""
    u = 26 * s
    out = [
        f'<path d="M{x - u * 0.72} {y + u * 0.30} L{x + u * 0.72} {y + u * 0.30} '
        f'L{x + u * 0.56} {y + u * 1.42} L{x - u * 0.56} {y + u * 1.42} Z" fill="#8e2a22" opacity="0.92"/>',
        f'<line x1="{x - u * 0.66}" y1="{y + u * 0.52}" x2="{x + u * 0.66}" y2="{y + u * 0.52}" '
        f'stroke="{CREAM}" stroke-width="{1.6 * s}" opacity="0.55"/>',
    ]
    for i, (dx, tilt, ln) in enumerate(((-0.42, -14, 1.35), (-0.16, -5, 1.62), (0.10, 6, 1.5),
                                        (0.36, 16, 1.28))):
        x0 = x + u * dx
        out.append(
            f'<g transform="rotate({tilt} {x0} {y + u * 0.30})">'
            f'<rect x="{x0 - u * 0.10}" y="{y + u * 0.30 - u * ln}" width="{u * 0.20}" '
            f'height="{u * ln}" rx="{u * 0.05}" fill="{color}" opacity="0.95"/></g>')
    out.append(f'<circle cx="{x}" cy="{y - u * 1.5}" r="{u * 0.10}" fill="{CREAM}" opacity="0.85"/>')
    return f'<g opacity="{op}">{"".join(out)}</g>'


def cup(x: float, y: float, s: float = 1.0, color: str = GOLD, op: float = 1.0) -> str:
    """可乐 = 圣杯：带盖和吸管的杯子，杯身有高光与冰块。"""
    u = 26 * s
    out = [
        f'<path d="M{x - u * 0.62} {y - u * 0.30} L{x + u * 0.62} {y - u * 0.30} '
        f'L{x + u * 0.44} {y + u * 1.30} L{x - u * 0.44} {y + u * 1.30} Z" '
        f'fill="{TEAL}" fill-opacity="0.55" stroke="{color}" stroke-opacity="0.85" stroke-width="{1.6 * s}"/>',
        f'<rect x="{x - u * 0.70}" y="{y - u * 0.44}" width="{u * 1.40}" height="{u * 0.20}" '
        f'rx="{u * 0.07}" fill="{color}" opacity="0.9"/>',
        f'<line x1="{x + u * 0.16}" y1="{y - u * 1.05}" x2="{x + u * 0.30}" y2="{y - u * 0.40}" '
        f'stroke="{CREAM}" stroke-width="{2.4 * s}" stroke-linecap="round" opacity="0.9"/>',
        f'<rect x="{x - u * 0.42}" y="{y - u * 0.10}" width="{u * 0.24}" height="{u * 0.34}" '
        f'rx="{u * 0.05}" fill="{CREAM}" opacity="0.28" transform="rotate(-12 {x} {y})"/>',
    ]
    return f'<g opacity="{op}">{"".join(out)}</g>'


def knife(x: float, y: float, s: float = 1.0, color: str = GOLD, op: float = 1.0) -> str:
    """餐刀 = 宝剑：竖握的刀，刀身有中线与高光。"""
    u = 26 * s
    out = [
        f'<path d="M{x - u * 0.16} {y - u * 1.55} L{x + u * 0.16} {y - u * 1.55} '
        f'L{x + u * 0.20} {y + u * 0.22} L{x - u * 0.20} {y + u * 0.22} Z" '
        f'fill="{CREAM}" fill-opacity="0.82" stroke="{color}" stroke-width="{1.3 * s}"/>',
        f'<line x1="{x}" y1="{y - u * 1.45}" x2="{x}" y2="{y + u * 0.16}" '
        f'stroke="{NIGHT}" stroke-opacity="0.35" stroke-width="{1.2 * s}"/>',
        f'<rect x="{x - u * 0.46}" y="{y + u * 0.22}" width="{u * 0.92}" height="{u * 0.16}" '
        f'rx="{u * 0.06}" fill="{color}"/>',
        f'<rect x="{x - u * 0.15}" y="{y + u * 0.38}" width="{u * 0.30}" height="{u * 0.72}" '
        f'rx="{u * 0.09}" fill="{GOLD_DEEP}"/>',
        f'<circle cx="{x}" cy="{y + u * 0.58}" r="{u * 0.05}" fill="{NIGHT}" opacity="0.5"/>',
    ]
    return f'<g opacity="{op}">{"".join(out)}</g>'


def coin(x: float, y: float, s: float = 1.0, color: str = GOLD, op: float = 1.0) -> str:
    """汉堡 = 星币：金圆盘里压一个迷你汉堡。"""
    u = 22 * s
    out = [
        f'<circle cx="{x}" cy="{y}" r="{u}" fill="{color}" fill-opacity="0.16" '
        f'stroke="{color}" stroke-width="{u * 0.11}"/>',
        f'<circle cx="{x}" cy="{y}" r="{u * 0.74}" fill="none" stroke="{color}" '
        f'stroke-opacity="0.55" stroke-width="{u * 0.05}"/>',
        f'<path d="M{x - u * 0.42} {y - u * 0.10} A{u * 0.42} {u * 0.26} 0 0 1 {x + u * 0.42} '
        f'{y - u * 0.10} Z" fill="{color}" opacity="0.95"/>',
        f'<rect x="{x - u * 0.44}" y="{y - u * 0.06}" width="{u * 0.88}" height="{u * 0.16}" '
        f'fill="{TEAL}" opacity="0.8"/>',
        f'<path d="M{x - u * 0.42} {y + u * 0.12} Q{x} {y + u * 0.40} {x + u * 0.42} '
        f'{y + u * 0.12} Z" fill="{color}" opacity="0.85"/>',
    ]
    return f'<g opacity="{op}">{"".join(out)}</g>'


SUIT_SYMBOL = {"wands": fries, "cups": cup, "swords": knife, "pentacles": coin}
SUIT_COLOR = {"wands": "#e07a3c", "cups": TEAL, "swords": "#b9c6d8", "pentacles": GOLD}


# ---------------------------------------------------------------------------
# 大阿卡纳的象征物
# ---------------------------------------------------------------------------
def eye(x: float, y: float, s: float = 1.0, color: str = GOLD) -> str:
    u = 22 * s
    return (f'<path d="M{x - u * 1.5} {y} Q{x} {y - u * 1.05} {x + u * 1.5} {y} '
            f'Q{x} {y + u * 1.05} {x - u * 1.5} {y} Z" fill="none" stroke="{color}" '
            f'stroke-width="{1.8 * s}"/>'
            f'<circle cx="{x}" cy="{y}" r="{u * 0.40}" fill="{color}" opacity="0.92"/>'
            f'<circle cx="{x}" cy="{y}" r="{u * 0.16}" fill="{NIGHT}"/>')


def key(x: float, y: float, s: float = 1.0, color: str = GOLD) -> str:
    u = 22 * s
    return (f'<circle cx="{x}" cy="{y - u * 0.9}" r="{u * 0.42}" fill="none" stroke="{color}" '
            f'stroke-width="{1.9 * s}"/>'
            f'<line x1="{x}" y1="{y - u * 0.48}" x2="{x}" y2="{y + u * 1.2}" stroke="{color}" '
            f'stroke-width="{1.9 * s}"/>'
            f'<line x1="{x}" y1="{y + u * 1.2}" x2="{x + u * 0.46}" y2="{y + u * 1.2}" '
            f'stroke="{color}" stroke-width="{1.9 * s}"/>'
            f'<line x1="{x}" y1="{y + u * 0.82}" x2="{x + u * 0.34}" y2="{y + u * 0.82}" '
            f'stroke="{color}" stroke-width="{1.9 * s}"/>')


def scale(x: float, y: float, s: float = 1.0, color: str = GOLD) -> str:
    u = 26 * s
    return (f'<line x1="{x}" y1="{y - u * 1.1}" x2="{x}" y2="{y + u * 1.15}" stroke="{color}" '
            f'stroke-width="{2 * s}"/>'
            f'<line x1="{x - u * 1.2}" y1="{y - u * 0.72}" x2="{x + u * 1.2}" y2="{y - u * 0.72}" '
            f'stroke="{color}" stroke-width="{2 * s}"/>'
            f'<path d="M{x - u * 1.5} {y - u * 0.1} A{u * 0.48} {u * 0.48} 0 0 0 {x - u * 0.54} '
            f'{y - u * 0.1} Z" fill="{color}" opacity="0.7"/>'
            f'<path d="M{x + u * 0.54} {y - u * 0.1} A{u * 0.48} {u * 0.48} 0 0 0 {x + u * 1.5} '
            f'{y - u * 0.1} Z" fill="{color}" opacity="0.7"/>'
            f'<line x1="{x - u * 0.72}" y1="{y - u * 1.1}" x2="{x + u * 0.72}" y2="{y - u * 1.1}" '
            f'stroke="{color}" stroke-width="{2.4 * s}"/>')


def wheel(x: float, y: float, s: float = 1.0, color: str = GOLD) -> str:
    r = 30 * s
    out = [f'<circle cx="{x}" cy="{y}" r="{r}" fill="none" stroke="{color}" stroke-width="3"/>',
           f'<circle cx="{x}" cy="{y}" r="{r * 0.72}" fill="none" stroke="{color}" '
           f'stroke-opacity="0.6" stroke-width="1.4"/>']
    for i in range(8):
        a = i * math.pi / 4
        out.append(f'<line x1="{x + math.cos(a) * r * 0.24:.1f}" y1="{y + math.sin(a) * r * 0.24:.1f}" '
                   f'x2="{x + math.cos(a) * r:.1f}" y2="{y + math.sin(a) * r:.1f}" '
                   f'stroke="{color}" stroke-width="1.8"/>')
    out.append(f'<circle cx="{x}" cy="{y}" r="{r * 0.22}" fill="{color}" opacity="0.9"/>')
    return "".join(out)


def tower(x: float, y: float, s: float = 1.0, color: str = GOLD) -> str:
    u = 24 * s
    return (f'<path d="M{x - u * 0.62} {y + u * 1.4} L{x - u * 0.44} {y - u * 0.7} '
            f'L{x + u * 0.44} {y - u * 0.7} L{x + u * 0.62} {y + u * 1.4} Z" fill="none" '
            f'stroke="{color}" stroke-width="{1.9 * s}"/>'
            f'<path d="M{x - u * 0.5} {y - u * 0.7} L{x - u * 0.5} {y - u * 1.1} L{x - u * 0.2} '
            f'{y - u * 0.95} L{x} {y - u * 1.25} L{x + u * 0.2} {y - u * 0.95} L{x + u * 0.5} '
            f'{y - u * 1.1} L{x + u * 0.5} {y - u * 0.7}" fill="none" stroke="{color}" '
            f'stroke-width="{1.9 * s}"/>'
            f'<rect x="{x - u * 0.14}" y="{y + u * 0.4}" width="{u * 0.28}" height="{u * 0.5}" '
            f'fill="{color}" opacity="0.8"/>')


def flame(x: float, y: float, s: float = 1.0, color: str = "#e07a3c") -> str:
    u = 24 * s
    return (f'<path d="M{x} {y - u * 1.5} C{x + u * 0.30} {y - u * 0.85} {x + u * 1.0} '
            f'{y - u * 0.55} {x + u * 0.86} {y + u * 0.20} C{x + u * 0.78} {y + u * 0.95} '
            f'{x + u * 0.24} {y + u * 1.25} {x} {y + u * 1.25} C{x - u * 0.24} {y + u * 1.25} '
            f'{x - u * 0.78} {y + u * 0.95} {x - u * 0.86} {y + u * 0.20} '
            f'C{x - u * 1.0} {y - u * 0.55} {x - u * 0.30} {y - u * 0.85} {x} {y - u * 1.5} Z" '
            f'fill="{color}" fill-opacity="0.75"/>'
            f'<path d="M{x} {y - u * 0.55} C{x + u * 0.34} {y - u * 0.05} {x + u * 0.30} '
            f'{y + u * 0.62} {x} {y + u * 0.86} C{x - u * 0.30} {y + u * 0.62} '
            f'{x - u * 0.34} {y - u * 0.05} {x} {y - u * 0.55} Z" fill="{CREAM}" opacity="0.7"/>')


def crown(x: float, y: float, s: float = 1.0, color: str = GOLD) -> str:
    u = 26 * s
    return (f'<path d="M{x - u} {y + u * 0.55} L{x - u * 0.75} {y - u * 0.7} L{x - u * 0.34} '
            f'{y + u * 0.05} L{x} {y - u * 0.95} L{x + u * 0.34} {y + u * 0.05} L{x + u * 0.75} '
            f'{y - u * 0.7} L{x + u} {y + u * 0.55} Z" fill="{color}" fill-opacity="0.9" '
            f'stroke="{GOLD_DEEP}" stroke-width="{1.2 * s}"/>')


def wing(x: float, y: float, s: float = 1.0, color: str = CREAM) -> str:
    u = 24 * s
    return "".join(
        f'<path d="M{x} {y} Q{x + u * (0.9 + i * 0.28)} {y - u * (1.1 - i * 0.18)} '
        f'{x + u * (1.5 + i * 0.2)} {y + u * (0.3 + i * 0.2)} Q{x + u * (0.7 + i * 0.2)} '
        f'{y + u * (0.1 + i * 0.2)} {x} {y}" fill="none" stroke="{color}" '
        f'stroke-opacity="{0.65 - i * 0.12}" stroke-width="{1.6 * s}"/>'
        for i in range(3))


def scroll(x: float, y: float, s: float = 1.0, color: str = CREAM) -> str:
    u = 22 * s
    return (f'<rect x="{x - u * 0.62}" y="{y - u * 0.85}" width="{u * 1.24}" height="{u * 1.7}" '
            f'rx="{u * 0.1}" fill="{color}" fill-opacity="0.22" stroke="{color}" '
            f'stroke-width="{1.5 * s}"/>'
            + "".join(f'<line x1="{x - u * 0.4}" y1="{y - u * 0.5 + i * u * 0.34}" '
                      f'x2="{x + u * 0.4}" y2="{y - u * 0.5 + i * u * 0.34}" stroke="{color}" '
                      f'stroke-opacity="0.55" stroke-width="{1.1 * s}"/>' for i in range(4))
            + f'<ellipse cx="{x - u * 0.62}" cy="{y - u * 0.85}" rx="{u * 0.16}" ry="{u * 0.1}" '
              f'fill="{color}" opacity="0.7"/>'
              f'<ellipse cx="{x + u * 0.62}" cy="{y + u * 0.85}" rx="{u * 0.16}" ry="{u * 0.1}" '
              f'fill="{color}" opacity="0.7"/>')


def pillar(x: float, y: float, s: float = 1.0, color: str = CREAM) -> str:
    u = 20 * s
    return (f'<rect x="{x - u * 0.34}" y="{y - u * 1.5}" width="{u * 0.68}" height="{u * 3.0}" '
            f'fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-opacity="0.75" '
            f'stroke-width="{1.4 * s}"/>'
            f'<rect x="{x - u * 0.52}" y="{y - u * 1.72}" width="{u * 1.04}" height="{u * 0.24}" '
            f'fill="{color}" opacity="0.55"/>'
            f'<rect x="{x - u * 0.52}" y="{y + u * 1.5}" width="{u * 1.04}" height="{u * 0.24}" '
            f'fill="{color}" opacity="0.55"/>')


def wheat(x: float, y: float, s: float = 1.0, color: str = GOLD) -> str:
    u = 20 * s
    out = [f'<path d="M{x} {y + u * 1.5} Q{x - u * 0.15} {y} {x} {y - u * 1.5}" fill="none" '
           f'stroke="{color}" stroke-width="{1.8 * s}"/>']
    for i in range(4):
        yy = y - u * 1.15 + i * u * 0.52
        out.append(f'<ellipse cx="{x - u * 0.34}" cy="{yy}" rx="{u * 0.30}" ry="{u * 0.15}" '
                   f'fill="{color}" opacity="0.8" transform="rotate(-28 {x} {yy})"/>')
        out.append(f'<ellipse cx="{x + u * 0.34}" cy="{yy}" rx="{u * 0.30}" ry="{u * 0.15}" '
                   f'fill="{color}" opacity="0.8" transform="rotate(28 {x} {yy})"/>')
    return "".join(out)


def horn(x: float, y: float, s: float = 1.0, color: str = GOLD) -> str:
    u = 24 * s
    return (f'<path d="M{x - u * 1.2} {y + u * 0.5} Q{x + u * 0.2} {y - u * 0.2} {x + u * 1.25} '
            f'{y - u * 0.85} L{x + u * 1.35} {y - u * 0.28} Q{x + u * 0.3} {y + u * 0.35} '
            f'{x - u * 1.05} {y + u * 1.05} Z" fill="{color}" fill-opacity="0.85"/>'
            f'<line x1="{x - u * 1.05}" y1="{y + u * 0.28}" x2="{x + u * 1.15}" y2="{y - u * 0.45}" '
            f'stroke="{NIGHT}" stroke-opacity="0.4" stroke-width="{1.4 * s}"/>')


def wreath(x: float, y: float, s: float = 1.0, color: str = GOLD) -> str:
    r = 42 * s
    out = [f'<ellipse cx="{x}" cy="{y}" rx="{r}" ry="{r * 0.72}" fill="none" stroke="{color}" '
           f'stroke-width="2.4" opacity="0.85"/>']
    for i in range(14):
        a = i * 2 * math.pi / 14
        out.append(f'<ellipse cx="{x + math.cos(a) * r:.1f}" cy="{y + math.sin(a) * r * 0.72:.1f}" '
                   f'rx="{r * 0.13}" ry="{r * 0.07}" fill="{TEAL}" opacity="0.6" '
                   f'transform="rotate({math.degrees(a):.0f} {x + math.cos(a) * r:.1f} '
                   f'{y + math.sin(a) * r * 0.72:.1f})"/>')
    return "".join(out)


def lightning(x: float, y: float, s: float = 1.0, color: str = CREAM) -> str:
    u = 26 * s
    return (f'<path d="M{x + u * 0.4} {y - u * 1.6} L{x - u * 0.55} {y + u * 0.1} L{x + u * 0.1} '
            f'{y + u * 0.1} L{x - u * 0.3} {y + u * 1.6} L{x + u * 0.65} {y - u * 0.25} L{x} '
            f'{y - u * 0.25} Z" fill="{color}" opacity="0.9"/>')


def infinity(x: float, y: float, s: float = 1.0, color: str = GOLD) -> str:
    u = 20 * s
    return (f'<path d="M{x} {y} C{x - u * 0.6} {y - u * 0.85} {x - u * 1.5} {y - u * 0.5} '
            f'{x - u * 1.5} {y} C{x - u * 1.5} {y + u * 0.5} {x - u * 0.6} {y + u * 0.85} '
            f'{x} {y} C{x + u * 0.6} {y - u * 0.85} {x + u * 1.5} {y - u * 0.5} {x + u * 1.5} '
            f'{y} C{x + u * 1.5} {y + u * 0.5} {x + u * 0.6} {y + u * 0.85} {x} {y} Z" '
            f'fill="none" stroke="{color}" stroke-width="{2.6 * s}"/>')


def chain(x: float, y: float, s: float = 1.0, color: str = GOLD) -> str:
    u = 21 * s
    return "".join(
        f'<ellipse cx="{x + u * (i - 2) * 1.05}" cy="{y + u * 0.26 * (i % 2)}" rx="{u * 0.55}" '
        f'ry="{u * 0.33}" fill="none" stroke="{color}" stroke-width="{1.7 * s}" '
        f'transform="rotate({-16 * (i % 2)} {x + u * (i - 2) * 1.05} {y})"/>'
        for i in range(5))


def mountain(x: float, y: float, s: float = 1.0, color: str = PLUM) -> str:
    u = 30 * s
    return (f'<path d="M{x - u * 1.7} {y + u * 0.9} L{x - u * 0.75} {y - u * 0.75} L{x - u * 0.1} '
            f'{y + u * 0.1} L{x + u * 0.55} {y - u * 0.95} L{x + u * 1.7} {y + u * 0.9} Z" '
            f'fill="{color}" opacity="0.5"/>')


SYMBOLS = {
    "eye": eye, "key": key, "scale": scale, "wheel": wheel, "tower": tower,
    "flame": flame, "crown": crown, "wing": wing, "scroll": scroll, "pillar": pillar,
    "wheat": wheat, "horn": horn, "wreath": wreath, "lightning": lightning,
    "infinity": infinity, "chain": chain, "mountain": mountain,
    "fries": fries, "cup": cup, "knife": knife, "coin": coin, "sun": sun, "moon": moon,
}


def draw_symbol(name: str, x: float, y: float, s: float = 1.0,
                color: Optional[str] = None) -> str:
    """按名字画一个象征物；不认识的名字静默跳过，牌面不至于崩。"""
    fn = SYMBOLS.get(name)
    if not fn:
        return ""
    if name == "flame":
        return fn(x, y, s)          # 火保持自己的橙，混进金色会看成水滴
    return fn(x, y, s, color or GOLD)


# ---------------------------------------------------------------------------
# 大阿卡纳构图配置：每张牌的光环/姿态/法器/底座/天空
# ---------------------------------------------------------------------------
MAJOR_ART = {
    0:  {"halo": "rays", "cape": True, "crown": False, "base": "cliff", "sky": "sun",
         "left": "wheat", "right": "scroll"},                     # 愚者：太阳、行囊
    1:  {"halo": "ring", "cape": False, "crown": False, "base": "altar", "sky": None,
         "left": "cup", "right": "knife", "extra": ["coin", "fries"]},   # 魔术师：四元素
    2:  {"halo": "ring", "cape": True, "crown": True, "base": "tray", "sky": "moon",
         "left": "pillar", "right": "scroll"},                    # 女祭司：双柱与卷轴
    3:  {"halo": "rays", "cape": True, "crown": True, "base": "wave", "sky": "sun",
         "left": "wheat", "right": "wheat"},                      # 皇后：麦穗丰饶
    4:  {"halo": "arch", "cape": True, "crown": True, "base": "altar", "sky": None,
         "left": "fries", "right": "mountain"},                   # 皇帝：权杖与山
    5:  {"halo": "ring", "cape": True, "crown": True, "base": "altar", "sky": None,
         "left": "key", "right": "key", "extra": ["pillar"]},      # 教皇：交叉钥匙
    6:  {"halo": "rays", "cape": True, "crown": False, "base": "cloud", "sky": "sun",
         "left": "wing", "right": "wing"},                        # 恋人：天使之翼
    7:  {"halo": "arch", "cape": True, "crown": True, "base": "wave", "sky": None,
         "left": "wheel", "right": "fries"},                      # 战车
    8:  {"halo": "ring", "cape": False, "crown": False, "base": "cloud", "sky": None,
         "left": "infinity", "right": "flame"},                   # 力量：无限与火
    9:  {"halo": "ring", "cape": True, "crown": False, "base": "cliff", "sky": "moon",
         "left": "fries", "right": "eye"},                        # 隐士：提灯
    10: {"halo": "ring", "cape": False, "crown": False, "base": "cloud", "sky": None,
         "left": "wheel", "right": "wheel", "extra": ["eye"]},    # 命运之轮
    11: {"halo": "arch", "cape": True, "crown": True, "base": "altar", "sky": None,
         "left": "scale", "right": "knife"},                      # 正义：天平与剑
    12: {"halo": "rays", "cape": True, "crown": False, "base": "cloud", "sky": None,
         "left": "chain", "right": "key"},                        # 倒吊人
    13: {"halo": "ring", "cape": True, "crown": False, "base": "cliff", "sky": "moon",
         "left": "wheat", "right": "flame"},                      # 死神：黑旗与玫瑰
    14: {"halo": "ring", "cape": True, "crown": False, "base": "wave", "sky": "sun",
         "left": "cup", "right": "cup"},                          # 节制：两只杯
    15: {"halo": "arch", "cape": True, "crown": True, "base": "altar", "sky": "moon",
         "left": "chain", "right": "flame"},                      # 恶魔：锁链与火
    16: {"halo": "rays", "cape": True, "crown": False, "base": "cliff", "sky": None,
         "left": "tower", "right": "lightning"},                  # 塔：雷电
    17: {"halo": "rays", "cape": True, "crown": False, "base": "wave", "sky": "moon",
         "left": "cup", "right": "cup", "extra": ["eye"]},        # 星星：倒水的杯
    18: {"halo": "ring", "cape": True, "crown": False, "base": "wave", "sky": "moon",
         "left": "tower", "right": "key"},                        # 月亮
    19: {"halo": "rays", "cape": True, "crown": True, "base": "wave", "sky": "sun",
         "left": "wheat", "right": "wheat"},                      # 太阳
    20: {"halo": "rays", "cape": True, "crown": False, "base": "cloud", "sky": None,
         "left": "horn", "right": "wing"},                        # 审判：号角
    21: {"halo": "ring", "cape": True, "crown": True, "base": "cloud", "sky": None,
         "left": "wreath", "right": "wreath"},                    # 世界：花环
}


def pips_arc(suit: str, n: int, cx: float, cy: float, r: float = 200,
             seed: int = 0) -> str:
    """小阿卡纳：把 N 个法器串成一道半圆光环，罩在圣像上方。

    这是韦特牌小阿卡纳的语法（按张数摆符号），换成薯条/可乐/餐刀/汉堡币，
    既是「几个」的计数，也像圣像头顶的念珠与光晕。
    宫廷牌（11–14）改为「一大两小」：主法器悬在头顶，两侧各一件。
    """
    fn = SUIT_SYMBOL.get(suit, coin)
    color = SUIT_COLOR.get(suit, GOLD)
    out = []

    if n >= 11:  # page / knight / queen / king
        out.append(fn(cx, cy - r * 0.86, 1.25, color))
        out.append(fn(cx - r * 0.56, cy - r * 0.62, 0.72, color))
        out.append(fn(cx + r * 0.56, cy - r * 0.62, 0.72, color))
        return "".join(out)

    if n == 1:
        return fn(cx, cy - r * 0.72, 1.35, color)

    start, end = math.radians(-168), math.radians(-12)
    s = 0.60 if n >= 9 else (0.68 if n >= 6 else 0.80)
    for i in range(n):
        t = i / (n - 1)
        a = start + (end - start) * t
        out.append(fn(cx + math.cos(a) * r, cy + math.sin(a) * r, s, color))
    return "".join(out)


def suit_rank_of(card_id: int):
    """牌号 → (花色, 张数)，宫廷牌返回 11。"""
    if card_id < 22:
        return None, 0
    idx = card_id - 22
    suit_list = ["wands", "cups", "swords", "pentacles"]
    suit = suit_list[idx // 14]
    rank = idx % 14 + 1        # 1=ace ... 10, 11=page...
    return suit, rank
