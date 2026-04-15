const BASE = '/api'

async function json(res) {
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export const api = {
  getLibrary: () => fetch(`${BASE}/library`).then(json),
  scanLibrary: () => fetch(`${BASE}/library/scan`, { method: 'POST' }).then(json),
  setLibraryPath: (path) =>
    fetch(`${BASE}/library/path`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    }).then(json),

  getBook: (id) => fetch(`${BASE}/books/${id}`).then(json),
  getCoverUrl: (id) => `${BASE}/books/${id}/cover`,

  getProgress: (id) => fetch(`${BASE}/progress/${id}`).then(json),

  play: (bookId, fileIndex, position) =>
    fetch(`${BASE}/player/play`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ book_id: bookId, file_index: fileIndex, position }),
    }).then(json),
  pause: () => fetch(`${BASE}/player/pause`, { method: 'POST' }).then(json),
  stop: () => fetch(`${BASE}/player/stop`, { method: 'POST' }).then(json),
  seek: (seconds, mode = 'absolute') =>
    fetch(`${BASE}/player/seek`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seconds, mode }),
    }).then(json),
  skipForward: (seconds = 30) =>
    fetch(`${BASE}/player/skip_forward`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seconds }),
    }).then(json),
  skipBackward: (seconds = 15) =>
    fetch(`${BASE}/player/skip_backward`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seconds }),
    }).then(json),
  seekToFile: (fileIndex, position = 0) =>
    fetch(`${BASE}/player/seek_to_file`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_index: fileIndex, position }),
    }).then(json),
  getStatus: () => fetch(`${BASE}/player/status`).then(json),
  setVolume: (volume) =>
    fetch(`${BASE}/player/volume`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ volume }),
    }).then(json),
}
