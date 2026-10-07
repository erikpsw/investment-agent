"use client";

import { useUser } from "@auth0/nextjs-auth0";
import Link from "next/link";
import { Database, LogIn, ShieldCheck, UserRound } from "lucide-react";

import { Header } from "@/components/header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function SettingsPage() {
  const { user, isLoading } = useUser();

  return <div className="flex min-h-screen flex-col"><Header /><main className="flex-1 space-y-6 p-4 sm:p-6"><div><h1 className="text-2xl sm:text-3xl font-bold tracking-tight">账户设置</h1><p className="mt-1 text-muted-foreground">查看账户状态与行情数据的更新策略。</p></div><div className="grid gap-4 lg:grid-cols-2"><Card><CardHeader><CardTitle className="flex items-center gap-2"><UserRound className="size-5" />账户</CardTitle><CardDescription>登录状态由 Auth0 管理。</CardDescription></CardHeader><CardContent>{isLoading ? <div className="h-5 w-40 animate-pulse rounded bg-muted" /> : user ? <div className="space-y-1"><p className="font-medium">{user.name || "已登录"}</p><p className="text-sm text-muted-foreground">{user.email}</p></div> : <Button render={<Link href="/auth/login?returnTo=/settings" prefetch={false} />}><LogIn className="mr-2 size-4" />登录 / 注册</Button>}</CardContent></Card><Card><CardHeader><CardTitle className="flex items-center gap-2"><Database className="size-5" />行情缓存</CardTitle><CardDescription>自选股先返回批量报价，再在后台准备走势、指标和新闻。</CardDescription></CardHeader><CardContent className="space-y-2 text-sm text-muted-foreground"><p>交易时段内，报价最多每 15 秒更新一次。</p><p>收盘后复用最近有效收盘数据，避免重复请求行情源。</p><p>日线、技术指标与新闻会在后台预热，打开侧栏时优先展示已缓存数据。</p></CardContent></Card><Card className="lg:col-span-2"><CardHeader><CardTitle className="flex items-center gap-2"><ShieldCheck className="size-5" />数据与隐私</CardTitle></CardHeader><CardContent className="text-sm text-muted-foreground">自选股和投资组合按当前登录账户隔离保存；行情缓存仅存储公开市场数据。</CardContent></Card></div></main></div>;
}
