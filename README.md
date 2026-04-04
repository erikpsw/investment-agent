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
# 安装 Python 依赖
pip3 install -r requirements.txt

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

## 免责声明

本工具仅供研究和学习使用，分析结果不构成投资建议。投资有风险，决策需谨慎。
