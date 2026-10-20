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
from datetime import date, datetime, timedelta
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

# ---------------------------------------------------------------------------
# 点餐时段：同样是「累」，早上十点和晚上十点该吃的东西不一样
# ---------------------------------------------------------------------------
PERIODS = [
    (5 * 60, 10 * 60 + 29, "breakfast", "早餐",
     "早餐时段的咖啡、奶铁常有早餐卡价，配个热的更舒服"),
    (10 * 60 + 30, 13 * 60 + 59, "lunch", "午餐",
     "午市套餐普遍比单点省十块以上，适合一次吃完整"),
    (14 * 60, 16 * 60 + 59, "afternoon", "下午茶",
     "容易犯困的时段，想吃就吃，配杯喝的慢慢回血"),
    (17 * 60, 20 * 60 + 59, "dinner", "晚餐",
     "晚餐适合把套餐吃完整，犒劳跑了一天的自己"),
    (21 * 60, 23 * 60 + 59, "night", "夜宵",
     "这个点别碰咖啡，胃会抗议"),
    (0, 4 * 60 + 59, "night", "夜宵",
     "这个点别碰咖啡，胃会抗议"),
]

# 时段 → 形态倾向：正餐推套餐，其余推轻食/单品
_PERIOD_PREFER = {
    "breakfast": "light",
    "lunch": "combo",
    "afternoon": "light",
    "dinner": "combo",
    "night": "light",
}


def period_of(now: Optional[datetime] = None) -> Dict[str, str]:
    """当前属于哪个点餐时段，以及该时段的推荐倾向。"""
    now = now or datetime.now()
    minutes = now.hour * 60 + now.minute
    for start, end, key, name, hint in PERIODS:
        if start <= minutes <= end:
            return {"key": key, "name": name, "hint": hint,
                    "prefer": _PERIOD_PREFER[key], "time": now.strftime("%H:%M")}
    return {"key": "lunch", "name": "正餐", "hint": "什么时候吃都别亏待自己",
            "prefer": "combo", "time": now.strftime("%H:%M")}


def tuned_portion(card: Dict, period: Optional[Dict[str, str]],
                  profile: Optional[Dict] = None) -> str:
    """把「牌意的份量倾向」+「时段」+「你在这个时段的实际习惯」合成推荐形态。

    有画像且该时段样本足够时，以你的真实习惯为准：
    你早餐一直点组合，就别硬推单品；你下午茶历来只买一样，也别塞套餐。
    """
    base = tarot_deck.portion_of(card)
    if not period:
        return base
    key = period["key"]
    learned = (((profile or {}).get("periods") or {}).get(key) or {}).get("top_form")
    if learned == "combo":
        return {"light": "single", "single": "combo", "combo": "combo", "share": "share"}[base]
    if learned == "single":
        return {"light": "light", "single": "single", "combo": "single", "share": "combo"}[base]
    if key in ("lunch", "dinner"):
        return {"light": "single", "single": "combo", "combo": "combo", "share": "share"}[base]
    if key in ("afternoon", "night"):
        return {"light": "light", "single": "light", "combo": "single", "share": "combo"}[base]
    return {"light": "light", "single": "single", "combo": "single", "share": "combo"}[base]


_FORM_CN = {"combo": "套餐", "single": "单品", "share": "分享装", "light": "轻食"}


