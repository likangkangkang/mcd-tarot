"""麦麦塔罗牌 · 麦当劳 MCP 客户端（仅标准库，无第三方依赖）。

仅用 urllib 实现 Streamable HTTP 版 MCP 的最小子集：
  initialize -> tools/call(query-meals)
真实可用菜单以用户麦当劳账号实时返回为准。

设计原则
--------
1. 真实优先：提供 MCD_MCP_TOKEN 时，直连 mcd-mcp 拉真实菜单（含名称/价格）。
2. 永远可演示：无 Token / 网络失败 / 解析异常时，自动回退到内置静态菜单，
   保证 Skill 在任何环境下都能产出完整的塔罗解读。
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

MCD_MCP_URL = "https://mcp.mcd.cn"
CLIENT_INFO = {"name": "mcd-tarot", "version": "1.0.0"}
PROTOCOL_VERSION = "2024-11-05"

# 内置静态菜单（回退用，价格仅供参考，非实时）
FALLBACK_MENU: List[Dict[str, Any]] = [
    {"name": "巨无霸", "code": "9900000001", "price": 24.0, "category": "汉堡"},
    {"name": "双层吉士汉堡", "code": "9900000002", "price": 22.5, "category": "汉堡"},
    {"name": "麦辣鸡腿汉堡", "code": "9900005456", "price": 21.0, "category": "辣味炸鸡"},
    {"name": "板烧鸡腿堡", "code": "9900000003", "price": 22.0, "category": "汉堡"},
    {"name": "麦香鸡", "code": "9900000004", "price": 14.0, "category": "汉堡"},
    {"name": "麦辣鸡翅(2块)", "code": "9900000005", "price": 13.0, "category": "辣味炸鸡"},
    {"name": "劲脆鸡腿堡", "code": "9900000006", "price": 21.0, "category": "炸鸡"},
    {"name": "薯条(中)", "code": "9900000007", "price": 12.0, "category": "主食配餐"},
    {"name": "玉米杯", "code": "9900000008", "price": 9.0, "category": "清爽轻盈"},
    {"name": "苹果片", "code": "9900000009", "price": 7.0, "category": "清爽轻盈"},
    {"name": "鲜煮咖啡", "code": "9900000010", "price": 12.0, "category": "饮品甜饮"},
    {"name": "美式咖啡(中)", "code": "9900000011", "price": 14.0, "category": "饮品甜饮"},
    {"name": "拿铁(中)", "code": "9900000012", "price": 18.0, "category": "饮品甜饮"},
    {"name": "可乐(中)", "code": "9900000013", "price": 10.0, "category": "饮品甜饮"},
    {"name": "红豆派", "code": "9900000014", "price": 7.0, "category": "饮品甜饮"},
    {"name": "麦旋风", "code": "9900000015", "price": 13.0, "category": "饮品甜饮"},
    {"name": "甜筒", "code": "9900000016", "price": 5.0, "category": "饮品甜饮"},
    {"name": "早餐全餐", "code": "9900000017", "price": 22.0, "category": "早餐"},
    {"name": "开心乐园餐", "code": "9900000018", "price": 35.0, "category": "分享"},
    {"name": "麦辣鸡翅分享盒", "code": "9900000019", "price": 39.0, "category": "辣味炸鸡"},
    {"name": "灰焰圆筒", "code": "9900000020", "price": 5.0, "category": "饮品甜饮"},
    {"name": "人气经典随心配", "code": "9900000021", "price": 14.9, "category": "随心配"},
    {"name": "限定风味麦旋风", "code": "9900000022", "price": 16.0, "category": "饮品甜饮"},
    {"name": "燕麦奶铁", "code": "9900000023", "price": 9.9, "category": "饮品甜饮"},
    {"name": "薄皮V翅双拼十翅", "code": "9900000024", "price": 49.9, "category": "辣味炸鸡"},
    {"name": "全明星双人分享餐", "code": "9900000025", "price": 49.9, "category": "分享"},
]


def _parse_body(body: str) -> Any:
    """解析 JSON-RPC 响应：支持纯 JSON 与 SSE(text/event-stream)。"""
    body = (body or "").strip()
    if not body:
        return None
    if body.startswith("{"):
        return json.loads(body)
    # SSE: 取最后一个 data: 行
    last = None
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            data = line[5:].strip()
            if data and data != "[DONE]":
                last = data
    if last:
        try:
            return json.loads(last)
        except json.JSONDecodeError:
            return None
    return None


def _post(token: str, payload: Dict[str, Any], session_id: Optional[str] = None):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(MCD_MCP_URL, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    if session_id:
        req.add_header("Mcp-Session-Id", session_id)
    resp = urllib.request.urlopen(req, timeout=20)
    body = resp.read().decode("utf-8")
    new_sid = resp.headers.get("Mcp-Session-Id") or resp.headers.get("mcp-session-id")
    return _parse_body(body), new_sid


def _extract_meals(result: Any) -> List[Dict[str, Any]]:
    """从 tools/call 结果里尽量抽出菜单列表。结构可能有多层，做防御式解析。"""
    if not isinstance(result, dict):
        return []
    content = result.get("result", result).get("content", []) if isinstance(result.get("result"), dict) else []
    texts: List[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            texts.append(item.get("text", ""))
    if not texts:
        return []
    blob = "\n".join(texts)
    # 可能是 JSON 字符串数组 / 对象
    try:
        parsed = json.loads(blob)
    except json.JSONDecodeError:
        return []
    items: List[Any] = []
    if isinstance(parsed, list):
        items = parsed
    elif isinstance(parsed, dict):
        for key in ("items", "meals", "data", "list", "products"):
            if isinstance(parsed.get(key), list):
                items = parsed[key]
                break
        else:
            items = [parsed]
    out: List[Dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        name = it.get("name") or it.get("productName") or it.get("title")
        if not name:
            continue
        out.append({
            "name": str(name),
            "code": it.get("code") or it.get("productCode") or it.get("id"),
            "price": it.get("price") or it.get("salePrice"),
            "category": it.get("category") or it.get("categoryName"),
        })
    return out


def fetch_real_menu(token: str, **kwargs: Any) -> List[Dict[str, Any]]:
    """直连 mcd-mcp 拉真实菜单；任何异常都向上抛出（由调用方回退）。"""
    init, sid = _post(token, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                   "clientInfo": CLIENT_INFO},
    })
    if not init or "result" not in init:
        raise RuntimeError("MCP initialize 失败")
    res, _ = _post(token, {
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "query-meals", "arguments": kwargs or {}},
    }, session_id=sid)
    meals = _extract_meals(res)
    if not meals:
        raise RuntimeError("MCP query-meals 未返回可识别菜单")
    return meals


def get_menu(token: Optional[str] = None) -> List[Dict[str, Any]]:
    """对外统一入口：有 Token 且成功取真实菜单则用真实；否则回退静态菜单。"""
    token = token or os.environ.get("MCD_MCP_TOKEN")
    if token:
        try:
            real = fetch_real_menu(token)
            if real:
                return real
        except Exception as exc:  # noqa: BLE001 - 真实失败则回退，不阻断
            print(f"[warn] 真实菜单获取失败，使用静态回退菜单：{exc}")
    return FALLBACK_MENU


# 非餐品（周边 / 贴纸 / 酱料）不参与映射，避免「薯条」命中「薯条脆卜卜毛绒周边」
NON_FOOD_PATTERN = re.compile(r"周边|贴纸|毛绒|捶|痒挠|贴$|酱$")
# 套餐类：单品的语义更准，只有在没有单品可选、或牌的关键词本身就指向套餐时才用
BUNDLE_PATTERN = re.compile(r"套餐|三件套|双人|全家桶|组合|桶")

# 与 profile.py 的 TRAITS 对齐：用于「这个菜合不合你口味」
_PREF_TRAITS: Dict[str, List[str]] = {
    "chicken": ["鸡", "板烧", "麦乐鸡", "鸡块", "鸡腿"],
    "beef": ["牛", "巨无霸", "吉士", "安格斯"],
    "pork": ["猪", "猪柳", "培根", "肉骨"],
    "fish": ["鱼", "三文鱼", "虾", "鳕"],
    "cheese": ["芝士", "吉士", "马苏里拉"],
    "potato": ["薯条", "薯饼", "薯"],
    "coffee": ["咖啡", "美式", "拿铁", "奶铁"],
    "spicy": ["辣", "麻辣", "花椒", "韩式", "椒"],
    "dessert": ["麦旋风", "甜筒", "冰淇淋", "派", "蛋糕", "圣代"],
    "drink": ["可乐", "汁", "茶", "豆浆", "柠", "雪碧", "芬达"],
    "breakfast": ["早餐", "麦满分", "炒双蛋", "脆薯饼", "豆浆", "粥"],
    "veg": ["玉米", "沙拉", "苹果", "蔬菜"],
}
_TRAIT_LABEL = {
    "chicken": "鸡肉", "beef": "牛肉", "pork": "猪肉", "fish": "鱼虾",
    "cheese": "芝士", "potato": "薯类", "coffee": "咖啡", "spicy": "辣味",
    "dessert": "甜品", "drink": "饮品", "breakfast": "早餐", "veg": "蔬果",
}


_NORM_STRIP = set(" \t\r\n（）()［］[]【】·•+＋-—–_/\\™®©")


def _norm(text: str) -> str:
    """去掉空格、括号、商标符号等噪音，只留下能比较的正文字符。"""
    return "".join(ch for ch in str(text or "") if ch not in _NORM_STRIP)


def affinity(item: Dict[str, Any], profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """打分：这道菜有多合你的口味。返回 score 与一句人话理由。

    分数构成（上限约 3.0）：
    - 你点过同名/近似的菜：最高 +2.2，理由是「你点过 N 次」
    - 命中你偏爱的口味类型：每类 +0.9 × 强度，最多计两类
    - 落在你常见客单价区间：+0.35
    """
    if not profile:
        return {"score": 0.0, "why": ""}
    name = _norm(item.get("name"))

    best_fav = None
    for fav in profile.get("favorites") or []:
        fname = _norm(fav.get("name"))
        if not fname or not name:
            continue
        familiar = (
            fname == name
            or (len(fname) >= 4 and fname in name)
            or (len(name) >= 4 and name in fname)
            # 「板烧鸡腿堡」和「原味板烧鸡腿炒双蛋堡组合」算同一口味
            or (_lcs_len(fname, name) >= 4
                and _lcs_len(fname, name) / min(len(fname), len(name)) >= 0.6)
        )
        if familiar:
            cnt = int(fav.get("count") or 0)
            if best_fav is None or cnt > best_fav[1]:
                best_fav = (fav.get("name"), cnt)

    score = 0.0
    why = ""
    if best_fav:
        score += 1.6 + min(0.6, 0.15 * best_fav[1])
        why = f"你点过 {best_fav[1]} 次「{best_fav[0]}」，这道对味"

    traits = profile.get("traits") or {}
    hits = []
    if name:
        for trait, words in _PREF_TRAITS.items():
            strength = float(traits.get(trait) or 0)
            if strength >= 0.2 and any(w in name for w in words):
                hits.append((trait, strength))
    for trait, strength in sorted(hits, key=lambda x: -x[1])[:2]:
        score += 0.9 * strength
        if not why:
            why = f"你偏爱的口味：{_TRAIT_LABEL.get(trait, trait)}"

    band = profile.get("spend") or {}
    price = item.get("price")
    if price is not None and band.get("p25") is not None and band.get("p75") is not None:
        p = float(price)
        if float(band["p25"]) <= p <= float(band["p75"]):
            score += 0.35
        elif p > float(band["p75"]) * 1.6:
            score -= 1.0

    return {"score": round(score, 3), "why": why}


def _coupon_matches(core: str, keywords: List[str], name: str) -> bool:
    """券和菜名是否指同一件东西：整体包含，或够长的公共片段。"""
    n, c = _norm(name), _norm(core)
    if not n or not c:
        return False
    if c in n or n in c:
        return True
    for kw in keywords:
        k = _norm(kw)
        if len(k) >= 2 and k in n:
            return True
        if len(k) >= 3 and _lcs_len(k, n) >= 4:
            return True
    return len(c) >= 4 and _lcs_len(c, n) >= len(c) - 1


def _lcs_len(a: str, b: str) -> int:
    """最长公共子串长度（中文菜名够用）。"""
    if not a or not b:
        return 0
    best = 0
    prev = [0] * (len(b) + 1)
    for ch in a:
        cur = [0] * (len(b) + 1)
        for j, ch2 in enumerate(b, 1):
            if ch == ch2:
                cur[j] = prev[j - 1] + 1
                best = max(best, cur[j])
        prev = cur
    return best


def deal_for(item: Dict[str, Any], profile: Optional[Dict[str, Any]],
             period: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
    """这道菜能用哪张券、大概省多少。只在真的更便宜时返回。"""
    if not profile:
        return None
    price = item.get("price")
    try:
        p = float(price) if price is not None else None
    except (TypeError, ValueError):
        p = None
    name = str(item.get("name") or "")

    best: Optional[Dict[str, Any]] = None
    for coupon in profile.get("coupons") or []:
        if coupon.get("combo"):
            continue  # 「任选 2 件」这类是组合券，单独提示，不按单品算
        # 单品券不能抵扣套餐（“11.9 麦辣鸡腿堡”不适用于“麦辣鸡腿汉堡三件套”）
        if _form(item) == "combo":
            continue
        if not _coupon_matches(coupon.get("core", ""), coupon.get("keywords") or [], name):
            continue
        cprice = coupon.get("price")
        saving = None
        if coupon.get("bogo"):
            if p is not None:
                saving = round(p / 2, 1)
        elif cprice is not None and p is not None:
            if float(cprice) == 0:
                saving = p
            elif float(cprice) < p:
                saving = round(p - float(cprice), 1)
        elif cprice is not None and p is None:
            saving = 0.0
        if saving is None or saving <= 0:
            continue
        cand = {
            "title": coupon.get("title"),
            "source": coupon.get("source"),
            "price": cprice,
            "saving": saving,
            "free": cprice == 0,
            "bogo": bool(coupon.get("bogo")),
        }
        if best is None or cand["saving"] > best["saving"]:
            best = cand
    return best


def combo_coupon_note(profile: Optional[Dict[str, Any]],
                      period: Optional[Dict[str, str]] = None) -> str:
    """组合型券（如 19.9 任选 2 件）无法落到单品，单独给一句提示。"""
    if not profile:
        return ""
    for coupon in profile.get("coupons") or []:
        if coupon.get("combo") and coupon.get("price") is not None:
            return f"另外还有「{coupon['title']}」，想多买一件时更划算"
    return ""


def _same_category(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    ca = _norm(a.get("category") or a.get("mcd_category"))
    cb = _norm(b.get("category") or b.get("mcd_category"))
    if not ca or not cb:
        return False
    if ca == cb or ca in cb or cb in ca:
        return True
    return _lcs_len(ca, cb) >= 3


def alternative_for(
    card: Dict[str, Any],
    chosen: Dict[str, Any],
    menu: List[Dict[str, Any]],
    profile: Optional[Dict[str, Any]] = None,
    exclude: Optional[set] = None,
    prefer_form: Optional[str] = None,
    period: Optional[Dict[str, str]] = None,
) -> Optional[Dict[str, Any]]:
    """在「同一类食物」里，找一道更像你平时会点、而且不更贵的备选。

    只在同时满足以下条件时才返回，避免变成推销：
    - 口味契合度高（点过 / 命中偏爱口味）
    - 与牌面推荐同类，换了也不违背牌意
    - 有券能省 ≥3 元，或价格不高于当前推荐
    """
    if not profile:
        return None
    exclude = exclude or set()
    chosen_name = str(chosen.get("name") or "")
    cur_price = chosen.get("price")
    cur_price = float(cur_price) if cur_price is not None else 999.0
    chosen_form = _form(chosen)

    best = None
    for it in menu:
        name = str(it.get("name") or "")
        if not name or name == chosen_name or name in exclude:
            continue
        if NON_FOOD_PATTERN.search(name):
            continue
        # 只跟「当前推荐这道」比品类（牌本身没有品类字段）
        if not _same_category(chosen, it):
            continue
        # 形态别跳档：推荐单品时不要突然塞套餐
        if chosen_form in ("single", "light") and _form(it) == "combo":
            continue
        aff = affinity(it, profile)
        if aff["score"] < 1.5:
            continue
        deal = deal_for(it, profile, period)
        price = it.get("price")
        price_f = float(price) if price is not None else 999.0
        saving = float(deal["saving"]) if deal else 0.0
        if saving < 3 and price_f > cur_price * 1.2:
            continue
        key = (aff["score"], saving, -price_f)
        if best is None or key > best[0]:
            best = (key, it, aff, deal)

    if not best:
        return None
    _, it, aff, deal = best
    return {
        "name": it.get("name"),
        "code": it.get("code"),
        "price": it.get("price"),
        "affinity": aff["score"],
        "why": aff["why"],
        "deal": deal,
    }


def claimable_hint(profile: Optional[Dict[str, Any]], limit: int = 2) -> str:
    """提示还能领的券（不含已有券）。"""
    if not profile:
        return ""
    picks = [c for c in (profile.get("coupons") or []) if c.get("source") == "claimable"]
    if not picks:
        return ""
    parts = []
    for c in picks[:limit]:
        if c.get("price") == 0:
            parts.append(f"「{c['title']}」（免费）")
        elif c.get("price") is not None:
            parts.append(f"「{c['title']}」（¥{c['price']}）")
        else:
            parts.append(f"「{c['title']}」")
    return "还能领：" + "、".join(parts)


def _pick_diverse(card: Dict[str, Any], menu: List[Dict[str, Any]], exclude: set) -> Optional[Dict[str, Any]]:
    """关键词都被占用的兜底：在同品类里换一道没用过的、便宜的、名字短的。

    只接受同品类（饮食语义一致），宁可重样也不硬塞一道不相干的菜。
    """
    cat = str(card.get("mcd_category") or "")
    if not cat:
        return None
    pool = [
        it for it in menu
        if it.get("name") and not NON_FOOD_PATTERN.search(str(it["name"]))
        and str(it["name"]) not in exclude
    ]
    same_cat = [
        it for it in pool
        if cat and str(it.get("category") or "")
        and (cat in str(it["category"]) or str(it["category"]) in cat)
    ]
    if not same_cat:
        return None
    return min(same_cat, key=lambda it: (float(it.get("price") or 999), len(str(it["name"]))))


def _tag(item: Dict[str, Any], how: str) -> Dict[str, Any]:
    """复制一份并标注匹配方式，避免污染菜单原始数据。"""
    out = dict(item)
    out["_match"] = how
    return out


def _cheapest(pool: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    priced = [it for it in pool if it.get("price") is not None]
    if not priced:
        return None
    return min(priced, key=lambda it: (float(it["price"]), len(str(it["name"]))))


def _form(item: Dict[str, Any]) -> str:
    """餐品形态：优先用菜单归一化时算好的 form，缺失时用名字兜底判断。"""
    f = item.get("form")
    if f:
        return str(f)
    name = str(item.get("name") or "")
    if NON_FOOD_PATTERN.search(name):
        return "goods"
    if BUNDLE_PATTERN.search(name):
        return "combo"
    return "single"


# 形态偏好的放宽顺序（选不到理想形态时退一档）
_FORM_FALLBACK = {
    "light": ("light", "single"),
    "single": ("single", "light"),
    "combo": ("combo", "single"),
    "share": ("share", "combo"),
}


def _pick_with_form(
    pool: List[Dict[str, Any]],
    prefer_form: Optional[str],
    profile: Optional[Dict[str, Any]] = None,
    period: Optional[Dict[str, str]] = None,
) -> Optional[Dict[str, Any]]:
    """在候选里挑一个：有形态偏好就优先满足；同形态内先看合不合口味、划不划算。"""
    if not pool:
        return None

    def rank(it: Dict[str, Any]):
        score = affinity(it, profile)["score"]
        deal = deal_for(it, profile, period)
        if deal:
            score += min(0.8, deal["saving"] / 10)
        return (-score, len(str(it.get("name"))))

    if prefer_form:
        allowed = _FORM_FALLBACK.get(prefer_form, (prefer_form,))
        for want in allowed:
            hits = [it for it in pool if _form(it) == want]
            if hits:
                return min(hits, key=rank)
    singles = [it for it in pool if _form(it) != "combo"]
    return min(singles or pool, key=rank)


def _resolve_core(
    card: Dict[str, Any],
    menu: List[Dict[str, Any]],
    exclude: Optional[set] = None,
    prefer_form: Optional[str] = None,
    profile: Optional[Dict[str, Any]] = None,
    period: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """根据牌的 mcd_keywords 在菜单里匹配真实单品；匹配不到用关键词兜底。

    同一关键词内按「同名 > 形态偏好 > 合口味/更划算 > 名称最短」择优：
    - 同名优先，避免「巨无霸」被「巨无霸三件套」抢先；
    - prefer_form 由牌意 + 点餐时段算出（light/single/combo/share），
      午餐晚餐更愿意给套餐，下午茶夜宵更愿意给轻食；
    - profile（口味画像）只在「同一意图内有多道可选」时参与排序，
      不会把牌指的品类换成别的品类；
    - 非餐品（周边、贴纸、酱料）直接排除；
    - exclude：已被本牌阵其它牌用掉的餐品名，先在同品类里换一道没用过的；
    - 关键词全都没命中时（新店/小菜单/换季），退到同品类里你最可能爱吃的。
    """
    keywords = card.get("mcd_keywords") or []
    exclude = exclude or set()
    candidates = [
        it for it in menu
        if it.get("name") and not NON_FOOD_PATTERN.search(str(it["name"]))
    ]
    cat = str(card.get("mcd_category") or "")

    backup: Optional[Dict[str, Any]] = None
    bundle_backup: Optional[Dict[str, Any]] = None
    for kw in keywords:
        if not kw:
            continue
        hits = [it for it in candidates if kw in str(it["name"])]
        if not hits:
            continue
        fresh = [it for it in hits if str(it["name"]) not in exclude]
        if not fresh:
            backup = backup or hits[0]
            continue
        # 关键词本身指向套餐（如「全明星双人分享餐」）时不做单品优先；
        # 正餐时段明确想要套餐时，也把套餐留在候选里
        allow_bundle = bool(BUNDLE_PATTERN.search(kw)) or prefer_form in ("combo", "share")
        pool = fresh if allow_bundle else [it for it in fresh if _form(it) != "combo"]
        if not pool:
            bundle_backup = bundle_backup or min(fresh, key=lambda it: len(str(it["name"])))
            continue
        # 想吃套餐/分享装时，形态优先于「同名单品」
        if prefer_form in ("combo", "share"):
            picked = _pick_with_form(pool, prefer_form, profile, period)
            if picked is not None:
                return _tag(picked, "keyword")
        for it in pool:
            if str(it["name"]) == kw:
                return _tag(it, "keyword")
        picked = _pick_with_form(pool, prefer_form, profile, period)
        if picked is not None:
            return _tag(picked, "keyword")

    # 关键词命中但都已被占用 → 同品类里换一道没用过的菜；没有就允许重样
    diverse = _pick_diverse(card, menu, exclude)
    if diverse:
        return _tag(diverse, "category")
    if bundle_backup:
        return _tag(bundle_backup, "bundle")
    if backup:
        return _tag(backup, "repeat")

    # 关键词全未命中：退到同品类真实带价餐品（小菜单 / 换季 / 新店）
    same_cat = [
        it for it in candidates
        if cat and str(it.get("category") or "")
        and (cat in str(it["category"]) or str(it["category"]) in cat)
    ]
    pick = _pick_with_form(same_cat, prefer_form, profile, period) if same_cat else None
    if pick:
        return _tag(pick, "category-fallback")
    pick = _cheapest([it for it in same_cat if str(it["name"]) not in exclude]) or _cheapest(same_cat)
    if pick:
        return _tag(pick, "category-fallback")

    # 连品类都对不上（菜单没带分类）：按牌号在菜单里轮转，优先满足推荐形态
    if candidates:
        # 注意：菜单里的 form 只有 combo/single/goods，没有 light，
        # 直接用 prefer_form 精确比对会让「轻食」偏好永远落空 → 走放宽表
        allowed = set(_FORM_FALLBACK.get(prefer_form, (prefer_form,))) if prefer_form else set()
        tier = [it for it in candidates if _form(it) in allowed]
        rest = [it for it in candidates if it not in tier]
        # 轮换只在「符合形态偏好」那一层里做，否则起点会跳到后面的套餐上
        if tier:
            start = int(card.get("id") or 0) % len(tier)
            ordered = tier[start:] + tier[:start]
        else:
            ordered = []
        ordered += [it for it in rest if not BUNDLE_PATTERN.search(str(it["name"]))]
        ordered += [it for it in rest if BUNDLE_PATTERN.search(str(it["name"]))]
        for it in ordered:
            if str(it["name"]) not in exclude and it.get("price") is not None:
                return _tag(it, "menu-fallback")
        pick = _cheapest([it for it in candidates if str(it["name"]) not in exclude])
        if pick:
            return _tag(pick, "menu-fallback")

    # 菜单为空/无价格：用首个关键词当名字，价格留空
    fallback_name = next((k for k in keywords if k and k not in exclude), None)
    fallback_name = fallback_name or (keywords[0] if keywords else card.get("mcd_category", "麦麦餐品"))
    return {"name": fallback_name, "code": None, "price": None, "category": card.get("mcd_category"),
            "original_price": None, "image": "", "form": prefer_form or "single", "_match": "none"}


def resolve_item(
    card: Dict[str, Any],
    menu: List[Dict[str, Any]],
    exclude: Optional[set] = None,
    prefer_form: Optional[str] = None,
    profile: Optional[Dict[str, Any]] = None,
    period: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """匹配餐品，并附上「合不合你口味」与「有没有券」的标注。

    返回值除菜单字段外，额外带：
    - _match：匹配方式（keyword/category/category-fallback/...）
    - affinity：口味契合分（0–3）
    - affinity_why：一句人话（如「你点过 4 次原味板烧鸡腿炒双蛋堡组合」）
    - deal：可用的券与预计省下的钱（没有则 None）
    """
    item = _resolve_core(card, menu, exclude, prefer_form, profile, period)
    aff = affinity(item, profile)
    out = dict(item)
    out["affinity"] = aff["score"]
    out["affinity_why"] = aff["why"]
    out["deal"] = deal_for(item, profile, period)
    return out


if __name__ == "__main__":
    token = os.environ.get("MCD_MCP_TOKEN")
    menu = get_menu(token)
    print(f"菜单条数: {len(menu)}（{'真实' if token else '静态回退'}）")
    print("样例:", menu[0])
