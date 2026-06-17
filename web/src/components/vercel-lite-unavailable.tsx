"use client";

import Link from "next/link";
import { AlertCircle, ArrowLeft } from "lucide-react";
import { Header } from "@/components/header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface VercelLiteUnavailableProps {
  title: string;
  description: string;
}

export function VercelLiteUnavailable({
  title,
  description,
}: VercelLiteUnavailableProps) {
  return (
    <>
      <Header />
      <main className="flex flex-1 items-center justify-center p-6">
        <Card className="w-full max-w-2xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-amber-500" />
              {title}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm leading-6 text-muted-foreground">
              {description}
            </p>
            <p className="text-sm leading-6 text-muted-foreground">
              当前 Vercel 轻量版优先开放搜索、行情、K 线、财务数据、新闻和公告查询。需要 PDF/RAG、长任务 Agent 或实时监控时，请使用本地完整后端或后续迁移到独立任务服务。
            </p>
            <Link href="/">
              <Button variant="outline">
                <ArrowLeft className="mr-2 h-4 w-4" />
                返回仪表盘
              </Button>
            </Link>
          </CardContent>
        </Card>
      </main>
    </>
  );
}
