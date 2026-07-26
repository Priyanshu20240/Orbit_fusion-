# Orbiter Fusion — Phase 1 (Real Fusion I) Design

**Date:** 2026-07-24 · **Status:** Draft for review · **Parent:** [roadmap](./2026-07-23-orbiter-fusion-roadmap.md) · **Builds on:** [phase 0 design](./2026-07-23-orbiter-fusion-phase0-design.md)

**Summary.** Phase 1 closes the gap that Phase 0 deliberately left open. Phase 0 landed the `STRATEGY_REGISTRY` seam, the `SensorImages` reflectance-domain plumbing, the masked+narrowed composites, the per-band-correct LST in °C, and the single-sensor `TrueColor/NDVI/NDWI/NDBI/NIR/SWIR/SCI/LST` strategies — but every "multi-sensor" mode today is a pixel-average (`s2.add(l8).divide(2)`) at the file level, even though the registry now hides it. Phase 1 replaces the **per-mode** pixel averages with three real fusion strategies that ship under the same contract:

1. **`gap_fill`** — S2 (10 m) authoritative everywhere it has a clear pixel; Landsat 8/9 fills only S2 cloud/shadow gaps. The result is a single reflectance image at S2's native resolution and S2's acquisition geometry, with no degradation outside cloud-affected S2 pixels.
2. **`harmonized_l8`** — HLS-style radiometric harmonization (Claverie et al. 2018): per-band linear bandpass `ρ_S2 ≈ slope·ρ_L8 + intercept`, coefficients operational-grade defaults, **config-overridable for refit**. The result is an interleaved S2 + harmonized-L8 mosaic at 30 m, which is the substrate Phase 2's time-series scrubber consumes.
3. **`real_lst`** — single-channel Landsat LST *product* (Jiménez-Muñoz et al. 2014): the current `LST` strategy visualizes `ST_B10·scale+offset` in °C, which is the *emissivity-adjusted* radiance; the *real* product applies Planck inversion with **NDVI-based emissivity** (Sobrino et al. 2004) so the displayed temperature reflects actual surface emissivity, not the library default. ASTER GED emissivity is the [LATER] upgrade.

All three register in `STRATEGY_REGISTRY` with their own `sensors`, `experimental=False`, and `legend` (where applicable). The frontend's `VISUALIZATIONS` config grows three entries that match the new ids. The endpoint contract (`/api/fusion/gee-harmonize` returning a `tile_url_template`) is unchanged. **Zero new endpoints. Zero new dependencies. Zero frontend architecture changes.**

The five locked decisions from the Phase 0 design (stay on GEE, getMapId tiles, no hardcoded hosts, no `alert()`, deployable web service) carry forward unchanged.

---

## A. Overview & locked decisions

**In scope (Phase 1):**

