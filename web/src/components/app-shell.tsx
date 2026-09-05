"use client";

import { usePathname } from "next/navigation";
import { Providers } from "@/components/providers";
import { Sidebar } from "@/components/sidebar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (pathname === "/") return <>{children}</>;
  return (
    <Providers>
      <div className="flex min-h-screen">
        <aside className="hidden lg:block">
          <Sidebar />
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">{children}</div>
      </div>
    </Providers>
  );
}
