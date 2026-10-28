import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

vi.mock("./ForecastChart", () => ({ ForecastChart: () => <div data-testid="forecast-chart" /> }));

const response = {
  period: { start: "2026-01-01T00:00:00Z", end: "2026-01-08T00:00:00Z" },
  cutoff: { effective_time: "2025-12-31T12:00:00Z", interpretation: "UTC" },
  forecast_history: { publication_from: "2025-12-24T12:00:01Z", publication_to: "2025-12-31T12:00:00Z", history_horizon_days: 7, completeness: "bounded" },
  metrics: { mae: 5, rmse: 6, bias: 1, matched_intervals_count: 1 },
  quality: { actual_intervals_count: 1, forecast_intervals_count: 1, matched_intervals_count: 1, missing_forecast_count: 0, no_eligible_forecast_count: 0, missing_actual_count: 0, invalid_record_count: 0, duplicate_record_count: 0, unmatched_forecast_count: 0 },
  comparisons: [{ start_time: "2026-01-01T00:00:00Z", actual_generation: 100, forecast_generation: 105, forecast_publish_time: "2025-12-31T10:00:00Z", error: 5, absolute_error: 5, squared_error: 25 }], assumptions: [],
};
const sources = [{ dataset: "FUELHH", documentation_url: "https://example.com/fuel", configured: true, last_successful_retrieval: "2026-01-08T00:00:00Z", last_retrieval_status: "healthy", last_error_summary: null, last_record_count: 336 }, { dataset: "WINDFOR", documentation_url: "https://example.com/forecast", configured: true, last_successful_retrieval: null, last_retrieval_status: "not_checked", last_error_summary: null, last_record_count: null }];
const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body });

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("Forecast Analysis", () => {
  it("loads analytics, exposes six UTC controls, and sends canonical query parameters", async () => {
    const fetchMock = vi.fn().mockResolvedValue(ok(response)); vi.stubGlobal("fetch", fetchMock);
    render(<MemoryRouter initialEntries={["/forecast-analysis?from=2026-01-01&to=2026-01-08&cutoff=12%3A00"]}><App /></MemoryRouter>);
    expect(await screen.findByText("100.00")).toBeInTheDocument();
    expect(screen.getByLabelText("Start date")).toHaveValue("2026-01-01"); expect(screen.getByLabelText("Start time")).toHaveValue("00:00");
    expect(screen.getByLabelText("End date")).toHaveValue("2026-01-08"); expect(screen.getByLabelText("End time")).toHaveValue("00:00");
    expect(screen.getByLabelText("Decision cutoff date")).toHaveValue("2026-01-01"); expect(screen.getByLabelText("Decision cutoff time")).toHaveValue("12:00");
    const url = new URL(fetchMock.mock.calls[0][0], "http://windsight.test");
    expect(url.searchParams.get("from")).toBe("2026-01-01T00:00:00Z"); expect(url.searchParams.get("to")).toBe("2026-01-08T00:00:00Z"); expect(url.searchParams.get("cutoff")).toBe("2026-01-01T12:00:00Z");
    expect(url.searchParams.has("interval")).toBe(false); expect(screen.queryByRole("combobox")).not.toBeInTheDocument(); expect(screen.getByText("All source intervals")).toBeInTheDocument();
  });
  it("updates independent times and cutoff date before applying", async () => {
    const fetchMock = vi.fn().mockResolvedValue(ok(response)); vi.stubGlobal("fetch", fetchMock); const user = userEvent.setup();
    render(<MemoryRouter initialEntries={["/forecast-analysis?from=2026-01-01&to=2026-01-08&cutoff=12%3A00"]}><App /></MemoryRouter>); await screen.findByText("100.00");
    fireEvent.change(screen.getByLabelText("Start time"), { target: { value: "01:15" } }); fireEvent.change(screen.getByLabelText("End time"), { target: { value: "01:00" } }); fireEvent.change(screen.getByLabelText("Decision cutoff date"), { target: { value: "2025-12-30" } });
    await user.click(screen.getByRole("button", { name: "Apply filters" })); await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const url = new URL(fetchMock.mock.calls[1][0], "http://windsight.test"); expect(url.searchParams.get("from")).toBe("2026-01-01T01:15:00Z"); expect(url.searchParams.get("to")).toBe("2026-01-08T01:00:00Z"); expect(url.searchParams.get("cutoff")).toBe("2025-12-30T12:00:00Z");
  });
  it("validates over-seven-day ranges without a request", async () => {
    const fetchMock = vi.fn().mockResolvedValue(ok(response)); vi.stubGlobal("fetch", fetchMock); const user = userEvent.setup();
    render(<MemoryRouter initialEntries={["/forecast-analysis?from=2026-01-01&to=2026-01-08&cutoff=12%3A00"]}><App /></MemoryRouter>); await screen.findByText("100.00");
    fireEvent.change(screen.getByLabelText("End time"), { target: { value: "00:01" } }); await user.click(screen.getByRole("button", { name: "Apply filters" }));
    expect(await screen.findByText(/cannot exceed seven days/i)).toBeInTheDocument(); expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it("shows a clear network failure and retries", async () => {
    const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError("offline")).mockResolvedValueOnce(ok(response)); vi.stubGlobal("fetch", fetchMock); const user = userEvent.setup();
    render(<MemoryRouter initialEntries={["/forecast-analysis"]}><App /></MemoryRouter>); expect(await screen.findByRole("alert")).toHaveTextContent(/cannot connect/i); await user.click(screen.getByRole("button", { name: "Retry" })); expect(await screen.findByText("100.00")).toBeInTheDocument();
  });
});

describe("routes and pages", () => {
  it("renders the authentication screen without blocking public routes", async () => { render(<MemoryRouter initialEntries={["/auth"]}><App /></MemoryRouter>); expect(await screen.findByRole("heading", { name: /sign in to windsight/i })).toBeInTheDocument(); expect(screen.getByRole("link", { name: /return to public analytics/i })).toBeInTheDocument(); });
  it.each([["/forecast-accuracy", /forecast accuracy/i], ["/settings", /analysis settings/i]])("renders %s", async (path, heading) => { vi.stubGlobal("fetch", vi.fn().mockResolvedValue(ok(response))); render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>); expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument(); });
  it.each(["/forecast-analysis", "/forecast-accuracy", "/settings"])("does not expose saved analysis controls on %s", async (path) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(ok(response)));
    render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
    expect((await screen.findAllByRole("heading")).length).toBeGreaterThan(0);
    expect(screen.queryByText("Save this analysis")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Analysis name")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save analysis" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Saved analyses" })).not.toBeInTheDocument();
  });
  it("renders data source metadata", async () => { vi.stubGlobal("fetch", vi.fn().mockResolvedValue(ok(sources))); render(<MemoryRouter initialEntries={["/data-sources"]}><App /></MemoryRouter>); expect(await screen.findByText("FUELHH")).toBeInTheDocument(); expect(screen.getByText("WINDFOR")).toBeInTheDocument(); });
  it("renders an explicit empty source state", async () => { vi.stubGlobal("fetch", vi.fn().mockResolvedValue(ok([]))); render(<MemoryRouter initialEntries={["/data-sources"]}><App /></MemoryRouter>); expect(await screen.findByText("No source metadata returned")).toBeInTheDocument(); });
  it("rejects malformed analytics instead of displaying it", async () => { vi.stubGlobal("fetch", vi.fn().mockResolvedValue(ok({ metrics: {} }))); render(<MemoryRouter initialEntries={["/forecast-analysis"]}><App /></MemoryRouter>); expect(await screen.findByRole("alert")).toHaveTextContent(/does not match/i); });
  it("marks the current navigation route", () => { render(<MemoryRouter initialEntries={["/settings"]}><App /></MemoryRouter>); expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("aria-current", "page"); });
  it("renders overview from analytics and source data", async () => { vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => Promise.resolve(ok(url.includes("data-sources") ? sources : response)))); render(<MemoryRouter initialEntries={["/overview"]}><App /></MemoryRouter>); expect(await screen.findByRole("heading", { name: /wind generation overview/i })).toBeInTheDocument(); expect(await screen.findByText("FUELHH")).toBeInTheDocument(); });
  it("redirects unknown routes to overview", async () => { vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => Promise.resolve(ok(url.includes("data-sources") ? sources : response)))); render(<MemoryRouter initialEntries={["/missing"]}><App /></MemoryRouter>); expect(await screen.findByRole("heading", { name: /wind generation overview/i })).toBeInTheDocument(); });
});
