import { securityIdentity, validScoreItem } from "./formula-score-validation";

const currencies: Record<string, string> = { CN: "CNY", HK: "HKD", US: "USD" };

export function validScreenCandidates(value: unknown, requestedMarket?: string): boolean {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const result = value as Record<string, unknown>;
  if (!Array.isArray(result.items)) return false;
  // Empty needs-revision responses have no candidate scores or security links.
  if (result.items.length === 0) return true;
  if (typeof result.market !== "string" || !Object.hasOwn(currencies, result.market)
    || (requestedMarket !== undefined && result.market !== requestedMarket)
    || (result.currency !== undefined && result.currency !== currencies[result.market]) || result.items.length > 50) return false;
  const seen = new Set<string>();
  for (const candidate of result.items) {
    if (!validScoreItem(candidate) || candidate.market !== result.market || typeof candidate.ticker !== "string") return false;
    const identity = securityIdentity(candidate.ticker);
    if (!identity || identity[0] !== candidate.ticker || identity[1] !== result.market || seen.has(candidate.ticker)) return false;
    if (candidate.name !== undefined && typeof candidate.name !== "string") return false;
    const reasons = (candidate as unknown as Record<string, unknown>).match_reasons;
    if (!Array.isArray(reasons) || !reasons.every(reason => typeof reason === "string")) return false;
    seen.add(candidate.ticker);
  }
  return true;
}
