"""麦麦塔罗牌 · 自检脚本（换季/上新后跑一次，确认牌面映射没坏）。

检查项
------
1. **价格覆盖**：78 张牌能否在菜单里匹配到带价格的真实餐品（匹配不到 = 用户会看到裸关键词）。
2. **误映射**：是否落到了套餐/周边/玩具这类不合适的对象（如「薯条 → 薯条脆卜卜毛绒周边」）。
3. **重复牌**：三张牌阵在同一天是否抽到同一张牌（不应发生）。
4. **菜品重复**：三张牌阵是否给出同一道菜（尽量不重样）。
5. **关键词命中率**：有多少张牌靠的是兜底关键词而非真实菜品。

用法
----
    python3 scripts/selfcheck.py                       # 用最近缓存的真实菜单
    python3 scripts/selfcheck.py --menu-file menu.json
    python3 scripts/selfcheck.py --json report.json    # 机器可读
    python3 scripts/selfcheck.py --days 180            # 采样天数（默认 365）

退出码：0 全部通过；1 发现问题（便于定时任务报警）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, timedelta
from typing import Any, Dict, List

import cache
import mcp_client
import tarot_deck
import tarot_engine

SUSPICIOUS = re.compile(r"套餐|三件套|双人|单人|组合|周边|毛绒|贴纸|玩具|盲盒|桶")


def _load_menu(path: str | None) -> tuple[List[Dict[str, Any]], str]:
    if path:
        with open(path, encoding="utf-8") as f:
            return json.load(f), f"文件 {path}"
    cached = cache.latest_menu()
    if cached:
        store = cache.load_store() or {}
        label = store.get("store_name") or store.get("store_code") or "未知门店"
        return cached, f"缓存（{label}）"
    return mcp_client.FALLBACK_MENU, "内置示例菜单（未找到真实菜单缓存）"


def run(menu: List[Dict[str, Any]], days: int) -> Dict[str, Any]:
    no_price: List[str] = []
    suspicious: List[Dict[str, str]] = []
    fallback_used: List[str] = []

    for card in tarot_deck.ALL_CARDS:
        item = mcp_client.resolve_item(card, menu)
        name = str(item.get("name", ""))
        if item.get("price") is None:
            no_price.append(f"{card['name_cn']} → {name}")
            fallback_used.append(card["name_cn"])
        if SUSPICIOUS.search(name):
            suspicious.append({"card": card["name_cn"], "food": name})

    spreads = ["trinity", "timeline", "choice"]
    dup_cards = 0
    dup_foods = 0
    samples = 0
    d0 = date.today()
    for i in range(days):
        d = (d0 + timedelta(days=i)).isoformat()
        for sp in spreads:
            drawn = tarot_engine.draw(sp, d)
            ids = [c["id"] for c, _o, _p in drawn]
            samples += 1
            if len(ids) != len(set(ids)):
                dup_cards += 1
            used: set = set()
            foods: List[Any] = []
            for c, _o, _p in drawn:
                f = mcp_client.resolve_item(c, menu, exclude=used).get("name")
                foods.append(f)
                used.add(str(f))
            if len(set(foods)) != len(foods):
                dup_foods += 1

    total = len(tarot_deck.ALL_CARDS)
    report = {
        "menu_size": len(menu),
        "cards": total,
        "price_coverage": f"{total - len(no_price)}/{total}",
        "no_price": no_price,
        "suspicious": suspicious,
        "fallback_rate": f"{len(fallback_used)}/{total}",
        "dup_card_samples": f"{dup_cards}/{samples}",
        "dup_food_samples": f"{dup_foods}/{samples}",
        "ok": not no_price and not suspicious and dup_cards == 0,
    }
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description="麦麦塔罗牌自检")
    ap.add_argument("--menu-file", default=None, help="指定菜单 JSON；默认用最近缓存菜单")
    ap.add_argument("--days", type=int, default=365, help="重复牌采样天数（默认 365）")
    ap.add_argument("--json", dest="json_out", default=None, help="把报告写成 JSON")
    args = ap.parse_args()

    menu, source = _load_menu(args.menu_file)
    report = run(menu, args.days)
    report["menu_source"] = source

    icon = "✅" if report["ok"] else "⚠️"
    print(f"{icon} 麦麦塔罗牌自检 · 菜单来源：{source}（{report['menu_size']} 条）\n")
    print(f"- 价格覆盖：{report['price_coverage']}")
    if report["no_price"]:
        print(f"  · 无价格（会退化成裸关键词）：{', '.join(report['no_price'])}")
    print(f"- 关键词兜底：{report['fallback_rate']}")
    if report["suspicious"]:
        print("- 疑似误映射（套餐/周边）：")
        for s in report["suspicious"]:
            print(f"  · {s['card']} → {s['food']}")
    print(f"- 重复牌：{report['dup_card_samples']}（{args.days} 天 × 3 牌阵）")
    print(f"- 同阵重复菜品：{report['dup_food_samples']}")

    if report["ok"]:
        print("\n结论：牌面映射健康，可以放心抽。")
    else:
        print("\n结论：需要修 mcd_keywords 或匹配规则。常见动作：")
        print("  1) 把新菜名补进 tarot_deck.py 对应牌的 mcd_keywords；")
        print("  2) 确认菜单缓存是最新的（cache.py menu get --store <code>）；")
        print("  3) 改完重跑本脚本，直到价格覆盖 78/78。")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print(f"\n[JSON] {args.json_out}")

    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
