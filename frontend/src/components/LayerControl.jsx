import { useState } from 'react'

function LayerControl({ layers, onToggleLayer, onOpacityChange, onRemoveLayer }) {
    const [expanded, setExpanded] = useState(true)

    if (!layers || layers.length === 0) {
        return null
    }

    return (
        <div className="layer-control">
            <div className="layer-control-header" onClick={() => setExpanded(!expanded)}>
                <span>🗂️ Active Layers ({layers.length})</span>
                <span className="expand-icon">{expanded ? '▼' : '▶'}</span>
            </div>

            {expanded && (
                <div className="layer-control-content">
                    {layers.map((layer, index) => (
                        <div key={layer.id} className="layer-item">
                            <div className="layer-item-header">
                                <label className="layer-checkbox">
                                    <input
                                        type="checkbox"
                                        checked={layer.visible}
                                        onChange={() => onToggleLayer(layer.id)}
                                    />
                                    <span className="layer-name">
                                        {layer.satellite === 'sentinel' && '🌍'}
                                        {layer.satellite === 'landsat' && '🌎'}
                                        {layer.satellite === 'bhuvan' && '🇮🇳'}
                                        {' '}{layer.name}
                                    </span>
                                </label>
                                <button
                                    className="layer-remove-btn"
                                    onClick={() => onRemoveLayer(layer.id)}
                                    title="Remove layer"
                                >
                                    ✕
                                </button>
                            </div>

                            <div className="layer-opacity">
                                <span className="opacity-label">Opacity</span>
                                <input
                                    type="range"
                                    min="0"
                                    max="100"
                                    value={layer.opacity}
                                    onChange={(e) => onOpacityChange(layer.id, parseInt(e.target.value))}
                                    className="opacity-slider"
                                />
                                <span className="opacity-value">{layer.opacity}%</span>
                            </div>

                            {layer.type && (
                                <div className="layer-type">
                                    <span className={`layer-badge ${layer.type}`}>
                                        {layer.type.toUpperCase()}
                                    </span>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}

            <style>{`
        .layer-control {
          position: absolute;
          top: 80px;
          right: 20px;
          width: 280px;
          background: rgba(19, 26, 42, 0.95);
          backdrop-filter: blur(10px);
          border: 1px solid rgba(148, 163, 184, 0.1);
          border-radius: 12px;
          z-index: 1000;
          box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
          overflow: hidden;
        }
        
        .layer-control-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 12px 16px;
          background: rgba(28, 36, 56, 0.8);
          cursor: pointer;
          font-size: 0.85rem;
          font-weight: 600;
          color: #f1f5f9;
          border-bottom: 1px solid rgba(148, 163, 184, 0.1);
        }
        
        .layer-control-header:hover {
          background: rgba(28, 36, 56, 1);
        }
        
        .expand-icon {
          font-size: 0.7rem;
          color: #64748b;
        }
        
        .layer-control-content {
          padding: 8px;
          max-height: 300px;
          overflow-y: auto;
        }
        
        .layer-item {
          background: rgba(28, 36, 56, 0.6);
          border-radius: 8px;
          padding: 10px 12px;
          margin-bottom: 8px;
        }
        
        .layer-item:last-child {
          margin-bottom: 0;
        }
        
        .layer-item-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 8px;
        }
        
        .layer-checkbox {
          display: flex;
          align-items: center;
          gap: 8px;
          cursor: pointer;
        }
        
        .layer-checkbox input {
          width: 16px;
          height: 16px;
          accent-color: #3b82f6;
        }
        
        .layer-name {
          font-size: 0.8rem;
          color: #f1f5f9;
        }
        
        .layer-remove-btn {
          background: transparent;
          border: none;
          color: #64748b;
          cursor: pointer;
          font-size: 0.8rem;
          padding: 4px;
          border-radius: 4px;
          transition: all 0.15s ease;
        }
        
        .layer-remove-btn:hover {
          background: rgba(239, 68, 68, 0.2);
          color: #ef4444;
        }
        
        .layer-opacity {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        
        .opacity-label {
          font-size: 0.7rem;
          color: #64748b;
          width: 50px;
        }
        
        .opacity-slider {
          flex: 1;
          height: 4px;
          -webkit-appearance: none;
          background: rgba(148, 163, 184, 0.2);
          border-radius: 2px;
          outline: none;
        }
        
        .opacity-slider::-webkit-slider-thumb {
          -webkit-appearance: none;
          width: 14px;
          height: 14px;
          background: #3b82f6;
          border-radius: 50%;
          cursor: pointer;
        }
        
        .opacity-value {
          font-size: 0.7rem;
          color: #94a3b8;
          width: 35px;
          text-align: right;
        }
        
        .layer-type {
          margin-top: 6px;
        }
        
        .layer-badge {
          font-size: 0.65rem;
          padding: 2px 6px;
          border-radius: 4px;
          font-weight: 600;
        }
        
        .layer-badge.rgb {
          background: rgba(59, 130, 246, 0.2);
          color: #3b82f6;
        }
        
        .layer-badge.ndvi {
          background: rgba(16, 185, 129, 0.2);
          color: #10b981;
        }
        
        .layer-badge.wms {
          background: rgba(245, 158, 11, 0.2);
          color: #f59e0b;
        }
      `}</style>
        </div>
    )
}

export default LayerControl
