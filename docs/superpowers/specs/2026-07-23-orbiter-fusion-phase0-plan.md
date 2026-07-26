# Orbiter Fusion — Phase 0 Implementation Plan

> **Provenance.** Generated 2026-07-23 by the `orbiter-phase0-plan` workflow (5 parallel area-drafters → global sequence → adversarial critique → finalize). All 16 critique points were confirmed against real source before finalizing — notably: `requests` is not imported by any kept module (bhuvan is a pure URL-builder), `rio-tiler` is transitive via unpinned `titiler.core>=0.11.0`, the `App.jsx:218` localhost hardcode, committed `frontend/dist/`, `axios`/`react-leaflet` having zero importers in `src/`, and the timelapse caller at `App.jsx:267`. Source of truth: `2026-07-23-orbiter-fusion-phase0-design.md`.

Merged, dependency-ordered milestone sequence across the five work areas (BACKEND-FOUNDATION, BACKEND-FUSION, CLEANUP-DEPS, FRONTEND, TESTING-CI), grounded in the approved Phase 0 spec (`/workspace/orbiter-fusion - Copy/docs/superpowers/specs/2026-07-23-orbiter-fusion-phase0-design.md`) and verified against real source. The project root has a space — always quote `"/workspace/orbiter-fusion - Copy"`. The prime directive: **every milestone leaves the app runnable, import-clean, tests-green** — no milestone half-breaks the build. Red-first tests that precede their production code are quarantined behind `@pytest.mark.xfail(strict=True)` (backend) or `.skip`/`.todo` (frontend) and un-quarantined *in the same milestone* that lands their production code. Each acceptance check is tagged **[sandbox]** (this Linux no-network box can self-verify it with fake `ee`) or **[windows-only]** (requires the user's live-GEE Windows host or network install); the sandbox agent must never claim to have run a `[windows-only]` check.

**Five ordering hazards drive the sequence:** (1) import-time GEE auth must die before any test can import the app → config+auth+lifespan land in M1–M2; (2) the `app/` package move rewrites every intra-backend import atomically → one milestone (M6), sequenced *after* dead files are deleted so no corpse is relocated; (3) the interim `titiler.core`/`rio-tiler` pin must precede titiler deletion → pinned in M0, removed in M9; (4) stale-schema removal + orphaned-import fix in `main.py` must be one commit → folded into M5; (5) the backend PNG→getMapId contract flip must co-land with the frontend tile-layer flip → the flip is split so the contract-neutral bulk (M8a) can precede M7 and only a tiny flip diff (M8b) must be adjacent to M7.

---

## M0 — Baseline validation & creds (Windows-gated) + repo hygiene

**Goal.** De-risk before any refactor: prove the *current* app runs against live GEE on Windows, capture pre-pivot behaviour as a hard gate, evict committed build/venv artifacts, establish the reproducible-install baseline (interim titiler/rio-tiler pins), and stand up the green-empty test harness.

**Ordered steps.**
- **cleanup-deps-1** — pin `titiler.core` to a version whose transitive `rio-tiler` sits in a known-good window, AND add an explicit top-level `rio-tiler>=0.14,<0.19` pin (both marked `# INTERIM — removed in M9`). Rationale comment must state: rio-tiler is transitive via titiler.core; pinning titiler.core prevents pip from backtracking to a rio-tiler outside the window; both are dropped together in M9.
- **cleanup-deps-2 (early half)** — `git rm -r --cached frontend/dist backend/venv backend/venv_new backend/a1` and add all to `.gitignore` (also `static/fusion/`, SA JSON `ee-sa.json`, `credentials`, frontend env files). Evicts the stale committed build so no later grep/CI trips over its old-contract `localhost` strings.
- **testing-ci-1** — backend pytest harness: `requirements-dev.txt`, `pytest.ini` (`integration` marker + `addopts=-m "not integration"`), `tests/__init__.py`, trivial `test_smoke.py`.
- **testing-ci-3** — frontend test tooling: add `vitest`/RTL/`jsdom`/`msw`/`@vitest/coverage-v8` devDeps + `test`/`test:watch`/`test:cov` scripts; Vitest `test`+`coverage` block in `vite.config.js`; `src/test/setup.js`.
- **USER (Windows) baseline — HARD GATE** — fresh venv from pinned requirements, run `uvicorn main:app`, draw an AOI, fire a fusion, confirm the pre-pivot `imageUrl` PNG renders; record latency + screenshot. **M1 does not start until the user confirms the PNG renders OR explicitly waives the baseline.**
- **USER (Windows) creds** — begin GEE service-account provisioning (create SA, download JSON, note project id). Interactive `earthengine authenticate` already works; SA is for deploy/CI. Per locked decision 3, do not block on it.

**Files.** `backend/requirements.txt`, `backend/requirements-dev.txt`, `backend/pytest.ini`, `backend/tests/`, `frontend/package.json`, `frontend/vite.config.js`, `frontend/src/test/setup.js`, `.gitignore`.

**ACCEPTANCE CHECK.** **[windows-only]** current app serves a fusion PNG end-to-end (screenshot captured); fresh venv installs from pinned requirements with no dependency conflict. **[windows-only]** `cd frontend && npm install && npx vitest run` → exit 0 (first install needs network; sandbox cannot run it). **[sandbox]** `cd backend && pytest` → 1 passed (dev deps assumed already present in the sandbox venv); `git ls-files frontend/dist backend/venv backend/venv_new backend/a1` → empty.

**State after.** Current app proven on live GEE (or baseline waived); SA setup in flight; committed artifacts evicted; reproducible install established; both suites green-empty. No production code changed.

**Smoke-test:** the *existing* app (PNG path) — the last time it produces a PNG.

---

## M1 — Typed config (`pydantic-settings`)

**Goal.** One typed `Settings` object (`ORBITER_` prefix) that M2's resolver and M3's CORS consume; kill the SSL-disabling env writes. In-place under `backend/` (package move is M6).

**Ordered steps.**
- **backend-foundation-1** — add `pydantic-settings>=2` + `cachetools>=5` to `requirements.txt` (add-only).
- **backend-foundation-2** — create `backend/config.py`: `Settings(BaseSettings)`, `env_prefix="ORBITER_"`, fields per §C.1.1 (`gee_project` required/loud, SA file+json, `gee_high_volume`, `cors_origins=["http://localhost:5173"]`, `max_scenes_per_composite=25`, `default_cloud_cover=20.0`, `mapid_ttl_seconds=21600`, `ee_threadpool_workers=8`), `@lru_cache get_settings()`.
- **backend-foundation-3** — ship `backend/.env.example`; delete the SSL env writes at `main.py:15-16` (`GDAL_HTTP_UNSAFESSL`/`CURL_CA_BUNDLE`).
- **cleanup-deps-3** — `backend/.env.example` (full `ORBITER_*` set) + `frontend/.env.example` (`VITE_*`); names must match Settings fields + frontend env reads.
- **testing-ci-4** — `tests/test_config.py` red-first (`xfail(strict)`), un-xfail in this milestone.

**Files.** `backend/requirements.txt`, `backend/config.py`, `backend/.env.example`, `backend/main.py` (lines 15-16), `frontend/.env.example`, `backend/tests/test_config.py`.

**ACCEPTANCE CHECK.** **[sandbox]** `ORBITER_GEE_PROJECT=test python -c "from config import get_settings; s=get_settings(); assert s.cors_origins==['http://localhost:5173'] and s.mapid_ttl_seconds==21600"`; missing-project exits non-zero (ValidationError); `grep -nE "GDAL_HTTP_UNSAFESSL|CURL_CA_BUNDLE" backend/main.py` empty; `pytest tests/test_config.py -q` passes.

**State after.** Typed config available; SSL globals gone; `.env.example`s in place. `main.py` not yet independently importable (still imports doomed titiler/schemas) — proven via the config unit test, not `import main`.

**Smoke-test:** none user-facing; config unit test is the proof.

---

## M2 — Auth resolver + lifespan-only GEE init (the testability unlock)

**Goal.** Extract GEE auth into a pure function; make lifespan the *only* place GEE initializes; **kill the import-time auth trigger — the module-level singleton `gee_fusion_service = GEEFusionService()` at `gee_fusion_service.py:1274`, which fires `__init__` (`:84`) → `_try_auto_init()` (`:94`) → `ee.Initialize(` (`:100`)**. After this, importing the app performs **zero** network calls.

**Ordered steps.**
- **backend-foundation-4** — create `backend/services/gee_auth.py`: `init_earth_engine(cfg)` implementing SA-json → SA-file → ADC priority; high-volume `opt_url`; no hardcoded project; `ee.Initialize` reachable only on call. Does not import `gee_fusion_service`.
- **backend-foundation-5** — neuter auth ownership in `GEEFusionService`: delete `_try_auto_init` (`:96-107`) **and** the `__init__` call to it (`:94`); make `__init__` side-effect-free (no network); delete `initialize_gee`; drop the dead `self._executor`. **Then convert the module-level `GEEFusionService()` at `:1274` into a side-effect-free instance (or lazy accessor) and confirm by grep that no import path can authenticate.** Keep a harmless `self.initialized=False` attribute until M7 removes its last reader.
- **backend-foundation-6** — replace the no-op lifespan at `main.py`: `cfg=get_settings()`; set `app.state.settings/gee_ready/gee_error`; `try init_earth_engine(cfg)` (degraded-safe, never crashes); create `app.state.ee_pool=ThreadPoolExecutor(max_workers=cfg.ee_threadpool_workers)`; shutdown on exit.
- **testing-ci-2** — fake-`ee` `conftest.py` + `tests/fakes/fake_ee.py` (chainable op-recording image/collection; `getMapId` returns `{z}/{x}/{y}` template; `size().getInfo()` controllable; `EEException`). **Scope the `sys.modules['ee']` injection to skip the `integration` marker** so M10's real-GEE suite binds real `ee`. Autouse sets `ORBITER_GEE_PROJECT=test-project`.
- **testing-ci-5** — `tests/test_auth_resolver.py`: SA-path-wins, ADC fallback, high-volume toggle, missing-project loud, and the regression guard `assert "compact-arc-482620-r8" not in inspect.getsource(gee_auth)`. Also assert the singleton import is auth-free: importing the service module with a fake `ee` records **zero** `Initialize` calls. Un-xfail here.
- **backend-foundation-10** — creds-free-import contract (same deliverable as testing-ci-2/4/5; testing-ci owns the files).

**Files.** `backend/services/gee_auth.py`, `backend/services/gee_fusion_service.py`, `backend/main.py`, `backend/tests/conftest.py`, `backend/tests/fakes/fake_ee.py`, `backend/tests/test_auth_resolver.py`.

**ACCEPTANCE CHECK.** **[sandbox]** `grep -nE "_try_auto_init|ee\.Initialize" backend/services/gee_fusion_service.py` empty; importing the service module under fake `ee` records zero `Initialize` calls (asserted in `test_auth_resolver.py`); mocked-`init_earth_engine`-raises lifespan test → `app.state.gee_ready is False and gee_error is not None`; `pytest tests/test_auth_resolver.py tests/test_config.py -q` passes with no creds/network.

**State after.** GEE auth is pure + lifespan-only; import-time auth eradicated; fake-`ee` harness live; auth/config suites green. (Full `import main` still blocked on titiler/schemas — proven via lifespan/singleton unit tests, not raw import.)

**Smoke-test:** **[windows-only]** run `pytest -m "not integration"` on Windows with no GEE creds and watch it pass — proof the app no longer authenticates at import. (**[sandbox]** the same command self-verifies here.)

---

## M3 — Threadpool helper + single env-driven CORS

**Goal.** Add the `run_in_pool` primitive (consumed by fusion/search later) and collapse the two CORS middlewares (`main.py:88` + `:431`, the second mixing `"*"` with credentials) into one config-driven registration.

**Ordered steps.**
- **backend-foundation-7** — add `async def run_in_pool(pool, fn, *a)` (→ `run_in_executor`); ship the primitive + `app.state.ee_pool` wiring. Fusion/search handlers are rewired by M5/M7.
- **backend-foundation-8** — delete the second CORS `add_middleware` block at `main.py:431-442`; rewrite the first (`:88`) to `allow_origins=cfg.cors_origins`, `allow_credentials=True`, methods/headers `*`. No `"*"` origin literal.

**Files.** `backend/main.py` (helper later moves to `app/core/concurrency.py` in M6).

**ACCEPTANCE CHECK.** **[sandbox]** unit test: a blocking `fn` via `run_in_pool` runs off the event loop; `grep -cE "add_middleware\(\s*$|CORSMiddleware," backend/main.py` — count the **registrations** via `grep -nE "add_middleware\(" backend/main.py` → exactly one; `grep -nE 'allow_origins=\["\*"\]' backend/main.py` empty. (The import line `from fastapi.middleware.cors import CORSMiddleware` is deliberately excluded from the count — do not `grep -c CORSMiddleware`, which matches the import too. The definitive uniqueness guard is M7's contract test.)

**State after.** Concurrency primitive + single secure CORS in place. Suite green.

**Smoke-test:** none new; CORS verifiable once endpoints exist (M7).

---

## M4 — Fusion building blocks (additive, pure, unit-tested; app unchanged)

**Goal.** Build the entire new fusion machinery as *new modules nothing imports yet*, each unit-tested against fake `ee`. The live `gee-harmonize` route keeps returning the old PNG shape throughout. The correctness bugs (LST °C, NDWI true-water, Landsat offset, mask-before-narrow) are fixed here in isolation and proven by **code-graph** assertions on the recorded op sequence — not by numeric output ranges (fake `ee` returns synthetic values, so any numeric range would be fabricated by the fake; the numeric 20–45 °C range belongs to M10's live test only).

**Ordered steps.**
- **backend-fusion-1** — confirm the M2 fake-`ee` op-recording surface covers fusion ops: `normalizedDifference`, `bitwiseAnd`, `linkCollection`, `limit`, `visualize`, etc.
- **backend-fusion-2** — additive schemas in `models/schemas.py`: `SceneCounts`, `FusionMapResponse`, `FusionRequest` (bounds `conlist(4)`, dates, cloud_cover 0-100, `visualization` Literal of the 8 modes, `platforms`, `geojson`, start>end validator). Do **not** touch old schemas yet.
- **backend-fusion-3** — `services/fusion/scaling.py`: `SensorImages` + `to_sensor_images` (S2 ×0.0001; Landsat SR ×0.0000275 −0.2; thermal ST_B10 ×0.00341802 +149.0 −273.15 → °C).
- **backend-fusion-4** — `services/fusion/masking.py`: `mask_s2` (SCL + Cloud Score+ `cs_cdf≥0.60`), `mask_landsat` (QA_PIXEL bits 1-4), band-list constants, `CSPLUS_ID`.
- **backend-fusion-5** — `services/fusion/composite.py`: bounded (`limit(max_scenes)`) mask→narrow→composite builders; no `reproject`/`sampleRectangle`; `scene_count()`.
- **backend-fusion-6** — `services/fusion/registry.py`: `VisSpec`, `FusionStrategy` Protocol, `STRATEGY_REGISTRY`, `register`/`get_strategy`.
- **backend-fusion-7** — the 8 P0 strategies (TrueColor, NDVI, NDWI=McFeeters Green/NIR, NDBI, FalseColorNIR, FalseColorSWIR, SCI, LST landsat-only °C). Drop `combined`/`true_color_swir`/`ndvi_change`.
- **backend-fusion-8** — `services/fusion/mapid.py`: `mint_mapid(image, vis, ttl)` + `visspec_to_vis`.
- **testing-ci-6** — `tests/test_fusion_graph.py` (un-xfail as each block lands): NDWI uses Green/NIR not NIR/SWIR; true-color is not `add`/`divide(2)`; **Landsat scale+offset (`×0.0000275 −0.2`) and thermal −273.15 applied *before* `normalizedDifference`** — asserted on the recorded op order, not on output value; Sentinel-LST raises + no `B10` on S2; every mode `visualize`s.
- **backend-fusion-2 test** — `tests/test_schemas_fusion.py` (start>end raises, bad Literal raises).

**Files.** `backend/models/schemas.py`, `backend/services/fusion/{__init__,scaling,masking,composite,registry,strategies,mapid}.py`, `backend/tests/{test_scaling,test_masking,test_composite,test_registry_skeleton,test_fusion_graph,test_mapid,test_schemas_fusion}.py`.

**ACCEPTANCE CHECK.** **[sandbox]** `pytest tests/test_scaling.py tests/test_masking.py tests/test_composite.py tests/test_registry_skeleton.py tests/test_fusion_graph.py tests/test_mapid.py tests/test_schemas_fusion.py -q` all pass; composite op-order asserts mask<select<median and no `reproject`/`sampleRectangle`; LST/index correctness proven by op-sequence assertions (scale→offset→−273.15→normalizedDifference), **no numeric-range assertion**. Everything additive — old PNG route still live.

**State after.** Full correct fusion engine exists and is proven by graph assertions, unused by the live route. Suite green.

**Smoke-test:** none user-facing (all additive); the fusion-graph tests are the proof the index math is correct.

---

## M5 — Delete dead code; wire the orchestrator; stale-schema removal + import fix (ATOMIC main.py/schemas)

**Goal.** Migrate live callers onto the new engine, then delete the entire numpy/PNG/COG/titiler path, the doomed service files, and **every route the spec's §C.3.1 table marks for deletion** — removing the stale schemas **in the same coherent `main.py`/`schemas.py` change** so `import main` never references a deleted symbol. This is the single commit boundary where schema-delete + orphaned-import-fix + all route-deletions co-land.

**Ordered steps.**
- **backend-fusion-9** — add `build_fusion_map(req)` to `gee_fusion_service.py` composing M4 blocks → `FusionMapResponse` dict with real scene counts (additive; old code still present).
- **backend-fusion-10** — re-plumb `generate_timelapse` (`:1058-1225`) through the registry; delete the nested `prepare_image` ladder.
- **backend-fusion-14** — delete the dead numpy/PNG pipeline from `gee_fusion_service.py` (`:316-1026` region: `resample_to_target`, `fetch_as_array`, `fuse_sensors`, `normalize_to_8bit`, `save_for_web`, `fuse_collections_server_side`, PNG/`getThumbURL`/`urlretrieve` block) plus the numpy-array helpers `compute_ndvi` (`:1227`) and `compute_ndwi` (`:1250`); drop `numpy`/`scipy`/`PIL` imports. **Guard: grep proves zero callers of `compute_ndvi`/`compute_ndwi` in kept code (esp. the re-plumbed timelapse path) before deletion.**
- **cleanup-deps-6** — delete `backend/debug_*.py` + `check_url_readability.py` (last `rio_tiler` importers outside `main.py`; these are also the only files importing `requests` — nothing kept imports `requests`, so no kept-code guard is needed for it).
- **BACKEND main.py route deletions (§C.3.1, by real line number — enumerate ALL):**
  - `:110-175` legacy `/api/fusion/harmonize` (titiler/rio_tiler path)
  - `:178-...` `/api/fusion/{fusion_id}/tiles/{z}/{x}/{y}` (**duplicate route #1**)
  - `:629-761` `/api/fusion/process` + its `FusionProcessing*` usage
  - `:764-...` `/api/fusion/{fusion_id}/tiles/{z}/{x}/{y}` (**duplicate route #2 — same path, silently shadowed**)
  - `:876-...` `/api/fusion/{fusion_id}/preview`
  - `:910`, `:923`, `:936` `/api/tiles/{sentinel,landsat,bhuvan}/*`
  - `:952`, `:989`, `:1025` `/api/analysis/*`
  - `:1060`, `:1097` `/api/export/*`
  - `:1126`, `:1157`, `:1178` `/api/datasets/{list,download,download-zip}` — **Dataset-Mode-tied; DELETED HERE.** (Decision: dataset routes die in M5, not deferred. The frontend caller at `Sidebar.jsx:321` is neutralized in M8a — see cross-milestone note below.)
  - the titiler mount + `add_exception_handlers` (`:39-40` imports, mount call) and the `StaticFiles("/static")` mount (`:104`).
  - **KEEP (explicitly, do not delete):** `/api/fusion/gee-window` (`:345`, tidy only), `/api/fusion/timelapse` (`:309`, re-plumbed), `/api/fusion/gee-harmonize` (`:214`, contract-flipped in M7 — still returns OLD PNG shape after M5), `/api/search/all` (`:580`), the sentinel/landsat/bhuvan search+scene routes.
- **cleanup-deps-8** — delete `services/{cache_service,tile_service,analysis,fusion_service}.py` (guard: grep proves zero importers in kept code first; the `main.py:31-34` imports are removed in the same commit).
- **backend-fusion-15 + cleanup-deps-7 (ATOMIC together)** — delete `FusionProcessingRequest/Response` (`schemas.py:67,75`) + old `HealthResponse` (`schemas.py:60`) **and** remove them from the `main.py:19-27` import block in the same change. New `FusionRequest`/`FusionMapResponse` (M4) already defined.
- **backend-fusion-13** — `/api/search/all`: run the two STAC searches concurrently via `asyncio.gather(run_in_pool,…)`; delete `SCENE_STORE`.
- **cleanup-deps-5** — delete the ~285 committed PNGs (the empty `static/fusion/` dir goes with its now-removed `StaticFiles` mount).

**Files.** `backend/services/gee_fusion_service.py`, `backend/main.py`, `backend/models/schemas.py`, `backend/services/{cache_service,tile_service,analysis,fusion_service}.py` (delete), `backend/debug_*.py` + `check_url_readability.py` (delete), PNGs + `static/fusion/` (delete).

**ACCEPTANCE CHECK.** **[sandbox]** `grep -rnE "getThumbURL|urlretrieve|sampleRectangle|import numpy|from scipy|from PIL|compact-arc-482620-r8|prepare_image|compute_ndvi|compute_ndwi" backend/services/gee_fusion_service.py` empty; `grep -nE "FusionProcessing|HealthResponse" backend/main.py backend/models/schemas.py` empty; `grep -rnE "tile_service|cache_service|fusion_service|analysis_service" backend/*.py` empty in kept code; `grep -nE "/api/(tiles|analysis|export|datasets)/|/api/fusion/harmonize|/api/fusion/process|/api/fusion/\{fusion_id\}/(tiles|preview)" backend/main.py` empty; `grep -nE "/api/fusion/(gee-window|timelapse|gee-harmonize)|/api/search/all" backend/main.py` all present; `pytest -m "not integration"` green.

**State after.** Codebase is registry-only; all dead files, dead routes (incl. both duplicate tile routes + all dataset routes), and stale schemas gone; `main.py` import-clean of removed symbols. **The live `gee-harmonize` route still returns the OLD PNG shape** (flipped in M7). Suite green.

**Cross-milestone note.** Backend `/api/datasets/*` are deleted here, but their frontend callers (`Sidebar.jsx:321` `download-zip`, `App.jsx` `datasetPath`) still exist until M8a. This is safe: M5 keeps the app import-clean and the backend suite green; the orphaned frontend calls simply 404 until M8a removes Dataset Mode. No milestone between M5 and M8a exercises those calls in an automated test. If schedule risk means M8a slips far past M5, that 404 window is acceptable (Dataset Mode is being removed regardless) — but M8a must remove the callers, not leave them pointing at deleted routes long-term.

**Smoke-test:** **[windows-only]** app still boots and still serves the old PNG fusion (unchanged wire contract on `gee-harmonize`) — confirm no regression from the big delete.

---

## M6 — Atomic `app/` package move

**Goal.** One commit: move every backend module under `backend/app/`, rewrite **all** flat intra-backend imports (`services.X`/`models.X`/`config` → `app.services.X`/`app.models.X`/`app.config` — flat style confirmed at `main.py:19-34`, `28-34`) to package form, create empty `app/routers/` + `app/core/` packages, switch the uvicorn target to `app.main:app`. Done *after* M5's deletions so no doomed file is relocated.

**Ordered steps.**
- **backend-foundation-9** — create `app/__init__.py`; move `main.py`, `config.py`, `models/`, `services/` (incl. `fusion/`, `gee_auth.py`) under `app/`; blanket-rewrite every flat import; create `app/routers/` + `app/core/` with `__init__.py`; move the M3 `run_in_pool` helper to `app/core/concurrency.py`; update entrypoint + docs to `uvicorn app.main:app`.
- **testing-ci-2 conftest update** — point the fake-`ee` conftest + `client` fixture at `app.main`; confirm creds-free import survives the move.

**Files.** entire `backend/app/**`, `backend/tests/conftest.py`, entrypoint/runbook docs.

**ACCEPTANCE CHECK.** **[sandbox]** from `backend/`: parse all of `app/**/*.py`; `grep -rnE "^from services\.|^from models\.|^from config import|^import main\b" app/` → **zero**; with fake `ee` + `ORBITER_GEE_PROJECT=test`: `python -c "import app.main; print('ok')"` succeeds (now fully clean — titiler/schemas gone in M5); `pytest -m "not integration"` green.

**State after.** Final package layout; import-clean; empty router/core packages ready for M7. Suite green.

**Smoke-test:** **[windows-only]** `uvicorn app.main:app` boots on Windows and still serves the old PNG fusion.

---

## M7 — Backend contract flip (PNG → getMapId) + honest `/health` + structured errors

**Goal.** Flip the live fusion endpoint to the typed getMapId contract, add the refresh-mapid endpoint, rewrite `/health` to report GEE readiness honestly (503 when not ready), wire the structured-error handler. **This is the backend half of the pivot; the tiny frontend flip M8b must follow immediately (M8a is already landed by now).**

**Ordered steps.**
- **BACKEND §C.1.4** — `app/core/errors.py`: `ServiceError` + FastAPI exception handler mapping `no_imagery`→404, `gee_unavailable`→503, `gee_compute_error`→502, `invalid_request`→400, else 500 (single `{code,...}` body).
- **BACKEND §C.1.5** — `app/core/mapid_cache.py`: TTLCaches for fusion image+vis and minted mapids.
- **backend-fusion-11** — rewrite `POST /api/fusion/gee-harmonize` into `app/routers/fusion.py`: `FusionRequest` in / `FusionMapResponse` out; gee-ready guard → 503; call `build_fusion_map` via `run_in_pool(app.state.ee_pool,…)`; errors through the shared handler; drop `create_dataset`/`destination_folder`/`window_size`.
- **backend-fusion-12** — add `GET /api/fusion/{fusion_id}/refresh-mapid` (cache lookup → re-`mint_mapid`; 404 if absent).
- **KEEP in `app/main.py`** — `/api/fusion/gee-window` and `/api/fusion/timelapse` stay where they are (only `gee-harmonize` + `refresh-mapid` move into the router); tidy `gee-window` only.
- **backend-foundation-11** — rewrite `/health`: read `app.state.gee_ready/gee_error/settings.gee_project`; 200 healthy / 503 degraded; delete `/api/fusion/gee/status` (`main.py:396-424`); drop the `gee_fusion_service.initialized` reader.
- **testing-ci-7** — `tests/test_endpoints_contract.py`: `{z}/{x}/{y}` template, `bounds [[S,W],[N,E]]`, `expires_at`, `max_native_zoom`; `/health` 200/503; **exactly one `CORSMiddleware` registration** (the definitive uniqueness guard for M3); **unique `(path,method)` across all routes** (guards against the M5 duplicate-tile-route regression); no orphaned `FusionProcessing*`/`HealthResponse` in `app.main`. Un-xfail.
- **testing-ci-8** — `tests/test_error_paths.py`: start>end → 422, short bounds → 422, both-zero counts → 404 `no_imagery`, `gee_ready=False` → 503 `gee_unavailable`, `EEException` → 502 `gee_compute_error`, cloud out-of-range → 422; structured `{code}` body. Un-xfail.

**Files.** `backend/app/core/{errors,mapid_cache}.py`, `backend/app/routers/fusion.py`, `backend/app/main.py`, `backend/tests/{test_endpoints_contract,test_error_paths}.py`.

**ACCEPTANCE CHECK.** **[sandbox]** `pytest -m "not integration"` green incl. contract + error-path suites; `grep -n "api/fusion/gee/status" backend/app/main.py` empty; TestClient: valid POST → 200 with `{z}/{x}/{y}` template, `gee_ready=False` → 503, both-zero → 404; contract test confirms one CORS registration + all-unique routes.

**State after.** Backend serves the **new getMapId contract**; PNG path fully gone; CORS + route uniqueness now test-enforced. The fusion path is broken *for the pre-flip frontend* — **M8b lands next**. Suite green.

**Smoke-test:** **[windows-only]** `curl -X POST /api/fusion/gee-harmonize` returns a JSON tile template (not a PNG); `GET /health` returns 503 without creds, 200 with project echoed. (Do not smoke-test the UI fusion until M8b.)

---

## M8a — Frontend contract-neutral rebuild (can precede or parallel M7)

**Goal.** All frontend modernization that does **not** depend on the new backend contract: api client, env, Vite proxy, config modules, store/reducer/contexts, App migration (still emitting the OLD `imageOverlay` layer), and removal of Dataset Mode's frontend surface (its backend routes died in M5). This is the large bulk of the frontend work; sequencing it as its own milestone makes the flip (M8b) a small isolated diff and makes the M7-adjacency realistic. Because everything here still speaks the old shape (or removes dead surface), it is contract-neutral and may land before, during, or after M7.

**Ordered steps.**
- **testing-ci-3 MSW handlers** — author `handlers.js` to the M7 contract (`tile_url_template`, `bounds`, `expires_at`, `scene_counts`, `visualization`, `max_native_zoom`) + `refresh-mapid` + `search/all`, ready for M8b to consume.
- **frontend-1.1–1.4** — `src/api/client.js` (`VITE_API_BASE_URL`, typed `ApiError`, `humanize`, `AbortController`); `.env.development/.production/.example`; env-driven Vite proxy (`vite.config.js:19`); route existing calls through the client **still speaking old shape**. **As part of FE-1, delete the hardcoded host at `App.jsx:216-218` (`http://localhost:8000${result.imageUrl}?t=…`)** — the client supplies the base URL, so the old-shape overlay can still render without a hardcoded host or cache-buster.
- **frontend Dataset-Mode removal (frontend surface only)** — remove the `download-zip` caller at `Sidebar.jsx:321`, `datasetPath` state (`App.jsx:56`) and its prop wiring (`App.jsx:189,351`), and the dataset-save `alert` at `App.jsx:204`. Backend routes already gone in M5, so this closes the 404 window.
- **testing-ci-10** — `api/client.test.js` incl. the repo-wide **no-`localhost:8000`** assertion. **Un-skip only now** (after FE-1 has removed `App.jsx:218`), so the repo-wide grep passes mid-milestone — never before line 218 is gone.
- **frontend-2.1–2.3** — `config/visualizations.js` (8 ids matching backend `STRATEGY_REGISTRY` exactly; LST °C 20–45 landsat-only; NDWI true-water legend), `config/basemaps.js`, `config/satellites.js` (bhuvan `readOnly`); extract `VizButton`, feed fusion+timelapse rows from config.
- **frontend-3.1–3.3** — reducer + `actions.js`; `SettingsContext`/`LayersContext` providers; migrate `App.jsx` to the store (still emitting the **old** `imageOverlay` layer so Map is untouched pre-flip).

**Files.** `frontend/src/api/client.js`, `frontend/.env.*`, `frontend/vite.config.js`, `frontend/src/config/{visualizations,basemaps,satellites}.js`, `frontend/src/components/Sidebar/VizButton.jsx`, `frontend/src/components/Sidebar.jsx`, `frontend/src/state/{reducer,actions,AppStore}.jsx`, `frontend/src/App.jsx`, plus matching `*.test.{js,jsx}`.

**ACCEPTANCE CHECK.** **[windows-only/CI]** `npm run build` succeeds; `npm run test` green incl. api-client + no-localhost tests. **[sandbox — static only]** `grep -rn "localhost:8000" frontend/src` → empty; `grep -rnE "datasetPath|download-zip|destination_folder" frontend/src` → empty. (Sandbox cannot run vitest without a network install; static greps are the sandbox-verifiable portion.)

**State after.** Frontend is config/store-driven and contract-neutral; hardcoded host and Dataset Mode gone; still renders the OLD `imageOverlay` (so if it lands before M7, the app is unchanged for the user; if after M7, fusion UX is down only until M8b). Suite green.

**Smoke-test:** **[windows-only]** app builds and runs; if M7 not yet landed, fusion still shows the old PNG overlay via the new client.

---

## M8b — The tile-layer flip (CO-LANDS WITH M7)

**Goal.** The single small diff that consumes M7's getMapId response and swaps `imageOverlay` for `L.tileLayer`. This is all that must be adjacent to M7; no shim is provided (per spec's clean-cut preference), so M7 and M8b ship as a coordinated pair on the same branch.

**Ordered steps.**
- **frontend-4.1–4.4 (THE FLIP)** — `useFusion.js` with AbortController race-fix consuming the new contract → `toTileLayer`; `Map.jsx` `type==='gee'` branch (`L.tileLayer`, `maxNativeZoom ?? 14`, `maxZoom:20`, `fitBounds`), demote `imageOverlay` (`Map.jsx:219-222`) to `[LATER]`, keep `wms` for Bhuvan; `tileerror` refetch via `refresh-mapid`; delete `pixelated`/`dim-tiles` CSS hacks. Add `data-testid={`layer-${mode}`}` on the active overlay.
- **testing-ci-12** — click-race test (NDVI slow, true_color fast → only `layer-true_color` present), consuming the `data-testid`. Un-skip.

**Files.** `frontend/src/hooks/useFusion.js`, `frontend/src/components/Map.jsx`, `frontend/src/index.css`, `frontend/src/**/*.test.{js,jsx}`.

**ACCEPTANCE CHECK.** **[windows-only/CI]** `npm run build` + `npm run test` green incl. click-race. **[windows-only]** draw AOI → click True Color → **real GEE XYZ tiles render** (crisp, zoom to 20); rapid mode-switch shows only the last-clicked layer; tile-expiry triggers `refresh-mapid`.

**State after.** End-to-end fusion works on the new getMapId contract; UI is store-driven and race-safe. Both suites green.

**Smoke-test (the big one):** **[windows-only]** full UI fusion against live GEE — tiles, mode switching, tile-expiry refetch.

---

## M9 — Real-UX polish, dead-code purge, dependency slimming, unpin

**Goal.** Replace all `alert()`s with real feedback, delete orphaned frontend files, remove the timelapse UI caller (endpoint stays, control surface deferred to Phase 2), drop unused deps on both sides with lockfile regeneration, and **remove the interim titiler/rio-tiler pins now that their last importer is gone**.

**Ordered steps.**
- **frontend-5.1–5.4** — Toast/FusionStatus/indeterminate Loader; replace all remaining `alert()`s → dispatch/toast/inline; DateRangePicker validation + config-driven LayerControl + IndexLegend (LST °C) + BasemapControl + ModeSelector. (Dataset Mode already gone in M8a; Bhuvan stays read-only with its `wms` branch.)
- **timelapse frontend fate** — the `/api/fusion/timelapse` endpoint is kept (P0), but its P0 control surface (`TimeSlider`) is deferred to Phase 2. **Remove the dangling timelapse caller at `App.jsx:267` and the "select a satellite" `alert` at `App.jsx:256`** so no UI invokes an endpoint with no control. (Endpoint remains callable for Phase 2 / API clients.)
- **testing-ci-11** — component smoke (disabled-in-flight, error-banner-not-alert) + repo-wide **no-`alert(`** test. Un-skip.
- **frontend-6.1 / cleanup-deps-10** — delete `TypingIntro`, `ExportPanel`, `TimeSlider`, `utils/performanceUtils.js` (imports removed in the same change).
- **frontend-6.2 / cleanup-deps-11** — drop `axios` + `react-leaflet` from `package.json` (grep-guarded: zero importers in `src/`, already confirmed). **Run `npm install` to regenerate `package-lock.json`** so M10's `npm ci` does not fail on lockfile mismatch.
- **frontend-6.3–6.4** — consolidate inline `<style>` into `index.css` + design tokens (run `frontend-design` skill to pin tokens); a11y baseline (`:focus-visible`, `prefers-reduced-motion`, `role="radiogroup"`, aria-labels) + responsive breakpoints.
- **cleanup-deps-9** — remove the interim `rio-tiler` pin AND the interim `titiler.core` pin; prune `requirements.txt` (DROP titiler.core, mercantile, rasterio, xarray, rio-tiler, python-multipart, numpy, scipy, Pillow, shapely, pyproj; `httpx` stays only if used by tests/kept code; `requests` — **confirmed unused by any kept module** (only the deleted debug files imported it) so DROP; KEEP fastapi/uvicorn/pydantic/pydantic-settings/cachetools/earthengine-api/pystac-client/planetary_computer). Grep proves zero importers of each dropped package in `backend/app` first.

**Files.** `frontend/src/components/feedback/*`, `frontend/src/components/{Sidebar,Map,legend}/*`, `frontend/src/App.jsx`, `frontend/src/index.css`, deleted frontend files, `frontend/package.json`, `frontend/package-lock.json`, `backend/requirements.txt`, `backend/tests/{test_no_alert,FusionStatus.test}.jsx`.

**ACCEPTANCE CHECK.** **[sandbox — static]** `grep -rn "alert(" frontend/src` empty; `grep -rnE "isDatasetMode|datasetPath|create_dataset|/api/fusion/timelapse|TypingIntro|ExportPanel|TimeSlider|axios|react-leaflet|<style>|pixelated" frontend/src` empty; `grep -rn "bhuvan" frontend/src` present; backend `for p in titiler mercantile rasterio xarray rio_tiler numpy scipy PIL multipart shapely pyproj requests; do grep -rqnE "import $p|from $p" backend/app && echo "LEFT: $p"; done` → no output. **[windows-only/CI]** fresh venv installs from pruned requirements; `npm ci` succeeds against the regenerated lockfile; `npm run build` + `npm run test` green; `pytest -m "not integration"` green.

**State after.** No `alert()`, no dead code, no dangling timelapse caller, lean dependency trees on both sides, interim pins removed, lockfile synced, design tokens + a11y in place. Both suites green.

**Smoke-test:** **[windows-only]** full UI with real feedback (loading bar, error cards + Retry, toasts), basemap switching, date validation, LST °C legend; lean `pip install` / `npm ci`.

---

## M10 — CI gates + gated real-GEE + non-blocking E2E

**Goal.** Lock the whole thing behind CI, author the on-demand real-GEE suite (never in CI), add a non-blocking Playwright happy path.

**Ordered steps.**
- **testing-ci-13** — `.github/workflows/ci.yml` backend job: `pip install -r backend/requirements-dev.txt` → `pytest -m "not integration" --cov=app --cov-fail-under=75` (+ per-module gates: resolver 95%, config 90%, fusion-graph 80%, endpoints 85%).
- **testing-ci-14** — frontend CI job: `npm ci` → `npm run test:cov` (threshold 55%; api/client 90%, components 60%) → `npm run build`.
- **testing-ci-9** — `tests/integration/test_gee_live.py` behind `@pytest.mark.integration` + `ORBITER_GEE_LIVE=1`: real tile 200 `image/*`, latency <20s, Landsat-only LST, **the numeric LST 20–45 °C range assertion** (belongs here, against real GEE — not M4's fake), Cloud Score+ smoke on Bengaluru Q1-2024. Its marker-scoped conftest binds real `ee` (per M2). Authored here; **run only by the user on Windows**.
- **testing-ci-15** — Playwright `e2e/happy-path.spec.ts` + `playwright.config.ts`; non-required CI job `continue-on-error: true`.

**Files.** `.github/workflows/ci.yml`, `backend/tests/integration/test_gee_live.py` (+ scoped conftest), `backend/.coveragerc`, `frontend/e2e/*`, `frontend/playwright.config.ts`, `frontend/package.json`.

**ACCEPTANCE CHECK.** **[windows-only/CI]** CI backend + frontend jobs green on a pushed branch; e2e job present + non-required; `pytest --collect-only -m "not integration"` shows 0 integration selected. **[windows-only]** `ORBITER_GEE_LIVE=1 ORBITER_GEE_PROJECT=<proj> pytest -m integration` → real tiles 200, latency <20s, LST within 20–45 °C.

**State after.** CI enforces green + coverage on every push; real-GEE proof runnable on demand; E2E authored non-blocking. **Phase 0 complete.**

**Smoke-test:** **[windows-only]** push a branch and watch CI go green; run the live-GEE integration suite to prove the pivot against real Earth Engine.

---

## Success criteria (spec §D) → milestone map

| # | Success criterion (§D) | Satisfied by |
|---|---|---|
| 1 | getMapId mints a working XYZ template; real tile returns 200 `image/*` | M4 (mint), M7 (endpoint), **M10** (live proof) |
| 2 | Fusion request completes < 20 s against live GEE | M4–M5 (bounded composite, no PNG download), **M10** (latency assertion) |
| 3 | No hardcoded project/host/creds (`compact-arc-482620-r8`, `localhost:8000`) | M1–M2 (config+resolver), M2 (regression guard on singleton import), M8a (frontend no-localhost, `App.jsx:218` removed) |
| 4 | `/health` honestly reports GEE readiness (200/503); `gee/status` gone | **M7** |
| 5 | Config from env (`ORBITER_`/`VITE_`), typed, loud on missing project | M1 (backend `Settings`), M8a (frontend env/client) |
| 6 | Correct indices: LST °C, true-water NDWI, Landsat offset, mask-before-narrow, registry-shared timelapse | **M4** (engine, op-graph proof), M5 (timelapse re-plumb), M10 (numeric LST range live) |
| 7 | "One of everything": single CORS, single tiles-route owner, no dup middleware/route | M3 (CORS collapse), M5 (both duplicate tile routes `:178`+`:764` deleted), M7 (uniqueness contract test) |
| 8 | Zero `alert()`; Dataset Mode removed; Bhuvan wired read-only; race-safe fusion | M8a (Dataset Mode frontend gone, Bhuvan read-only), M8b (race-fix), **M9** (alerts) |
| 9 | Suites present + green in CI; coverage ≥75% backend / ≥55% frontend; `npm run build` passes | M0/M2/M4/M7 (backend suites), M8a/M8b/M9 (frontend suites), **M10** (CI + gates) |
| 10 | Audited `requirements.txt` installs without missing-`rio-tiler`/titiler conflict | M0 (interim titiler+rio-tiler pins, transitive rationale), **M9** (prune + unpin + lockfile sync), M10 (clean install in CI) |

## What the user can smoke-test after each milestone

- **M0:** current app still serves a PNG fusion (baseline screenshot, HARD GATE); artifacts evicted; suites green-empty.
- **M1:** config unit test passes; missing project fails loudly.
- **M2:** `pytest -m "not integration"` passes with no GEE creds — import is auth-free.
- **M3:** (internal) single CORS registration + `run_in_pool` unit test.
- **M4:** fusion-graph tests prove LST °C + true-water NDWI + Landsat offset ordering (no UI change).
- **M5:** app still boots + still serves old PNG fusion after the big delete (no regression); all dead routes gone.
- **M6:** `uvicorn app.main:app` boots; old PNG fusion still works.
- **M7:** `curl` fusion returns a JSON tile template; `/health` 503/200 honest. (UI fusion intentionally down until M8b.)
- **M8a:** app builds/runs on the new client; Dataset Mode gone; still old overlay if M7 not yet in.
- **M8b:** **full UI fusion on live GEE** — real XYZ tiles, rapid mode-switch shows only last layer, tile-expiry refetch.
- **M9:** real feedback (loading/error/toast), basemap switch, date validation, LST °C legend; lean installs.
- **M10:** CI green on push; live-GEE integration suite proves real tiles <20s on Windows.

---

**Global runnable-at-every-milestone invariant.** Backend: `cd backend && pytest -m "not integration"` exits 0 at the end of every milestone (red-first tests `xfail(strict)` until their production step lands in the same milestone), self-verifiable **[sandbox]** with fake `ee` for M1–M10. Frontend: `cd frontend && npm run build && npx vitest run` exit 0 from M0 onward (requires an installed node_modules — **[windows-only/CI]**; the sandbox verifies frontend milestones by static grep only). The only window where the *end-to-end fusion UX* is intentionally broken is strictly between M7 and M8b — which is why M8b is the small isolated flip that ships coordinated with M7 on the same branch, with M8a's contract-neutral bulk landed beforehand. No shim to `imageUrl` is provided (spec prefers the clean cut), so M7 must not merge to a shared branch without M8b ready.