# Orbiter Fusion — Program Roadmap

**Date:** 2026-07-23 · **Status:** Draft for review

## What we're building

Orbiter Fusion is a multi-satellite data-fusion web app — Sentinel-2 (10 m) + Landsat 8/9 (30 m), FastAPI + Google Earth Engine backend, React 18 + Vite + Leaflet frontend. The goal is to turn the current prototype into a **deployable web service** that eventually delivers **four** fusion capabilities.

## Locked decisions

- **Four capabilities (eventual):** (1) cloud-free gap-fill, (2) HLS-style harmonized time series, (3) spectral extension / real LST, (4) sharper-than-10 m.
  - Capability (4) is achievable **only** via ML super-resolution (blending cannot exceed Sentinel's native 10 m; Landsat's 15 m pan is coarser). It is sequenced **last**, gated `experimental=True`, and shipped with an explicit "may hallucinate detail — not for measurement" caveat + a fidelity metric.
- **Target:** deployable web service — config-driven, concurrency-safe, no hardcoded hosts, real error/loading UX, tests.
- **Stay on GEE.**
- **Map display = GEE tile layer** — backend mints `image.getMapId(vis)` → XYZ URL template; frontend `L.tileLayer`. No server-side PNG download. mapid tokens expire → TTL cache + refetch on tile 4xx.

## Phases (each gets its own spec → plan → build)

| Phase | Deliverable |
|---|---|
| **Phase 0 — Foundation** | getMapId tile pivot, config-driven GEE auth, bounded+masked composites, strategy registry, correct indices, honest errors/health, dead-code purge, real UX (no `alert()`), request cancellation, tests + CI, runnable on Linux/Windows/headless. Detailed spec: [2026-07-23-orbiter-fusion-phase0-design.md](./2026-07-23-orbiter-fusion-phase0-design.md). |
| **Phase 1 — Real fusion I** | Cloud-free **gap-fill** (S2 master, Landsat `unmask` fill) + **HLS-style radiometric harmonization** (per-band linear) + real Landsat **LST** product. Replaces `add/divide(2)`. |
| **Phase 2 — Harmonized time series** | Interleaved S2 + harmonized-L8 on a common date axis; real time-series scrubber (rebuilt `TimeSlider`); swipe/spyglass compare; timelapse deepened. |
| **Phase 3 — Spectral extension + export** | Broader spectral products; GeoTIFF/PNG export (`ExportPanel` + `create_dataset`) via async GEE `getDownloadURL`; Dataset Mode UI returns. |
| **Phase 4 — Super-resolution (experimental)** | GEE patch export → PyTorch SR model server → restitch → GEE ingest → tiles; UI "AI-enhanced" badge + fidelity metric; `experimental=True` gate. |

## Provenance

The Phase 0 spec was produced by a multi-agent design workflow (5 parallel expert tracks: UI, fusion logic, backend, testing, runbook → synthesize → adversarial critique → finalize) grounded in the live tree, then reviewed by the operator.
