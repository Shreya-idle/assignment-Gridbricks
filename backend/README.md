# WindSight backend — Phase 2 core analytics

FastAPI foundation for validated access to Elexon's public FUELHH wind actuals and WINDFOR
forecast publications. No API key is required by the current Elexon Insights API.

## Setup (PowerShell)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Open `http://127.0.0.1:8001/docs`. Useful requests:

```text
GET /api/v1/health
GET /api/v1/data-sources
GET /api/v1/generation/actuals?from=2025-01-01T00:00:00Z&to=2025-01-02T00:00:00Z
GET /api/v1/generation/forecasts?from=2025-01-01T00:00:00Z&to=2025-01-02T00:00:00Z
GET /api/v1/analytics/forecast-accuracy?from=2025-01-01T00:00:00Z&to=2025-01-02T00:00:00Z&cutoff=2025-01-01T00:00:00Z
```

Application boundaries are inclusive at `from` and exclusive at `to`; both must carry a timezone
offset. Internally all timestamps are normalized to UTC. The configured maximum range defaults to
seven days. Since raw stream endpoints filter by publication time, forecast bounds apply to
`publishTime`; returned `startTime` remains the distinct delivery timestamp. All publications are
preserved. FUELHH results are filtered to exact source fuel type `WIND`.

## Forecast accuracy analytics

`from` is inclusive and `to` is exclusive for delivery timestamps. `cutoff` is an inclusive
publication-time boundary: only forecasts with `publishTime <= cutoff` are eligible. All three
parameters must include `Z` or an explicit UTC offset; equivalent timezone representations are
normalized to UTC. The cutoff is a configurable analytical assumption, **not an official Elexon
market or purchasing deadline**.

Analytics reads the raw WINDFOR stream through a bounded publication-time window ending at the
inclusive cutoff. `ANALYTICS_FORECAST_HISTORY_DAYS` controls the lookback and defaults to seven
days; it cannot exceed `ELEXON_MAX_RANGE_DAYS`. Every response reports the effective
`forecast_history.publication_from`, `publication_to`, and `completeness: "bounded"`. Publications
older than that boundary are not queried, so a missing forecast does not prove that Elexon never
published one. The dedicated `wind/latest/stream` endpoint is not used because its documented
contract provides a latest forecast view but no as-of-cutoff publication parameter.

For each delivery `startTime`, analytics chooses the latest eligible publication. If records have
the same delivery and publication timestamps, the highest numeric generation is the documented,
stable tie-break. Duplicate actuals use the lowest numeric generation as their stable tie-break.
These deterministic rules do not imply that either duplicate is authoritative; extras are reported.
Matching uses only normalized delivery timestamps and performs no interpolation or filling.

Signed error is `forecast - actual`. Positive bias means overforecasting; negative bias means
underforecasting. Metrics retain full precision: MAE is `mean(abs(error))`, RMSE is
`sqrt(mean(error ** 2))`, and bias is `mean(error)`.

Zero is valid generation. Missing, NaN, infinite, or otherwise invalid source records fail as
`invalid_source_record` rather than creating a partial dataset. Thus `invalid_record_count` is zero
in a successful response. With no valid pairs all metrics are `null`, not zero. Upstream failures
retain their error response and never become empty analytics.

Quality counters use unique normalized delivery intervals unless noted:

- `actual_intervals_count`: intervals having at least one valid actual.
- `forecast_intervals_count`: intervals having at least one valid forecast publication.
- `matched_intervals_count`: canonical pairs used as every metric's denominator.
- `missing_forecast_count`: actual intervals having no forecast publication.
- `no_eligible_forecast_count`: actual intervals whose forecasts are all after cutoff.
- `missing_actual_count`: selected eligible forecast intervals having no actual.
- `invalid_record_count`: excluded malformed records; zero because malformed batches are rejected.
- `duplicate_record_count`: extra actuals plus extra forecasts sharing delivery/publication time.
- `unmatched_forecast_count`: forecast intervals, whether eligible or late, having no actual.

`missing_actual_count` is intentionally a selected-forecast subset of `unmatched_forecast_count`;
the actual-side missing categories are disjoint.

Example from deterministic illustrative data (not live market data):

