"""麦麦塔罗牌 · 塔罗牌面卡片（SVG，无第三方依赖）。

这一版把输出做成一张**真正的塔罗牌**，而不是「带图的信息卡」：

- 深靛夜空 + 旧金双线框 + 四角鸢尾，拱形画窗（教堂窗式构图）
- 主画面把一份汉堡画成**圣像**：穹顶面包、生菜披风、张臂托法器、头顶金拱门光环
- 大阿卡纳各有自己的法器与天空（愚者的太阳、女祭司的双柱与月、正义的天平与刀、
  世界的花环……）；小阿卡纳按张数把薯条/可乐/餐刀/汉堡币串成一道半圆光环
- 逆位时圣像整体倒置，并打红色逆位徽章——跟真塔罗一样
- 保留小票区（餐品、价格、形态、省额），但它退到画面下方，不抢主画面

餐品照片默认**不再贴进画框**（那会毁掉塔罗感）；需要时用 `--photo`
在底部小票旁加一枚圆形餐品章。

用法
----
    python3 scripts/tarot_engine.py --spread today --card-svg card.svg
    python3 scripts/tarot_engine.py --spread trinity --card-svg cards.svg   # 会生成 3 张
    python3 scripts/tarot_card.py reading.json card.svg --photo
    python3 scripts/tarot_card.py reading.json card.png --png              # 需要 Chrome
"""

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

import tarot_art as A

W, H = 750, 1200
FONT = ("'Songti SC','STSong','Noto Serif CJK SC','Source Han Serif SC',"
        "'PingFang SC',serif")
FONT_SANS = "'PingFang SC','Hiragino Sans GB','Noto Sans CJK SC',sans-serif"

GOLD = A.GOLD
GOLD_DEEP = A.GOLD_DEEP
CREAM = A.CREAM
MUTED = "#b79a72"
RED = A.RED
NIGHT = A.NIGHT
NIGHT_DEEP = A.NIGHT_DEEP

IMG_CACHE = Path.home() / ".cache" / "mcd-tarot" / "img"

_ROMAN = ["0", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
          "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX", "XXI"]
_RANK_ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
               "XI", "XII", "XIII", "XIV"]

# 画窗
ART_X, ART_Y, ART_W, ART_H = 76, 176, 598, 556
ART_CX = ART_X + ART_W / 2

# 小票
TICKET_Y = 1028


def _esc(s: object) -> str:
    return A.esc(s)


def _numeral(card_id: Optional[int]) -> str:
    if card_id is None:
        return "0"
    if card_id >= 22:
        return _RANK_ROMAN[(card_id - 22) % 14]
    return _ROMAN[max(0, min(21, int(card_id)))]


def _wrap(text: str, width: int = 17, max_lines: int = 3) -> List[str]:
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
# 餐品照片（可选，只在 --photo 时下载并内嵌）
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
            with urllib.request.urlopen(req, timeout=8) as resp:
                path.write_bytes(resp.read())
        except Exception:  # noqa: BLE001 - 图挂了不该让整张卡失败
            return None
    try:
        mime = "image/gif" if ext == ".gif" else "image/png"
        return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"
    except OSError:
        return None


# ---------------------------------------------------------------------------
# 画窗内容
# ---------------------------------------------------------------------------
def _sky(card_id: int) -> str:
    """天空元素：大阿卡纳按牌配太阳/月亮，小阿卡纳按花色配。"""
    if card_id < 22:
        kind = (A.MAJOR_ART.get(card_id) or {}).get("sky")
    else:
        suit, _ = A.suit_rank_of(card_id)
        kind = {"wands": "sun", "cups": "moon", "swords": None, "pentacles": "sun"}.get(suit or "")
    if kind == "sun":
        return A.sun(ART_X + ART_W - 116, ART_Y + 170, 1.0)
    if kind == "moon":
        return A.moon(ART_X + ART_W - 112, ART_Y + 160, 1.0)
    return ""


