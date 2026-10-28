export interface AccuracyMetrics { mae: number | null; rmse: number | null; bias: number | null; matched_intervals_count: number; }
export interface QualityCounts { actual_intervals_count: number; forecast_intervals_count: number; matched_intervals_count: number; missing_forecast_count: number; no_eligible_forecast_count: number; missing_actual_count: number; invalid_record_count: number; duplicate_record_count: number; unmatched_forecast_count: number; }
export interface IntervalComparison { start_time: string; actual_generation: number; forecast_generation: number; forecast_publish_time: string; error: number; absolute_error: number; squared_error: number; }
export interface ForecastHistoryDetails { publication_from: string; publication_to: string; history_horizon_days: number; completeness: "bounded"; }
export interface ForecastAccuracyResponse { period: { start: string; end: string }; cutoff: { effective_time: string; interpretation: string }; forecast_history: ForecastHistoryDetails; metrics: AccuracyMetrics; quality: QualityCounts; comparisons: IntervalComparison[]; assumptions: string[]; }
export type RetrievalStatus = "not_checked" | "healthy" | "unavailable" | "error";
export interface SourceMetadata { dataset: "FUELHH" | "WINDFOR"; documentation_url: string; configured: boolean; last_successful_retrieval: string | null; last_retrieval_status: RetrievalStatus; last_error_summary: string | null; last_record_count: number | null; }
export interface AnalysisFilters { startDate: string; startTime: string; endDate: string; endTime: string; cutoffDate: string; cutoffTime: string; }
export type RequestState = "idle" | "loading" | "refreshing" | "success" | "error";
export interface SavedAnalysis {
  id: string;
  name: string;
  period_start: string;
  period_end: string;
  cutoff: string;
  created_at: string;
  updated_at: string;
}
