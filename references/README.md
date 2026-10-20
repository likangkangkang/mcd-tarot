# 🔮 麦麦塔罗牌 (McDonald's Tarot)

> 今天该吃什么麦当劳？让塔罗替你抽一张，顺便被温柔地接住一下。

**麦麦塔罗牌**是一个把「塔罗牌」的仪式感与「麦当劳餐盘」结合的情绪向 Skill：
用 78 张塔罗牌做每日抽签，把每张牌映射到你今天真正该吃的那道麦麦，
再附上一句像朋友说的、刚好接住你情绪的话。

它更像一面帮你「听见自己、好好吃饭」的小镜子。

---

## ✨ 它解决了什么

点外卖最难的从来不是「吃什么」，而是「今天我值得被怎么对待」。
麦麦塔罗牌把这个抽象的问题，变成一次有仪式感、有情绪价值的小游戏：

- **确定性抽签**：按「今天」生成，同一天随时来抽都一样，像一份每日心情灵感。
- **真实菜单映射**：通过麦当劳 MCP 拉真实菜单，给出的建议是**具体单品 + 价格**，不是空泛鸡汤。
- **情绪价值优先**：无论正位逆位，收束都落在「允许、休息、被爱、被看见」，绝不制造焦虑。
- **永远可演示**：没配 Token 也能跑（自动回退示例菜单），体验不打折。

## 🎴 玩法

| 玩法 | 适合 | 抽几张 |
|---|---|---|
| `today` 今日宜吃 | 一句话决定今天吃啥 | 1 张 |
| `choice` 三选一 | 选择困难，想让牌给三个选项 | 3 张 |
| `trinity` 身·心·灵 三餐 | 想被全方位关照 | 3 张 |
| `timeline` 过去·现在·未来 | 想看清一段状态 | 3 张 |
| `--week` 本周餐单 | 一次安排好一周七顿 | 7 张 |

## 🚀 快速开始

### 方式一：在 WorkBuddy 里用（推荐）
1. 把本目录作为 Skill 放入 WorkBuddy 的技能目录（或连接器市场）。
2. 在【连接器】中启用 `mcd-mcp`（见 `mcp-config.example.json`）。
3. 直接对 WorkBuddy 说：
   - 「用麦麦塔罗牌帮我抽今天的」 → 今日宜吃
   - 「我今天有点累，抽个身心灵的」 → 三张解读
   - 「给我抽个过去现在未来」 → 时间线

### 方式二：命令行 / 脚本
```bash
# 无需任何第三方依赖（仅 Python 标准库）
python3 scripts/tarot_engine.py --spread today --mood "加班到很晚，有点丧"
python3 scripts/tarot_engine.py --spread choice --mood "选择困难"
python3 scripts/tarot_engine.py --spread timeline --date 2026-10-16
python3 scripts/tarot_engine.py --week                    # 本周餐单
python3 scripts/tarot_engine.py --spread today --card-svg card.svg   # 可分享卡片

# 想用真实菜单（需要 Token）：通过环境变量传入
export MCD_MCP_TOKEN=你的Token
python3 scripts/tarot_engine.py --spread today
```
> 直连脚本复用 `mcp_client.py`，真实菜单优先；无 Token 或网络失败自动回退示例菜单。
> 在 WorkBuddy 内更推荐走连接器 + 本地缓存（见 `INSTALL.md`）。

## 📂 文件结构
```
mcd-tarot/
├── SKILL.md                 # WorkBuddy 技能定义与工作流
├── scripts/
│   ├── tarot_deck.py        # 78 张牌组 + 麦当劳映射 + 情绪寄语（可离线单测）
│   ├── tarot_engine.py      # 引擎：确定性抽签 / 牌阵 / 三选一 / 本周餐单 / 卡片
│   ├── mcp_client.py        # 仅标准库的 mcd-mcp 客户端（真实菜单优先，回退示例）
│   ├── menu_from_connector.py  # query-meals 返回 → 引擎菜单（可写缓存）
│   ├── cache.py             # 门店记忆 + 当日菜单缓存
│   ├── selfcheck.py         # 换季自检（价格覆盖 / 误映射 / 重复牌）
│   ├── card_svg.py          # 可分享竖版卡片（SVG）
│   └── tests/               # 单元测试
├── references/              # README / MCP 集成说明 / 示例解读 / 安装维护 / 参赛材料
├── assets/                  # 连接器配置模板、环境变量示例、requirements
└── .cache/                  # 运行时缓存（不入库）
```

## 🍟 与麦当劳 MCP 的关系
本 Skill 真实调用麦当劳 MCP（`mcd-mcp`，`https://mcp.mcd.cn`）的 `query-meals`
拉取菜单，把塔罗建议落到你账号可见的真实餐品与价格上。详见 `MCP_INTEGRATION.md`。

## 🔒 安全与合规
- 仓库不含任何真实 Token / 密钥；配置一律使用 `${MCD_MCP_TOKEN}` 占位符（见 `mcp-config.example.json`）。
- 仅读取菜单，**绝不下单、不碰地址/支付等写操作**。
- 作为麦当劳程序员节创意开发大赛参赛作品，遵循赛事规则与 `CONTEST_DECLARATION.md`。

> ⚠️ 餐品、价格、供应状态以麦当劳官方实时结果为准；本输出仅供参考，不构成任何专业建议。
