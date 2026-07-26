// src/state/actions.js
//
// Action types for the App reducer. Centralised so a typo in a `type:`
// string is a single-character fix instead of a buried bug across the
// tree.

export const AOI_CHANGED = "AOI_CHANGED";
export const DATE_RANGE_CHANGED = "DATE_RANGE_CHANGED";
export const SATELLITE_TOGGLED = "SATELLITE_TOGGLED";
export const SEARCH_STARTED = "SEARCH_STARTED";
export const SEARCH_SUCCEEDED = "SEARCH_SUCCEEDED";
export const SEARCH_FAILED = "SEARCH_FAILED";
export const SCENE_SELECTED = "SCENE_SELECTED";
export const MAP_CENTER_SET = "MAP_CENTER_SET";
export const BASEMAP_SET = "BASEMAP_SET";
export const LAYER_ADDED = "LAYER_ADDED";
export const LAYER_UPDATED = "LAYER_UPDATED";
export const LAYER_REMOVED = "LAYER_REMOVED";
export const VIZ_SELECTED = "VIZ_SELECTED";

// M9 — fusion lifecycle + toast surface.
export const FUSION_STARTED = "FUSION_STARTED";
export const FUSION_SUCCEEDED = "FUSION_SUCCEEDED";
export const FUSION_FAILED = "FUSION_FAILED";
export const FUSION_EMPTY = "FUSION_EMPTY";
export const TOAST_PUSHED = "TOAST_PUSHED";
export const TOAST_DISMISSED = "TOAST_DISMISSED";

// Phase 2 — time series + compare + timelapse lifecycle.
export const TIME_SERIES_REQUESTED = "TIME_SERIES_REQUESTED";
export const TIME_SERIES_FRAMES_LOADED = "TIME_SERIES_FRAMES_LOADED";
export const TIME_SERIES_FRAME_READY = "TIME_SERIES_FRAME_READY";
export const TIME_SERIES_FAILED = "TIME_SERIES_FAILED";
export const TIME_SERIES_SET_CURRENT = "TIME_SERIES_SET_CURRENT";
export const TIME_SERIES_CLEAR = "TIME_SERIES_CLEAR";
export const COMPARE_TOGGLED = "COMPARE_TOGGLED";
export const COMPARE_SLOT_CHANGED = "COMPARE_SLOT_CHANGED";
export const COMPARE_DIVIDER_MOVED = "COMPARE_DIVIDER_MOVED";
export const TIMELAPSE_STARTED = "TIMELAPSE_STARTED";
export const TIMELAPSE_SUCCEEDED = "TIMELAPSE_SUCCEEDED";
export const TIMELAPSE_FAILED = "TIMELAPSE_FAILED";

// Session Snapshot Gallery & Export
export const SNAPSHOT_SAVED = "SNAPSHOT_SAVED";
export const SNAPSHOT_REMOVED = "SNAPSHOT_REMOVED";
export const AI_ALERTS_SET = "AI_ALERTS_SET";
