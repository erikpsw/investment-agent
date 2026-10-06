import { z } from "zod";

const metrics = z.object({ net_return: z.number().finite().min(-1), max_drawdown: z.number().finite().min(0).max(1), average_exposure: z.number().finite().min(0).max(1), days: z.literal(400) });
const counts = z.object({ before: z.number().int().min(0).max(1120), after: z.number().int().min(0).max(1120) });
const row = (mode: "balanced" | "conservative" | "aggressive") => z.object({ mode: z.literal(mode), before: metrics, after: metrics, cost_stress: z.tuple([metrics.extend({ one_way_cost: z.literal(.003) }), metrics.extend({ one_way_cost: z.literal(.005) })]) });
const schema = z.object({ schema: z.literal("us-cover-research-summary-v1"), status: z.literal("research_only"), market: z.literal("US"), applied: z.literal(false), historical_mapping_complete: z.literal(false), available_count: z.literal(56), requested_count: z.literal(60), download_failure_count: z.literal(3), excluded_fund_count: z.literal(1), train_days: z.literal(240), test_days: z.literal(80), fold_count: z.literal(5), test_start: z.literal("2024-12-09"), test_end: z.literal("2026-07-16"), coverage: z.object({ denominator: z.literal(1120), market_cap: counts, pe_ratio: counts, pb_ratio: counts }), modes: z.tuple([row("balanced"), row("conservative"), row("aggressive")]) }).refine(d => d.coverage.market_cap.after >= d.coverage.market_cap.before && [d.coverage.pe_ratio, d.coverage.pb_ratio].every(c => c.before === c.after));
export type UsCoverSummary = z.infer<typeof schema>;
export function validateUsCoverSummary(value: unknown): UsCoverSummary { return schema.parse(value); }
