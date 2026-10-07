"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  LayoutDashboard,
  Settings,
  Star,
  Target,
} from "lucide-react";

import { cn } from "@/lib/utils";

const items = [
  { name: "仪表盘", href: "/dashboard", icon: LayoutDashboard },
  { name: "自选", href: "/watchlist", icon: Star },
  { name: "盯盘", href: "/watchlist/monitor", icon: Activity },
  { name: "选股", href: "/stock-picker", icon: Target },
  { name: "我的", href: "/settings", icon: Settings },
] as const;

function isActive(pathname: string, href: string) {
  if (href === "/watchlist") return pathname === "/watchlist";
  return pathname === href || pathname.startsWith(`${href}/`);
}

/**
 * 移动端底部标签栏。仅在小屏显示（lg 以上由侧边栏承担导航）。
 * 预留 iOS 安全区，避免被 Home Indicator 遮挡。
 */
export function MobileTabBar() {
  const pathname = usePathname();

  return (
    <nav
      data-slot="mobile-tab-bar"
      aria-label="移动端主导航"
      className="fixed inset-x-0 bottom-0 z-40 border-t bg-background/95 pb-[env(safe-area-inset-bottom)] backdrop-blur supports-[backdrop-filter]:bg-background/80 lg:hidden"
    >
      <ul className="grid grid-cols-5">
        {items.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex h-14 min-h-11 flex-col items-center justify-center gap-1 text-[11px] font-medium transition-colors",
                  active
                    ? "text-primary"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                <item.icon className="h-5 w-5" aria-hidden="true" />
                <span>{item.name}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
