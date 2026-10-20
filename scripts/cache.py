"""麦麦塔罗牌 · 本地缓存（门店记忆 + 当日菜单缓存），仅标准库。

解决两件事
----------
1. **不用每次都问门店**：记住上次用过的门店（storeCode + 门店名），下次直接复用；
   只有用户换城市、换店、或缓存被清掉时才需要重新查。
2. **不用每次都重拉菜单**：菜单按「门店 + 日期」缓存，同一天第二次抽牌秒回，
   不再重复调用连接器。

缓存位置
--------
默认 `<skill>/.cache/`（可用环境变量 `MCD_TAROT_CACHE` 覆盖），不入 git：

    .cache/store.json                      # 上次门店
    .cache/menus/menu-<store>-<date>.json  # 当日菜单

CLI
---
    python3 scripts/cache.py store get                 # 命中打印 JSON，未命中退出码 1
    python3 scripts/cache.py store set --code 1990262001 --name "南京徐庄路快捷小站" --city 南京
    python3 scripts/cache.py menu get --store 1990262001 [--date 2026-10-20]
    python3 scripts/cache.py menu save --store 1990262001 --file menu.json
    python3 scripts/cache.py clear --all
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

SKILL_ROOT = Path(__file__).resolve().parent.parent


def cache_dir() -> Path:
    """缓存根目录：环境变量优先，默认 skill 下 .cache。"""
    env = os.environ.get("MCD_TAROT_CACHE")
    root = Path(env).expanduser() if env else SKILL_ROOT / ".cache"
    (root / "menus").mkdir(parents=True, exist_ok=True)
    return root


def _store_file() -> Path:
    return cache_dir() / "store.json"


def _menu_file(store_code: str, day: str) -> Path:
    return cache_dir() / "menus" / f"menu-{store_code}-{day}.json"


# ---------------------------------------------------------------------------
# 门店记忆
# ---------------------------------------------------------------------------
def load_store() -> Optional[Dict[str, Any]]:
    f = _store_file()
    if not f.exists():
        return None
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) and data.get("store_code") else None


def save_store(store_code: str, store_name: str = "", city: str = "") -> Dict[str, Any]:
    data = {
        "store_code": str(store_code),
        "store_name": store_name or "",
        "city": city or "",
        "saved_at": date.today().isoformat(),
    }
    _store_file().write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def store_label(store: Optional[Dict[str, Any]]) -> str:
    """人类可读的门店名，用于开场白（不暴露 storeCode）。"""
    if not store:
        return ""
    return store.get("store_name") or "你常去的门店"


# ---------------------------------------------------------------------------
# 菜单缓存
# ---------------------------------------------------------------------------
def menu_path(store_code: str, day: Optional[str] = None) -> Path:
    return _menu_file(str(store_code), day or date.today().isoformat())


def load_menu(store_code: str, day: Optional[str] = None) -> Optional[list]:
    f = menu_path(store_code, day)
    if not f.exists():
        return None
    try:
        menu = json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return menu if isinstance(menu, list) and menu else None


def save_menu(store_code: str, menu: list, day: Optional[str] = None) -> Path:
    f = menu_path(store_code, day)
    f.write_text(json.dumps(menu, ensure_ascii=False, indent=1), encoding="utf-8")
    return f


def latest_menu() -> Optional[list]:
    """取最近一份缓存菜单（自检脚本用：没有真实菜单时退回内置示例菜单）。"""
    menus = sorted((cache_dir() / "menus").glob("menu-*.json"), key=lambda p: p.stat().st_mtime)
    for f in reversed(menus):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, list) and data:
            return data
    return None


def clear(what: str = "all") -> None:
    if what in ("all", "store"):
        _store_file().unlink(missing_ok=True)
    if what in ("all", "menus"):
        for f in (cache_dir() / "menus").glob("menu-*.json"):
            f.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="麦麦塔罗牌本地缓存")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_store = sub.add_parser("store", help="门店记忆")
    p_store.add_argument("action", choices=["get", "set"])
    p_store.add_argument("--code", help="storeCode")
    p_store.add_argument("--name", default="", help="门店名")
    p_store.add_argument("--city", default="", help="城市（可选）")

    p_menu = sub.add_parser("menu", help="菜单缓存")
    p_menu.add_argument("action", choices=["get", "save", "path"])
    p_menu.add_argument("--store", required=True, help="storeCode")
    p_menu.add_argument("--date", default=None, help="YYYY-MM-DD，默认今天")
    p_menu.add_argument("--file", default=None, help="menu save 时的菜单 JSON 文件")

    p_clear = sub.add_parser("clear", help="清缓存")
    p_clear.add_argument("--what", choices=["all", "store", "menus"], default="all")

    args = ap.parse_args()

    if args.cmd == "store":
        if args.action == "get":
            data = load_store()
            if not data:
                print("[]")
                sys.exit(1)
            print(json.dumps(data, ensure_ascii=False))
        else:
            if not args.code:
                print("缺少 --code", file=sys.stderr)
                sys.exit(2)
            print(json.dumps(save_store(args.code, args.name, args.city), ensure_ascii=False))

    elif args.cmd == "menu":
        if args.action == "path":
            print(menu_path(args.store, args.date))
        elif args.action == "get":
            menu = load_menu(args.store, args.date)
            if not menu:
                print("[]")
                sys.exit(1)
            print(json.dumps({"path": str(menu_path(args.store, args.date)), "count": len(menu),
                              "menu": menu}, ensure_ascii=False))
        else:
            if not args.file:
                print("缺少 --file", file=sys.stderr)
                sys.exit(2)
            menu = json.loads(Path(args.file).read_text(encoding="utf-8"))
            print(save_menu(args.store, menu, args.date))

    else:
        clear(args.what)
        print(f"已清理缓存（{args.what}）")


if __name__ == "__main__":
    main()
