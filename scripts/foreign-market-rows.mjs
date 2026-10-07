function number(value) {
  if (value && typeof value === 'object') value = value.raw;
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

// HKEX equity RMB counters use 8xxxx; formula stock classification is applied separately.
export function eastmoneyHkRows(entries) {
  return entries.flatMap(q => {
    const code = String(q.f12 || '');
    if (!/^\d{1,5}$/.test(code) || Number(code) < 1 || Number(code) > 9999) return [];
    const price = number(q.f2), amount = number(q.f6);
    if (!(price > 0) || !(amount > 0)) return [];
    const cap = number(q.f20), floatCap = number(q.f21);
    return [{ticker:`hk${code.padStart(5, '0')}`,name:String(q.f14 || code),market:'HK',currency:'HKD',
      currency_basis:'HKEX HKD equity counter code range; non-stock types excluded before formula scoring',
      price,amount,today_change_percent:number(q.f3),turnover_rate:number(q.f8),volume_ratio:number(q.f10),
      market_cap:cap > 0 ? cap : null,float_market_cap:floatCap > 0 ? floatCap : null,
      pe_ratio:number(q.f9) || null,pb_ratio:number(q.f23) || null,
      valuation_basis:'Eastmoney f9 / f23 provider ratios; current snapshot, not historical PIT'}];
  });
}

// Provider valuation is a current snapshot. Never use it to reconstruct PIT history.
export function yahooRows(quotes, market) {
  if (!['HK', 'US'].includes(market)) throw new Error('Expected HK or US');
  const currency = market === 'HK' ? 'HKD' : 'USD';
  return quotes.flatMap(q => {
    if (q.currency !== currency) return [];
    const symbol = String(q.symbol || '');
    const hk = /^(\d{1,5})\.HK$/i.exec(symbol);
    if (market === 'HK' ? !hk : !/^[A-Z][A-Z0-9.-]{0,14}$/.test(symbol)) return [];
    const price = number(q.regularMarketPrice), volume = number(q.regularMarketVolume);
    if (!(price > 0) || !(volume > 0) || !Number.isFinite(price * volume)) return [];
    const average = number(q.averageDailyVolume3Month);
    const ticker = market === 'HK' ? `hk${hk[1].padStart(5, '0')}` : symbol;
    return [{ticker, name:q.longName || q.shortName || ticker, market, currency,
      price, amount:price * volume, today_change_percent:number(q.regularMarketChangePercent),
      turnover_rate:null, volume_ratio:average > 0 ? volume / average : null,
      market_cap:number(q.marketCap), pe_ratio:number(q.trailingPE), pb_ratio:number(q.priceToBook),
      quote_time:number(q.regularMarketTime),
      valuation_basis:'Yahoo trailingPE / priceToBook; current snapshot, not historical PIT'}];
  });
}