def _portion_note(card: Dict, item: Dict, period: Optional[Dict[str, str]],
                  profile: Optional[Dict] = None) -> str:
    """一句话解释「为什么给你配了这个形态」。

    关键：形态和牌面不一致时（牌面偏套餐、实际给单品），不能再说「牌面偏套餐」，
    否则一行里前后自相矛盾；此时要把「为什么调」说清楚。
    """
    base = tarot_deck.portion_of(card)
    label = tarot_deck.PORTION_LABEL.get(base, "单品")
    form = item.get("form") or ("combo" if "套餐" in str(item.get("name")) else "single")
    form_cn = _FORM_CN.get(form, "单品")
    pname = period["name"] if period else ""
    key = (period or {}).get("key")
    learned = (((profile or {}).get("periods") or {}).get(key) or {}).get("top_form")

    heavy_base = base in ("combo", "share")
    heavy_form = form in ("combo", "share")

    if heavy_base == heavy_form:
        # 形态与牌面一致：解释牌面本身
        if heavy_form:
            if learned == "combo":
                return f"牌面偏「{label}」，你{pname}一向点套餐，这样最顺手"
            if key in ("lunch", "dinner"):
                return f"牌面偏「{label}」，{pname}配套餐更划算"
            return f"牌面偏「{label}」，这份套餐配得齐、不用再凑"
        if learned == "single":
            return f"牌面偏「{label}」，你{pname}一向点单品，这样最顺手"
        if key in ("afternoon", "night"):
            return f"牌面偏「{label}」，{pname}点单品刚好"
        if key == "breakfast":
            return f"牌面偏「{label}」，早上吃轻一点，一整天都舒服"
        return f"牌面偏「{label}」，单品就是今天的分寸"

    # 形态与牌面不一致：说清是按什么调的
    if learned in ("combo", "single") and form == learned:
        habit = "套餐" if learned == "combo" else "单品"
        return f"牌面偏「{label}」，但你在{pname}习惯点{habit}，就按你的惯性来"
    if key in ("afternoon", "night"):
        return f"牌面偏「{label}」，{pname}换成{form_cn}更合节奏"
    if key in ("lunch", "dinner"):
        return f"牌面偏「{label}」，{pname}吃{form_cn}更对路"
    return f"牌面偏「{label}」，今天用{form_cn}接着"


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
    at: Optional[str] = None,
    profile: Optional[Dict] = None,
) -> Dict:
    """生成一次完整解读，返回含 markdown 的字典。

    menu: 直接注入菜单（[{"name","price","code","category"}, ...]，通常由
    mcd-mcp 连接器的 query-meals 返回经 menu_from_connector.py 归一化而来）；
    为 None 时按原有逻辑走 get_menu(token)（有 Token 直连 / 无 Token 回退静态菜单）。
    at: 指定点餐时间 "YYYY-MM-DD HH:MM"（默认现在），用于按时段调整推荐。
    profile: 口味画像（profile.py 构建）；给出时会在牌意范围内优先你爱吃的、
    并提示可用优惠券。为 None 时自动读本地画像，读不到就只按牌意推荐。
    """
    if at:
        now = datetime.strptime(at, "%Y-%m-%d %H:%M")
    else:
        now = datetime.now()
    date_str = date_str or now.date().isoformat()
    period = period_of(now)
    spread_name = SPREADS[spread_key][0]
    if menu is None:
        menu = get_menu(token)
    if profile is None:
        try:
            import profile as profile_mod
            profile = profile_mod.load_profile()
        except Exception:  # noqa: BLE001 - 画像是增强项，坏了不影响解读
            profile = None
    is_fallback = menu is mcp_client.FALLBACK_MENU
    drawn = draw(spread_key, date_str)

    cards_block: List[Dict] = []
    lines: List[str] = [_mood_opening(mood, spread_name)]
    lines.append(f"> ⏰ 现在是{period['name']}（{period['time']}）：{period['hint']}。\n")
    used_foods: set = set()
    total_saving = 0.0
    saving_lines: List[str] = []

    for idx, (card, orientation, position) in enumerate(drawn, 1):
        prefer = tuned_portion(card, period, profile)
        item = resolve_item(card, menu, exclude=used_foods, prefer_form=prefer,
                            profile=profile, period=period)
        name = item.get("name", card.get("mcd_category", "麦麦餐品"))
        used_foods.add(str(name))
        price = _fmt_price(item.get("price"))
        price_text = f"（{price}）" if price else ""
        note = _portion_note(card, item, period, profile)
        form = item.get("form") or "single"
        form_label = {"combo": "套餐", "share": "分享装", "light": "轻食", "single": "单品"}.get(form, "单品")
        orig = item.get("original_price")
        saving_text = ""
        card_saving = 0.0
        if orig is not None and item.get("price") is not None:
            try:
                diff = float(orig) - float(item["price"])
                if diff >= 0.5:
                    saving_text = f"原价 ¥{_fmt_price(orig)[1:]}，立省 ¥{_fmt_price(diff)[1:]}"
                    total_saving += diff
                    card_saving += diff
            except (TypeError, ValueError):
                saving_text = ""

        # 券：只在这道菜真能用、且真更便宜时才说
        deal = item.get("deal") or None
        deal_text = ""
        if deal:
            more = "再" if saving_text else ""
            if deal.get("free"):
                deal_text = f"卡包里有「{deal['title']}」0 元券，这道直接免单（{more}省 ¥{_fmt_price(deal['saving'])[1:]}）"
            elif deal.get("bogo"):
                deal_text = f"有「{deal['title']}」，两件相当于{more}省 ¥{_fmt_price(deal['saving'])[1:]}"
            else:
                deal_text = (f"用「{deal['title']}」后 ¥{_fmt_price(deal['price'])[1:]}，"
                             f"{more}省 ¥{_fmt_price(deal['saving'])[1:]}")
            total_saving += float(deal.get("saving") or 0)
            card_saving += float(deal.get("saving") or 0)

        pref_why = item.get("affinity_why") or ""

        # 同类里更像你平时会点的备选（只在更合口味 / 有券更省时才出现）
        alt = mcp_client.alternative_for(card, item, menu, profile,
                                         exclude=used_foods, prefer_form=prefer, period=period)
        alt_text = ""
        if alt:
            alt_price = _fmt_price(alt.get("price"))
            bits = [f"**{alt['name']}**{(' ' + alt_price) if alt_price else ''}"]
            alt_deal = alt.get("deal")
            if alt_deal:
                bits.append(f"用券后 ¥{_fmt_price(alt_deal['price'])[1:]}，省 ¥{_fmt_price(alt_deal['saving'])[1:]}")
            if alt.get("why"):
                bits.append(alt["why"])
            alt_text = "，".join(bits)

        meaning = card["reversed"] if orientation == "rev" else card["upright"]
        emotion = card["emotion_rev"] if orientation == "rev" else card["emotion_up"]
        ori_tag = "逆位" if orientation == "rev" else "正位"

        lines.append(f"\n## {position}\n")
        lines.append(f"**{card['name_cn']} · {card['name_en']}**（{ori_tag}）")
        lines.append(f"- 塔罗意涵：{meaning}")
        lines.append(f"- 🍔 麦麦指引：**{name}**{price_text}")
        lines.append(f"- 🍱 形态：{form_label} · {note}")
        if pref_why:
            lines.append(f"- 🧠 合你口味：{pref_why}")
        if saving_text:
            lines.append(f"- 💰 更划算：{saving_text}")
        if deal_text:
            lines.append(f"- 🎟 用券：{deal_text}")
        if alt_text:
            lines.append(f"- 🔁 或者更像你：{alt_text}")
        lines.append(f"- 💛 给你的话：{emotion}")

        if saving_text or deal_text:
            bits = [b for b in (saving_text, deal_text) if b]
            saving_lines.append(f"- {name}：{'；'.join(bits)}")

        cards_block.append({
            "position": position,
            "card_id": card["id"],
            "card_cn": card["name_cn"],
            "card_en": card["name_en"],
            "orientation": ori_tag,
            "meaning": meaning,
            "food": name,
            "food_code": item.get("code"),
            "price": price,
            "price_raw": item.get("price"),
            "original_price": orig,
            "image": item.get("image") or "",
            "form": form,
            "form_label": form_label,
            "portion": prefer,
            "portion_note": note,
            "saving": saving_text,
            "saving_value": round(card_saving, 1),
            "deal": deal_text,
            "alternative": alt_text,
            "affinity": item.get("affinity") or 0,
            "affinity_why": pref_why,
            "message": emotion,
        })

    # 省钱小结：把所有能省的钱收个口
    combo_note = mcp_client.combo_coupon_note(profile, period)
    claim_note = mcp_client.claimable_hint(profile)
    if saving_lines or claim_note:
        lines.append("\n---\n")
        lines.append("## 🧾 今天这样买更省\n")
        lines.extend(saving_lines)
        if total_saving >= 0.5:
            lines.append(f"\n**合计可省约 ¥{_fmt_price(total_saving)[1:]}**（券以结算页实际可用为准）")
        if claim_note:
            lines.append(f"> {claim_note}")
        if combo_note:
            lines.append(f"> {combo_note}")

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
    lines.append(
        "\n💡 想直接吃这一份？回「就它」，我可以帮你核对实时价格并下单，"
        "付款链接由你自己打开付款。"
    )

    markdown = "\n".join(lines)
    return {
        "spread": spread_key,
        "spread_name": spread_name,
        "date": date_str,
        "mood": mood,
        "period": period,
        "menu_source": "fallback" if is_fallback else "real(mcd-mcp)",
        "profile_used": bool(profile),
        "total_saving": round(total_saving, 1),
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
    profile: Optional[Dict] = None,
) -> Dict:
    """本周餐单：周一至周日各一张牌、一道菜，尽量不重样。

    start_date 为本周任意一天（默认今天），自动对齐到本周周一。
    """
    base_day = date.fromisoformat(start_date) if start_date else date.today()
    monday = base_day - timedelta(days=base_day.weekday())

    if menu is None:
        menu = get_menu(token)
    if profile is None:
        try:
            import profile as profile_mod
            profile = profile_mod.load_profile()
        except Exception:  # noqa: BLE001
            profile = None
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
        item = resolve_item(card, menu, exclude=used_foods, profile=profile)
        name = str(item.get("name"))
        used_foods.add(name)
        price = _fmt_price(item.get("price"))
        deal = item.get("deal") or None
        price_cell = f"**{name}**{' ' + price if price else ''}"
        if deal:
            price_cell += f" 🎟省¥{_fmt_price(deal['saving'])[1:]}"
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
        "profile_used": bool(profile),
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
    ap.add_argument("--at", default=None,
                    help='指定点餐时间 "YYYY-MM-DD HH:MM"（默认现在），用于按时段调整推荐')
    ap.add_argument("--token-env", default="MCD_MCP_TOKEN", help="读取真实菜单的 Token 环境变量名")
    ap.add_argument("--menu-file", default=None,
                    help="从 JSON 文件加载菜单（[{name, price, code, category}, ...]），"
                         "可由 mcd-mcp 连接器 query-meals 结果经 menu_from_connector.py 归一化生成")
    ap.add_argument("--no-cache", action="store_true", help="不使用本地门店/菜单缓存")
    ap.add_argument("--json", dest="json_out", default=None, help="把解读结果写成 JSON 文件")
    ap.add_argument("--card-svg", default=None, help="生成塔罗牌面卡片（SVG 路径）")
    ap.add_argument("--profile-file", default=None, help="口味画像 JSON（默认读 ~/.cache/mcd-tarot/profile.json）")
    ap.add_argument("--no-profile", action="store_true", help="不使用口味画像，只按牌意推荐")
    args = ap.parse_args()

    token = os.environ.get(args.token_env) if args.token_env else None
    profile = False if args.no_profile else None
    if profile is None:
        if args.profile_file:
            try:
                with open(args.profile_file, encoding="utf-8") as f:
                    profile = json.load(f)
            except (OSError, json.JSONDecodeError) as exc:
                print(f"[warn] 画像文件读取失败，忽略：{exc}")
                profile = False
        else:
            try:
                import profile as profile_mod
                profile = profile_mod.load_profile()
            except Exception:  # noqa: BLE001
                profile = None
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
        result = do_week_reading(args.date, args.mood, token, menu=menu, profile=profile)
    else:
        result = do_reading(args.spread, args.date, args.mood, token, menu=menu,
                            at=args.at, profile=profile)

    print(result["markdown"])
    print(f"\n[菜单来源] {result['menu_source']}　[口味画像] {'已使用' if result.get('profile_used') else '未使用'}")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
        print(f"[JSON] {args.json_out}")

    if args.card_svg:
        import tarot_card
        path = tarot_card.render(result, args.card_svg)
        print(f"[卡片] {path}")


if __name__ == "__main__":
    main()
