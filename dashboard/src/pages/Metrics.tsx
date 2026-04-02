import { useState, useEffect, useCallback } from 'react'
import { fetchMetrics } from '../utils/api'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'

interface Metrics {
  total_triaged: number
  approved: number
  rejected: number
  auto_labeled: number
  avg_confidence: number
  total_tokens: number
  approval_rate: number
}

const COLORS = ['#22c55e', '#3b82f6', '#ef4444', '#f59e0b']

export default function Metrics() {
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [loading, setLoading] = useState(true)

  const loadMetrics = useCallback(async () => {
    try {
      const data = await fetchMetrics()
      setMetrics(data)
    } catch (err) {
      console.error('Failed to load metrics:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadMetrics() }, [loadMetrics])

  if (loading) {
    return <div className="flex justify-center py-20"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" /></div>
  }

  if (!metrics || metrics.total_triaged === 0) {
    return (
      <div className="text-center py-20">
        <div className="text-6xl mb-4">📊</div>
        <h2 className="text-xl font-semibold text-gray-900 mb-2">Collecting data...</h2>
        <p className="text-gray-500">Metrics will appear after your first triage.</p>
      </div>
    )
  }

  const pieData = [
    { name: 'Approved', value: metrics.approved },
    { name: 'Auto-labeled', value: metrics.auto_labeled },
    { name: 'Rejected', value: metrics.rejected },
    { name: 'Other', value: Math.max(0, metrics.total_triaged - metrics.approved - metrics.auto_labeled - metrics.rejected) },
  ].filter(d => d.value > 0)

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-gray-900">Metrics</h2>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-sm text-gray-500">Total Triaged</p>
          <p className="text-2xl font-bold text-gray-900">{metrics.total_triaged}</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-sm text-gray-500">Avg Confidence</p>
          <p className="text-2xl font-bold text-gray-900">{(metrics.avg_confidence * 100).toFixed(0)}%</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-sm text-gray-500">Approval Rate</p>
          <p className="text-2xl font-bold text-gray-900">{(metrics.approval_rate * 100).toFixed(0)}%</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-sm text-gray-500">Tokens Used</p>
          <p className="text-2xl font-bold text-gray-900">{metrics.total_tokens.toLocaleString()}</p>
        </div>
      </div>

      {/* Charts */}
      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Outcome Distribution</h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={pieData} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Breakdown</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={pieData}>
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
