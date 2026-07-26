# Orbiter Fusion — Phase 0 (Foundation) Design

**Date:** 2026-07-23 · **Status:** Draft for review · **Parent:** [roadmap](./2026-07-23-orbiter-fusion-roadmap.md)

**Summary.** Phase 0 turns the current prototype — which pixel-averages Sentinel-2 and Landsat (`s2.add(l8).divide(2)`), downloads a PNG server-side on a 90 s timeout, authenticates to a hardcoded GEE project at import time, and ships zero tests — into a *correct, deployable, tested* skeleton that renders **real GEE XYZ tiles** via `image.getMapId(vis)`. It does **not** build the four fusion algorithms yet; instead it lays a `STRATEGY_REGISTRY` seam they plug into, fixes radiometric scaling / cloud-masking / index correctness for the honest single-sensor views, replaces import-time auth with a config-driven lifespan resolver + honest `/health`, rewrites the React frontend around a reducer store with real loading/empty/error UX and request cancellation, purges ~570 MB of committed venvs plus dead code, and stands up backend (pytest, `ee` mocked) + frontend (Vitest/RTL/MSW) suites in CI. Multi-sensor "fusion" modes that are today naive averages or placeholders are **hidden/demoted**, not rebuilt. Every `file:line` anchor below is verified against the live tree.

Legend: **[P0]** = build now (Foundation). **[LATER]** = Phase 1–4 spec, sketched only.

---

## A. Overview & locked decisions

**What Orbiter Fusion is:** a multi-satellite data-fusion web app — Sentinel-2 (10 m) + Landsat 8/9 (30 m) — FastAPI + Google Earth Engine backend, React 18 + Vite + raw Leaflet frontend.

**Locked decisions (not relitigated):**
- Deliver **all four** fusion capabilities eventually: (1) cloud-free gap-fill, (2) HLS-style harmonized time series, (3) spectral extension / real LST, (4) sharper-than-10 m — capability 4 is ML super-resolution only, sequenced **last**, experimental, shipped with an explicit hallucination caveat.
- **Deployable web service:** config-driven, concurrency-safe, no hardcoded hosts, real error/loading UX, tests.
- **Stay on GEE.**
- **Map display = GEE tile layer.** Backend mints `image.getMapId(vis)` → XYZ URL template; frontend `L.tileLayer`. **No server-side PNG download.** mapid tokens expire → TTL cache + refetch on tile 4xx.
- Phase 0 is designed in detail now; Phases 1–4 are later specs.

---

## B. Roadmap (one line each)

| Phase | Deliverable |
|---|---|
| **Phase 0 — Foundation** | getMapId tile pivot, config-driven GEE auth, bounded+masked composites, strategy registry, correct indices, honest errors/health, dead-code purge, real UX (no `alert()`), request cancellation, tests + CI, runnable on Linux/Windows/headless. |
| **Phase 1 — Real fusion I** | Cloud-free **gap-fill** (S2 master, Landsat `unmask` fill) + **HLS-style radiometric harmonization** (per-band linear) + real Landsat **LST** product. Replaces `add/divide(2)`. |
| **Phase 2 — Harmonized time series** | Interleaved S2 + harmonized-L8 on a common date axis; real time-series scrubber (rebuilt `TimeSlider`); swipe/spyglass compare; timelapse re-plumbed through the registry. |
| **Phase 3 — Spectral extension + export** | Broader spectral products; GeoTIFF/PNG export (`ExportPanel` + `create_dataset` flow) via async GEE `getDownloadURL`; Dataset Mode UI returns. |
| **Phase 4 — Super-resolution (experimental)** | GEE patch export → PyTorch SR model server → restitch → GEE ingest → tiles; UI "AI-enhanced, may hallucinate" badge + fidelity metric; `experimental=True` gate. |

---

## C. Phase 0 — Detailed design

### C.0 The architectural pivot everything hangs off

Today the GEE service builds an `ee.Image`, then **downloads a PNG server-side and re-serves it**:
- `getThumbURL(...)` at `gee_fusion_service.py:989`, then a blocking `httpx.Client(timeout=90.0)` download at `:1005-1012` → returns `imageUrl: "/static/fusion/{id}.png"` (`:1026`). This is the 90-second hang.
- `getDownloadURL` + `urllib.request.urlretrieve` GeoTIFF path at `:923-935` (also blocking, on the request thread).
- A **second, entirely dead** numpy pipeline (`fetch_as_array :359`, `sampleRectangle().getInfo() :415-418`, eager `reproject(crs='EPSG:3857') :410`, `fuse_sensors :447`, `save_for_web :521`) that nothing in `create_harmonized_fusion` calls — it drags in numpy/scipy/PIL for code that never runs.

**[P0] pivot:** the fusion builder returns an **`ee.Image` + vis params**; a thin layer calls `image.getMapId(vis)` and returns an **XYZ tile URL template**. Leaflet streams tiles directly from GEE's CDN. No server raster ever touches disk.

```python
# [P0] Replaces the entire getThumbURL/download block (gee_fusion_service.py:959–1031)
def mint_mapid(image: ee.Image, vis: dict, cfg) -> dict:
    m = image.getMapId(vis)                       # one lightweight GEE metadata call
    return {
        "tile_url_template": m["tile_fetcher"].url_format,   # https://earthengine.../{z}/{x}/{y}
        "mapid": m["mapid"],
        "expires_at": int(time.time() + cfg.mapid_ttl_seconds),
    }
```

Ripple effects (drive the rest of the design): the numpy/scipy/PIL array path becomes deletable (§C.5.6); index math moves server-side into `ee` (§C.2); GeoTIFF export becomes **[LATER]** and must be async-only (never `urlretrieve` on the request thread).

---

### C.1 Backend

#### C.1.1 Typed config via `pydantic-settings` **[P0]**

Replace scattered `os.environ[...]` writes (`main.py:16-17`) and the hardcoded project (`gee_fusion_service.py:100`) with one typed settings object loaded once.

```python
# app/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ORBITER_", env_file=".env", extra="ignore")
    # GEE auth
    gee_project: str = Field(..., description="was hardcoded compact-arc-482620-r8")
    gee_service_account_file: str | None = None
    gee_service_account_json: str | None = None       # raw JSON for secret managers
    gee_high_volume: bool = True
    # server / CORS
    cors_origins: list[str] = ["http://localhost:5173"]
    # fusion limits (re-introduce the bounds :180/:246 dropped)
    max_scenes_per_composite: int = 25
    default_cloud_cover: float = 20.0
    # mapid cache
    mapid_ttl_seconds: int = 21600                    # 6h — see §C.1.5 / F.3
    ee_threadpool_workers: int = 8

@lru_cache
def get_settings() -> Settings: return Settings()
```

`.env.example` ships with `ORBITER_GEE_PROJECT=`, `ORBITER_GEE_SERVICE_ACCOUNT_FILE=`, `ORBITER_CORS_ORIGINS=[...]`, `ORBITER_MAPID_TTL_SECONDS=21600`, `ORBITER_MAX_SCENES_PER_COMPOSITE=25`.

**Canonical env names: `ORBITER_`-prefixed** (`ORBITER_GEE_PROJECT`, `ORBITER_GEE_SERVICE_ACCOUNT_FILE`) — a single prefix keeps app config namespaced and matches `pydantic-settings`' `env_prefix`. `GOOGLE_APPLICATION_CREDENTIALS` stays as-is where it's a Google SDK convention, but the service-account path is preferentially read from `ORBITER_GEE_SERVICE_ACCOUNT_FILE`.

**Delete `main.py:16-17`** (`GDAL_HTTP_UNSAFESSL=YES` + blanked `CURL_CA_BUNDLE`): they globally disable SSL verification and existed only for the rio-tiler/COG path being deleted (§C.1.6). Since that path is deleted in P0, they go entirely rather than being gated behind `os.name=='nt'`.

#### C.1.2 GEE auth resolver + lifespan init + honest `/health` **[P0]**

**Problem:** `_try_auto_init()` (`gee_fusion_service.py:96-107`) runs at **import** (via `__init__` `:94` ← `main.py:34`), hardcodes the project (`:100`), and swallows failure into a `logger.warning`. `/health` (`main.py:458-469`) never checks GEE — it reports `"healthy"` unconditionally.

An explicit resolver (pure priority logic, no network — unit-testable), called from lifespan:

