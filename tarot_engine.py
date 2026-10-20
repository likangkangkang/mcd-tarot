"""麦麦塔罗牌 · 塔罗引擎。

把 78 张塔罗牌与麦当劳餐盘连接：按「日期」做确定性抽签（同一天结果稳定），
支持多种牌阵与正/逆位，把每张牌映射到真实麦当劳单品，并产出温暖的情绪化解读。

用法
----
    python tarot_engine.py --spread today
    python tarot_engine.py --spread timeline --mood "有点累"
    python tarot_engine.py --spread trinity --date 2026-10-16

作为库：
    from tarot_engine import do_reading
    result = do_reading("today")          # 返回含 markdown 的 dict
    print(result["markdown"])
"""

from __future__ import annotations

import argparse
import hashlib
import os
import random
from datetime import date
from typing import Dict, List, Optional, Tuple

import tarot_deck
import mcp_client
from mcp_client import get_menu, resolve_item

# 牌阵定义：key -> (中文名, 位置标签列表)
SPREADS: Dict[str, Tuple[str, List[str]]] = {
    "today": ("今日宜吃", ["今天，宇宙建议你吃"]),
    "timeline": (
        "过去 · 现在 · 未来",
        ["过去 · 你带着什么走来", "现在 · 你正需要什么", "未来 · 你将被怎样治愈"],
    ),
    "trinity": (
        "身 · 心 · 灵 三餐",
        ["给身体的一口（落地与能量）", "给心灵的一口（情绪与温柔）", "给关系的一口（连接与分享）"],
    ),
}

REVERSED_CHANCE = 0.3  # 逆位概率


def daily_seed(date_str: str) -> int:
    """把日期字符串映射成稳定整数种子，保证同一天抽签结果一致。"""
    h = hashlib.sha256(date_str.encode("utf-8")).hexdigest()
    return int(h[:16], 16)


def _draw_one(rng: random.Random) -> Tuple[Dict, str]:
    card = rng.choice(tarot_deck.ALL_CARDS)
    orientation = "rev" if rng.random() < REVERSED_CHANCE else "up"
    return card, orientation


def draw(spread_key: str, date_str: str, reversed_chance: float = REVERSED_CHANCE):
    """返回 [(card, orientation, position), ...]；同日可复现。"""
    if spread_key not in SPREADS:
        raise ValueError(f"未知牌阵: {spread_key}，可选: {list(SPREADS)}")
    _, positions = SPREADS[spread_key]
    base = f"{date_str}|{spread_key}"
    rng = random.Random(daily_seed(base))
    rng_reversed = random.Random(daily_seed(base + ":rev"))
    out = []
    for pos in positions:
        card = rng.choice(tarot_deck.ALL_CARDS)
        orientation = "rev" if rng_reversed.random() < reversed_chance else "up"
        out.append((card, orientation, pos))
    return out


def _fmt_price(price) -> str:
    if price is None:
        return ""
    try:
        p = float(price)
    except (TypeError, ValueError):
        return ""
    if p == int(p):
        return f"¥{int(p)}"
    return f"¥{p:.1f}"


def _mood_opening(mood: Optional[str], spread_name: str) -> str:
    base = f"# 🔮 麦麦塔罗牌 · {spread_name}\n"
    if mood:
        base += f"\n> 你今天的心情是：「{mood}」。塔罗听见了，下面是为你抽出的牌。\n"
    else:
        base += "\n> 把今天的疲惫交给牌面，看看麦麦想请你吃点什么。\n"
    return base


def do_reading(
    spread_key: str = "today",
    date_str: Optional[str] = None,
    mood: Optional[str] = None,
    token: Optional[str] = None,
) -> Dict:
    """生成一次完整解读，返回含 markdown 的字典。"""
    date_str = date_str or date.today().isoformat()
    spread_name = SPREADS[spread_key][0]
    menu = get_menu(token)
    is_fallback = menu is mcp_client.FALLBACK_MENU
    drawn = draw(spread_key, date_str)

    cards_block: List[Dict] = []
    lines: List[str] = [_mood_opening(mood, spread_name)]

    for idx, (card, orientation, position) in enumerate(drawn, 1):
        item = resolve_item(card, menu)
        name = item.get("name", card.get("mcd_category", "麦麦餐品"))
        price = _fmt_price(item.get("price"))
        price_text = f"（{price}）" if price else ""

        meaning = card["reversed"] if orientation == "rev" else card["upright"]
        emotion = card["emotion_rev"] if orientation == "rev" else card["emotion_up"]
        ori_tag = "逆位" if orientation == "rev" else "正位"

        lines.append(f"\n## {position}\n")
        lines.append(f"**{card['name_cn']} · {card['name_en']}**（{ori_tag}）")
        lines.append(f"- 塔罗意涵：{meaning}")
        lines.append(f"- 🍔 麦麦指引：**{name}**{price_text}")
        lines.append(f"- 💛 给你的话：{emotion}")

        cards_block.append({
            "position": position,
            "card_cn": card["name_cn"],
            "card_en": card["name_en"],
            "orientation": ori_tag,
            "meaning": meaning,
            "food": name,
            "price": price,
            "message": emotion,
        })

    # 结尾情绪寄语
    lines.append("\n---\n")
    lines.append(
        "无论今天过得怎样，好好吃一顿，是你对自己最朴素的温柔。"
        "以上由麦麦塔罗牌生成，餐品供应与价格以麦当劳官方实时为准。🥤"
    )

    markdown = "\n".join(lines)
    return {
        "spread": spread_key,
        "spread_name": spread_name,
        "date": date_str,
        "mood": mood,
        "menu_source": "fallback" if is_fallback else "real(mcd-mcp)",
        "cards": cards_block,
        "markdown": markdown,
    }


def _menu_source_label(token: Optional[str], menu) -> str:
    return "真实菜单(mcd-mcp)" if not (menu is mcp_client.FALLBACK_MENU) else "静态示例菜单"


def main() -> None:
    ap = argparse.ArgumentParser(description="麦麦塔罗牌塔罗引擎")
    ap.add_argument("--spread", choices=list(SPREADS), default="today", help="牌阵")
    ap.add_argument("--mood", default=None, help="今天的心情（可选，用于个性化开场）")
    ap.add_argument("--date", default=None, help="指定日期 YYYY-MM-DD（默认今天）")
    ap.add_argument("--token-env", default="MCD_MCP_TOKEN", help="读取真实菜单的 Token 环境变量名")
    args = ap.parse_args()

    token = os.environ.get(args.token_env) if args.token_env else None
    result = do_reading(args.spread, args.date, args.mood, token)
    print(result["markdown"])
    print(f"\n[菜单来源] {result['menu_source']}")


if __name__ == "__main__":
    main()
