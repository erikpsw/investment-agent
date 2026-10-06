import type { FormulaRankingItem } from "./api";

// Match the detail API's input aliases; returned identities must be canonical.
export function securityIdentity(input: string): [string, string] | undefined {
  const value = input.trim();
  if (/^(sh|sz|bj)\d{6}$/i.test(value)) return [value.toLowerCase(), "CN"];
  if (/^\d{6}$/.test(value)) return [(value.startsWith("6") ? "sh" : /^[489]/.test(value) ? "bj" : "sz") + value, "CN"];
  if (/^(hk\d{4,5}|\d{4,5}(\.hk)?)$/i.test(value)) {
    return ["hk" + value.toLowerCase().replace(/^hk/, "").replace(/\.hk$/, "").padStart(5, "0"), "HK"];
  }
  if (/^[a-z][a-z0-9.-]{0,14}$/i.test(value)) return [value.toUpperCase(), "US"];
}

export function validScoreItem(value: unknown): value is FormulaRankingItem {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const item = value as Record<string, unknown>;
  const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
  if (!finite(item.formula_score) || item.formula_score < 0 || item.formula_score > 100 || typeof item.recommendation !== "string") return false;
  if (item.data_coverage !== undefined && (!finite(item.data_coverage) || item.data_coverage < 0 || item.data_coverage > 1)) return false;
  for (const key of ["risks", "missing_fields"]) {
    const list = item[key];
    if (list !== undefined && (!Array.isArray(list) || !list.every(v => typeof v === "string"))) return false;
  }
  for (const key of ["weights", "contributions", "components"]) {
    const record = item[key];
    if (record === undefined) continue;
    if (!record || typeof record !== "object" || Array.isArray(record)) return false;
    if (!Object.values(record).every(v => finite(v) && v >= 0 && (key !== "weights" || v <= 1))) return false;
  }
  const factors = ["5日动量", "20日趋势", "60日趋势", "今日动量", "量比", "换手率", "估值", "市值质量"];
  const weights = item.weights as Record<string, number> | undefined;
  const contributions = item.contributions as Record<string, number> | undefined;
  const components = item.components as Record<string, number> | undefined;
  // A complete factor map identifies the current detailed response. Partial
  // legacy records remain partial; never invent its missing arithmetic inputs.
  const complete = [weights, contributions, components].some(record => record && factors.every(name => name in record));
  if (complete) {
    if (!weights || !contributions || !components || !finite(components["风险惩罚"]) || !finite(item.data_coverage) || !Array.isArray(item.missing_fields)) return false;
    if (Object.keys(weights).length !== factors.length || Object.keys(contributions).length !== factors.length) return false;
    if (components["风险惩罚"] > 100 || factors.some(name => !finite(weights[name]) || !finite(contributions[name]) || !finite(components[name]) || components[name] > 100)) return false;
    if (Math.abs(Object.values(weights).reduce((sum, weight) => sum + weight, 0) - 1) > 1e-8) return false;
    // Components and contributions are each rounded from unrounded engine
    // values; their independent half-unit errors both contribute here.
    if (factors.some(name => Math.abs(components[name] * weights[name] - contributions[name]) > .00005 * (1 + weights[name]) + 1e-8)) return false;
    const unclipped = factors.reduce((sum, name) => sum + contributions[name], 0) - components["风险惩罚"];
    const score = Math.max(0, Math.min(100, unclipped));
    if (Math.abs(item.formula_score - score) > .05000001 || Math.abs(item.formula_score * 10 - Math.round(item.formula_score * 10)) > 1e-8) return false;
    const fields = ["change_5d", "change_20d", "change_60d", "today_change_percent", "volume_ratio", "turnover_rate", "pe_ratio", "pb_ratio", "market_cap"];
    const missing = new Set(item.missing_fields as string[]);
    if (missing.size !== item.missing_fields.length || [...missing].some(field => !fields.includes(field))) return false;
    for (const field of fields) {
      if (!Object.prototype.hasOwnProperty.call(item, field)) continue;
      const v = item[field];
      if (v != null && !finite(v)) return false;
      const available = finite(v) && (!(field === "market_cap") || v > 0) && (!(field === "volume_ratio" || field === "turnover_rate") || v >= 0);
      if (available === missing.has(field)) return false;
    }
    if (factors.slice(0, 6).some((name, i) => missing.has(fields[i]) && components[name] !== 0)) return false;
    if ((missing.has("market_cap") && components["市值质量"] !== 0) || (missing.has("pe_ratio") && missing.has("pb_ratio") && components["估值"] !== 0)) return false;
    const coverage = factors.slice(0, 6).reduce((sum, name, i) => sum + weights[name] * Number(!missing.has(fields[i])), 0)
      + weights["估值"] * (.65 * Number(!missing.has("pe_ratio")) + .35 * Number(!missing.has("pb_ratio")))
      + weights["市值质量"] * Number(!missing.has("market_cap"));
    if (Math.abs(item.data_coverage - coverage) > .00005001) return false;
  }
  return true;
}

