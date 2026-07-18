# MCP 接入、用户头像与 A 股财报 PDF 设计

## 目标

本次上线包含三个相互独立但共享现有 Web 应用导航和认证状态的改动：

1. 将投资组合页的远程 MCP 接入调整为 OAuth 优先、Personal Access Token 备用。
2. 修复右上角 Auth0 用户头像加载失败时显示破图或 404 的问题。
3. 在财报数据页提供 A 股财报列表和基础 PDF 查看能力。

不在本次范围内：港股和美股财报 PDF、PDF 文本解析、RAG、AI 财报问答、自动创建第三方 OAuth 客户端。

## MCP 接入界面

投资组合页保留现有折叠卡片，但内容分为两个层级。

### OAuth 推荐接入

页面固定展示：

- MCP Streamable HTTP 地址：`https://invest.erikai.top/mcp`
- OAuth Client ID：`IrvtRzsuLDheMJokS88tjMwg4o2clrCN`
- OAuth Client Secret：不需要
- 权限：`portfolio:read`

地址和 Client ID 均提供复制按钮。Claude 和 ChatGPT 使用操作按钮打开各自连接器设置入口，并在界面中说明需要粘贴 MCP 地址和 Client ID。由于第三方产品没有稳定的、能够安全预填全部 OAuth 参数的公开深链，按钮不得描述为“自动完成授权”。

### Token 备用接入

现有 90 天 Personal Access Token 创建、展示、撤销和 Codex 命令继续保留，但放入“备用 Token 接入”折叠区域。说明文本明确 Token 仅用于不支持 OAuth 的客户端或故障排查。

## 用户头像

Header 从应用自己的用户资料接口读取 Auth0 会话资料，不直接信任远程图片可用性。

- 有 `picture` 时尝试渲染头像。
- 图片加载失败时由 Avatar 组件自动显示 fallback。
- fallback 优先使用用户姓名首字母，其次邮箱首字母，最后显示用户图标。
- 下拉菜单显示当前用户的姓名或邮箱。
- 未登录或资料请求失败时保持可用，不显示破图，也不阻塞页面。

退出菜单项应链接到现有 `/auth/logout`，而不是无行为的静态菜单项。

## A 股财报 PDF

财报数据页继续使用现有股票搜索和财务指标。新增财报区域，数据来自已经部署在 Vercel 轻量 API 的 `/api/disclosure/{ticker}`。

### 数据与筛选

- 首版仅对 `sh`、`sz` 开头的 A 股代码启用。
- 支持年报、中报、季报和全部筛选。
- 列表展示标题、发布日期、来源和文件大小（存在时）。
- 只将有效的 HTTP(S) 地址作为可打开文档。

### PDF 查看

- 点击 PDF 项目打开大尺寸对话框。
- 对话框通过浏览器原生 PDF 能力嵌入文档。
- 同时提供“新窗口打开”按钮，作为移动端或来源禁止 iframe 时的回退。
- iframe 加载失败无法被所有浏览器可靠检测，因此界面始终显示回退说明和外部打开按钮。
- 非 PDF 公告链接直接在新窗口打开，不进入 PDF 查看器。

### 状态处理

- 加载时显示骨架或加载提示。
- 空列表区分“暂无财报”和“不支持的市场”。
- API 错误显示可重试提示，不影响原有财务指标。
- 切换股票或筛选后清除已经选择的 PDF，避免显示上一只股票的文档。

## 组件边界

- `McpAccessPanel`：负责 OAuth 配置信息、复制动作、第三方入口和备用 PAT UI。
- `UserMenu`：负责加载会话资料和头像回退。
- `FinancialReportList`：负责公告查询、筛选和列表状态。
- `PdfViewerDialog`：只负责显示一个已验证的 PDF URL 和外部打开回退。

这些组件不直接修改后端数据模型。财报列表继续通过 `ApiClient` 和 React Query 获取，认证资料通过同源 Next.js Route Handler 返回最小用户字段。

## 安全与错误处理

- 用户资料接口只返回 `name`、`email`、`picture`，不返回 access token 或完整 Auth0 claims。
- PDF URL 必须使用 `http:` 或 `https:` 协议，拒绝脚本和数据 URL。
- OAuth Client ID 是公开标识，可以展示；Client Secret 不存在也不展示。
- PAT 完整值仍只在创建后显示一次。

## 测试与验收

- 单元测试覆盖用户资料字段收敛、PDF URL 校验和财报市场判断。
- MCP 元数据和现有 MCP 工具测试必须继续通过。
- 生产构建必须通过。
- 浏览器验收覆盖桌面与手机宽度下的 MCP 卡片、头像 fallback、A 股财报列表和 PDF 对话框。
- 生产部署后验证 Auth0 登录、投资组合读取和 `/api/disclosure/{ticker}` 不回归。
