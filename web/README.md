# Investment Agent Web

基于 Next.js 15 + shadcn/ui 的投资分析前端。

## 技术栈

- **框架**: Next.js 15 (App Router)
- **UI**: shadcn/ui + Tailwind CSS v4
- **图表**: TradingView Lightweight Charts v5
- **状态**: TanStack Query v5
- **类型**: TypeScript

## 开发

```bash
# 安装依赖
npm install

# 启动开发服务器 (需要先启动后端 API)
npm run dev

# 构建生产版本
npm run build
```

## 后端 API

前端依赖 FastAPI 后端提供数据。启动后端:

```bash
cd ../api
uvicorn main:app --reload --port 8000
```

## 环境变量

```bash
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 功能

- 股票搜索 (支持中文名称)
- 实时行情展示
- K线图表 (日K/周K/分钟K)
- 均线指标 (MA5/MA20)
- 成交量分析
- 财务指标展示

## 项目结构

```
src/
├── app/                 # 页面
│   ├── page.tsx        # 首页仪表盘
│   └── stock/[ticker]/ # 个股详情
├── components/
│   ├── ui/             # shadcn 组件
│   ├── charts/         # 图表组件
│   ├── header.tsx
│   ├── sidebar.tsx
│   ├── stock-card.tsx
│   └── stock-search.tsx
├── hooks/              # 自定义 Hooks
├── lib/
│   ├── api.ts          # API 客户端
│   └── utils.ts
└── stores/             # 状态管理
```