```python
# app/services/gee_auth.py
def init_earth_engine(cfg) -> None:
    opt_url = "https://earthengine-highvolume.googleapis.com" if cfg.gee_high_volume else None
    if cfg.gee_service_account_json or cfg.gee_service_account_file:
        # 1. Service account (deployable, non-interactive)
        ... ee.Initialize(ee.ServiceAccountCredentials(sa_email, key_path),
                          project=cfg.gee_project, opt_url=opt_url)
    else:
        # 2. ADC / user creds (local dev after `earthengine authenticate`)
        ee.Initialize(project=cfg.gee_project, opt_url=opt_url)
    # No silent default; missing project => pydantic already raised at Settings load.
```

```python
@asynccontextmanager
async def lifespan(app: FastAPI):        # replaces the no-op lifespan main.py:63-68
    cfg = get_settings()
    app.state.settings, app.state.gee_ready, app.state.gee_error = cfg, False, None
    try:
        init_earth_engine(cfg); app.state.gee_ready = True
    except Exception as e:
        app.state.gee_error = str(e)     # do NOT crash; /health reports degraded
        logger.error("GEE init failed: %s", e)
    app.state.ee_pool = ThreadPoolExecutor(max_workers=cfg.ee_threadpool_workers)
    yield
    app.state.ee_pool.shutdown(wait=False)
```

`GEEFusionService` **stops owning auth**: delete `_try_auto_init` (`:96`) + its `__init__` call (`:94`), delete the interactive-auth fallbacks (`:124-147`), delete `self._executor` (`:91`, only fed the dead parallel-download path). Service assumes `ee` is initialized.

**Honest `/health`** (rewrite `main.py:458-469`): return `503`/`"degraded"` when `gee_ready` is false, echo `project` + `error`, keep the existing STAC-client checks. Delete `/api/fusion/gee/status` (`main.py:396-424`) — `/health` now covers it. A `/health/live` vs `/health/ready` split is **[LATER]** (k8s probes).

> **Testability note:** this refactor is a *prerequisite* — today `import main` authenticates to GEE, so no test can run without real creds or a mock installed before import. The resolver-as-pure-function + lifespan-only init is what makes the whole suite possible.

#### C.1.3 The core endpoint contract — `POST /api/fusion/gee-harmonize` **[P0]**

Replaces the PNG flow with a getMapId mint. Response contract (the shape the frontend depends on):

```python
class SceneCounts(BaseModel): sentinel: int; landsat: int
class FusionMapResponse(BaseModel):
    fusion_id: str
    tile_url_template: str        # ".../tiles/{z}/{x}/{y}"
    bounds: list[list[float]]     # Leaflet [[S,W],[N,E]]
    expires_at: int               # epoch seconds; TTL for refetch
    scene_counts: SceneCounts
    visualization: str
    max_native_zoom: int = 14     # informs Leaflet maxNativeZoom (§C.3.2); GEE upsamples above
```

The handler currently reads an untyped dict via `await request.json()` (`main.py:248`) with manual `.get()` validation (`:250-262`). Replace with a Pydantic request model:

```python
class FusionRequest(BaseModel):
    bounds: conlist(float, min_length=4, max_length=4)        # [W,S,E,N]
    start_date: date
    end_date: date
    cloud_cover: float = Field(20.0, ge=0, le=100)
    visualization: Literal["true_color","ndvi","ndwi","ndbi",
                           "false_color_nir","false_color_swir","sci","lst"] = "true_color"
    platforms: list[Literal["sentinel","landsat"]] = ["sentinel","landsat"]
    geojson: dict | None = None

    @model_validator(mode="after")
    def _dates_ordered(self):
        if self.end_date < self.start_date: raise ValueError("end_date before start_date")
        return self
```

> Note the mode `id` list uses `ndwi` as **true McFeeters water** (Green/NIR) — see §C.2.5 / F.1 (resolved: option a). `create_dataset`/`destination_folder`/`window_size` are **deliberately absent** from the P0 model — Dataset Mode is deferred (§C.3.1a, Phase 3).

Handler: gee-ready guard → build image + real scene counts in the threadpool → 404 if both counts 0 → `mint_mapid` → return `FusionMapResponse`. **Real `scene_counts`** replaces the fake stats: reintroduce **one** `collection.size().getInfo()` per platform inside the builder (counts are commented out today at `:184,:249`), run in the pool.

**Response field style: snake_case + epoch** (`tile_url_template`, `scene_counts`, `expires_at` as epoch seconds) — matches Python style; epoch is trivial for the frontend's `Date.now() > expires_at*1000` check. Frontend maps these into its camelCase layer object internally.

**Stale schema cleanup [P0]:** the new `FusionRequest`/`FusionMapResponse`/`SceneCounts` **replace** `FusionProcessingRequest`/`FusionProcessingResponse` (defined `models/schemas.py:67,75`) and the old `HealthResponse` (`schemas.py:60`). Delete those three from `schemas.py` and **fix the orphaned imports** at `main.py:19-27` (which currently import `FusionProcessingRequest`, `FusionProcessingResponse`, `HealthResponse`) — otherwise the app fails to import after the `/api/fusion/process` deletion.

**Kept + typed endpoints (UI touches exactly four — verified by grep over `frontend/src`):**
- `POST /api/search/all` (`main.py:580`) — run the two STAC searches **concurrently** in the pool (currently sequential `:585`→`:594`); drop the `SCENE_STORE` side-effect (`:606-609`) once `/api/fusion/process` is deleted.
- `POST /api/fusion/timelapse` (`main.py:309`) — kept, **but re-plumbed through the strategy registry in P0** so it inherits the same LST/offset/masking fixes (§C.2.7). GIF stays a URL-to-artifact response (legitimately different from tiles).
- `POST /api/fusion/gee-window` (`main.py:345`) — cheap AOI-bounds utility, no GEE compute; keep + tidy.
- `POST /api/datasets/download-zip` (`main.py:1178`) — see §C.3.1a for its Dataset-Mode-tied fate.

#### C.1.4 Structured errors **[P0]**

Replace the ~12 `except Exception as e: raise HTTPException(500, str(e))` blocks (`main.py:171-175, 303-307, 336-342, 757-761`, …) with one exception + one handler:

| Condition | Code | HTTP |
|---|---|---|
| GEE not initialized | `gee_unavailable` | 503 |
| No scenes for AOI/date/cloud | `no_imagery` | 404 |
| Bad bounds / dates / AOI too large | `invalid_request` | 400 / 422 (Pydantic) |
| `ee.EEException` (GEE rejected graph) | `gee_compute_error` | 502 |
| Unexpected | `internal_error` | 500 |

`ee.EEException` → **502** (upstream failure), distinguishing "GEE rejected our graph" from "our code threw."

#### C.1.5 mapid caching with TTL + refresh **[P0]**

Two distinct caches, not conflated:
1. **Fusion-image cache** — keyed by `md5(bounds,dates,cloud,vis,platforms,geojson)` (pattern already at `gee_fusion_service.py:844-851`). Cache the built `ee.Image` handle + scene counts + bounds, **not** a PNG path (its current v4 cache stores the download result — obsolete after the pivot). Use `cachetools.TTLCache` (bounded `maxsize`, auto-eviction) instead of the hand-rolled `dict + time.time()`.
2. **mapid-token cache** — same key, stores `{tile_url, expires_at}`, TTL = `mapid_ttl_seconds`.

**TTL sizing:** GEE mapids live for hours-to-days, so the P0 default is **`21600` s (6 h)** — comfortably inside the real token lifetime, avoiding needless re-mints. The **primary refresh mechanism in P0 is reactive** (refetch on tile 4xx, §C.3.4); the TTL is a coarse backstop, and a proactive pre-expiry timer is **[LATER]**.

**Refresh-on-expiry (two-sided contract):** add cheap `GET /api/fusion/{fusion_id}/refresh-mapid` **[P0]** that re-mints a token for an already-built (still-cached) image — no recompute. Frontend calls it on Leaflet `tileerror` (§C.3.4).

#### C.1.6 Delete-vs-keep plan **[P0]** (anchored to "UI touches only 4 endpoints")

**DELETE:**

