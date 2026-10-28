import type { AnalysisFilters, ForecastAccuracyResponse } from "./types";

const DAY_MS = 86_400_000;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const TIME = /^([01]\d|2[0-3]):[0-5]\d$/;

export function toDateInput(date: Date): string { return date.toISOString().slice(0, 10); }
export function getDefaultFilters(now = new Date()): AnalysisFilters {
  const end = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  const start = new Date(end.getTime() - 7 * DAY_MS);
  const startDate = toDateInput(start);
  return { startDate, startTime: "00:00", endDate: toDateInput(end), endTime: "00:00", cutoffDate: startDate, cutoffTime: "12:00" };
}
export function toUtcIso(date: string, time: string): string { return `${date}T${time}:00Z`; }
function isValidDate(value: string): boolean {
  if (!DATE.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}
export function validateFilters(filters: AnalysisFilters): Partial<Record<keyof AnalysisFilters, string>> {
  const errors: Partial<Record<keyof AnalysisFilters, string>> = {};
  if (!isValidDate(filters.startDate)) errors.startDate = "Choose a valid start date.";
  if (!TIME.test(filters.startTime)) errors.startTime = "Choose a valid start time.";
  if (!isValidDate(filters.endDate)) errors.endDate = "Choose a valid end date.";
  if (!TIME.test(filters.endTime)) errors.endTime = "Choose a valid end time.";
  if (!isValidDate(filters.cutoffDate)) errors.cutoffDate = "Choose a valid cutoff date.";
  if (!TIME.test(filters.cutoffTime)) errors.cutoffTime = "Choose a valid cutoff time.";
  if (Object.keys(errors).length) return errors;
  const start = Date.parse(toUtcIso(filters.startDate, filters.startTime));
  const end = Date.parse(toUtcIso(filters.endDate, filters.endTime));
  if (start >= end) errors.endDate = "End must be later than start.";
  else if (end - start > 7 * DAY_MS) errors.endDate = "Analysis periods cannot exceed seven days.";
  return errors;
}
function splitIso(value: string | null, dateFallback: string, timeFallback: string) {
  if (!value) return { date: dateFallback, time: timeFallback };
  if (DATE.test(value)) return { date: value, time: timeFallback };
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(value)) return { date: dateFallback, time: timeFallback };
  const parsed = new Date(value);
  if (!Number.isFinite(parsed.getTime())) return { date: dateFallback, time: timeFallback };
  return { date: parsed.toISOString().slice(0, 10), time: parsed.toISOString().slice(11, 16) };
}
export function filtersFromSearch(search: string, fallback = getDefaultFilters()): AnalysisFilters {
  const params = new URLSearchParams(search);
  const start = splitIso(params.get("from"), fallback.startDate, fallback.startTime);
  const end = splitIso(params.get("to"), fallback.endDate, fallback.endTime);
  const cutoffValue = params.get("cutoff");
  const cutoff = cutoffValue && TIME.test(cutoffValue) ? { date: start.date, time: cutoffValue } : splitIso(cutoffValue, fallback.cutoffDate, fallback.cutoffTime);
  const candidate = { startDate: start.date, startTime: start.time, endDate: end.date, endTime: end.time, cutoffDate: cutoff.date, cutoffTime: cutoff.time };
  return Object.keys(validateFilters(candidate)).length ? fallback : candidate;
}
export function filtersToSearch(filters: AnalysisFilters): string {
  return new URLSearchParams({ from: toUtcIso(filters.startDate, filters.startTime), to: toUtcIso(filters.endDate, filters.endTime), cutoff: toUtcIso(filters.cutoffDate, filters.cutoffTime) }).toString();
}
export function average(values: number[]): number | null { return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null; }
export function deriveSnapshot(data: ForecastAccuracyResponse | null) {
  const comparisons = data?.comparisons ?? [];
  return { actualAverage: average(comparisons.map((item) => item.actual_generation)), forecastAverage: average(comparisons.map((item) => item.forecast_generation)), mae: data?.metrics.mae ?? null, rmse: data?.metrics.rmse ?? null, bias: data?.metrics.bias ?? null };
}