def _idol(card_id: int, reversed_: bool) -> str:
    """主画面：汉堡圣像 + 法器 + 底座。逆位时整组倒置。"""
    if card_id < 22:
        cfg = A.MAJOR_ART.get(card_id) or {}
        halo = cfg.get("halo", "arch")
        cape = cfg.get("cape", True)
        crown = cfg.get("crown", False)
        base = cfg.get("base", "cloud")
        arms = True
        idol_w = 186
        idol_cy = ART_Y + 316
        sym_y = ART_Y + 330
        sym_dx = 236
        left, right = cfg.get("left"), cfg.get("right")
    else:
        suit, n = A.suit_rank_of(card_id)
        halo, cape, crown, base = "ring", True, n >= 11, "cloud"
        arms = n >= 11
        idol_w = 166
        idol_cy = ART_Y + 356
        sym_y = ART_Y + 340
        sym_dx = 240
        left = right = None

    body = A.burger_idol(ART_CX, idol_cy, idol_w, halo=halo, arms=arms, cape=cape,
                         crown=crown, base=None, seed=card_id or 0)
    pedestal = A._pedestal(ART_CX, idol_cy + idol_w * 0.62, idol_w, base)

    if reversed_:
        # 只倒置圣像（含光环与法器），底座与天空不动
        body = f'<g transform="rotate(180 {ART_CX} {idol_cy})">{body}</g>'

    parts = [body, pedestal]

    if card_id >= 22:
        suit, n = A.suit_rank_of(card_id)
        parts.append(A.pips_arc(suit, n, ART_CX, idol_cy + idol_w * 0.10,
                                r=204, seed=card_id))
    else:
        cfg = A.MAJOR_ART.get(card_id) or {}
        sym_s = 1.0 if idol_w > 160 else 0.95
        if left:
            parts.append(f'<g opacity="0.92">{A.draw_symbol(left, ART_CX - sym_dx, sym_y, sym_s)}</g>')
        if right:
            parts.append(f'<g opacity="0.92">{A.draw_symbol(right, ART_CX + sym_dx, sym_y, sym_s)}</g>')
        for i, extra in enumerate(cfg.get("extra") or []):
            x = ART_CX + (-1) ** i * (sym_dx - 46)
            parts.append(f'<g opacity="0.66">{A.draw_symbol(extra, x, sym_y + 132, 0.62)}</g>')
    return "".join(parts)


def _arch_path() -> str:
    """教堂窗式拱形：两肩为半圆，底部平直。"""
    r = round(ART_W / 2)
    y_shoulder = round(ART_Y + r)
    return (f"M{ART_X} {ART_Y + ART_H} L{ART_X} {y_shoulder} "
            f"A{r} {r} 0 0 1 {ART_X + ART_W} {y_shoulder} "
            f"L{ART_X + ART_W} {ART_Y + ART_H} Z")


def _corner_flourish(x: float, y: float, sx: int, sy: int) -> str:
    """四角鸢尾：塔罗牌框角上的经典装饰。"""
    return (
        f'<g transform="translate({x} {y}) scale({sx} {sy})" opacity="0.62">'
        f'<path d="M0 0 C14 2 24 12 26 26" fill="none" stroke="{GOLD}" stroke-width="1.6"/>'
        f'<path d="M0 0 C4 12 12 20 24 24" fill="none" stroke="{GOLD}" stroke-width="1"/>'
        f'<path d="M13 13 L17 9 L21 13 L17 17 Z" fill="{GOLD}" opacity="0.8"/>'
        f'<circle cx="26" cy="26" r="2" fill="{GOLD}"/>'
        f'</g>'
    )


