import { useState, useEffect, useCallback, useRef } from 'react'
import { RefreshCw, Settings, Headphones, X } from 'lucide-react'
import { api } from './api'
import CoverGrid from './components/CoverGrid'
import Player from './components/Player'
import MiniPlayer from './components/MiniPlayer'

function SettingsModal({ libraryPath, onClose, onSave }) {
  const [path, setPath] = useState(libraryPath)
  const [error, setError] = useState('')

  const handleSave = async () => {
    try {
      await onSave(path)
      onClose()
    } catch (e) {
      setError(e.message || 'Ungültiger Pfad')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-[#1a1a28] rounded-2xl p-6 w-full max-w-md shadow-2xl border border-white/10">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">Einstellungen</h2>
          <button onClick={onClose} className="p-1 hover:bg-white/10 rounded-lg transition-colors">
            <X size={18} />
          </button>
        </div>
        <label className="block text-sm text-gray-400 mb-1">Bibliothekspfad</label>
        <input
          value={path}
          onChange={(e) => setPath(e.target.value)}
          className="w-full bg-[#12121c] border border-white/10 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-violet-500 transition-colors"
          placeholder="/home/pi/Audiobooks"
        />
        {error && <p className="text-red-400 text-xs mt-1">{error}</p>}
        <button
          onClick={handleSave}
          className="mt-4 w-full bg-violet-600 hover:bg-violet-500 text-white rounded-lg py-2 text-sm font-medium transition-colors"
        >
          Speichern & Scannen
        </button>
      </div>
    </div>
  )
}

function App() {
  const [books, setBooks] = useState([])
  const [progress, setProgress] = useState({})
  const [libraryPath, setLibraryPath] = useState('')
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [selectedBook, setSelectedBook] = useState(null)
  const [playerOpen, setPlayerOpen] = useState(false)
  const [playerStatus, setPlayerStatus] = useState(null)
  const [showSettings, setShowSettings] = useState(false)
  const statusPollRef = useRef(null)

  const loadLibrary = useCallback(async () => {
    try {
      const data = await api.getLibrary()
      setBooks(data.books || [])
      setLibraryPath(data.library_path || '')
      const progs = {}
      await Promise.all(
        (data.books || []).map(async (b) => {
          try {
            const p = await api.getProgress(b.id)
            if (p.position > 0 || p.file_index > 0) progs[b.id] = p
          } catch (_) {}
        })
      )
      setProgress(progs)
    } catch (_) {}
    setLoading(false)
  }, [])

  const pollStatus = useCallback(async () => {
    try {
      const s = await api.getStatus()
      setPlayerStatus(s)
    } catch (_) {}
  }, [])

  useEffect(() => {
    loadLibrary()
    statusPollRef.current = setInterval(pollStatus, 2000)
    return () => clearInterval(statusPollRef.current)
  }, [loadLibrary, pollStatus])

  const handleScan = async () => {
    setScanning(true)
    try {
      const data = await api.scanLibrary()
      setBooks(data.books || [])
    } catch (_) {}
    setScanning(false)
  }

  const handleSelectBook = async (book) => {
    setSelectedBook(book)
    setPlayerOpen(true)
    await api.play(book.id)
    pollStatus()
  }

  const handleStatusChange = (s) => {
    setPlayerStatus(s)
    if (s?.book_id) {
      setProgress((prev) => ({
        ...prev,
        [s.book_id]: { book_id: s.book_id, position: s.position, file_index: s.file_index },
      }))
    }
  }

  const handleSaveSettings = async (path) => {
    const data = await api.setLibraryPath(path)
    setBooks(data.books || [])
    setLibraryPath(data.library_path || path)
  }

  const currentPlayingBook = books.find((b) => b.id === playerStatus?.book_id) || null

  return (
    <div className="min-h-screen bg-[#0f0f14] text-gray-100 pb-24">
      {/* Header */}
      <header className="sticky top-0 z-30 bg-[#0f0f14]/90 backdrop-blur-md border-b border-white/5 px-4 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Headphones className="text-violet-400" size={22} />
            <span className="font-semibold text-white text-lg">Audiobooks</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleScan}
              disabled={scanning}
              className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 transition-colors disabled:opacity-50"
            >
              <RefreshCw size={14} className={scanning ? 'animate-spin' : ''} />
              {scanning ? 'Scannen…' : 'Scannen'}
            </button>
            <button
              onClick={() => setShowSettings(true)}
              className="p-1.5 rounded-lg hover:bg-white/10 transition-colors text-gray-400 hover:text-white"
            >
              <Settings size={18} />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {loading ? (
          <div className="flex items-center justify-center py-24">
            <RefreshCw className="animate-spin text-violet-400" size={32} />
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between mb-5">
              <h1 className="text-xl font-bold text-white">Bibliothek</h1>
              <span className="text-sm text-gray-500">{books.length} {books.length === 1 ? 'Buch' : 'Bücher'}</span>
            </div>
            <CoverGrid
              books={books}
              progress={progress}
              currentBookId={playerStatus?.book_id}
              onSelect={handleSelectBook}
            />
          </>
        )}
      </main>

      {/* Full Player */}
      {playerOpen && selectedBook && (
        <Player
          book={selectedBook}
          onClose={() => setPlayerOpen(false)}
          onStatusChange={handleStatusChange}
        />
      )}

      {/* Mini Player */}
      {!playerOpen && (
        <MiniPlayer
          book={currentPlayingBook}
          status={playerStatus}
          onOpen={() => {
            if (currentPlayingBook) {
              setSelectedBook(currentPlayingBook)
              setPlayerOpen(true)
            }
          }}
          onPoll={pollStatus}
        />
      )}

      {/* Settings Modal */}
      {showSettings && (
        <SettingsModal
          libraryPath={libraryPath}
          onClose={() => setShowSettings(false)}
          onSave={handleSaveSettings}
        />
      )}
    </div>
  )
}

export default App
