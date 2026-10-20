---
name: mcd-tarot
description: 用塔罗牌的仪式感决定「今天吃什么麦当劳」，并附一句暖心解读——适合纠结、想被安慰、想有点小仪式感的时刻。覆盖今日一签、三选一、身心灵三餐、过去现在未来、本周餐单、正逆位解读、真实菜单与价格、可分享卡片。仅做情绪陪伴与选餐建议；省钱比价、优惠券、凑单下单请用点餐/省钱类技能，不要用本技能。
agent_created: true
---

# 麦麦塔罗牌 (McDonald's Tarot)

把 78 张塔罗牌摊在麦当劳的餐盘上：今天该吃什么，让牌替你决定，顺便被温柔地接住一下。

本 Skill 更像一面帮你「听见自己、好好吃饭」的小镜子。它通过 WorkBuddy 已连接的 **mcd-mcp** 连接器拉取真实菜单，再结合内置的 78 张牌组，按「日期」做确定性抽签，把每张牌映射到一道真实餐品，并附上温暖的情绪寄语。

> 参赛作品，非麦当劳官方产品。餐品、价格、供应状态以麦当劳官方实时结果为准。

## 启用前提
- WorkBuddy【连接器】中已启用 `mcd-mcp`（配置示例见 `assets/mcp-config.example.json`）。
- 仅使用只读菜单工具；连接器暂不可用时自动回退内置示例菜单，解读体验不受影响。
- 纯情绪与推荐，不涉及下单、地址、支付等写操作；不下单、不改任何数据。
- 本地只在 `.cache/` 记住「上次门店 + 当日菜单」，不上传、不涉及隐私。

## 路径约定
下文所有相对路径均相对本 Skill 目录（用户级安装时为 `~/.workbuddy/skills/mcd-tarot/`）。临时文件（`raw.json`）写到系统临时目录即可，用完即弃；`menu.json` 建议直接走缓存，不必手动管理。

## 工作流
1. **接住情绪**：先轻问用户今天的状态 / 心情（如「累」「开心」「纠结」），作为解读开场白。若用户直接要抽牌，也可跳过。
2. **选玩法**：
   - `today`（今日宜吃，单张）——默认，最常用。
   - `choice`（三选一，三张不同牌 + 三道不同菜）——选择困难、想自己挑时。
   - `trinity`（身·心·灵 三餐，三张）——想被全方位关照时。
   - `timeline`（过去·现在·未来，三张）——想看清一段状态时。
   - `--week`（本周餐单，周一至周日七张）——想一次安排好一周时。
3. **拿门店（缓存优先，别每次都问）**：
   a. 先跑 `python3 scripts/cache.py store get`：有输出就直接用其中的 `store_code`，**不要再问用户在哪**；
   b. 没有缓存时调 `query-nearby-stores`：`beType=1, searchType=1` 查收藏门店；查不到再问用户城市，用 `searchType=2` + `city` + `keyword`；
   c. 拿到门店后立刻记住：`python3 scripts/cache.py store set --code <storeCode> --name "<门店名>" --city "<城市>"`。
4. **拿菜单（当天只拉一次）**：
   a. `python3 scripts/cache.py menu get --store <storeCode>` 命中（退出码 0）就直接用，**不要再调连接器**；
   b. 未命中则调 `query-meals`（orderType=1, beType=1, storeCode=上一步结果），原始返回写入临时 `raw.json`；
   c. 归一化并写入当日缓存：`python3 scripts/menu_from_connector.py <raw.json> --store <storeCode>`；
   d. 任一步失败（连接器未启用 / 查不到门店 / 调用异常）→ 不传 `--menu-file`，引擎自动回退内置示例菜单；不要向用户暴露技术细节，只呈现解读。
5. **抽签并解读**：运行
   `python3 scripts/tarot_engine.py --spread <today|choice|trinity|timeline> [--mood "用户心情"] [--menu-file <menu.json>] [--card-svg <卡片路径>]`
   或本周餐单 `python3 scripts/tarot_engine.py --week [--mood "用户心情"]`
   - 不给 `--menu-file` 时，引擎会自动读第 4 步的当日缓存；只有连接器完全不可用时才回退示例菜单。
   - 抽签按「日期」确定性生成：**同一天结果稳定**（用户随时来抽都一样），不同日期/不同牌阵给出不同牌。
   - 约 30% 概率为逆位，逆位给出更温柔、更内收的视角。
   - 引擎把每张牌的 `mcd_keywords` 与菜单匹配，给出具体单品名与价格（如「巨无霸 ¥26」）；同一牌阵内尽量不重样，优先单品而非套餐/周边。
   - 直接采用脚本输出的 markdown 作为解读主体：不重新抽牌、不替换餐品、不删改情绪寄语。
