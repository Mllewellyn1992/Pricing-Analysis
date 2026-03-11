function Dashboard({ onNavigate }) {
  const stats = [
    {
      label: 'Analyses Run',
      value: '24',
      subtext: 'This month',
      color: 'bg-blue-50 border-blue-200',
    },
    {
      label: 'Avg Spread',
      value: '285 bps',
      subtext: 'Portfolio average',
      color: 'bg-green-50 border-green-200',
    },
    {
      label: 'Active Facilities',
      value: '18',
      subtext: 'Tracked facilities',
      color: 'bg-purple-50 border-purple-200',
    },
    {
      label: 'Saved vs Market',
      value: '+42 bps',
      subtext: 'Pricing advantage',
      color: 'bg-green-50 border-green-200',
    },
  ]

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-12">
        <h1 className="text-4xl font-bold text-gray-900 mb-3">Welcome to Credit Pricing</h1>
        <p className="text-lg text-gray-600">
          Advanced credit spread analysis for NZ corporate finance teams
        </p>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className={`card card-hover p-6 border-l-4 ${stat.color}`}
          >
            <p className="text-sm font-medium text-gray-600 mb-2">{stat.label}</p>
            <p className="text-3xl font-bold text-gray-900 mb-1">{stat.value}</p>
            <p className="text-xs text-gray-500">{stat.subtext}</p>
          </div>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-12">
        <div className="card p-8">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Manual Analysis</h2>
          <p className="text-gray-600 mb-6">
            Input your company's financial data directly to calculate expected credit spreads and all-in rates.
          </p>
          <button
            onClick={() => onNavigate('#/analysis')}
            className="btn-primary w-full"
          >
            Start Analysis
          </button>
        </div>

        <div className="card p-8">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Upload Financial Statements</h2>
          <p className="text-gray-600 mb-6">
            Extract financial data from PDF statements using AI-powered extraction to populate analysis automatically.
          </p>
          <button
            onClick={() => onNavigate('#/upload')}
            className="btn-primary w-full"
          >
            Upload PDF
          </button>
        </div>
      </div>

      {/* Information Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="card p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center">
            <span className="text-2xl mr-3">📊</span>
            How It Works
          </h3>
          <ul className="space-y-2 text-sm text-gray-600">
            <li className="flex items-start">
              <span className="text-primary font-bold mr-2">1.</span>
              <span>Input financial metrics or upload statements</span>
            </li>
            <li className="flex items-start">
              <span className="text-primary font-bold mr-2">2.</span>
              <span>System calculates credit ratios and profile</span>
            </li>
            <li className="flex items-start">
              <span className="text-primary font-bold mr-2">3.</span>
              <span>Compare expected vs actual facility rates</span>
            </li>
            <li className="flex items-start">
              <span className="text-primary font-bold mr-2">4.</span>
              <span>Identify pricing opportunities</span>
            </li>
          </ul>
        </div>

        <div className="card p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center">
            <span className="text-2xl mr-3">💡</span>
            Key Metrics
          </h3>
          <ul className="space-y-2 text-sm text-gray-600">
            <li>
              <span className="font-medium text-gray-900">Debt/EBITDA</span> - Leverage ratio
            </li>
            <li>
              <span className="font-medium text-gray-900">FFO/Debt</span> - Coverage ratio
            </li>
            <li>
              <span className="font-medium text-gray-900">EBITDA/Interest</span> - Interest coverage
            </li>
            <li>
              <span className="font-medium text-gray-900">Credit Spread</span> - Expected margin (bps)
            </li>
          </ul>
        </div>

        <div className="card p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center">
            <span className="text-2xl mr-3">🏦</span>
            NZ Base Rates
          </h3>
          <p className="text-sm text-gray-600 mb-4">
            Monitor current corporate and working capital base rates from major NZ banks.
          </p>
          <button
            onClick={() => onNavigate('#/rates')}
            className="btn-secondary w-full text-sm"
          >
            View Rates
          </button>
        </div>
      </div>

      {/* Footer Info */}
      <div className="mt-12 p-6 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-sm text-gray-700">
          <span className="font-semibold text-primary">Note:</span> Credit ratings are calculated internally and not displayed to users. This tool shows expected market-based spreads and all-in rates for benchmarking purposes.
        </p>
      </div>
    </div>
  )
}

export default Dashboard
