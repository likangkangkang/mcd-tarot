---
name: mcd-tarot
description: 用塔罗牌的仪式感决定「今天吃什么麦当劳」：给一张带餐品图的塔罗牌面 + 一段暖心解读，按你的点餐时段推荐套餐或单品，并可在你确认后直接下单（付款由你本人完成）。覆盖今日一签、三选一、身心灵三餐、过去现在未来、本周餐单、正逆位、真实菜单价格与优惠。仅做情绪陪伴与选餐建议；省钱比价、优惠券、凑单请用点餐/省钱类技能。
agent_created: true
---

# 麦麦塔罗牌 (McDonald's Tarot)

把 78 张塔罗牌摊在麦当劳的餐盘上：今天该吃什么，让牌替你决定，顺便被温柔地接住一下。

它通过 WorkBuddy 已连接的 **mcd-mcp** 连接器拉真实菜单，按「日期」做确定性抽签，把每张牌映射到一道真实餐品，再输出一张**带餐品图的塔罗牌面**和一段解读；用户说「就它」时，还能走完核对价格 → 下单 → 支付链接的完整流程。

> 参赛作品，非麦当劳官方产品。餐品、价格、供应状态以麦当劳官方实时结果为准。
> 本技能**不做占卜、不算命、不预测运势**：只是借塔罗牌的意象做情绪陪伴和「今天吃什么」的选餐建议。

## 启用前提
- WorkBuddy【连接器】中已启用 `mcd-mcp`（配置示例见 `assets/mcp-config.example.json`）。
- 抽牌/推荐只读菜单；下单只在用户**明确要求**时发生，且付款永远由用户本人完成。
- 本地只在 `~/.cache/mcd-tarot/` 记住门店、当日菜单、订单记录，不上传、不涉及支付信息。

## 路径约定
下文所有相对路径均相对本 Skill 目录（用户级安装时为 `~/.workbuddy/skills/mcd-tarot/`）。临时文件写系统临时目录，用完即弃。

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
4. **拿菜单（当天只拉一次）**：
   a. `python3 scripts/cache.py menu get --store <storeCode>` 命中（退出码 0）就直接用，**不要再调连接器**；
   b. 未命中则调 `query-meals`（orderType=1, beType=1, storeCode=上一步结果），原始返回写入临时 `raw.json`；
   c. 归一化并写当日缓存：`python3 scripts/menu_from_connector.py <raw.json> --store <storeCode>`。
      **注意**：务必用这个脚本，它会把餐品图 `image`、划线价、优惠类型和「套餐 / 单品」标记一起保留，卡片和推荐都依赖这些字段。
   d. 任一步失败 → 不传 `--menu-file`，引擎回退内置示例菜单；不要向用户暴露技术细节。
5. **抽签 + 出牌面**：
   `python3 scripts/tarot_engine.py --spread <today|choice|trinity|timeline> [--mood "心情"] [--card-svg <卡片路径>]`
   或本周餐单 `python3 scripts/tarot_engine.py --week [--mood "心情"]`
   - 不给 `--menu-file` 时引擎自动读当日缓存；`--no-cache` 可关闭。
   - 引擎按**当前时间**判定点餐时段（早餐/午餐/下午茶/晚餐/夜宵）并调整推荐形态；想模拟其他时段加 `--at "YYYY-MM-DD HH:MM"`。
   - 每张牌会给出「形态」（套餐 / 单品 / 分享装 / 轻食）、立省金额（有划线价时）和一句为什么这样配。
   - 首选加 `--card-svg <路径>`：单张出 1 张牌面，三牌阵出 3 张（自动加 `-1/-2/-3` 后缀）。
6. **呈现**：先给牌面图（把文件路径给用户），再给文字解读——抽到的牌（正/逆位）、塔罗意涵、麦麦指引（吃什么 + 价格）、形态说明、给你的话。
   - 语气像朋友，不要念参数、不要提 storeCode、JSON、缓存等技术细节。
   - 用户对某天的菜不满意：把该日期传给 `--date` 只重抽那一张。
   - 结尾带一句：想直接吃这一份，回「就它」就能下单。
7. **下单（仅当用户明确说「就它 / 下单 / 买 / 帮我点」时进入，见下节）**。

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
- **具体的关怀**：结合真实餐品、价格、时段和优惠，让建议可落地。
- **尊重边界**：不追问隐私、不评价身材/饮食，用户说「不吃」就停。

## 与其它技能的边界
- 本技能关键词是**情绪、仪式感、抽牌、纠结**；用户要的是「被理解 + 一个决定」。
- 用户明确说「哪家便宜 / 有没有券 / 怎么凑单」→ 交给省钱或点餐类技能，不要用塔罗抢答。
- 用户只问「麦当劳有什么 / 某店营业吗」→ 直接查菜单，不必抽牌。
- 同一条回复里不要既抽牌又抛优惠计算，两个技能同时上会让体验失真。

## 输出规范
- 标注「餐品供应与价格以麦当劳官方实时为准」。
- 正/逆位、牌名中英文、餐品与价格、形态（套餐/单品）信息清晰；寄语口语化、短句为主。
- 不输出原始 JSON、工具调用细节、门店编码。

## 维护
- 换季上新后自检：`python3 scripts/selfcheck.py`（价格覆盖 / 误映射 / 重复牌；退出码非 0 说明要修 `mcd_keywords`）。
- 换门店：`python3 scripts/cache.py clear --what store` 后重走第 3 步。
- 缓存坏了：`python3 scripts/cache.py clear --all` 重建。

## 参考
- `scripts/tarot_engine.py`：抽签、牌阵、时段与形态推荐、三选一、本周餐单、卡片入口。
- `scripts/tarot_card.py`：塔罗牌面卡片（红金框 + 拱形画框 + 餐品图 + 罗马数字，SVG）。
- `scripts/menu_from_connector.py`：连接器菜单归一化（保留图片、划线价、优惠、套餐/单品标记）。
- `scripts/cache.py`：门店记忆与当日菜单缓存。
- `scripts/order.py`：下单确认卡与订单记录（不代替付款）。
- `scripts/selfcheck.py`：换季自检。
- `scripts/mcp_client.py`：直连 mcd-mcp 的备用客户端（脚本/CI 用，WorkBuddy 内优先走连接器）。
- `scripts/tarot_deck.py`：78 张牌组、麦当劳映射、份量倾向。
- `scripts/tests/test_tarot_engine.py`：单元测试（`python3 scripts/tests/test_tarot_engine.py`）。
- `references/INSTALL.md`：单一真源（本目录即 git 仓库）与更新方式。
- `references/MCP_INTEGRATION.md`：MCP 工具与调用流程。
- `assets/mcp-config.example.json`：连接器配置示例（`${MCD_MCP_TOKEN}` 占位，勿提交真实 Token）。
