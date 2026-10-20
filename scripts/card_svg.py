"""麦麦塔罗牌 · 可分享卡片（生成 SVG，无第三方依赖）。

把一次解读渲染成一张竖版卡片（1080x1350，适合微信/朋友圈/小红书），
纯 SVG 文本输出，可直接在浏览器或设计工具里打开、截图分享。

用法
----
    # 引擎直接生成
    python3 scripts/tarot_engine.py --spread today --card-svg /tmp/mm-card.svg

    # 也可以用引擎导出的 JSON 单独渲染
    python3 scripts/tarot_engine.py --spread today --json /tmp/r.json
    python3 scripts/card_svg.py /tmp/r.json /tmp/mm-card.svg
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List

W, H = 1080, 1350
FONT = "'PingFang SC','Hiragino Sans GB','Microsoft YaHei','Noto Sans CJK SC',sans-serif"
GOLD = "#d9b46c"
CREAM = "#f6efe4"
MUTED = "#a89684"
BG1, BG2 = "#16110e", "#2a1d16"


def _esc(s: str) -> str:
    return (
        str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )


PUNCT = "。，、；：！？）」』%…"


def _wrap(text: str, width: int = 17, max_lines: int = 4) -> List[str]:
    """按字符数折行（中文场景足够），避免行首标点，最多 max_lines 行。"""
    text = (text or "").strip()
    lines: List[str] = []
    while text and len(lines) < max_lines:
        if len(text) <= width:
            lines.append(text)
            text = ""
            break
        cut = width
        while cut > 1 and text[cut] in PUNCT:
            cut -= 1
        lines.append(text[:cut])
        text = text[cut:]
    if text and lines:
        lines[-1] = lines[-1][: max(1, width - 1)] + "…"
    return lines or [""]


def _card_block(card: Dict, y: int, big: bool) -> str:
    """渲染一张牌的区块，返回 SVG 片段；y 为区块顶部。"""
    out: List[str] = []
    name_size = 66 if big else 42
    sub_size = 26 if big else 18
    food_size = 46 if big else 30
    msg_size = 30 if big else 22
    line_h = 44 if big else 33
    max_lines = 4 if big else 2
    wrap_w = 17 if big else 24

    out.append(
        f'<text x="96" y="{y}" font-size="{sub_size}" fill="{MUTED}" letter-spacing="3">'
        f'{_esc(card.get("position", ""))}</text>'
    )
    out.append(
        f'<text x="96" y="{y + name_size + 16}" font-size="{name_size}" font-weight="700" '
        f'fill="{CREAM}">{_esc(card.get("card_cn", ""))}'
        f'<tspan font-size="{sub_size + 4}" font-weight="400" fill="{MUTED}" dx="14">'
        f'{_esc(card.get("card_en", ""))}</tspan></text>'
    )
    # 正/逆位胶囊
    pill_w, pill_h = (92, 40) if big else (78, 34)
    pill_y = y + name_size - (20 if big else 12)
    out.append(
        f'<rect x="{W - 96 - pill_w}" y="{pill_y}" width="{pill_w}" height="{pill_h}" '
        f'rx="{pill_h / 2}" fill="none" stroke="{GOLD}" stroke-opacity="0.7"/>'
    )
    out.append(
        f'<text x="{W - 96 - pill_w / 2}" y="{pill_y + pill_h / 2 + 6}" font-size="{18 if big else 16}" '
        f'fill="{GOLD}" text-anchor="middle">{_esc(card.get("orientation", ""))}</text>'
    )

    fy = y + name_size + (66 if big else 56)
    out.append(
        f'<text x="96" y="{fy}" font-size="{sub_size - 4}" fill="{MUTED}" letter-spacing="2">'
        f'🍔 麦麦指引</text>'
    )
    out.append(
        f'<text x="96" y="{fy + food_size + 8}" font-size="{food_size}" font-weight="600" '
        f'fill="{GOLD}">{_esc(card.get("food", ""))}'
        f'<tspan font-size="{food_size - 12}" font-weight="400" dx="12">{_esc(card.get("price", ""))}</tspan>'
        f'</text>'
    )

    my = fy + food_size + (58 if big else 44)
    for line in _wrap(card.get("message", ""), wrap_w, max_lines):
        out.append(
            f'<text x="96" y="{my}" font-size="{msg_size}" fill="{CREAM}" '
            f'fill-opacity="0.86">{_esc(line)}</text>'
        )
        my += line_h
    return "\n".join(out)


def render(reading: Dict, out_path: str) -> str:
    cards = reading.get("cards") or []
    big = len(cards) == 1

    parts: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        "<defs>",
        f'<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{BG1}"/><stop offset="1" stop-color="{BG2}"/></linearGradient>',
        "</defs>",
        f'<rect width="{W}" height="{H}" fill="url(#bg)"/>',
        f'<rect x="40" y="40" width="{W - 80}" height="{H - 80}" rx="28" fill="none" '
        f'stroke="{GOLD}" stroke-opacity="0.35" stroke-width="2"/>',
        # 页眉
        f'<text x="96" y="140" font-size="24" fill="{GOLD}" letter-spacing="6">麦麦塔罗牌 · MCD TAROT</text>',
        f'<text x="{W - 96}" y="140" font-size="24" fill="{MUTED}" text-anchor="end">'
        f'{_esc(reading.get("date", ""))}</text>',
        f'<line x1="96" y1="176" x2="{W - 96}" y2="176" stroke="{GOLD}" stroke-opacity="0.25"/>',
        # 牌阵名
        f'<text x="96" y="248" font-size="34" fill="{CREAM}" fill-opacity="0.95">'
        f'{_esc(reading.get("spread_name", ""))}</text>',
    ]

    if reading.get("mood"):
        parts.append(
            f'<text x="96" y="296" font-size="24" fill="{MUTED}">心情：「{_esc(reading["mood"])}」</text>'
        )

    start_y = 380
    if big:
        # 单张牌：中间留白处放一个克制的星盘纹样，整张卡更稳
        parts.append(
            f'<g stroke="{GOLD}" stroke-opacity="0.07" fill="none">'
            f'<circle cx="{W / 2}" cy="960" r="150"/>'
            f'<circle cx="{W / 2}" cy="960" r="196"/>'
            f'<rect x="{W / 2 - 150}" y="810" width="300" height="300" '
            f'transform="rotate(45 {W / 2} 960)"/>'
            f'</g>'
        )
        parts.append(_card_block(cards[0], start_y, True))
    else:
        step = 250
        for i, card in enumerate(cards[:3]):
            parts.append(_card_block(card, start_y - 40 + i * step, False))

    # 页脚
    parts += [
        f'<line x1="96" y1="{H - 200}" x2="{W - 96}" y2="{H - 200}" stroke="{GOLD}" stroke-opacity="0.25"/>',
        f'<text x="96" y="{H - 148}" font-size="26" fill="{CREAM}" fill-opacity="0.9">'
        f'好好吃一顿，是你对自己最朴素的温柔。</text>',
        f'<text x="96" y="{H - 100}" font-size="19" fill="{MUTED}">'
        f'餐品供应与价格以麦当劳官方实时为准 · 塔罗仅供参考，胃口归你</text>',
        "</svg>",
    ]

    svg = "\n".join(parts)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(svg, encoding="utf-8")
    return out_path


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    reading = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(render(reading, sys.argv[2]))


if __name__ == "__main__":
    main()
