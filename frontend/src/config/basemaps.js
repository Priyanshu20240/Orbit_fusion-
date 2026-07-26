// src/config/basemaps.js
//
// Basemap switcher (design §C.3.5). Each entry is a Leaflet `tileLayer`
// descriptor. The CartoDB Positron is the prototype's default; the others
// are common web map styles that play nicely with the GEE fusion tiles.

export const BASEMAPS = [
    {
        id: "dark",
        label: "Dark",
        url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attribution:
            '© <a href="https://www.openstreetmap.org/copyright">OSM</a> · <a href="https://carto.com/attributions">CARTO</a>',
        maxZoom: 20,
    },
    {
        id: "light",
        label: "Light",
        url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        attribution:
            '© <a href="https://www.openstreetmap.org/copyright">OSM</a> · <a href="https://carto.com/attributions">CARTO</a>',
        maxZoom: 20,
    },
    {
        id: "satellite",
        label: "Satellite",
        // Esri World Imagery — the conventional web satellite basemap.
        url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attribution:
            "Tiles © Esri · Source: USGS, NASA, USDA",
        maxZoom: 19,
    },
];

export const DEFAULT_BASEMAP_ID = "dark";
export const BASEMAP_BY_ID = Object.fromEntries(BASEMAPS.map((b) => [b.id, b]));