def _card_svg(card: Dict, meta: Dict, photo: bool = False) -> str:
    reversed_ = card.get("orientation") == "逆位"
    card_id = card.get("card_id")
    try:
        card_id = int(card_id) if card_id is not None else 0
    except (TypeError, ValueError):
        card_id = 0

    name_cn = card.get("card_cn", "")
    name_en = card.get("card_en", "")
    food = card.get("food", "")
    price = card.get("price", "")
    form_label = card.get("form_label", "")
    numeral = _numeral(card_id)

    quote_lines = _wrap(card.get("message", ""), 16, 3)
    quote = "".join(
        f'<text x="{W / 2}" y="{896 + i * 40}" font-size="25" fill="{CREAM}" '
        f'fill-opacity="0.88" text-anchor="middle" letter-spacing="0.5">{_esc(line)}</text>'
        for i, line in enumerate(quote_lines)
    )

    badge_fill = RED if reversed_ else "none"
    badge_stroke = RED if reversed_ else GOLD
    badge_text = CREAM if reversed_ else GOLD

    saving = card.get("saving_value") or 0
    try:
        saving_f = float(saving)
    except (TypeError, ValueError):
        saving_f = 0.0
    saving_badge = ""
    if saving_f >= 3:
        label = f"省 ¥{saving_f:.1f}".replace(".0", "")
        bw = 26 + len(label) * 13
        saving_badge = (
            f'<rect x="{W / 2 + 216 - bw}" y="{TICKET_Y - 30}" width="{bw}" height="26" '
            f'rx="13" fill="{RED}" fill-opacity="0.9"/>'
            f'<text x="{W / 2 + 216 - bw / 2}" y="{TICKET_Y - 12}" font-size="15" '
            f'fill="{CREAM}" text-anchor="middle">{_esc(label)}</text>'
        )

    # 套餐在小票上补一行「里面装了什么」：光看「三件套」不知道点了啥
    detail = str(card.get("combo_detail") or "")
    detail_line = ""
    if detail:
        if len(detail) > 30:
            detail = detail[:29] + "…"
        detail_line = (
            f'<text x="{W / 2}" y="{TICKET_Y + 78}" font-size="12.5" fill="{MUTED}" '
            f'fill-opacity="0.85" text-anchor="middle" font-family="{FONT_SANS}">'
            f'内有 {_esc(detail)}</text>'
        )

    # 小票左侧：可选的餐品照片章（默认不出现，保持塔罗感）
    medallion = ""
    if photo:
        uri = _data_uri(card.get("image", ""))
        if uri:
            mx = W / 2 - 186
            my = TICKET_Y + 60
            medallion = (
                f'<clipPath id="med"><circle cx="{mx}" cy="{my}" r="30"/></clipPath>'
                f'<image href="{uri}" x="{mx - 30}" y="{my - 30}" width="60" height="60" '
                f'preserveAspectRatio="xMidYMid slice" clip-path="url(#med)"/>'
                f'<circle cx="{mx}" cy="{my}" r="30" fill="none" stroke="{GOLD}" '
                f'stroke-opacity="0.6" stroke-width="1.2"/>'
            )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
  <linearGradient id="night" x1="0.1" y1="0" x2="0.7" y2="1">
    <stop offset="0" stop-color="{NIGHT}"/><stop offset="0.55" stop-color="#080a1e"/>
    <stop offset="1" stop-color="{NIGHT_DEEP}"/>
  </linearGradient>
  <linearGradient id="artsky" x1="0" y1="0" x2="0.3" y2="1">
    <stop offset="0" stop-color="#161b44"/><stop offset="0.6" stop-color="#0c1030"/>
    <stop offset="1" stop-color="#06071a"/>
  </linearGradient>
  <linearGradient id="goldbar" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{GOLD_DEEP}"/><stop offset="0.5" stop-color="{GOLD}"/>
    <stop offset="1" stop-color="{GOLD_DEEP}"/>
  </linearGradient>
  <radialGradient id="halo" cx="0.5" cy="0.45" r="0.55">
    <stop offset="0" stop-color="{GOLD}" stop-opacity="0.16"/>
    <stop offset="1" stop-color="{GOLD}" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="vig" cx="0.5" cy="0.46" r="0.66">
    <stop offset="0.5" stop-color="#000000" stop-opacity="0"/>
    <stop offset="1" stop-color="#04050f" stop-opacity="0.9"/>
  </radialGradient>
  <mask id="archMask" maskUnits="userSpaceOnUse">
    <path d="{_arch_path()}" fill="#ffffff"/>
  </mask>
</defs>

<rect width="{W}" height="{H}" fill="url(#night)"/>
<rect width="{W}" height="{H}" fill="url(#halo)"/>

<!-- 双线框 + 四角鸢尾 -->
<rect x="24" y="24" width="{W - 48}" height="{H - 48}" rx="6" fill="none"
      stroke="{GOLD}" stroke-opacity="0.55" stroke-width="2.2"/>
<rect x="36" y="36" width="{W - 72}" height="{H - 72}" rx="3" fill="none"
      stroke="{GOLD_DEEP}" stroke-opacity="0.5" stroke-width="1"/>
{_corner_flourish(52, 52, 1, 1)}
{_corner_flourish(W - 52, 52, -1, 1)}
{_corner_flourish(52, H - 52, 1, -1)}
{_corner_flourish(W - 52, H - 52, -1, -1)}

<!-- 牌冠：金拱门 + 编号 -->
{A.arches(W / 2, 92, 64)}
<text x="{W / 2}" y="120" font-size="13" fill="{MUTED}" text-anchor="middle"
      letter-spacing="6" font-family="{FONT_SANS}">MCD TAROT</text>
<text x="{W / 2}" y="162" font-size="27" fill="{GOLD}" text-anchor="middle"
      letter-spacing="7" font-family="{FONT}">{numeral}</text>

<!-- 拱形画窗 -->
<path d="{_arch_path()}" fill="url(#artsky)"/>
<g mask="url(#archMask)">
  {A.stars(ART_CX, ART_Y + 250, ART_W * 0.92, ART_H * 0.86, n=52, seed=card_id + 3)}
  {_sky(card_id)}
  {_idol(card_id, reversed_)}
  <rect x="{ART_X}" y="{ART_Y}" width="{ART_W}" height="{ART_H}" fill="url(#vig)"/>
