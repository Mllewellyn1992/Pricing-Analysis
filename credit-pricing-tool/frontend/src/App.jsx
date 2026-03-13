import { useState, useEffect } from 'react'
import Landing from './pages/Landing'
import Dashboard from './pages/Dashboard'
import AnalysisForm from './pages/AnalysisForm'
import Results from './pages/Results'
import BaseRates from './pages/BaseRates'
import Audit from './pages/Audit'

function App() {
  const [currentHash, setCurrentHash] = useState(window.location.hash || '#/')
  const [analysisResults, setAnalysisResults] = useState(null)
  const [extractedData, setExtractedData] = useState(null)

  useEffect(() => {
    const handleHashChange = () => {
      setCurrentHash(window.location.hash || '#/')
    }
    window.addEventListener('hashchange', handleHashChange)
    return () => window.removeEventListener('hashchange', handleHashChange)
  }, [])

  const navigate = (path) => {
    window.location.hash = path
    setCurrentHash(path)
  }

  const handleAnalysisSubmit = (results) => {
    setAnalysisResults(results)
    navigate('#/results')
  }

  const handleExtractedData = (data) => {
    setExtractedData(data)
    navigate('#/analysis')
  }

  const renderPage = () => {
    const page = currentHash.slice(2) || '/'
    switch (page) {
      case '/':
      case '':
      case 'landing':
        return <Landing onNavigate={navigate} />
      case 'dashboard':
        return <Dashboard onNavigate={navigate} />
      case 'analysis':
      case 'upload':
        return (
          <AnalysisForm
            onResults={handleAnalysisSubmit}
            extractedData={extractedData}
            onClearExtracted={() => setExtractedData(null)}
          />
        )
      case 'results':
        return <Results data={analysisResults} onNavigate={navigate} />
      case 'rates':
        return <BaseRates onNavigate={navigate} />
      case 'audit':
        return <Audit onNavigate={navigate} />
      default:
        return <Landing onNavigate={navigate} />
    }
  }

  const isLandingPage = currentHash === '#/' || currentHash === '' || currentHash === '#/landing'

  const navItems = [
    { href: '#/dashboard', label: 'Dashboard', icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
      </svg>
    )},
    { href: '#/analysis', label: 'Analysis', icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
      </svg>
    )},
    { href: '#/rates', label: 'Base Rates', icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
      </svg>
    )},
    { href: '#/audit', label: 'Rate Audit', icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
      </svg>
    )},
  ]

  return (
    <div className="flex h-screen bg-slate-50">
      {/* Sidebar */}
      {!isLandingPage && (
        <aside className="sidebar flex flex-col text-white shadow-xl" style={{ width: 200, minWidth: 200 }}>
          {/* Logo */}
          <div className="px-4 py-4 border-b border-slate-700/50">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-md bg-blue-500 flex items-center justify-center">
                <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-white leading-tight">Credit Pricing</p>
                <p className="text-[10px] text-slate-400 leading-tight">NZ Corporate Finance</p>
              </div>
            </div>
          </div>

          {/* Nav */}
          <nav className="flex-1 px-2 py-3 space-y-0.5">
            {navItems.map((item) => (
              <button
                key={item.href}
                onClick={() => navigate(item.href)}
                className={`nav-item ${currentHash === item.href ? 'active' : ''}`}
              >
                <span className="mr-2.5 opacity-70">{item.icon}</span>
                {item.label}
              </button>
            ))}
          </nav>

          {/* Footer */}
          <div className="px-3 py-2.5 border-t border-slate-700/50">
            <p className="text-[10px] text-slate-500">v1.0 • NZ Bank Credit Pricing</p>
          </div>
        </aside>
      )}

      {/* Main Content */}
      <main className={`flex-1 overflow-auto ${isLandingPage ? 'w-full' : ''}`}>
        {renderPage()}
      </main>
    </div>
  )
}

export default App
