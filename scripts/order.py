"""麦麦塔罗牌 · 下单辅助（本地记录 + 确认卡，绝不代替用户付款）。

真实下单必须由 WorkBuddy 的 mcd-mcp 连接器完成：
    calculate-price  →  create-order  →  用户自己打开支付链接付款
本脚本只做三件「不碰钱」的事：
    1. 把要下的单整理成一张可核对的确认卡（门店 / 餐品 / 数量 / 预估金额 / 取餐方式）；
    2. 记录订单号与支付链接，方便之后 query-order 查状态；
    3. 留存历史，避免重复下单。

用法
----
    # 1) 整理确认卡（只读，不下单）
    python3 scripts/order.py draft --store 1990262001 --store-name "南京徐庄路快捷小站" \
        --items "1100:1,1401:1" --way locker-in --way-name "外带"

    # 2) 连接器 create-order 成功后登记（支付仍由用户完成）
    python3 scripts/order.py record --order-id 123456 --pay-url "https://..." --total 34.0

    # 3) 支付完成后更新状态 / 查看历史
    python3 scripts/order.py update --order-id 123456 --status paid
    python3 scripts/order.py list
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import combo_detail  # 同目录模块：套餐明细

CACHE = Path(os.environ.get("MCD_TAROT_CACHE") or (Path.home() / ".cache" / "mcd-tarot"))
ORDERS = CACHE / "orders.json"


def _load() -> Dict[str, List[Dict[str, Any]]]:
    if ORDERS.exists():
        try:
            data = json.loads(ORDERS.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {"drafts": data.get("drafts", []), "orders": data.get("orders", [])}
        except (json.JSONDecodeError, OSError):
            pass
    return {"drafts": [], "orders": []}


def _save(data: Dict[str, List[Dict[str, Any]]]) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    ORDERS.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def _menu_lookup(store: str) -> Dict[str, Dict[str, Any]]:
    """从当日菜单缓存里按 code 查餐品，用于生成确认卡。"""
    try:
        import cache  # 同目录模块
        menu = cache.load_menu(store) or cache.latest_menu() or []
    except Exception:  # noqa: BLE001
        return {}
    return {str(it.get("code")): it for it in menu if it.get("code")}


def _fmt(v: Optional[float]) -> str:
    if v is None:
        return "—"
    return f"¥{v:.2f}".rstrip("0").rstrip(".") if v != int(v) else f"¥{int(v)}"


def _menu_list(store: str) -> List[Dict[str, Any]]:
    """当日菜单（用于查套餐明细）。"""
    try:
        import cache  # 同目录模块
        return cache.load_menu(store) or cache.latest_menu() or []
    except Exception:  # noqa: BLE001
        return []


def cmd_draft(args: argparse.Namespace) -> None:
    lookup = _menu_lookup(args.store)
    menu = _menu_list(args.store)
    items: List[Dict[str, Any]] = []
    total = 0.0
    unknown = []
    for part in args.items.split(","):
        if not part.strip():
            continue
        code, _, qty = part.partition(":")
        code = code.strip()
        qty = int(qty or 1)
        info = lookup.get(code)
        if not info:
            unknown.append(code)
            items.append({"code": code, "name": f"未知餐品({code})", "qty": qty,
                          "price": None, "original_price": None})
            continue
        price = info.get("price")
        # 套餐把里面装了什么写清楚，下单前才知道自己点了啥
        detail = combo_detail.describe(info, menu)
        items.append({"code": code, "name": info.get("name", ""), "qty": qty,
                      "price": price, "original_price": info.get("original_price"),
                      "form": info.get("form", ""),
                      "combo_detail": (detail or {}).get("text") or ""})
        if price is not None:
            total += float(price) * qty

    draft = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "store": args.store,
        "store_name": args.store_name,
        "way": args.way,
        "way_name": args.way_name,
        "items": items,
        "estimate": round(total, 2) if total else None,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "status": "draft",
    }
    data = _load()
    data["drafts"].append(draft)
    _save(data)

    lines = ["## 🧾 订单确认（还没下单）\n",
             f"- 门店：{args.store_name or args.store}",
             f"- 取餐方式：{args.way_name or args.way}"]
    for it in items:
        price = _fmt(it.get("price"))
        orig = it.get("original_price")
        extra = f"（原价 {_fmt(orig)}）" if orig and it.get("price") and orig > it["price"] else ""
        lines.append(f"- {it['name']} ×{it['qty']}　{price}{extra}")
        if it.get("combo_detail"):
            lines.append(f"  - 📦 内含：{it['combo_detail']}")
    if total:
        lines.append(f"\n**预估合计：{_fmt(total)}**（最终以 calculate-price 实时计算为准）")
    lines.append("\n确认无误请回复「确认下单」；要改数量或餐品直接说。"
                 "正式下单由我在连接器里完成，付款链接会发给你，**钱由你自己付**。")
    print("\n".join(lines))

    if unknown:
        print(f"\n[warn] 以下 code 没在当日菜单缓存里找到，建议先刷新菜单：{', '.join(unknown)}",
              file=sys.stderr)


def cmd_record(args: argparse.Namespace) -> None:
    data = _load()
    data["orders"].append({
        "order_id": str(args.order_id),
        "pay_url": args.pay_url or "",
        "total": args.total,
        "status": "created",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    _save(data)
    print(f"已记录订单 {args.order_id}（待支付）。支付链接只有你能打开，我不会代付。")
    if args.pay_url:
        print(f"支付链接：{args.pay_url}")


def cmd_update(args: argparse.Namespace) -> None:
    data = _load()
    hit = False
    for o in data["orders"]:
        if str(o.get("order_id")) == str(args.order_id):
            o["status"] = args.status
            o["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            hit = True
    _save(data)
    print(f"订单 {args.order_id} 状态已更新为 {args.status}" if hit else f"没找到订单 {args.order_id}")


def cmd_list(args: argparse.Namespace) -> None:
    data = _load()
    orders = data["orders"][-args.limit:]
    if not orders:
        print("还没有下过单。")
        return
    for o in orders:
        print(f"- {o['created_at']}  #{o['order_id']}  {_fmt(o.get('total'))}  [{o.get('status')}]")
        if o.get("pay_url"):
            print(f"  支付链接：{o['pay_url']}")


def main() -> None:
    ap = argparse.ArgumentParser(description="麦麦塔罗牌下单辅助（不代替付款）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("draft", help="生成订单确认卡（只读）")
    p.add_argument("--store", required=True, help="storeCode")
    p.add_argument("--store-name", default="", help="门店名")
    p.add_argument("--items", required=True, help='餐品，格式 "code:qty,code:qty"')
    p.add_argument("--way", default="locker-in", help="取餐方式 code（来自 calculate-price 的 takeWayList）")
    p.add_argument("--way-name", default="外带", help="取餐方式名称")

    p2 = sub.add_parser("record", help="登记已创建的订单")
    p2.add_argument("--order-id", required=True)
    p2.add_argument("--pay-url", default="")
    p2.add_argument("--total", type=float, default=None)

    p3 = sub.add_parser("update", help="更新订单状态")
    p3.add_argument("--order-id", required=True)
    p3.add_argument("--status", required=True, choices=["paid", "cancelled", "failed"])

    p4 = sub.add_parser("list", help="查看历史订单")
    p4.add_argument("--limit", type=int, default=5)

    args = ap.parse_args()
    {"draft": cmd_draft, "record": cmd_record, "update": cmd_update, "list": cmd_list}[args.cmd](args)


if __name__ == "__main__":
    main()
