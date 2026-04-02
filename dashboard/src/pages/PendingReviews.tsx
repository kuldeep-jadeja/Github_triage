import { useState, useEffect, useCallback } from 'react'
import { fetchPending, approveReview, rejectReview } from '../utils/api'
import { useWebSocket } from '../hooks/useWebSocket'

interface Review {
  id: number
  issue_id: number
  issue_number: number
  repo_full_name: string
  title: string
  author: string
  suggested_labels: string
  suggested_priority: string
  confidence: number
  reasoning: string
  draft_comment: string
  status: string
  created_at: string
  trace_id: string
  event_type: string
}

const priorityColors: Record<string, string> = {
  P0: 'bg-red-100 text-red-800 border-red-200',
  P1: 'bg-orange-100 text-orange-800 border-orange-200',
  P2: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  P3: 'bg-green-100 text-green-800 border-green-200',
}

const labelColors = [
  'bg-blue-100 text-blue-800',
  'bg-purple-100 text-purple-800',
  'bg-pink-100 text-pink-800',
  'bg-indigo-100 text-indigo-800',
  'bg-teal-100 text-teal-800',
]

function confidenceColor(c: number): string {
  if (c >= 0.9) return 'text-green-600'
  if (c >= 0.7) return 'text-yellow-600'
  return 'text-red-600'
}

function parseLabels(raw: string): string[] {
  try {
    return JSON.parse(raw)
  } catch {
    return []
  }
}

export default function PendingReviews() {
  const [reviews, setReviews] = useState<Review[]>([])
  const [loading, setLoading] = useState(true)
  const [processing, setProcessing] = useState<Set<number>>(new Set())
  const { events } = useWebSocket()

  const loadReviews = useCallback(async () => {
    try {
      const data = await fetchPending()
      setReviews(data.reviews || [])
    } catch (err) {
      console.error('Failed to load reviews:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadReviews()
  }, [loadReviews])

  // React to WebSocket events
  useEffect(() => {
    if (events.length === 0) return
    const last = events[events.length - 1]
    if (last.type === 'triage_complete' || last.type === 'triage_error') {
      loadReviews()
      if (last.job_id) {
        setProcessing(prev => {
          const next = new Set(prev)
          next.delete(last.job_id!)
          return next
        })
      }
    }
    if (last.type === 'triage_started' && last.job_id) {
      setProcessing(prev => new Set(prev).add(last.job_id!))
    }
    if (last.type === 'review_approved' || last.type === 'review_rejected') {
      loadReviews()
    }
  }, [events, loadReviews])

  const handleApprove = async (jobId: number) => {
    try {
      await approveReview(jobId)
      setReviews(prev => prev.filter(r => r.id !== jobId))
    } catch (err) {
      alert('Failed to approve: ' + err)
    }
  }

  const handleReject = async (jobId: number) => {
    try {
      await rejectReview(jobId)
      setReviews(prev => prev.filter(r => r.id !== jobId))
    } catch (err) {
      alert('Failed to reject: ' + err)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    )
  }

  if (reviews.length === 0) {
    return (
      <div className="text-center py-20">
        <div className="text-6xl mb-4">✅</div>
        <h2 className="text-xl font-semibold text-gray-900 mb-2">All caught up!</h2>
        <p className="text-gray-500">No pending triage reviews. New issues will appear here automatically.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900">
          Pending Reviews ({reviews.length})
        </h2>
        <button
          onClick={loadReviews}
          className="text-sm text-blue-600 hover:text-blue-800"
        >
          Refresh
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {reviews.map((review, idx) => {
          const labels = parseLabels(review.suggested_labels)
          const isProcessing = processing.has(review.id)

          return (
            <div
              key={review.id}
              className={`bg-white rounded-lg border p-4 transition-all ${
                isProcessing ? 'border-blue-300 ring-2 ring-blue-100' : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1 min-w-0">
                  <a
                    href={`https://github.com/${review.repo_full_name}/issues/${review.issue_number}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-medium text-gray-900 hover:text-blue-600 truncate block"
                  >
                    #{review.issue_number} — {review.title}
                  </a>
                  <p className="text-xs text-gray-500 mt-0.5">by @{review.author}</p>
                </div>
                <span className={`ml-2 px-2 py-0.5 text-xs font-medium rounded border ${priorityColors[review.suggested_priority] || priorityColors.P2}`}>
                  {review.suggested_priority}
                </span>
              </div>

              {/* Labels */}
              {labels.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-3">
                  {labels.map((label, i) => (
                    <span
                      key={label}
                      className={`px-2 py-0.5 text-xs font-medium rounded-full ${labelColors[i % labelColors.length]}`}
                    >
                      {label}
                    </span>
                  ))}
                </div>
              )}

              {/* Confidence */}
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs text-gray-500">Confidence:</span>
                <div className="flex-1 bg-gray-200 rounded-full h-1.5">
                  <div
                    className={`h-1.5 rounded-full ${
                      review.confidence >= 0.9 ? 'bg-green-500' :
                      review.confidence >= 0.7 ? 'bg-yellow-500' : 'bg-red-500'
                    }`}
                    style={{ width: `${review.confidence * 100}%` }}
                  />
                </div>
                <span className={`text-xs font-medium ${confidenceColor(review.confidence)}`}>
                  {(review.confidence * 100).toFixed(0)}%
                </span>
              </div>

              {/* Reasoning */}
              {review.reasoning && (
                <p className="text-xs text-gray-600 mb-3 line-clamp-2">{review.reasoning}</p>
              )}

              {/* Processing indicator */}
              {isProcessing && (
                <div className="flex items-center gap-2 mb-3 text-blue-600">
                  <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-blue-600" />
                  <span className="text-xs">Processing...</span>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-2">
                <button
                  onClick={() => handleApprove(review.id)}
                  disabled={isProcessing}
                  className="flex-1 px-3 py-1.5 text-xs font-medium text-white bg-green-600 rounded hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Approve
                </button>
                <button
                  onClick={() => window.location.href = `/review/${review.id}`}
                  className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-gray-100 rounded hover:bg-gray-200 transition-colors"
                >
                  Details
                </button>
                <button
                  onClick={() => handleReject(review.id)}
                  disabled={isProcessing}
                  className="px-3 py-1.5 text-xs font-medium text-red-600 bg-red-50 rounded hover:bg-red-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Reject
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
