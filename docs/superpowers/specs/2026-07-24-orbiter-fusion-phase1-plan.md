# Orbiter Fusion — Phase 1 (Real Fusion I) Plan

**Date:** 2026-07-24 · **Status:** Draft for review · **Builds on:** [phase 1 design](./2026-07-24-orbiter-fusion-phase1-design.md)

This is the **executable plan** for the Phase 1 design. It's broken into milestones, each a single coherent unit of work, each with its own success gate.

---

## M0 — Pre-flight: confirm Phase 0 is the baseline

**Goal:** ensure no Phase 0 work has regressed before Phase 1 starts.

**Tasks:**
1. Run the full backend test suite: `cd backend && ORBITER_GEE_PROJECT=test-project pytest -m "not integration" -q`. **Expect:** 68/68 pass.
2. Run the frontend test suite: `cd frontend && npm test`. **Expect:** 4/4 pass (the click-race + the api-client tests + the toast test).

**Gate:** both green. If not, fix or pause — Phase 1 doesn't proceed on a broken baseline.

**Owner:** Claude (sandbox-static). **Estimated scope:** 5 min.

---

## M1 — Backend: HLS bandpass helper + config

**Goal:** the per-band linear bandpass helper is in place and unit-tested; the env-var override works.

**Files touched:**
- `backend/app/services/fusion/scaling.py` — add `HLSCoefficients` dataclass + `apply_hls_bandpass` function. ~40 LOC.
- `backend/app/config.py` — add `hls_coeffs_path: Optional[str] = None`. 1 LOC.
- `backend/.env.example` — add the `ORBITER_HLS_COEFFS=` line. 3 LOC.
- `backend/tests/test_scaling.py` — new file, 2 tests. ~60 LOC.

**Tasks:**
1. Add `HLSCoefficients` to `scaling.py` with the 6 default `(slope, intercept)` pairs from the design doc.
2. Add `apply_hls_bandpass(l8, coefs)` that does `slope.multiply().add()` per band.
3. Add `HLSCoefficients.from_env(cfg)` that loads from `cfg.hls_coeffs_path` if set.
4. Add `hls_coeffs_path` field to `Settings`.
5. Update `.env.example`.
6. Write `test_apply_hls_bandpass` — verify the 6 bands come out with the expected slope/intercept applied.
7. Write `test_hls_coeffs_from_env_overrides` — verify env-var path overrides defaults.

**Gate:** `pytest tests/test_scaling.py` 2/2 pass. **No regression in M0.**

**Owner:** Claude (sandbox). **Estimated scope:** 1 sub-task.

---

## M2 — Backend: 3 new strategy classes

**Goal:** `gap_fill`, `harmonized_l8`, `real_lst` are registered; each is reachable through `STRATEGY_REGISTRY[id]`.

**Files touched:**
- `backend/app/services/fusion/strategies.py` — 3 new classes; updated registration loop. ~80 LOC.
- `backend/app/services/fusion/registry.py` — add `experimental: bool = False` to the `FusionStrategy` Protocol. 1 LOC.

**Tasks:**
1. Add `experimental: bool = False` to the `FusionStrategy` Protocol. (The 8 existing strategies inherit the default.)
2. Write `class GapFill` with the `sentinel.unmask(landsat)` algorithm + sensor-only fallbacks.
3. Write `class HarmonizedL8` with the `apply_hls_bandpass` step + 2-sensor requirement.
4. Write `class RealLST` with the NDVI-based emissivity + grey-body correction.
5. Update the registration loop at the bottom of `strategies.py` to register the 3 new classes.
6. Add a comment in `__init__.py` to document the new modes (no code change).

**Gate:** `python -c "from app.services.fusion.registry import STRATEGY_REGISTRY; print(sorted(STRATEGY_REGISTRY))"` lists 11 ids. **No regression in M0/M1.**

**Owner:** Claude (sandbox). **Estimated scope:** 1 sub-task.

---

## M3 — Backend: 4 new tests in `test_fusion_graph.py`

**Goal:** the 3 new strategies are locked in by tests that don't depend on real GEE.

**Files touched:**
- `backend/tests/test_fusion_graph.py` — 4 new tests. ~120 LOC.

