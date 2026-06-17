"use client";

import { VercelLiteUnavailable } from "@/components/vercel-lite-unavailable";

export default function MonitorPage() {
  return (
    <VercelLiteUnavailable
      title="实时盯盘暂未在 Vercel 轻量版开放"
      description="实时盯盘依赖持续轮询、运行日志、本地状态文件和提醒决策，属于长时间后台任务，不适合直接运行在 Vercel 请求函数内。"
    />
  );
}

