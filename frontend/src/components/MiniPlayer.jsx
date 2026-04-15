import { Play, Pause, SkipBack, SkipForward } from 'lucide-react'
import { api } from '../api'
import { formatTime, progressPercent } from '../utils'

export default function MiniPlayer({ book, status, onOpen, onPoll }) {
  if (!book || !status?.playing) return null

  const isPlaying = status.playing && !status.paused
  const position = status.position ?? 0
  const duration = status.duration ?? 0
  const coverUrl = api.getCoverUrl(book.id)

  return (
    <div
      className="fixed bottom-0 inset-x-0 bg-[#1a1a28]/95 backdrop-blur-md border-t border-white/10 z-40"
    >
      <div
        className="h-1 bg-white/10 cursor-pointer"
        onClick={async (e) => {
          if (!duration) return
          const rect = e.currentTarget.getBoundingClientRect()
          const ratio = (e.clientX - rect.left) / rect.width
          await api.seek(ratio * duration)
          onPoll?.()
        }}
      >
        <div
          className="h-full bg-violet-500 transition-all"
          style={{ width: `${progressPercent(position, duration)}%` }}
        />
      </div>

      <div className="flex items-center gap-3 px-4 py-2 max-w-4xl mx-auto">
        <button onClick={onOpen} className="flex items-center gap-3 flex-1 min-w-0">
          <div className="w-10 h-10 rounded-lg overflow-hidden bg-[#12121a] flex-shrink-0">
            {book.has_cover ? (
              <img src={coverUrl} alt={book.title} className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-violet-400 text-lg">🎧</div>
            )}
          </div>
          <div className="min-w-0 text-left">
            <p className="text-sm font-medium text-white truncate">{book.title}</p>
            <p className="text-xs text-gray-400">{formatTime(position)} / {formatTime(duration)}</p>
          </div>
        </button>

        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={() => api.skipBackward(15).then(() => onPoll?.())}
            className="p-2 rounded-full hover:bg-white/10 text-gray-300 transition-colors"
          >
            <SkipBack size={18} />
          </button>
          <button
            onClick={async () => { await api.pause(); onPoll?.() }}
            className="w-10 h-10 rounded-full bg-violet-600 hover:bg-violet-500 flex items-center justify-center transition-colors"
          >
            {isPlaying
              ? <Pause size={16} fill="currentColor" />
              : <Play size={16} fill="currentColor" className="ml-0.5" />}
          </button>
          <button
            onClick={() => api.skipForward(30).then(() => onPoll?.())}
            className="p-2 rounded-full hover:bg-white/10 text-gray-300 transition-colors"
          >
            <SkipForward size={18} />
          </button>
        </div>
      </div>
    </div>
  )
}
