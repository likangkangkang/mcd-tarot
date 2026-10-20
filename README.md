# 🔮 麦麦塔罗牌 · McDonald's Tarot

> 今天该吃什么麦当劳？让塔罗替你抽一张，顺便被温柔地接住一下。

一个把「塔罗牌的仪式感」和「麦当劳的餐盘」缝在一起的 WorkBuddy Skill：**78 张牌**做确定性每日抽签，每张牌落到你账号可见的**真实餐品与价格**上，再给一张带餐品图的**塔罗牌面**和一段像朋友说的话。用户说「就它」时，还能走完核对价格 → 下单 → 支付链接的完整流程（付款永远由用户本人完成）。

<img src="assets/sample-card.jpg" width="360" alt="麦麦塔罗牌示例牌面：星币七 → 巨无霸">

> 上图是真实渲染的牌面（示例菜单渲染，价格随门店与活动变化）。牌面由 `scripts/tarot_card.py` 生成 SVG，餐品图从 `query-meals` 的 `image` 字段下载后 base64 内联，单文件可直接转发截图。

---

## 它解决什么

点外卖最难的从来不是「吃什么」，而是「今天我值得被怎么对待」。
这个 Skill 把那个模糊的问题，变成一次有仪式感、又**真能落到一份具体汉堡上**的小事：

- **确定性抽签** —— 按日期播种，同一天随时来抽都一样，像一份每日心情灵感，不是随机噪音。
- **真实菜单映射** —— 走麦当劳 MCP（`mcd-mcp`）拉当日菜单，建议是**具体单品/套餐 + 价格**，不是空泛鸡汤。
- **知道你爱吃什么** —— 读历史订单与券包，得出常点品类、口味倾向、各时段习惯（早餐爱组合还是单品）、手上有什么券，再在牌意范围内优先推你爱吃的。
- **跟着饭点走** —— 按当前时间判定早餐/午餐/下午茶/晚餐/夜宵，同一张牌在早上和深夜给的建议不一样。
- **顺势省一点** —— 只说「这道刚好能用哪张券、省多少」，不为了用券改推荐，也不做凑单比价。
- **永远可演示** —— 没配 Token 也能跑（自动回退示例菜单），体验不打折。

## 玩法

| 玩法 | 适合 | 张数 |
|---|---|---|
| `today` 今日宜吃 | 一句话决定今天吃啥 | 1 |
| `choice` 三选一 | 选择困难，想三个选项 | 3 |
| `trinity` 身·心·灵三餐 | 想被全方位关照 | 3 |
| `timeline` 过去·现在·未来 | 想看清一段状态 | 3 |
| `--week` 本周餐单 | 一次安排一周七顿 | 7 |

正逆位都会给：逆位不做恐吓，落点永远是「允许、休息、被看见」。

## 快速开始

**在 WorkBuddy 里用（推荐）**

1. 把本目录放进技能目录（用户级为 `~/.workbuddy/skills/mcd-tarot/`）。
2. 在【连接器】启用 `mcd-mcp`（配置模板见 `assets/mcp-config.example.json`）。
3. 直接说：
   - 「用麦麦塔罗牌帮我抽今天的」→ 今日宜吃 + 牌面图
   - 「我今天有点累，抽个身心灵的」→ 三张解读
   - 「抽个过去现在未来」→ 时间线

**命令行 / 脚本**（纯标准库，无需第三方依赖）

```bash
python3 scripts/tarot_engine.py --spread today --mood "加班到很晚，有点丧"
python3 scripts/tarot_engine.py --spread choice --mood "选择困难"
python3 scripts/tarot_engine.py --spread today --card-svg card.svg        # 出牌面
python3 scripts/tarot_engine.py --spread today --at "2026-10-20 12:30"    # 模拟午餐时段
python3 scripts/tarot_engine.py --week                                    # 本周餐单

# 想接真实菜单（需要 Token）：
export MCD_MCP_TOKEN=你的Token
python3 scripts/tarot_engine.py --spread today
```

