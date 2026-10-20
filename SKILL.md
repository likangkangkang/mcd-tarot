---
name: mcd-tarot
description: 用塔罗牌的仪式感决定「今天吃什么麦当劳」：给一张把汉堡画成塔罗圣像的牌面 + 一段暖心解读，默认优先推荐套餐（并在套餐名下方写明里面每样餐品和数量）、叠加立减与满减券，结合你的口味习惯与点餐时段，可在你确认后直接下单（付款由你本人完成）。覆盖今日一签、三选一、身心灵三餐、过去现在未来、本周餐单、正逆位、真实菜单价格与优惠。仅做情绪陪伴与选餐建议；深度比价、凑单算最优券、代点外卖请用点餐/省钱类技能。
agent_created: true
---

# 麦麦塔罗牌 (McDonald's Tarot)

把 78 张塔罗牌摊在麦当劳的餐盘上：今天该吃什么，让牌替你决定，顺便被温柔地接住一下。

它通过 WorkBuddy 已连接的 **mcd-mcp** 连接器拉真实菜单，同时读你的历史订单与券包，算出「你爱吃什么、这个点你通常怎么点、手上有什么券」，按「日期」做确定性抽签，把每张牌映射到一道真实餐品（默认优先套餐、能叠券就叠券），再输出一张**把手里的汉堡画成塔罗圣像的牌面**和一段解读；用户说「就它」时，还能走完核对价格 → 下单 → 支付链接的完整流程。

> 参赛作品，非麦当劳官方产品。餐品、价格、供应状态以麦当劳官方实时结果为准。
> 本技能**不做占卜、不算命、不预测运势**：只是借塔罗牌的意象做情绪陪伴和「今天吃什么」的选餐建议。

## 启用前提
- WorkBuddy【连接器】中已启用 `mcd-mcp`（配置示例见 `assets/mcp-config.example.json`）。
- 抽牌/推荐只读菜单；下单只在用户**明确要求**时发生，且付款永远由用户本人完成。
- 本地只在 `~/.cache/mcd-tarot/` 记住门店、当日菜单、口味画像、订单记录，不上传、不涉及支付信息。

## 路径约定
下文所有相对路径均相对本 Skill 目录（用户级安装时为 `~/.workbuddy/skills/mcd-tarot/`）。临时文件写系统临时目录，用完即弃。

## 快速路径（先想这个）

**缓存齐全时，别走完整工作流。** 用户只是想抽一张，就走：

```bash
python3 scripts/quick.py --spread <today|choice|trinity|timeline> [--mood "心情"] [--svg <卡片路径>] [--timing]
```

它只读本地缓存（门店 → 当日菜单 → 口味画像），**不联网、不下图、不开浏览器**，通常几十毫秒出结果。
只有下面这几种情况才需要回到完整工作流重新拉数据：

| 情况 | 判断 | 动作 |
|---|---|---|
| 没有门店记忆 | `cache.py store get` 退出码 1 | 走工作流第 3 步 |
| 今天还没拉菜单 | `cache.py menu get --store <code>` 退出码 1 | 走工作流第 5 步 |
| 画像超过 6 小时 | `quick.py` 会自己提示；或 `profile.py show` 看时间 | 走工作流第 4 步 |
| 用户明确要下单 | 见「下单与支付」 | 必须重新 `calculate-price` 核价 |

`quick.py` 拿不到菜单时会以退出码 3 报错并提示，不要自己编菜单；加 `--allow-fallback` 才用内置示例菜单（结果不代表真实门店）。

## 工作流
1. **接住情绪**：先轻问用户今天的状态 / 心情（如「累」「开心」「纠结」），作为解读开场白。若用户直接要抽牌，也可跳过。
2. **选玩法**：
   - `today`（今日宜吃，单张）——默认，最常用。
   - `choice`（三选一，三张不同牌 + 三道不同菜）——选择困难时。
   - `trinity`（身·心·灵 三餐，三张）——想被全方位关照时。
   - `timeline`（过去·现在·未来，三张）——想看清一段状态时。
   - `--week`（本周餐单，周一至周日七张）——想一次安排好一周时。
