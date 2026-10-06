/** Display analytical levels without rounding a positive protection gap away. */
export function formatRiskPrice(value?: number, smallestGap?: number): string {
  if (value == null || !Number.isFinite(value) || value <= 0) return "--";
  const gap = smallestGap != null && Number.isFinite(smallestGap) && smallestGap > 0 ? smallestGap : value;
  // Fixed notation has at most 20 fractional digits. Scientific notation also
  // preserves adjacent representable values when the price/gap is extreme.
  if (value < 1e-10 || value >= 1e21 || gap < 1e-15) return value.toExponential(16);
  const digits = Math.min(20, Math.max(2, value < 1 ? 5 - Math.floor(Math.log10(value)) : 2, 2 - Math.floor(Math.log10(gap))));
  return value.toFixed(digits).replace(/(\.\d{2}.*?)0+$/, "$1");
}
