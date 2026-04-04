"use client";

import { Search, Bell, User, Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Sidebar } from "./sidebar";

interface HeaderProps {
  onSearchClick?: () => void;
}

export function Header({ onSearchClick }: HeaderProps) {
  return (
    <header className="sticky top-0 z-50 flex h-14 items-center gap-4 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 px-4 lg:px-6">
      <Sheet>
        <SheetTrigger className="lg:hidden inline-flex items-center justify-center rounded-lg p-2 hover:bg-muted">
          <Menu className="h-5 w-5" />
          <span className="sr-only">Toggle menu</span>
        </SheetTrigger>
        <SheetContent side="left" className="p-0 w-64">
          <Sidebar />
        </SheetContent>
      </Sheet>

      <div className="flex-1 flex items-center gap-4">
        <Button
          variant="outline"
          className="w-full max-w-sm justify-start text-muted-foreground"
          onClick={onSearchClick}
        >
          <Search className="mr-2 h-4 w-4" />
          搜索股票...
          <kbd className="pointer-events-none ml-auto hidden h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground sm:flex">
            <span className="text-xs">⌘</span>K
          </kbd>
        </Button>
      </div>

      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon">
          <Bell className="h-5 w-5" />
          <span className="sr-only">Notifications</span>
        </Button>

        <DropdownMenu>
          <DropdownMenuTrigger className="inline-flex items-center justify-center rounded-lg p-2 hover:bg-muted">
            <Avatar className="h-8 w-8">
              <AvatarFallback>
                <User className="h-4 w-4" />
              </AvatarFallback>
            </Avatar>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>我的账户</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem>自选股</DropdownMenuItem>
            <DropdownMenuItem>持仓管理</DropdownMenuItem>
            <DropdownMenuItem>设置</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem>退出</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
