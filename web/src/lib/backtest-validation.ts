import { z } from "zod";

type Mode = "balanced" | "conservative" | "aggressive";
const number = z.number().finite();
const count = number.int().nonnegative();
const date = z.string().regex(/^\d{4}-\d{2}-\d{2}$/).refine(value => {
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
});
const curve = z.array(z.object({ date, equity: number.nonnegative() })).refine(rows => rows.every((row, i) => !i || rows[i - 1].date < row.date));
const metrics = z.object({
  net_return: number.min(-1), max_drawdown: number.min(0).max(1), sharpe_zero_rate: number, days: count.optional(),
  equity_curve: curve, average_exposure: number.min(0).max(1).optional(),
  missing_quote_days: count.optional(), stale_quote_days: count.optional(), max_quote_age_calendar_days: count.optional(),
  risk_unverifiable_days: count.nullable().optional(), risk_missing_entries: count.nullable().optional(),
  risk_evaluation_status: z.string().optional(),
});
const coverage = z.object({ available: count, observations: count, basis: z.string() }).refine(value => value.available <= value.observations);
const weights = z.record(z.string(), number.min(0).max(1).nullable());
const schema = z.object({
  status: z.string().min(1), applied: z.boolean(), formula_mode: z.enum(["balanced", "conservative", "aggressive"]).optional(),
  scoring_input_fingerprint: z.string().optional(),
  mode_risk_defaults: z.object({ risk_budget_percent: number.positive(), position_cap_percent: number.positive(), atr_multiple: number.positive() }).optional(),
  parameter_grid: z.array(weights).optional(),
  risk_protection_policy_version: z.string().optional(), risk_availability_as_of: date.optional(),
  risk_availability_policy: z.string().optional(), risk_availability_training_universe: z.array(z.string()).optional(),
  execution_lot_coverage: coverage.optional(), execution_risk_costs_included: z.boolean().optional(),
  execution_scenario: z.object({ market: z.enum(["CN", "HK", "US"]), initial_capital: number.positive(), minimum_fee: number.nonnegative(), entry_lot_size: count.positive().nullable(), lot_ledger: z.record(z.string(), z.unknown()).optional() }).nullable().optional(),
  volume_weight_tuning: z.object({ enabled: z.boolean(), weights: z.array(number.min(0).max(1)), policy: z.string() }).optional(),
  volume_reference_coverage: z.object({ status: z.string().optional(), available: count, observations: count, basis: z.string(), status_counts: z.record(z.string(), count) }).refine(value => value.available <= value.observations).optional(),
  selection_quality_policy: z.string().optional(),
  fundamental_coverage: z.object({ observations: count, pe_observations: count, pb_observations: count, cap_observations: count, missing_ledgers: z.array(z.string()), basis: z.string(), availability: z.string() }).refine(value => [value.pe_observations, value.pb_observations, value.cap_observations].every(n => n <= value.observations)).optional(),
  fundamental_mode: z.string().optional(), download_failures: z.array(z.object({ ticker: z.string() })).optional(),
  cost_stress: z.array(metrics.extend({ equity_curve: curve.optional(), one_way_cost: number.min(0).max(1), strategy: z.string() })).optional(),
  quality_failures: z.array(z.object({ ticker: z.string(), reason: z.string() })).optional(),
  message: z.string().optional(), formula_version: z.string().optional(), formula_scope: z.string().optional(), source: z.string().optional(),
  available_count: count.optional(), requested_count: count.optional(), selection_method: z.string().optional(), generated_at: z.string().optional(), limitations: z.array(z.string()).optional(),
  folds: z.array(z.object({
    train_start: date, train_end: date, test_start: date, test_end: date,
    candidate_weights: weights, candidate_risk_parameters: z.object({ atr_multiple: number.positive(), target_r: number.positive() }).nullable().optional(),
    weight_selection_status: z.string().optional(), risk_selection_status: z.string().optional(),
  }).refine(f => f.train_start <= f.train_end && f.train_end < f.test_start && f.test_start <= f.test_end)).optional(),
  out_of_sample: z.object({ candidate: metrics, baseline: metrics, benchmark: metrics, protected: metrics.optional(), risk_tuned: metrics.optional(), capped_control: metrics.optional() }).optional(),
});

/** Validate display inputs and retain original metadata, without filling legacy gaps. */
export function validateBacktestReport(value: unknown, mode: Mode): unknown {
  const report = schema.parse(value);
  if (report.out_of_sample && (report.formula_mode ?? "balanced") !== mode) throw new Error("回测模式与请求不匹配");
  return value;
}
