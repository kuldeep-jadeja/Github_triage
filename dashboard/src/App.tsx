import { Routes, Route, Link, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import PendingReviews from './pages/PendingReviews'
import ReviewDetail from './pages/ReviewDetail'
import History from './pages/History'
import Metrics from './pages/Metrics'
import { useWebSocket } from './hooks/useWebSocket'

function App() {
  const location = useLocation()
  const { events, connected } = useWebSocket()

  const navItems = [
    { path: '/', label: 'Pending', icon: '📋' },
    { path: '/history', label: 'History', icon: '📜' },
    { path: '/metrics', label: 'Metrics', icon: '📊' },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <span className="text-2xl">🤖</span>
              <div>
                <h1 className="text-lg font-semibold text-gray-900">GitHub Triage Agent</h1>
                <div className="flex items-center gap-2">
                  <span className={`inline-block w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-gray-400'}`} />
                  <span className="text-xs text-gray-500">{connected ? 'Live' : 'Disconnected'}</span>
                </div>
              </div>
            </div>
            <nav className="flex gap-1">
              {navItems.map(item => (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    location.pathname === item.path
                      ? 'bg-blue-100 text-blue-700'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <span className="mr-1">{item.icon}</span>
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Routes>
          <Route path="/" element={<PendingReviews />} />
          <Route path="/review/:jobId" element={<ReviewDetail />} />
          <Route path="/history" element={<History />} />
          <Route path="/metrics" element={<Metrics />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
