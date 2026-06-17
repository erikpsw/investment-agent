"use client";

import { VercelLiteUnavailable } from "@/components/vercel-lite-unavailable";

export default function StockPickerPage() {
  return (
    <VercelLiteUnavailable
      title="AI选股暂未在 Vercel 轻量版开放"
      description="AI选股会调用长任务 Agent、LLM、新闻聚合和本地结果存储，不适合直接运行在当前 Vercel Python Function 部署中。"
    />
  );
}

