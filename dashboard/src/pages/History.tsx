import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { fetchHistory } from '../utils/api'

interface HistoryItem {
  id: number
  issue_number: number
  title: string
  author: string
  status: string
  confidence: number
  suggested_priority: string
  created_at: string
  event_type: string
}

const statusColors: Record<string, string> = {
  executed: 'bg-green-100 text-green-800',
  auto_labeled: 'bg-blue-100 text-blue-800',
  rejected: 'bg-red-100 text-red-800',
  error: 'bg-gray-100 text-gray-800',
  pending_review: 'bg-yellow-100 text-yellow-800',
}

export default function History() {
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')

  const loadHistory = useCallback(async () => {
    try {
      const data = await fetchHistory(200)
      setHistory(data.history || [])
    } catch (err) {
      console.error('Failed to load history:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadHistory() }, [loadHistory])

  const filtered = filter === 'all' ? history : history.filter(h => h.status === filter)

  if (loading) {
    return <div className="flex justify-center py-20"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" /></div>
  }

  if (history.length === 0) {
    return (
      <div className="text-center py-20">
        <div className="text-6xl mb-4">📜</div>
        <h2 className="text-xl font-semibold text-gray-900 mb-2">No history yet</h2>
        <p className="text-gray-500">Triage decisions will appear here.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900">History ({filtered.length})</h2>
        <div className="flex gap-2">
          {['all', 'executed', 'auto_labeled', 'rejected', 'error'].map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-2 py-1 text-xs rounded ${filter === f ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            >
              {f.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Issue</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Priority</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Confidence</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {filtered.map(item => (
              <tr key={item.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <Link to={`/review/${item.id}`} className="text-sm text-blue-600 hover:underline">
                    #{item.issue_number} — {item.title?.slice(0, 50)}{item.title && item.title.length > 50 ? '...' : ''}
                  </Link>
                  <p className="text-xs text-gray-500">@{item.author}</p>
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${statusColors[item.status] || 'bg-gray-100 text-gray-800'}`}>
                    {item.status.replace('_', ' ')}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-gray-700">{item.suggested_priority || '—'}</td>
                <td className="px-4 py-3 text-sm text-gray-700">{item.confidence ? `${(item.confidence * 100).toFixed(0)}%` : '—'}</td>
                <td className="px-4 py-3 text-xs text-gray-500">{new Date(item.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