```json
{
  "period": {"start": "2025-01-01T00:00:00Z", "end": "2025-01-01T00:30:00Z"},
  "cutoff": {"effective_time": "2024-12-31T12:00:00Z", "interpretation": "Inclusive publication-time cutoff, normalized to UTC"},
  "forecast_history": {
    "publication_from": "2024-12-24T12:00:01Z",
    "publication_to": "2024-12-31T12:00:00Z",
    "history_horizon_days": 7,
    "completeness": "bounded",
    "limitation": "Forecast publications older than publication_from were not queried; missing forecasts therefore do not prove that Elexon never published one."
  },
  "metrics": {"mae": 10.0, "rmse": 10.0, "bias": 10.0, "matched_intervals_count": 1},
  "quality": {
    "actual_intervals_count": 1, "forecast_intervals_count": 1,
    "matched_intervals_count": 1, "missing_forecast_count": 0,
    "no_eligible_forecast_count": 0, "missing_actual_count": 0,
    "invalid_record_count": 0, "duplicate_record_count": 0,
    "unmatched_forecast_count": 0
  },
  "comparisons": [{
    "start_time": "2025-01-01T00:00:00Z", "actual_generation": 100.0,
    "forecast_generation": 110.0, "forecast_publish_time": "2024-12-31T10:00:00Z",
    "error": 10.0, "absolute_error": 10.0, "squared_error": 100.0
  }],
  "assumptions": ["The cutoff is an analytical assumption, not an official Elexon market deadline."]
}
```

## Verification

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

The tests mock upstream HTTP and therefore need neither network access nor credentials.

## Configuration

See `.env.example`. `ELEXON_BASE_URL`, timeouts, retries, maximum range, analytics forecast-history
horizon, CORS origins, environment, timezone, and logging are environment-driven. Elexon's official production default is
`https://data.elexon.co.uk/bmrs/api/v1`. `ELEXON_API_KEY` is deliberately absent because the
official developer portal states that the APIs are public and require no key.

## PostgreSQL persistence

WindSight writes successful live FUELHH and WINDFOR retrievals to PostgreSQL when
`DATABASE_URL` is configured in the project-root `.env`. SQLAlchemy uses Psycopg 3 and Alembic
owns the schema. Persistence is best-effort: a database outage is reported by
`GET /api/v1/health/database`, but does not replace a valid live Elexon response with an error.
Analytics continues to use the current live retrieval in this phase.

Use a standard PostgreSQL URL and percent-encode reserved characters in credentials:

```text
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE
```

Install, migrate, and run from `backend/`:

```powershell
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m alembic current
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Verify `GET /api/v1/health` for application health and `GET /api/v1/health/database` for a
credential-free connectivity result. The latter returns HTTP 503 when PostgreSQL is unavailable or
not configured.

## Supabase authentication and saved analyses

Analytics endpoints remain public. Supabase Auth supplies optional email/password and anonymous
guest sessions; only permanent authenticated users can access `/api/v1/saved-analyses`. The
backend verifies access-token signatures against the project's rotating asymmetric JWKS and uses
the verified `sub` UUID for every ownership query. It never accepts a user identifier from a
request payload and does not store passwords or duplicate Supabase credentials.

Add these values to the project-root `.env`:

```dotenv
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
SUPABASE_JWT_AUDIENCE=authenticated
SUPABASE_JWKS_CACHE_SECONDS=600
```

Set matching `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` values for the frontend. The
publishable key is intended for browsers; never place a service-role key or `DATABASE_URL` in a
`VITE_` variable.

Supabase dashboard setup:

1. Enable Email/Password and Anonymous Sign-ins under Authentication providers.
2. Configure local and deployed Site URL / Redirect URLs.
3. Use asymmetric JWT signing keys so the JWKS endpoint contains public verification keys.
4. Keep the anonymous sign-in rate limit enabled and enable CAPTCHA/Turnstile in public deployments.
5. Establish cleanup for old anonymous users, which Supabase does not remove automatically.

Email confirmation follows the dashboard setting. Anonymous sessions are temporary, cannot save
analyses, and cannot be recovered after logout or cleared browser storage. Apply the existing
schema with `python -m alembic upgrade head`. Run backend verification with `python -m pytest`,
`python -m ruff check .`, and `python -m ruff format --check .`; in `frontend`, run `npm test`,
`npm run typecheck`, `npm run build`, and `npm run test:sites`.

## Source contract and limitations

- [FUELHH stream documentation](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream)
- [WINDFOR stream documentation](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream)
- [Elexon developer portal](https://developer.data.elexon.co.uk/)

The client uses `publishDateTimeFrom`, `publishDateTimeTo`, and `format=json`, and accepts either
the stream array or JSON `data` envelope. There is no offset pagination on these stream endpoints;
bounded retrieval is enforced before network access. A malformed matching source record fails the
request rather than being silently dropped. Source status is process-local and resets on restart;
no database is justified for core analytics. Caching, schedulers, trading decisions, and dashboard
aggregation remain out of scope.
