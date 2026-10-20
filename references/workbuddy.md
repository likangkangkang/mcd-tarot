# WorkBuddy 开发记录 · 麦麦塔罗牌

> 本文件记录本项目在 **腾讯 WorkBuddy** 中的开发上下文，用于冲刺大赛「WorkBuddy 专项奖励」。

## 1. 为什么用 WorkBuddy 开发
- **Skill 即原生交付物**：大赛「开发 Skill」赛道要求产出一个可被智能体调用的技能；WorkBuddy 的 `SKILL.md` 规范天然契合，本项目以 `SKILL.md` 作为一等交付物。
- **连接器直连麦当劳 MCP**：WorkBuddy 的【连接器】能力让我们无需自建服务，直接在技能内声明使用 `mcd-mcp`，真实调用 `query-meals` 拉菜单。
- **对话即产品**：塔罗解读是强对话场景，WorkBuddy 的多轮对话、情绪化表达、工具调用编排正好匹配。

## 2. 开发过程（对话式）
1. 用户提出创意：「把麦当劳餐盘与塔罗牌结合，解读今天该吃什么，给足情绪价值」。
2. 在 WorkBuddy 中确认命名 **麦麦塔罗牌**，并约定「明天检查」。
3. 与助手一起搭建：78 张牌组（`tarot_deck.py`）→ 塔罗引擎（`tarot_engine.py`，按日期确定性抽签）→ 仅标准库的 mcd-mcp 客户端（`mcp_client.py`，真实菜单优先、回退示例）→ `SKILL.md` 与文档。
4. 全程使用 WorkBuddy 的代码编写、Python 运行验证、文件管理完成。

## 3. 与 WorkBuddy 的契合点（评审要点）
- 交付物是标准的 WorkBuddy **Skill**（`SKILL.md` + 触发描述）。
- 真实使用 WorkBuddy **连接器**（`mcd-mcp`）调用麦当劳 MCP。
- 情绪化、对话式的产品形态，正是 WorkBuddy 智能体擅长承载的体验。
- 代码零第三方重依赖，标准库即可运行，易于在 WorkBuddy 环境复现与评审。

## 4. 验证方式
- `python3 scripts/tarot_deck.py`：确认 78 张牌组构建正确。
- `python3 scripts/tarot_engine.py --spread today|choice|trinity|timeline`：各牌阵均产出完整情绪化解读。
- 同日复现性、各牌阵独立性已通过断言验证（见 `tests/`）。
- 无 Token 时自动回退示例菜单，演示零门槛。
