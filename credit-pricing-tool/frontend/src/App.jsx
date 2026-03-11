import { useState, useEffect } from 'react'
import Landing from './pages/Landing'
import Dashboard from './pages/Dashboard'
import AnalysisForm from './pages/AnalysisForm'
import Results from './pages/Results'
import BaseRates from './pages/BaseRates'
import Upload from './pages/Upload'

function App() {
  const [currentHash, setCurrentHash] = useState(window.location.hash || '#/')
  const [analysisResults, setAnalysisResults] = useState(null)

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
        return <AnalysisForm onResults={handleAnalysisSubmit} />
      case 'results':
        return <Results data={analysisResults} onNavigate={navigate} />
      case 'rates':
        return <BaseRates onNavigate={navigate} />
      case 'upload':
        return <Upload onNavigate={navigate} />
      default:
        return <Landing onNavigate={navigate} />
    }
  }

  const isLandingPage = currentHash === '#/' || currentHash === '' || currentHash === '#/landing'

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar Navigation - Hidden on Landing Page */}
      {!isLandingPage && (
        <aside className="w-64 gradient-primary text-white shadow-lg">
          <div className="p-6 border-b border-blue-700">
            <h1 className="text-2xl font-bold">Credit Pricing</h1>
            <p className="text-blue-100 text-sm mt-1">NZ Corporate Finance</p>
          </div>

          <nav className="p-4 space-y-2">
            {[
              { href: '#/dashboard', label: 'Dashboard', icon: '📊' },
              { href: '#/analysis', label: 'Analysis', icon: '📋' },
              { href: '#/upload', label: 'Upload PDF', icon: '📄' },
              { href: '#/rates', label: 'Base Rates', icon: '💹' },
            ].map((item) => (
              <button
                key={item.href}
                onClick={() => navigate(item.href)}
                className={`w-full text-left px-4 py-3 rounded-lg transition-colors ${
                  currentHash === item.href
                    ? 'bg-blue-700 text-white'
                    : 'text-blue-100 hover:bg-blue-600'
                }`}
              >
                <span className="mr-3">{item.icon}</span>
                {item.label}
              </button>
            ))}
          </nav>

          <div className="absolute bottom-0 left-0 right-0 w-64 p-4 border-t border-blue-700 bg-blue-900">
            <p className="text-blue-200 text-xs">
              v1.0 • NZ Bank Credit Pricing Tool
            </p>
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
