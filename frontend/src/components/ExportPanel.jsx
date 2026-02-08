import { useState } from 'react'

function ExportPanel({ selectedScene, mapLayers }) {
    const [exportFormat, setExportFormat] = useState('png')
    const [isExporting, setIsExporting] = useState(false)
    const [exportStatus, setExportStatus] = useState(null)

    const handleExport = async () => {
        if (!selectedScene && mapLayers.length === 0) {
            alert('No scene or layers selected for export')
            return
        }

        setIsExporting(true)
        setExportStatus('Preparing export...')

        try {
            // Simulate export process
            await new Promise(resolve => setTimeout(resolve, 1500))

            // In production, this would call the backend export API
            const exportUrl = selectedScene?.download_url || '#'

            if (exportFormat === 'png') {
                setExportStatus('Generating PNG...')
                await new Promise(resolve => setTimeout(resolve, 1000))
                // Open in new tab for download
                if (exportUrl !== '#') {
                    window.open(exportUrl, '_blank')
                }
            } else if (exportFormat === 'geotiff') {
                setExportStatus('Generating GeoTIFF...')
                await new Promise(resolve => setTimeout(resolve, 1000))
                // GeoTIFF export would use rasterio on backend
            }

            setExportStatus('Export complete! ✓')
            setTimeout(() => setExportStatus(null), 3000)
        } catch (error) {
            console.error('Export error:', error)
            setExportStatus('Export failed')
        } finally {
            setIsExporting(false)
        }
    }

    return (
        <div className="export-panel">
            <h3 className="section-title">📥 Export</h3>

            <div className="export-options">
                <div className="export-format">
                    <label className="form-label">Format</label>
                    <div className="format-buttons">
                        <button
                            className={`format-btn ${exportFormat === 'png' ? 'active' : ''}`}
                            onClick={() => setExportFormat('png')}
                        >
                            🖼️ PNG
                        </button>
                        <button
                            className={`format-btn ${exportFormat === 'geotiff' ? 'active' : ''}`}
                            onClick={() => setExportFormat('geotiff')}
                        >
                            🗺️ GeoTIFF
                        </button>
                        <button
                            className={`format-btn ${exportFormat === 'json' ? 'active' : ''}`}
                            onClick={() => setExportFormat('json')}
                        >
                            📄 GeoJSON
                        </button>
                    </div>
                </div>

                <button
                    className="btn btn-primary btn-block"
                    onClick={handleExport}
                    disabled={isExporting || (!selectedScene && mapLayers.length === 0)}
                    style={{ marginTop: '12px' }}
                >
                    {isExporting ? '⏳ Exporting...' : '⬇️ Download'}
                </button>

                {exportStatus && (
                    <p className="export-status">{exportStatus}</p>
                )}
            </div>

            <style>{`
        .export-panel {
          margin-top: 16px;
          padding-top: 16px;
          border-top: 1px solid var(--border-color);
        }

        .export-options {
          margin-top: 8px;
        }

        .format-buttons {
          display: flex;
          gap: 6px;
        }

        .format-btn {
          flex: 1;
          padding: 8px 6px;
          background: var(--bg-tertiary);
          border: 1px solid var(--border-color);
          border-radius: 6px;
          color: var(--text-secondary);
          font-size: 0.7rem;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .format-btn.active {
          background: rgba(59, 130, 246, 0.15);
          border-color: var(--accent-primary);
          color: var(--accent-primary);
        }

        .format-btn:hover:not(.active) {
          border-color: var(--text-muted);
        }

        .export-status {
          font-size: 0.75rem;
          color: var(--accent-success);
          text-align: center;
          margin-top: 8px;
        }
      `}</style>
        </div>
    )
}

export default ExportPanel
