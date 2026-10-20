"""麦麦塔罗牌 · 口味画像与优惠索引。

把 mcd-mcp 连接器里能拿到的「跟你有关」的数据，压成一份推荐用的画像：

- 历史订单 → 常点什么、偏好哪类食材、各时段客单价、常去门店
- 卡包券   → 手上已经有的券（含 ¥0 免单券）
- 可领券   → 现在能领的券（免费薯饼、特价汉堡等）
- 积分账户 → 可用积分（只做提示，不参与排序）

画像存在 `~/.cache/mcd-tarot/profile.json`，抽牌时引擎自动读取，
用来在「牌意允许的范围」内，优先推荐你爱吃的、以及有券更划算的那道。

用法
----
    # 四个入参都是连接器返回原样保存的文件（JSON 或 markdown 文本均可）
    python3 scripts/profile.py build \
        --orders    orders.json \
        --wallet    coupons.md \
        --available available.md \
        --account   account.json

    python3 scripts/profile.py show      # 看画像摘要
    python3 scripts/profile.py clear     # 清掉（下次重新学）

设计原则
--------
1. 画像只影响「多选一」时的排序，不推翻牌意：牌指向什么品类，就还是什么品类。
2. 券只在真正更便宜时才提示，不做「为了用券而改推荐」。
3. 全部本地计算，画像文件不上传、不进 git。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CACHE_DIR = Path(os.environ.get("MCD_TAROT_CACHE", Path.home() / ".cache" / "mcd-tarot"))
PROFILE_PATH = CACHE_DIR / "profile.json"

# 食材/品类偏好词表：命中越多，说明越爱吃这一类
TRAITS: Dict[str, List[str]] = {
    "chicken": ["鸡", "板烧", "麦乐鸡", "麦辣鸡翅", "鸡块", "鸡腿"],
    "beef": ["牛", "巨无霸", "吉士", "安格斯"],
    "pork": ["猪", "猪柳", "培根", "肉骨"],
    "fish": ["鱼", "三文鱼", "虾", "鳕"],
    "cheese": ["芝士", "吉士", "马苏里拉"],
    "potato": ["薯条", "薯饼", "薯"],
    "coffee": ["咖啡", "美式", "拿铁", "奶铁", "麦咖啡"],
    "spicy": ["辣", "麻辣", "花椒", "韩式", "椒"],
    "dessert": ["麦旋风", "甜筒", "冰淇淋", "派", "蛋糕", "圣代"],
    "drink": ["可乐", "汁", "茶", "豆浆", "柠", "雪碧", "芬达"],
    "breakfast": ["早餐", "麦满分", "炒双蛋", "脆薯饼", "豆浆", "粥"],
    "veg": ["玉米", "沙拉", "苹果", "蔬菜"],
}

# 券标题里的噪音词，去掉后剩下的才是「这张券管什么」
_COUPON_NOISE = [
    "优惠券", "麦麦省", "人气", "王牌", "超值", "限时", "新品", "特价",
    "元", "免费", "买一送一", "第二份半价", "任选", "折扣", "立减",
    "中杯", "大杯", "小杯", "单人", "双人", "套餐", "™", "®", "券",
]
_COUPON_COMBO = ("任选", "套餐", "双人", "分享", "组合", "桶")

# 这些不是「想吃什么」的信号
_CONDIMENT = ("酱", "蘸", "调料", "餐具", "纸巾", "吸管", "袋")


def _load_raw(path: str) -> Any:
    """读入连接器返回：JSON 优先，否则当纯文本（连接器有时直接回 markdown）。"""
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    stripped = text.strip()
    if stripped[:1] in "{[":
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass
    return text


def _as_list(payload: Any, *keys: str) -> List[Dict[str, Any]]:
    """从可能的信封结构里掏出列表。"""
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in keys:
            val = payload.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
        data = payload.get("data")
        if isinstance(data, dict):
            return _as_list(data, *keys)
    return []


# ---------------------------------------------------------------------------
# 历史订单 → 口味
# ---------------------------------------------------------------------------
def _parse_orders(payload: Any) -> Dict[str, Any]:
    orders = _as_list(payload, "list", "orders", "orderList")
    if not orders:
        return {"orders_analyzed": 0}

    item_weight: Dict[str, Dict[str, Any]] = {}
    trait_score: Dict[str, float] = {k: 0.0 for k in TRAITS}
    cat_score: Dict[str, float] = {}
    period_stats: Dict[str, List[float]] = {}
    period_form: Dict[str, Dict[str, int]] = {}
    hours: Dict[str, List[int]] = {}
    stores: Dict[str, Dict[str, Any]] = {}
    spends: List[float] = []

    for order in orders:
        ts = str(order.get("createTime") or "")
        hour = None
        m = re.match(r"\d{4}-\d{2}-\d{2}\s+(\d{2}):", ts)
        if m:
            hour = int(m.group(1))
        period = _period_key(hour)

        amount = order.get("realTotalAmount")
        try:
            amount_f = float(amount)
        except (TypeError, ValueError):
            amount_f = 0.0
        # 0 元订单多是兑换/赠品，不计入客单价，但仍能反映口味
        if amount_f > 0:
            spends.append(amount_f)
            period_stats.setdefault(period, []).append(amount_f)
        if hour is not None:
            hours.setdefault(period, []).append(hour)

        store_code = str(order.get("storeCode") or "")
        if store_code:
            s = stores.setdefault(store_code, {"store_code": store_code,
                                              "store_name": order.get("storeName") or "",
                                              "count": 0})
            s["count"] += 1

        for prod in order.get("orderProductList") or []:
            if not isinstance(prod, dict):
                continue
            pname = str(prod.get("productName") or "")
            # 这个时段他习惯点套餐还是单品？——决定推荐形态，而不是只看时间
            if pname:
                forms = period_form.setdefault(period, {"combo": 0, "single": 0})
                forms["combo" if _is_combo(pname) else "single"] += 1
            # 主商品权重 1.0，套餐子项 0.5（子项也代表口味，但信号弱一些）
            _tally(pname, 1.0, item_weight, trait_score, cat_score,
                   amount_f)
            for sub in prod.get("comboItemList") or []:
                if isinstance(sub, dict):
                    _tally(str(sub.get("name") or ""), 0.5, item_weight, trait_score, cat_score,
                           amount_f)

    # 归一化口味强度：最常吃的那类记 1.0
    peak = max(trait_score.values()) or 1.0
    traits = {k: round(v / peak, 3) for k, v in trait_score.items() if v > 0}

    favorites = sorted(
        ({"name": k, **v} for k, v in item_weight.items()),
        key=lambda x: (-x["weight"], -x["count"], x["name"]),
    )

    spend_stats = {}
    if spends:
        s = sorted(spends)
        spend_stats = {
            "min": round(s[0], 1),
            "p25": round(_pct(s, 0.25), 1),
            "median": round(_pct(s, 0.5), 1),
            "p75": round(_pct(s, 0.75), 1),
            "max": round(s[-1], 1),
            "avg": round(sum(s) / len(s), 1),
        }

    return {
        "orders_analyzed": len(orders),
        "favorites": [
            {"name": f["name"], "count": f["count"], "weight": round(f["weight"], 1)}
            for f in favorites[:12]
        ],
        "traits": traits,
        "top_traits": sorted(traits, key=lambda k: -traits[k])[:4],
        "categories": dict(sorted(cat_score.items(), key=lambda kv: -kv[1])[:8]),
        "periods": {
            k: {"count": len(v), "avg_spend": round(sum(v) / len(v), 1),
                "usual_hour": _mode_int(hours.get(k, [])),
                "top_form": _top_form(period_form.get(k))}
            for k, v in period_stats.items()
        },
        "spend": spend_stats,
        "stores": sorted(stores.values(), key=lambda s: -s["count"])[:5],
    }


def _tally(name: str, weight: float, item_weight, trait_score, cat_score, amount: float = 0.0) -> None:
    name = name.strip()
    if not name:
        return
    # 酱料/蘸料/餐具不算「爱吃什么」，会污染口味画像
    if any(w in name for w in _CONDIMENT):
        return
    rec = item_weight.setdefault(name, {"count": 0, "weight": 0.0, "amount": 0.0})
    rec["count"] += 1
    rec["weight"] += weight
    rec["amount"] += amount
    if _is_combo(name):
        cat_score["套餐"] = cat_score.get("套餐", 0.0) + weight
    for trait, words in TRAITS.items():
        if any(w in name for w in words):
            trait_score[trait] += weight


def _is_combo(name: str) -> bool:
    return any(w in name for w in ("套餐", "组合", "三件套", "四件套", "分享", "随心配", "双人"))


def _period_key(hour: Optional[int]) -> str:
    if hour is None:
        return "unknown"
    if 5 <= hour <= 10:
        return "breakfast"
    if 11 <= hour <= 13:
        return "lunch"
    if 14 <= hour <= 16:
        return "afternoon"
    if 17 <= hour <= 20:
        return "dinner"
    return "night"


def _pct(sorted_vals: List[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, max(0, int(round(q * (len(sorted_vals) - 1)))))
    return sorted_vals[idx]


def _mode_int(vals: List[int]) -> Optional[int]:
    if not vals:
        return None
    return max(set(vals), key=vals.count)


def _top_form(forms: Optional[Dict[str, int]]) -> Optional[str]:
    """这个时段主要点套餐还是单品；样本太少（<2）就不下结论。"""
    if not forms:
        return None
    total = forms.get("combo", 0) + forms.get("single", 0)
    if total < 2:
        return None
    return "combo" if forms.get("combo", 0) > forms.get("single", 0) else "single"


# ---------------------------------------------------------------------------
# 券包 / 可领券 → 优惠索引
# ---------------------------------------------------------------------------
def _parse_coupons(payload: Any, source: str) -> List[Dict[str, Any]]:
    """兼容两种形态：结构化 JSON，或连接器直接回的 markdown。"""
    if isinstance(payload, (dict, list)):
        rows = _as_list(payload, "list", "coupons", "data")
        out = []
        for row in rows:
            title = str(row.get("title") or row.get("couponName") or row.get("name") or "")
            if title:
                out.append(_coupon_from_title(title, row.get("price"), source))
        return out

    text = str(payload)
    out: List[Dict[str, Any]] = []
    # markdown 形态：`- 优惠券标题：xxx` 或 `## xxx`
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^[-*]?\s*优惠券标题[：:]\s*(.+)$", line)
        if m:
            out.append(_coupon_from_title(m.group(1), None, source))
            continue
        if line.startswith("## "):
            out.append(_coupon_from_title(line[3:], None, source))
    # 券包 markdown 里价格单独一行：`**优惠**: ¥0 (用券价格)`
    if out:
        current = 0
        for line in text.splitlines():
            if line.strip().startswith("## "):
                current += 1
                continue
            m = re.search(r"\*\*优惠\*\*[：:]\s*¥\s*(\d+(?:\.\d+)?)", line)
            if m and 0 < current <= len(out):
                out[current - 1]["price"] = float(m.group(1))
    return [c for c in out if c["title"]]


def _coupon_from_title(title: str, price: Any, source: str) -> Dict[str, Any]:
    # 连接器有时会在行尾带 "\" 和空格，先清掉
    title = title.strip().strip("\\").strip()
    core = title
    for word in _COUPON_NOISE:
        core = core.replace(word, "")
    core = re.sub(r"[\d.]+", "", core).strip(" -·+")
    if core == "":
        core = title

    bogo = "买一送一" in title
    combo = any(w in title for w in _COUPON_COMBO)
    if price is None:
        m = re.search(r"(\d+(?:\.\d+)?)\s*元", title)
        if m:
            price = float(m.group(1))
        elif "免费" in title or "0元" in title:
            price = 0.0
    try:
        price_f = float(price) if price is not None else None
    except (TypeError, ValueError):
        price_f = None

    return {
        "title": title,
        "core": core,
        "price": price_f,
        "bogo": bogo,
        "combo": combo,
        "source": source,          # wallet=已有券，claimable=可领
        "keywords": _coupon_keywords(core),
    }


def _coupon_keywords(core: str) -> List[str]:
    """从券名里切出用于匹配菜单的关键词（整串 + 去品牌前缀后的核心词）。"""
    words = {core}
    for seg in re.split(r"[+＋/、·（( ）)]", core):
        seg = seg.strip()
        if len(seg) >= 2:
            words.add(seg)
    # 「麦咖啡奶铁」这种带品牌的，额外留一个「奶铁」，好匹配「燕麦奶铁」
    for brand in ("麦咖啡", "麦乐", "麦麦"):
        if core.startswith(brand) and len(core) > len(brand) + 1:
            words.add(core[len(brand):])
    return sorted(w for w in words if len(w) >= 2)


# ---------------------------------------------------------------------------
# 画像构建与读写
# ---------------------------------------------------------------------------
def build(orders=None, wallet=None, available=None, account=None) -> Dict[str, Any]:
    prof: Dict[str, Any] = {"updated": datetime.now().strftime("%Y-%m-%d %H:%M")}
    if orders is not None:
        prof.update(_parse_orders(orders))

    coupons: List[Dict[str, Any]] = []
    if wallet is not None:
        coupons += _parse_coupons(wallet, "wallet")
    if available is not None:
        coupons += _parse_coupons(available, "claimable")
    # 同标题去重，已有券优先（钱包里的比可领的更确定）
    seen: Dict[str, Dict[str, Any]] = {}
    for c in coupons:
        key = c["title"]
        if key not in seen or c["source"] == "wallet":
            seen[key] = c
    prof["coupons"] = sorted(seen.values(), key=lambda c: (c["price"] is None, c["price"] or 0))

    if account is not None:
        acc = account
        if isinstance(acc, dict) and isinstance(acc.get("data"), dict):
            acc = acc["data"]
        if isinstance(acc, dict):
            try:
                prof["points"] = int(float(acc.get("availablePoint") or 0))
            except (TypeError, ValueError):
                prof["points"] = 0
    return prof


def load_profile() -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) and data.get("favorites") else None
    except (OSError, json.JSONDecodeError):
        return None


def save_profile(prof: Dict[str, Any]) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(prof, ensure_ascii=False, indent=1), encoding="utf-8")
    return PROFILE_PATH


def clear() -> bool:
    try:
        PROFILE_PATH.unlink()
        return True
    except FileNotFoundError:
        return False


def summary(prof: Dict[str, Any]) -> str:
    """给 Agent / 用户看的一段摘要。"""
    lines = ["# 🧠 口味画像\n"]
    if prof.get("orders_analyzed"):
        lines.append(f"> 基于最近 {prof['orders_analyzed']} 笔真实订单。\n")
    favs = prof.get("favorites") or []
    if favs:
        lines.append("**常点**")
        for f in favs[:6]:
            lines.append(f"- {f['name']} ×{f['count']}")
    traits = prof.get("traits") or {}
    if traits:
        names = {"chicken": "鸡肉", "beef": "牛肉", "pork": "猪肉", "fish": "鱼虾",
                 "cheese": "芝士", "potato": "薯类", "coffee": "咖啡", "spicy": "辣味",
                 "dessert": "甜品", "drink": "饮品", "breakfast": "早餐", "veg": "蔬果"}
        ranked = sorted(traits.items(), key=lambda kv: -kv[1])[:5]
        lines.append("\n**口味倾向**：" + "、".join(
            f"{names.get(k, k)} {int(v * 100)}%" for k, v in ranked))
    spend = prof.get("spend") or {}
    if spend:
        lines.append(f"\n**客单价**：常见 ¥{spend.get('p25')}–¥{spend.get('p75')}，"
                     f"中位 ¥{spend.get('median')}")
    periods = prof.get("periods") or {}
    if periods:
        label = {"breakfast": "早餐", "lunch": "午餐", "afternoon": "下午茶",
                 "dinner": "晚餐", "night": "夜宵"}
        bits = [f"{label.get(k, k)} 约 {p['usual_hour']} 点 / ¥{p['avg_spend']}"
                for k, p in periods.items() if p.get("usual_hour")]
        if bits:
            lines.append("**时段习惯**：" + "；".join(bits))
    coupons = prof.get("coupons") or []
    if coupons:
        lines.append("\n**手上的券**")
        for c in coupons[:8]:
            tag = "已有" if c["source"] == "wallet" else "可领"
            price = "免费" if c["price"] == 0 else (f"¥{c['price']}" if c["price"] is not None else "")
            bogo = " · 买一送一" if c.get("bogo") else ""
            lines.append(f"- [{tag}] {c['title']} {price}{bogo}")
    if prof.get("points"):
        lines.append(f"\n**积分**：{prof['points']}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="麦麦塔罗牌 · 口味画像")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="从连接器返回构建画像")
    b.add_argument("--orders", help="order-list 返回（JSON 或文本）")
    b.add_argument("--wallet", help="query-my-coupons 返回")
    b.add_argument("--available", help="available-coupons 返回")
    b.add_argument("--account", help="query-my-account 返回")

    sub.add_parser("show", help="查看画像摘要")
    sub.add_parser("clear", help="清空画像")

    args = ap.parse_args()

    if args.cmd == "build":
        prof = build(
            orders=_load_raw(args.orders) if args.orders else None,
            wallet=_load_raw(args.wallet) if args.wallet else None,
            available=_load_raw(args.available) if args.available else None,
            account=_load_raw(args.account) if args.account else None,
        )
        if not prof.get("favorites") and not prof.get("coupons"):
            print("没有解析到任何数据，检查一下入参文件内容。", file=sys.stderr)
            sys.exit(1)
        path = save_profile(prof)
        print(summary(prof))
        print(f"\n[画像] {path}")
    elif args.cmd == "show":
        prof = load_profile()
        if not prof:
            print("还没有画像。先跑 build。", file=sys.stderr)
            sys.exit(1)
        print(summary(prof))
    else:
        print("已清空。" if clear() else "本来就没有画像。")


if __name__ == "__main__":
    main()
