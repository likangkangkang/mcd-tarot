# 安装与维护（WorkBuddy 用户级 Skill）

## 单一真源
- 唯一来源就是这个目录：`~/.workbuddy/skills/mcd-tarot/`（WorkBuddy 直接加载的「主 skill」）。
- 目录本身就是一个 git 仓库，`origin` = https://github.com/likangkangkang/mcd-tarot
- **不再维护第二份副本**：改动直接在主 skill 里做，然后 `git commit && git push`；仓库与本地永远同一份代码。

## 目录结构
```
mcd-tarot/
├── SKILL.md            # 技能定义、工作流、触发边界
├── scripts/            # 牌组 / 引擎 / 缓存 / 自检 / 塔罗牌面 / 下单辅助 / 连接器菜单归一化 / 测试
│   ├── tarot_deck.py       tarot_engine.py    mcp_client.py
│   ├── menu_from_connector.py   cache.py      selfcheck.py    tarot_card.py    order.py
│   └── tests/test_tarot_engine.py
├── references/         # README、MCP 集成说明、示例解读、参赛材料、本文件
├── assets/             # 配置模板：mcp-config.example.json、.env.example、requirements.txt
└── (运行时缓存不在本目录：~/.cache/mcd-tarot/)
```

## 更新方式（单份代码，无需覆盖）
```bash
cd ~/.workbuddy/skills/mcd-tarot
git pull            # 从仓库取最新
python3 scripts/tests/test_tarot_engine.py
python3 scripts/selfcheck.py     # 换季后建议跑
```
改完想发版：
```bash
git add -A && git commit -m "..." && git push
```

## 本地运行时数据
- 位置：`~/.cache/mcd-tarot/`（可用 `MCD_TAROT_CACHE` 覆盖），不放在 skill 目录，也不会被打包/提交。
- `store.json`：上次门店（storeCode + 门店名 + 城市），用于免去每次询问。
- `menus/menu-<store>-<date>.json`：当日菜单缓存，同一天只拉一次连接器。
- 清理：`python3 scripts/cache.py clear --all`；只清门店：`--what store`。

## 自检
```bash
cd ~/.workbuddy/skills/mcd-tarot
python3 scripts/tests/test_tarot_engine.py     # 20 项单元测试
python3 scripts/selfcheck.py                   # 价格覆盖 / 误映射 / 重复牌
python3 scripts/tarot_engine.py --spread today  # 离线抽牌（无真实菜单时用示例菜单）
```

## 菜单词表维护
牌面关键词按 2026-10 的真实菜单校准。麦当劳换季上新后可能出现「某张牌给的餐品没有价格」，处理方式：
1. 拉一次真实菜单并写缓存：`python3 scripts/menu_from_connector.py <raw.json> --store <storeCode>`；
2. 跑 `python3 scripts/selfcheck.py`，看「无价格」与「疑似误映射」列表；
3. 改 `scripts/tarot_deck.py` 里对应牌的 `mcd_keywords`，优先用真实菜单里的完整菜名；
4. 重跑自检直到价格覆盖 78/78。

## 变更记录（相对仓库 c72da94 的演进，现已全部在主 skill 中）
- 连接器优先：新增 `menu_from_connector.py`，引擎支持 `--menu-file` / `menu` 参数。
- 抽签修正：`draw()` 改为无放回抽样，同一牌阵不再出现重复牌。
- 匹配修正：`resolve_item` 改为「同名 → 单品优先 → 名称最短」，排除周边/贴纸/酱料，支持 `exclude` 去重。
- 词表校准：22 张大阿卡纳按真实菜单重校，78/78 牌可匹配到带价单品。
- 体验优化：门店记忆 + 当日菜单缓存（`cache.py`）、换季自检（`selfcheck.py`）、三选一与本周餐单、塔罗牌面卡片（`tarot_card.py`）。
- 推荐升级：按时段（早餐/午餐/下午茶/晚餐/夜宵）与牌意份量倾向推荐套餐或单品，展示立省金额。
- 下单能力：`order.py` 出确认卡并记录订单，真实下单/支付走连接器，付款始终由用户本人完成。
- 触发边界：与省钱/比价/凑单类技能互斥，避免抢答。
