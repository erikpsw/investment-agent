type Values = { pe_ratio?: number | null; pb_ratio?: number | null; eps?: number | null; pe_basis?: string | null; pe_source?: string | null; source?: string | null; pb_source?: string | null };
const finite = (value: unknown): number | null => typeof value === "number" && Number.isFinite(value) ? value : null;

export function detailValuation(quote: Values | null | undefined, financials: Values | null | undefined) {
  const q = quote || {}; const f = financials || {};
  const pe = finite(f.pe_ratio) !== null || f.pe_basis === "TTM" ? f : q;
  const pb = finite(f.pb_ratio) !== null ? f : q;
  return { pe_ratio: finite(pe.pe_ratio), pb_ratio: finite(pb.pb_ratio), eps: finite(pe.eps), pe_basis: pe.pe_basis ?? null, pe_source: pe.pe_source || pe.source || null, pb_source: finite(pb.pb_ratio) !== null ? pb.pb_source || pb.source || null : null };
}
