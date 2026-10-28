import {
  FormEvent,
  ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  ArrowClockwise,
  CalendarBlank,
  CaretRight,
  CheckCircle,
  Database,
  Info,
  List,
  WarningCircle,
  X,
} from "@phosphor-icons/react";
import {
  Link,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";

import {
  deriveSnapshot,
  filtersFromSearch,
  filtersToSearch,
  getDefaultFilters,
  validateFilters,
} from "./analysis";
import { ApiError, fetchDataSources, fetchForecastAccuracy } from "./api";
import { AuthProvider, useAuth } from "./auth";
import { AuthPage } from "./AuthPage";
import { Brand, Field, InfoHint, MetricCard, navigation } from "./components";
import { ForecastChart } from "./ForecastChart";
import type {
  AnalysisFilters,
  ForecastAccuracyResponse,
  RequestState,
  SourceMetadata,
} from "./types";

const pageMeta: Record<string, { section: string; title: string }> = {
  "/overview": { section: "Workspace", title: "Overview" },
  "/forecast-analysis": { section: "Analytics", title: "Forecast Analysis" },
  "/forecast-accuracy": { section: "Analytics", title: "Forecast Accuracy" },
  "/data-sources": { section: "Operations", title: "Data Sources" },
  "/settings": { section: "Workspace", title: "Settings" },
};

function AppShell({
  children,
  requestState = "idle",
  onRefresh,
}: {
  children: ReactNode;
  requestState?: RequestState;
  onRefresh?: () => void;
}) {
  const location = useLocation();
  const auth = useAuth();
  const navigate = useNavigate();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const meta = pageMeta[location.pathname] ?? pageMeta["/overview"];
  const busy = requestState === "loading" || requestState === "refreshing";
  return (
    <div className="app-shell">
      <aside
        className={`sidebar ${mobileNavOpen ? "sidebar--open" : ""}`}
        aria-label="Primary navigation"
      >
        <div className="sidebar-brand-row">
          <Brand />
          <button
            className="mobile-close"
            onClick={() => setMobileNavOpen(false)}
            aria-label="Close navigation"
          >
            <X />
          </button>
        </div>
        <p className="nav-eyebrow">WORKSPACE</p>
        <nav>
          {navigation.map(({ label, icon: Icon, path }) => (
            <Link
              key={path}
              to={path}
              className={`nav-item ${location.pathname === path ? "nav-item--active" : ""}`}
              aria-current={location.pathname === path ? "page" : undefined}
              onClick={() => setMobileNavOpen(false)}
            >
              <Icon aria-hidden="true" />
              <span>{label}</span>
            </Link>
          ))}
        </nav>
      </aside>
      {mobileNavOpen && (
        <button
          className="nav-backdrop"
          onClick={() => setMobileNavOpen(false)}
          aria-label="Close navigation"
        />
      )}
      <header className="utility-bar">
        <button
          className="menu-button"
          onClick={() => setMobileNavOpen(true)}
          aria-label="Open navigation"
        >
          <List />
        </button>
        <div className="breadcrumbs">
          <span>{meta.section}</span>
          <CaretRight />
          <strong>{meta.title}</strong>
        </div>
        <div className="utility-actions">
          {requestState !== "idle" && (
            <span
              className={`service-status ${requestState === "error" ? "service-status--error" : ""}`}
            >
              <i />
              {requestState === "error" ? "API unavailable" : "WindSight API"}
            </span>
          )}
          {onRefresh && (
            <button
              className="secondary-button"
              disabled={busy}
              onClick={onRefresh}
            >
              <ArrowClockwise
                className={requestState === "refreshing" ? "spin" : ""}
              />
              Refresh data
            </button>
          )}
          {auth.status === "authenticated" ? (
            <div className="account-state">
              <span>{auth.isGuest ? "Guest" : auth.session?.user.email ?? "Account"}</span>
              <button className="text-button" onClick={() => void auth.signOut()}>Log out</button>
            </div>
          ) : (
            <button className="secondary-button" onClick={() => navigate("/auth", { state: { returnTo: `${location.pathname}${location.search}` } })}>Sign in</button>
          )}
        </div>
      </header>
      <main className="workspace">{children}</main>
    </div>
  );
}

function PageHeading({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="page-heading-row">
      <div>
        <p className="page-eyebrow">
          GENERATION INTELLIGENCE&nbsp;&nbsp;/&nbsp;&nbsp;GB WIND
        </p>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="period-chip">
        <CalendarBlank />
        Great Britain&nbsp;&nbsp;·&nbsp;&nbsp;UTC
      </div>
    </div>
  );
}

function ErrorBanner({
  message,
  onRetry,
  title = "Unable to retrieve data",
}: {
  message: string;
  onRetry?: () => void;
  title?: string;
}) {
  return (
    <div className="error-banner" role="alert">
      <WarningCircle aria-hidden="true" />
      <div>
        <strong>{title}</strong>
        <p>{message}</p>
      </div>
      {onRetry && (
        <button type="button" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

function DateTimeFields({
  prefix,
  label,
  dateField,
  timeField,
  filters,
  errors,
  update,
}: {
  prefix: string;
  label: string;
  dateField: keyof AnalysisFilters;
  timeField: keyof AnalysisFilters;
  filters: AnalysisFilters;
  errors: Partial<Record<keyof AnalysisFilters, string>>;
  update: (field: keyof AnalysisFilters, value: string) => void;
}) {
  return (
    <div
      className="datetime-group"
      role="group"
      aria-labelledby={`${prefix}-label`}
    >
      <span id={`${prefix}-label`} className="group-label">
        {label} · UTC
      </span>
      <div className="datetime-pair">
        <Field id={`${prefix}-date`} label="Date" error={errors[dateField]}>
          <input
            id={`${prefix}-date`}
            aria-label={`${label} date`}
            type="date"
            value={filters[dateField]}
            onChange={(e) => update(dateField, e.target.value)}
            aria-invalid={Boolean(errors[dateField])}
          />
        </Field>
        <Field id={`${prefix}-time`} label="Time" error={errors[timeField]}>
          <input
            id={`${prefix}-time`}
            aria-label={`${label} time`}
            type="time"
            value={filters[timeField]}
            onChange={(e) => update(timeField, e.target.value)}
            aria-invalid={Boolean(errors[timeField])}
          />
        </Field>
      </div>
    </div>
  );
}

function FilterForm({
  draft,
  errors,
  busy,
  update,
  submit,
  reset,
  submitLabel = "Apply filters",
}: {
  draft: AnalysisFilters;
  errors: Partial<Record<keyof AnalysisFilters, string>>;
  busy: boolean;
  update: (field: keyof AnalysisFilters, value: string) => void;
  submit: (event: FormEvent) => void;
  reset: () => void;
  submitLabel?: string;
}) {
  return (
    <section className="filter-panel" aria-labelledby="parameters-title">
      <div className="panel-heading">
        <div>
          <h2 id="parameters-title">Analysis parameters</h2>
          <p>
            Delivery boundaries and forecast cutoff are explicit UTC timestamps.
          </p>
        </div>
        <InfoHint>Values persist in the URL</InfoHint>
      </div>
      <form onSubmit={submit} noValidate>
        <div className="filter-grid filter-grid--datetime">
          <DateTimeFields
            prefix="start"
            label="Start"
            dateField="startDate"
            timeField="startTime"
            filters={draft}
            errors={errors}
            update={update}
          />
          <DateTimeFields
            prefix="end"
            label="End"
            dateField="endDate"
            timeField="endTime"
            filters={draft}
            errors={errors}
            update={update}
          />
          <DateTimeFields
            prefix="cutoff"
            label="Decision cutoff"
            dateField="cutoffDate"
            timeField="cutoffTime"
            filters={draft}
            errors={errors}
            update={update}
          />
          <div className="interval-fact">
            <span>Delivery interval</span>{" "}
            <strong>All source intervals</strong>
          </div>
          <div className="form-actions">
            <button className="primary-button" type="submit" disabled={busy}>
              {busy ? "Applying…" : submitLabel}
            </button>
            <button
              className="ghost-button"
              type="button"
              disabled={busy}
              onClick={reset}
            >
              Reset
            </button>
          </div>
        </div>
        <p className="filter-help">
          Start is inclusive and End is exclusive. The period may not exceed
          seven elapsed days. The cutoff is an independent inclusive
          publication-time boundary.
        </p>
      </form>
    </section>
  );
}

function useAnalytics() {
  const location = useLocation();
  const navigate = useNavigate();
  const defaults = getDefaultFilters();
  const initial = filtersFromSearch(location.search, defaults);
  const [draft, setDraft] = useState(initial),
    [committed, setCommitted] = useState(initial);
  const [errors, setErrors] = useState<
    Partial<Record<keyof AnalysisFilters, string>>
  >({});
  const [requestState, setRequestState] = useState<RequestState>("idle");
  const [data, setData] = useState<ForecastAccuracyResponse | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);
  const requestRef = useRef<AbortController | null>(null);
  const run = useCallback(
    async (filters: AnalysisFilters, background = false) => {
      requestRef.current?.abort();
      const controller = new AbortController();
      requestRef.current = controller;
      setRequestState(background ? "refreshing" : "loading");
      setRequestError(null);
      try {
        setData(await fetchForecastAccuracy(filters, controller.signal));
        setRequestState("success");
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError")
          return;
        setRequestError(
          error instanceof ApiError
            ? error.message
            : "The analytics request failed.",
        );
        setRequestState("error");
      }
    },
    [],
  );
  useEffect(() => {
    void run(initial);
    return () => requestRef.current?.abort();
  }, [run]);
  function update(field: keyof AnalysisFilters, value: string) {
    setDraft((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    const next = validateFilters(draft);
    setErrors(next);
    if (Object.keys(next).length) {
      requestAnimationFrame(() =>
        document.querySelector<HTMLElement>("[aria-invalid='true']")?.focus(),
      );
      return;
    }
    setCommitted(draft);
    navigate(
      { pathname: location.pathname, search: `?${filtersToSearch(draft)}` },
      { replace: true },
    );
    void run(draft, Boolean(data));
  }
  function reset() {
    setDraft(defaults);
    setCommitted(defaults);
    setErrors({});
    navigate(
      { pathname: location.pathname, search: `?${filtersToSearch(defaults)}` },
      { replace: true },
    );
    void run(defaults, Boolean(data));
  }
  return {
    draft,
    committed,
    errors,
    requestState,
    data,
    requestError,
    update,
    submit,
    reset,
    run,
  };
}

function ForecastAnalysis({ accuracy = false }: { accuracy?: boolean }) {
  const model = useAnalytics();
  const snapshot = deriveSnapshot(model.data);
  const busy =
    model.requestState === "loading" || model.requestState === "refreshing";
  const matched = model.data?.metrics.matched_intervals_count ?? 0;
  return (
    <AppShell
      requestState={model.requestState}
      onRefresh={() => void model.run(model.committed, Boolean(model.data))}
    >
      <PageHeading
        title={accuracy ? "Forecast Accuracy" : "Wind Forecast Analytics"}
        description={
          accuracy
            ? "Measure error, bias, coverage and forecast-history quality."
            : "Evaluate forecast performance against actual wind generation."
        }
      />
      <FilterForm
        draft={model.draft}
        errors={model.errors}
        busy={busy}
        update={model.update}
        submit={model.submit}
        reset={model.reset}
      />
      {model.requestError && (
        <ErrorBanner
          title="Unable to retrieve analysis"
          message={model.requestError}
          onRetry={() => void model.run(model.committed, Boolean(model.data))}
        />
      )}
      <section
        className="snapshot-section"
        aria-labelledby="snapshot-title"
        aria-busy={busy}
      >
        <div className="section-title-row">
          <div>
            <h2 id="snapshot-title">
              {accuracy ? "Accuracy metrics" : "Performance snapshot"}
            </h2>
            <p>Matched delivery intervals · UTC</p>
          </div>
          <span className="data-status">
            {busy ? (
              "Updating analysis…"
            ) : model.data ? (
              <>
                <CheckCircle />
                {matched} matched intervals
              </>
            ) : (
              "Waiting for API data"
            )}
          </span>
        </div>
        <div className="metrics-grid">
          {accuracy ? (
            <>
              <MetricCard
                label="Root mean square error"
                value={snapshot.rmse}
                detail="Penalises larger errors"
                tone="blue"
                icon="chart"
              />
              <MetricCard
                label="Mean absolute error"
                value={snapshot.mae}
                detail="Lower is better"
                tone="slate"
                icon="target"
              />
              <MetricCard
                label="Signed bias"
                value={snapshot.bias}
                detail={
                  snapshot.bias === null
                    ? "No matched errors"
                    : snapshot.bias > 0
                      ? "Overforecasting"
                      : snapshot.bias < 0
                        ? "Underforecasting"
                        : "No average bias"
                }
                tone="teal"
                icon="trend"
              />
              <MetricCard
                label="Matched intervals"
                value={matched}
                detail="Metric denominator"
                tone="slate"
                icon="target"
                unit="count"
              />
            </>
          ) : (
            <>
              <MetricCard
                label="Actual wind generation"
                value={snapshot.actualAverage}
                detail="Average · matched intervals"
                tone="teal"
                icon="wind"
              />
              <MetricCard
                label="Forecast wind generation"
                value={snapshot.forecastAverage}
                detail="Comparable average"
                tone="blue"
                icon="trend"
              />
              <MetricCard
                label="Mean absolute error"
                value={snapshot.mae}
                detail="Lower is better"
                tone="slate"
                icon="target"
              />
              <MetricCard
                label="Forecast bias"
                value={snapshot.bias}
                detail={
                  snapshot.bias === null
                    ? "No matched errors"
                    : snapshot.bias > 0
                      ? "Overforecasting"
                      : snapshot.bias < 0
                        ? "Underforecasting"
                        : "No average bias"
                }
                tone="slate"
                icon="chart"
              />
            </>
          )}
        </div>
      </section>
      <ForecastChart comparisons={model.data?.comparisons ?? []} />
      {accuracy && model.data && (
        <>
          <QualityPanel data={model.data} />
          <HistoryNotice data={model.data} />
        </>
      )}
    </AppShell>
  );
}

function QualityPanel({ data }: { data: ForecastAccuracyResponse }) {
  const entries = [
    ["Actual intervals", data.quality.actual_intervals_count],
    ["Forecast intervals", data.quality.forecast_intervals_count],
    ["Missing forecasts", data.quality.missing_forecast_count],
    ["No eligible forecast", data.quality.no_eligible_forecast_count],
    ["Missing actuals", data.quality.missing_actual_count],
    ["Duplicates", data.quality.duplicate_record_count],
    ["Unmatched forecasts", data.quality.unmatched_forecast_count],
    ["Invalid records", data.quality.invalid_record_count],
  ];
  return (
    <section className="detail-panel">
      <div className="panel-heading">
        <div>
          <h2>Data quality</h2>
          <p>Backend counters for the selected delivery window.</p>
        </div>
      </div>
      <dl className="quality-grid">
        {entries.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
function HistoryNotice({ data }: { data: ForecastAccuracyResponse }) {
  return (
    <div className="notice-panel">
      <Info />
      <div>
        <strong>
          Bounded forecast history ·{" "}
          {data.forecast_history.history_horizon_days} days
        </strong>
        <p>{data.forecast_history.limitation}</p>
      </div>
    </div>
  );
}

function Overview() {
  const filters = filtersFromSearch(useLocation().search);
  const [state, setState] = useState<RequestState>("loading");
  const [analytics, setAnalytics] = useState<ForecastAccuracyResponse | null>(
    null,
  );
  const [sources, setSources] = useState<SourceMetadata[]>([]);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async (background = false) => {
    setState(background ? "refreshing" : "loading");
    setError(null);
    try {
      const [a, s] = await Promise.all([
        fetchForecastAccuracy(filters),
        fetchDataSources(),
      ]);
      setAnalytics(a);
      setSources(s);
      setState("success");
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "The dashboard request failed.",
      );
      setState("error");
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  const snap = deriveSnapshot(analytics);
  const healthy = sources.filter(
    (source) => source.last_retrieval_status === "healthy",
  ).length;
  return (
    <AppShell
      requestState={state}
      onRefresh={() => void load(Boolean(analytics))}
    >
      <PageHeading
        title="Wind generation overview"
        description="A live operational view of forecast performance and source availability."
      />
      {error && (
        <ErrorBanner
          message={error}
          onRetry={() => void load(Boolean(analytics))}
        />
      )}
      <section className="snapshot-section">
        <div className="section-title-row">
          <div>
            <h2>Current analytical window</h2>
            <p>Latest configured seven-day UTC view</p>
          </div>
        </div>
        <div className="metrics-grid">
          <MetricCard
            label="Actual generation"
            value={snap.actualAverage}
            detail="Matched average"
            tone="teal"
            icon="wind"
          />
          <MetricCard
            label="Forecast generation"
            value={snap.forecastAverage}
            detail="Matched average"
            tone="blue"
            icon="trend"
          />
          <MetricCard
            label="RMSE"
            value={snap.rmse}
            detail="Forecast error"
            tone="slate"
            icon="target"
          />
          <MetricCard
            label="Healthy sources"
            value={sources.length ? healthy : null}
            detail={`of ${sources.length || 2} registered`}
            tone="slate"
            icon="chart"
            unit="count"
          />
        </div>
      </section>
      <div className="overview-grid">
        <section className="detail-panel">
          <div className="panel-heading">
            <div>
              <h2>Availability</h2>
              <p>Observed backend coverage, not estimated data.</p>
            </div>
          </div>
          {analytics ? (
            <dl className="quality-grid quality-grid--compact">
              <div>
                <dt>Matched</dt>
                <dd>{analytics.quality.matched_intervals_count}</dd>
              </div>
              <div>
                <dt>Actual intervals</dt>
                <dd>{analytics.quality.actual_intervals_count}</dd>
              </div>
              <div>
                <dt>Forecast intervals</dt>
                <dd>{analytics.quality.forecast_intervals_count}</dd>
              </div>
            </dl>
          ) : (
            <p className="empty-copy">No analytics are available.</p>
          )}
        </section>
        <section className="detail-panel">
          <div className="panel-heading">
            <div>
              <h2>Source retrieval</h2>
              <p>Status resets when the backend process restarts.</p>
            </div>
          </div>
          <div className="source-mini-list">
            {sources.map((source) => (
              <div key={source.dataset}>
                <strong>{source.dataset}</strong>
                <StatusBadge status={source.last_retrieval_status} />
              </div>
            ))}
          </div>
        </section>
      </div>
      {analytics && <HistoryNotice data={analytics} />}
    </AppShell>
  );
}

function StatusBadge({
  status,
}: {
  status: SourceMetadata["last_retrieval_status"];
}) {
  return (
    <span className={`status-badge status-badge--${status}`}>
      {status.replace("_", " ")}
    </span>
  );
}
function DataSources() {
  const [sources, setSources] = useState<SourceMetadata[]>([]),
    [state, setState] = useState<RequestState>("loading"),
    [error, setError] = useState<string | null>(null);
  const load = useCallback(async (background = false) => {
    setState(background ? "refreshing" : "loading");
    setError(null);
    try {
      setSources(await fetchDataSources());
      setState("success");
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "The source request failed.",
      );
      setState("error");
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  return (
    <AppShell
      requestState={state}
      onRefresh={() => void load(Boolean(sources.length))}
    >
      <PageHeading
        title="Data Sources"
        description="Retrieval health and metadata reported by the running backend process."
      />
      {error && (
        <ErrorBanner
          message={error}
          onRetry={() => void load(Boolean(sources.length))}
        />
      )}
      <section className="source-grid" aria-busy={state === "loading"}>
        {sources.map((source) => (
          <article className="source-card" key={source.dataset}>
            <div className="source-card__head">
              <span>
                <Database />
              </span>
              <div>
                <h2>{source.dataset}</h2>
                <p>
                  {source.dataset === "FUELHH"
                    ? "Half-hourly generation outturn"
                    : "Wind generation forecast"}
                </p>
              </div>
              <StatusBadge status={source.last_retrieval_status} />
            </div>
            <dl>
              <div>
                <dt>Configured</dt>
                <dd>{source.configured ? "Yes" : "No"}</dd>
              </div>
              <div>
                <dt>Last record count</dt>
                <dd>{source.last_record_count ?? "Not checked"}</dd>
              </div>
              <div>
                <dt>Last successful retrieval</dt>
                <dd>
                  {source.last_successful_retrieval
                    ? new Date(source.last_successful_retrieval).toLocaleString(
                        "en-GB",
                        { timeZone: "UTC" },
                      ) + " UTC"
                    : "Not yet retrieved"}
                </dd>
              </div>
            </dl>
            {source.last_error_summary && (
              <p className="source-error">{source.last_error_summary}</p>
            )}
            <a href={source.documentation_url} target="_blank" rel="noreferrer">
              View Elexon documentation
            </a>
          </article>
        ))}
      </section>
      {state !== "loading" && !error && !sources.length && (
        <div className="empty-panel">
          <strong>No source metadata returned</strong>
          <p>The backend registered no data sources.</p>
        </div>
      )}
    </AppShell>
  );
}

function Settings() {
  const location = useLocation(),
    navigate = useNavigate(),
    defaults = getDefaultFilters();
  const [draft, setDraft] = useState(
    filtersFromSearch(location.search, defaults),
  );
  const [errors, setErrors] = useState<
    Partial<Record<keyof AnalysisFilters, string>>
  >({});
  function update(field: keyof AnalysisFilters, value: string) {
    setDraft((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    const next = validateFilters(draft);
    setErrors(next);
    if (Object.keys(next).length) return;
    navigate(`/forecast-analysis?${filtersToSearch(draft)}`);
  }
  return (
    <AppShell>
      <PageHeading
        title="Analysis Settings"
        description="Prepare UTC analysis parameters and open them in Forecast Analysis."
      />
      <FilterForm
        draft={draft}
        errors={errors}
        busy={false}
        update={update}
        submit={submit}
        reset={() => {
          setDraft(defaults);
          setErrors({});
        }}
        submitLabel="Open analysis"
      />
    </AppShell>
  );
}

export function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/auth" element={<AuthPage />} />
        <Route path="/overview" element={<Overview />} />
        <Route path="/forecast-analysis" element={<ForecastAnalysis />} />
        <Route path="/forecast-accuracy" element={<ForecastAnalysis accuracy />} />
        <Route path="/data-sources" element={<DataSources />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/overview" replace />} />
      </Routes>
    </AuthProvider>
  );
}