**Tasks:**
1. **`test_gap_fill_unmask_chain`** — assert the recorded op-chain on a fake `ee` contains `unmask`; sensor-only fallbacks work; `ValueError` raised when both sensors are None.
2. **`test_harmonized_l8_bandpass`** — assert `apply_hls_bandpass` is called; assert the operational Claverie defaults are used when no override; assert env-var override applies.
3. **`test_real_lst_emissivity`** — assert NDVI < 0.2 → ε = 0.97; NDVI > 0.5 → ε = 0.99; mid → linear ramp; the output °C range is reasonable (15–55).
4. **`test_experimental_default_false`** — regression guard for Phase 4: all 11 strategies have `experimental=False`.

**Gate:** `pytest tests/test_fusion_graph.py` 100% pass. **No regression.**

**Owner:** Claude (sandbox). **Estimated scope:** 1 sub-task.

---

## M4 — Backend: 1 new test in `test_endpoints_contract.py`

**Goal:** the 3 new modes are reachable through the `POST /api/fusion/gee-harmonize` endpoint.

**Files touched:**
- `backend/tests/test_endpoints_contract.py` — 1 new test. ~40 LOC.

**Tasks:**
1. **`test_three_new_modes_reachable`** — for each of `gap_fill`, `harmonized_l8`, `real_lst`, POST to `/api/fusion/gee-harmonize` with a stub AOI and assert: status 200, response has `tile_url_template` containing `{z}/{x}/{y}`.

**Gate:** `pytest tests/test_endpoints_contract.py` 100% pass. **No regression.**

**Owner:** Claude (sandbox). **Estimated scope:** 1 sub-task.

---

## M5 — Frontend: 3 new entries in `VISUALIZATIONS`

**Goal:** the 3 new modes show up in the `ModeSelector`; their `sensors` filter correctly.

**Files touched:**
- `frontend/src/config/visualizations.js` — 3 new entries. ~30 LOC.

**Tasks:**
1. Add the 3 entries from design §C.5: `gap_fill`, `harmonized_l8`, `real_lst`.
2. `gap_fill` and `harmonized_l8` have `legend: null` (RGB).
3. `real_lst` has the same legend as the existing `lst` (°C 20–45).

**Gate:** no tests to run yet (frontend test changes are M6). **Sanity:** `availableFor(['sentinel', 'landsat'])` returns 10 (the original 8 minus `real_lst` + `gap_fill` + `harmonized_l8` = 10); `availableFor(['landsat'])` returns 11; `availableFor(['sentinel'])` returns 8 (no `lst`, no `real_lst`, no `harmonized_l8`).

**Owner:** Claude (sandbox). **Estimated scope:** 1 sub-task.

---

## M6 — Frontend: 2 new tests

**Goal:** the 3 new modes are testable end-to-end (handler level + click-race level).

**Files touched:**
- `frontend/src/test/handlers.js` — extend the MSW handler to accept any `visualization` (the existing handler does this; verify by inspection).
- `frontend/src/test/click-race.test.js` — 1 new test that exercises a click-race for `harmonized_l8`. ~40 LOC.

**Tasks:**
1. **Click-race for the new modes.** Reuse the existing test infrastructure; substitute `harmonized_l8` for `ndvi`/`true_color` and confirm the AbortController race-fix still works.
2. **Regression check.** The existing `test_status_transitions_to_success_on_a_clean_fusion` still passes with `visualization: 'real_lst'`.

**Gate:** `npm test` shows 5/5 pass (the original 4 + the new 1). **No regression.**

**Owner:** Claude (sandbox). **Estimated scope:** 1 sub-task.

---

## M7 — CI: re-run, re-verify

**Goal:** the `.github/workflows/ci.yml` jobs are still well-formed and the coverage gates still hold.

**Tasks:**
1. **No code change** to `ci.yml`. Phase 1 doesn't introduce a new job, doesn't introduce a new env var requirement for the existing jobs. (The `ORBITER_HLS_COEFFS` env var is *optional*; both `backend-unit` and `backend-live` work without it.)
2. Run the **full backend suite** with coverage: `pytest -m "not integration" --cov=app --cov-fail-under=75`. **Expect:** 75/75 pass (68 + 7 new), coverage still ≥ 75%.
3. Run the **full frontend suite** with coverage: `npm run test:cov`. **Expect:** 5/5 pass, coverage still ≥ 55%.

**Gate:** both green.

**Owner:** Claude (sandbox) + operator (CI). **Estimated scope:** 1 sub-task.

---

## M8 — Docs: `PHASE1.md`

**Goal:** the operator can read one file and understand what Phase 1 changed.

**Files touched:**
- `PHASE1.md` at the repo root. ~120 LOC.

