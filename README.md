# Investment Agent

基于 LangGraph 的投资分析 Agent，支持 A股/港股/美股行情、财报分析、可视化等功能。

## 功能

- 实时行情查询（A股/港股/美股）
- 财报 PDF 下载与解析
- 财报语义搜索 (RAG)
- 财务可视化（收入趋势、杜邦分析等）
- 多 Agent 协作分析

## 安装

```bash
pip install -r requirements.txt

# 下载中文 embedding 模型
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')"
```

## 配置

复制 `.env.example` 为 `.env` 并填入 API Key：

```bash
cp .env.example .env
```

## 运行

```bash
streamlit run app.py
```

## 项目结构

```
investment/
├── app.py              # Streamlit 入口
├── agents/             # LangGraph Agent
├── data/               # 数据获取层
├── reports/            # 财报处理
├── viz/                # 可视化模块
├── ui/                 # Streamlit 页面
├── storage/            # 本地存储
└── utils/              # 工具函数
```

## 免责声明

本工具仅供研究和学习使用，分析结果不构成投资建议。投资有风险，决策需谨慎。
