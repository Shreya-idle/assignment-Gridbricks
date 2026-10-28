import { describe, expect, it } from "vitest";
import { deriveSnapshot, filtersFromSearch, filtersToSearch, toUtcIso, validateFilters } from "./analysis";
import type { ForecastAccuracyResponse } from "./types";

const valid = { startDate: "2026-01-01", startTime: "00:00", endDate: "2026-01-08", endTime: "00:00", cutoffDate: "2025-12-31", cutoffTime: "12:30" };

describe("analysis filters", () => {
  it("accepts exactly seven elapsed days and rejects longer or reversed ranges", () => {
    expect(validateFilters(valid)).toEqual({});
    expect(validateFilters({ ...valid, endTime: "00:01" }).endDate).toMatch(/seven days/i);
    expect(validateFilters({ ...valid, endDate: "2025-12-31" }).endDate).toMatch(/later/i);
  });
  it("requires all date and time values", () => {
    expect(validateFilters({ ...valid, cutoffDate: "" }).cutoffDate).toMatch(/cutoff date/i);
    expect(validateFilters({ ...valid, startTime: "25:00" }).startTime).toMatch(/start time/i);
  });
  it("serializes explicit UTC timestamps and restores canonical URL state", () => {
    expect(toUtcIso("2026-01-01", "10:30")).toBe("2026-01-01T10:30:00Z");
    expect(filtersFromSearch(`?${filtersToSearch(valid)}`)).toEqual(valid);
  });
  it("supports legacy date-only boundaries and time-only cutoff", () => {
    expect(filtersFromSearch("?from=2026-01-01&to=2026-01-08&cutoff=09%3A45", valid)).toEqual({ ...valid, startDate: "2026-01-01", startTime: "00:00", endDate: "2026-01-08", endTime: "00:00", cutoffDate: "2026-01-01", cutoffTime: "09:45" });
  });
});

describe("snapshot derivation", () => {
  it("preserves zero and calculates averages", () => {
    const response = { metrics: { mae: 2, rmse: 2.5, bias: 0, matched_intervals_count: 2 }, comparisons: [{ actual_generation: 0, forecast_generation: 2 }, { actual_generation: 10, forecast_generation: 8 }] } as ForecastAccuracyResponse;
    expect(deriveSnapshot(response)).toEqual({ actualAverage: 5, forecastAverage: 5, mae: 2, rmse: 2.5, bias: 0 });
  });
});