**Tasks:**
1. Section 1: what Phase 1 is (3 strategies, registry extension, no contract change).
2. Section 2: how to use the 3 new modes in the UI.
3. Section 3: how to override HLS coefficients via `ORBITER_HLS_COEFFS`.
4. Section 4: which test files were added/extended and how to run them.
5. Section 5: known limitations (grey-body emissivity correction, NDVI-threshold ε, no provenance band, no refit workflow).
6. Section 6: what's next (Phase 2 time-series scrubber).

**Gate:** file exists; section anchors all link to the design doc + the touched files.

**Owner:** Claude (sandbox). **Estimated scope:** 1 sub-task.

---

## M9 — Verification: full test pass + final acceptance

**Goal:** Phase 1 is signed off.

**Tasks:**
1. Run the full test suite (M7).
2. Run the M0 baseline check (68 backend + 4 frontend → 75 backend + 5 frontend).
3. Run the M9 acceptance greps (one per design-criterion success criterion):
   - `python -c "from app.services.fusion.registry import STRATEGY_REGISTRY; assert set(STRATEGY_REGISTRY) == {'true_color','ndvi','ndwi','ndbi','false_color_nir','false_color_swir','sci','lst','gap_fill','harmonized_l8','real_lst'}"`
   - `grep -n "gap_fill\|harmonized_l8\|real_lst" backend/app/services/fusion/strategies.py`
   - `grep -n "gap_fill\|harmonized_l8\|real_lst" frontend/src/config/visualizations.js`
   - `grep -n "experimental" backend/app/services/fusion/strategies.py` (should be `False` everywhere)
   - `grep -E "^titiler|^rio-tiler|^rasterio|^xarray" backend/requirements.txt` (should be empty)
4. Update `MEMORY.md` with a one-line Phase 1 pointer.

**Gate:** all 4 greps return expected output; both test suites green.

**Owner:** Claude (sandbox). **Estimated scope:** 1 sub-task.

---

## Risks + mitigations

| Risk | Mitigation |
|---|---|
| `real_lst` grey-body shortcut is wrong by more than the 0.5 K claim | Document explicitly in the docstring + design doc; mark as [LATER] upgrade path. |
| Claverie coefficients change between HLS versions | The env-var override is the escape hatch; the in-tree defaults are pinned to a specific HLS version (v1.5) and documented as such. |
| `unmask` doesn't propagate correctly for the 6-band reflectance case | M3 test covers it; if it fails, the strategy is wrong, not the test. |
| `apply_hls_bandpass` produces NaN where Landsat has no valid pixel | The Landsat input is already masked (`scale_landsat` after `mask_landsat`); masked pixels stay masked through the linear transform (GEE propagates masks). The output is masked in the same pixels. Documented in the helper docstring. |
| Frontend `ModeSelector` overflows with 11 entries | Current layout is 2-column grid; 11 entries / 2 cols = 5.5 rows, fits. If it overflows in CI, switch to 3-column. **Defer this** — verify visually on Windows. |
| Existing `lst` and new `real_lst` look identical to the user | The legend is the same; the difference is in the computation. Phase 1's `IndexLegend` doesn't surface this. Documented in the docstring + design doc; the operator can see the difference in a side-by-side render on Windows. |

---

## Scope summary

| Milestone | Files | LOC | Sub-tasks |
|---|---|---|---|
| M0 — Pre-flight | 0 | 0 | 1 |
| M1 — HLS helper + config | 4 | ~100 | 7 |
| M2 — 3 strategy classes | 2 | ~80 | 6 |
| M3 — 4 graph tests | 1 | ~120 | 4 |
| M4 — 1 endpoint test | 1 | ~40 | 1 |
| M5 — 3 VISUALIZATIONS entries | 1 | ~30 | 3 |
| M6 — 2 frontend tests | 2 | ~40 | 2 |
| M7 — CI re-run | 0 | 0 | 3 |
| M8 — PHASE1.md | 1 | ~120 | 6 |
| M9 — Final acceptance | 1 | ~5 | 4 |
| **Total** | **~13** | **~535** | **35** |

**Estimated turns:** 1 (this is the design + plan; the implementation is 1-2 more turns depending on test coverage).

---

## Open questions (carry-over from design §E)

1. **Operational Claverie coefficients.** Defaults in code; env-var override for regional refit. Confirm?
2. **`real_lst` atmospheric correction.** Grey-body approximation is Phase 1; full single-channel is [LATER]. Confirm?
3. **Naming.** `gap_fill`, `harmonized_l8`, `real_lst`. Confirm or rename.
4. **Frontend discoverability.** 3 new modes advertised from day one. Confirm.
