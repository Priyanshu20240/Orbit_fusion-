import { useEffect, useRef, useState, useCallback } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import 'leaflet-draw'
import 'leaflet-draw/dist/leaflet.draw.css'
import LayerControl from './LayerControl'


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

function Map({ aoi, onAoiChange, selectedScene, activeSatellites, isLoading, mapLayers, onLayerUpdate, scenes, isTimeLapsePlaying, onTimeLapseToggle, onTimeSliderChange, mapCenter, isDatasetMode, setIsDatasetMode }) {
    const mapRef = useRef(null)
    const mapInstanceRef = useRef(null)
    const drawnItemsRef = useRef(null)
    const tileLayersRef = useRef({}) // Store tile layers by ID
    const [coords, setCoords] = useState({ lat: 0, lng: 0 })

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

        // Add dark tile layer (CartoDB Dark Matter)
        // Add Light tile layer (CartoDB Positron) - "White Map"
        // Add Light tile layer (CartoDB Positron) - "White Map"
        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 20,
            className: 'dim-tiles' // Custom class for brightness control
        }).addTo(map)

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
                onAoiChange(null)
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
                onAoiChange({
                    bounds: bounds,
                    geojson: geojson
                })
            }
        }

        // Handle draw start - Clear existing items for fresh start
        map.on(L.Draw.Event.DRAWSTART, () => {
            drawnItems.clearLayers()
            onAoiChange(null)
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

        // Track mouse position
        map.on('mousemove', (e) => {
            setCoords({
                lat: e.latlng.lat.toFixed(4),
                lng: e.latlng.lng.toFixed(4)
            })
        })

        mapInstanceRef.current = map

        return () => {
            map.remove()
            mapInstanceRef.current = null
        }
    }, [onAoiChange])

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
                } else {
                    if (map.hasLayer(existingLayer)) {
                        map.removeLayer(existingLayer)
                    }
                }
            } else if (layer.visible) {
                // Create new layer based on type
                let leafletLayer

                if (layer.type === 'imageOverlay' && layer.imageUrl && layer.bounds) {
                    // GEE Fusion - Image Overlay at specific geographic bounds
                    // Bounds format: [[south, west], [north, east]]
                    leafletLayer = L.imageOverlay(layer.imageUrl, layer.bounds, {
                        opacity: layer.opacity / 100,
                        interactive: true,
                        alt: layer.name || 'GEE Fusion Result'
                    })

                    // Auto-zoom to the image bounds
                    map.fitBounds(layer.bounds, { padding: [20, 20] })

                } else if (layer.type === 'wms' && layer.tileUrl) {
                    // WMS layer for Bhuvan
                    leafletLayer = L.tileLayer.wms(layer.tileUrl.split('?')[0], {
                        layers: layer.layerId || 'india_sat',
                        format: 'image/png',
                        transparent: true,
                        attribution: 'ISRO Bhuvan',
                        opacity: layer.opacity / 100
                    })
                } else if (layer.tileUrl) {
                    // XYZ tile layer for Sentinel/Landsat
                    let attribution = 'Sentinel-2 / ESA'
                    if (layer.satellite === 'landsat') {
                        attribution = 'Landsat / NASA'
                    } else if (layer.type === 'fusion') {
                        attribution = 'Fused Multi-Satellite Data'
                    } else if (layer.satellite === 'gee-fusion') {
                        attribution = 'GEE Harmonized Fusion'
                    }
                    leafletLayer = L.tileLayer(layer.tileUrl, {
                        attribution: attribution,
                        opacity: layer.opacity / 100,
                        maxZoom: 18,
                        tileSize: 256,       // FIX 1: Lock tile size
                        detectRetina: false, // FIX 1: Disable retina
                        zoomOffset: 0,       // FIX 1: No zoom offset
                        keepBuffer: 8,       // FIX 1: Large buffer
                        updateWhenIdle: false,    // FIX 1: Prevent white flash
                        updateWhenZooming: false, // FIX 1: Prevent blur
                        fadeAnimation: false      // FIX 1: No fade

                    })
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



            {/* Time Slider */}

        </div>
    )
}

export default Map
