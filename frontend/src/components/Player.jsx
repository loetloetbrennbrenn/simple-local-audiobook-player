import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Play, Pause, SkipBack, SkipForward, Volume2, VolumeX,
  ChevronLeft, List, X,
} from 'lucide-react'
import { api } from '../api'
import { formatTime, progressPercent } from '../utils'

export default function Player({ book, onClose, onStatusChange }) {
  const [status, setStatus] = useState(null)
  const [volume, setVolume] = useState(80)
  const [dragging, setDragging] = useState(false)
  const [dragVal, setDragVal] = useState(0)
  const [showFiles, setShowFiles] = useState(false)
  const pollRef = useRef(null)
  const seekBarRef = useRef(null)

  const poll = useCallback(async () => {
    try {
      const s = await api.getStatus()
      setStatus(s)
      if (onStatusChange) onStatusChange(s)
    } catch (_) {}
  }, [onStatusChange])

  useEffect(() => {
    poll()
    pollRef.current = setInterval(poll, 1000)
    return () => clearInterval(pollRef.current)
  }, [poll])

  const handlePlayPause = async () => {
    if (!status?.playing) {
      await api.play(book.id)
    } else {
      await api.pause()
    }
    poll()
  }

  const handleSeekBarClick = async (e) => {
    if (!seekBarRef.current || !status?.duration) return
    const rect = seekBarRef.current.getBoundingClientRect()
    const ratio = (e.clientX - rect.left) / rect.width
    const target = ratio * status.duration
    await api.seek(target)
    poll()
  }

  const handleVolume = async (val) => {
    setVolume(val)
    await api.setVolume(val)
  }

  const handleFileClick = async (idx) => {
    await api.seekToFile(idx, 0)
    setShowFiles(false)
    poll()
  }

  const position = dragging ? dragVal : (status?.position ?? 0)
  const duration = status?.duration ?? 0
  const isPlaying = status?.playing && !status?.paused
  const currentFileIdx = status?.file_index ?? 0

  const coverUrl = api.getCoverUrl(book.id)

  return (
    <div className="fixed inset-0 z-50 bg-[#0f0f14]/95 backdrop-blur-sm flex flex-col">
      <div className="flex items-center gap-3 px-4 py-3 border-b border-white/10">
        <button onClick={onClose} className="p-2 rounded-lg hover:bg-white/10 transition-colors">
          <ChevronLeft size={20} />
        </button>
        <span className="text-sm text-gray-400 truncate flex-1">{book.title}</span>
        <button
          onClick={() => setShowFiles((v) => !v)}
          className={`p-2 rounded-lg transition-colors ${showFiles ? 'bg-violet-600 text-white' : 'hover:bg-white/10'}`}
        >
          <List size={20} />
        </button>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Main Player */}
        <div className="flex flex-col items-center justify-center flex-1 px-6 py-8 gap-6">
          <div className="w-56 h-56 rounded-2xl overflow-hidden bg-[#1a1a24] flex items-center justify-center shadow-2xl">
            {book.has_cover ? (
              <img src={coverUrl} alt={book.title} className="w-full h-full object-cover" />
            ) : (
              <div className="text-violet-400 opacity-30 text-7xl">🎧</div>
            )}
          </div>

          <div className="text-center max-w-sm">
            <h2 className="text-xl font-bold text-white leading-tight">{book.title}</h2>
            {book.author && <p className="text-sm text-gray-400 mt-1">{book.author}</p>}
            {book.files && (
              <p className="text-xs text-gray-500 mt-1">
                Datei {currentFileIdx + 1} / {book.files.length}
              </p>
            )}
          </div>

          {/* Seek bar */}
          <div className="w-full max-w-md space-y-1">
            <div
              ref={seekBarRef}
              onClick={handleSeekBarClick}
              className="w-full h-2 bg-white/10 rounded-full cursor-pointer group relative"
            >
              <div
                className="h-full bg-violet-500 rounded-full relative transition-all"
                style={{ width: `${progressPercent(position, duration)}%` }}
              >
                <div className="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
            </div>
            <div className="flex justify-between text-xs text-gray-500">
              <span>{formatTime(position)}</span>
              <span>{formatTime(duration)}</span>
            </div>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-6">
            <button
              onClick={() => api.skipBackward(15).then(poll)}
              className="p-3 rounded-full hover:bg-white/10 transition-colors text-gray-300 hover:text-white"
              title="−15s"
            >
              <SkipBack size={24} />
            </button>

            <button
              onClick={handlePlayPause}
              className="w-16 h-16 rounded-full bg-violet-600 hover:bg-violet-500 active:bg-violet-700 flex items-center justify-center transition-colors shadow-lg shadow-violet-900/40"
            >
              {isPlaying
                ? <Pause size={28} fill="currentColor" />
                : <Play size={28} fill="currentColor" className="ml-1" />}
            </button>

            <button
              onClick={() => api.skipForward(30).then(poll)}
              className="p-3 rounded-full hover:bg-white/10 transition-colors text-gray-300 hover:text-white"
              title="+30s"
            >
              <SkipForward size={24} />
            </button>
          </div>

          {/* Volume */}
          <div className="flex items-center gap-3 w-full max-w-xs">
            <button onClick={() => handleVolume(volume === 0 ? 80 : 0)}>
              {volume === 0 ? <VolumeX size={18} className="text-gray-500" /> : <Volume2 size={18} className="text-gray-400" />}
            </button>
            <input
              type="range"
              min={0}
              max={100}
              value={volume}
              onChange={(e) => handleVolume(Number(e.target.value))}
              className="flex-1 accent-violet-500"
            />
            <span className="text-xs text-gray-500 w-8 text-right">{volume}%</span>
          </div>
        </div>

        {/* File list panel */}
        {showFiles && book.files && (
          <div className="w-72 border-l border-white/10 overflow-y-auto bg-[#13131c]">
            <div className="p-3 border-b border-white/10 text-sm font-medium text-gray-300">
              Kapitel / Dateien
            </div>
            {book.files.map((f, idx) => {
              const name = f.split('/').pop().replace(/\.[^.]+$/, '')
              const active = idx === currentFileIdx
              return (
                <button
                  key={idx}
                  onClick={() => handleFileClick(idx)}
                  className={`w-full text-left px-4 py-2.5 text-sm transition-colors border-b border-white/5
                    ${active ? 'bg-violet-600/20 text-violet-300' : 'hover:bg-white/5 text-gray-300'}`}
                >
                  <span className="text-xs text-gray-500 mr-2">{idx + 1}.</span>
                  {name}
                </button>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
