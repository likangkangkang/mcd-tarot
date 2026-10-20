"""麦麦塔罗牌 · 连接器菜单归一化（仅标准库）。

把 WorkBuddy【连接器】mcd-mcp 的 `query-meals` 返回 JSON 归一化为塔罗引擎
可直接使用的菜单文件（[{"name","price","code","category"}, ...]）。

用法
----
    python menu_from_connector.py <query-meals响应.json> <输出菜单.json>

WorkBuddy 内的典型链路：
    1. 调用连接器工具 query-nearby-stores（beType=1）取 storeCode；
    2. 调用连接器工具 query-meals（orderType=1, beType=1）拉真实菜单，
       原始返回写入 raw.json；
    3. python scripts/menu_from_connector.py raw.json menu.json
    4. python scripts/tarot_engine.py --spread today --menu-file menu.json
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List


def normalize(raw: Any) -> List[Dict[str, Any]]:
    """把 query-meals 的原始返回归一化为菜单列表。

    兼容两种形态：
    - 完整业务返回: {"success": true, "data": {"categories": [...], "meals": {code: {...}}}}
    - 已是简化菜单: [{"name": ..., "price": ...}, ...]

    除名称/价格外，还会保留：餐品图 image、划线价 original_price、优惠类型
    discount_type、分类 tags，以及「套餐 / 单品 / 周边」形态 form——推荐时要靠这些
    信息判断该点套餐还是单品、能不能省钱。
    """
    # 形态二：本身就是菜单列表
    if isinstance(raw, list):
        return [it for it in (_norm_item(x) for x in raw if isinstance(x, dict)) if it["name"]]

    if not isinstance(raw, dict):
        return []
    data = raw.get("data") if isinstance(raw.get("data"), dict) else raw

    categories = data.get("categories") or []
    # code -> 分类名（分类名可能含换行，如 "鸡肉汉堡\\n/卷"）
    code_to_cat: Dict[str, str] = {}
    code_to_tags: Dict[str, List[str]] = {}
    if isinstance(categories, list):
        for cat in categories:
            if not isinstance(cat, dict):
                continue
            cat_name = str(cat.get("name", "")).replace("\n", "").strip()
            for m in cat.get("meals") or []:
                if isinstance(m, dict) and m.get("code"):
                    code = str(m["code"])
                    code_to_cat[code] = cat_name
                    tags = m.get("tags") or []
                    code_to_tags[code] = [str(t) for t in tags if t]

    meals = data.get("meals")
    out: List[Dict[str, Any]] = []
    if isinstance(meals, dict):
        # 标准形态：{code: {name, image, currentPrice, originalPrice, ...}}
        for code, detail in meals.items():
            if not isinstance(detail, dict):
                continue
            name = detail.get("name")
            if not name:
                continue
            tags = code_to_tags.get(str(code), [])
            out.append({
                "name": str(name),
                "code": str(code),
                "price": _to_float(detail.get("currentPrice") or detail.get("originalPrice")),
                "category": code_to_cat.get(str(code), ""),
                "original_price": _to_float(detail.get("originalPrice")),
                "discount_type": str(detail.get("discountType") or ""),
                "image": str(detail.get("image") or ""),
                "tags": tags,
                "form": form_of(str(name), tags),
            })
    elif isinstance(meals, list):
        out = [it for it in (_norm_item(x) for x in meals if isinstance(x, dict)) if it["name"]]
    return out


# 形态判断：套餐 / 单品 / 周边
_COMBO_WORDS = ("套餐", "三件套", "四件套", "分享餐", "双拼", "拼盘", "桶", "组合", "随心选", "随心配", "任选")
_GOODS_WORDS = ("周边", "贴纸", "毛绒", "玩具", "盲盒", "捶", "挠")


def form_of(name: str, tags: List[str] | None = None) -> str:
    """把餐品分成 combo（套餐）/ single（单品）/ goods（周边）。"""
    tags = tags or []
    if any(w in name for w in _GOODS_WORDS) or any(w in t for t in tags for w in _GOODS_WORDS):
        return "goods"
    if "套餐" in tags or any(w in name for w in _COMBO_WORDS):
        return "combo"
    return "single"


def _norm_item(it: Dict[str, Any]) -> Dict[str, Any]:
    name = it.get("name") or it.get("productName") or it.get("title") or ""
    code = it.get("code") or it.get("productCode") or it.get("id")
    price = it.get("price") or it.get("currentPrice") or it.get("salePrice")
    tags = [str(t) for t in (it.get("tags") or []) if t]
    return {
        "name": str(name),
        "code": str(code) if code is not None else None,
        "price": _to_float(price),
        "category": it.get("category") or it.get("categoryName") or "",
        "original_price": _to_float(it.get("original_price") or it.get("originalPrice")),
        "discount_type": str(it.get("discount_type") or it.get("discountType") or ""),
        "image": str(it.get("image") or it.get("imageUrl") or ""),
        "tags": tags,
        "form": form_of(str(name), tags),
    }


def _to_float(v: Any):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main() -> None:
    ap = argparse.ArgumentParser(description="把 query-meals 返回归一化为引擎可用菜单")
    ap.add_argument("raw", help="query-meals 的原始返回 JSON 文件")
    ap.add_argument("out", nargs="?", default=None, help="输出的菜单 JSON（可选）")
    ap.add_argument("--store", default=None, help="storeCode：给出时同时写入当日菜单缓存")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD，默认今天（配合 --store）")
    args = ap.parse_args()

    with open(args.raw, encoding="utf-8") as f:
        raw = json.load(f)
    menu = normalize(raw)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(menu, f, ensure_ascii=False, indent=1)
        print(f"归一化菜单 {len(menu)} 条 -> {args.out}")

    if args.store:
        import cache  # 同目录模块，避免脚本外依赖
        path = cache.save_menu(args.store, menu, args.date)
        print(f"归一化菜单 {len(menu)} 条 -> 缓存 {path}")

    if not args.out and not args.store:
        print(f"归一化菜单 {len(menu)} 条（未指定输出，仅统计）")
    if not menu:
        sys.exit(1)


if __name__ == "__main__":
    main()