未配置 Token 或网络失败时自动回退示例菜单，命令照样跑。

## 一次抽牌发生了什么

```
门店（有缓存就不问） → 口味画像（订单/券包，一天一次） → 当日菜单（当天只拉一次）
        ↓
确定性抽签（date 播种） → 牌 → 关键词打分映射真实餐品
        ↓
按饭点调形态（套餐/单品） + 按画像挑更合口味的那道 + 匹配手上有用的券
        ↓
牌面 SVG（餐品图内联） + 文字解读（牌意 → 为什么适合你 → 怎么买更省）
        ↓
用户说「就它」 → calculate-price 核价 → create-order → 支付链接交给用户自己付
```

## 目录结构

```
mcd-tarot/
├── SKILL.md                    # 技能定义与工作流（连接器优先 + 缓存优先 + 下单红线）
├── scripts/
│   ├── tarot_deck.py           # 78 张牌 + 麦当劳映射 + 情绪寄语 + 份量倾向
│   ├── tarot_engine.py         # 抽签、牌阵、时段/形态、三选一、本周餐单、卡片入口
│   ├── mcp_client.py           # 标准库 mcd-mcp 客户端 + 口味/券匹配打分
│   ├── profile.py              # 口味画像：历史订单 → 常点/口味/时段；券包 → 优惠索引
│   ├── menu_from_connector.py  # query-meals → 引擎菜单（保留图片/划线价/套餐标记）
│   ├── cache.py                # 门店记忆 + 当日菜单缓存
│   ├── selfcheck.py            # 换季自检：价格覆盖 / 误映射 / 重复牌
│   ├── tarot_card.py           # 牌面 SVG：红金双层框 + 拱形画框 + 餐品图 + 罗马数字
│   ├── order.py                # 下单确认卡 + 订单记录（不代付）
│   └── tests/                  # 单元测试（30 项）
├── references/                 # 安装维护 / MCP 集成 / 示例解读 / 参赛声明
├── assets/                     # 连接器配置模板、requirements、示例牌面
└── 运行时数据在 ~/.cache/mcd-tarot/（门店、当日菜单、口味画像、订单，不入库）
```

## 自检与维护

```bash
python3 scripts/tests/test_tarot_engine.py   # 30 项单测
python3 scripts/selfcheck.py                 # 换季自检，非零退出说明要修关键词
python3 scripts/cache.py clear --all         # 缓存坏了就重建
python3 scripts/profile.py clear             # 用户说「别记我」
```

当前状态：78/78 张牌有价、关键词命中 78/78、365 天 × 3 牌阵零重复牌。

## 安全与合规

- 仓库不含任何真实 Token / 密钥，配置一律用 `${MCD_MCP_TOKEN}` 占位。
- 抽牌只读菜单与个人订单/券包；**下单只在用户明确要求时发生，付款永远由用户本人完成**，不代付、不索要验证码。
- 口味画像只存在本机 `~/.cache/mcd-tarot/profile.json`，不上传、不入库，随时可清。
- 本技能**不做占卜、不算命、不预测运势**，只借塔罗意象做情绪陪伴与选餐建议。
- 参赛作品，非麦当劳官方产品；餐品、价格、供应以麦当劳官方实时结果为准。

## 更多

| 文档 | 内容 |
|---|---|
| [`SKILL.md`](SKILL.md) | 完整工作流与下单红线 |
| [`references/INSTALL.md`](references/INSTALL.md) | 安装、单一真源与更新方式 |
| [`references/MCP_INTEGRATION.md`](references/MCP_INTEGRATION.md) | MCP 工具与调用流程 |
| [`references/sample_reading.md`](references/sample_reading.md) | 一份完整解读示例 |
| [`references/CONTEST_DECLARATION.md`](references/CONTEST_DECLARATION.md) | 参赛声明 |
