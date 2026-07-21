# 公式选股与板块排名 MCP 设计

## 目标

在现有 `https://invest.erikai.top/mcp` 服务中增加公式选股排名和板块排名两个只读工具。工具复用当前 OAuth/PAT 鉴权及 Python 市场数据接口，不增加新的 MCP 地址，不修改任何用户或市场数据。

## 方案

沿用现有 Next.js MCP 路由作为协议与鉴权层，通过 HTTP 调用已有 Python API：

- 公式选股调用 `GET /api/formula-ranking`。
- 板块排名调用 `GET /api/sectors`，在 MCP 层按综合分降序并按请求数量截断。
- 市场工具与投资组合工具在同一 MCP Server 中注册。
- 所有工具继续要求有效 OAuth Access Token 或 PAT。市场接口虽然读取公共数据，但不绕过 MCP 的统一认证入口。

不新建独立 `/market-mcp`，避免重复配置 OAuth Resource、连接器和客户端。

## 工具契约

### get_formula_stock_ranking

用途：查询公式选股排名。

输入：

- `market`: `CN`、`HK`、`US` 或 `all`，默认 `CN`。
- `mode`: `balanced`、`conservative` 或 `aggressive`，默认 `balanced`。
- `limit`: 1 至 100，默认 20。

输出保留后端返回的生成时间、市场、模式、公式说明、数据源、缓存/降级标记、扫描数量和排名条目。工具不接受 `user_id`。

### get_sector_ranking

用途：查询板块综合排名。

输入：

- `limit`: 1 至 100，默认 20。

输出包含生成时间、覆盖数量、数据源、缓存标记和板块条目。板块按数值型 `score` 降序排列；缺失或非数值评分排在末尾；最多返回 `limit` 条。工具不接受 `user_id`。

## 数据流

1. MCP 客户端通过现有 `/mcp` 发起请求。
2. 现有 `withMcpAuth` 校验 OAuth Token 或 PAT。
3. Zod 校验工具参数并应用默认值。
4. MCP 工具请求 Python API，使用 `cache: "no-store"` 获取当前结果。
5. 成功响应同时返回 JSON 文本和 `structuredContent`。
6. 非 2xx 响应转换为带 HTTP 状态码的 MCP 错误，不返回后端堆栈或敏感信息。

## 安全与边界

- 两个工具均为只读，不写入数据库、缓存文件或用户配置。
- 不暴露任意 URL、任意路径、用户 ID 或未经约束的排序表达式。
- 参数由枚举和数值范围限制，防止构造异常后端请求。
- Bearer Token 仅用于 MCP 身份验证；市场接口不依赖用户身份，结构化输出不包含 Token。
- 现有投资组合工具行为保持不变。

## 测试

在 MCP 协议测试中覆盖：

- 工具列表同时包含投资组合、公式选股和板块排名。
- 公式工具正确编码 `market`、`mode`、`limit` 参数并返回结构化结果。
- 板块工具按综合分降序、处理缺失评分并执行 `limit` 截断。
- 两个工具均不暴露 `user_id` 输入。
- API 非 2xx 时返回 MCP `isError`，且不泄漏认证信息。
- 原有 OAuth、PAT、投资组合 MCP 测试继续通过。

## 验收标准

- 现有 MCP 连接器无需重新配置即可发现两个新工具。
- Claude、ChatGPT 或 MCP Inspector 能调用两个工具并获得结构化排名。
- 参数范围、排序和错误处理符合上述契约。
- MCP 测试、认证测试和生产构建通过。