3. **拿门店（缓存优先，别每次都问）**：
   a. 先跑 `python3 scripts/cache.py store get`：有输出就直接用其中的 `store_code`，**不要再问用户在哪**；
   b. 没有缓存时调 `query-nearby-stores`：`beType=1, searchType=1` 查收藏门店；查不到再问城市，用 `searchType=2` + `city` + `keyword`；
   c. 拿到门店立刻记住：`python3 scripts/cache.py store set --code <storeCode> --name "<门店名>" --city "<城市>"`。
4. **了解他（口味画像，6 小时内不重复学）**：
   目标：知道他常吃什么、偏哪类口味、各时段习惯套餐还是单品、手上有什么券。
   a. 先跑 `python3 scripts/profile.py show`：有输出且 `updated` 在 6 小时内 → 直接用，**不要重复学**；
      （订单和券包变化不快，6 小时内的画像足够用；`profile.is_stale()` 就是这个判断）
   b. 否则并行调 4 个只读连接器工具，把**原始返回原样**存成临时文件：
      `order-list` → `orders.json`；`query-my-coupons` → `wallet.md`（返回是 markdown 就存 .md）；
      `available-coupons` → `available.md`；`query-my-account` → `account.json`；
   c. 跑 `python3 scripts/profile.py build --orders … --wallet … --available … --account …`；
   d. **全部失败也不要紧**：画像只是增强项，拿不到就跳过，引擎会退回纯牌意推荐。
   e. 隐私：画像只写在 `~/.cache/mcd-tarot/profile.json`，不进 git、不上传；用户说「别记我」就跑 `python3 scripts/profile.py clear`。
5. **拿菜单（当天只拉一次）**：
   a. `python3 scripts/cache.py menu get --store <storeCode>` 命中（退出码 0）就直接用，**不要再调连接器**；
   b. 未命中则调 `query-meals`（orderType=1, beType=1, storeCode=上一步结果），原始返回写入临时 `raw.json`；
   c. 归一化并写当日缓存：`python3 scripts/menu_from_connector.py <raw.json> --store <storeCode>`。
      **注意**：务必用这个脚本，它会把餐品图 `image`、划线价、优惠类型和「套餐 / 单品」标记一起保留，卡片和推荐都依赖这些字段。
   d. 任一步失败 → 不传 `--menu-file`，引擎回退内置示例菜单；不要向用户暴露技术细节。
6. **抽签 + 出牌面**：
   `python3 scripts/tarot_engine.py --spread <today|choice|trinity|timeline> [--mood "心情"] [--card-svg <卡片路径>]`
   或本周餐单 `python3 scripts/tarot_engine.py --week [--mood "心情"]`
   - 不给 `--menu-file` 时引擎自动读当日缓存；`--no-cache` 可关闭。
   - 画像默认自动读取；`--no-profile` 可关闭（用户不想被「记住」时用）。
   - 引擎按**当前时间**判定点餐时段（早餐/午餐/下午茶/晚餐/夜宵），并优先采用**你在这个时段的真实习惯**（比如你早餐一向点组合，就不会给你推单品）；想模拟其他时段加 `--at "YYYY-MM-DD HH:MM"`。
   - **默认套餐优先**：同关键词或同品类里能落套餐就落套餐（套餐吃得更完整，也更容易吃到「划线价立减 + 满减券」）。
     兜底顺序是「同关键词套餐 → 同品类套餐 → 随心配/1+1 这类自选组合 → 单品」，菜单里真没有套餐才会给单品。
     用户想要单品、或只想看看轻的，加 `--single-only` 关掉。
   - **套餐必带明细**：抽到套餐时，名字下面紧跟一行「📦 这一份里有：麦辣鸡腿汉堡 ×1 ｜ 薯条(中) ×1 ｜ 可乐(中) ×1」，让用户一眼看清点了什么。
     明细由 `scripts/combo_detail.py` 生成，优先用官方明细（菜单自带 / `query-meal-detail` 拉过的），
     没有就按套餐名的件数、结合本店菜单里的真实单品名推断，并标注「参考配置，以结算页为准」；
     绝不凭空编菜单里没有的名字。
     用户追问「里面到底是什么」时，才调连接器的 `query-meal-detail` 拿官方明细并导入缓存：
     `python3 scripts/combo_detail.py --raw <meal-detail.json> [--code <code>]`（之后自动优先使用）。
   - 每张牌会给出「形态」、立省金额（有划线价时）、`🧠 合你口味`（为什么这道像你）、`🎟 用券`（这道能用哪张券、省多少）、`🔁 或者更像你`（同类里更合口味的备选）。
     优惠是可叠加的两层：套餐自带的划线价立减 + 满减券（`满 30 减 5` 这类），两笔都会算进「合计可省」。
     **单品券绝不抵扣套餐**（「11.9 麦辣鸡腿堡」不能套到「麦辣鸡腿汉堡三件套」上）。
   - 首选加 `--card-svg <路径>`：单张出 1 张牌面，三牌阵出 3 张（自动加 `-1/-2/-3` 后缀）。
     牌面是纯代码画的塔罗牌（汉堡圣像 + 法器 + 星月），**不内嵌商品照**，所以不需要联网下图；
     用户想看真图时加 `--photo`，会在底部小票旁加一枚圆形餐品章。
     要 PNG 用 `python3 scripts/tarot_card.py reading.json card.png --png`（需要本机 Chrome，慢 1–2 秒，非必要不用）。
