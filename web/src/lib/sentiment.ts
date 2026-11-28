export type SentimentRegime =
  | "extreme_fear"
  | "fear"
  | "neutral"
  | "greed"
  | "extreme_greed";

export type ResonanceSignal =
  | "bottom"
  | "right_turn"
  | "top"
  | "watch_bottom"
  | "watch_top"
  | "none";

export interface RegimeVisualMeta {
  label: string;
  accentHex: string;
  badgeClass: string;
  barClass: string;
  ringClass: string;
}

export const REGIME_META: Record<SentimentRegime, RegimeVisualMeta> = {
  extreme_fear: {
    label: "极度恐慌",
    accentHex: "#0ea5e9",
    badgeClass:
      "border-sky-500/30 bg-sky-500/12 text-sky-700 dark:text-sky-300",
    barClass: "bg-sky-500",
    ringClass: "border-sky-500/30 bg-sky-500/5",
  },
  fear: {
    label: "恐慌偏冷",
    accentHex: "#14b8a6",
    badgeClass:
      "border-teal-500/30 bg-teal-500/12 text-teal-700 dark:text-teal-300",
    barClass: "bg-teal-500",
    ringClass: "border-teal-500/25 bg-teal-500/5",
  },
  neutral: {
    label: "中性震荡",
    accentHex: "#f59e0b",
    badgeClass:
      "border-amber-500/30 bg-amber-500/12 text-amber-700 dark:text-amber-300",
    barClass: "bg-amber-500",
    ringClass: "border-border bg-muted/30",
  },
  greed: {
    label: "乐观偏热",
    accentHex: "#f97316",
    badgeClass:
      "border-orange-500/30 bg-orange-500/12 text-orange-700 dark:text-orange-300",
    barClass: "bg-orange-500",
    ringClass: "border-orange-500/25 bg-orange-500/5",
  },
  extreme_greed: {
    label: "极度贪婪",
    accentHex: "#ef4444",
    badgeClass:
      "border-red-500/30 bg-red-500/12 text-red-700 dark:text-red-300",
    barClass: "bg-red-500",
    ringClass: "border-red-500/30 bg-red-500/5",
  },
};

export function getRegimeMeta(regime: string): RegimeVisualMeta {
  return REGIME_META[regime as SentimentRegime] ?? REGIME_META.neutral;
}

/** Map 0..100 sentiment score onto semi-circle gauge needle angle (-90deg..+90deg). */
export function gaugeArcAngle(score: number): number {
  const clamped = Number.isFinite(score) ? Math.max(0, Math.min(100, score)) : 50;
  return Number((((clamped / 100) * 180) - 90).toFixed(2));
}

export function formatSentimentDelta(
  delta: number | null | undefined,
  prefix = "",
): string {
  if (delta == null || !Number.isFinite(delta)) return "--";
  const sign = delta > 0 ? "+" : "";
  return `${prefix}${sign}${delta.toFixed(1)}`;
}

export function resonanceBadgeMeta(signal: string): {
  tone: "bottom" | "right_turn" | "top" | "watch" | "neutral";
  containerClass: string;
  badgeClass: string;
} {
  switch (signal as ResonanceSignal) {
    case "right_turn":
      return {
        tone: "right_turn",
        containerClass:
          "border-teal-500/45 bg-teal-500/12 text-teal-900 dark:text-teal-200",
        badgeClass:
          "border-teal-500/45 bg-teal-500/20 text-teal-700 dark:text-teal-300",
      };
    case "bottom":
      return {
        tone: "bottom",
        containerClass:
          "border-emerald-500/40 bg-emerald-500/10 text-emerald-900 dark:text-emerald-200",
        badgeClass:
          "border-emerald-500/40 bg-emerald-500/20 text-emerald-700 dark:text-emerald-300",
      };
    case "top":
      return {
        tone: "top",
        containerClass:
          "border-red-500/40 bg-red-500/10 text-red-900 dark:text-red-200",
        badgeClass:
          "border-red-500/40 bg-red-500/20 text-red-700 dark:text-red-300",
      };
    case "watch_bottom":
      return {
        tone: "watch",
        containerClass:
          "border-sky-500/30 bg-sky-500/8 text-sky-900 dark:text-sky-200",
        badgeClass:
          "border-sky-500/30 bg-sky-500/15 text-sky-700 dark:text-sky-300",
      };
    case "watch_top":
      return {
        tone: "watch",
        containerClass:
          "border-orange-500/30 bg-orange-500/8 text-orange-900 dark:text-orange-200",
        badgeClass:
          "border-orange-500/30 bg-orange-500/15 text-orange-700 dark:text-orange-300",
      };
    default:
      return {
        tone: "neutral",
        containerClass: "border-border/70 bg-muted/40 text-muted-foreground",
        badgeClass: "border-border bg-background text-muted-foreground",
      };
  }
}
