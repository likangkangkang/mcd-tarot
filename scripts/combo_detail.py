"""麦麦塔罗牌 · 套餐明细：这一份里到底装了什么。

为什么要它
----------
套餐名常常只写「麦辣鸡腿汉堡三件套」，用户看不出自己到底点了什么。
抽到套餐时，需要在名字下面补一行明细（餐品名 + 数量），让人下单前心里有数。

三级来源，能用真实的就绝不用猜
------------------------------
1. **菜单自带**：归一化后的菜单项里若带 `items` / `includes` 等明细字段，直接用；
2. **本地缓存**：用 `query-meal-detail` 拉过一次的官方明细存在
   `~/.cache/mcd-tarot/combo_details.json`，之后直接读；
3. **按名推断**：前两级都没有时，按套餐名的件数（三件套/四件套/双人餐…）
   结合**本店菜单里真实存在的单品名**拼出明细，并标注「参考配置」。

推断不是凭空编造：配餐一律优先取菜单里真实存在的名字（例如菜单里叫
「薯条(中)」就写「薯条(中)」），拿不到才用通用名兜底。

用法
----
    python3 scripts/combo_detail.py --name "麦辣鸡腿汉堡三件套" --menu-file menu.json
    python3 scripts/combo_detail.py --raw meal-detail.json          # 导入官方明细到缓存
    python3 scripts/combo_detail.py --raw meal-detail.json --code 12345
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cache

# 明细字段在原始返回里可能的键名（各家命名不统一，做防御式解析）
_ITEM_KEYS = (
    "items", "includes", "combo_items", "comboItems", "sub_items", "subItems",
    "details", "detailList", "mealDetails", "products", "children", "groups",
    "packageItems", "skuList",
)
_QTY_KEYS = ("qty", "quantity", "count", "num", "nums", "amount", "number",
             "mealCount", "meal_count", "productCount", "product_count")
_NAME_KEYS = ("name", "mealName", "productName", "title", "itemName", "skuName")

# 套餐名里的件数
_PIECES = {
    "两件套": 2, "二件套": 2, "三件套": 3, "四件套": 4, "五件套": 5, "六件套": 6,
    "1+1": 2, "任选2件": 2, "任选两件": 2, "任选3件": 3, "任选三件": 3,
}
# 需要整体识别、不能按后缀乱拆的名字
_WHOLE_NAMES = ("开心乐园餐", "早餐全餐", "全餐", "随心配", "1+1", "任选")

# 剥离主品名时要去掉的后缀（长的在前，避免「超值三件套」被拆成「超值」）
_SUFFIX = (
    "超值三件套", "超值四件套", "欢乐分享餐", "双人分享餐", "全家分享餐",
    "三件套", "四件套", "五件套", "两件套", "二件套",
    "超值套餐", "超值餐", "组合餐", "双人餐", "分享餐", "分享盒", "分享装",
    "套餐", "组合", "桶",
)

# 配餐：按件数补的默认内容（键是在菜单里搜的关键词）
_SIDE_PLAN: Dict[int, Tuple[str, ...]] = {
    2: ("薯条",),
    3: ("薯条", "可乐"),
    4: ("薯条", "可乐", "麦乐鸡"),
    5: ("薯条", "可乐", "麦乐鸡", "派"),
    6: ("薯条", "可乐", "麦乐鸡", "派", "玉米"),
}
# 菜单里找不到时的通用名
_SIDE_FALLBACK = {
    "薯条": "薯条(中)", "可乐": "可乐(中)", "麦乐鸡": "麦乐鸡(5块)",
    "派": "派(1个)", "玉米": "玉米杯", "咖啡": "鲜煮咖啡", "薯饼": "脆薯饼",
    "牛奶": "牛奶", "果汁": "果汁",
}

_QTY_IN_NAME = re.compile(r"[（(]?\s*(\d+)\s*(?:块|片|只|支|杯|个)\s*[)）]?")
_NON_FOOD = re.compile(r"周边|贴纸|毛绒|捶|痒挠|玩具|图书")


# ---------------------------------------------------------------------------
# 缓存：官方明细（query-meal-detail 拉取后写本地）
# ---------------------------------------------------------------------------
def _detail_file() -> Path:
    return cache.cache_dir() / "combo_details.json"


def load_details() -> Dict[str, List[Dict[str, Any]]]:
    f = _detail_file()
    if not f.exists():
        return {}
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_details(data: Dict[str, List[Dict[str, Any]]]) -> Path:
    f = _detail_file()
    f.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return f


def _key_of(name: str) -> str:
    """明细缓存的键：去掉空格与标点，避免「麦当劳 薯条(中)」对不上。"""
    return re.sub(r"[\s（）()【】\[\]“”\"'·•,，、/\\]", "", str(name or ""))


def put_detail(name: str, items: List[Dict[str, Any]], code: Optional[str] = None) -> None:
    """把官方明细写进缓存（按餐品名，可选同时按 code）。"""
    if not items:
        return
    data = load_details()
    data[_key_of(name)] = items
    if code:
        data[f"code:{code}"] = items
    _save_details(data)


# ---------------------------------------------------------------------------
# 从原始返回里抽明细
# ---------------------------------------------------------------------------
def _clean_items(raw_items: Any) -> List[Dict[str, Any]]:
    """把任意形态的明细列表整理成 [{"name", "qty"}, ...]。"""
    out: List[Dict[str, Any]] = []
    if not isinstance(raw_items, list):
        return out
    for it in raw_items:
        if isinstance(it, str) and it.strip():
            out.append({"name": it.strip(), "qty": 1})
            continue
        if not isinstance(it, dict):
            continue
        nm = next((it[k] for k in _NAME_KEYS if it.get(k)), None)
        if not nm:
            continue
        qty = 1
        for k in _QTY_KEYS:
            if it.get(k) not in (None, ""):
                try:
                    qty = int(float(it[k]))
                except (TypeError, ValueError):
                    qty = 1
                break
        out.append({"name": str(nm).strip(), "qty": max(1, qty)})
    return out


def items_of(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """菜单项自带的明细（归一化时若保留了这些字段就能直接用）。"""
    for key in _ITEM_KEYS:
        got = _clean_items(item.get(key))
        if got:
            return got
    return []


def _scan(node: Any, depth: int = 0) -> List[Dict[str, Any]]:
    """递归扫描任意 JSON，找出第一处「像餐品明细」的列表。"""
    if depth > 6:
        return []
    if isinstance(node, list):
        got = _clean_items(node)
        if got:
            return got
        for x in node:
            got = _scan(x, depth + 1)
            if got:
                return got
        return []
    if isinstance(node, dict):
        for key in _ITEM_KEYS:
            got = _clean_items(node.get(key))
            if got:
                return got
        for v in node.values():
            got = _scan(v, depth + 1)
            if got:
                return got
    return []


def ingest(raw: Any, code: Optional[str] = None, name: Optional[str] = None) -> List[Dict[str, Any]]:
    """从 query-meal-detail 的返回里抽明细并写入缓存，返回抽到的明细。"""
    items = _scan(raw)
    if not items:
        return []
    key_name = name
    if not key_name and isinstance(raw, dict):
        for k in _NAME_KEYS:
            if raw.get(k):
                key_name = str(raw[k])
                break
    if not key_name:
        data = raw.get("data") if isinstance(raw, dict) and isinstance(raw.get("data"), dict) else raw
        if isinstance(data, dict):
            for k in _NAME_KEYS:
                if data.get(k):
                    key_name = str(data[k])
                    break
    if key_name:
        put_detail(key_name, items, code)
    return items


# ---------------------------------------------------------------------------
# 按名推断（零网络兜底，优先借用本店菜单里真实存在的单品名）
# ---------------------------------------------------------------------------
_BUNDLE_WORDS = re.compile(r"套餐|三件套|四件套|五件套|两件套|分享|桶|组合|双人|全家|乐园餐")


def _pick_menu_name(key: str, menu: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    """在本店菜单里找包含 key 的单品名：优先单品，其次是套餐名里的主品部分。

    不能直接拿套餐名当主品（否则「全明星双人分享餐」里会拆出它自己），
    所以套餐名要先剥掉件数后缀再做匹配。
    """
    if not menu:
        return None
    hits = [str(it["name"]) for it in menu
            if it.get("name") and key in str(it["name"]) and not _NON_FOOD.search(str(it["name"]))]
    plain = [n for n in hits if not _BUNDLE_WORDS.search(n)]
    if plain:
        return min(plain, key=len)
    cores = [_main_of(n)[0] for n in hits]
    cores = [c for c in cores if key in c and not _BUNDLE_WORDS.search(c)]
    return min(cores, key=len) if cores else None


def _main_of(name: str) -> Tuple[str, int]:
    """从套餐名里拆出主品名与件数。"""
    pieces = 0
    for word, n in _PIECES.items():
        if word in name:
            pieces = max(pieces, n)
    core = name
    for suf in _SUFFIX:
        if core.endswith(suf) and len(core) > len(suf):
            core = core[: -len(suf)]
            break
    core = core.strip(" 的·-—")
    if len(core) < 2:
        core = name
    return core, pieces


def _qty_from_name(name: str) -> Tuple[str, int]:
    """名字里自带数量就拆出来：「麦辣鸡翅(2块)」→ ("麦辣鸡翅", 2)。"""
    m = _QTY_IN_NAME.search(name)
    if not m:
        return name, 1
    qty = int(m.group(1))
    if qty <= 0 or qty > 99:
        return name, 1
    stripped = _QTY_IN_NAME.sub("", name).strip(" （）()")
    return (stripped or name), qty


def guess_items(name: str, menu: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """按套餐名推断里面装了什么；配餐尽量用菜单里真实的名字。"""
    nm = str(name or "").strip()
    if not nm:
        return []

    # 自选类：本身就能装任意单品，不替用户决定
    if re.search(r"随心配|1\s*\+\s*1|任选|自选|自由搭", nm):
        # 内容由用户自己挑，别替他决定写哪两件（plain：不再加 ×1）
        return [{"name": "任选 2 件（下单时自己挑）", "qty": 1, "plain": True}]

    # 开心乐园餐 / 早餐全餐：内容固定但和「几件套」不是一套逻辑，主餐到店选
    if "乐园餐" in nm:
        side = _pick_menu_name("玉米", menu) or _SIDE_FALLBACK["玉米"]
        drink = _pick_menu_name("牛奶", menu) or _pick_menu_name("果汁", menu) or "牛奶/果汁"
        return [{"name": "主餐（汉堡或麦乐鸡，到店选）", "qty": 1},
                {"name": side, "qty": 1}, {"name": drink, "qty": 1},
                {"name": "玩具/图书", "qty": 1}]
    if "早餐" in nm and "全餐" in nm:
        side = _pick_menu_name("薯饼", menu) or _SIDE_FALLBACK["薯饼"]
        drink = _pick_menu_name("咖啡", menu) or _pick_menu_name("豆浆", menu) or _SIDE_FALLBACK["咖啡"]
        return [{"name": "主食（到店选）", "qty": 1},
                {"name": side, "qty": 1}, {"name": drink, "qty": 1}]

    core, pieces = _main_of(nm)
    core, main_qty = _qty_from_name(core)

    # 双人 / 分享 / 桶：份量翻倍
    multi = 2 if re.search(r"双人|双人份|分享|桶|全家", nm) else 1
    if pieces not in _SIDE_PLAN:
        pieces = 3 if multi == 1 else 4

    # 主品：优先用菜单里真实存在的那道（「麦辣鸡腿堡」而不是半个名字）
    # 名字里自带块数（麦辣鸡翅(2块)）就按块数算，不再被「双人/分享」翻倍
    main_name = _pick_menu_name(core, menu) or core
    main_name, main_qty2 = _qty_from_name(main_name)
    items: List[Dict[str, Any]] = [
        {"name": main_name, "qty": main_qty2 if main_qty2 > 1 else main_qty * multi}]

    for key in _SIDE_PLAN.get(pieces, _SIDE_PLAN[3]):
        real = _pick_menu_name(key, menu)
        items.append({"name": real or _SIDE_FALLBACK.get(key, key), "qty": multi})
    return items


# ---------------------------------------------------------------------------
# 对外主入口
# ---------------------------------------------------------------------------
def describe(item: Dict[str, Any], menu: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    """给出这一份的明细。返回 None 表示说不清（此时不要硬凑一行）。"""
    name = str(item.get("name") or "")
    if not name:
        return None

    items = items_of(item)
    source = "menu"
    if not items:
        data = load_details()
        code = item.get("code")
        items = data.get(f"code:{code}") if code else None
        if not items:
            items = data.get(_key_of(name))
        if items:
            source = "cache"
    if not items:
        # 单品不需要明细（「薯条(中)」就是一份薯条），别给单品硬凑套餐内容
        if not is_bundle(item):
            return None
        items = guess_items(name, menu)
        source = "guess"

    items = [it for it in items if str(it.get("name") or "").strip()]
    if not items:
        return None

    text = " ｜ ".join(
        it["name"] if it.get("plain") else f"{it['name']} ×{it['qty']}"
        for it in items)
    return {
        "items": items,
        "text": text,
        "source": source,
        "exact": source in ("menu", "cache"),
        "note": "以结算页为准" if source in ("menu", "cache") else "参考配置，以结算页为准",
    }


def is_bundle(item: Dict[str, Any]) -> bool:
    """是不是需要写明细的「多件装」（套餐 / 分享装）。"""
    import mcp_client
    return mcp_client._form(item) in ("combo", "share")


def main() -> None:
    ap = argparse.ArgumentParser(description="麦麦塔罗牌 · 套餐明细")
    ap.add_argument("--name", help="套餐名（配合 --menu-file 推断）")
    ap.add_argument("--menu-file", help="菜单 JSON，用来找真实的单品名")
    ap.add_argument("--raw", help="query-meal-detail 的返回 JSON，导入为官方明细")
    ap.add_argument("--code", help="餐品 code（配合 --raw 一起存）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    if args.raw:
        with open(args.raw, encoding="utf-8") as f:
            raw = json.load(f)
        got = ingest(raw, args.code, args.name)
        print(f"已导入明细 {len(got)} 项 -> {_detail_file()}")
        for it in got:
            print(f"  - {it['name']} ×{it['qty']}")
        if not got:
            sys.exit(1)
        return

    if not args.name:
        ap.error("需要 --name 或 --raw")

    menu = None
    if args.menu_file:
        with open(args.menu_file, encoding="utf-8") as f:
            menu = json.load(f)

    got = describe({"name": args.name}, menu)
    if not got:
        print("说不清这一份里有什么（不硬凑）")
        sys.exit(1)
    if args.json:
        print(json.dumps(got, ensure_ascii=False, indent=1))
    else:
        print(f"{args.name}：{got['text']}（{got['note']}）")


if __name__ == "__main__":
    main()