7. **呈现**：先给牌面图（把文件路径给用户），再给文字解读——抽到的牌（正/逆位）、塔罗意涵、麦麦指引（吃什么 + 价格）、形态说明、给你的话，最后带一句「今天这样买更省」。
   - 语气像朋友，不要念参数、不要提 storeCode、JSON、缓存等技术细节。
   - 按顺序说：**牌怎么说 → 为什么这道适合你 → 怎么买更省**，不要一上来就报优惠。
   - 用户对某天的菜不满意：把该日期传给 `--date` 只重抽那一张。
   - 结尾带一句：想直接吃这一份，回「就它」就能下单。
8. **下单（仅当用户明确说「就它 / 下单 / 买 / 帮我点」时进入，见下节）**。

## 下单与支付（真实花钱，必须守规矩）

**硬性红线**
- 用户只是抽牌 / 问推荐，**不等于**下单授权。没有明确的「下单 / 买 / 就它」表述，只能出确认卡，**绝不调用 `create-order`**。
- 金额一律以 `calculate-price` 返回为准（单位是**分**，展示时 ÷100）。不要拿菜单页价格直接下单。
- **付款只能由用户本人完成**：把支付链接/二维码给用户，绝不代付、绝不索要验证码、密码、银行卡或支付截图。
- 下单前先 `python3 scripts/order.py list` 看一眼，避免重复下单。

**流程**
1. 确认餐品：取解读里的 `cards[0].food_code`（用户指定了别的菜就用他指定的 code）；数量默认 1，用户说了才改。
2. 生成确认卡（只读，不下单）：
   `python3 scripts/order.py draft --store <storeCode> --store-name "<门店名>" --items "<code>:<qty>" --way locker-in --way-name "外带"`
3. 调 `calculate-price`（`beType=1, orderType=1, storeCode, items:[{productCode, quantity}]`），拿到 `data.price`（分）、`data.discount`、`data.takeWayList`。
4. **把确认卡 + 实付金额 + 取餐方式原样复述给用户，等明确确认**。这一步不能跳。
5. 用户确认后调 `create-order`（`takeWayCode` 取自 `takeWayList[].code`，如 `locker-in` 外带 / `eat-in` 堂食）。
6. 登记并把支付链接给用户：
   `python3 scripts/order.py record --order-id <id> --pay-url "<链接>" --total <元>`
   话术：「订单已创建，点这个链接自己付款：<链接>。付完回我一声，我帮你查状态。」
7. 用户回「付好了」→ 调 `query-order` 查最新状态；成功则 `python3 scripts/order.py update --order-id <id> --status paid`。
8. 用户反悔 / 超时 → 调 `cancel-order`，并 `order.py update --status cancelled`。不要在未支付状态下重复 create。

