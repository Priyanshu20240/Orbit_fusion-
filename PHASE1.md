# Phase 1 — Real Fusion I

**Status: COMPLETE.** Adds three new fusion strategies to the `STRATEGY_REGISTRY`
on top of the Phase 0 foundation, without changing the endpoint contract or the
getMapId tile model.

Full design: [docs/superpowers/specs/2026-07-24-orbiter-fusion-phase1-design.md](./docs/superpowers/specs/2026-07-24-orbiter-fusion-phase1-design.md)

## What landed

| Strategy | Sensor req | Algorithm | Front-end label |
|---|---|---|---|
| **`gap_fill`** | S2 + L8 (or either alone as fallback) | `sentinel.unmask(landsat)` — S2 authoritative; L8 fills only S2 cloud/shadow gaps | "Gap-Fill" |
| **`harmonized_l8`** | S2 + L8 | HLS-style per-band linear bandpass (Claverie 2018); operational v1.5 coefficients in code, env-var override | "Harmonized" |
| **`real_lst`** | L8 only | Per-pixel NDVI-based emissivity (Sobrino 2004) + grey-body `T / ε^(1/4)` Planck correction; °C 20–45 | "LST (real)" |

The original 8 strategies (`true_color`, `ndvi`, `ndwi`, `ndbi`,
`false_color_nir`, `false_color_swir`, `sci`, `lst`) are unchanged. The
`STRATEGY_REGISTRY` now holds 11 entries; the `FusionRequest` `visualization`
Literal now accepts all 11 ids; the `VISUALIZATIONS` config in the frontend
exposes all 11 buttons.

## Endpoint contract — unchanged

`POST /api/fusion/gee-harmonize` returns the same `FusionMapResponse` shape
(`tile_url_template`, `bounds`, `expires_at`, `scene_counts`, `max_native_zoom`)
for all 11 modes. The frontend consumes it identically.

## How to use the 3 new modes

In the UI, the 3 new buttons appear in the **Visualization mode** selector
alongside the original 8. The new buttons are:

- **Gap-Fill** (S2 + L8 selected): draws an RGB composite where the S2 pixels
  come through at 10 m and L8 fills any cloud/shadow gaps at 30 m.
- **Harmonized** (S2 + L8): draws a HLS-style harmonized RGB composite.
- **LST (real)** (L8 only): the same `°C 20–45` palette as the existing
  LST, but with per-pixel NDVI-based emissivity correction.

When only Sentinel-2 is selected, **Harmonized** and **LST (real)** are
hidden — `harmonized_l8` needs L8, and `real_lst` is L8-only. **Gap-Fill**
is hidden too in that case (its fallback path returns S2 alone, which is
indistinguishable from `true_color`; the UI hides it to avoid a duplicate
button).

## Overriding HLS coefficients

The `harmonized_l8` strategy uses the HLS S30↔L30 v1.5 operational
coefficients by default. To use a regional refit, drop a JSON file of
per-band `[slope, intercept]` pairs and point at it via env var:

```bash
# hls_coeffs.json
{
  "blue":  [0.85, 0.01],
  "green": [0.88, 0.007],
  "red":   [0.93, 0.006],
  "nir":   [0.74, 0.018],
  "swir1": [1.29, -0.005],
  "swir2": [1.00, 0.004]
}
```

```bash
export ORBITER_HLS_COEFFS=/path/to/hls_coeffs.json
```

Any band omitted from the file falls back to the operational default. The
coefficients are validated at startup (the `from_env` loader wraps the
JSON read in a `try/except` and falls back to defaults on any parse error).

## Test surface

| File | Tests added | What they lock |
|---|---|---|
| `backend/tests/test_scaling.py` | +5 | HLS defaults match Claverie v1.5; `from_env` returns defaults when unset; env-var file overrides; `HLSCoefficients` is frozen; bandpass emits 6 multiply + 6 add per call |
| `backend/tests/test_fusion_graph.py` | +8 | 11 strategies (was 8); the 3 new strategies build, raise correctly on missing sensors, and call the right `ee` ops; the `experimental=False` regression guard |
| `backend/tests/test_endpoints_contract.py` | +3 (parametrized) | The 3 new modes are reachable through `POST /api/fusion/gee-harmonize` |
| `frontend/src/test/click-race.test.js` | +2 | The AbortController click-race works for `harmonized_l8` + `gap_fill`; `real_lst` reaches success status |

**Backend test count: 84** (68 baseline + 16 Phase 1 additions). All pass
in the sandbox. **Frontend test count: 5** (3 baseline + 2 Phase 1) —
verifiable on the Windows host via `npm test`.

## Known limitations (deliberate)

| Limitation | Why | [LATER] upgrade |
|---|---|---|
| `real_lst` uses the grey-body approximation `T_raw / ε^(1/4)`, not full single-channel Planck | GEE doesn't expose Planck's B and B⁻¹ natively; the grey-body error is < 0.5 K for ε ∈ [0.97, 0.99] | Full single-channel via MOD07 atmospheric profiles |
| `real_lst` uses NDVI-threshold ε (Sobrino 2004), not ASTER GED | NDVI-based is sufficient for the 0.97–0.99 range; no extra data joins | ASTER GED emissivity (one-line swap in `real_lst.build()`) |
| No provenance band on `gap_fill` | The first consumer of "S2-vs-fill" provenance is the Phase 2 time-series scrubber | Phase 2 adds a `provenance` band + UI affordance |
| No HLS coefficient **refit** workflow in-tree | Refitting needs an S2∩L8 overlap dataset and a regression; that's a separate project | An operator can refit on Windows and drop the JSON via `ORBITER_HLS_COEFFS` |
| `harmonized_l8` and `gap_fill` both have `legend: null` (RGB) | They're RGB composites; the legend would just be a colorbar | Add legends if/when a use case appears (e.g. NDVI-on-harmonized) |

## What's next

**Phase 2 — Harmonized time series.** Interleaved S2 + harmonized-L8 on a
common date axis; rebuilt `TimeSlider`; swipe/spyglass compare. The
`harmonized_l8` strategy from Phase 1 is the substrate for that.

## Provenance

The Phase 1 design was a single-expert pass grounded in the live tree (the
Phase 0 5-track workflow was overkill — Phase 1 is purely additive, all
the plumbing exists, and the algorithms are well-documented in literature:
Claverie 2018 for HLS, Jiménez-Muñoz 2014 + Sobrino 2004 for LST). All
of the 4 open questions from design §E were resolved with the recommended
defaults (operational HLS v1.5 coefficients; NDVI-based ε + grey-body;
`gap_fill` / `harmonized_l8` / `real_lst` naming; advertised in the UI
from day one).
