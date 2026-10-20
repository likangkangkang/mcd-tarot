"""麦麦塔罗牌 · 塔罗牌面卡片（SVG，无第三方依赖）。

和上一版的「信息卡」不同，这一版把输出做成一张**真的塔罗牌**：
红金配色、双层金框、顶部金拱门、罗马数字、拱形画框里放**真实餐品图**，
牌名/正逆位/一句解读/餐品与价格按牌面节奏排布。逆位会打上红色标记。

餐品图来自连接器 query-meals 返回的 `image` 字段，下载后以 base64 内联进 SVG，
所以单文件可直接打开、转发、截图，不依赖网络。

用法
----
    python3 scripts/tarot_engine.py --spread today --card-svg card.svg
    python3 scripts/tarot_engine.py --spread trinity --card-svg cards.svg   # 会生成 3 张
    python3 scripts/tarot_card.py reading.json card.svg
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

W, H = 750, 1200
FONT = "'PingFang SC','Hiragino Sans GB','Microsoft YaHei','Noto Sans CJK SC',sans-serif"

GOLD = "#f0c25a"
GOLD_DEEP = "#b98a2e"
CREAM = "#fdf4e3"
MUTED = "#c9a98a"
RED = "#c8102e"
BG1, BG2 = "#4a0c08", "#160302"

IMG_CACHE = Path.home() / ".cache" / "mcd-tarot" / "img"

_ROMAN = ["0", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
          "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX", "XXI"]
_RANK_ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
               "XI", "XII", "XIII", "XIV"]


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _numeral(card_id: int) -> str:
    if card_id is None:
        return "0"
    if card_id >= 22:
        return _RANK_ROMAN[(card_id - 22) % 14]
    return _ROMAN[max(0, min(21, int(card_id)))]


def _wrap(text: str, width: int = 18, max_lines: int = 4) -> List[str]:
    """折行，避免行首标点，超出时省略。"""
    punct = "。，、；：！？）」』%…"
    text = (text or "").strip()
    lines: List[str] = []
    while text and len(lines) < max_lines:
        if len(text) <= width:
            lines.append(text)
            text = ""
            break
        cut = width
        while cut > 1 and text[cut] in punct:
            cut -= 1
        lines.append(text[:cut])
        text = text[cut:]
    if text and lines:
        lines[-1] = lines[-1][: max(1, width - 1)] + "…"
    return lines or [""]


# ---------------------------------------------------------------------------
# 餐品图：下载 → 缓存 → base64 内联（失败就返回 None，用绘制占位）
# ---------------------------------------------------------------------------
def _data_uri(url: str) -> Optional[str]:
    if not url:
        return None
    IMG_CACHE.mkdir(parents=True, exist_ok=True)
    ext = ".gif" if ".gif" in url.lower() else ".png"
    path = IMG_CACHE / (hashlib.sha1(url.encode()).hexdigest() + ext)
    if not path.exists():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (mcd-tarot)"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                path.write_bytes(resp.read())
        except Exception:  # noqa: BLE001 - 图挂了不该让整张卡失败
            return None
    try:
        mime = "image/gif" if ext == ".gif" else "image/png"
        return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"
    except OSError:
        return None


def _placeholder_food(cx: float, cy: float) -> str:
    """没有图时画一个极简汉堡，别让画框空着。"""
    return f"""
  <g opacity="0.9">
    <path d="M{cx - 92} {cy + 6} A92 92 0 0 1 {cx + 92} {cy + 6} Z" fill="{GOLD}" opacity="0.92"/>
    <rect x="{cx - 92}" y="{cy + 12}" width="184" height="18" rx="9" fill="#8c4a24"/>
    <rect x="{cx - 84}" y="{cy + 34}" width="168" height="12" rx="6" fill="#e0b53f"/>
    <rect x="{cx - 92}" y="{cy + 50}" width="184" height="20" rx="10" fill="#a8541f"/>
    <path d="M{cx - 96} {cy + 76} Q{cx} {cy + 132} {cx + 96} {cy + 76} Z" fill="{GOLD}" opacity="0.92"/>
    <circle cx="{cx - 40}" cy="{cy - 34}" r="4" fill="#fff6dc" opacity="0.85"/>
    <circle cx="{cx - 8}" cy="{cy - 48}" r="4" fill="#fff6dc" opacity="0.85"/>
    <circle cx="{cx + 30}" cy="{cy - 34}" r="4" fill="#fff6dc" opacity="0.85"/>
  </g>"""


def _arches(cx: float, y: float) -> str:
    """金拱门（极简双弧），塔罗牌的「麦门」印记。"""
    return (
        f'<path d="M{cx - 46} {y} C{cx - 46} {y - 44} {cx - 16} {y - 60} {cx} {y - 20} '
        f'C{cx + 16} {y - 60} {cx + 46} {y - 44} {cx + 46} {y} Z" '
        f'fill="{GOLD}" opacity="0.95"/>'
    )


def _diamond(x: float, y: float, r: float = 6, color: str = GOLD, op: float = 0.8) -> str:
    return (f'<path d="M{x} {y - r} L{x + r} {y} L{x} {y + r} L{x - r} {y} Z" '
            f'fill="{color}" opacity="{op}"/>')


def _card_svg(card: Dict, meta: Dict) -> str:
    reversed_ = card.get("orientation") == "逆位"
    name_cn = card.get("card_cn", "")
    name_en = card.get("card_en", "")
    food = card.get("food", "")
    price = card.get("price", "")
    form_label = card.get("form_label", "")
    numeral = _numeral(card.get("card_id"))

    px, py, pw, ph = 165, 268, 420, 400          # 拱形画框
    cx = px + pw / 2

    uri = _data_uri(card.get("image", ""))
    if uri:
        art = (f'<image href="{uri}" x="{px}" y="{py}" width="{pw}" height="{ph}" '
               f'preserveAspectRatio="xMidYMid slice" clip-path="url(#arch)"/>')
    else:
        art = _placeholder_food(cx, py + ph * 0.46)

    quote_lines = _wrap(card.get("message", ""), 17, 4)
    quote = "\n".join(
        f'<text x="{W / 2}" y="{880 + i * 44}" font-size="27" fill="{CREAM}" '
        f'fill-opacity="0.9" text-anchor="middle">{_esc(line)}</text>'
        for i, line in enumerate(quote_lines)
    )

    badge_fill = RED if reversed_ else "none"
    badge_stroke = RED if reversed_ else GOLD
    badge_text = CREAM if reversed_ else GOLD

    # 有券/有立省时，在小票右上角挂一个克制的「省 ¥X」角标
    saving = card.get("saving_value") or 0
    try:
        saving_f = float(saving)
    except (TypeError, ValueError):
        saving_f = 0.0
    if saving_f >= 3:
        label = f"省 ¥{saving_f:.1f}".replace(".0", "")
        badge_w = 26 + len(label) * 13
        saving_badge = (
            f'<rect x="{W / 2 + 210 - badge_w - 10}" y="1010" width="{badge_w}" height="30" '
            f'rx="15" fill="{RED}" fill-opacity="0.9"/>'
            f'<text x="{W / 2 + 210 - badge_w / 2 - 10}" y="1031" font-size="17" fill="{CREAM}" '
            f'text-anchor="middle">{_esc(label)}</text>'
        )
    else:
        saving_badge = ""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="0.6" y2="1">
    <stop offset="0" stop-color="{BG1}"/><stop offset="1" stop-color="{BG2}"/>
  </linearGradient>
  <radialGradient id="glow" cx="0.5" cy="0.42" r="0.45">
    <stop offset="0" stop-color="{GOLD}" stop-opacity="0.20"/>
    <stop offset="1" stop-color="{GOLD}" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="vig" cx="0.5" cy="0.48" r="0.62">
    <stop offset="0.55" stop-color="#000000" stop-opacity="0"/>
    <stop offset="1" stop-color="{BG2}" stop-opacity="0.88"/>
  </radialGradient>
  <clipPath id="arch">
    <path d="M{px} {py + ph} L{px} {py + 180} A{pw / 2} {pw / 2} 0 0 1 {px + pw} {py + 180} L{px + pw} {py + ph} Z"/>
  </clipPath>
</defs>

<rect width="{W}" height="{H}" fill="url(#bg)"/>
<rect width="{W}" height="{H}" fill="url(#glow)"/>

<!-- 双层金框 -->
<rect x="26" y="26" width="{W - 52}" height="{H - 52}" rx="16" fill="none" stroke="{GOLD}" stroke-opacity="0.55" stroke-width="2"/>
<rect x="40" y="40" width="{W - 80}" height="{H - 80}" rx="10" fill="none" stroke="{GOLD_DEEP}" stroke-opacity="0.55" stroke-width="1"/>
{_diamond(W / 2, 26, 9, GOLD, 0.9)}
{_diamond(26, 150, 5, GOLD, 0.55)}
{_diamond(W - 26, 150, 5, GOLD, 0.55)}
{_diamond(26, H - 150, 5, GOLD, 0.55)}
{_diamond(W - 26, H - 150, 5, GOLD, 0.55)}
{_diamond(W / 2, H - 26, 9, GOLD, 0.9)}

<!-- 顶部：金拱门 + 品牌 -->
{_arches(W / 2, 132)}
<text x="{W / 2}" y="170" font-size="17" fill="{MUTED}" text-anchor="middle" letter-spacing="7">麦麦塔罗牌 · MCD TAROT</text>
<text x="{W / 2}" y="232" font-size="26" fill="{GOLD}" text-anchor="middle" letter-spacing="6">{numeral}</text>
<line x1="{W / 2 - 70}" y1="248" x2="{W / 2 + 70}" y2="248" stroke="{GOLD}" stroke-opacity="0.35"/>

<!-- 拱形餐品画框 -->
<path d="M{px} {py + ph} L{px} {py + 180} A{pw / 2} {pw / 2} 0 0 1 {px + pw} {py + 180} L{px + pw} {py + ph} Z"
      fill="#2a0805" stroke="{GOLD}" stroke-opacity="0.75" stroke-width="2"/>
{art}
<rect x="{px}" y="{py}" width="{pw}" height="{ph}" fill="url(#vig)" clip-path="url(#arch)"/>
<path d="M{px} {py + ph} L{px} {py + 180} A{pw / 2} {pw / 2} 0 0 1 {px + pw} {py + 180} L{px + pw} {py + ph}"
      fill="none" stroke="{GOLD}" stroke-opacity="0.55" stroke-width="1"/>

<!-- 正逆位 -->
<rect x="{W - 40 - 96}" y="{py - 4}" width="96" height="34" rx="17" fill="{badge_fill}" stroke="{badge_stroke}" stroke-opacity="0.9"/>
<text x="{W - 40 - 48}" y="{py + 19}" font-size="17" fill="{badge_text}" text-anchor="middle" letter-spacing="2">{_esc(card.get("orientation", "正位"))}</text>

<!-- 牌名 -->
<text x="{W / 2}" y="740" font-size="48" font-weight="700" fill="{CREAM}" text-anchor="middle" letter-spacing="3">{_esc(name_cn)}</text>
<text x="{W / 2}" y="778" font-size="19" fill="{MUTED}" text-anchor="middle" letter-spacing="3">{_esc(name_en)}</text>

{_diamond(W / 2 - 120, 806, 5, GOLD, 0.5)}
{_diamond(W / 2 + 120, 806, 5, GOLD, 0.5)}
<line x1="{W / 2 - 96}" y1="806" x2="{W / 2 - 16}" y2="806" stroke="{GOLD}" stroke-opacity="0.35"/>
<line x1="{W / 2 + 16}" y1="806" x2="{W / 2 + 96}" y2="806" stroke="{GOLD}" stroke-opacity="0.35"/>

<!-- 解读 -->
{quote}

<!-- 餐品小票 -->
<rect x="{W / 2 - 210}" y="1032" width="420" height="74" rx="12" fill="#000000" fill-opacity="0.18" stroke="{GOLD}" stroke-opacity="0.45"/>
<text x="{W / 2}" y="1068" font-size="19" fill="{MUTED}" text-anchor="middle" letter-spacing="3">今天麦麦请你吃</text>
<text x="{W / 2}" y="1096" font-size="25" fill="{GOLD}" text-anchor="middle">{_esc(food)}  ·  {_esc(price)}{("  ·  " + _esc(form_label)) if form_label else ""}</text>
{saving_badge}

<!-- 页脚 -->
<text x="{W / 2}" y="1140" font-size="15" fill="{MUTED}" text-anchor="middle" opacity="0.8">{_esc(meta.get("date", ""))} · 餐品与价格以麦当劳官方实时为准</text>
<text x="{W / 2}" y="1164" font-size="14" fill="{MUTED}" text-anchor="middle" opacity="0.6">塔罗仅供参考，胃口归你</text>
</svg>"""


def render(reading: Dict, out_path: str) -> str:
    """渲染一张（或多张）塔罗牌卡片，返回实际写入的路径。"""
    cards = reading.get("cards") or []
    if not cards:
        raise ValueError("没有可渲染的牌：reading 里缺少 cards")

    meta = {
        "date": reading.get("date", ""),
        "spread_name": reading.get("spread_name", ""),
        "mood": reading.get("mood") or "",
    }
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    paths: List[str] = []
    for i, card in enumerate(cards, 1):
        target = out if len(cards) == 1 else out.with_name(f"{out.stem}-{i}{out.suffix or '.svg'}")
        target.write_text(_card_svg(card, meta), encoding="utf-8")
        paths.append(str(target))

    return paths[0] if len(paths) == 1 else "、".join(paths)


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    reading = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(render(reading, sys.argv[2]))


if __name__ == "__main__":
    main()
