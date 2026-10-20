"""麦麦塔罗牌 · 快速抽牌（零网络、零渲染依赖）。

为什么需要它
------------
一次完整体验原本要串行走：查门店 → 拉菜单（90+ SKU）→ 拉订单 → 拉券包 →
拉可领券 → 拉积分 → 抽牌 → 渲染图片。七步里五步是网络往返，慢的不是引擎
（抽牌本身只要 5 毫秒），而是这些往返和图片渲染。

quick.py 只用本地缓存做三件事：读门店 → 读当日菜单 → 读口味画像 → 抽牌。
全程不联网、不下载图片、不启动 Chrome，通常 100 毫秒内出结果。

缓存怎么来
----------
第一次用（或换门店、换日期）时，仍要走一次连接器把数据落到本地：

    python3 scripts/cache.py store set --code <storeCode> --name "<门店名>"
    python3 scripts/menu_from_connector.py raw.json --store <storeCode>   # 存当日菜单
    python3 scripts/profile.py build --orders ... --wallet ... --available ... --account ...

之后同一天再怎么抽都是秒回。

用法
----
    python3 scripts/quick.py                          # 今日一张
    python3 scripts/quick.py --question "明天面试能顺利吗"   # 按问题抽一张预测
    python3 scripts/quick.py --mood "想被哄一下"       # 带心情
    python3 scripts/quick.py --at "2026-10-20 12:30"  # 指定点餐时间
    python3 scripts/quick.py --svg card.svg           # 同时出牌面（单张）
    python3 scripts/quick.py --inline                 # 把牌面 SVG 打到 stdout（内联进对话框用）
    python3 scripts/quick.py --lean                   # 精简文字（清单/形态/价格交给牌面图）
    python3 scripts/quick.py --json out.json          # 结构化结果
    python3 scripts/quick.py --allow-fallback         # 没缓存时用内置示例菜单

退出码：0 正常；3 没有可用菜单（此时提示先拉一次菜单）。
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import cache
import mcp_client
import profile as profile_mod
import tarot_engine
import tarot_deck


def main() -> None:
    ap = argparse.ArgumentParser(description="麦麦塔罗牌 · 零网络快速抽牌（单张预测）")
    ap.add_argument("--spread", default="today", choices=["today"],
                    help="牌阵（当前仅支持单张预测 today）")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD，默认今天")
    ap.add_argument("--at", default=None, help='点餐时间 "YYYY-MM-DD HH:MM"，默认现在')
    ap.add_argument("--mood", default=None, help="今天的心情")
    ap.add_argument("--question", default=None,
                    help="你关心的问题；给出时牌作为这个问题的回答，不同问题抽到不同牌")
    ap.add_argument("--svg", default=None, help="同时生成牌面 SVG 的路径（单张）")
    ap.add_argument("--inline", action="store_true",
                    help="把牌面 SVG（宽 680，单张）打到 stdout，供内联呈现在对话框")
    ap.add_argument("--lean", action="store_true",
                    help="精简文字：清单/形态/价格交给牌面图，文字只留解读与行动引导")
    ap.add_argument("--png", default=None, help="同时生成牌面 PNG（需要 Chrome，慢约 1–2 秒）")
    ap.add_argument("--photo", action="store_true", help="牌面小票旁附圆形餐品图（会联网下图）")
    ap.add_argument("--json", dest="json_out", default=None, help="把结果写成 JSON")
    ap.add_argument("--no-profile", action="store_true", help="不用口味画像")
    ap.add_argument("--single-only", action="store_true", help="关掉套餐优先")
    ap.add_argument("--king", action="store_true",
                    help="只在 4 张国王（权杖/圣杯/宝剑/星币）里抽一张")
    ap.add_argument("--allow-fallback", action="store_true",
                    help="没有菜单缓存时用内置示例菜单（结果不代表真实门店）")
    ap.add_argument("--timing", action="store_true", help="打印各步骤耗时")
    args = ap.parse_args()

    t0 = time.perf_counter()
    marks = []

    def mark(label: str) -> None:
        marks.append((label, (time.perf_counter() - t0) * 1000))

    # --- 门店 ---
    store = cache.load_store()
    mark("门店")
    store_name = store.get("store_name") if store else ""

    # --- 菜单：只读缓存，绝不联网 ---
    menu = None
    if store:
        menu = cache.load_menu(store["store_code"], args.date)
    if not menu:
        menu = cache.latest_menu()          # 换日期时退回最近一份，不至于没得抽
    mark("菜单")

    if not menu:
        if not args.allow_fallback:
            print("没有可用的菜单缓存。先跑一次连接器把菜单落到本地：", file=sys.stderr)
            print("  python3 scripts/menu_from_connector.py raw.json --store <storeCode>",
                  file=sys.stderr)
            print("或者加 --allow-fallback 用内置示例菜单先玩。", file=sys.stderr)
            sys.exit(3)
        menu = mcp_client.FALLBACK_MENU

    # --- 画像：过期也先用着，旧偏好总比没有强 ---
    prof = None if args.no_profile else profile_mod.load_profile()
    stale = profile_mod.is_stale(6.0, prof) if prof else False
    mark("画像")

    combo_first = not args.single_only
    card_pool = None
    if args.king:
        card_pool = [c for c in tarot_deck.ALL_CARDS if c.get("rank") == "king"]
    result = tarot_engine.do_reading(
        args.spread, args.date, args.mood, menu=menu,
        at=args.at, profile=prof, combo_first=combo_first,
        lean=args.lean, question=args.question, card_pool=card_pool)
    mark("抽牌")

    if args.inline:
        import tarot_card
        # 牌面在前、文字在后：先打 SVG，再打解读
        print(tarot_card.render_inline(result, photo=args.photo))
        print()

    print(result["markdown"])

    source = "缓存菜单" if menu is not mcp_client.FALLBACK_MENU else "内置示例菜单"
    bits = [f"菜单来源={source}（{len(menu)} 项）"]
    if store_name:
        bits.append(f"门店={store_name}")
    bits.append(f"口味画像={'已用' if prof else '未用'}")
    print("\n[" + "　".join(bits) + "]")
    if stale:
        print("[提示] 口味画像超过 6 小时，券包和常点可能有变化；"
              "想刷新就跑一次 profile.py build。")

    if args.svg or args.png:
        import tarot_card
        try:
            if args.png:
                path = tarot_card.render_png(result, args.png, photo=args.photo)
            else:
                path = tarot_card.render(result, args.svg, photo=args.photo)
            print(f"[牌面] {path}")
        except RuntimeError as exc:
            print(f"[牌面] {exc}", file=sys.stderr)
        mark("牌面")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
        print(f"[JSON] {args.json_out}")

    mark("总计")
    if args.timing:
        print("\n[耗时] " + "　".join(f"{k} {v:.0f}ms" for k, v in marks))


if __name__ == "__main__":
    main()
