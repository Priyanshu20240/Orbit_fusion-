import { useEffect, useRef, useState, useCallback } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import 'leaflet-draw'
import 'leaflet-draw/dist/leaflet.draw.css'
import LayerControl from './LayerControl'
import TimeSlider from './TimeSlider.jsx'
import SwipeCompare, { COMPARE_LAYER_ID } from './SwipeCompare.jsx'
import BasemapControl from './BasemapControl.jsx'
import { request } from '../api/client'
import { BASEMAP_BY_ID, DEFAULT_BASEMAP_ID } from '../config/basemaps.js'


// Fix Leaflet default marker icons
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
    iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
    shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png'
})

// Fix for Leaflet Draw "type is not defined" error
if (L.GeometryUtil) {
    L.GeometryUtil.readableArea = function (area, isMetric, precision) {
        if (isMetric) {
            if (area >= 10000) {
                return (area * 0.0001).toFixed(2) + ' ha';
            } else {
                return area.toFixed(2) + ' m²';
            }
        } else {
            area /= 0.836127; // Square yards in 1 meter
            if (area >= 3097600) { // 3097600 square yards in 1 square mile
                return (area / 3097600).toFixed(2) + ' mi²';
            } else if (area >= 4840) { // 4840 square yards in 1 acre
                return (area / 4840).toFixed(2) + ' acres';
            } else {
                return Math.ceil(area) + ' yd²';
            }
        }
    }
}

// Customize Leaflet Draw Strings
L.drawLocal.edit.toolbar.actions.save.text = 'Confirm'
L.drawLocal.edit.toolbar.actions.save.title = 'Save changes'
L.drawLocal.edit.toolbar.actions.cancel.text = 'Cancel'
L.drawLocal.edit.toolbar.buttons.remove = 'Delete layers (Select then Confirm)'
L.drawLocal.edit.toolbar.buttons.removeDisabled = 'No layers to delete'

