# WindSight

WindSight compares Great Britain wind-generation forecasts with actual generation. The React/Vite
dashboard calls a FastAPI service that retrieves live Elexon FUELHH and WINDFOR data, applies an
inclusive publication-time decision cutoff, and reports MAE, RMSE, signed bias, coverage, and data
quality. PostgreSQL stores retrieved source records, and Supabase Auth supplies email/password
and anonymous guest sessions.

## Architecture and boundaries

- Analytics and source-status endpoints are public and read live Elexon data.
- Persistence is best-effort for Elexon retrievals: a database outage does not replace valid live
  analytics with an empty or failed result.
- The browser receives only the Supabase project URL and publishable key. Database credentials and
  service-role keys remain backend-only.

  <img width="1336" height="1226" alt="mermaid-diagram" src="https://github.com/user-attachments/assets/60c749ad-6a8e-4f5f-9036-90de7d39c99e" />


## Configuration

Copy placeholder values from `backend/.env.example` and `frontend/.env.example`. The backend reads
the project-root `.env` independent of its launch directory. Required external configuration:

- `DATABASE_URL`
- `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY`
- `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY`

In Supabase, enable Email/Password and Anonymous Sign-ins, configure allowed Site/Redirect URLs,
and use asymmetric signing keys with a populated JWKS endpoint. Keep anonymous rate limiting
enabled; use CAPTCHA/Turnstile for a public deployment. Never use a service-role key in a `VITE_`
variable.

## Local startup

```powershell
cd backend
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:8001`. Open `http://127.0.0.1:5173`.

## Docker Compose

Compose builds a production Nginx frontend and non-root FastAPI backend while retaining external
Elexon, PostgreSQL, and Supabase services. The root `.env` is mounted read-only into the backend;
only publishable Supabase values become frontend build arguments.

```powershell
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
```

Open `http://127.0.0.1:8080`. Stop with `docker compose down`. The backend applies Alembic
migrations before serving traffic.

## Vercel container deployment

Vercel deploys this repository as two container services declared in `vercel.json`. Requests under
`/api/` go directly to the FastAPI service and every other request goes to the Nginx/Vite service.
The Vercel Nginx configuration deliberately has no API proxy, and `VITE_API_BASE_URL` remains unset
so browser requests use the deployment's same origin. The Compose files remain the local workflow.

In the Vercel project dashboard, select the **Services** framework preset. Configure Preview and
Production with these values:

- Secret: `DATABASE_URL` and any future private API token.
- Config: `APP_ENV=production`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`,
  `SUPABASE_JWT_AUDIENCE=authenticated`, `VITE_SUPABASE_URL`,
  `VITE_SUPABASE_PUBLISHABLE_KEY`, and `CORS_ORIGINS=[]`.
- Do not configure `VITE_API_BASE_URL` or `PORT`; Vercel uses same-origin routing and port 80 by
  default. Never put a database URL or Supabase service-role key in a `VITE_` variable.

Configure the production and preview Site/Redirect URLs in Supabase Auth, enable anonymous sign-in
only if guest access is intended, and verify Row Level Security policies before release.

Migrations are not run by autoscaling backend containers. Apply them once from a controlled machine
before promoting production:

```powershell
npx vercel@latest link
npx vercel@latest env pull .env.production.local --environment=production
Set-Location backend
npx dotenv-cli -e ../.env.production.local -- python -m alembic upgrade head
Set-Location ..
Remove-Item -LiteralPath .env.production.local
```

Create and inspect a preview deployment:

```powershell
npx vercel@latest deploy
npx vercel@latest inspect <preview-url>
curl.exe -fsS <preview-url>/api/v1/health
curl.exe -fsS <preview-url>/api/v1/health/database
curl.exe -fsS <preview-url>/overview
```

After the preview and migration pass, stage the exact production build, smoke-test it, and promote
that tested deployment:

```powershell
npx vercel@latest deploy --prod --skip-domain
npx vercel@latest inspect <staged-production-url>
curl.exe -fsS <staged-production-url>/api/v1/health
curl.exe -fsS <staged-production-url>/api/v1/health/database
npx vercel@latest promote <staged-production-url>
npx vercel@latest logs <production-url>
```

## Verification

```powershell
cd backend
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m alembic current
python -m alembic check

cd ../frontend
npm test
npm run typecheck
npm run build
npm run test:sites
```

Set `TEST_DATABASE_URL` only to a disposable PostgreSQL database when running database integration
tests. Automated auth tests use generated keys and mocked JWKS; they never require real users.

## Assumptions and limitations

- Delivery ranges and forecast-history retrieval are bounded to seven elapsed days by default.
- Start is inclusive, end is exclusive, and all timestamps require an explicit timezone before
  normalization to UTC.
- The cutoff is inclusive and analytical, not an official Elexon market deadline.
- Forecasts match actuals only by normalized delivery timestamp; there is no filling or interpolation.
- Exact duplicate forecasts use highest generation and duplicate actuals use lowest generation as
  deterministic tie-breaks; neither rule asserts source authority.
- Older publications outside the reported bounded history may exist.
- Source health is process-local and resets after backend restart.
- Anonymous sessions cannot be recovered after logout or cleared browser storage.
- Live end-to-end authentication requires manual Supabase project configuration.

See [backend/README.md](backend/README.md) for API details and [docs/DEMO.md](docs/DEMO.md) for the
ten-minute walkthrough.