</g>
<path d="{_arch_path()}" fill="none" stroke="{GOLD}" stroke-opacity="0.8" stroke-width="2.2"/>
<path d="{_arch_path()}" fill="none" stroke="{GOLD}" stroke-opacity="0.3" stroke-width="6"
      transform="translate(0 0)"/>

<!-- 正逆位徽章 -->
<rect x="{W - 40 - 100}" y="{ART_Y - 16}" width="100" height="34" rx="17"
      fill="{badge_fill}" stroke="{badge_stroke}" stroke-opacity="0.9"/>
<text x="{W - 40 - 50}" y="{ART_Y + 7}" font-size="16" fill="{badge_text}"
      text-anchor="middle" letter-spacing="2" font-family="{FONT_SANS}">{_esc(card.get("orientation", "正位"))}</text>

<!-- 牌名 -->
<text x="{W / 2}" y="772" font-size="46" font-weight="700" fill="{CREAM}"
      text-anchor="middle" letter-spacing="4" font-family="{FONT}">{_esc(name_cn)}</text>
<text x="{W / 2}" y="812" font-size="16" fill="{MUTED}" text-anchor="middle"
      letter-spacing="4" font-family="{FONT_SANS}">{_esc(name_en).upper()}</text>
<line x1="{W / 2 - 92}" y1="838" x2="{W / 2 + 92}" y2="838" stroke="url(#goldbar)"
      stroke-opacity="0.7"/>
{A._diamond(W / 2 - 108, 838, 4.2, GOLD, 0.7)}
{A._diamond(W / 2 + 108, 838, 4.2, GOLD, 0.7)}

<!-- 意涵 -->
{quote}

<!-- 小票 -->
<rect x="{W / 2 - 216}" y="{TICKET_Y}" width="432" height="{96 if detail_line else 86}" rx="4" fill="#000000"
      fill-opacity="0.28" stroke="{GOLD}" stroke-opacity="0.38"/>
<text x="{W / 2}" y="{TICKET_Y + 28}" font-size="13" fill="{MUTED}" text-anchor="middle"
      letter-spacing="5" font-family="{FONT_SANS}">今天麦麦请你吃</text>
<text x="{W / 2}" y="{TICKET_Y + 58}" font-size="24" fill="{GOLD}" text-anchor="middle"
      font-family="{FONT}">{_esc(food)}  ·  {_esc(price)}{("  ·  " + _esc(form_label)) if form_label else ""}</text>
{detail_line}
{saving_badge}
{medallion}

<!-- 页脚 -->
<text x="{W / 2}" y="1152" font-size="13" fill="{MUTED}" text-anchor="middle"
      opacity="0.7" font-family="{FONT_SANS}">{_esc(meta.get("date", ""))} · 餐品与价格以麦当劳官方实时为准 · 塔罗仅供参考</text>
</svg>"""


def render(reading: Dict, out_path: str, photo: bool = False) -> str:
    """渲染一张（或多张）塔罗牌，返回实际写入的路径。"""
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
        target.write_text(_card_svg(card, meta, photo=photo), encoding="utf-8")
        paths.append(str(target))

    return paths[0] if len(paths) == 1 else "、".join(paths)


def render_png(reading: Dict, out_png: str, photo: bool = False, width: int = 750) -> str:
    """用本机 Chrome 无头模式把牌面渲染成 PNG（可选，慢约 1–2 秒）。

    没装 Chrome 时抛 RuntimeError，调用方可以只用 SVG。
    """
    import shutil
    import tempfile

    chrome = None
    for cand in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                 "/Applications/Chromium.app/Contents/MacOS/Chromium",
                 shutil.which("google-chrome"), shutil.which("chromium")):
        if cand and Path(cand).exists():
            chrome = cand
            break
    if not chrome:
        raise RuntimeError("没找到 Chrome/Chromium，无法渲染 PNG；SVG 已经可以正常预览")

    out = Path(out_png)
    svg_path = str(out.with_suffix(".svg"))
    render(reading, svg_path, photo=photo)
    height = int(width * H / W)
    tmp = Path(tempfile.mkdtemp()) / "card.png"
    subprocess.run(
        [chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
         f"--force-device-scale-factor=2", f"--window-size={width},{height}",
         f"--screenshot={tmp}", f"file://{Path(svg_path).resolve()}"],
        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if not tmp.exists():
        raise RuntimeError("Chrome 渲染失败，请直接使用 SVG")
    out.write_bytes(tmp.read_bytes())
    return str(out)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if len(args) != 2:
        print(__doc__)
        sys.exit(2)
    reading = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    if "--png" in flags:
        print(render_png(reading, args[1], photo="--photo" in flags))
    else:
        print(render(reading, args[1], photo="--photo" in flags))


if __name__ == "__main__":
    main()
