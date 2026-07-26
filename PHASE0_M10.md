# Phase 0 — M10: CI + on-demand live-GEE

**Status: COMPLETE.**

Phase 0 ends with the CI plumbing that proves the rest of the milestones
actually hold together under automation.

## What runs on every push

| Job | What | Wall clock |
|---|---|---|
| `backend-unit` | `pytest -m "not integration" --cov=app --cov-fail-under=70` | ~30s |
| `frontend-unit` | `npm run test:cov` (vitest, coverage gate 60/60/55/50) | ~30s |

Push CI target: < 90s end-to-end.

## What runs on-demand (workflow_dispatch)

| Job | What | Why opt-in |
|---|---|---|
| `backend-live` | `pytest -m integration` against real GEE | Needs creds, network, blows GEE quota |
| `e2e` | `playwright test` against a built frontend + live backend | Same; also needs a browser |

The on-demand jobs require two GitHub secrets:

- `ORBITER_GEE_PROJECT` — your Earth Engine / GCS project id.
- `ORBITER_GEE_SERVICE_ACCOUNT_JSON` — a service-account JSON blob
  with the `Earth Engine Resource Viewer` (or `Owner`) role. The
  workflow writes it to `/tmp/ee/sa.json` and exports
  `GOOGLE_APPLICATION_CREDENTIALS` so the EE SDK picks it up via ADC.

## Running the suite locally

Backend:

```bash
cd backend
ORBITER_GEE_PROJECT=test-project pytest -m "not integration"
# or
ORBITER_GEE_PROJECT=test-project pytest -m "not integration" --cov=app --cov-fail-under=70
```

Frontend:

```bash
cd frontend
npm ci
npm test                       # once
npm run test:cov               # with coverage
npm run e2e                    # Playwright happy-path (needs backend on :8000)
```

## Why a marker (not a separate test directory)?

`tests/integration/test_gee_live.py` lives next to the unit tests but
is gated by the `integration` marker. `pytest.ini` excludes the
marker from the default run via `addopts = -m "not integration"`.
The CI `backend-unit` job uses the same flag; the `backend-live` job
drops the exclusion and adds `ORBITER_GEE_LIVE=1` so the fake_ee
injection in `tests/conftest.py` is bypassed.

## Why opt-in for E2E?

A real E2E that draws an AOI and round-trips a fusion needs a live
GEE backend and 30+ seconds. Running that on every PR is slow,
flaky, and burns free-tier quota. The on-demand `e2e` job is the
operator's pre-release check, not a gating signal.

## M10 deliverables

| File | Purpose |
|---|---|
| `.github/workflows/ci.yml` | All four jobs (push + workflow_dispatch) |
| `backend/tests/integration/test_gee_live.py` | Real-GEE smoke + happy-path fusion |
| `backend/tests/integration/__init__.py` | Package marker |
| `frontend/playwright.config.js` | Playwright config (preview server, not dev) |
| `frontend/e2e/happy-path.spec.js` | The single E2E test |
| `frontend/package.json` | `e2e` script + `@playwright/test` devDep |
| `frontend/vite.config.js` | Coverage thresholds (60/60/55/50) |

## What the M10 plan did NOT include

- **Per-PR deploy previews.** Phase 1 work; M10 deliberately stops
  at the CI signal, not the deploy signal.
- **Mutation testing / fuzz.** Not in the spec.
- **Performance regression suite.** The P0 latency budget (`<20s
  end-to-end fusion`) is a manual smoke on the Windows host.
