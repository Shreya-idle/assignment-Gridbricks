import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SaveAnalysisControl, SavedAnalysesPanel } from "./SavedAnalyses";
import type { AnalysisFilters, SavedAnalysis } from "./types";

const mocks = vi.hoisted(() => ({
  auth: { status: "authenticated", isGuest: false, accessToken: "token" } as Record<string, unknown>,
  create: vi.fn(), list: vi.fn(), rename: vi.fn(), remove: vi.fn(),
}));
vi.mock("./auth", () => ({ useAuth: () => mocks.auth }));
vi.mock("./api", () => ({
  createSavedAnalysis: mocks.create,
  listSavedAnalyses: mocks.list,
  renameSavedAnalysis: mocks.rename,
  deleteSavedAnalysis: mocks.remove,
}));

const filters: AnalysisFilters = { startDate: "2026-01-01", startTime: "00:00", endDate: "2026-01-02", endTime: "00:00", cutoffDate: "2025-12-31", cutoffTime: "12:00" };
const item: SavedAnalysis = { id: "4ad2d43d-e096-4bab-bdca-b860ea2b4ce8", name: "Morning", period_start: "2026-01-01T00:00:00Z", period_end: "2026-01-02T00:00:00Z", cutoff: "2025-12-31T12:00:00Z", created_at: "2026-01-02T00:00:00Z", updated_at: "2026-01-02T00:00:00Z" };

beforeEach(() => {
  mocks.auth = { status: "authenticated", isGuest: false, accessToken: "token" };
  mocks.create.mockResolvedValue(item); mocks.list.mockResolvedValue([item]);
  mocks.rename.mockResolvedValue({ ...item, name: "Renamed" }); mocks.remove.mockResolvedValue(undefined);
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("saved analysis UI", () => {
  it("shows the save control for guests without authentication messaging", () => {
    mocks.auth = { status: "authenticated", isGuest: true, accessToken: "guest-token" };
    render(<MemoryRouter><SaveAnalysisControl filters={filters} /></MemoryRouter>);
    expect(screen.getByRole("button", { name: "Save analysis" })).toBeInTheDocument();
    expect(screen.queryByText(/sign in|account required/i)).not.toBeInTheDocument();
    expect(mocks.create).not.toHaveBeenCalled();
  });

  it("reports save success only after the API succeeds", async () => {
    render(<MemoryRouter><SaveAnalysisControl filters={filters} /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText("Analysis name"), "Morning");
    await userEvent.click(screen.getByRole("button", { name: "Save analysis" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Analysis saved");
    expect(mocks.create).toHaveBeenCalledWith("token", "Morning", filters);
  });

  it("shows API failures without a false success message", async () => {
    mocks.create.mockRejectedValue(new Error("Saved analyses are temporarily unavailable"));
    render(<MemoryRouter><SaveAnalysisControl filters={filters} /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText("Analysis name"), "Morning");
    await userEvent.click(screen.getByRole("button", { name: "Save analysis" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/temporarily unavailable/i);
    expect(screen.queryByText("Analysis saved.")).not.toBeInTheDocument();
  });

  it("loads, opens, renames, and deletes owned configurations", async () => {
    function Location() { return <output data-testid="location">{useLocation().pathname}{useLocation().search}</output>; }
    const first = render(<MemoryRouter initialEntries={["/settings"]}><SavedAnalysesPanel /><Location /></MemoryRouter>);
    expect(await screen.findByText("Morning")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Open" }));
    expect(screen.getByTestId("location")).toHaveTextContent("/forecast-analysis?from=2026-01-01T00%3A00%3A00Z");
    first.unmount();
    render(<MemoryRouter><SavedAnalysesPanel /></MemoryRouter>);
    await screen.findByText("Morning");
    await userEvent.click(screen.getByRole("button", { name: "Rename" }));
    const input = screen.getByLabelText("Analysis name");
    await userEvent.clear(input); await userEvent.type(input, "Renamed");
    await userEvent.click(screen.getByRole("button", { name: "Save name" }));
    expect(await screen.findByText("Renamed")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(screen.queryByText("Renamed")).not.toBeInTheDocument());
  });

  it("renders empty and failed list states", async () => {
    mocks.list.mockResolvedValueOnce([]);
    const view = render(<MemoryRouter><SavedAnalysesPanel /></MemoryRouter>);
    expect(await screen.findByText("No saved analyses yet.")).toBeInTheDocument();
    view.unmount(); mocks.list.mockRejectedValueOnce(new Error("Database unavailable"));
    render(<MemoryRouter><SavedAnalysesPanel /></MemoryRouter>);
    expect(await screen.findByRole("alert")).toHaveTextContent("Database unavailable");
  });
});