## 情绪价值设计原则
- **不制造焦虑**：永远给正向收束，逆位也落到「允许、休息、温柔」。
- **把选择交还用户**：塔罗是参考，不是命令，明确说「你也可以按自己胃口来」。
- **具体的关怀**：结合真实餐品、价格、时段、你的口味习惯和手上的券，让建议可落地。
- **省钱要克制**：只提「这道菜刚好能用上的券」和「顺手能领的券」，最多两句；不为了用券而改推荐，也不做凑单、比价、最优组合的算术题（那是省钱类技能的事）。
- **尊重边界**：不追问隐私、不评价身材/饮食，用户说「不吃」就停。

## 与其它技能的边界
- 本技能关键词是**情绪、仪式感、抽牌、纠结**；用户要的是「被理解 + 一个决定」。
- 本技能会顺带提一句「这道能用你哪张券」，但**不做**跨店比价、凑单最优解、批量领券这类任务；用户明确要这些 → 交给省钱或点餐类技能。
- 用户只问「麦当劳有什么 / 某店营业吗」→ 直接查菜单，不必抽牌。
- 再强调一次：优惠只作为「这一道菜」的注解，不要展开成独立的优惠分析。

## 输出规范
- 标注「餐品供应与价格以麦当劳官方实时为准」。
- 套餐要在名字下方写明里面每样餐品和数量（参考配置也要标注清楚）。
- 正/逆位、牌名中英文、餐品与价格、形态（套餐/单品）信息清晰；寄语口语化、短句为主。
- 不输出原始 JSON、工具调用细节、门店编码。

## 维护
- 换季上新后自检：`python3 scripts/selfcheck.py`（价格覆盖 / 误映射 / 重复牌；退出码非 0 说明要修 `mcd_keywords`）。
- 换门店：`python3 scripts/cache.py clear --what store` 后重走第 3 步。
- 缓存坏了：`python3 scripts/cache.py clear --all` 重建。
- 口味画像过时（很久没点、口味变了）：`python3 scripts/profile.py clear` 后重走第 4 步。
- 想看它到底记住了什么：`python3 scripts/profile.py show`（只读，可以原样念给用户听）。

## 参考
- `scripts/quick.py`：零网络快速抽牌（只读本地缓存，几十毫秒出结果，日常首选）。
- `scripts/tarot_engine.py`：抽签、牌阵、时段与形态推荐、套餐升级、三选一、本周餐单、卡片入口。
- `scripts/tarot_deck.py`：78 张牌的定义（牌意、麦当劳关键词、品类、份量倾向、情绪寄语）。
- `scripts/tarot_art.py`：牌面图形元件（汉堡圣像、法器、星月、四色花色、大阿卡纳构图配置）。
- `scripts/tarot_card.py`：牌面排版（夜空 + 拱窗 + 罗马数字 + 小票），出 SVG；`--png` 才启 Chrome。
- `scripts/profile.py`：口味画像（历史订单 → 常点/口味倾向/时段习惯；券包 → 优惠索引）+ 6 小时 TTL。
- `scripts/menu_from_connector.py`：连接器菜单归一化（保留图片、划线价、优惠、套餐/单品标记）。
- `scripts/combo_detail.py`：套餐明细（官方明细缓存 → 按名推断，标注参考配置）。
- `scripts/mcp_client.py`：餐品匹配与口味/券/套餐打分（含单品券不抵套餐的边界）。
- `scripts/cache.py`：门店记忆与当日菜单缓存。
- `scripts/order.py`：下单确认卡与订单记录（不代替付款）。
- `scripts/selfcheck.py`：换季自检。
- `scripts/mcp_client.py`：直连 mcd-mcp 的备用客户端（脚本/CI 用，WorkBuddy 内优先走连接器）。
- `scripts/tarot_deck.py`：78 张牌组、麦当劳映射、份量倾向。
- `scripts/tests/test_tarot_engine.py`：单元测试（`python3 scripts/tests/test_tarot_engine.py`）。
- `references/INSTALL.md`：单一真源（本目录即 git 仓库）与更新方式。
- `references/MCP_INTEGRATION.md`：MCP 工具与调用流程。
- `assets/mcp-config.example.json`：连接器配置示例（`${MCD_MCP_TOKEN}` 占位，勿提交真实 Token）。
