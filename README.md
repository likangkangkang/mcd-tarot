# 🔮 麦麦塔罗牌 · McDonald's Tarot

> 今天该吃什么麦当劳？让塔罗替你抽一张，顺便被温柔地接住一下。

一个把「塔罗牌的仪式感」和「麦当劳的餐盘」缝在一起的 WorkBuddy Skill：**78 张牌**做确定性每日抽签，每张牌落到你账号可见的**真实餐品与价格**上，再出一张**把汉堡画成塔罗圣像**的牌面和一段像朋友说的话。默认多给套餐、顺手叠加立减与满减券；用户说「就它」时，还能走完核对价格 → 下单 → 支付链接的完整流程（付款永远由用户本人完成）。

<img src="assets/sample-card.jpg" width="340" alt="麦麦塔罗牌示例牌面：隐者 → 咖啡双人套餐">

<img src="assets/sample-trinity.jpg" width="820" alt="身心灵三餐：权杖七 / 宝剑九（逆位）/ 隐者">

> 牌面由 `scripts/tarot_art.py` + `scripts/tarot_card.py` 纯代码绘制：深靛夜空、旧金双线框、拱形画窗、罗马数字、月相与星点。主画面把一份汉堡画成**披着生菜披风、头顶光环、张臂托着法器**的圣像；大阿卡纳各有自己的法器与天空（愚者的太阳、正义的天平与餐刀、世界的花环），小阿卡纳则把薯条/可乐/餐刀/汉堡币按张数串成一道半圆光环。逆位时圣像整体倒置。**不再把商品照贴进画框**，需要时用 `--photo` 在底部小票旁加一枚圆形餐品章。

---

## 它解决什么

点外卖最难的从来不是「吃什么」，而是「今天我值得被怎么对待」。
这个 Skill 把那个模糊的问题，变成一次有仪式感、又**真能落到一份具体汉堡上**的小事：

- **确定性抽签** —— 按日期播种，同一天随时来抽都一样，像一份每日心情灵感，不是随机噪音。
- **真实菜单映射** —— 走麦当劳 MCP（`mcd-mcp`）拉当日菜单，建议是**具体单品/套餐 + 价格**，不是空泛鸡汤。
- **知道你爱吃什么** —— 读历史订单与券包，得出常点品类、口味倾向、各时段习惯（早餐爱组合还是单品）、手上有什么券，再在牌意范围内优先推你爱吃的。
- **跟着饭点走** —— 按当前时间判定早餐/午餐/下午茶/晚餐/夜宵，同一张牌在早上和深夜给的建议不一样。
- **多给套餐，还会叠券** —— 默认套餐优先：套餐吃得更完整，也更容易吃到「划线价立减 + 满减券」这层叠加。只有当菜单里真有对应套餐、且这份套餐值得时才会升级，夜宵碰到清简牌意又没有优惠就保持轻盈，不硬塞。
- **套餐不藏内容** —— 抽到套餐时，名字下方直接写明里面每样餐品和数量（「麦辣鸡腿汉堡 ×1 ｜ 薯条(中) ×1 ｜ 可乐(中) ×1」），牌面小票上也会印出来；优先用官方明细，没有就按件数结合本店真实单品名推断，并标注「参考配置」。
- **顺势省一点** —— 只说「这道刚好能用哪张券、省多少」，不为了用券改推荐，也不做凑单比价。
- **快** —— 抽牌本身 5 毫秒；`scripts/quick.py` 走全本地缓存，不联网、不下图、不开浏览器，通常百毫秒内出结果（实测含出图 30ms）。
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
python3 scripts/tarot_engine.py --spread today --single-only              # 关掉套餐优先
python3 scripts/tarot_engine.py --week                                    # 本周餐单

# 最快的一条路：读本地缓存直接出牌，不联网不下图（缓存缺失时先跑一次连接器）
python3 scripts/quick.py --mood "想被哄一下" --svg card.svg --timing

