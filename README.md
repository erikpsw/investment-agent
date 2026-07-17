# Investment Agent

基于 LangGraph 的投资分析 Agent，支持 A股/港股/美股行情、财报分析、可视化等功能。

## 前端

新版前端使用 Next.js 15 + shadcn/ui 构建，位于 `web/` 目录。

```bash
# 启动后端
cd api && uvicorn main:app --reload --port 8000

# 启动前端
cd web && npm run dev
```

访问 http://localhost:3000

## 功能

- **智能股票搜索**：支持中文名称搜索（如"茅台"、"腾讯"、"苹果"），自动匹配股票代码
- **实时行情查询**：A股/港股/美股，A股使用新浪+腾讯双数据源，无限流限制
- **K线图表**：TradingView Lightweight Charts，支持日K/周K/分钟K
- **财报 PDF 下载与解析**
- **财报语义搜索 (RAG)**
- **财务可视化**（收入趋势、杜邦分析等）
- **多 Agent 协作分析**

## 数据源

| 市场 | 实时行情 | 历史数据 | 股票列表 |
|------|----------|----------|----------|
| A股 (沪深) | Ashare (新浪+腾讯双数据源，无限流) | Ashare | 本地CSV |
| 港股 | 腾讯财经 | - | 本地CSV |
| 美股 | YFinance | YFinance | 本地CSV |

股票列表数据来源：[open-stock-data](https://github.com/irachex/open-stock-data)

## 安装

```bash
# 安装 Vercel 轻量 API 依赖
pip3 install -r requirements.txt

# 安装本地完整版依赖（Streamlit、PDF/RAG、Playwright、Agent）
pip3 install -r requirements-full.txt

# 下载中文 embedding 模型（首次运行会自动下载）
python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')"
```

## 配置

复制 `.env.example` 为 `.env` 并填入 API Key：

```bash
cp .env.example .env
# 编辑 .env 文件，设置 OPENAI_COMPAT_API_KEY
```

## 运行

```bash
# 方法 1：使用启动脚本
./run.sh

# 方法 2：手动运行
cd /path/to/workspace-investment
export PYTHONPATH=$(pwd)
python3 -m streamlit run investment/app.py

# 指定端口
PORT=8080 ./run.sh
```

## 测试

```bash
# 运行集成测试
cd investment
python3 test_integration.py
```

## 项目结构

```
investment/
├── app.py              # Streamlit 入口
├── agents/             # LangGraph Agent
├── data/               # 数据获取层
│   ├── stock_lists/    # 本地股票列表CSV
│   ├── ashare_client.py  # A股行情 (新浪+腾讯)
│   ├── stock_search.py   # 股票名称搜索
│   └── stock_fetcher.py  # 统一数据接口
├── reports/            # 财报处理
├── viz/                # 可视化模块
├── ui/                 # Streamlit 页面
├── storage/            # 本地存储
└── utils/              # 工具函数
```

## 更新股票列表

股票列表存储在 `data/stock_lists/` 目录下，可手动更新：

```bash
# 下载最新股票列表
curl -o investment/data/stock_lists/SSE.csv https://raw.githubusercontent.com/irachex/open-stock-data/main/symbols/SSE.csv
curl -o investment/data/stock_lists/SZSE.csv https://raw.githubusercontent.com/irachex/open-stock-data/main/symbols/SZSE.csv
curl -o investment/data/stock_lists/HKEX.csv https://raw.githubusercontent.com/irachex/open-stock-data/main/symbols/HKEX.csv
curl -o investment/data/stock_lists/NASDAQ.csv https://raw.githubusercontent.com/irachex/open-stock-data/main/symbols/NASDAQ.csv
curl -o investment/data/stock_lists/NYSE.csv https://raw.githubusercontent.com/irachex/open-stock-data/main/symbols/NYSE.csv
```

## 用户登录与云端投资组合

部署版本使用 Auth0 登录，并把每个用户的投资组合保存到 Supabase。Auth0 access token 的 `sub` 是唯一用户标识，投资组合接口不接受客户端传入的 `user_id`。

默认复用现有 Auth0 Regular Web Application，不要求额外创建 API。`AUTH0_AUDIENCE` 留空时，FastAPI 和 MCP 通过 Auth0 `/userinfo` 验证 access token；如需本地 JWT 校验，可配置现有 Auth0 API Identifier，并使用 RS256 签名。应用需要配置：

- Allowed Callback URLs: `http://localhost:3000/auth/callback` 和 `https://你的域名/auth/callback`
- Allowed Logout URLs: `http://localhost:3000` 和线上域名
- Allowed Web Origins: `http://localhost:3000` 和线上域名

把 `.env.example` 中的 `AUTH0_*`、`APP_BASE_URL`、`SUPABASE_URL` 和 `SUPABASE_SERVICE_KEY` 配置到本地环境及 Vercel。`SUPABASE_SERVICE_KEY` 只能存在于服务端，不能使用 `NEXT_PUBLIC_` 前缀。

登录后可通过以下接口操作当前用户的组合：

```text
GET  /api/portfolio/positions
PUT  /api/portfolio/positions
POST /api/portfolio/analyze
```

所有接口要求 `Authorization: Bearer <Auth0 access token>`。无 Audience 模式下 token 必须包含 `openid profile email` scope，并能通过同一 Auth0 租户的 `/userinfo` 验证。

## 远程 MCP

部署后 MCP Streamable HTTP 地址为：

```text
https://你的域名/mcp
```

服务在 `/.well-known/oauth-protected-resource` 发布 OAuth Protected Resource Metadata，远程 MCP 客户端应使用同一个 Auth0 API 获取 Bearer token。可用工具：

```text
get_portfolio_details(include_analysis?: boolean)
```

工具不会接收 `user_id`，只返回 access token 所属用户的持仓、现价、市值、浮盈亏、仓位权重和组合汇总。`include_analysis=true` 时还会返回新闻、技术面和 AI 仓位管理分析。

### Personal Access Token

长期 MCP 接入不要延长或保存 Auth0 access token。登录投资组合页面后创建 Personal Access Token：

- 默认有效期 90 天，可随时撤销。
- 完整 Token 仅在创建成功时显示一次，数据库只保存 SHA-256 哈希。
- PAT 仅有 `portfolio:read` 权限，可读取和分析投资组合，不能修改仓位或管理其他 Token。

```bash
export ERIK_AI_ACCESS_TOKEN="eai_pat_..."
codex mcp add erik_ai --url https://invest.erikai.top/mcp --bearer-token-env-var ERIK_AI_ACCESS_TOKEN
```

### 热门市场与 ETF 快照

首页通过 `/api/market/hot-stocks` 分别展示 A 股、港股和美股热门股票，支持综合热度、成交额和涨幅排行。综合热度由成交额、涨跌幅、换手率和量比计算，接口返回数据时间、来源及是否为历史快照。

投资组合页面通过 `/api/etfs/hot-sectors` 展示 A 股股票行业 ETF 热门板块。工作流 `.github/workflows/market-snapshot.yml` 在工作日北京时间 15:15 更新 A 股、板块、ETF、港股和美股快照；实时接口最多每 10 分钟刷新一次，行情源失败时保留上一份有效快照。

## 免责声明

本工具仅供研究和学习使用，分析结果不构成投资建议。投资有风险，决策需谨慎。
