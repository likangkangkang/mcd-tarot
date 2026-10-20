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


def pack(out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    root_name = SKILL_ROOT.name  # mcd-tarot —— zip 里的顶层目录
    written = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        files = sorted(p for p in SKILL_ROOT.rglob("*") if p.is_file())
        for f in files:
            rel = f.relative_to(SKILL_ROOT)
            if EXCLUDE_DIRS & set(rel.parts[:-1]) or rel.name in EXCLUDE_FILES:
                continue
            zf.write(f, f"{root_name}/{rel.as_posix()}")
            written += 1
    return out_path, written


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="打包 mcd-tarot 技能包 zip")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="输出 zip 路径")
    args = ap.parse_args(argv)

    out = Path(args.out).expanduser()
    _, written = pack(out)
    size_kb = out.stat().st_size / 1024 if out.exists() else 0
    print(f"[技能包] {out}  ({written} 个文件, {size_kb:.0f} KB)")
    print("把它发给对方：【专家·技能·连接器】→ 技能 → 添加技能 → 上传技能 → 选这个 zip")
    return 0


if __name__ == "__main__":
    sys.exit(main())
