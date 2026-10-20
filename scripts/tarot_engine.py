"""麦麦塔罗牌 · 塔罗引擎。

把 78 张塔罗牌与麦当劳餐盘连接：按「日期」做确定性抽签（同一天结果稳定），
支持多种牌阵与正/逆位，把每张牌映射到真实麦当劳单品，并产出温暖的情绪化解读。

用法
----
    python tarot_engine.py --spread today
    python tarot_engine.py --spread timeline --mood "有点累"
    python tarot_engine.py --spread trinity --date 2026-10-16
    python tarot_engine.py --spread today --menu-file menu.json   # 注入 mcd-mcp 连接器真实菜单

作为库：
    from tarot_engine import do_reading
    result = do_reading("today")          # 返回含 markdown 的 dict
    print(result["markdown"])
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
from datetime import date, timedelta
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
    "choice": (
        "三选一 · 三道菜，你挑一个",
        ["选项 A", "选项 B", "选项 C"],
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
    # 同一牌阵内不放回发牌，更接近真实牌阵（原实现可能抽到重复牌）
    cards = rng.sample(tarot_deck.ALL_CARDS, len(positions))
    out = []
    for card, pos in zip(cards, positions):
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
    menu: Optional[List[Dict]] = None,
) -> Dict:
    """生成一次完整解读，返回含 markdown 的字典。

    menu: 直接注入菜单（[{"name","price","code","category"}, ...]，通常由
    mcd-mcp 连接器的 query-meals 返回经 menu_from_connector.py 归一化而来）；
    为 None 时按原有逻辑走 get_menu(token)（有 Token 直连 / 无 Token 回退静态菜单）。
    """
    date_str = date_str or date.today().isoformat()
    spread_name = SPREADS[spread_key][0]
    if menu is None:
        menu = get_menu(token)
    is_fallback = menu is mcp_client.FALLBACK_MENU
    drawn = draw(spread_key, date_str)

    cards_block: List[Dict] = []
    lines: List[str] = [_mood_opening(mood, spread_name)]
    used_foods: set = set()

    for idx, (card, orientation, position) in enumerate(drawn, 1):
        item = resolve_item(card, menu, exclude=used_foods)
        name = item.get("name", card.get("mcd_category", "麦麦餐品"))
        used_foods.add(str(name))
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

    # 三选一：把选择权交还用户
    if spread_key == "choice":
        lines.append("\n---\n")
        lines.append(
            "三道菜都是今天可以吃的，牌只是在帮你排序。"
            "跟着第一眼心动的那一个走——通常那就是你真正想要的。"
        )

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


WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _short_message(text: str, limit: int = 22) -> str:
    """取情绪寄语的第一句，作为周餐单里的一行短句。"""
    first = re.split(r"[。；;\n]", (text or "").strip())[0].strip()
    return first if len(first) <= limit else first[:limit] + "…"


def do_week_reading(
    start_date: Optional[str] = None,
    mood: Optional[str] = None,
    token: Optional[str] = None,
    menu: Optional[List[Dict]] = None,
) -> Dict:
    """本周餐单：周一至周日各一张牌、一道菜，尽量不重样。

    start_date 为本周任意一天（默认今天），自动对齐到本周周一。
    """
    base_day = date.fromisoformat(start_date) if start_date else date.today()
    monday = base_day - timedelta(days=base_day.weekday())

    if menu is None:
        menu = get_menu(token)
    is_fallback = menu is mcp_client.FALLBACK_MENU

    lines: List[str] = ["# 🗓 麦麦塔罗牌 · 本周餐单\n"]
    if mood:
        lines.append(f"> 这周的心情底色：「{mood}」。先把吃饭安排好，别的事慢慢来。\n")
    else:
        lines.append("> 一周七天，先替你把「吃什么」想好。牌是参考，胃口归你。\n")
    lines.append("| 日期 | 牌（正/逆） | 麦麦指引 | 一句话 |")
    lines.append("|---|---|---|---|")

    used_foods: set = set()
    days: List[Dict] = []
    for i in range(7):
        d = monday + timedelta(days=i)
        d_str = d.isoformat()
        card, orientation, _pos = draw("today", d_str)[0]
        item = resolve_item(card, menu, exclude=used_foods)
        name = str(item.get("name"))
        used_foods.add(name)
        price = _fmt_price(item.get("price"))
        message = card["emotion_rev"] if orientation == "rev" else card["emotion_up"]
        ori = "逆位" if orientation == "rev" else "正位"
        lines.append(
            f"| {d.strftime('%m-%d')} {WEEKDAYS[i]} | {card['name_cn']} · {ori} | "
            f"**{name}**{' ' + price if price else ''} | {_short_message(message)} |"
        )
        days.append({
            "date": d_str,
            "weekday": WEEKDAYS[i],
            "card_cn": card["name_cn"],
            "card_en": card["name_en"],
            "orientation": ori,
            "food": name,
            "price": price,
            "message": message,
        })

    lines.append("\n---\n")
    lines.append(
        "不用每顿都吃对，能按时吃上就已经很好。"
        "餐品供应与价格以麦当劳官方实时为准，想换某一天就重抽那一张。🥤"
    )

    return {
        "mode": "week",
        "spread": "week",
        "spread_name": f"本周餐单（{monday.isoformat()} 起）",
        "date": monday.isoformat(),
        "mood": mood,
        "menu_source": "fallback" if is_fallback else "real(mcd-mcp)",
        "days": days,
        "cards": [],
        "markdown": "\n".join(lines),
    }


def _menu_source_label(token: Optional[str], menu) -> str:
    return "真实菜单(mcd-mcp)" if not (menu is mcp_client.FALLBACK_MENU) else "静态示例菜单"


def main() -> None:
    ap = argparse.ArgumentParser(description="麦麦塔罗牌塔罗引擎")
    ap.add_argument("--spread", choices=list(SPREADS), default="today", help="牌阵")
    ap.add_argument("--week", action="store_true", help="输出本周餐单（周一至周日）")
    ap.add_argument("--mood", default=None, help="今天的心情（可选，用于个性化开场）")
    ap.add_argument("--date", default=None, help="指定日期 YYYY-MM-DD（默认今天）")
    ap.add_argument("--token-env", default="MCD_MCP_TOKEN", help="读取真实菜单的 Token 环境变量名")
    ap.add_argument("--menu-file", default=None,
                    help="从 JSON 文件加载菜单（[{name, price, code, category}, ...]），"
                         "可由 mcd-mcp 连接器 query-meals 结果经 menu_from_connector.py 归一化生成")
    ap.add_argument("--no-cache", action="store_true", help="不使用本地门店/菜单缓存")
    ap.add_argument("--json", dest="json_out", default=None, help="把解读结果写成 JSON 文件")
    ap.add_argument("--card-svg", default=None, help="额外生成一张可分享卡片（SVG 路径）")
    args = ap.parse_args()

    token = os.environ.get(args.token_env) if args.token_env else None
    menu = None
    if args.menu_file:
        with open(args.menu_file, encoding="utf-8") as f:
            menu = json.load(f)
    elif not args.no_cache:
        # 缓存优先：上次门店 + 当天菜单，命中就免去重复调用连接器
        try:
            import cache as cache_mod
            store = cache_mod.load_store()
            if store:
                menu = cache_mod.load_menu(store["store_code"], args.date)
        except Exception:  # noqa: BLE001 - 缓存只是优化，坏了不影响解读
            menu = None

    if args.week:
        result = do_week_reading(args.date, args.mood, token, menu=menu)
    else:
        result = do_reading(args.spread, args.date, args.mood, token, menu=menu)

    print(result["markdown"])
    print(f"\n[菜单来源] {result['menu_source']}")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
        print(f"[JSON] {args.json_out}")

    if args.card_svg:
        import card_svg
        path = card_svg.render(result, args.card_svg)
        print(f"[卡片] {path}")


if __name__ == "__main__":
    main()
