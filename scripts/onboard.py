"""麦麦塔罗牌 · 首次招呼（onboarding）。

WorkBuddy 的 Skill **没有「安装后自动运行」的钩子**：技能只在对话命中它的
description 时才被加载。所以「装好就打招呼」实际落在**第一次被唤起的那轮对话**：

    首次命中 → 自我介绍 + 说明能做什么 + 问「要不要看今日运势？（是 / 否）」
              → 停下来等用户回答，不擅自抽牌
    答「是」  → 走抽牌出图；答「否」→ 简短收尾
    之后每次  → 不再打招呼，直接玩法

首次与否由状态文件判断（默认 `~/.cache/mcd-tarot/onboarded.json`，
可用环境变量 `MCD_TAROT_CACHE` 覆盖）。删掉这个文件即可重新体验首次招呼。

CLI
---
    python3 scripts/onboard.py --check              # JSON: {first_time, greeting}
    python3 scripts/onboard.py --greeting           # 只打印招呼话术
    python3 scripts/onboard.py --answer 是          # JSON: {answer, reply}
    python3 scripts/onboard.py --done               # 标记「已打过招呼」
    python3 scripts/onboard.py --reset              # 恢复为「未招呼」（重新自我介绍）
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Optional

CACHE_DIR = Path(os.environ.get("MCD_TAROT_CACHE", Path.home() / ".cache" / "mcd-tarot"))
ONBOARDED_PATH = CACHE_DIR / "onboarded.json"

GREETING = """你好，我是 **麦麦塔罗牌** 🃏🍔

我把麦当劳的菜单摊成一副 78 张的塔罗牌：每天替你抽一张，配一张把汉堡画成圣像的牌面，落在今天菜单里的一道菜上，顺手把能用的券叠好。看中了只要回一句「**就它**」，剩下的我来跑——付款你自己完成，钱我不碰。

我能帮你三件事：

- **今日运势**：按今天抽一张牌，告诉你今天适合吃哪一道
- **有想问的事**：一句话提问，我抽一张牌当它的回答
- **看中就下单**：核对实时价格 → 下单 → 支付链接给你

要不要现在翻开你的 **今日运势**？回复「**是**」我就抽，「**否**」我就不打扰。"""

REPLY_YES = "好，牌已经洗好了——这就翻开你的今日运势。"
REPLY_NO = "好，那我先收起牌。想吃的时候随时叫我，我在。"
REPLY_UNKNOWN = "回「**是**」我立刻抽一张，回「**否**」我就不打扰——一个字就够。"

_YES = re.compile(
    r"^\s*(是|好|好的|可以|要|要的|来|来吧|来一个|开始|开启|抽|抽吧|抽一张|试试|试一下|"
    r"ok|okay|y|yes|yeah|sure|go|当然|乐意|没问题)\s*[。.!！,，~～]*\s*$", re.I)
_NO = re.compile(
    r"^\s*(否|不|不要|不用|不抽|算了|先不|下次|不用了|不必|算了\s*吧|"
    r"no|n|nope|later|skip)\s*[。.!！,，~～]*\s*$", re.I)


def first_time() -> bool:
    """是否从未打过招呼。"""
    try:
        return not json.loads(ONBOARDED_PATH.read_text(encoding="utf-8")).get("greeted")
    except (OSError, json.JSONDecodeError, AttributeError):
        return True


def mark_done(note: str = "") -> Path:
    """标记已招呼（幂等）。"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ONBOARDED_PATH.write_text(
        json.dumps({"greeted": True, "note": note}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    return ONBOARDED_PATH


def reset() -> Path:
    """清除招呼标记，恢复成首次。"""
    try:
        ONBOARDED_PATH.unlink()
    except FileNotFoundError:
        pass
    return ONBOARDED_PATH


def check() -> Dict:
    """是否首次 + 要不要发招呼文案。"""
    is_first = first_time()
    return {"first_time": is_first, "greeting": GREETING if is_first else ""}


def parse_answer(text: str) -> Dict:
    """把用户的回复归一化成 yes / no / unknown。"""
    raw = (text or "").strip()
    if _YES.match(raw):
        return {"answer": "yes", "reply": REPLY_YES, "draw": True}
    if _NO.match(raw):
        return {"answer": "no", "reply": REPLY_NO, "draw": False}
    return {"answer": "unknown", "reply": REPLY_UNKNOWN, "draw": False}


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(
        description="麦麦塔罗牌 · 首次招呼：自我介绍并问是否开启今日运势")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="是否首次（JSON）")
    g.add_argument("--greeting", action="store_true", help="打印招呼话术")
    g.add_argument("--answer", metavar="TEXT", help="解析用户回答：是 / 否")
    g.add_argument("--done", action="store_true", help="标记已招呼")
    g.add_argument("--reset", action="store_true", help="恢复为首次")
    ap.add_argument("--json", action="store_true", help="招呼/环节也用 JSON 输出")
    args = ap.parse_args(argv)

    if args.check:
        print(json.dumps(check(), ensure_ascii=False))
    elif args.greeting:
        print(json.dumps({"greeting": GREETING}, ensure_ascii=False) if args.json
              else GREETING)
    elif args.answer is not None:
        out = parse_answer(args.answer)
        if out["answer"] != "unknown":
            mark_done(out["answer"])
        print(json.dumps(out, ensure_ascii=False))
    elif args.done:
        print(json.dumps({"marked": str(mark_done("greeted"))}, ensure_ascii=False))
    else:
        print(json.dumps({"reset": str(reset())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