6. **呈现**：用温暖、像朋友说话的语气，输出——抽到的牌（正/逆位）、塔罗意涵、麦麦指引（吃什么）、给你的话（情绪价值）。结尾落在「好好吃一顿，是你对自己最朴素的温柔」。
   - 用户说「想发朋友圈 / 存下来 / 想要张图」时，加 `--card-svg <路径>` 生成竖版卡片，把文件路径给用户（不要描述技术细节）。
   - 用户对某天的菜不满意：只重抽那一张（把该日期传给 `--date`），不要说「牌不能改」。

## 情绪价值设计原则（代理须遵循）
- **不制造焦虑**：永远给正向收束，即使是逆位也落到「允许、休息、温柔」而非恐吓。
- **把选择交还用户**：塔罗是参考，不是命令。明确说「牌建议你……你也可以按自己胃口来」。
- **具体的关怀**：结合真实餐品与价格，让建议可落地，而不是空泛鸡汤。
- **尊重边界**：不追问隐私、不评价身材/饮食，用户说「不吃」就停。

## 与其它技能的边界（重要）
- 本技能的关键词是**情绪、仪式感、抽牌、纠结**；用户要的是「被理解 + 一个决定」，不是比价。
- 用户明确说「哪家便宜 / 有没有券 / 怎么凑单 / 帮我下单」→ 交给点餐或省钱类技能（如「穷鬼体验卡」），不要用塔罗抢答，也不要把牌面包装成优惠建议。
- 用户只是问「麦当劳有什么 / 某店营业吗」→ 直接查菜单，不必抽牌。
- 同一条回复里不要既抽牌又抛优惠计算，两个技能同时上会让体验失真。

## 输出规范
- 标注「餐品供应与价格以麦当劳官方实时为准」。
- 正/逆位、牌名中英文、建议餐品与价格，信息清晰；情绪寄语口语化、短句为主。
- 不输出原始 JSON / 工具调用细节 / 门店编码。

## 维护
- 换季上新后跑一次自检：`python3 scripts/selfcheck.py`（检查 78 张牌的价格覆盖、误映射、重复牌；退出码非 0 说明要修 `mcd_keywords`）。
- 想换门店：`python3 scripts/cache.py clear --what store` 后重新走第 3 步。
- 缓存坏了不影响使用：`python3 scripts/cache.py clear --all` 即可重建。

## 参考
- `scripts/tarot_engine.py`：塔罗引擎（确定性抽签、牌阵、三选一、本周餐单、菜单映射、情绪化输出、卡片入口），可 CLI 运行。
- `scripts/menu_from_connector.py`：把 query-meals 连接器返回归一化为引擎可用菜单，可直接写当日缓存。
- `scripts/cache.py`：门店记忆与当日菜单缓存（本地 `.cache/`）。
- `scripts/selfcheck.py`：换季自检（价格覆盖 / 误映射 / 重复牌）。
- `scripts/card_svg.py`：可分享竖版卡片（SVG，无第三方依赖）。
- `scripts/mcp_client.py`：直连 mcd-mcp 的备用客户端（需 `MCD_MCP_TOKEN` 环境变量，供脚本/CI 场景；WorkBuddy 内优先走连接器）。
- `scripts/tarot_deck.py`：78 张牌组与麦当劳映射（可离线单测）。
- `scripts/tests/test_tarot_engine.py`：单元测试，运行 `python3 scripts/tests/test_tarot_engine.py`。
- `references/INSTALL.md`：单一真源说明（主 skill 即仓库，git 更新与自检）。
- `references/MCP_INTEGRATION.md`：MCP Server / Tool / 调用流程 / 业务价值。
- `references/sample_reading.md`：完整示例解读。
- `assets/mcp-config.example.json`：mcd-mcp 连接器配置示例（`${MCD_MCP_TOKEN}` 占位符，勿提交真实 Token）。
