import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { fetchReview, approveReview, rejectReview, editReview } from '../utils/api'
import { diffLines } from 'diff'

interface Review {
  id: number
  issue_id: number
  issue_number: number
  repo_full_name: string
  title: string
  author: string
  body: string
  suggested_labels: string
  suggested_priority: string
  confidence: number
  reasoning: string
  draft_comment: string
  critique_notes: string
  status: string
  created_at: string
  trace_log: string
  trace_id: string
  edited_draft: string
  event_type: string
}

function parseTraceLog(raw: string): any[] {
  try { return JSON.parse(raw) } catch { return [] }
}

function parseLabels(raw: string): string[] {
  try { return JSON.parse(raw) } catch { return [] }
}

const stepIcons: Record<string, string> = {
  INTAKE: '📥',
  ANALYZE: '🧠',
  DETECT_LANGUAGE: '🌍',
  TRANSLATE: '🔄',
  SEARCH_SIMILAR: '🔍',
  DECIDE: '⚖️',
  DRAFT_REPLY: '✍️',
  SELF_CRITIQUE: '🪞',
  COMPLETE: '✅',
}

const stepColors: Record<string, string> = {
  INTAKE: 'bg-blue-500',
  ANALYZE: 'bg-purple-500',
  DETECT_LANGUAGE: 'bg-green-500',
  TRANSLATE: 'bg-yellow-500',
  SEARCH_SIMILAR: 'bg-indigo-500',
  DECIDE: 'bg-orange-500',
  DRAFT_REPLY: 'bg-pink-500',
  SELF_CRITIQUE: 'bg-teal-500',
  COMPLETE: 'bg-green-600',
}