| Target | file:line | Why |
|---|---|---|
| Duplicate/broken fusion-tile route (`get_fusion_tile` #2, uses unimported `Reader`/`Resampling`) | `main.py:764-873` | Same path as `:178`; **shadowed by FastAPI** (first registration wins — empirically confirmed); NameError; UI-dead |
| First fusion-tile route | `main.py:178-207` | Serves `fusion_service.get_fusion_tile`; UI-dead — **with getMapId there is no backend tile proxy at all** |
| Legacy `/api/fusion/harmonize` (STAC) | `main.py:110-175` | Superseded; UI-dead |
| `/api/fusion/{id}/preview` | `main.py:876-905` | Depends on deleted tile route |
| `/api/fusion/process` (fake stats `mean_ndvi:0.45`) | `main.py:629-761` | UI-dead; fake |
| `/api/fusion/gee/status` | `main.py:396-424` | Redundant with honest `/health` |
| `/api/tiles/*`, `/api/analysis/*`, `/api/export/*` | `main.py:910-1118` | UI-dead |
| Titiler / local COG tiler mount | `main.py:38-40, 96-99` | UI renders GEE tiles, never local COGs |
| `services/{fusion_service,tile_service,cache_service,analysis}.py` | whole files | `cache_service` never imported; the other three only fed deleted routes (`analysis_service` imported `main.py:32`, used only in `/api/fusion/process :828` + dead `:764` route — **unconditional delete**) |
| numpy path in GEE service | `fetch_as_array :359-445`, `resample_to_target :316`, `fuse_sensors :447`, `normalize_to_8bit :484`, `save_for_web :521`, `compute_ndvi/ndwi :1227,:1250` | Unreachable from getMapId flow |
| Second CORS middleware | `main.py:431-437` | Duplicate of `:88-94` |
| SSL-disabling env writes | `main.py:16-17` | Only the deleted COG path needed them |
| Committed `venv/`, `venv_new/`, `a1/` (~570 MB) + ~285 committed PNGs + `static/fusion/*` | dirs/files | Not produced once server-download is gone |
| `backend/debug_*.py`, `check_url_readability.py`, `debug_mosaic_test.py` scratch scripts | files | Not part of the app; also the last remaining `rio_tiler` importers (§C.5.6) |

**KEEP:** `gee_fusion_service.py` (stripped), `sentinel.py`/`landsat.py` (back `/api/search/all`), `bhuvan.py` (see §C.3.1b for WMS resolution), the 4 UI endpoints + `gee-window`.

**Dataset endpoints — explicit fate (see §C.3.1a):** `datasets/list` (`:1126`), `datasets/download/{filename}` (`:1157`), `datasets/download-zip` (`:1178`) are **kept but dormant** in P0 (their traversal guards hardened), because Dataset Mode *generation* moves to Phase 3. They will list an empty folder until Phase 3 rewires `create_dataset` — this is acceptable and documented, not a bug. Rationale: deleting then re-adding them across a phase boundary churns more than leaving hardened, unused-but-safe read endpoints.

> **`TypingIntro`** is *imported* (`App.jsx:4`) but never rendered (`showIntro` is `false`, `:9`). Delete the import, the dead state, and the file in P0.

#### C.1.7 Concurrency + CORS **[P0]**

**Threadpool for blocking `ee`/STAC calls.** Handlers are `async def` but call sync service methods directly (`main.py:270,:315,:488`) — under concurrency this serializes the whole server. Add:

```python
async def run_in_pool(pool, fn, *a):
    return await asyncio.get_running_loop().run_in_executor(pool, fn, *a)
```

Use `app.state.ee_pool` for every `getInfo()`, `getMapId()`, `size().getInfo()`, and both STAC searches.

**CORS once, from env** (replace both `main.py:88-94` and `:431-437`):
```python
app.add_middleware(CORSMiddleware, allow_origins=cfg.cors_origins,   # NOT ["*"] with credentials
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
```
The current `allow_origins=["*"]` **with** `allow_credentials=True` (verified at `:88-94` and duplicated at `:431-437`, the second literally mixing `"*"` with named origins) is spec-invalid (browsers reject it) and insecure.

#### C.1.8 Package layout **[P0]**

```
backend/app/
├── main.py            # FastAPI() + lifespan + middleware + router includes (~60 LOC)
├── config.py          # Settings (§C.1.1)
├── routers/           # fusion.py, search.py, datasets.py, health.py
├── services/          # gee_auth.py, gee_fusion_service.py (stripped), sentinel.py, landsat.py, bhuvan.py
├── models/schemas.py  # FusionRequest, FusionMapResponse, SceneCounts, TimelapseRequest, errors
└── core/              # errors.py (ServiceError+handler), mapid_cache.py (TTLCache)
```

---

### C.2 Fusion logic

#### C.2.1 Bounded, cloud-sorted, per-pixel-masked composite **[P0]**

**Problem:** `.limit(25)` was removed at `:180` (S2) / `:246` (L8) → unbounded composites; "cloud handling" is only a scene-level metadata filter (`CLOUDY_PIXEL_PERCENTAGE < cloud_cover :178`, `CLOUD_COVER :235,:242`) — a 19%-cloud scene still dumps all its cloudy pixels into the median; **no per-pixel mask at all**. Additionally, `get_sentinel_image` narrows to `['B2'…'B12']` at `:202` (verified) — **`SCL` and `QA60` are NOT in that list**, so a mask that does `img.select('SCL')` on the already-narrowed image throws "band SCL not found."

**Fix — mask at the per-scene level (bands still present), then narrow, then bound+composite:**

```python
# Cloud Score+ is the P0 DEFAULT for Sentinel-2. QA60 is deprecated/empty for
# S2_SR_HARMONIZED after ~2022 (the test AOI is Q1-2024), so QA60 masking would
# silently no-op. Cloud Score+ (cs_cdf) is populated for all recent scenes.
CSPLUS = ee.ImageCollection('GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED')

def mask_s2(img):                                              # runs BEFORE any .select() narrowing
    scl = img.select('SCL')                                   # drop 0,1,3,8,9,10 (cloud/shadow/snow/cirrus)
    scl_bad = scl.eq(0).Or(scl.eq(1)).Or(scl.eq(3)).Or(scl.eq(8)).Or(scl.eq(9)).Or(scl.eq(10))
    cs = img.select('cs_cdf').gte(0.60)                        # Cloud Score+ clear-probability
    return img.updateMask(scl_bad.Not().And(cs))

def mask_landsat(img):
    qa = img.select('QA_PIXEL')                                # C2 bits 1 dilated,2 cirrus,3 cloud,4 shadow
    clear = (qa.bitwiseAnd(1<<1).eq(0).And(qa.bitwiseAnd(1<<2).eq(0))
               .And(qa.bitwiseAnd(1<<3).eq(0)).And(qa.bitwiseAnd(1<<4).eq(0)))
    return img.updateMask(clear)

REFLECT_S2 = ['B2','B3','B4','B5','B6','B7','B8','B8A','B11','B12']

s2 = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
        .filterBounds(geom).filterDate(start, end)
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', cloud_cover))
        .linkCollection(CSPLUS, ['cs_cdf'])                    # attach cs_cdf before masking
        .sort('CLOUDY_PIXEL_PERCENTAGE').limit(cfg.max_scenes_per_composite)   # bounded again
        .map(mask_s2)
        .select(REFLECT_S2))                                   # narrow AFTER masking → SensorImages input
# Landsat: l8.merge(l9) → filter CLOUD_COVER → sort → limit → map(mask_landsat) → select(SR_*, ST_B10)
```

**Ordering contract (fixes the "SCL not in band list" trap):** mask on the *full* per-scene band set (SCL/QA60/cs_cdf/QA_PIXEL all present), **then** `.select(reflectance bands + ST_B10)`, **then** composite. The final narrowed set is exactly what §C.2.3's `SensorImages` consumes. `.limit()` **after** `.sort()` keeps the cleanest N; masking-then-`.median()` composites only clear pixels (masking beats scene filtering — the real cloud fix). Keep `mosaic/mean/median` selectable via the existing `composite_method` param (`:158`).

> QA60 is intentionally dropped as a co-mask: it is dead for the target 2023+ dates. SCL + Cloud Score+ carry the S2 mask. (QA60 bit-ops remain a documented fallback only for pre-2022 AOIs, not wired by default.)

#### C.2.2 Drop eager reproject + `sampleRectangle().getInfo()` **[P0]**

Delete `fetch_as_array` (`:359-445`): the eager `reproject(crs='EPSG:3857', scale=scale)` (`:410`) forces GEE to materialize pixels (the "Reprojection output too large" failures the code already fights at `:696`), and `sampleRectangle().getInfo()` (`:415-418`) is a synchronous full-array pull. With getMapId, GEE reprojects lazily per tile — no explicit reproject anywhere. The one legit eager call, `collection.size().getInfo()` in `generate_timelapse` (`:1177`), stays but is wrapped so failure doesn't 500.

#### C.2.3 Fusion-STRATEGY registry **[P0]** — foundation for all later phases

`fuse_collections_server_side` (`:612-818`) is a 200-line `if/elif` ladder mixing three orthogonal concerns (sensor scaling, per-viz band selection, fusion algorithm). Replace with a registry so modes/algorithms plug in without editing a ladder.

```python
@dataclass
class SensorImages:
    s2: Optional[ee.Image]          # pre-scaled to reflectance 0..1
    landsat: Optional[ee.Image]     # pre-scaled to reflectance 0..1 (offset applied); ST_B10 pre-converted to °C

@dataclass
class VisSpec:
    bands: Optional[list]; min: float; max: float; gamma: float = 1.0; palette: Optional[list] = None

class FusionStrategy(Protocol):
    id: str; label: str
    sensors: list                   # ['landsat'] for LST → API won't offer it for S2-only AOIs
    experimental: bool              # gates the super-resolution track
    def build(self, imgs: SensorImages, ctx) -> tuple[ee.Image, VisSpec]: ...

STRATEGY_REGISTRY: dict[str, FusionStrategy] = {}
```

- **Scaling centralized once** (not repeated at `:634,:662,:695,:1096,:1127`): a helper produces reflectance-domain `SensorImages` before any strategy runs — kills the scattered `multiply(0.0001)` / `multiply(0.0000275).add(-0.2)`, and **applies the LST scale+offset+°C conversion in exactly one place** (§C.2.4).
- **`sensors`** lets the API advertise only valid modes per platform selection (fixes LST-on-S2 at the API layer).
- **`experimental`** gates super-resolution behind an explicit opt-in.
- P0 strategies are the current single-sensor views re-expressed as classes (`TrueColor, NDVI, NDWI, NDBI, FalseColorNIR, FalseColorSWIR, SCI, LST`). Real fusion strategies (gap-fill, harmonized, SR) register in later phases without touching the ladder.
- `/api/fusion/gee-harmonize` and `/api/fusion/timelapse` both become: resolve strategy by `id` → `build()` → for tiles `mint_mapid(vis)`; for timelapse `visualize(**vis)` per frame.

#### C.2.4 LST correctness + units **[P0]**

- **LST-on-Sentinel is fabricated:** `s2.select('B10')` (`:686,:812`, and timelapse `:1121`) — **S2 SR has no B10** (B10 is L1C cirrus). Remove `lst` from every Sentinel-only / fused / timelapse Sentinel branch; register LST with `sensors=['landsat']`.
- **Landsat LST scaling + Kelvin→°C:** current code visualizes **raw DN** with `min=273,max=323` (verified `:656,:815,:1155`), but raw `ST_B10` DN is ~44000 — the palette range is meaningless. The scaling helper (§C.2.3) applies `ST_B10 · 0.00341802 + 149.0` → Kelvin, then **subtracts 273.15 → °C**. `ST_B10` is already emissivity-adjusted; do **not** re-apply a Planck inversion.
- **Single unit contract (fixes the K-vs-°C mismatch):** `SensorImages.landsat`'s thermal band is in **°C**, and the LST `VisSpec` uses `min=20, max=45` **°C** — matching the frontend legend `{min:20, max:45, unit:'°C'}` in §C.3.5 exactly. Backend output and legend are both °C; no per-client conversion.
- **`combined`** is a literal placeholder (`:791-794`, "Placeholder for complex logic" returning S2 true-color) — removed from the advertised list until real gap-fill/harmonization back it.
- **`true_color_swir`** (`:772-789`) naive-averages TC+SWIR — dropped from P0 (not one of the four locked capabilities). `false_color_swir` (a single-sensor SWIR composite) is kept.

#### C.2.5 Index correctness per sensor **[P0]**

**The Landsat `-0.2` offset trap.** Normalized-difference indices are invariant to a *multiplicative* scale but **not to an additive offset**. Landsat C2 L2 SR = `DN·0.0000275 − 0.2`. Computing NDVI on **raw** `SR_B5/SR_B4` (`:639,:734,:1131`) is **wrong** — the comment at `:1131` ("using raw bands … is ok") is incorrect. (S2 NDVI on raw `B8/B4` *is* fine — S2 scaling is purely multiplicative, so it cancels.) **Fix:** compute all indices on the reflectance image after scale+offset — automatic once `SensorImages` are pre-scaled.

**NDWI → true McFeeters water (F1 resolution: option a).** Code labeled "NDWI" actually uses NIR/SWIR (`B8/B11 :683`; `SR_B5/SR_B6 :652,:806`) = Gao **moisture** (NDMI), not water. P0 **changes the `ndwi` formula to true McFeeters water = (Green−NIR)/(Green+NIR)** — S2 `normalizedDifference(['B3','B8'])`, Landsat `normalizedDifference(['SR_B3','SR_B5'])` — computed on scale+offset-corrected reflectance. The mode id stays `ndwi` (now correctly named). The moisture index (NIR/SWIR) is **dropped from P0** and may return as a distinct `ndmi` mode in a later phase. The dead `compute_ndwi :1250` already carries the correct Green/NIR formula — reuse it as the reference, then delete the numpy helper.

**Band-choice table (verified):**

| Mode id | Formula | Sentinel-2 | Landsat 8/9 | P0 action |
|---|---|---|---|---|
| `ndvi` | (NIR−Red)/(NIR+Red) | `B8,B4` | `SR_B5,SR_B4` | correct bands; **fix L8 offset via pre-scaling** |
| `ndwi` (true water) | (Green−NIR)/(Green+NIR) | `B3,B8` | `SR_B3,SR_B5` | **switch to McFeeters water**; compute on reflectance |
| `ndbi` | (SWIR1−NIR)/(SWIR1+NIR) | `B11,B8` | `SR_B6,SR_B5` | correct |

Move all index computation server-side, by band name; delete the brittle numpy helpers with hardcoded tensor indices (`nir_idx=6`, `:1227-1270`).

#### C.2.6 The real-fusion roadmap **[LATER]** (why P0 doesn't do fusion yet)

Every multi-sensor mode today is `s2.add(l8).divide(2)` (`:723,737,750,758,769,779,787,800,807,814`) — a pixel-average that (a) drags S2's 10 m detail toward Landsat's 30 m blur and (b) mixes radiometrically-different sensors unharmonized. Real capabilities that replace it:

- **[Phase 1] Gap-fill:** harmonize Landsat to S2 first, then `s2_masked.unmask(l8_masked)` — S2 authoritative wherever present (never degraded), Landsat fills only cloud/shadow gaps; `unmask` is per-band and lazy (no reproject-too-large risk). Provenance band flags S2-vs-fill pixels.
- **[Phase 1/2] HLS-style harmonization:** per-band linear bandpass `ρ_S2 ≈ slope·ρ_L8 + intercept` (Claverie et al. 2018), coefficients in **config** (refit/regionalizable), validated over S2∩L8 overlap dates.
- **[Phase 3] Real LST product** beyond the °C visualization P0 ships (multi-source, emissivity refinement, export).
- **[Phase 4, experimental, LAST] Super-resolution:** GEE patch export (async `getDownloadURL`, tiled/bounded) → PyTorch SR model server (separate container) → restitch/georeference → GEE ingest → getMapId tiles. Async job + poll, not a synchronous tile request. **Mandatory:** fidelity metric (PSNR/SSIM) + UI "AI-enhanced — may hallucinate detail; not for measurement" label; `experimental=True` gates it.

#### C.2.7 Timelapse re-plumb **[P0]**

`generate_timelapse` (`:1058-1225`) today carries its own duplicate visualization ladder (`prepare_image :1092`) that reproduces **every** bug P0 fixes elsewhere: S2 LST via non-existent `B10` (`:1121`), raw-band NDVI-on-Landsat (`:1131`), and unmasked `CLOUDY_PIXEL_PERCENTAGE < 30` (`:1173`). Because timelapse is a **kept** UI endpoint, P0 routes each frame through the shared machinery: `SensorImages` scaling (§C.2.3) + `mask_s2`/`mask_landsat` (§C.2.1) + `STRATEGY_REGISTRY[id].build()` → `visualize(**vis)`. This deletes `prepare_image` and its private ladder, and makes success criterion #6 ("correct indices; LST Landsat-only") hold **system-wide**, not just on the tile path.

---

### C.3 UI/UX

#### C.3.1 Component-architecture refactor **[P0]**

Today: `App.jsx` holds **13 `useState`s** and drills 18 props to Sidebar / 14 to Map (`:9-56, :334-369`); `Sidebar.jsx` is a **669-line god-component** with ~130 lines of copy-paste timelapse buttons (`:438-571`), the same modes repeated in the fusion row (`:356-400`), three inline `<style>` blocks, and inline geocoding fetch (`:66-91`).

**Target tree** (abridged): `config/{visualizations,satellites,basemaps}.js`, `api/client.js`, `state/AppStore.jsx`, `hooks/{useFusion,useGeocode}.js`, `components/{Sidebar/*, Map/*, layers/*, legend/IndexLegend, feedback/{Toast,FusionStatus,Loader}}`. Sidebar → layout shell (~70 LOC); App → provider mount + layout (~60 LOC).

**Config-driven buttons — kill ~250 lines of copy-paste.** One `VISUALIZATIONS` array (id, label, icon, ramp, `fusion`/`timelapse` flags, `accent` gradient, `sensors`, `legend` spec) drives fusion buttons, timelapse buttons, LayerControl badges, **and** legends.

```js
// config/visualizations.js (excerpt) — ids MUST match backend STRATEGY_REGISTRY / FusionRequest Literal
export const VISUALIZATIONS = [
  { id:'ndvi', label:'NDVI', sub:'Vegetation', icon:'🌿', ramp:'ndvi', fusion:true, timelapse:true,
    accent:['#22c55e','#10b981'],
    legend:{ min:-0.2, max:0.8, colors:['#a50026','#ffffbf','#006837'], unit:'' } },
  { id:'ndwi', label:'NDWI', sub:'Water', icon:'💧', fusion:true, timelapse:true,             // true McFeeters water (Green/NIR)
    legend:{ min:-0.3, max:0.6, colors:['#8c510a','#f6e8c3','#2166ac'], unit:'' } },
  { id:'lst', label:'LST', sub:'Temperature', icon:'🌡️', fusion:true, timelapse:true, sensors:['landsat'],
    legend:{ min:20, max:45, colors:['#313695','#fee090','#a50026'], unit:'°C' } },  // °C — matches backend
  // true_color, ndbi, false_color_swir, false_color_nir …
]
```
```jsx
{VISUALIZATIONS.filter(v => v.timelapse).map(v =>
  <VizButton key={v.id} viz={v} disabled={busy||!aoi} onClick={() => onTimelapse(v.id)} />)}
```

> **Cross-track alignment:** the frontend `VISUALIZATIONS` ids and backend `STRATEGY_REGISTRY` ids are **identical** (`true_color, ndvi, ndwi, ndbi, false_color_nir, false_color_swir, sci, lst`) so the `Literal` in `FusionRequest` and the buttons never drift. `sensors` appears in both (LST → landsat-only) so the UI hides what the backend would reject.

**State: `useReducer` + Context (single store), NOT Redux/Zustand.** The 13 `useState`s are already a coupled state machine (clearing AOI must reset `searchResults`+`selectedScene`, done by hand at `:80-90`; `handleGEEFusion` reads 5 fields and writes 3, `:151-245`). A reducer expresses transitions (`AOI_CLEARED, FUSION_STARTED, FUSION_SUCCEEDED, FUSION_EMPTY, FUSION_FAILED, LAYER_UPDATED`) in one place; Context removes prop-drilling with zero new deps (we're *removing* `axios`/`react-leaflet`). Split into **two contexts**: `SettingsContext` (aoi/dates/platforms/mode — rare) and `LayersContext` (layers/opacity/compare — every slider drag), so opacity drags don't re-render the Sidebar.

**Delete outright [P0]:** `TypingIntro.jsx` (+ import `App.jsx:4` + dead `showIntro` state `:9`), `ExportPanel.jsx` (real one returns Phase 3), `TimeSlider.jsx` (returns Phase 2), `utils/performanceUtils.js`; drop `axios`+`react-leaflet` from `package.json`. Move the three inline `<style>` blocks to `index.css`.

#### C.3.1a Dataset Mode — explicit removal **[P0]**

Dataset Mode is a **live, fully-wired UI flow** that P0 must not silently orphan: `isDatasetMode`/`datasetPath` state (`App.jsx:55-56`), the `create_dataset`/`destination_folder` fields sent to the backend (`App.jsx:188-189`), the "Dataset Saved" success alert keyed on `result.dataset_path` (`App.jsx:202-204`), props threaded App→Sidebar (`:349-351, :367-368`), and the Sidebar toggle + path input + `download-zip` URL builder (`Sidebar.jsx:20-22, :219, :286-324`).

Because GeoTIFF *generation* moves to **Phase 3** (the getMapId pivot produces no server-side raster), P0 **removes the Dataset Mode UI entirely**:
- Delete `isDatasetMode`/`datasetPath` state and the two props; delete the Sidebar toggle/path-input/zip-button block (`Sidebar.jsx:219, :286-324`).
- The new `FusionRequest` model omits `create_dataset`/`destination_folder` (§C.1.3), so App sends neither.
- Backend `datasets/list|download|download-zip` are **kept dormant + hardened** (§C.1.6) so no route 404s if hit directly, but nothing in the P0 UI references them.

This is a **deliberately scoped-out capability**, returning in Phase 3 with a real `ExportPanel` + async `getDownloadURL`. It is listed in §E (Out of scope) so the cut is explicit, not accidental.

#### C.3.1b Bhuvan / ISRO WMS — decided in P0 **[P0]**

`bhuvan_service.get_available_layers()` feeds `/api/search/all` (`:603`) and the frontend reads `data.bhuvan.layers` (`App.jsx:130`), with a satellite toggle (`Sidebar.jsx:118`) and a `type==='wms'` render branch (`Map.jsx:231`). Because the Sidebar rewrite touches this toggle, its fate is **decided now, not deferred**: **keep the bhuvan block wired read-only in P0** — search-all continues to return `bhuvan.layers`, the toggle and the `wms` layer branch stay. No new capability, no removal; a full ISRO-WMS decision (promote vs drop) is Phase 1. This avoids the "App requests bhuvan but Sidebar dropped the toggle" orphan the rewrite would otherwise risk.

#### C.3.2 Fusion under the getMapId tile model **[P0]**

The frontend layer object moves from `imageOverlay`/`imageUrl` (`App.jsx:212-223`) to a `tileUrl` shape. **Map.jsx does not yet fully handle this:** `type==='fusion'` (`:245`) only sets an attribution string *inside* the generic `else if (layer.tileUrl)` fallthrough (`:240`), which hardcodes `maxZoom:18` (`:253`) and has **no `tileerror` handler and no `expiresAt` awareness**. So the tile-layer branch is **rewritten in P0**, not merely reused:

```js
// FUSION_SUCCEEDED payload
{ id:'fusion', name:'Fused · NDVI', type:'gee',
  tileUrl: r.tile_url_template, expiresAt: r.expires_at*1000,
  bounds: r.bounds, visible:true, opacity:100, mode: r.visualization,
  maxNativeZoom: r.max_native_zoom }
```

```js
// Map.jsx rewritten GEE-tile branch (replaces :240-262)
leafletLayer = L.tileLayer(layer.tileUrl, {
  attribution: 'GEE Harmonized Fusion',
  opacity: layer.opacity / 100,
  maxNativeZoom: layer.maxNativeZoom ?? 14,   // GEE tiles native to ~14; upsample above
  maxZoom: 20,                                // match CartoDB basemap (Map.jsx:74) — no blank at z18–20
  tileSize: 256,
})
leafletLayer.on('tileerror', onTileError)     // §C.3.4 — net-new, not inherited
```

- **`maxZoom:18` → `maxZoom:20`** (basemap is `maxZoom:20` at `Map.jsx:74`) with `maxNativeZoom` so GEE upsamples rather than blanking the fusion layer past z18 — the bug the old fallthrough would inherit.
- `imageOverlay` (`:219-229`) becomes a **[LATER]** fallback only; `fitBounds` moves into the tile branch (currently only in the overlay branch `:229`).
- Remove the `image-rendering: pixelated` hack (`index.css:384-390`) — that was for the downloaded PNG; real GEE tiles must render normally.

#### C.3.3 Replace all 7 `alert()`s with inline status + toasts **[P0]**

Today: 7 `alert()`s including **two success alerts per fusion** (`:204` dataset-saved + `:236` completion — the dataset one is removed with §C.3.1a) and a mid-run timelapse alert (`:265`). Drive UI from `fusion.status`:

| State | UI |
|---|---|
| `loading` | button → inline spinner "Fusing Sentinel + Landsat…"; thin **indeterminate** bar under the map top-bar (GEE gives no percent); buttons disabled via `status==='loading'` |
| `success` | toast "Fusion ready" (3 s auto-dismiss); LayerControl row appears; **no second alert** |
| `empty` | empty-state card: "No cloud-free scenes for this area/date range. Widen dates or raise cloud tolerance." (today this throws/alerts) |
| `error` | inline error card + **Retry** (re-dispatch same args); replaces `:195,241,301` |

`FusionStatus.jsx` renders these; `Toast`+`ToastHost` is a tiny context. A11y: status region `role="status" aria-live="polite"`, errors `aria-live="assertive"`.

#### C.3.4 Request cancellation + tile-expiry refetch **[P0]**

**Last-writer-wins race** (`handleGEEFusion :151-245` has no `AbortController`): rapid NDVI→SWIR leaves two in-flight fetches; the slower resolves last and overwrites the map. Fix in `useFusion.js`:

```js
const ctrlRef = useRef(null)
const run = useCallback(async (mode) => {
  ctrlRef.current?.abort()                                  // cancel any in-flight fusion
  const ctrl = new AbortController(); ctrlRef.current = ctrl
  dispatch({ type:'FUSION_STARTED', mode })
  try {
    const r = await api.post('/api/fusion/gee-harmonize', body, { signal: ctrl.signal })
    if (ctrl.signal.aborted) return                         // stale-winner guard
    dispatch(r.scene_counts.sentinel + r.scene_counts.landsat === 0
      ? { type:'FUSION_EMPTY' } : { type:'FUSION_SUCCEEDED', layer: toTileLayer(r) })
  } catch (e) {
    if (e.name === 'AbortError') return                     // superseded click — silent
    dispatch({ type:'FUSION_FAILED', error: humanize(e) })
  }
}, [dispatch])
useEffect(() => () => ctrlRef.current?.abort(), [])         // abort on unmount
```

**Refetch on tile expiry** (locked "refetch on tile 4xx") — this is **net-new** code attached to the rewritten tile branch (§C.3.2), since the old fallthrough had no `tileerror` handler:

```js
tl.on('tileerror', async (e) => {
  const s = e?.tile?.status
  if ((s===401||s===403||s===404 || Date.now()>layer.expiresAt) && !refetching) {
    refetching = true
    const fresh = await api.get(`/api/fusion/${layer.id}/refresh-mapid`)   // cheap re-mint (§C.1.5)
    tl.setUrl(fresh.tile_url_template)                                     // swap, no teardown/flicker
    dispatch({ type:'LAYER_UPDATED', id:layer.id,
               patch:{ tileUrl:fresh.tile_url_template, expiresAt:fresh.expires_at*1000 } })
    refetching = false
  }
})
```
The `refetching` guard prevents a thundering herd when a whole viewport 403s. A proactive pre-expiry timer is **[LATER]**.

#### C.3.5 LayerControl, compare, legend, controls **[P0]**

- **LayerControl:** badges from config (not the `rgb/ndvi/wms`-only hardcode at `:212-225`), inline `<style>` (`:69-226`) → CSS, keep opacity/visibility but route through `LAYER_UPDATED`, add master opacity.
- **Compare in P0 is opacity/visibility only.** A **3-way input/fused compare is [LATER]** (Phase 2): rendering Sentinel-only and Landsat-only as separate selectable layers is itself a fusion capability (the raw inputs to gap-fill), and minting 3 mapids per request triples the getMapId load P0 optimizes — and the `FusionMapResponse` contract (§C.1.3) intentionally carries a **single** `tile_url_template`. P0 ships the honest single-sensor views as ordinary selectable layers, which already lets a user eyeball S2 vs L8 by toggling; a synchronized swipe/spyglass/segmented compare is Phase 2.
- **Mode selector (P0):** explicit segmented control reading `VISUALIZATIONS` (mode is implicit today — whichever button you click, `:46,157`).
- **Basemap switch (P0):** dropdown Dark / Light / Satellite (only CartoDB Positron hardcoded today `Map.jsx:71-76`); `BASEMAPS` config + `L.tileLayer` swap in `SettingsContext`. Removes the `dim-tiles` brightness hack (`index.css:665-667`).
- **Date validation (P0):** `DateRangePicker` (extract `Sidebar:128-213`) rejects end<start inline and disables fusion (no guard today) + quick presets.
- **`IndexLegend` (P0):** color-ramp bar + min/max/unit from `VISUALIZATIONS[mode].legend`, shown only for modes with a legend (NDVI/NDMI/LST), bottom-right above the coords pill. LST legend is **°C** (§C.2.4).

#### C.3.6 API client + env + design tokens + a11y **[P0]**

- **`api/client.js`:** one `fetch` wrapper reading `import.meta.env.VITE_API_BASE_URL ?? ''` (empty → Vite proxy in dev); typed `ApiError` → `humanize()`. **Remove the hardcoded `http://localhost:8000` + `?t=${Date.now()}` cache-buster** (`App.jsx:216-218`) — GEE tile URLs are absolute (host disappears), and freshness is the expiry refetch, so no cache-buster. `.env.development` → empty; `.env.production` → deploy URL. The base URL lives **only** inside `api/client.js` (single ingress) — no separate `config.js` constant.
- **`vite.config.js` proxy is env-driven too [P0].** So the deploy build does not hardcode a dev host, the proxy target reads an env var:
  ```js
  // vite.config.js — proxy target from env (was hardcoded 'http://localhost:8000' at line 19)
  target: process.env.VITE_DEV_PROXY_TARGET || 'http://localhost:8000',
  ```
  The literal `http://localhost:8000` remains only as a **dev default fallback** in `vite.config.js` (a build-time-only file, never bundled into the client). Success criterion §D.3 scopes its grep accordingly (see D.3).
- **Design tokens:** three palettes fight today — `index.css:5-47` pure-black vs Sidebar slate vs LayerControl navy. Unify on one slate/navy set, single cyan accent (+ amber for warnings), gradients only on data (legends), never on chrome; retire the blue→purple button gradients; mono for coords/dates. Run the `frontend-design` skill to pin exact tokens before locking.
- **A11y baseline:** `aria-label` on every icon/emoji button; live regions for status/errors; segmented controls as `role="radiogroup"` with arrow-key nav; global `:focus-visible` rings; bump `--text-muted` to ≥4.5:1; gate animations behind `prefers-reduced-motion`.
- **Responsive:** ≥1024 px side-by-side; 768–1024 sidebar → overlay drawer; <768 map full-screen + swipe-up sheet (map already `flex:1`, only the sidebar needs breakpoints).

---

### C.4 Testing

**Nothing to lean on today:** zero project tests; and `import main` authenticates to GEE (`__init__ :94` → `_try_auto_init :100`, singleton imported at `main.py:34`). So the §C.1.2 refactor (pure resolver + lifespan-only init) is a **testability prerequisite**.

**Frontend test tooling to add [P0]** (none present in `package.json` today): `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`, `msw` as devDependencies, plus a `"test": "vitest run"` script. Listed here because criterion #9 depends on them.

**Backend unit suite (pytest, `ee` mocked) [P0].** `conftest.py` installs a fake `ee` into `sys.modules` **before** importing `main`; a chainable `_FakeImage` records the op-chain and returns a fake `getMapId` with `tile_fetcher.url_format`. Suites:
- `test_auth_resolver.py` — SA-path-wins / ADC-fallback / missing-project-is-a-loud-error / **`assert "compact-arc-482620-r8" not in inspect.getsource(module)`** (regression guard on the hardcode).
- `test_config.py` — no hardcoded localhost; CORS origins parsed from env; TTL > 0.
- `test_fusion_graph.py` — true-color is **not** `add`+`divide(2)`; Landsat NDVI/NDMI/NDBI computed on scale+offset-corrected reflectance; **Landsat LST output is in °C range (~20–45), not raw DN (~44000) and not Kelvin**; Sentinel-only LST **raises** (no `B10`); "requires ≥1 image"; every viz mode `visualize`s; **timelapse uses the same registry path** (no private `prepare_image` ladder; no `B10`).
- `test_endpoints_contract.py` — `gee-harmonize` returns a `{z}/{x}/{y}` template + `bounds` `[[S,W],[N,E]]` + `expires_at` + `max_native_zoom`; **single** tiles-route owner; CORS middleware present **exactly once**; `/health` 200/503; **no orphaned `FusionProcessing*`/old-`HealthResponse` import** in `main`.
- `test_error_paths.py` — missing/short bounds → 400; no-imagery → 404; init-failure → 503; **start>end → 400/422** (currently-missing validation, written red-first).

**Real-GEE integration suite [P0 author / on-demand run].** `@pytest.mark.integration`, gated by `ORBITER_GEE_LIVE=1` + real creds, **never in CI** (`-m "not integration"`). Proves getMapId mints a working template, a real center tile is HTTP 200 `image/*`, fusion latency < 20 s (vs old 90 s), Landsat-only LST smoke, **Cloud Score+ masking runs clean on the Q1-2024 AOI** (i.e. `cs_cdf` present, no "band not found"). AOI fixture: Bengaluru `(77.55,12.95,77.62,13.02)`, Q1-2024.

**Frontend (Vitest + RTL + MSW) [P0].** `api/client.js` tests (posts bounds/dates, returns template, surfaces error detail, **no `localhost:8000` in `src/`**); component smoke (fuse button disabled in-flight, **error banner not alert**, loading indicator); and the **highest-value test — the click-race:** click NDVI (slow) then true_color (fast); after both resolve, `layer-ndvi` must be absent and `layer-true_color` present (proves the AbortController guard). Add `data-testid={`layer-${mode}`}` on the active overlay so the race is observable without Leaflet's canvas.

**E2E (Playwright) [LATER — end of P0, non-blocking].** One happy path against a fully-mocked backend (route-fulfill the fusion call + a 1×1 PNG tile): draw AOI → click True Color → assert `img.leaflet-tile` visible and `[role="alert"]` count 0.

**CI [P0 backend+frontend jobs; e2e LATER].** GitHub Actions: backend `pytest -m "not integration" --cov`, frontend `vitest run --coverage` + `npm run build`. Coverage gates: resolver 95%, config 90%, fusion-graph builder 80%, fusion endpoints 85%, `api/client.js` 90%, components 60% smoke; **fail CI < backend 75% / frontend 55%**, ratchet per phase. Exclude code slated for deletion.

**Manual acceptance [P0 — run first, today]** with a working GEE id, before any refactor, to prove the live path end-to-end. See Runbook §C.5.5.

---

### C.5 Runbook

> **What `gee-harmonize` returns *today*.** `:214`'s handler path returns **`imageUrl: "/static/fusion/{id}.png"`** (`gee_fusion_service.py:1026`), **not** a tile template. Only the *legacy* `/api/fusion/harmonize` (`:110`) returns a `tile_url` (`:158`), and that route is being **deleted**. So the P0 target contract (`tile_url_template` from getMapId) is a *change*; the smoke test below checks `imageUrl` **today** vs `tile_url_template` **after the pivot**.

#### C.5.1 Ground truth
- Committed `venv/` + `venv_new/` are **Windows / Python 3.9.6** (`venv_new/pyvenv.cfg` → `C:\...\Python39`, `Scripts/`), unusable on Linux; `a1/` is empty. Always build a fresh venv.
- `rio-tiler` is **used transitively but absent from `requirements.txt`** — it arrives only via `titiler.core` (verified: no literal `rio-tiler`/`rio_tiler` line in `requirements.txt`; `rasterio` *is* present, also a titiler dep). The P0 delete plan removes the titiler/COG mount **and** the only `rio_tiler` importers (dead duplicate tile route `:764`, plus `check_url_readability.py`/`debug_mosaic_test.py`), so **after the deletions `rio-tiler` is not needed at all.** Until then, pin it to keep the app importable.

> **rio-tiler pin vs delete — sequencing.** *Interim* (before deletes land) → `pip install "rio-tiler>=0.14,<0.19"` to unblock. *End state of P0* → titiler/COG mount and every `rio_tiler` importer deleted, so `rio-tiler`, `titiler.core`, `mercantile`, `rasterio`, `xarray` all leave `requirements.txt`.

#### C.5.2 Linux (fresh venv — the reproducible path)
```bash
sudo apt-get install -y python3.11 python3.11-venv python3-pip build-essential nodejs npm
cd "/workspace/orbiter-fusion - Copy/backend"          # quote — the path has a space
python3.11 -m venv .venv-linux && source .venv-linux/bin/activate   # NOT venv/ or venv_new/ (Windows)
pip install -U pip wheel && pip install -r requirements.txt
export ORBITER_GEE_PROJECT="<your-gee-project>"
# creds — pick ONE:
earthengine authenticate                               # dev w/ browser → ~/.config/earthengine/credentials
# OR service account (headless/deploy):
export ORBITER_GEE_SERVICE_ACCOUNT_FILE=/etc/orbiter/ee-sa.json
uvicorn app.main:app --host 0.0.0.0 --port 8000        # NOT `python main.py`
```
Frontend:
```bash
cd "/workspace/orbiter-fusion - Copy/frontend" && npm ci
# frontend/.env (dev, uses Vite proxy vite.config.js): VITE_API_BASE_URL=
npm run dev                                            # :5173
# deploy: frontend/.env.production → VITE_API_BASE_URL=https://api.your-host ; npm run build && npm run preview
```

#### C.5.3 Windows host (operator's real env)
`py -3.9 -m venv .venv-win` → `.\.venv-win\Scripts\Activate.ps1` → `pip install -r requirements.txt` → `earthengine authenticate` → `$env:ORBITER_GEE_PROJECT="…"` → `uvicorn app.main:app --host 0.0.0.0 --port 8000`. `vite.config.js` already sets `watch.usePolling:true` (line 19) for Windows HMR. Since §C.1.1 deletes the SSL-unsafe env writes with the COG path, no Windows SSL workaround is needed.

#### C.5.4 Headless-sandbox blockers (ranked)
1. **No browser → interactive `earthengine authenticate` can't complete.** Only real fix: **service-account JSON** via `ORBITER_GEE_SERVICE_ACCOUNT_FILE`. (Or copy in an existing `~/.config/earthengine/credentials`.)
2. **No credential present here** → `ee.Initialize` throws; today it's swallowed (`:106-107`) so the server boots but every fusion call fails; **after §C.1.2** `/health` reports `503 degraded` honestly.
3. **Egress required:** `earthengine.googleapis.com` + `earthengine-highvolume.googleapis.com`, `oauth2.googleapis.com`, pypi, npm. (Nominatim geocoding `Sidebar.jsx:72` is non-fatal if blocked.)
4. Windows venvs are dead weight on Linux — always `.venv-linux`.

**Go/no-go:** with a service-account JSON + egress, the full stack runs headless. Without a credential: boot-OK-but-fusion-fails — validate `/health` and `/docs` reachability before blaming code.

#### C.5.5 Smoke test
```bash
BASE=http://localhost:8000
curl -sf "$BASE/health" | python -m json.tool          # after §C.1.2: 200 healthy / 503 degraded (gee.ready)
curl -sf -X POST "$BASE/api/fusion/gee-harmonize" -H 'Content-Type: application/json' -d '{
  "bounds":[77.55,12.95,77.62,13.02],"start_date":"2024-01-01","end_date":"2024-03-31",
  "cloud_cover":20,"visualization":"true_color","platforms":["sentinel","landsat"]}' | tee /tmp/f.json
```
Interpreting, tied to defects:
- **`imageUrl:"/static/fusion/…png"`** → you hit the **pre-pivot PNG path** (today's reality, `gee_fusion_service.py:1026`). After the getMapId pivot this becomes `tile_url_template` with `{z}/{x}/{y}` — confirm one real tile: `curl -o /tmp/tile.png "<template with z/x/y substituted>" && file /tmp/tile.png` → `PNG image data`.
- **500 `NameError`** → the duplicate `/api/fusion/{id}/tiles` route (`:764` survivor, unimported `Reader`/`Resampling`) — gone after §C.1.6.
- **GEE auth error** → creds/env not wired (§C.5.2) — expected in this sandbox.
- Full-stack: draw a rectangle over Bengaluru → tick Sentinel+Landsat → dates 2024-01-01…03-31 → **True Color** → fused overlay appears within seconds, no error banner.

#### C.5.6 Repo hygiene **[P0]**
- Add `.env.example` (backend + frontend); git-ignore `ee-sa.json`, `**/credentials`.
- Purge from the working tree (and later from history): committed `venv/`, `venv_new/`, `a1/` (~570 MB), ~285 committed PNGs, `static/fusion/*`, `backend/debug_*.py`, `check_url_readability.py`, `debug_mosaic_test.py`. Enforce via `.gitignore` (already lists `venv/` but the dirs are committed anyway).
- **Final P0 `requirements.txt` — full audit** (verified current contents):

| Package | P0 action | Why |
|---|---|---|
| `fastapi`, `uvicorn[standard]`, `pydantic>=2` | **keep** | core app |
| `pydantic-settings>=2` | **add** | typed config (§C.1.1) |
| `cachetools>=5` | **add** | TTLCache (§C.1.5) |
| `earthengine-api` (pin) | **keep** | the whole point |
| `pystac-client`, `planetary_computer` | **keep** | STAC search (`sentinel.py`/`landsat.py`) |
| `requests` | **keep** | used by `bhuvan.py` |
| `httpx` | **keep** if any outbound remains post-delete; **drop** if only the deleted PNG download used it — verify |
| `titiler.core`, `mercantile`, `rasterio`, `xarray` | **drop** | all tied to the deleted COG/titiler path |
| `rio-tiler` | **drop** (interim pin only; §C.5.1) | zero importers after deletes |
| `python-multipart` | **drop** | no form/multipart uploads exist in the kept endpoints |
| `numpy`, `scipy`, `Pillow` | **drop** if the timelapse GIF assembler doesn't need them post-registry-replumb; **keep** only what `generate_timelapse` truly imports — verify post-delete |
| `shapely`, `pyproj` | **verify** | keep only if a kept endpoint imports them (AOI geometry); drop if only dead paths did |

---

## D. Success criteria (measurable)

A Phase 0 is "done" when **all** hold:

1. **Tiles, not PNGs.** `POST /api/fusion/gee-harmonize` returns `{tile_url_template, bounds, expires_at, scene_counts, max_native_zoom}` with `{z}/{x}/{y}` in the template; **no** `getThumbURL`/`urlretrieve`/`/static/fusion/*.png` remains in the live path. A real center tile fetches HTTP 200 `image/*`.
2. **Latency.** A fusion request returns in **< 20 s** (getMapId is metadata-only), vs the current 90 s download timeout.
3. **Config-driven, no hardcoded hosts in shipped code.** `grep -rn "compact-arc-482620-r8" backend/` and `grep -rn "localhost:8000" backend/app frontend/src` both return **zero**. The only surviving `localhost:8000` literal is the **dev-only fallback** in `vite.config.js` (build-time file, never bundled), and its proxy target is env-overridable via `VITE_DEV_PROXY_TARGET` (§C.3.6). GEE project, CORS origins, and frontend base URL all come from env.
4. **Honest health.** `/health` returns **503** when GEE isn't initialized, **200** when it is, echoing `project` + `error`.
5. **Bounded + masked composites.** Composites capped at `max_scenes_per_composite` (`.limit` restored at `:180,:246`); per-pixel masks applied — **SCL + Cloud Score+ `cs_cdf`** for S2 (QA60 dropped as dead for target dates), **QA_PIXEL** for Landsat — with masking done *before* band-narrowing so `SCL`/`cs_cdf` exist; `scene_counts` are **real** `size().getInfo()` values, not `mean_ndvi:0.45`.
6. **Correct indices, system-wide.** Landsat indices computed on scale+offset-corrected reflectance (offset bug at `:639,734,1131` fixed); LST is Landsat-only (no `B10` on S2), output in **°C** matching the legend; NDWI switched to **true McFeeters water** (Green/NIR) end-to-end (F1). Holds on the **timelapse** path too (§C.2.7), not just tiles.
7. **One of everything.** Exactly one CORS middleware; exactly one `/api/fusion/{id}/tiles` route owner (or none, post-getMapId); no `NameError` route; no orphaned `FusionProcessing*`/old-`HealthResponse` imports.
8. **Real UX, no orphaned flows.** Zero `alert()` in `frontend/src`; loading/empty/error/retry states render in-DOM; rapid mode-switch (NDVI→SWIR) never leaves a stale layer (AbortController); expired tiles refetch on `tileerror`; the fusion tile layer renders through zoom 20 (`maxZoom:20`+`maxNativeZoom`); **Dataset Mode UI is fully removed** (no dangling `isDatasetMode`/`datasetPath` handlers), and the bhuvan toggle stays wired (§C.3.1a/b).
9. **Tests green.** Backend `pytest -m "not integration"` and frontend `vitest run` pass in CI; frontend test devDeps are in `package.json`; coverage ≥ **backend 75% / frontend 55%**; the click-race, auth-resolver, LST-°C, and start>end tests pass. Integration suite authored + runnable on demand.
10. **Runs from clean.** A fresh Linux venv + service-account JSON boots backend and frontend, and the §C.5.5 smoke sequence passes; committed venvs/PNGs removed; audited `requirements.txt` installs without the missing-`rio-tiler` failure.

---

## E. Out-of-scope for Phase 0

- The **four real fusion algorithms** — gap-fill, HLS harmonization, real LST *product*, super-resolution (Phases 1–4). P0 ships the *registry seam*, correct scaling/masking, and honest single-sensor views (including an LST *visualization* in °C); it does **not** replace `add/divide(2)` with real fusion (naive-average multi-sensor modes are hidden/demoted, not rebuilt).
- **Dataset Mode / GeoTIFF export** — the `create_dataset` flow, `ExportPanel`, and async `getDownloadURL` (Phase 3). The P0 UI removes the Dataset Mode controls (§C.3.1a); backend `datasets/*` endpoints stay hardened-but-dormant.
- **Input/fused compare** (3-way Sentinel|Fused|Landsat), **swipe/spyglass**, **time-series scrubber** (rebuilt `TimeSlider`), proactive pre-expiry token-refresh timer — all [LATER, Phase 2].
- **Deploy hardening:** Dockerfile, k8s live/ready split, rate-limiting, auth on write endpoints, purging git *history* (P0 cleans the working tree + `.gitignore`; history rewrite is later).
- **E2E Playwright** job is authored at the end of P0 but **non-blocking** in CI.
- Moisture index (NDMI, NIR/SWIR) as a *distinct* mode — deferred to a later phase (P0 ships true water NDWI instead).

---

## F. Open questions for the user

1. **NDWI — RESOLVED (option a).** P0 changes the `ndwi` mode to **true McFeeters water** (Green/NIR): S2 `B3/B8`, Landsat `SR_B3/SR_B5`, computed on reflectance. The mislabeled NIR/SWIR moisture index is dropped from P0 (may return later as `ndmi`).
2. **GEE project for Phase 0.** Confirm the target `ORBITER_GEE_PROJECT` and whether we issue a **service-account** key for headless/CI/sandbox runs (required for any non-browser environment — §C.5.4). Is `compact-arc-482620-r8` still intended, or a fresh project?
3. **`mapid_ttl_seconds` default.** Set to **21600 s (6 h)** — well inside GEE's real token lifetime, with tile-4xx as the reactive backstop. Comfortable, or prefer longer/shorter?
4. **CORS origins for the first deploy.** What origin(s) beyond `http://localhost:5173` will the frontend serve from, so `ORBITER_CORS_ORIGINS` is set correctly?
5. **`bhuvan`/ISRO WMS.** P0 keeps it **wired read-only** (§C.3.1b). Confirm that's the intent, with the promote-vs-drop decision in Phase 1.
6. **Env-var prefix.** Standardized on `ORBITER_`. Confirm, or name a preferred prefix.
7. **Git history rewrite — RESOLVED (defer).** P0 cleans the working tree + `.gitignore` only; history purge deferred to a later phase to avoid disrupting existing clones.
