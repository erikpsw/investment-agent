"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  LineChart,
  Search,
  FileText,
  Settings,
  TrendingUp,
  PanelLeftClose,
  PanelLeft,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const navigation = [
  { name: "仪表盘", href: "/", icon: LayoutDashboard },
  { name: "行情搜索", href: "/search", icon: Search },
  { name: "个股分析", href: "/stock", icon: LineChart },
  { name: "财报数据", href: "/financials", icon: FileText },
];

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("sidebar-collapsed");
    if (saved !== null) {
      setCollapsed(saved === "true");
    }
  }, []);

  const toggleCollapse = () => {
    const newState = !collapsed;
    setCollapsed(newState);
    localStorage.setItem("sidebar-collapsed", String(newState));
  };

  return (
    <TooltipProvider delayDuration={0}>
      <div
        className={cn(
          "flex h-full flex-col border-r bg-background transition-all duration-300",
          collapsed ? "w-16" : "w-64"
        )}
      >
        <div className="flex h-14 items-center border-b px-3 justify-between">
          <Link
            href="/"
            className={cn(
              "flex items-center gap-2 font-semibold overflow-hidden",
              collapsed && "justify-center"
            )}
          >
            <TrendingUp className="h-6 w-6 text-primary shrink-0" />
            {!collapsed && <span className="text-lg truncate">Investment Agent</span>}
          </Link>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 shrink-0"
            onClick={toggleCollapse}
          >
            {collapsed ? (
              <PanelLeft className="h-4 w-4" />
            ) : (
              <PanelLeftClose className="h-4 w-4" />
            )}
          </Button>
        </div>

        <ScrollArea className="flex-1 px-2 py-4">
          <nav className="flex flex-col gap-1">
            {navigation.map((item) => {
              const isActive =
                pathname === item.href ||
                (item.href !== "/" && pathname.startsWith(item.href));

              const navItem = (
                <Link
                  key={item.name}
                  href={item.href}
                  className={cn(
                    "flex items-center rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    "hover:bg-accent hover:text-accent-foreground",
                    collapsed ? "justify-center px-2" : "justify-start gap-3",
                    isActive && "bg-secondary text-secondary-foreground"
                  )}
                >
                  <item.icon className="h-4 w-4 shrink-0" />
                  {!collapsed && <span className="truncate">{item.name}</span>}
                </Link>
              );

              if (collapsed) {
                return (
                  <Tooltip key={item.name}>
                    <TooltipTrigger asChild>
                      {navItem}
                    </TooltipTrigger>
                    <TooltipContent side="right">
                      <p>{item.name}</p>
                    </TooltipContent>
                  </Tooltip>
                );
              }

              return navItem;
            })}
          </nav>

          {!collapsed && (
            <>
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
            </>
          )}
        </ScrollArea>

        <div className={cn("border-t", collapsed ? "p-2" : "p-4")}>
          {collapsed ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <Link
                  href="/settings"
                  className="flex items-center justify-center rounded-md p-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground"
                >
                  <Settings className="h-4 w-4" />
                </Link>
              </TooltipTrigger>
              <TooltipContent side="right">
                <p>设置</p>
              </TooltipContent>
            </Tooltip>
          ) : (
            <>
              <Link
                href="/settings"
                className="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground"
              >
                <Settings className="h-4 w-4" />
                设置
              </Link>
              <p className="text-xs text-muted-foreground mt-2 text-center">
                v1.0.0 · 仅供研究学习
              </p>
            </>
          )}
        </div>
      </div>
    </TooltipProvider>
  );
}
