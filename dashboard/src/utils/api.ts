const API_BASE = import.meta.env.VITE_API_BASE || ''

export async function fetchPending() {
  const res = await fetch(`${API_BASE}/api/reviews/pending`)
  if (!res.ok) throw new Error('Failed to fetch pending reviews')
  return res.json()
}

export async function fetchReview(jobId: number) {
  const res = await fetch(`${API_BASE}/api/reviews/${jobId}`)
  if (!res.ok) throw new Error('Review not found')
  return res.json()
}

export async function fetchHistory(limit = 50) {
  const res = await fetch(`${API_BASE}/api/reviews/history?limit=${limit}`)
  if (!res.ok) throw new Error('Failed to fetch history')
  return res.json()
}

export async function fetchMetrics() {
  const res = await fetch(`${API_BASE}/api/metrics`)
  if (!res.ok) throw new Error('Failed to fetch metrics')
  return res.json()
}

export async function approveReview(jobId: number) {
  const res = await fetch(`${API_BASE}/api/reviews/${jobId}/approve`, { method: 'POST' })
  if (!res.ok) throw new Error('Failed to approve')
  return res.json()
}

export async function rejectReview(jobId: number) {
  const res = await fetch(`${API_BASE}/api/reviews/${jobId}/reject`, { method: 'POST' })
  if (!res.ok) throw new Error('Failed to reject')
  return res.json()
}

export async function editReview(jobId: number, draftComment: string) {
  const res = await fetch(`${API_BASE}/api/reviews/${jobId}/edit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ draft_comment: draftComment }),
  })
  if (!res.ok) throw new Error('Failed to edit')
  return res.json()
}

export async function undoAutoLabel(jobId: number) {
  const res = await fetch(`${API_BASE}/api/reviews/${jobId}/undo`, { method: 'POST' })
  if (!res.ok) throw new Error('Failed to undo')
  return res.json()
}
