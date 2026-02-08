

import React from 'react'

function Sidebar({
    aoi,
    dateRange,
    setDateRange,
    activeSatellites,
    toggleSatellite,
    searchResults,
    selectedScene,
    setSelectedScene,
    onSearch,
    isLoading,
    onGEEFusion,
    onTimelapse,
    onNavigate,
    isProcessingFusion,
    isDatasetMode,
    setIsDatasetMode,
    datasetPath,
    setDatasetPath
}) {
    // Format date for display
    const formatDate = (dateString) => {
        if (!dateString) return 'N/A'
        const date = new Date(dateString)
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        })
    }

    // Get cloud cover class
    const getCloudClass = (cloudCover) => {
        if (cloudCover < 10) return 'cloud-low'
        if (cloudCover < 30) return 'cloud-medium'
        return 'cloud-high'
    }

    // Count total results
    const totalResults =
        searchResults.sentinel.length +
        searchResults.landsat.length +
        searchResults.bhuvan.length

    return (
        <aside className="sidebar">
            {/* Header */}
            <div className="sidebar-header">
                <h1>🛰️ Orbiter Fusion</h1>
                <p>Multi-Satellite Data Dashboard</p>
            </div>

            <div className="sidebar-content">
                {/* Place Search */}
                <section className="section">
                    <h3 className="section-title">Discover Places</h3>
                    <div className="form-group" style={{ position: 'relative' }}>
                        <input
                            type="text"
                            className="form-input"
                            placeholder="🔍 Search for a place (e.g. New York)"
                            onKeyDown={async (e) => {
                                if (e.key === 'Enter') {
                                    const query = e.target.value;
                                    if (!query) return;

                                    try {
                                        const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}`);
                                        const data = await res.json();

                                        if (data && data.length > 0) {
                                            const place = data[0];
                                            const lat = parseFloat(place.lat);
                                            const lon = parseFloat(place.lon);
                                            // Call onNavigate (need to add this prop)
                                            if (onNavigate) {
                                                onNavigate(lat, lon);
                                            }
                                        } else {
                                            alert("Place not found!");
                                        }
                                    } catch (err) {
                                        console.error("Geocoding error", err);
                                        alert("Failed to search place.");
                                    }
                                }
                            }}
                        />
                        <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                            Press Enter to search
                        </p>
                    </div>
                </section>

                {/* Satellite Selection */}
                <section className="section">
                    <h3 className="section-title">Data Sources</h3>
                    <div className="satellite-toggles">
                        <button
                            className={`satellite-btn ${activeSatellites.sentinel ? 'active' : ''}`}
                            onClick={() => toggleSatellite('sentinel')}
                        >
                            <span>🌍</span>
                            Sentinel-2
                        </button>
                        <button
                            className={`satellite-btn ${activeSatellites.landsat ? 'active' : ''}`}
                            onClick={() => toggleSatellite('landsat')}
                        >
                            <span>🌎</span>
                            Landsat 8/9
                        </button>
                        <button
                            className={`satellite-btn ${activeSatellites.bhuvan ? 'active' : ''}`}
                            onClick={() => toggleSatellite('bhuvan')}
                        >
                            <span>🇮🇳</span>
                            ISRO
                        </button>
                    </div>
                </section>

                {/* Date Range */}
                <section className="section">
                    <h3 className="section-title">Date Range 🗓️</h3>
                    <style>{`
                        .date-card {
                            background: linear-gradient(180deg, rgba(15, 23, 42, 0.85), rgba(2, 6, 23, 0.95)) !important;
                            padding: 18px !important;
                            border-radius: 16px !important;
                            box-shadow: 0 0 0 1px rgba(255,255,255,0.06), 0 20px 40px rgba(0,0,0,0.5) !important;
                            margin-bottom: 16px !important;
                        }
                        .date-group {
                            display: flex;
                            flex-direction: column;
                            gap: 6px;
                            margin-bottom: 14px;
                        }
                        .date-group label {
                            font-size: 0.7rem;
                            letter-spacing: 0.12em;
                            text-transform: uppercase;
                            color: #94a3b8;
                            font-weight: 600;
                        }
                        .date-group input[type="date"] {
                            background: rgba(2, 6, 23, 0.8) !important;
                            border: 1px solid rgba(255,255,255,0.08) !important;
                            border-radius: 12px !important;
                            padding: 12px 14px !important;
                            color: #e5e7eb !important;
                            font-size: 0.9rem !important;
                            font-family: "JetBrains Mono", monospace, sans-serif !important;
                            transition: all 0.25s ease !important;
                            width: 100% !important;
                            outline: none !important;
                        }
                        .date-group input[type="date"]::-webkit-calendar-picker-indicator {
                            filter: invert(1);
                            opacity: 0.6;
                            cursor: pointer;
                        }
                        .date-group input[type="date"]:hover {
                            border-color: rgba(56, 189, 248, 0.35) !important;
                        }
                        .date-group input[type="date"]:focus {
                            border-color: #38bdf8 !important;
                            box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.6), 0 0 18px rgba(56, 189, 248, 0.35) !important;
                            background: rgba(2, 6, 23, 0.95) !important;
                        }
                        /* OrbitFusion Accent Variants */
                        .date-group input[type="date"][data-type="start"]:focus {
                            border-color: #22c55e !important;
                            box-shadow: 0 0 18px rgba(34,197,94,0.45) !important;
                        }
                        .date-group input[type="date"][data-type="end"]:focus {
                            border-color: #9333ea !important;
                            box-shadow: 0 0 18px rgba(147,51,234,0.45) !important;
                        }
                    `}</style>
                    <div className="date-card">
                        <div className="date-group">
                            <label>Start Date</label>
                            <input
                                type="date"
                                value={dateRange.startDate}
                                onChange={(e) => setDateRange(prev => ({
                                    ...prev,
                                    startDate: e.target.value
                                }))}
                                data-type="start"
                            />
                        </div>

                        <div className="date-group">
                            <label>End Date</label>
                            <input
                                type="date"
                                value={dateRange.endDate}
                                onChange={(e) => setDateRange(prev => ({
                                    ...prev,
                                    endDate: e.target.value
                                }))}
                                data-type="end"
                            />
                        </div>
                    </div>
                </section>

                {/* Tools Toolbar */}
                <section className="section">
                    <h3 className="section-title">Tools</h3>
                    <button
                        onClick={() => setIsDatasetMode(!isDatasetMode)}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: '8px',
                            width: '100%',
                            padding: '12px 16px',
                            background: isDatasetMode 
                                ? 'rgba(34, 197, 94, 0.2)' 
                                : 'rgba(59, 130, 246, 0.1)',
                            border: isDatasetMode
                                ? '2px solid rgba(34, 197, 94, 0.5)'
                                : '1px solid rgba(59, 130, 246, 0.2)',
                            borderRadius: '8px',
                            color: 'var(--text-primary)',
                            fontWeight: 500,
                            fontSize: '0.85rem',
                            cursor: 'pointer',
                            transition: 'all 0.3s ease',
                            textAlign: 'center'
                        }}
                        onMouseEnter={(e) => {
                            e.target.style.background = isDatasetMode 
                                ? 'rgba(34, 197, 94, 0.3)' 
                                : 'rgba(59, 130, 246, 0.15)';
                            e.target.style.boxShadow = isDatasetMode
                                ? '0 0 12px rgba(34, 197, 94, 0.2)'
                                : '0 0 12px rgba(59, 130, 246, 0.2)';
                        }}
                        onMouseLeave={(e) => {
                            e.target.style.background = isDatasetMode 
                                ? 'rgba(34, 197, 94, 0.2)' 
                                : 'rgba(59, 130, 246, 0.1)';
                            e.target.style.boxShadow = 'none';
                        }}
                    >
                        <span style={{ fontSize: '1.2rem' }}>💾</span>
                        <span>Save Dataset</span>
                    </button>
                </section>

                {/* Search Button */}
                <button
                    className="btn btn-primary btn-block"
                    onClick={onSearch}
                    disabled={isLoading}
                    style={{
                        marginTop: '12px',
                        marginBottom: '16px'
                    }}
                >
                    {isLoading ? '🔄 Searching...' : '🔍 Search'}
                </button>

                {/* Results */}
                {totalResults > 0 && (
                    <section className="section">
                        <h3 className="section-title">
                            Results ({totalResults} scenes)
                        </h3>

                        {/* Merge and Load Image Button - GEE Fusion */}
                        {aoi && (
                            <div style={{ marginBottom: '16px' }}>

                                {/* Session Manager (Zip Download) */}
                                {isDatasetMode && (
                                    <div style={{
                                        marginBottom: '10px',
                                        padding: '10px',
                                        background: 'rgba(255,255,255,0.05)',
                                        borderRadius: '8px',
                                        border: '1px solid var(--border-color)'
                                    }}>
                                        <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                                            Session Name (Folder):
                                        </label>
                                        <div style={{ display: 'flex', gap: '8px' }}>
                                            <input
                                                type="text"
                                                className="form-input"
                                                value={datasetPath}
                                                onChange={(e) => setDatasetPath(e.target.value)}
                                                placeholder="My_Session_1"
                                                style={{ fontSize: '0.85rem', padding: '8px', flex: 1 }}
                                            />
                                        </div>

                                        {/* Download Zip Button */}
                                        <button
                                            className="btn btn-secondary btn-block"
                                            style={{
                                                marginTop: '8px',
                                                fontSize: '0.8rem',
                                                padding: '6px',
                                                background: datasetPath ? 'var(--accent-primary)' : 'var(--bg-secondary)',
                                                color: datasetPath ? 'white' : 'var(--text-muted)',
                                                cursor: datasetPath ? 'pointer' : 'not-allowed'
                                            }}
                                            onClick={() => {
                                                if (!datasetPath) return;
                                                const url = `/api/datasets/download-zip?folder=${encodeURIComponent(datasetPath)}`;
                                                window.location.href = url;
                                            }}
                                            disabled={!datasetPath}
                                        >
                                            📦 Download Session Zip
                                        </button>
                                        <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                                            Generates a .zip of all files in this folder.
                                        </p>
                                    </div>
                                )}

                                <button
                                    className="btn btn-primary btn-block"
                                    style={{
                                        marginBottom: '12px',
                                        background: 'linear-gradient(135deg, #4CAF50, #2196F3)',
                                        border: 'none',
                                        padding: '14px',
                                        fontSize: '1rem',
                                        fontWeight: '600'
                                    }}
                                    onClick={() => onGEEFusion && onGEEFusion('true_color')}
                                    disabled={isProcessingFusion}
                                >
                                    {isProcessingFusion ? '⏳ Processing...' :
                                        (activeSatellites.sentinel && activeSatellites.landsat) ? '🛰️ Merge and Load Image' :
                                            (activeSatellites.sentinel) ? '🌍 Load Sentinel-2' :
                                                (activeSatellites.landsat) ? '🌎 Load Landsat 8/9' :
                                                    '⚠️ Select a Satellite'}
                                </button>

                                {/* Visualization Options */}
                                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                                    <button
                                        className="btn btn-secondary"
                                        style={{ flex: 1, minWidth: '80px', fontSize: '0.75rem', padding: '8px' }}
                                        onClick={() => onGEEFusion && onGEEFusion('ndvi')}
                                        disabled={isProcessingFusion}
                                        title="Normalized Difference Vegetation Index"
                                    >
                                        🌿 NDVI
                                    </button>
                                    <button
                                        className="btn btn-secondary"
                                        style={{ flex: 1, minWidth: '80px', fontSize: '0.75rem', padding: '8px' }}
                                        onClick={() => onGEEFusion && onGEEFusion('false_color_swir')}
                                        disabled={isProcessingFusion}
                                        title="SWIR False Color (Geology/Urban)"
                                    >
                                        🏔️ SWIR
                                    </button>
                                    <button
                                        className="btn btn-secondary"
                                        style={{ flex: 1, minWidth: '80px', fontSize: '0.75rem', padding: '8px' }}
                                        onClick={() => onGEEFusion && onGEEFusion('ndbi')}
                                        disabled={isProcessingFusion}
                                        title="Built-up Areas & Urban Growth"
                                    >
                                        🏢 NDBI
                                    </button>
                                    <button
                                        className="btn btn-secondary"
                                        style={{ flex: 1, minWidth: '80px', fontSize: '0.75rem', padding: '8px' }}
                                        onClick={() => onGEEFusion && onGEEFusion('ndwi')}
                                        disabled={isProcessingFusion}
                                        title="Water & Wetlands"
                                    >
                                        💧 NDWI
                                    </button>
                                    <button
                                        className="btn btn-secondary"
                                        style={{ flex: 1, minWidth: '80px', fontSize: '0.75rem', padding: '8px' }}
                                        onClick={() => onGEEFusion && onGEEFusion('lst')}
                                        disabled={isProcessingFusion}
                                        title="Surface Temperature Mapping"
                                    >
                                        🌡️ LST
                                    </button>
                                </div>

                                {/* Timelapse Section - Active after search */}
                                {totalResults > 0 && (
                                <div style={{ 
                                    background: 'rgba(139, 92, 246, 0.1)',
                                    border: '2px solid rgba(139, 92, 246, 0.5)',
                                    borderRadius: '12px',
                                    padding: '12px',
                                    marginTop: '12px',
                                    animation: 'slideDown 0.4s ease-out',
                                    boxShadow: '0 0 20px rgba(139, 92, 246, 0.2)'
                                }}>
                                    <style>{`
                                        @keyframes slideDown {
                                            from {
                                                opacity: 0;
                                                transform: translateY(-10px);
                                            }
                                            to {
                                                opacity: 1;
                                                transform: translateY(0);
                                            }
                                        }
                                    `}</style>
                                    <p style={{
                                        fontSize: '0.8rem',
                                        fontWeight: '600',
                                        color: 'var(--accent-secondary)',
                                        marginBottom: '10px',
                                        textAlign: 'center'
                                    }}>
                                        🎬 Generate Timelapse Analysis
                                    </p>
                                    
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                                        {/* True Color (RGB) */}
                                        <button
                                            className="btn btn-secondary"
                                            style={{
                                                fontSize: '0.75rem',
                                                padding: '10px 8px',
                                                background: 'linear-gradient(135deg, rgba(255, 193, 7, 0.4), rgba(233, 30, 99, 0.4))',
                                                border: '1px solid rgba(255, 193, 7, 0.3)',
                                                color: '#ffeeba'
                                            }}
                                            onClick={() => onTimelapse && onTimelapse('true_color')}
                                            disabled={isProcessingFusion || !aoi}
                                            title="Visual Baseline"
                                        >
                                            🌈 True Color<br/>(RGB)
                                        </button>

                                        {/* NDVI */}
                                        <button
                                            className="btn btn-secondary"
                                            style={{
                                                fontSize: '0.75rem',
                                                padding: '10px 8px',
                                                background: 'linear-gradient(135deg, rgba(34, 197, 94, 0.4), rgba(16, 185, 129, 0.4))',
                                                border: '1px solid rgba(34, 197, 94, 0.3)',
                                                color: '#86efac'
                                            }}
                                            onClick={() => onTimelapse && onTimelapse('ndvi')}
                                            disabled={isProcessingFusion || !aoi}
                                            title="Vegetation & Health"
                                        >
                                            🌿 NDVI<br/>(Vegetation)
                                        </button>

                                        {/* SWIR */}
                                        <button
                                            className="btn btn-secondary"
                                            style={{
                                                fontSize: '0.75rem',
                                                padding: '10px 8px',
                                                background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.4), rgba(244, 114, 182, 0.4))',
                                                border: '1px solid rgba(239, 68, 68, 0.3)',
                                                color: '#fca5a5'
                                            }}
                                            onClick={() => onTimelapse && onTimelapse('false_color_swir')}
                                            disabled={isProcessingFusion || !aoi}
                                            title="Moisture, Fire & Stress"
                                        >
                                            🔥 SWIR<br/>(Moisture)
                                        </button>

                                        {/* NDVI Change (Delta NDVI) */}
                                        <button
                                            className="btn btn-secondary"
                                            style={{
                                                fontSize: '0.75rem',
                                                padding: '10px 8px',
                                                background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.4), rgba(139, 92, 246, 0.4))',
                                                border: '1px solid rgba(59, 130, 246, 0.3)',
                                                color: '#93c5fd'
                                            }}
                                            onClick={() => onTimelapse && onTimelapse('ndvi_change')}
                                            disabled={isProcessingFusion || !aoi}
                                            title="Impact Analysis"
                                        >
                                            📊 ΔNDVI<br/>(Change)
                                        </button>

                                        {/* NDBI - Built-up Index */}
                                        <button
                                            className="btn btn-secondary"
                                            style={{
                                                fontSize: '0.75rem',
                                                padding: '10px 8px',
                                                background: 'linear-gradient(135deg, rgba(107, 114, 128, 0.4), rgba(75, 85, 99, 0.4))',
                                                border: '1px solid rgba(107, 114, 128, 0.3)',
                                                color: '#d1d5db'
                                            }}
                                            onClick={() => onTimelapse && onTimelapse('ndbi')}
                                            disabled={isProcessingFusion || !aoi}
                                            title="Built-up Areas & Urban Growth"
                                        >
                                            🏢 NDBI<br/>(Built-up)
                                        </button>

                                        {/* NDWI - Water Index */}
                                        <button
                                            className="btn btn-secondary"
                                            style={{
                                                fontSize: '0.75rem',
                                                padding: '10px 8px',
                                                background: 'linear-gradient(135deg, rgba(6, 182, 212, 0.4), rgba(34, 197, 94, 0.4))',
                                                border: '1px solid rgba(6, 182, 212, 0.3)',
                                                color: '#67e8f9'
                                            }}
                                            onClick={() => onTimelapse && onTimelapse('ndwi')}
                                            disabled={isProcessingFusion || !aoi}
                                            title="Water & Wetlands"
                                        >
                                            💧 NDWI<br/>(Water)
                                        </button>

                                        {/* LST - Land Surface Temperature */}
                                        <button
                                            className="btn btn-secondary"
                                            style={{
                                                fontSize: '0.75rem',
                                                padding: '10px 8px',
                                                background: 'linear-gradient(135deg, rgba(244, 63, 94, 0.4), rgba(251, 146, 60, 0.4))',
                                                border: '1px solid rgba(244, 63, 94, 0.3)',
                                                color: '#fca5a5'
                                            }}
                                            onClick={() => onTimelapse && onTimelapse('lst')}
                                            disabled={isProcessingFusion || !aoi}
                                            title="Surface Temperature Mapping"
                                        >
                                            🌡️ LST<br/>(Temperature)
                                        </button>

                                        {/* False Color NIR */}
                                        <button
                                            className="btn btn-secondary"
                                            style={{
                                                fontSize: '0.75rem',
                                                padding: '10px 8px',
                                                background: 'linear-gradient(135deg, rgba(168, 85, 247, 0.4), rgba(236, 72, 153, 0.4))',
                                                border: '1px solid rgba(168, 85, 247, 0.3)',
                                                color: '#d8b4fe'
                                            }}
                                            onClick={() => onTimelapse && onTimelapse('false_color_nir')}
                                            disabled={isProcessingFusion || !aoi}
                                            title="NIR False Color"
                                        >
                                            👁️ NIR FC<br/>(NIR False)
                                        </button>
                                    </div>
                                </div>
                                )}
                            </div>
                        )}

                        {/* Bhuvan Layers */}
                        {searchResults.bhuvan.length > 0 && activeSatellites.bhuvan && (
                            <div style={{ marginBottom: '16px' }}>
                                <p style={{
                                    fontSize: '0.8rem',
                                    fontWeight: 600,
                                    color: 'var(--accent-warning)',
                                    marginBottom: '8px'
                                }}>
                                    🇮🇳 ISRO Bhuvan ({searchResults.bhuvan.length})
                                </p>
                                <div className="scene-list">
                                    {searchResults.bhuvan.map((layer, idx) => (
                                        <div
                                            key={idx}
                                            className="scene-item"
                                            style={{ cursor: 'default' }}
                                        >
                                            <div className="scene-thumbnail" style={{
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'center',
                                                fontSize: '1.5rem',
                                                background: 'var(--bg-secondary)'
                                            }}>🗺️</div>
                                            <div className="scene-info">
                                                <div className="scene-date">{layer.name}</div>
                                                <div className="scene-meta">{layer.description}</div>
                                            </div>
                                            <span className="cloud-badge" style={{
                                                background: 'rgba(245, 158, 11, 0.2)',
                                                color: 'var(--accent-warning)'
                                            }}>
                                                WMS
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </section>
                )}

                {/* Selected Scene Details */}
                {selectedScene && (
                    <section className="section">
                        <h3 className="section-title">Selected Scene</h3>
                        <div className="card">
                            <p style={{ fontWeight: 600, marginBottom: '8px' }}>
                                {selectedScene.satellite}
                            </p>
                            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                                📅 {formatDate(selectedScene.datetime)}
                            </p>
                            {selectedScene.cloud_cover !== null && (
                                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                                    ☁️ Cloud Cover: {Math.round(selectedScene.cloud_cover)}%
                                </p>
                            )}
                            {selectedScene.bands && (
                                <p style={{
                                    fontSize: '0.75rem',
                                    color: 'var(--text-muted)',
                                    marginTop: '8px'
                                }}>
                                    Bands: {Object.keys(selectedScene.bands).join(', ')}
                                </p>
                            )}

                            {selectedScene.download_url && (
                                <a
                                    href={selectedScene.download_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="btn btn-secondary btn-block"
                                    style={{ marginTop: '8px', textDecoration: 'none' }}
                                >
                                    ⬇️ View Full Image
                                </a>
                            )}
                        </div>
                    </section>
                )}

            </div>
        </aside>
    )
}



export default Sidebar
