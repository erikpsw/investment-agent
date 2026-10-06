const sources: Record<string, string> = { Eastmoney: "东方财富", Tencent: "腾讯", Yahoo: "Yahoo" };
const bases: Record<string, string> = { raw: "原始价", qfq: "前复权", adjusted: "调整价", latest_raw_close_reference: "调整价换算至最近原始价" };
const record = (value: unknown): Record<string, unknown> => value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
const name = (value: unknown, labels: Record<string, string>) => typeof value === "string" && Object.hasOwn(labels, value) ? labels[value] : undefined;

export function historyPriceLabels(metadata: unknown) {
  const data = record(metadata), trend = record(data.trend), protection = record(data.protection);
  const provided = data.version === "history-price-metadata-v1";
  const label = (part: Record<string, unknown>) => {
    const source = name(part.source, sources), basis = name(part.price_basis, bases);
    return part.status === "reported" && source && basis ? `${source} · ${basis}` : undefined;
  };
  const mixed = provided && protection.status === "mixed";
  return { provided, mixed, trend: provided ? label(trend) || "价格口径未记录" : "价格口径未记录",
    protection: mixed ? "混合价格口径，未核验" : provided && protection.bar_count === 21 && label(protection)
      ? `${label(protection)}（最近21条）` : "价格口径未核验" };
}
