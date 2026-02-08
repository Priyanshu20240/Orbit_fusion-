import React, { useState, useCallback, useMemo } from 'react'
import Map from './components/Map'
import Sidebar from './components/Sidebar'
import TypingIntro from './components/TypingIntro'
import Loader from './components/Loader'

function App() {
    // Intro state
    const [showIntro, setShowIntro] = useState(false)


    // AOI (Area of Interest) state
    const [aoi, setAoi] = useState(null)

    // Date range state
    const [dateRange, setDateRange] = useState({
        startDate: '2024-01-01',
        endDate: '2024-12-31'
    })

    // Active satellites
    const [activeSatellites, setActiveSatellites] = useState({
        sentinel: true,
        landsat: true,
        bhuvan: false
    })

    // Search results
    const [searchResults, setSearchResults] = useState({
        sentinel: [],
        landsat: [],
        bhuvan: []
    })

    // Loading state
    const [isLoading, setIsLoading] = useState(false)

    // Selected scene
    const [selectedScene, setSelectedScene] = useState(null)

    // Map layers (Phase 2)
    const [mapLayers, setMapLayers] = useState([])

    // Fusion state
    const [isProcessingFusion, setIsProcessingFusion] = useState(false)
    const [activeVisualization, setActiveVisualization] = useState('true_color'); // Track current viz mode

    // Time-lapse state (Phase 4)
    const [isTimeLapsePlaying, setIsTimeLapsePlaying] = useState(false)

    // Map Center state (for search navigation)
    const [mapCenter, setMapCenter] = useState(null)

    // Dataset Mode state
    const [isDatasetMode, setIsDatasetMode] = useState(false)
    const [datasetPath, setDatasetPath] = useState('datasets')



    // Get all scenes for time-lapse - Memoized to prevent re-renders
    const allScenes = useMemo(() =>
        [...searchResults.sentinel, ...searchResults.landsat],
        [searchResults.sentinel, searchResults.landsat]
    )

    // Handle AOI selection from map
    const handleAoiChange = useCallback((input) => {
        if (input) {
            // Check if input is just bounds (legacy) or object with geojson
            const bounds = input.bounds || input
            const geojson = input.geojson || null

            setAoi({
                min_lon: bounds.getWest(),
                min_lat: bounds.getSouth(),
                max_lon: bounds.getEast(),
                max_lat: bounds.getNorth(),
                geojson: geojson
            })
        } else {
            setAoi(null)
            // Clear search results when AOI is removed
            setSearchResults({
                sentinel: [],
                landsat: [],
                bhuvan: []
            })
            // Also clear selection
            setSelectedScene(null)
        }
    }, [])

    // Handle Map Navigation
    const handleNavigate = (lat, lon) => {
        setMapCenter([lat, lon])
    }

    // Search for satellite data
    const handleSearch = async () => {
        if (!aoi) {
            alert('Please draw an Area of Interest on the map first!')
            return
        }

        setIsLoading(true)
        setSearchResults({ sentinel: [], landsat: [], bhuvan: [] })

        try {
            const response = await fetch('/api/search/all', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    bbox: aoi,
                    start_date: dateRange.startDate,
                    end_date: dateRange.endDate,
                    max_cloud_cover: 30,
                    limit: 10
                })
            })

            if (!response.ok) {
                throw new Error('Search failed')
            }

            const data = await response.json()

            setSearchResults({
                sentinel: data.sentinel?.scenes || [],
                landsat: data.landsat?.scenes || [],
                bhuvan: Object.values(data.bhuvan?.layers || {})
            })
        } catch (error) {
            console.error('Search error:', error)
            alert('Failed to search for satellite data. Make sure the backend is running.')
        } finally {
            setIsLoading(false)
        }
    }

    // Toggle satellite visibility
    const toggleSatellite = (satellite) => {
        setActiveSatellites(prev => ({
            ...prev,
            [satellite]: !prev[satellite]
        }))
    }



    // Handle GEE Geographic Windowing Fusion
    const handleGEEFusion = async (visualization = 'true_color') => {
        if (!aoi) {
            alert('Please draw an Area of Interest on the map first!');
            return;
        }

        setActiveVisualization(visualization); // Update state on click
        setIsProcessingFusion(true);

        try {
            // Convert AOI to bounds array [west, south, east, north]
            const bounds = [aoi.min_lon, aoi.min_lat, aoi.max_lon, aoi.max_lat];

            console.log("Starting GEE Fusion with bounds:", bounds);
            console.log("Date range:", dateRange);

            // Get active platforms
            const platforms = Object.keys(activeSatellites).filter(k => activeSatellites[k] && ['sentinel', 'landsat'].includes(k));

            if (platforms.length === 0) {
                alert("Please select at least one satellite (Sentinel-2 or Landsat 8/9)");
                setIsProcessingFusion(false);
                return;
            }

            const response = await fetch('/api/fusion/gee-harmonize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    bounds: bounds,
                    geojson: aoi.geojson, // Send custom shape if available
                    start_date: dateRange.startDate,
                    end_date: dateRange.endDate,
                    window_size: 256,
                    cloud_cover: 20,
                    visualization: visualization,
                    platforms: platforms,
                    create_dataset: isDatasetMode,
                    destination_folder: datasetPath
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'GEE Fusion failed');
            }

            const result = await response.json();
            console.log("GEE Fusion result:", result);

            // Handle Dataset Download / Save
            if (isDatasetMode && result.dataset_path) {
                // Alert that server save is done
                alert(`✅ Dataset Saved to Session Folder!\n\nFolder: ${datasetPath || 'datasets'}\nFile: ${result.dataset_path}\n\nContinue generating more datasets for this session.`);
            }



            // Continue to visualization...

            // Add as an imageOverlay layer (PNG image at specific bounds)
            const fusionLayer = {
                id: `gee-fusion-${Date.now()}`,
                name: '🛰️ GEE Fusion (Sentinel + Landsat)',
                satellite: 'fusion',
                imageUrl: result.imageUrl.startsWith('http')
                    ? result.imageUrl
                    : `http://localhost:8000${result.imageUrl}?t=${Date.now()}`,
                bounds: result.bounds, // [[south, west], [north, east]]
                type: 'imageOverlay',
                visible: true,
                opacity: 100
            };

            setMapLayers(prev => {
                // Remove previous GEE Fusion layers to prevent stacking/dimming
                const filtered = prev.filter(l => !l.id.startsWith('gee-fusion-'));
                return [...filtered, fusionLayer];
            });

            let message = `✅ ${platforms.length > 1 ? 'Fusion' : 'Processing'} Complete!\n`;
            if (platforms.includes('sentinel')) message += `Sentinel bands: ${result.num_sentinel_bands}\n`;
            if (platforms.includes('landsat')) message += `Landsat bands: ${result.num_landsat_bands || result.total_bands}\n`; // Fallback for single landsat
            message += `Visualization: ${visualization}`;

            alert(message);

        } catch (error) {
            console.error('GEE Fusion error:', error);
            // Show more detailed error if available
            alert(`GEE Fusion failed: ${error.message || error.detail || JSON.stringify(error)}`);
        } finally {
            setIsProcessingFusion(false);
        }
    }

    // Handle Timelapse Generation
    const handleTimelapse = async (visualizationType = 'true_color') => {
        if (!aoi) {
            alert('Please draw an Area of Interest on the map first!');
            return;
        }

        const platform = activeSatellites.sentinel ? 'sentinel' : (activeSatellites.landsat ? 'landsat' : null);
        if (!platform) {
            alert("Please select a satellite (Sentinel-2 or Landsat) for timelapse.");
            return;
        }

        setIsProcessingFusion(true); // Reuse loading state for now

        try {
            const bounds = [aoi.min_lon, aoi.min_lat, aoi.max_lon, aoi.max_lat];

            alert(`🎬 Generating ${visualizationType.toUpperCase()} Timelapse for ${platform.toUpperCase()}...\nCheck dates: ${dateRange.startDate} to ${dateRange.endDate}\nThis may take 10-20 seconds.`);

            const response = await fetch('/api/fusion/timelapse', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    bounds: bounds,
                    geojson: aoi.geojson, // Send custom shape
                    start_date: dateRange.startDate,
                    end_date: dateRange.endDate,
                    platform: platform,
                    visualization: visualizationType
                })
            });

            if (!response.ok) {
                const errorText = await response.text();
                try {
                    const error = JSON.parse(errorText);
                    throw new Error(error.detail || 'Timelapse failed');
                } catch (e) {
                    throw new Error(`Timelapse failed: ${response.status} ${response.statusText} - ${errorText}`);
                }
            }

            const result = await response.json();
            console.log("Timelapse Result:", result);

            if (result && result.success && result.url) {
                window.open(result.url, '_blank');
            } else {
                throw new Error(result?.error || 'No URL returned (Result is null or invalid)');
            }

        } catch (error) {
            console.error('Timelapse error:', error);
            alert(`Timelapse failed: ${error.message}`);
        } finally {
            setIsProcessingFusion(false);
        }
    }

    // Handle layer updates (toggle, opacity, remove)
    const handleLayerUpdate = (layerId, action, value) => {
        setMapLayers(prev => {
            if (action === 'toggle') {
                return prev.map(layer =>
                    layer.id === layerId
                        ? { ...layer, visible: !layer.visible }
                        : layer
                )
            }
            if (action === 'opacity') {
                return prev.map(layer =>
                    layer.id === layerId
                        ? { ...layer, opacity: value }
                        : layer
                )
            }
            if (action === 'remove') {
                return prev.filter(layer => layer.id !== layerId)
            }
            return prev
        })
    }

    return (
        <div className="app">
            <Loader isLoading={isLoading} />
            <Sidebar
                aoi={aoi}
                dateRange={dateRange}
                setDateRange={setDateRange}
                activeSatellites={activeSatellites}
                toggleSatellite={toggleSatellite}
                searchResults={searchResults}
                selectedScene={selectedScene}
                setSelectedScene={setSelectedScene}
                onSearch={handleSearch}
                isLoading={isLoading}
                onGEEFusion={handleGEEFusion}
                onTimelapse={handleTimelapse}
                onNavigate={handleNavigate}
                isProcessingFusion={isProcessingFusion}
                isDatasetMode={isDatasetMode}
                setIsDatasetMode={setIsDatasetMode}
                datasetPath={datasetPath}
                setDatasetPath={setDatasetPath}
            />
            <Map
                aoi={aoi}
                onAoiChange={handleAoiChange}
                selectedScene={selectedScene}
                activeSatellites={activeSatellites}
                isLoading={isLoading}
                mapLayers={mapLayers}
                onLayerUpdate={handleLayerUpdate}
                scenes={allScenes}
                isTimeLapsePlaying={isTimeLapsePlaying}
                onTimeLapseToggle={() => setIsTimeLapsePlaying(prev => !prev)}
                onTimeSliderChange={setSelectedScene}
                mapCenter={mapCenter}
                isDatasetMode={isDatasetMode}
                setIsDatasetMode={setIsDatasetMode}
            />
        </div>
    )
}

export default App
