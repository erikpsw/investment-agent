"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  LineChart,
  Search,
  FileText,
  Settings,
  TrendingUp,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";

const navigation = [
  { name: "仪表盘", href: "/", icon: LayoutDashboard },
  { name: "行情搜索", href: "/search", icon: Search },
  { name: "个股分析", href: "/stock", icon: LineChart },
  { name: "财报数据", href: "/financials", icon: FileText },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="flex h-full w-64 flex-col border-r bg-background">
      <div className="flex h-14 items-center border-b px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <TrendingUp className="h-6 w-6 text-primary" />
          <span className="text-lg">Investment Agent</span>
        </Link>
      </div>

      <ScrollArea className="flex-1 px-3 py-4">
        <nav className="flex flex-col gap-1">
          {navigation.map((item) => {
            const isActive =
              pathname === item.href ||
              (item.href !== "/" && pathname.startsWith(item.href));
            return (
              <Link key={item.name} href={item.href}>
                <Button
                  variant={isActive ? "secondary" : "ghost"}
                  className={cn(
                    "w-full justify-start gap-3",
                    isActive && "bg-secondary"
                  )}
                >
                  <item.icon className="h-4 w-4" />
                  {item.name}
                </Button>
              </Link>
            );
          })}
        </nav>

        <Separator className="my-4" />

        <div className="px-2">
          <p className="text-xs text-muted-foreground mb-2">市场</p>
          <div className="flex flex-wrap gap-1">
            <Button variant="outline" size="sm" className="h-7 text-xs">
              🇨🇳 A股
            </Button>
            <Button variant="outline" size="sm" className="h-7 text-xs">
              🇭🇰 港股
            </Button>
            <Button variant="outline" size="sm" className="h-7 text-xs">
              🇺🇸 美股
            </Button>
          </div>
        </div>
      </ScrollArea>

      <div className="border-t p-4">
        <Link href="/settings">
          <Button variant="ghost" className="w-full justify-start gap-3">
            <Settings className="h-4 w-4" />
            设置
          </Button>
        </Link>
        <p className="text-xs text-muted-foreground mt-2 text-center">
          v1.0.0 · 仅供研究学习
        </p>
      </div>
    </div>
  );
}
