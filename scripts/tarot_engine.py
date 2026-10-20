"""麦麦塔罗牌 · 塔罗引擎。

把 78 张塔罗牌与麦当劳餐盘连接：按「日期」做确定性抽签（同一天结果稳定），
每次只抽**一张牌**、只出**一张图**——专为「一张图预测」场景设计。
可选传入 question（你关心的问题），牌会作为这个问题的回答，且不同问题抽到不同牌。

用法
----
    python tarot_engine.py                       # 今日一张（今日宜吃）
    python tarot_engine.py --mood "有点累"
    python tarot_engine.py --question "明天面试能顺利吗"
    python tarot_engine.py --menu-file menu.json   # 注入 mcd-mcp 连接器真实菜单

作为库：
    from tarot_engine import do_reading
    result = do_reading()                        # 今日一张，返回含 markdown 的 dict
    result = do_reading(question="明天面试能顺利吗")
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
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tarot_deck
import mcp_client
import combo_detail
import tarot_sense
from mcp_client import get_menu, resolve_item

# 牌阵定义：本技能只做「单张预测」一种场景。
# key -> (中文名, 单张位置标签)
SPREADS: Dict[str, Tuple[str, List[str]]] = {
    "today": ("今日宜吃", ["今天，宇宙建议你吃"]),
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
                  profile: Optional[Dict] = None, combo_first: bool = True) -> str:
    """把「牌意的份量倾向」+「时段」+「你在这个时段的实际习惯」合成推荐形态。

    有画像且该时段样本足够时，以你的真实习惯为准：
    你早餐一直点组合，就别硬推单品；你下午茶历来只买一样，也别塞套餐。

    combo_first：默认把形态往套餐方向推（套餐更完整、也更容易吃到立减和满减券）。
    真正是否给套餐还要看菜单里有没有对应套餐（由 combo_option 决定），
    这里只负责「愿望」，不凭空捏造。
    """
    base = tarot_deck.portion_of(card)
    if not period:
        return base
    key = period["key"]
    pinfo = ((profile or {}).get("periods") or {}).get(key) or {}
    learned = pinfo.get("top_form")
    count = int(pinfo.get("count") or 0)

    # 1 笔订单还称不上「习惯」，别拿它压过牌意
    if learned == "combo" and count >= 2:
        return {"light": "combo" if combo_first else "single", "single": "combo",
                "combo": "combo", "share": "share"}[base]
    if learned == "single" and count >= 5 and not combo_first:
        return {"light": "light", "single": "single", "combo": "single", "share": "combo"}[base]
    if key in ("lunch", "dinner"):
        return {"light": "single", "single": "combo", "combo": "combo", "share": "share"}[base]
    if key in ("afternoon", "night"):
        return {"light": "combo" if combo_first else "light",
                "single": "combo" if combo_first else "light",
                "combo": "combo", "share": "combo"}[base]
    return {"light": "combo" if combo_first else "light",
            "single": "single" if not combo_first else "combo",
            "combo": "combo", "share": "combo"}[base]


def _worth_combo(item: Dict, card: Dict, period: Optional[Dict[str, str]],
                 profile: Optional[Dict] = None) -> bool:
    """这个套餐值不值得把牌面的「轻」升级成「整套」。

    夜宵/下午茶碰上本身就清简的牌（隐士、节制这类），
    如果套餐既没券也没立减，就保持轻盈——需求是「多给套餐」，不是「硬塞套餐」。
    """
    base = tarot_deck.portion_of(card)
    key = (period or {}).get("key")
    if base != "light" or key not in ("afternoon", "night"):
        return True
    if mcp_client.deal_for(item, profile, period):
        return True
    return mcp_client.discount_ratio(item) >= 0.08


_FORM_CN = {"combo": "套餐", "single": "单品", "share": "分享装", "light": "轻食"}


def _portion_note(card: Dict, item: Dict, period: Optional[Dict[str, str]],
                  profile: Optional[Dict] = None, upgraded: bool = False) -> str:
    """一句话解释「为什么给你配了这个形态」。

    关键：形态和牌面不一致时（牌面偏套餐、实际给单品），不能再说「牌面偏套餐」，
    否则一行里前后自相矛盾；此时要把「为什么调」说清楚。
    """
    base = tarot_deck.portion_of(card)
    label = tarot_deck.PORTION_LABEL.get(base, "单品")
    # 菜单没写 form 字段时按名字判断（与 do_reading 保持一致），别让文案自相矛盾
    form = item.get("form") or mcp_client._form(item)
    form_cn = _FORM_CN.get(form, "单品")
    pname = period["name"] if period else ""
    key = (period or {}).get("key")
    learned = (((profile or {}).get("periods") or {}).get(key) or {}).get("top_form")

    if upgraded and form in ("combo", "share"):
        if item.get("deal"):
            return f"牌面偏「{label}」，不过这份套餐能用券、也吃得更完整，就给你配齐"
        if mcp_client.discount_ratio(item) > 0:
            return f"牌面偏「{label}」，这份套餐自带立减，比单点划算"
        return f"牌面偏「{label}」，{pname}配套餐更完整，不用再一样样凑" if pname \
            else f"牌面偏「{label}」，套餐配得齐，省得一样样凑"

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


_PERIOD_CLOSER = {
    "breakfast": "热的东西先下肚，这一天就立得住了。",
    "lunch": "吃饱了，下午才扛得住。",
    "afternoon": "慢一点吃，下午还长着呢。",
    "dinner": "把这一顿吃完整，今天就算交代过去了。",
    "night": "吃完就收工，剩下的留给明天。",
}
_CLOSERS = [
    "趁热吃，别等它凉。",
    "一口一口来，不用赶。",
    "今天这点甜头，是你自己给自己的。",
    "别分心，这一口是专门给你的。",
    "吃完了再上，路还长。",
]
# 冷饮不说「趁热」，换个说法
_CLOSERS_COLD = [
    "趁冰的时候喝，风味最好。",
    "慢慢啜，别一口闷。",
    "这口凉的，正好给你降降温。",
]
_COLD_WORDS = ("可乐", "雪碧", "怡泉", "咖啡", "奶铁", "美式", "拿铁", "麦旋风",
               "新地", "派", "果汁", "茶", "牛奶", "可可", "冰")


def _closer(card: Dict, period: Optional[Dict[str, str]], idx: int = 0,
            item: Optional[Dict] = None) -> str:
    """解读落点句：优先用时段的语境，冷饮不说「趁热」，同一局内尽量不重样。"""
    key = (period or {}).get("key")
    nm = str((item or {}).get("name", ""))
    cat = str((item or {}).get("category", ""))
    cold = any(w in nm or w in cat for w in _COLD_WORDS)
    pool = ([_PERIOD_CLOSER[key]] if key in _PERIOD_CLOSER else []) + \
        (_CLOSERS_COLD if cold else _CLOSERS)
    return pool[(int(card["id"]) + idx) % len(pool)]


def daily_seed(date_str: str) -> int:
    """把日期字符串映射成稳定整数种子，保证同一天抽签结果一致。"""
    h = hashlib.sha256(date_str.encode("utf-8")).hexdigest()
    return int(h[:16], 16)


def _draw_one(rng: random.Random) -> Tuple[Dict, str]:
    card = rng.choice(tarot_deck.ALL_CARDS)
    orientation = "rev" if rng.random() < REVERSED_CHANCE else "up"
    return card, orientation


def draw(spread_key: str = "today", date_str: str = "", salt: str = "",
         reversed_chance: float = REVERSED_CHANCE):
    """抽**一张**牌，返回 [(card, orientation, position)]（固定一张）。

    salt 用于区分不同问题 / 场景：同日期、同 salt 可复现；换 salt（如不同问题）
    会抽到不同的牌，让「一张图预测」能服务任意提问而不总是同一张。
    """
    if spread_key not in SPREADS:
        raise ValueError(f"未知牌阵: {spread_key}，可选: {list(SPREADS)}")
    _, positions = SPREADS[spread_key]
    base = f"{date_str}|{salt or spread_key}"
    rng = random.Random(daily_seed(base))
    rng_reversed = random.Random(daily_seed(base + ":rev"))
    card = rng.choice(tarot_deck.ALL_CARDS)
    orientation = "rev" if rng_reversed.random() < reversed_chance else "up"
    return [(card, orientation, positions[0])]


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


def _mood_opening(mood: Optional[str], spread_name: str, question: Optional[str] = None) -> str:
    base = f"# 🔮 麦麦塔罗牌 · {spread_name}\n"
    if question:
        q = question.strip()
        if mood:
            base += f"\n> 你问：「{q}」\n> 你今天的心情是：「{mood}」。塔罗翻开一张牌，给你一个回答。\n"
        else:
            base += f"\n> 你问：「{q}」\n> 塔罗翻开一张牌，给你一个回答。\n"
    else:
        if mood:
            base += f"\n> 你今天的心情是：「{mood}」。塔罗听见了，下面是为你抽出的牌。\n"
        else:
            base += "\n> 把今天的疲惫交给牌面，看看麦麦想请你吃点什么。\n"
    return base


def _norm_question(q: str) -> str:
    """把问题归一化（去空白/标点/大小写），让同一个问题的签文稳定可复现。"""
    return re.sub(r"\s+", "", q.strip().lower())


def do_reading(
    spread_key: str = "today",
    date_str: Optional[str] = None,
    mood: Optional[str] = None,
    token: Optional[str] = None,
    menu: Optional[List[Dict]] = None,
    at: Optional[str] = None,
    profile: Optional[Dict] = None,
    combo_first: bool = True,
    lean: bool = False,
    question: Optional[str] = None,
) -> Dict:
    """生成一次完整解读，返回含 markdown 的字典。

    lean=True 时走「图在前、文在后」的精简文本：餐品清单/形态/价格都在牌面图里，
    文字只留牌名、意涵、细腻解读与一句行动引导，不重复罗列。

    menu: 直接注入菜单（[{"name","price","code","category"}, ...]，通常由
    mcd-mcp 连接器的 query-meals 返回经 menu_from_connector.py 归一化而来）；
    为 None 时按原有逻辑走 get_menu(token)（有 Token 直连 / 无 Token 回退静态菜单）。
    at: 指定点餐时间 "YYYY-MM-DD HH:MM"（默认现在），用于按时段调整推荐。
    profile: 口味画像（profile.py 构建）；给出时会在牌意范围内优先你爱吃的、
    并提示可用优惠券。为 None 时自动读本地画像，读不到就只按牌意推荐。
    combo_first: 默认偏向套餐——套餐更完整、更容易吃到立减和满减券；
    只有当菜单里真有对应套餐、且套餐有一定优惠（或有立减）时才升级。
    """
    if at:
        now = datetime.strptime(at, "%Y-%m-%d %H:%M")
    else:
        now = datetime.now()
    date_str = date_str or now.date().isoformat()
    period = period_of(now)

    # 单张预测场景：有 question 时，牌作为这个问题的回答，且按问题做种子（不同问题→不同牌）
    if question:
        salt = "ask|" + _norm_question(question)
        spread_name = "塔罗预测"
        position_label = "牌对你的回答"
    else:
        salt = spread_key
        spread_name = SPREADS[spread_key][0]
        position_label = SPREADS[spread_key][1][0]

    if menu is None:
        menu = get_menu(token)
    if profile is None:
        try:
            import profile as profile_mod
            profile = profile_mod.load_profile()
        except Exception:  # noqa: BLE001 - 画像是增强项，坏了不影响解读
            profile = None
    is_fallback = menu is mcp_client.FALLBACK_MENU
    drawn = draw(spread_key, date_str, salt=salt)
    # 位置标签随「今日/提问」切换
    drawn = [(card, orientation, position_label) for card, orientation, _ in drawn]

    cards_block: List[Dict] = []
    lines: List[str] = [_mood_opening(mood, spread_name, question=question)]
    if not lean:
        lines.append(f"> ⏰ 现在是{period['name']}（{period['time']}）：{period['hint']}。\n")
    used_foods: set = set()
    total_saving = 0.0
    saving_lines: List[str] = []

    for idx, (card, orientation, position) in enumerate(drawn, 1):
        prefer = tuned_portion(card, period, profile, combo_first=combo_first)
        # 套餐优先：菜单里真有对应套餐、且这顿套餐值得，就把形态升级成套餐
        combo_up = None
        if combo_first:
            cand = mcp_client.combo_option(card, menu, exclude=used_foods,
                                           profile=profile, period=period)
            if cand and _worth_combo(cand, card, period, profile):
                combo_up = cand
                prefer = "combo"
        item = resolve_item(card, menu, exclude=used_foods, prefer_form=prefer,
                            profile=profile, period=period)
        # 关键词池里没有套餐、但同品类里有更划算的套餐 → 用套餐接管
        if combo_up and mcp_client._form(item) not in ("combo", "share"):
            item = mcp_client.finalize_item(combo_up, profile, period, match="combo-upgrade")
        # 牌面本来是轻/单、最后给了套餐 → 这是「套餐优先」调的，文案要交代理由
        upgraded = (mcp_client._form(item) in ("combo", "share")
                    and tarot_deck.portion_of(card) in ("light", "single"))
        name = item.get("name", card.get("mcd_category", "麦麦餐品"))
        used_foods.add(str(name))
        price = _fmt_price(item.get("price"))
        price_text = f"（{price}）" if price else ""
        note = _portion_note(card, item, period, profile, upgraded=upgraded)
        # 菜单没写 form（内置示例菜单）时按名字判断，别把套餐当成单品
        form = item.get("form") or mcp_client._form(item)
        form_label = {"combo": "套餐", "share": "分享装", "light": "轻食", "single": "单品"}.get(form, "单品")
        orig = item.get("original_price")
        # 套餐要把里面装了什么写清楚：光看「三件套」不知道自己点了啥
        detail = combo_detail.describe(item, menu) if form in ("combo", "share") else None
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
            kind = deal.get("kind")
            if deal.get("free"):
                deal_text = f"卡包里有「{deal['title']}」0 元券，这道直接免单（{more}省 ¥{_fmt_price(deal['saving'])[1:]}）"
            elif deal.get("bogo"):
                deal_text = f"有「{deal['title']}」，两件相当于{more}省 ¥{_fmt_price(deal['saving'])[1:]}"
            elif kind == "threshold":
                # 满减券能和套餐立减叠着用，这是套餐最实在的地方
                deal_text = (f"再叠满减「{deal['title']}」，{more}省 ¥{_fmt_price(deal['saving'])[1:]}，"
                             f"到手约 ¥{_fmt_price(deal['price'])[1:]}")
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
        fine = tarot_sense.lines_for(card, orientation)
        closer = _closer(card, period, idx, item=item)

        lines.append(f"\n## {position}\n")
        lines.append(f"**{card['name_cn']} · {card['name_en']}**（{ori_tag}）")
        if lean:
            # 图在前文在后：清单、形态、价格都在牌面图里，文字不重复
            lines.append(f"> 塔罗意涵：{meaning}")
            if fine:
                lines.append("")
                first = fine[0]
                if not first.endswith(("。", "！", "？", "…")):
                    first += "。"
                lines.append(first)
                lines.extend(fine[1:])
            lines.append(f"\n牌把它落在 **{name}** 上{f' · {price}' if price else ''}——{closer}")
        else:
            lines.append(f"- 塔罗意涵：{meaning}")
            lines.append(f"- 🍔 麦麦指引：**{name}**{price_text}")
            if detail:
                lines.append(f"  - 📦 这一份里有：{detail['text']}（{detail['note']}）")
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
            "combo_items": (detail or {}).get("items") or [],
            "combo_detail": (detail or {}).get("text") or "",
            "combo_detail_source": (detail or {}).get("source") or "",
            "combo_detail_note": (detail or {}).get("note") or "",
            "portion": prefer,
            "portion_note": note,
            "saving": saving_text,
            "saving_value": round(card_saving, 1),
            "deal": deal_text,
            "deal_kind": (deal or {}).get("kind") or "",
            "combo_upgraded": upgraded,
            "alternative": alt_text,
            "affinity": item.get("affinity") or 0,
            "affinity_why": pref_why,
            "message": emotion,
            "sense": fine[0] if fine else "",
            "whisper": fine[1] if len(fine) > 1 else "",
            "closer": closer,
        })

    # 省钱小结：把所有能省的钱收个口（lean 模式只留图里那一张小票，不再复述）
    combo_note = mcp_client.combo_coupon_note(profile, period)
    claim_note = mcp_client.claimable_hint(profile)
    if lean:
        # 精简收尾：重心全部压在下一步操作上
        lines.append("\n---\n")
        lines.append("👉 回「**就它**」，我帮你核对实时价格并下单——付款链接你自己打开，钱我不碰。")
        lines.append("\n*餐品供应与价格以麦当劳官方实时为准。*")
    else:
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
        "question": question,
        "date": date_str,
        "mood": mood,
        "period": period,
        "menu_source": "fallback" if is_fallback else "real(mcd-mcp)",
        "profile_used": bool(profile),
        "total_saving": round(total_saving, 1),
        "cards": cards_block,
        "markdown": markdown,
    }


def _menu_source_label(token: Optional[str], menu) -> str:
    return "真实菜单(mcd-mcp)" if not (menu is mcp_client.FALLBACK_MENU) else "静态示例菜单"


def main() -> None:
    ap = argparse.ArgumentParser(description="麦麦塔罗牌塔罗引擎（单张预测）")
    ap.add_argument("--spread", choices=list(SPREADS), default="today",
                    help="牌阵（当前仅支持单张预测 today）")
    ap.add_argument("--question", default=None,
                    help="你关心的问题；给出时牌作为这个问题的回答，不同问题抽到不同牌")
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
    ap.add_argument("--card-svg", default=None,
                    help="生成塔罗牌面卡片（SVG 路径；单张牌面）")
    ap.add_argument("--inline", default=None,
                    help="渲染可内联到对话框的牌面 SVG（宽 680，单张）。"
                         "写文件给路径；要直接打 stdout 就传 -")
    ap.add_argument("--lean", action="store_true",
                    help="精简文字：清单/形态/价格交给牌面图，文字只留解读与行动引导")
    ap.add_argument("--profile-file", default=None, help="口味画像 JSON（默认读 ~/.cache/mcd-tarot/profile.json）")
    ap.add_argument("--no-profile", action="store_true", help="不使用口味画像，只按牌意推荐")
    ap.add_argument("--single-only", action="store_true",
                    help="关掉套餐优先（默认优先给套餐，套餐更容易吃到立减与满减券）")
    args = ap.parse_args()
    combo_first = not args.single_only

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

    result = do_reading(args.spread, args.date, args.mood, token, menu=menu,
                        at=args.at, profile=profile, combo_first=combo_first,
                        lean=args.lean, question=args.question)

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

    if args.inline:
        import tarot_card
        svg = tarot_card.render_inline(result)
        if args.inline == "-":
            print(svg)
        else:
            Path(args.inline).write_text(svg, encoding="utf-8")
            print(f"[内联卡片] {args.inline}")


if __name__ == "__main__":
    main()
