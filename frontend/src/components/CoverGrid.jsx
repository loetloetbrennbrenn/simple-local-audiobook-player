import { BookOpen } from 'lucide-react'
import { api } from '../api'
import { formatDuration } from '../utils'

function BookCard({ book, progress, isPlaying, onClick }) {
  const coverUrl = api.getCoverUrl(book.id)
  const prog = progress[book.id]
  const totalDuration = book.total_duration || 0
  const pos = prog ? (prog.file_index > 0
    ? prog.position + book.files.slice(0, prog.file_index).reduce((a) => a, 0)
    : prog.position)
    : 0
  const percent = totalDuration > 0 && prog
    ? Math.min(100, (prog.position / totalDuration) * 100)
    : 0

  return (
    <button
      onClick={() => onClick(book)}
      className={`group relative flex flex-col rounded-2xl overflow-hidden transition-all duration-200 text-left
        bg-[#1a1a24] hover:bg-[#222231] hover:scale-[1.02] active:scale-[0.98]
        ${isPlaying ? 'ring-2 ring-violet-500' : 'ring-1 ring-white/5'}`}
    >
      <div className="relative w-full aspect-square bg-[#12121a] flex items-center justify-center overflow-hidden">
        {book.has_cover ? (
          <img
            src={coverUrl}
            alt={book.title}
            className="w-full h-full object-cover"
            onError={(e) => { e.currentTarget.style.display = 'none'; e.currentTarget.nextSibling.style.display = 'flex' }}
          />
        ) : null}
        <div
          className={`absolute inset-0 flex items-center justify-center ${book.has_cover ? 'hidden' : 'flex'}`}
        >
          <BookOpen className="text-violet-400 opacity-40" size={56} />
        </div>

        {isPlaying && (
          <div className="absolute bottom-2 right-2 flex gap-0.5 items-end h-4">
            {[1, 2, 3].map((i) => (
              <span
                key={i}
                className="w-1 bg-violet-400 rounded-sm animate-bounce"
                style={{ height: `${8 + i * 4}px`, animationDelay: `${i * 0.1}s` }}
              />
            ))}
          </div>
        )}
      </div>

      <div className="p-3 flex flex-col gap-1 flex-1">
        <p className="font-semibold text-sm text-white leading-tight line-clamp-2">{book.title}</p>
        {book.author && (
          <p className="text-xs text-gray-400 line-clamp-1">{book.author}</p>
        )}
        <p className="text-xs text-gray-500 mt-auto">
          {book.file_count} {book.file_count === 1 ? 'file' : 'files'} · {formatDuration(totalDuration)}
        </p>
        {percent > 0 && (
          <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden mt-1">
            <div
              className="h-full bg-violet-500 rounded-full transition-all"
              style={{ width: `${percent}%` }}
            />
          </div>
        )}
      </div>
    </button>
  )
}

export default function CoverGrid({ books, progress, currentBookId, onSelect }) {
  if (books.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-gray-500">
        <BookOpen size={48} className="mb-4 opacity-30" />
        <p className="text-lg font-medium">Keine Bücher gefunden</p>
        <p className="text-sm mt-1">Bibliothekspfad prüfen oder Scan starten</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
      {books.map((book) => (
        <BookCard
          key={book.id}
          book={book}
          progress={progress}
          isPlaying={book.id === currentBookId}
          onClick={onSelect}
        />
      ))}
    </div>
  )
}