function Map({ aoi, onAoiChange, selectedScene, activeSatellites, isLoading, mapLayers, onLayerUpdate, scenes, mapCenter, basemapId, onBasemapChange, compare, timeSeries, aiAlerts, onMapClick }) {
    const mapRef = useRef(null)
    const mapInstanceRef = useRef(null)
    const drawnItemsRef = useRef(null)
    const basemapLayerRef = useRef(null)
    const aiAlertsLayerRef = useRef(null)
    const tileLayersRef = useRef({}) // Store tile layers by ID
    const [coords, setCoords] = useState({ lat: 0, lng: 0 })
    const onAoiChangeRef = useRef(onAoiChange)
    const onMapClickRef = useRef(onMapClick)
    useEffect(() => {
        onAoiChangeRef.current = onAoiChange
        onMapClickRef.current = onMapClick
    }, [onAoiChange, onMapClick])

    // Initialize map
    useEffect(() => {
        if (!mapRef.current || mapInstanceRef.current) return

        // Create map instance
        const map = L.map(mapRef.current, {
            center: [20.5937, 78.9629], // Center on India
            zoom: 5,
            zoomControl: true,
            attributionControl: true,
            zoomSnap: 1,      // FIX 2: Disable fractional zoom
            zoomDelta: 1,     // FIX 2: Lock zoom steps to integers
            preferCanvas: false
        })

        // Add dynamic basemap tile layer looked up from BASEMAP_BY_ID
        const activeBasemap = BASEMAP_BY_ID[basemapId || DEFAULT_BASEMAP_ID] || BASEMAP_BY_ID[DEFAULT_BASEMAP_ID]
        const basemapLayer = L.tileLayer(activeBasemap.url, {
            attribution: activeBasemap.attribution,
            subdomains: 'abcd',
            maxZoom: activeBasemap.maxZoom || 20,
        }).addTo(map)
        basemapLayerRef.current = basemapLayer

        // Initialize feature group for drawn items
        const drawnItems = new L.FeatureGroup()
        map.addLayer(drawnItems)
        drawnItemsRef.current = drawnItems

        // Add drawing controls
        const drawControl = new L.Control.Draw({
            position: 'topright',
            draw: {
                polygon: {
                    allowIntersection: false,
                    showArea: true,
                    shapeOptions: {
                        color: '#10b981', // Emerald green for polygons
                        weight: 2
                    }
                },
                circle: false,
                circlemarker: false,
                marker: false,
                polyline: false,
                rectangle: {
                    shapeOptions: {
                        color: '#3b82f6',
                        weight: 2,
                        fillOpacity: 0.1
                    }
                }
            },
            edit: {
                featureGroup: drawnItems,
                remove: true
            }
        })
        map.addControl(drawControl)



        // Helper to update AOI state from all drawn items
        const updateAoiFromDrawnItems = () => {
            const layers = drawnItems.getLayers()
            if (layers.length === 0) {
                onAoiChangeRef.current?.(null)
            } else {
                const group = new L.FeatureGroup(layers)
                const bounds = group.getBounds()

                // Get GeoJSON of feature collection or single feature
                let geojson
                if (layers.length === 1) {
                    geojson = layers[0].toGeoJSON().geometry
                } else {
                    // For multiple features, we might need a GeometryCollection or MultiPolygon
                    // But backend expects single geometry usually. 
                    // Let's send the feature collection if supported, or just the main geometry.
                    // For safety with current backend, let's treat it as a FeatureCollection or get geometry of first?
                    // Actually, let's just send the FeatureCollection if possible, or handle it as specific bounds.
                    // Given backend constraints, let's stick to bounds for search, and sending the first feature's geometry for now if strictly needed,
                    // OR better: Create a GeometryCollection.
                    const featureCollection = group.toGeoJSON()
                    // Simplification: backend might check for geometry type. 
                    // Let's just send the whole FeatureCollection object as 'geojson' property, 
                    // and let backend/frontend handle it.
                    geojson = featureCollection
                }

                // Pass both bounds and geometry
                onAoiChangeRef.current?.({
                    min_lon: parseFloat(bounds.getWest().toFixed(6)),
                    min_lat: parseFloat(bounds.getSouth().toFixed(6)),
                    max_lon: parseFloat(bounds.getEast().toFixed(6)),
                    max_lat: parseFloat(bounds.getNorth().toFixed(6)),
                    bounds: bounds,
                    geojson: geojson
                })
            }
        }

        // Handle draw start - Clear existing items for fresh start
        map.on(L.Draw.Event.DRAWSTART, () => {
            drawnItems.clearLayers()
            onAoiChangeRef.current?.(null)
        })

        // Handle draw created event
        map.on(L.Draw.Event.CREATED, (e) => {
            drawnItems.addLayer(e.layer)
            updateAoiFromDrawnItems()
        })

        // Handle draw deleted event
        map.on(L.Draw.Event.DELETED, (e) => {
            e.layers.eachLayer((layer) => {
                drawnItems.removeLayer(layer)
            })
            updateAoiFromDrawnItems()
        })

        // Handle draw edited event (resize/move)
        map.on(L.Draw.Event.EDITED, () => {
            updateAoiFromDrawnItems()
        })

        // Track mouse position & map click for point inspection
        map.on('mousemove', (e) => {
            setCoords({
                lat: e.latlng.lat.toFixed(4),
                lng: e.latlng.lng.toFixed(4)
            })
        })

        map.on('click', (e) => {
            if (e.latlng && onMapClickRef.current) {
                onMapClickRef.current(e.latlng.lat, e.latlng.lng);
            }
        })

        mapInstanceRef.current = map

        return () => {
            map.remove()
            mapInstanceRef.current = null
        }
    }, [])

    // Manage satellite tile layers
    useEffect(() => {
        if (!mapInstanceRef.current || !mapLayers) return

        const map = mapInstanceRef.current

        // Update existing layers or add new ones
        mapLayers.forEach(layer => {
            if (tileLayersRef.current[layer.id]) {
                // Update existing layer
                const existingLayer = tileLayersRef.current[layer.id]

                if (layer.visible) {
                    if (!map.hasLayer(existingLayer)) {
                        map.addLayer(existingLayer)
                    }
                    existingLayer.setOpacity(layer.opacity / 100)
                    // Phase 2 (M4): if the tileUrl changed (the slider moved
                    // → TIME_SERIES_SET_CURRENT → LAYER_UPDATED patches the
                    // active layer's tileUrl/fusionId), swap via setUrl to
                    // keep the data-testid container stable. Without this,
                    // every slider scrub would remove+re-add the layer and
                    // break the M8b click-race test.
                    if (
                        layer.kind === 'gee' &&
                        existingLayer._url !== layer.tileUrl
                    ) {
                        existingLayer.setUrl(layer.tileUrl)
                    }
                } else {
                    if (map.hasLayer(existingLayer)) {
                        map.removeLayer(existingLayer)
                    }
                }
            } else if (layer.visible) {
                // Create new layer based on type
                let leafletLayer

                if (layer.kind === 'gee' && layer.tileUrl && layer.bounds) {
                    // M8b: GEE getMapId tile layer. Replaces the pre-M5
                    // imageOverlay shape. GEE tiles are native to ~z14;
                    // upsample above to match the basemap's maxZoom:20.
                    leafletLayer = L.tileLayer(layer.tileUrl, {
                        attribution: 'GEE Harmonized Fusion',
                        opacity: layer.opacity / 100,
                        maxNativeZoom: layer.maxNativeZoom ?? 14,
                        maxZoom: 20,
                        tileSize: 256,
                        detectRetina: false,
                        zoomOffset: 0,
                        keepBuffer: 8,
                        updateWhenIdle: false,
                        updateWhenZooming: false,
                        fadeAnimation: false,
                    })
                    // data-testid for the click-race test (vitest).
                    // ElementWrapper doesn't see Leaflet panes, so we
                    // stamp the *layer container* with a class — that's
                    // the only DOM the test can read.
                    leafletLayer.getContainer?.()?.classList?.add(
                        `layer-${layer.mode || "fusion"}`
                    )
                    // Auto-zoom to the AOI bounds.
                    map.fitBounds(layer.bounds, { padding: [20, 20] })

                    // Reactive refetch on tile 4xx OR a token past its
                    // expiry — the mapid's reactive refresh path
                    // (design §C.3.4). The `refetching` guard prevents a
                    // thundering herd when a whole viewport 403s.
                    let refetching = false
                    leafletLayer.on('tileerror', async (e) => {
                        const status = e?.tile?.status
                        const expired =
                            layer.expiresAt && Date.parse(layer.expiresAt) <= Date.now()
                        if (
                            (status === 401 || status === 403 || status === 404 || expired) &&
                            !refetching &&
                            layer.fusionId
                        ) {
                            refetching = true
                            try {
                                const fresh = await request(
                                    `/api/fusion/${layer.fusionId}/refresh-mapid`
                                )
                                if (fresh?.tile_url_template) {
                                    leafletLayer.setUrl(fresh.tile_url_template)
                                }
                            } catch {
                                // Refetch is best-effort; the layer keeps the
                                // stale URL until the next reload.
                            } finally {
                                refetching = false
                            }
                        }
                    })

                } else if (layer.kind === 'wms' && layer.tileUrl) {
                    // WMS layer for Bhuvan (P0: read-only).
                    leafletLayer = L.tileLayer.wms(layer.tileUrl.split('?')[0], {
                        layers: layer.layerId || 'india_sat',
                        format: 'image/png',
                        transparent: true,
                        attribution: 'ISRO Bhuvan',
                        opacity: layer.opacity / 100,
                    })
                } else if (layer.imageUrl && layer.bounds) {
                    // Legacy `imageOverlay` shape. M8b demotes this to
                    // [LATER] — the post-M5 backend no longer returns
                    // `imageUrl`. Kept here as a fallback so older saved
                    // state still renders something, but the new path
                    // is the `kind === 'gee'` branch above.
                    leafletLayer = L.imageOverlay(layer.imageUrl, layer.bounds, {
                        opacity: layer.opacity / 100,
                        interactive: true,
                        alt: layer.name || 'GEE Fusion Result',
                    })
                    map.fitBounds(layer.bounds, { padding: [20, 20] })
                }

                if (leafletLayer) {
                    leafletLayer.addTo(map)
                    tileLayersRef.current[layer.id] = leafletLayer
                }
            }
        })

        // Remove layers that are no longer in mapLayers
        const currentLayerIds = mapLayers.map(l => l.id)
        Object.keys(tileLayersRef.current).forEach(id => {
            if (id === COMPARE_LAYER_ID) return  // owned by the M5 effect
            if (!currentLayerIds.includes(id)) {
                map.removeLayer(tileLayersRef.current[id])
                delete tileLayersRef.current[id]
            }
        })
    }, [mapLayers])



    // Update map when selected scene changes
    useEffect(() => {
        if (!mapInstanceRef.current || !selectedScene) return

        if (selectedScene.geometry && selectedScene.geometry.coordinates) {
            try {
                const geoJson = L.geoJSON(selectedScene.geometry)
                mapInstanceRef.current.fitBounds(geoJson.getBounds(), {
                    padding: [50, 50]
                })
            } catch (e) {
                console.log('Could not fit to scene bounds')
            }
        }
    }, [selectedScene])

    // Update map center when searching for places
    useEffect(() => {
        if (!mapInstanceRef.current || !mapCenter) return

        mapInstanceRef.current.flyTo(mapCenter, 12, {
            animate: true,
            duration: 1.5
        })
    }, [mapCenter])

    // Update active basemap tile layer dynamically when basemapId changes
    useEffect(() => {
        if (!mapInstanceRef.current) return
        const map = mapInstanceRef.current
        const conf = BASEMAP_BY_ID[basemapId || DEFAULT_BASEMAP_ID] || BASEMAP_BY_ID[DEFAULT_BASEMAP_ID]
        if (basemapLayerRef.current && map.hasLayer(basemapLayerRef.current)) {
            map.removeLayer(basemapLayerRef.current)
        }
        const newBasemap = L.tileLayer(conf.url, {
            attribution: conf.attribution,
            subdomains: 'abcd',
            maxZoom: conf.maxZoom || 20,
        }).addTo(map)
        basemapLayerRef.current = newBasemap
    }, [basemapId])

    // ── Phase 2 (M5): the swipe compare slot B layer. ─────────────────
    // A second L.tileLayer added on top of the active layer, with a
    // CSS clip-path that masks everything LEFT of the divider. The
    // divider position is `compare.dividerX` (0..1). The frame tileUrl
    // comes from `timeSeries.frames[compare.slotB]`. When compare is
    // disabled, the layer is removed.
    useEffect(() => {
        const map = mapInstanceRef.current
        if (!map) return

        const existing = tileLayersRef.current[COMPARE_LAYER_ID]

        if (!compare?.enabled || !timeSeries?.frames?.length) {
            if (existing) {
                map.removeLayer(existing)
                delete tileLayersRef.current[COMPARE_LAYER_ID]
            }
            return
        }

        const slotB = timeSeries.frames[compare.slotB]
        if (!slotB?.tileUrl) {
            // The slot B frame hasn't been minted yet (the per-frame loop
            // is still running). Don't add a broken tile layer.
            if (existing) {
                map.removeLayer(existing)
                delete tileLayersRef.current[COMPARE_LAYER_ID]
            }
            return
        }

        const clipPct = (compare.dividerX ?? 0.5) * 100
        if (existing) {
            // The URL may have changed (the slider moved slot B).
            if (existing._url !== slotB.tileUrl) {
                existing.setUrl(slotB.tileUrl)
            }
            // Apply the clip-path to the layer container.
            const container = existing.getContainer?.()
            if (container) {
                container.style.clipPath = `inset(0 0 0 ${clipPct}%)`
                container.style.webkitClipPath = `inset(0 0 0 ${clipPct}%)`
            }
        } else {
            const ll = L.tileLayer(slotB.tileUrl, {
                attribution: "GEE Compare (slot B)",
                opacity: 1.0,
                maxNativeZoom: 14,
                maxZoom: 20,
                tileSize: 256,
                detectRetina: false,
                zoomOffset: 0,
                keepBuffer: 8,
                updateWhenIdle: false,
                updateWhenZooming: false,
                fadeAnimation: false,
            })
            ll.addTo(map)
            tileLayersRef.current[COMPARE_LAYER_ID] = ll
            // Apply the clip-path on the next paint so the container exists.
            requestAnimationFrame(() => {
                const container = ll.getContainer?.()
                if (container) {
                    container.style.clipPath = `inset(0 0 0 ${clipPct}%)`
                    container.style.webkitClipPath = `inset(0 0 0 ${clipPct}%)`
                }
            })
        }
    }, [compare?.enabled, compare?.slotB, compare?.dividerX, timeSeries?.frames])

    // Render ASTRA-AI Alert Markers & Warning Polygons
    useEffect(() => {
        const map = mapInstanceRef.current
        if (!map) return

        if (!aiAlertsLayerRef.current) {
            aiAlertsLayerRef.current = L.layerGroup().addTo(map)
        }
        const layerGroup = aiAlertsLayerRef.current
        layerGroup.clearLayers()

        if (!aiAlerts) return

        // 1. Draw alert pins
        if (aiAlerts.pins && aiAlerts.pins.length) {
            aiAlerts.pins.forEach((pin) => {
                const color = pin.type === "water_loss" ? "#0284c7" : pin.type === "heat_island" ? "#f97316" : "#ef4444"
                const iconHtml = `<div style="background-color: ${color}; width: 24px; height: 24px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 10px ${color}; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 11px;">🚨</div>`
                const customIcon = L.divIcon({
                    html: iconHtml,
                    className: "ai-alert-pin",
                    iconSize: [24, 24],
                    iconAnchor: [12, 12],
                })
                const marker = L.marker([pin.lat, pin.lon], { icon: customIcon })
                marker.bindPopup(`<b>${pin.label}</b><br/>Area: ${pin.area_ha} hectares<br/>GPS: ${pin.lat}, ${pin.lon}`)
                layerGroup.addLayer(marker)
            })
        }

        // 2. Draw alert polygons
        if (aiAlerts.polygons && aiAlerts.polygons.length) {
            aiAlerts.polygons.forEach((poly) => {
                const latLngs = poly.coordinates.map(([lon, lat]) => [lat, lon])
                const polygon = L.polygon(latLngs, {
                    color: poly.color || "#ef4444",
                    weight: 3,
                    dashArray: "6, 6",
                    fillOpacity: 0.25,
                })
                polygon.bindPopup(`<b>${poly.label}</b>`)
                layerGroup.addLayer(polygon)
            })
        }
    }, [aiAlerts])

    // Layer control handlers
    const handleToggleLayer = useCallback((layerId) => {
        if (onLayerUpdate) {
            onLayerUpdate(layerId, 'toggle')
        }
    }, [onLayerUpdate])

    const handleOpacityChange = useCallback((layerId, opacity) => {
        if (onLayerUpdate) {
            onLayerUpdate(layerId, 'opacity', opacity)
        }
    }, [onLayerUpdate])

    const handleRemoveLayer = useCallback((layerId) => {
        if (onLayerUpdate) {
            onLayerUpdate(layerId, 'remove')
        }
    }, [onLayerUpdate])

    // Manual reset for AOI
    const handleResetMap = () => {
        if (drawnItemsRef.current) {
            drawnItemsRef.current.clearLayers()
        }
        onAoiChange(null)
    }

    return (
        <div className="map-container">
            <div ref={mapRef} className="map" />

            {/* Layer Control */}
            <LayerControl
                layers={mapLayers}
                onToggleLayer={handleToggleLayer}
                onOpacityChange={handleOpacityChange}
                onRemoveLayer={handleRemoveLayer}
            />

            {/* AOI info overlay */}
            {aoi && (
                <div className="aoi-info success fade-in">
                    <span>📍</span>
                    <span>
                        AOI: {aoi.min_lat.toFixed(2)}°N, {aoi.min_lon.toFixed(2)}°E
                    </span>
                    <button
                        onClick={handleResetMap}
                        style={{
                            background: '#ef4444',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            padding: '4px 8px',
                            marginLeft: '8px',
                            cursor: 'pointer',
                            fontSize: '0.75rem'
                        }}
                        title="Clear all drawings and reset"
                    >
                        🗑️ Clear
                    </button>
                </div>
            )}

            {!aoi && (
                <div className="aoi-info fade-in">
                    <span>✏️</span>
                    <span>Draw a rectangle to select Area of Interest</span>
                </div>
            )}

            {/* Coordinates display */}
            <div className="coordinates-display">
                Lat: {coords.lat}° | Lng: {coords.lng}°
            </div>

            {/* Compact Map Basemap Selector Box */}
            <div
                style={{
                    position: "absolute",
                    bottom: "14px",
                    right: "14px",
                    zIndex: 1000,
                    background: "rgba(15, 23, 42, 0.9)",
                    backdropFilter: "blur(8px)",
                    border: "1px solid rgba(148, 163, 184, 0.2)",
                    borderRadius: "8px",
                    padding: "4px",
                }}
            >
                <BasemapControl
                    value={basemapId || "dark"}
                    onChange={(id) => onBasemapChange?.(id)}
                />
            </div>

            {/* Time Slider (Phase 2) */}
            <TimeSlider />
            {/* Swipe compare overlay (Phase 2 M5) — divider + badges. */}
            <SwipeCompare />
        </div>
    )
}

export default Map