export default function ReviewDetail() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const [review, setReview] = useState<Review | null>(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [editedDraft, setEditedDraft] = useState('')
  const [showDiff, setShowDiff] = useState(false)

  const loadReview = useCallback(async () => {
    if (!jobId) return
    try {
      const data = await fetchReview(parseInt(jobId))
      setReview(data.review)
      setEditedDraft(data.review.draft_comment || '')
    } catch {
      navigate('/')
    } finally {
      setLoading(false)
    }
  }, [jobId, navigate])

  useEffect(() => { loadReview() }, [loadReview])

  const handleApprove = async () => {
    if (!review) return
    try {
      await approveReview(review.id)
      navigate('/')
    } catch (err) {
      alert('Failed to approve: ' + err)
    }
  }

  const handleReject = async () => {
    if (!review) return
    try {
      await rejectReview(review.id)
      navigate('/')
    } catch (err) {
      alert('Failed to reject: ' + err)
    }
  }

  const handleSaveEdit = async () => {
    if (!review) return
    try {
      await editReview(review.id, editedDraft)
      setReview(prev => prev ? { ...prev, edited_draft: editedDraft } : null)
      setEditing(false)
      setShowDiff(true)
    } catch (err) {
      alert('Failed to save edit: ' + err)
    }
  }

  if (loading) {
    return <div className="flex justify-center py-20"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" /></div>
  }
  if (!review) return null

  const traceLog = parseTraceLog(review.trace_log)
  const labels = parseLabels(review.suggested_labels)
  const diffResult = review.edited_draft ? diffLines(review.draft_comment || '', review.edited_draft) : []

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Back button */}
      <button onClick={() => navigate('/')} className="text-sm text-blue-600 hover:text-blue-800">
        ← Back to reviews
      </button>

      {/* Issue info */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              <a href={`https://github.com/${review.repo_full_name}/issues/${review.issue_number}`} target="_blank" rel="noopener noreferrer" className="hover:text-blue-600">
                #{review.issue_number} — {review.title}
              </a>
            </h2>
            <p className="text-sm text-gray-500 mt-1">by @{review.author} · {review.event_type}</p>
          </div>
          <span className={`px-2 py-1 text-xs font-medium rounded ${
            review.confidence >= 0.9 ? 'bg-green-100 text-green-800' :
            review.confidence >= 0.7 ? 'bg-yellow-100 text-yellow-800' :
            'bg-red-100 text-red-800'
          }`}>
            {(review.confidence * 100).toFixed(0)}% confidence
          </span>
        </div>

        {/* Labels */}
        {labels.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-4">
            {labels.map(l => (
              <span key={l} className="px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded-full">{l}</span>
            ))}
            <span className="px-2 py-1 text-xs font-medium bg-gray-100 text-gray-800 rounded-full">{review.suggested_priority}</span>
          </div>
        )}

        {/* Reasoning */}
        {review.reasoning && (
          <div className="mt-4 p-3 bg-gray-50 rounded-md">
            <p className="text-sm text-gray-700">{review.reasoning}</p>
          </div>
        )}

        {/* Critique notes */}
        {review.critique_notes && review.critique_notes !== 'PASS' && (
          <div className="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded-md">
            <p className="text-sm text-yellow-800">⚠️ {review.critique_notes}</p>
          </div>
        )}
      </div>

      {/* Reasoning Trace Timeline */}
      {traceLog.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Reasoning Trace</h3>
          <div className="space-y-0">
            {traceLog.map((step, i) => (
              <div key={i} className="flex gap-4">
                <div className="flex flex-col items-center">
                  <div className={`w-8 h-8 rounded-full ${stepColors[step.node] || 'bg-gray-500'} flex items-center justify-center text-white text-sm`}>
                    {stepIcons[step.node] || '📌'}
                  </div>
                  {i < traceLog.length - 1 && <div className="w-0.5 h-full bg-gray-200 min-h-[2rem]" />}
                </div>
                <div className="pb-6">
                  <p className="text-sm font-medium text-gray-900">{step.node.replace(/_/g, ' ')}</p>
                  {step.detail && <p className="text-xs text-gray-500 mt-0.5">{step.detail}</p>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Draft Comment */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-900">Draft Comment</h3>
          <div className="flex gap-2">
            {!editing && (
              <button onClick={() => { setEditing(true); setShowDiff(false) }} className="text-xs text-blue-600 hover:text-blue-800">
                Edit
              </button>
            )}
            {showDiff && (
              <button onClick={() => setShowDiff(false)} className="text-xs text-gray-600 hover:text-gray-800">
                Hide diff
              </button>
            )}
          </div>
        </div>

        {editing ? (
          <div className="space-y-3">
            <textarea
              value={editedDraft}
              onChange={e => setEditedDraft(e.target.value)}
              className="w-full h-48 p-3 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <div className="flex gap-2">
              <button onClick={handleSaveEdit} className="px-3 py-1.5 text-xs font-medium text-white bg-blue-600 rounded hover:bg-blue-700">
                Save
              </button>
              <button onClick={() => { setEditing(false); setEditedDraft(review.draft_comment || '') }} className="px-3 py-1.5 text-xs text-gray-600 hover:text-gray-800">
                Cancel
              </button>
            </div>
          </div>
        ) : showDiff && review.edited_draft ? (
          <div className="text-sm font-mono bg-gray-50 p-3 rounded-md max-h-64 overflow-y-auto">
            {diffResult.map((part, i) => (
              <div key={i} className={part.added ? 'bg-green-100 text-green-800' : part.removed ? 'bg-red-100 text-red-800 line-through' : 'text-gray-700'}>
                {part.value}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-gray-700 whitespace-pre-wrap">{review.draft_comment || 'No draft generated.'}</div>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        <button onClick={handleApprove} className="flex-1 px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700">
          Approve & Execute
        </button>
        <button onClick={handleReject} className="px-4 py-2 text-sm font-medium text-red-600 bg-red-50 rounded-lg hover:bg-red-100">
          Reject
        </button>
      </div>
    </div>
  )
}
