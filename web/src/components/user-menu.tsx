"use client";

import { useEffect, useState } from "react";
import { LogOut, Settings, User, WalletCards } from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { profileInitials, type PublicUserProfile } from "@/lib/user-profile";

export function UserMenu() {
  const [profile, setProfile] = useState<PublicUserProfile>({});

  useEffect(() => {
    const controller = new AbortController();
    fetch("/account/profile", {
      credentials: "same-origin",
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) return {};
        const payload = (await response.json()) as { user?: PublicUserProfile | null };
        return payload.user || {};
      })
      .then(setProfile)
      .catch((error: unknown) => {
        if (error instanceof Error && error.name === "AbortError") return;
        setProfile({});
      });
    return () => controller.abort();
  }, []);

  const initial = profileInitials(profile);
  const accountLabel = profile.name || profile.email || "我的账户";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="账户菜单"
        className="inline-flex items-center justify-center rounded-lg p-1 hover:bg-muted"
      >
        <Avatar className="h-8 w-8">
          {profile.picture && <AvatarImage src={profile.picture} alt={accountLabel} />}
          <AvatarFallback>
            {initial || <User className="h-4 w-4" />}
          </AvatarFallback>
        </Avatar>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-48">
        <DropdownMenuLabel className="max-w-56 truncate">{accountLabel}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem render={<a href="/portfolio" />}>
          <WalletCards />投资组合
        </DropdownMenuItem>
        <DropdownMenuItem render={<a href="/settings" />}>
          <Settings />设置
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive" render={<a href="/auth/logout" />}>
          <LogOut />退出登录
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
