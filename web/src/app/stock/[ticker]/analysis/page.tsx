"use client";

import { VercelLiteUnavailable } from "@/components/vercel-lite-unavailable";

export default function AnalysisPage() {
  return (
    <VercelLiteUnavailable
      title="AI 深度分析暂未在 Vercel 轻量版开放"
      description="AI 深度分析会调用 LangGraph、LLM 流式输出、财报 PDF 分析和本地缓存，当前轻量部署先保留核心行情与财务查询能力。"
    />
  );
}

