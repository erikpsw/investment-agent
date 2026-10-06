import type { FormulaRankingItem } from "./api";

type Plan = NonNullable<FormulaRankingItem["risk_plan"]>;
const currencies: Record<string, string> = { CN: "CNY", HK: "HKD", US: "USD" };

export function validRiskPlan(value: unknown, market?: string): value is Plan {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const p = value as Record<string, unknown>;
  const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
  if (p.status !== "ok" || !market || !currencies[market] || p.currency !== currencies[market]) return false;
  for (const key of ["reference_price", "stop_loss", "take_profit_1", "take_profit_2", "atr14", "trailing_distance"]) {
    if (!finite(p[key]) || p[key] <= 0) return false;
  }
  // Narrowed above; keep the arithmetic local and never coerce response values.
  const reference = p.reference_price as number, stop = p.stop_loss as number;
  if (!(stop < reference && reference < (p.take_profit_1 as number) && (p.take_profit_1 as number) < (p.take_profit_2 as number))) return false;
  for (const key of ["stop_distance_percent", "position_cap_percent", "risk_budget_percent"]) {
    if (!finite(p[key]) || p[key] <= 0 || p[key] > 100) return false;
  }
  const distance = (reference - stop) / reference * 100;
  if (!Number.isFinite(distance) || Math.abs((p.stop_distance_percent as number) - distance) > Math.max(1e-8, distance * 1e-8)) return false;
  for (const key of ["basis", "limitations"]) {
    if (p[key] !== undefined && (!Array.isArray(p[key]) || !(p[key] as unknown[]).every(v => typeof v === "string"))) return false;
  }
  for (const key of ["history_as_of", "quote_as_of", "history_timing_status"]) {
    if (p[key] != null && typeof p[key] !== "string") return false;
  }
  for (const key of ["support20", "resistance20"]) {
    if (p[key] != null && (!finite(p[key]) || p[key] <= 0)) return false;
  }
  if (p.history_lag_calendar_days != null && (!finite(p.history_lag_calendar_days) || p.history_lag_calendar_days < 0)) return false;
  return true;
}
