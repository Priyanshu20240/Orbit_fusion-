import { useState, useEffect, useRef, useMemo } from 'react'

function TimeSlider({ scenes, selectedScene, onSceneChange, isPlaying, onPlayToggle }) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [playbackSpeed, setPlaybackSpeed] = useState(1500) // ms per frame
  const intervalRef = useRef(null)

  // Sort scenes by date - Memoized to prevent re-renders
  const sortedScenes = useMemo(() =>
    [...(scenes || [])].sort((a, b) =>
      new Date(a.datetime) - new Date(b.datetime)
    ), [scenes])

  // Sync currentIndex when selectedScene changes externally
  useEffect(() => {
    if (selectedScene && sortedScenes.length > 0 && !isPlaying) {
      const index = sortedScenes.findIndex(s => s.id === selectedScene.id)
      if (index !== -1 && index !== currentIndex) {
        setCurrentIndex(index)
      }
    }
  }, [selectedScene, sortedScenes, isPlaying])

  // Handle playback
  useEffect(() => {
    if (isPlaying && sortedScenes.length > 1) {
      intervalRef.current = setInterval(() => {
        setCurrentIndex(prev => {
          const next = (prev + 1) % sortedScenes.length
          return next
        })
      }, playbackSpeed)
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [isPlaying, sortedScenes.length, playbackSpeed])

  // Notify parent when scene changes (only if playing or user interaction, prevent loop)
  useEffect(() => {
    // Only trigger change if the current scene in slider is different from selectedScene
    // AND we are playing OR this effect triggered by slider change
    if (sortedScenes[currentIndex] && onSceneChange) {
      if (!selectedScene || sortedScenes[currentIndex].id !== selectedScene.id) {
        onSceneChange(sortedScenes[currentIndex])
      }
    }
  }, [currentIndex, sortedScenes, onSceneChange, isPlaying])

  if (!sortedScenes.length) return null

  const currentScene = sortedScenes[currentIndex]
  const formatDate = (dateStr) => {
    if (!dateStr) return ''
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    })
  }

  return (
    <div className="time-slider">
      <div className="time-slider-header">
        <span>🎬 Time-Lapse</span>
        <span className="scene-count">{sortedScenes.length} scenes</span>
      </div>

      <div className="time-slider-controls">
        {/* Play/Pause Button */}
        <button
          className="play-btn"
          onClick={onPlayToggle}
          title={isPlaying ? 'Pause' : 'Play'}
        >
          {isPlaying ? '⏸️' : '▶️'}
        </button>

        {/* Slider */}
        <div className="slider-container">
          <input
            type="range"
            min={0}
            max={sortedScenes.length - 1}
            value={currentIndex}
            onChange={(e) => setCurrentIndex(parseInt(e.target.value))}
            className="time-range"
          />
          <div className="time-labels">
            <span>{formatDate(sortedScenes[0]?.datetime)}</span>
            <span className="current-date">{formatDate(currentScene?.datetime)}</span>
            <span>{formatDate(sortedScenes[sortedScenes.length - 1]?.datetime)}</span>
          </div>
        </div>

        {/* Speed Control */}
        <select
          className="speed-select"
          value={playbackSpeed}
          onChange={(e) => setPlaybackSpeed(parseInt(e.target.value))}
          title="Playback Speed"
        >
          <option value={2500}>0.5x</option>
          <option value={1500}>1x</option>
          <option value={800}>2x</option>
          <option value={400}>4x</option>
        </select>
      </div>

      <style>{`
        .time-slider {
          position: absolute;
          bottom: 30px;
          left: 50%;
          transform: translateX(-50%);
          width: 500px;
          max-width: 80%;
          background: rgba(19, 26, 42, 0.95);
          backdrop-filter: blur(10px);
          border: 1px solid rgba(148, 163, 184, 0.1);
          border-radius: 12px;
          padding: 12px 16px;
          z-index: 1000;
          box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
        }

        .time-slider-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 10px;
          font-size: 0.85rem;
          font-weight: 600;
          color: #f1f5f9;
        }

        .scene-count {
          font-size: 0.75rem;
          color: #64748b;
          font-weight: 400;
        }

        .time-slider-controls {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .play-btn {
          width: 36px;
          height: 36px;
          border-radius: 50%;
          background: linear-gradient(135deg, #3b82f6. 0%, #8b5cf6 100%);
          border: none;
          cursor: pointer;
          font-size: 1rem;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: transform 0.15s ease;
        }

        .play-btn:hover {
          transform: scale(1.1);
        }

        .slider-container {
          flex: 1;
        }

        .time-range {
          width: 100%;
          height: 6px;
          -webkit-appearance: none;
          background: rgba(148, 163, 184, 0.2);
          border-radius: 3px;
          outline: none;
        }

        .time-range::-webkit-slider-thumb {
          -webkit-appearance: none;
          width: 16px;
          height: 16px;
          background: #3b82f6;
          border-radius: 50%;
          cursor: pointer;
          box-shadow: 0 0 10px rgba(59, 130, 246, 0.5);
        }

        .time-labels {
          display: flex;
          justify-content: space-between;
          margin-top: 6px;
          font-size: 0.65rem;
          color: #64748b;
        }

        .current-date {
          color: #3b82f6;
          font-weight: 600;
        }

        .speed-select {
          padding: 6px 10px;
          background: rgba(28, 36, 56, 0.8);
          border: 1px solid rgba(148, 163, 184, 0.2);
          border-radius: 6px;
          color: #f1f5f9;
          font-size: 0.75rem;
          cursor: pointer;
        }

        .speed-select:focus {
          outline: none;
          border-color: #3b82f6;
        }
      `}</style>
    </div>
  )
}

export default TimeSlider