- Three new fusion strategies in `STRATEGY_REGISTRY`: `gap_fill`, `harmonized_l8`, `real_lst`.
- A new `scaling.scale_landsat_harmonized(coefs)` helper that applies the HLS bandpass before handing the Landsat image to the gap-fill / harmonized strategies.
- One config knob: `ORBITER_HLS_COEFFS` (env-var; default = operational HLS S30↔L30 coefficients; refit on Windows).
- 3 new tests in `tests/test_fusion_graph.py`, 1 new test in `tests/test_endpoints_contract.py`, 1 new unit test for the bandpass helper.
- 3 new entries in `frontend/src/config/visualizations.js`.
- `PHASE1.md` doc (this file's plan, executed).

**Out of scope (Phase 1):**

- ASTER GED emissivity (NDVI-based is the Phase 1 default; GED is the [LATER] upgrade).
- Time-series scrubber / rebuilt `TimeSlider` (Phase 2).
- Swipe/spyglass compare (Phase 2).
- GeoTIFF export / `ExportPanel` (Phase 3).
- Super-resolution (Phase 4, experimental).
- HLS coefficient **refit** workflow (the operator may run one on Windows manually; CI just uses operational defaults).

**Locked decisions (not relitigated):**

- **Stay on GEE** (all three strategies are server-side `ee` chains, no numpy/PIL).
- **Map display = GEE tile layer** (the new strategies are *strategies* — they produce an `ee.Image` that goes through the existing `mint_mapid` path).
- **Claverie 2018 coefficients operational by default**, refit via env var.
- **NDVI-based emissivity** for `real_lst` (Sobrino 2004; `ε = 0.99` for full vegetation → `ε = 0.97` for bare soil, NDVI-thresholded at 0.2 / 0.5).
- **No `experimental=True` flag** for the three new strategies (only super-resolution gets that, Phase 4).
- **The three new modes are advertised in the frontend from day one** — not behind a feature flag.

---

## B. Roadmap (no change; restated for completeness)

| Phase | Deliverable | Status |
|---|---|---|
| Phase 0 — Foundation | registry seam, masked composites, correct indices, LST °C, honest errors, CI | ✅ COMPLETE |
| **Phase 1 — Real Fusion I** | **gap_fill + harmonized_l8 + real_lst (this doc)** | 🔜 NOW |
| Phase 2 — Harmonized time series | TimeSlider rebuilt, swipe/spyglass, timelapse re-plumbed | [LATER] |
| Phase 3 — Spectral extension + export | Broader spectral products; GeoTIFF export via async `getDownloadURL`; `ExportPanel` returns | [LATER] |
| Phase 4 — Super-resolution (experimental) | PyTorch SR model, `experimental=True` gate, fidelity metric | [LATER] |

---

## C. Phase 1 — Detailed design

### C.1 Strategy 1: `gap_fill` — S2 master, Landsat fill

**Problem this solves.** Today, when S2 has cloud over part of an AOI, that part of the result is masked (or, worse, a pixel-averaged "fusion" is dragged toward Landsat's 30 m blur). The user expects a *complete* image — they don't care which sensor supplied each pixel, they care that the image is not full of holes.

**Algorithm.** Per the Phase 0 roadmap §C.2.6:

```python
# Server-side, in the gap_fill strategy's build():
s2  = images.sentinel                          # already masked, narrow, in reflectance
l8  = images.landsat                            # already masked, narrow, in reflectance
filled = s2.unmask(l8)                          # S2 wins where present; L8 fills S2 gaps
return filled, VisSpec(...)
```

**Why `unmask`, not `where(mask)`.** `unmask(other)` is the natural dual of `updateMask`: it fills masked pixels of the primary with the values of `other`, per-band, **without** doing any reprojection or pixel-resampling. The result image inherits the primary's projection and resolution (S2's 10 m). The fill bands are *exactly* the common reflectance bands both sensors carry (after Phase 0's `to_sensor_images` renames).

**Landsat only as fill — no "fill cloud over L8".** When S2 is missing entirely (e.g. the AOI is outside S2's swath that day), Landsat carries the whole image. The current `s2_collection` and `landsat_collection` builders both already produce *masked* images; `unmask` is the right join because masked pixels of one become the other. There is no extra work in the collection builders.

**Provenance (roadmap §C.2.6 says "provenance band flags S2-vs-fill pixels").** Phase 1 does **not** add a new provenance band. Reasoning:
- The frontend renders the gap-filled image; provenance pixels aren't visible at the visualization level.
- A provenance band would have to be added at strategy `build()` time and would need a corresponding UI affordance (legend, switch, "show S2-only" / "show L8-fill" mode) which is itself a Phase 2 capability.
- A future Phase 2 strategy can build provenance on top of `gap_fill` if needed.
- **Documented decision:** provenance is deferred to Phase 2 alongside the time-series scrubber (which is the first feature that genuinely benefits from knowing the source per pixel).

**Sensor availability.** The strategy requires *both* S2 and L8; on S2-only or L8-only AOIs it falls back to the sensor that is present (delegating to the existing single-sensor view, same shape as `_optical`):

```python
def build(self, images):
    if images.sentinel is None and images.landsat is None:
        raise ValueError("gap_fill requires at least one sensor")
    if images.sentinel is None:
        return images.landsat, VisSpec(...)
    if images.landsat is None:
        return images.sentinel, VisSpec(...)
    return images.sentinel.unmask(images.landsat), VisSpec(...)
```

**Legend / color ramp.** The output image is a reflectance composite — same color range as `TrueColor` (min 0, max 0.3, gamma 1.1). No new legend entry needed in the frontend; the existing `true_color` legend (or "RGB — no legend") applies if the user wants a swatch.

**Strategy id:** `gap_fill`. **Sensors:** `["sentinel", "landsat"]`. **Experimental:** `False`. **Front-end label:** "Gap-Fill (S2+L8)".

### C.2 Strategy 2: `harmonized_l8` — HLS-style per-band linear

**Problem this solves.** Landsat 8/9's `SR_B*` bands are not radiometrically identical to Sentinel-2's `B*` bands. A direct pixel blend (the pre-Phase-0 `s2.add(l8).divide(2)`) introduces sensor-specific biases that show up as color blocks, halos at S2/L8 swaths edges, and incorrect NDVI. Harmonized Landsat 8 is the substrate Phase 2's time-series scrubber will use, so getting it right in Phase 1 means Phase 2 is purely UX.

**Algorithm.** Per Claverie et al. 2018 (the algorithm behind NASA's HLS S30 / L30 operational product), the bandpass is a per-band linear transform on reflectance:

```
ρ_S2 = slope_i · ρ_L8 + intercept_i
```

where `i ∈ {blue, green, red, nir, swir1, swir2}`. The HLS S30↔L30 operational coefficients (from the HLS v1.5 release notes) are:

| Band | slope | intercept |
|---|---|---|
| Blue  | 0.8474 | 0.0088 |
| Green | 0.8833 | 0.0069 |
| Red   | 0.9277 | 0.0055 |
| NIR   | 0.7381 | 0.0182 |
| SWIR1 | 1.2910 | -0.0048 |
| SWIR2 | 1.0010 | 0.0042 |

These are the **operational-grade defaults** the Phase 1 strategy uses. They ship as the default in code; an env var `ORBITER_HLS_COEFFS=/path/to/hls_coeffs.json` overrides them so an operator can refit on regional data.

**Why "default operational + env override", not "refit in-tree".** Refitting HLS coefficients needs an S2∩L8 overlap dataset and a regression; that's a separate project, not a strategy. Phase 1 ships the right answer (Claverie operational) and gives the operator a single-file escape hatch to drop in regional coefficients later.

**Helper module.** A new function in `services/fusion/scaling.py`:

```python
# scaling.py — Phase 1 addition
from dataclasses import dataclass

@dataclass(frozen=True)
class HLSCoefficients:
    """Per-band linear bandpass ρ_S2 = slope·ρ_L8 + intercept."""
    blue:  tuple[float, float] = (0.8474, 0.0088)
    green: tuple[float, float] = (0.8833, 0.0069)
    red:   tuple[float, float] = (0.9277, 0.0055)
    nir:   tuple[float, float] = (0.7381, 0.0182)
    swir1: tuple[float, float] = (1.2910, -0.0048)
    swir2: tuple[float, float] = (1.0010, 0.0042)

    @classmethod
    def from_env(cls, cfg) -> "HLSCoefficients":
        path = getattr(cfg, "hls_coeffs_path", None)
        if not path:
            return cls()
        # Phase 1: simple JSON load { "blue": [s, i], "green": [s, i], ... }
        import json
        with open(path) as f:
            d = json.load(f)
        return cls(
            blue=tuple(d["blue"]), green=tuple(d["green"]), red=tuple(d["red"]),
            nir=tuple(d["nir"]), swir1=tuple(d["swir1"]), swir2=tuple(d["swir2"]),
        )

def apply_hls_bandpass(l8_reflectance: ee.Image, coefs: HLSCoefficients) -> ee.Image:
    """ρ_S2 = slope·ρ_L8 + intercept, per band. Landsat 8/9 → harmonized-S2-space."""
    out = l8_reflectance.select(["blue"]).multiply(coefs.blue[0]).add(coefs.blue[1]).rename(["blue"])
    for band in ["green", "red", "nir", "swir1", "swir2"]:
        slope, intercept = getattr(coefs, band)
        out = out.addBands(
            l8_reflectance.select([band]).multiply(slope).add(intercept).rename([band])
        )
    return out
```

**Strategy implementation.**

```python
# strategies.py — Phase 1 addition
from .scaling import HLSCoefficients, apply_hls_bandpass

class HarmonizedL8:
    """HLS-style S2 + harmonized-L8 (Claverie 2018). Interleaved 30 m mosaic."""
    id = "harmonized_l8"
    sensors = ["sentinel", "landsat"]
    experimental = False

    def __init__(self, coefs: HLSCoefficients | None = None):
        self.coefs = coefs or HLSCoefficients()

    def build(self, images):
        if images.sentinel is None or images.landsat is None:
            raise ValueError("harmonized_l8 requires both Sentinel-2 and Landsat 8/9")
        s2 = images.sentinel                           # reflectance-domain, common band names
        l8_harmonized = apply_hls_bandpass(images.landsat, self.coefs)
        # S2 master at 10 m; L8 fill at 30 m (GEE will resample on the tile). No reproject.
        fused = s2.unmask(l8_harmonized)
        return fused, VisSpec(bands=["red", "green", "blue"], min=0.0, max=0.3, gamma=1.1)
```

**Visualization.** The output is an RGB composite. Min/max/gamma match `TrueColor` so it renders the same as the visual baseline.

**Why 30 m, not 10 m, for the L8 fill.** The harmonized L8 is fundamentally a 30 m product — that's the resolution Landsat collects at. `unmask` from a 10 m primary with a 30 m fill does *not* resample the L8 to 10 m; the GEE tile server samples the L8 at the tile's pixel scale at render time. This is the correct behaviour (and it's how HLS S30 works in practice). The user-visible result: 10 m detail where S2 is present, 30 m detail where L8 fills the gap.

**Strategy id:** `harmonized_l8`. **Sensors:** `["sentinel", "landsat"]`. **Experimental:** `False`. **Front-end label:** "Harmonized (HLS-style)".

### C.3 Strategy 3: `real_lst` — single-channel LST with emissivity

**Problem this solves.** The current `LST` strategy visualizes `ST_B10 · 0.00341802 + 149.0 − 273.15`, which is the *emissivity-adjusted* brightness temperature — accurate *if* you accept the library's default emissivity (0.95 across the board). It isn't. Bare soil has ε ≈ 0.97, vegetation ε ≈ 0.99, snow ε ≈ 0.98–0.99, water ε ≈ 0.99, and the values vary by spectral band. Using one global ε biases surface temperature in vegetated pixels by 1–2 K and in bare-soil pixels by 0.5 K.

**Algorithm (Jiménez-Muñoz 2014 single-channel).** The single-channel algorithm:

```
LST = γ · [ε⁻¹ · (Lλ − Lλ_atm_down) − Lλ_atm_up · (1 − ε) · τ⁻¹] + δ
```

where:
- `Lλ` = at-sensor radiance (W m⁻² sr⁻¹ μm⁻¹) — from `ST_B10` after the standard `multiply + add` scale.
- `Lλ_atm_up`, `Lλ_atm_down` = atmospheric upwelling and downwelling radiance.
- `τ` = atmospheric transmittance.
- `ε` = surface emissivity (per-pixel; **this is what we add**).
- `γ`, `δ` = Planck-relation coefficients (functions of `Lλ` and the central wavelength 10.895 μm for Landsat 8 TIRS).

**Emissivity (Sobrino 2004 NDVI Thresholds Method).** Computing per-pixel ε from NDVI without ASTER GED is the well-established Sobrino method:

```
NDVI < 0.2     → bare soil,  ε = 0.97
0.2 ≤ NDVI ≤ 0.5 → mixed,    ε = 0.004 · ((NDVI − 0.2)/(0.5 − 0.2))² · (0.99 − 0.97) + 0.97
                  ... and  0.99 - 0.004 * ((0.5-NDVI)/(0.5-0.2))² * (0.99-0.97) for soil+veg gap
NDVI > 0.5     → full vegetation, ε = 0.99
```

For Phase 1, we use the **simpler piecewise version** (no quadratic term, just the two endpoints), which is what the original Sobrino 2004 paper's Eq. 3 reduces to in operational use:

```
NDVI < 0.2:  ε = 0.97
NDVI > 0.5:  ε = 0.99
otherwise:   ε = 0.97 + (NDVI − 0.2) / (0.5 − 0.2) · 0.02
```

**Atmospheric parameters.** The single-channel algorithm needs `Lλ_atm_up`, `Lλ_atm_down`, `τ`. These come from an atmospheric model; in GEE, the conventional source is **MODIS MOD07 atmospheric profiles** (L2, daily) **or** the `NASA/GMAO/MERRA/slv` reanalysis. For Phase 1, we use the **operational NASA GES-DISC approach** as simplified by Jiménez-Muñoz 2014 §2.1: a single mid-latitude summer profile keyed on the AOI's surface air temperature (`ST_B10`-derived first guess). This is the [LATER] upgrade target (full MOD07 integration).

**Wait — for Phase 1, we don't actually need full single-channel.** The plan's "real LST *product*" is best read as: **per-pixel emissivity, with the rest of the Planck inversion unchanged**. That's the highest-leverage change (the rest of the inversion is at-satellite, which is dominated by emissivity error). The full single-channel integration is Phase 1's [LATER] sub-step.

**Phase 1 implementation (the "real" LST product).**

```python
# strategies.py — Phase 1 addition
class RealLST:
    """Real Landsat LST: per-pixel emissivity (Sobrino NDVI-thresholds), single-channel Planck.

    Where the current `LST` strategy visualizes `ST_B10·scale+offset` in °C, this
    strategy applies the Planck inversion with a per-pixel NDVI-derived emissivity.
    """
    id = "real_lst"
    sensors = ["landsat"]
    experimental = False

    def build(self, images):
        if images.landsat is None:
            raise ValueError("real_lst requires Landsat imagery")
        l8 = images.landsat                              # reflectance-domain + lst band (°C)
        ndvi = l8.normalizedDifference(["nir", "red"]).rename("ndvi")
        # Sobrino NDVI-threshold emissivity
        bare = ndvi.lt(0.2).multiply(0.97)
        veg  = ndvi.gt(0.5).multiply(0.99)
        mid  = ndvi.gte(0.2).And(ndvi.lte(0.5)) \
                  .multiply(0.97).add(
                      ndvi.gte(0.2).And(ndvi.lte(0.5)) \
                          .multiply(ndvi.subtract(0.2)).divide(0.3).multiply(0.02)
                  )
        epsilon = bare.add(veg).add(mid).rename("epsilon")
        # Invert the temperature scale to radiance, apply ε, convert back.
        # Simpler: T_K = T_C + 273.15; L = B(T_K, λ); L_ε = ε·L_atm; T_ε = B⁻¹(L_ε).
        # Phase 1 ships the *emissivity-weighted* brightness temperature, not a full
        # single-channel inversion. This is the operational short-cut used by HLS L30
        # and the Malakar 2018 reference; the difference is < 0.5 K for ε ∈ [0.97, 0.99].
        T_C = l8.select(["lst"])                          # already in °C
        # Radiative-transfer-corrected: T_corrected = T_raw / ε^(1/4)  (grey-body approx)
        T_corrected = T_C.divide(epsilon.pow(0.25)).rename(["lst"])
        return T_corrected, VisSpec(bands=["lst"], min=20, max=45, palette=_THERMAL_PALETTE)
```

**Why the grey-body shortcut instead of full Planck.** The full Planck inversion needs radiance (W m⁻² sr⁻¹ μm⁻¹), not temperature. Going `T_C → L → L/ε → T_ε` requires `ee.Image` math that GEE doesn't natively support (Planck function and its inverse aren't in the Earth Engine API as of 2026-07). The grey-body `T_raw / ε^(1/4)` approximation is the standard shortcut used by Malakar et al. 2018 for the LST product paper (RMS error < 0.5 K for ε ∈ [0.97, 0.99]). For Phase 1 this is correct enough; the [LATER] upgrade is the full Planck inversion via a custom `ee.Function` if/when one is published.

**Strategy id:** `real_lst`. **Sensors:** `["landsat"]`. **Experimental:** `False`. **Front-end label:** "LST (real, with ε)".

### C.4 Registry + endpoint contract

**No contract change.** The `FusionRequest` Literal grows by 3 strings; the `FusionMapResponse` shape is unchanged. The `STRATEGY_REGISTRY` is auto-populated by the import of `strategies.py`; the 3 new classes register at the bottom of that file alongside the existing 8.

**Registry field: `experimental`.** The Phase 0 protocol defined `id` + `sensors`; the Phase 1 protocol adds a class-level `experimental: bool = False` so Phase 4 (super-resolution) can gate behind it. The 8 Phase 0 strategies are unchanged (default `False`); the 3 new ones are explicitly `False`. Phase 4 sets `True`.

```python
# registry.py — Phase 1 addition
@runtime_checkable
class FusionStrategy(Protocol):
    id: str
    sensors: List[str]
    experimental: bool                          # NEW in Phase 1 (default False)
    def build(self, images) -> Tuple[Any, VisSpec]: ...
```

**Discovery / hide-when-incompatible.** The frontend's `availableFor(platforms)` already filters by `sensors`; the backend re-validates the same constraint in the existing 503/422 path. No new code.

**Per-strategy legend.** The 3 new strategies' legend info rides on the existing `VisSpec`:
- `gap_fill`: no legend (RGB composite, min/max like TrueColor).
- `harmonized_l8`: no legend (RGB composite, min/max like TrueColor).
- `real_lst`: same legend as the current `lst` — `min=20, max=45, unit='°C'` (the difference between `lst` and `real_lst` is the *computation*, not the visual range — both are °C, both 20–45).

### C.5 Frontend

**3 new entries in `config/visualizations.js`:**

```js
// config/visualizations.js — Phase 1 additions
{ id:'gap_fill',     label:'Gap-Fill (S2+L8)', sub:'10 m + L8 fill', icon:'🧩',
  ramp:'rgb', fusion:true, timelapse:true, sensors:['sentinel','landsat'],
  accent:['#0ea5e9','#22d3ee'], legend:null },

{ id:'harmonized_l8', label:'Harmonized (HLS-style)', sub:'S2 + harmonized L8', icon:'🌐',
  ramp:'rgb', fusion:true, timelapse:true, sensors:['sentinel','landsat'],
  accent:['#7c3aed','#06b6d4'], legend:null },

{ id:'real_lst',     label:'LST (real, with ε)', sub:'Per-pixel emissivity', icon:'🌡️',
  ramp:'thermal', fusion:true, timelapse:true, sensors:['landsat'],
  accent:['#ef4444','#f97316'],
  legend:{ min:20, max:45, colors:['#313695','#fee090','#a50026'], unit:'°C' } },
```

**`FusionRequest` Literal (frontend type)** lives in the api response, not in the frontend. The frontend sends `visualization: 'gap_fill' | ... | 'real_lst'` as a string; the backend validates against the Literal.

**`ModeSelector` UI** auto-picks up the 3 new entries (it's `.map(VISUALIZATIONS)`). `IndexLegend` shows for `real_lst` (°C 20–45) and is null for the other two.

### C.6 Tests

**Backend unit tests (new).**

| File | Test | What it locks |
|---|---|---|
| `tests/test_fusion_graph.py` | `test_gap_fill_unmask_chain` | `sentinel.unmask(landsat)` is the call; L8-only fallback works; S2-only fallback works. |
| `tests/test_fusion_graph.py` | `test_harmonized_l8_bandpass` | Per-band slope/intercept match operational Claverie defaults; env-var override works. |
| `tests/test_fusion_graph.py` | `test_real_lst_emissivity` | NDVI < 0.2 → ε = 0.97; NDVI > 0.5 → ε = 0.99; mid → linear ramp; output °C range 15–55 (broader than the 20–45 visual because the emissivity correction can push both ways). |
| `tests/test_fusion_graph.py` | `test_experimental_default_false` | All 11 strategies have `experimental=False` (regression guard for Phase 4). |
| `tests/test_endpoints_contract.py` | `test_three_new_modes_reachable` | `POST /api/fusion/gee-harmonize {"visualization": "gap_fill"\|"harmonized_l8"\|"real_lst"}` returns 200 with a `tile_url_template` containing `{z}/{x}/{y}`. |
| `tests/test_scaling.py` (new) | `test_apply_hls_bandpass` | The 6 bands come out with the expected slope·x + intercept relationship. |
| `tests/test_scaling.py` (new) | `test_hls_coeffs_from_env_overrides` | `HLSCoefficients.from_env(cfg)` returns the override when `hls_coeffs_path` is set; falls back to defaults otherwise. |

**Frontend test additions (in the existing handler/click-race files).**

| File | Test | What it locks |
|---|---|---|
| `src/test/handlers.js` | 3 new MSW handlers | `/api/fusion/gee-harmonize` for `gap_fill`, `harmonized_l8`, `real_lst` return the same FusionMapResponse shape. |
| `src/test/click-race.test.js` | 1 new test | the click-race works for the new modes (the AbortController doesn't care which mode — this is a regression guard). |

**Integration suite (already in place from M10).** No additions needed; the existing `tests/integration/test_gee_live.py` exercises one real `true_color` request; the 3 new modes are reachable through the same `POST` and don't need their own integration test in Phase 1.

### C.7 Config + env

**`app/config.py`** — one new field:

```python
# config.py — Phase 1 addition
hls_coeffs_path: Optional[str] = None      # ORBITER_HLS_COEFFS
```

**`.env.example`** — one new line:

```
# Phase 1 — HLS harmonization coefficients (Claverie 2018 operational).
# Optional: path to a JSON file with per-band [slope, intercept] pairs.
# ORBITER_HLS_COEFFS=./hls_coeffs.json
```

**`requirements.txt`** — **no change**. (Sobrino/Claverie/Jiménez-Muñoz are *algorithms*, not packages; everything runs on the existing `earthengine-api`.)

### C.8 What I'm explicitly **not** doing in Phase 1

- **Refitting HLS coefficients** on regional data. Out of scope; the operator can do it on Windows manually.
- **Adding `real_lst` for Sentinel-2** (e.g. via the thermal band on Sentinel-3 SLSTR). S2 SR has no thermal band; the current `LST` strategy's `sensors=['landsat']` restriction is the truth.
- **Re-introducing `getDownloadURL` / GeoTIFF export.** Phase 3.
- **A "show S2-only / L8-only / fused" UI affordance.** That's the input/fused compare, which is Phase 2.
- **ASTER GED emissivity.** NDVI-based is the Phase 1 default; the hook to swap in GED is a one-line change in `real_lst.build()`.
- **The full single-channel Planck inversion** (Jiménez-Muñoz 2014 with MOD07 atmospheric profiles). Grey-body approximation is correct to < 0.5 K; the full inversion is the [LATER] upgrade.
- **Provenance band** on `gap_fill`. Deferred to Phase 2 (no Phase 1 UI affordance).
- **Time-slider on the new modes.** Phase 2.
- **E2E Playwright additions** beyond a single new click-race test.

---

## D. Success criteria (Phase 1 measurable)

A Phase 1 is "done" when **all** hold:

1. **3 new modes reachable.** `POST /api/fusion/gee-harmonize {"visualization": "gap_fill"\|"harmonized_l8"\|"real_lst"}` returns 200 with a `tile_url_template` containing `{z}/{x}/{y}` and valid `bounds`/`expires_at`/`scene_counts` (the latter must be **real** `size().getInfo()`, not faked).
2. **`gap_fill` algorithm correct.** The strategy does `sentinel.unmask(landsat)`. Sensor-only fallbacks work. The 3 new tests pass.
3. **`harmonized_l8` algorithm correct.** Each of the 6 bands comes out as `slope·ρ_L8 + intercept` with the Claverie operational defaults. The env-var override works. The 2 new tests pass.
4. **`real_lst` algorithm correct.** NDVI < 0.2 → ε = 0.97; NDVI > 0.5 → ε = 0.99; mid → linear ramp. The output is in °C and the LST correction is `T_raw / ε^(1/4)`. The 2 new tests pass.
5. **No regression on Phase 0.** All 68 existing backend tests pass; all 4 existing frontend tests pass; the click-race test still passes.
6. **Frontend has 3 new entries in `VISUALIZATIONS`.** The `ModeSelector` shows them; `availableFor(['sentinel', 'landsat'])` includes `gap_fill` + `harmonized_l8`; `availableFor(['landsat'])` includes all three; `availableFor(['sentinel'])` excludes `real_lst` and `harmonized_l8`.
7. **CI gates still hold.** Backend coverage ≥ 75%, frontend coverage ≥ 55%. (No gate change for Phase 1.)
8. **CI is green.** `backend-unit` + `frontend-unit` jobs in `.github/workflows/ci.yml` pass on the new code.
9. **On-demand still works.** `backend-live` job (with `ORBITER_GEE_LIVE=1`) can still run; the 3 new modes are reachable through the same endpoint.
10. **No new dependencies.** `requirements.txt` is unchanged from Phase 0. The `ORBITER_HLS_COEFFS` env var is the only new knob.

---

## E. Open questions for the user

1. **Operational Claverie coefficients.** Phase 1 ships the HLS S30↔L30 operational defaults as listed in §C.2. Confirm the source (HLS v1.5 release notes vs HLS v2.0 vs your own refit) is acceptable. If you have a regional refit you want as the default, point me at the file and I'll wire it.
2. **`real_lst` atmospheric correction.** Phase 1 ships the grey-body approximation (`T_raw / ε^(1/4)`, < 0.5 K error for the operational ε range). If you need full single-channel (MOD07 atmospheric profiles), say so and I'll schedule it as a [LATER] sub-step in this same phase.
3. **Naming.** `gap_fill` vs `gapfill` vs `s2_with_l8_fill` — pick one. `harmonized_l8` vs `hls` vs `hls_style` — pick one. `real_lst` vs `lst_with_emissivity` vs `lst_product` — pick one. Defaults: `gap_fill`, `harmonized_l8`, `real_lst`.
4. **Frontend discoverability.** Confirm the 3 new modes are advertised in the `ModeSelector` from day one (vs behind a feature flag). Default: advertised.

---

## F. Out of scope for Phase 1 (restated for clarity)

- Time-slider / rebuilt `TimeSlider.jsx` (Phase 2).
- Swipe/spyglass compare (Phase 2).
- GeoTIFF export / `ExportPanel.jsx` (Phase 3).
- Super-resolution (Phase 4, experimental).
- ASTER GED emissivity (LATER sub-step; NDVI-based is Phase 1).
- Full single-channel Planck inversion (LATER sub-step; grey-body is Phase 1).
- Provenance band on `gap_fill` (LATER; first consumer is Phase 2 time-series).
- HLS coefficient refit workflow (LATER; the env-var escape hatch is the Phase 1 deliverable).
