import { toUtcIso } from "./analysis";
import type { AnalysisFilters, ForecastAccuracyResponse, SavedAnalysis, SourceMetadata } from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
export class ApiError extends Error {
  constructor(message: string, public readonly status?: number, public readonly kind: "network" | "http" | "schema" = "http") { super(message); this.name = "ApiError"; }
}

const object = (value: unknown): value is Record<string, unknown> => Boolean(value) && typeof value === "object" && !Array.isArray(value);
const finite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const nullableFinite = (value: unknown) => value === null || finite(value);
const nonNegativeInteger = (value: unknown) => Number.isInteger(value) && (value as number) >= 0;
const timestamp = (value: unknown) => typeof value === "string" && Number.isFinite(Date.parse(value));

function debugAnalyticsContract(value: unknown): void {
  if (!object(value)) {
    console.error("Analytics response is not an object", value);
    return;
  }

  console.log("Analytics response keys:", Object.keys(value));
  console.log("Analytics contract checks:", {
    period: object(value.period),
    cutoff: object(value.cutoff),
    forecast_history: object(value.forecast_history),
    metrics: object(value.metrics),
    quality: object(value.quality),
    comparisonsArray: Array.isArray(value.comparisons),
    assumptionsArray: Array.isArray(value.assumptions),
  });
}
function isAnalytics(value: unknown): value is ForecastAccuracyResponse {
  if (!object(value) || !object(value.period) || !object(value.cutoff) || !object(value.forecast_history) || !object(value.metrics) || !object(value.quality)) return false;
  const m = value.metrics, q = value.quality, h = value.forecast_history;
  const qualityKeys = ["actual_intervals_count", "forecast_intervals_count", "matched_intervals_count", "missing_forecast_count", "no_eligible_forecast_count", "missing_actual_count", "invalid_record_count", "duplicate_record_count", "unmatched_forecast_count"];
  return timestamp(value.period.start) && timestamp(value.period.end) && timestamp(value.cutoff.effective_time) && typeof value.cutoff.interpretation === "string"
    && timestamp(h.publication_from) && timestamp(h.publication_to) && nonNegativeInteger(h.history_horizon_days) && h.completeness === "bounded"
    && nullableFinite(m.mae) && nullableFinite(m.rmse) && nullableFinite(m.bias) && nonNegativeInteger(m.matched_intervals_count)
    && qualityKeys.every((key) => nonNegativeInteger(q[key]))
    && Array.isArray(value.comparisons) && value.comparisons.every((item) => object(item) && timestamp(item.start_time) && timestamp(item.forecast_publish_time) && finite(item.actual_generation) && finite(item.forecast_generation) && finite(item.error) && finite(item.absolute_error) && finite(item.squared_error))
    && Array.isArray(value.assumptions) && value.assumptions.every((item) => typeof item === "string");
}

function isSources(value: unknown): value is SourceMetadata[] {
  const statuses = new Set(["not_checked", "healthy", "unavailable", "error"]);
  return Array.isArray(value) && value.every((item) => object(item) && (item.dataset === "FUELHH" || item.dataset === "WINDFOR") && typeof item.documentation_url === "string" && typeof item.configured === "boolean" && statuses.has(String(item.last_retrieval_status)) && (item.last_successful_retrieval === null || timestamp(item.last_successful_retrieval)) && (item.last_error_summary === null || typeof item.last_error_summary === "string") && (item.last_record_count === null || nonNegativeInteger(item.last_record_count)));
}

async function request<T>(path: string, validate: (value: unknown) => value is T, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try { response = await fetch(`${API_BASE}${path}`, { signal }); }
  catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError("Cannot connect to WindSight API. Check that the backend is running on port 8001.", undefined, "network");
  }
  let body: unknown;
  try { body = await response.json(); }
  catch { throw new ApiError("The API returned an unreadable response.", response.status, "schema"); }
  if (!response.ok) {
    const message = object(body) && object(body.error) && typeof body.error.message === "string" ? body.error.message : `The API request failed (${response.status}).`;
    throw new ApiError(message, response.status, "http");
  }
  
  if (!validate(body)) {
  if (path.includes("forecast-accuracy")) {
    debugAnalyticsContract(body);
  }

  throw new ApiError(
    "The API response does not match the current WindSight contract.",
    response.status,
    "schema"
  );
}
  return body;
}

const savedAnalysis = (value: unknown): value is SavedAnalysis => object(value)
  && typeof value.id === "string" && typeof value.name === "string"
  && timestamp(value.period_start) && timestamp(value.period_end) && timestamp(value.cutoff)
  && timestamp(value.created_at) && timestamp(value.updated_at);

async function protectedRequest<T>(path: string, token: string, init: RequestInit, validate?: (value: unknown) => value is T): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...init.headers },
    });
  } catch {
    throw new ApiError("Cannot connect to WindSight API. Check that the backend is running on port 8001.", undefined, "network");
  }
  if (response.status === 204) return undefined as T;
  let body: unknown;
  try { body = await response.json(); }
  catch { throw new ApiError("The API returned an unreadable response.", response.status, "schema"); }
  if (!response.ok) {
    const message = object(body) && typeof body.detail === "string" ? body.detail
      : object(body) && object(body.error) && typeof body.error.message === "string" ? body.error.message
      : `The API request failed (${response.status}).`;
    throw new ApiError(message, response.status, "http");
  }
  if (validate && !validate(body)) throw new ApiError("The API response does not match the current WindSight contract.", response.status, "schema");
  return body as T;
}

export function fetchForecastAccuracy(filters: AnalysisFilters, signal?: AbortSignal) {
  const params = new URLSearchParams({ from: toUtcIso(filters.startDate, filters.startTime), to: toUtcIso(filters.endDate, filters.endTime), cutoff: toUtcIso(filters.cutoffDate, filters.cutoffTime) });
  return request(`/api/v1/analytics/forecast-accuracy?${params}`, isAnalytics, signal);
}
export function fetchDataSources(signal?: AbortSignal) { return request("/api/v1/data-sources", isSources, signal); }
export function listSavedAnalyses(token: string) {
  return protectedRequest("/api/v1/saved-analyses", token, { method: "GET" }, (value): value is SavedAnalysis[] => Array.isArray(value) && value.every(savedAnalysis));
}
export function createSavedAnalysis(token: string, name: string, filters: AnalysisFilters) {
  return protectedRequest("/api/v1/saved-analyses", token, { method: "POST", body: JSON.stringify({ name, period_start: toUtcIso(filters.startDate, filters.startTime), period_end: toUtcIso(filters.endDate, filters.endTime), cutoff: toUtcIso(filters.cutoffDate, filters.cutoffTime) }) }, savedAnalysis);
}
export function renameSavedAnalysis(token: string, id: string, name: string) {
  return protectedRequest(`/api/v1/saved-analyses/${encodeURIComponent(id)}`, token, { method: "PATCH", body: JSON.stringify({ name }) }, savedAnalysis);
}
export function deleteSavedAnalysis(token: string, id: string) {
  return protectedRequest<void>(`/api/v1/saved-analyses/${encodeURIComponent(id)}`, token, { method: "DELETE" });
}
