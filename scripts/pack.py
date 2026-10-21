"""麦麦塔罗牌 · 打包成可上传的技能包（zip）。

WorkBuddy 的【技能 → 添加技能 → 上传技能】只认本地技能包 zip，
所以分享给别人时给 zip，而不是让他 git clone（云端版不会克隆第三方仓库）。

zip 内部结构（顶层必须是技能名目录）：

    mcd-tarot/
    ├── SKILL.md
    ├── scripts/
    ├── references/
    └── assets/

用法
----
    python3 scripts/pack.py                       # 产出 dist/mcd-tarot-skill.zip
    python3 scripts/pack.py --out ~/Desktop/x.zip
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = SKILL_ROOT / "dist" / "mcd-tarot-skill.zip"

# 不进技能包：版本控制、Python 缓存、系统垃圾、已有产物
EXCLUDE_DIRS = {".git", "__pycache__", ".pytest_cache", ".idea", ".vscode", "dist"}
EXCLUDE_FILES = {".DS_Store", ".gitignore", "Thumbs.db"}

# 开放平台硬限制：zip 内最多「根目录 / 二级目录 / 文件」三层。
# 例：mcd-tarot/scripts/quick.py 合法；mcd-tarot/scripts/tests/x.py 会被判「目录层级超限」。
MAX_DEPTH = 3


def collect():
    """返回 [(绝对路径, zip 内相对路径)]，并校验层级。"""
    items = []
    too_deep = []
    for f in sorted(p for p in SKILL_ROOT.rglob("*") if p.is_file()):
        rel = f.relative_to(SKILL_ROOT)
        if EXCLUDE_DIRS & set(rel.parts[:-1]) or rel.name in EXCLUDE_FILES:
            continue
        # +1 = zip 里的顶层目录 mcd-tarot/
        if len(rel.parts) + 1 > MAX_DEPTH:
            too_deep.append(f"{SKILL_ROOT.name}/{rel.as_posix()}")
            continue
        items.append((f, f"{SKILL_ROOT.name}/{rel.as_posix()}"))
    return items, too_deep


def pack(out_path: Path):
    items, too_deep = collect()
    if too_deep:
        print("目录层级超限（开放平台只支持 根/二级/文件 三层），请移除子目录嵌套：")
        for p in too_deep:
            print(f"  - {p}")
        sys.exit(1)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f, arc in items:
            zf.write(f, arc)
    return out_path, len(items)


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="打包 mcd-tarot 技能包 zip")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="输出 zip 路径")
    args = ap.parse_args(argv)

    out = Path(args.out).expanduser()
    _, written = pack(out)
    size_kb = out.stat().st_size / 1024 if out.exists() else 0
    print(f"[技能包] {out}  ({written} 个文件, {size_kb:.0f} KB)  层级校验 ≤{MAX_DEPTH} 层 通过")
    print("把它发给对方：【专家·技能·连接器】→ 技能 → 添加技能 → 上传技能 → 选这个 zip")
    return 0


if __name__ == "__main__":
    sys.exit(main())
