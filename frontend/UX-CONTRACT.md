# WindSight UX Contract

## Canonical UI Map

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
|---|---|---|---|---|
| Select/Listbox | Native HTML select | DESIGN.md and this contract | Native, read-only-disabled | Keyboard and browser inspection |
| Date | Native HTML date/time inputs | Backend UTC date contract | Date, time | Validation unit and browser tests |
| Form | Shared `Field` component and analysis validators | Backend analytics query contract | Analytics filters | Component tests |
| Scrollbar | Global application stylesheet | DESIGN.md | Default document geometry | Computed style and browser inspection |

## Workflow Contract

- The Forecast Analysis page owns the committed UTC period and cutoff in URL parameters.
- Apply validates locally, replaces URL state, cancels stale requests, and fetches analytics.
- Refresh repeats the committed query and retains the last successful result while loading.
- Reset restores the latest seven completed UTC days and a 12:00 cutoff.
- Backend failure remains visible inline with Retry; it never silently displays demo analytics.
- Disabled navigation items expose “Coming soon” and never navigate.

## State Contract

| State | Observable behavior |
|---|---|
| Initial loading | Primary actions are busy; stable empty metric and chart geometry remains visible. |
| Success | Metrics and chronological comparison chart use only backend matched intervals. |
| Empty | Metrics show em dashes and the chart explains that no matched records were returned. |
| Refreshing | Existing results remain visible; refresh and apply actions show busy state. |
| Error | Inline alert names the recovery step and provides Retry. |
| Validation error | Field retains its value, exposes associated text, and receives focus. |
