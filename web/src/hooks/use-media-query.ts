"use client";

import { useCallback, useSyncExternalStore } from "react";

/**
 * SSR 安全的媒体查询 hook。
 *
 * 服务端渲染按 `serverSnapshot` 返回（默认 false），水合后切换为真实匹配结果。
 * 用它做「桌面表格 / 手机卡片」二选一，可以避免同一份数据在 DOM 里渲染两遍
 * （CSS 双渲染会让 aria/测试定位出现重复匹配，也会重复计算）。
 */
export function useMediaQuery(query: string, serverSnapshot = false) {
  const subscribe = useCallback(
    (onStoreChange: () => void) => {
      const mql = window.matchMedia(query);
      mql.addEventListener("change", onStoreChange);
      return () => mql.removeEventListener("change", onStoreChange);
    },
    [query],
  );

  const getSnapshot = useCallback(
    () => window.matchMedia(query).matches,
    [query],
  );

  return useSyncExternalStore(subscribe, getSnapshot, () => serverSnapshot);
}
