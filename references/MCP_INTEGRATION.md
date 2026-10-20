# MCP 集成说明 · 麦麦塔罗牌

本文件说明「麦麦塔罗牌」使用的麦当劳 MCP 能力与调用流程。

## 1. 连接的 MCP Server
- **名称**：`mcd-mcp`
- **端点**：`https://mcp.mcd.cn`（Streamable HTTP）
- **鉴权**：`Authorization: Bearer <MCP Token>`（Token 由用户本人在连接器配置，仓库仅留 `${MCD_MCP_TOKEN}` 占位符）

## 2. 使用的工具
| 工具 | 用途 | 在本项目中的角色 |
|---|---|---|
| `query-nearby-stores` | 查收藏/附近门店 | 取 `storeCode`，缓存后免重复询问 |
| `query-meals` | 商品名、`code`、价格 | **核心数据源**：把塔罗建议映射到用户账号可见的真实餐品与价格 |
| `order-list` / `query-my-coupons` / `available-coupons` / `query-my-account` | 历史订单与券包 | 构建口味画像（6 小时 TTL，可跳过） |
| `calculate-price` / `create-order` / `query-order` / `cancel-order` | 下单与支付 | **仅当用户明确说「就它/下单」时**走核价 → 下单 → 给支付链接，付款由用户本人完成 |

> 抽牌与推荐**只读**菜单与订单；写操作（下单/支付）只在用户明确要求时发生，且永不代付、不索要验证码。

## 3. 调用流程
```
用户心情 / 问题
   │
   ▼
tarot_engine.do_reading(spread, date, mood, question, token)
   │  1) 按日期确定性抽签（78 张中抽 1 张，含正/逆位）
   ▼
   │  2) 用牌的 mcd_keywords 在菜单中匹配真实餐品（套餐优先、能叠券就叠券）
   ▼
mcp_client.get_menu(token) 或连接器 query-meals
   │  ├─ 有 Token 且成功 → 真实菜单
   │  └─ 无 Token / 失败  → 内置示例菜单（回退，体验不打折）
   ▼
输出：牌面 SVG + 塔罗意涵 + 麦麦指引(具体餐品+价格) + 情绪寄语
```

## 4. 设计取向
- **真实优先，回退兜底**：有 Token 时给「真实单品 + 价格」，没 Token 也能完整演示，降低体验门槛。
- **最小权限 + 明确边界**：只读工具用于推荐；下单/支付走连接器且须用户明确授权，付款永远由用户本人完成。
- **确定性体验**：抽签以日期为种子，同一天结果稳定，便于分享与复现。

## 5. 连接器配置（用户侧）
见 `assets/mcp-config.example.json`：在 WorkBuddy【连接器】→【自定义连接器】填入，把
`${MCD_MCP_TOKEN}` 替换为本人麦当劳 MCP Token，保存启用 `mcd-mcp` 即可。
