import { afterEach, describe, expect, it, vi } from "vitest";

import { createSavedAnalysis, deleteSavedAnalysis, listSavedAnalyses, renameSavedAnalysis } from "./api";
import type { AnalysisFilters } from "./types";

const saved = {
  id: "1b8af7ee-3296-4074-b843-7aeed0047563",
  name: "Morning run",
  period_start: "2026-01-01T00:00:00Z",
  period_end: "2026-01-02T00:00:00Z",
  cutoff: "2025-12-31T12:00:00Z",
  created_at: "2026-01-01T10:00:00Z",
  updated_at: "2026-01-01T10:00:00Z",
};
const filters: AnalysisFilters = { startDate: "2026-01-01", startTime: "00:00", endDate: "2026-01-02", endTime: "00:00", cutoffDate: "2025-12-31", cutoffTime: "12:00" };

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("saved analysis API", () => {
  it("attaches bearer tokens only to protected requests and sends canonical UTC values", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, status: 201, json: async () => saved })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ ...saved, name: "Renamed" }) })
      .mockResolvedValueOnce({ ok: true, status: 204 });
    vi.stubGlobal("fetch", fetchMock);
    await listSavedAnalyses("access-token");
    await createSavedAnalysis("access-token", "Morning run", filters);
    await renameSavedAnalysis("access-token", saved.id, "Renamed");
    await deleteSavedAnalysis("access-token", saved.id);
    expect(fetchMock).toHaveBeenCalledTimes(4);
    for (const call of fetchMock.mock.calls) expect(call[1].headers.Authorization).toBe("Bearer access-token");
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
      name: "Morning run",
      period_start: "2026-01-01T00:00:00Z",
      period_end: "2026-01-02T00:00:00Z",
      cutoff: "2025-12-31T12:00:00Z",
    });
  });

  it("does not claim success when the protected API fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 409, json: async () => ({ detail: "Duplicate name" }) }));
    await expect(createSavedAnalysis("token", "Morning run", filters)).rejects.toThrow("Duplicate name");
  });
});