# 想接真实菜单（需要 Token）：
export MCD_MCP_TOKEN=你的Token
python3 scripts/tarot_engine.py --spread today
```

未配置 Token 或网络失败时自动回退示例菜单，命令照样跑。

### 为什么快，慢在哪

抽牌本身只要 **5ms**——慢的从来不是塔罗，而是串行的网络往返（门店→菜单→订单→券包→可领券→积分）和图片渲染。所以：

| 优化 | 效果 |
|---|---|
| `quick.py` 只读本地缓存 | 全流程 **30ms**（含出牌面 SVG） |
| 菜单按「门店 + 日期」缓存 | 同一天第二次抽牌 0 网络 |
| 口味画像 6 小时 TTL（`profile.is_stale`） | 不用每次重拉 4 个接口 |
| 牌面不再下载/内联商品图 | SVG 从 200KB+ 降到 21–27KB，渲染快且可秒传 |
| PNG 改为按需（`--png` 才启 Chrome） | 平常只出 SVG，省 1–2 秒 |

## 一次抽牌发生了什么

```
门店（有缓存就不问） → 口味画像（订单/券包，6 小时内复用） → 当日菜单（当天只拉一次）
        ↓
确定性抽签（date 播种） → 牌 → 关键词打分映射真实餐品
        ↓
套餐优先（同品类套餐 → 随心配兜底） + 按饭点调形态 + 按画像挑更合口味的那道
        ↓
叠加优惠：套餐划线价立减 ＋ 满减券；单品券不越界抵扣套餐
        ↓
牌面 SVG（汉堡圣像 + 法器，纯代码绘制） + 文字解读（牌意 → 为什么适合你 → 怎么买更省）
        ↓
用户说「就它」 → calculate-price 核价 → create-order → 支付链接交给用户自己付
```

## 目录结构

```
mcd-tarot/
├── SKILL.md                    # 技能定义与工作流（连接器优先 + 缓存优先 + 下单红线）
├── scripts/
│   ├── tarot_deck.py           # 78 张牌 + 麦当劳映射 + 情绪寄语 + 份量倾向 + 品类
│   ├── tarot_engine.py         # 抽签、牌阵、时段/形态/套餐升级、本周餐单、卡片入口
│   ├── tarot_art.py            # 牌面图形元件：汉堡圣像、法器、星月、四色花色
│   ├── tarot_card.py           # 牌面排版：夜空 + 拱窗 + 罗马数字 + 小票（SVG/PNG）
│   ├── mcp_client.py           # 标准库 mcd-mcp 客户端 + 口味/券/套餐匹配打分
│   ├── profile.py              # 口味画像：历史订单 → 常点/口味/时段；券包 → 优惠索引
│   ├── menu_from_connector.py  # query-meals → 引擎菜单（保留图片/划线价/套餐标记）
│   ├── combo_detail.py         # 套餐明细：官方明细缓存 → 按名推断，标注参考配置
│   ├── cache.py                # 门店记忆 + 当日菜单缓存
│   ├── quick.py                # 零网络快速抽牌（全本地缓存，30ms 级）
│   ├── selfcheck.py            # 换季自检：价格覆盖 / 误映射 / 重复牌
│   ├── order.py                # 下单确认卡 + 订单记录（不代付）
│   └── tests/                  # 单元测试（47 项）
├── references/                 # 安装维护 / MCP 集成 / 示例解读 / 参赛声明
├── assets/                     # 连接器配置模板、requirements、示例牌面
└── 运行时数据在 ~/.cache/mcd-tarot/（门店、当日菜单、口味画像、订单，不入库）
```

## 自检与维护

```bash
python3 scripts/tests/test_tarot_engine.py   # 47 项单测
python3 scripts/selfcheck.py                 # 换季自检，非零退出说明要修关键词
python3 scripts/cache.py clear --all         # 缓存坏了就重建
python3 scripts/profile.py clear             # 用户说「别记我」
```

当前状态：78/78 张牌有价、关键词命中 78/78、365 天 × 3 牌阵零重复牌；菜单里各品类都有套餐时，套餐占比可达 98%，平均每单省约 ¥9。

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
