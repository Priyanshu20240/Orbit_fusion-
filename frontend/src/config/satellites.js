// src/config/satellites.js
//
// The three satellite sources the UI exposes. `readOnly: true` on Bhuvan
// reflects the P0 decision: search-all returns bhuvan.layers, the toggle
// stays wired, but the promote/drop decision is Phase 1 (design §C.3.1b).

export const SATELLITES = [
    { id: "sentinel", label: "Sentinel-2",  icon: "🛰️", readOnly: false },
    { id: "landsat",  label: "Landsat 8/9", icon: "🌍", readOnly: false },
    { id: "bhuvan",   label: "Bhuvan (ISRO)", icon: "🇮🇳", readOnly: true },
];
