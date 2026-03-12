import { useState, useEffect } from 'react'
import { getBaseRates } from '../api'

function BaseRates({ onNavigate }) {
  const [rates, setRates] = useState(null)
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState(new Date())

  useEffect(() => {
    const fetchRates = async () => {
      try {
        const data = await getBaseRates()
        setRates(data)
      } catch (error) {
        console.error('Error fetching rates:', error)
        setRates(null)
      } finally {
        setLoading(false)
      }
    }

    fetchRates()
  }, [])

  const defaultRates = [
    {
      bank: 'ANZ',
      corporateRate: 5.45,
      workingCapitalRate: 5.75,
      logo: '🏦',
    },
    {
      bank: 'ASB',
      corporateRate: 5.40,
      workingCapitalRate: 5.70,
      logo: '🏦',
    },
    {
      bank: 'BNZ',
      corporateRate: 5.50,
      workingCapitalRate: 5.80,
      logo: '🏦',
    },
    {
      bank: 'Westpac',
      corporateRate: 5.48,
      workingCapitalRate: 5.78,
      logo: '🏦',
    },
    {
      bank: 'Kiwibank',
      corporateRate: 5.55,
      workingCapitalRate: 5.85,
      logo: '🏦',
    },
  ]

  const displayRates = rates || defaultRates
  const ratesWithCorporate = displayRates.filter(r => r.corporateRate != null)
  const ratesWithWC = displayRates.filter(r => r.workingCapitalRate != null)
  const avgCorporate = ratesWithCorporate.length > 0
    ? ratesWithCorporate.reduce((sum, r) => sum + r.corporateRate, 0) / ratesWithCorporate.length
    : 0
  const avgWorkingCap = ratesWithWC.length > 0
    ? ratesWithWC.reduce((sum, r) => sum + r.workingCapitalRate, 0) / ratesWithWC.length
    : 0

  const handleRefresh = () => {
    setLoading(true)
    setTimeout(() => {
      setRates(null)
      setLastUpdated(new Date())
      setLoading(false)
    }, 1000)
  }

  return (
    <div className="p-8">
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            NZ Bank Base Rates
          </h1>
          <p className="text-gray-600">
            Current corporate and working capital rates from major NZ banks
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={loading}
          className={`btn-secondary px-4 py-2 ${loading ? 'opacity-50' : ''}`}
        >
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div className="card p-6">
          <p className="text-sm font-medium text-gray-600 mb-2">
            Average Corporate Rate
          </p>
          <p className="text-4xl font-bold text-primary mb-2">
            {avgCorporate.toFixed(2)}%
          </p>
          <div className="flex gap-4 text-xs">
            {ratesWithCorporate
              .slice(0, 3)
              .map((r) => (
                <span key={r.bank} className="text-gray-500">
                  {r.bank}: {r.corporateRate.toFixed(2)}%
                </span>
              ))}
          </div>
        </div>

        <div className="card p-6">
          <p className="text-sm font-medium text-gray-600 mb-2">
            Average Working Capital Rate
          </p>
          <p className="text-4xl font-bold text-primary mb-2">
            {avgWorkingCap.toFixed(2)}%
          </p>
          <div className="flex gap-4 text-xs">
            {ratesWithWC
              .slice(0, 3)
              .map((r) => (
                <span key={r.bank} className="text-gray-500">
                  {r.bank}: {r.workingCapitalRate.toFixed(2)}%
                </span>
              ))}
          </div>
        </div>
      </div>

      {/* Rates Table */}
      <div className="card overflow-hidden mb-8">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">
                  Bank
                </th>
                <th className="px-6 py-4 text-right text-sm font-semibold text-gray-900">
                  Corporate Loans (%)
                </th>
                <th className="px-6 py-4 text-right text-sm font-semibold text-gray-900">
                  Working Capital (%)
                </th>
                <th className="px-6 py-4 text-right text-sm font-semibold text-gray-900">
                  Spread (bps)
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {displayRates.map((rate) => {
                const corp = rate.corporateRate ?? 0
                const wc = rate.workingCapitalRate ?? 0
                const spread = (wc - corp) * 100
                return (
                  <tr key={rate.bank} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <span className="text-2xl">{rate.logo || '🏦'}</span>
                        <span className="font-medium text-gray-900">
                          {rate.bank}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <p className="text-lg font-semibold text-gray-900">
                        {rate.corporateRate != null ? `${corp.toFixed(2)}%` : '—'}
                      </p>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <p className="text-lg font-semibold text-gray-900">
                        {rate.workingCapitalRate != null ? `${wc.toFixed(2)}%` : '—'}
                      </p>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <span className="inline-block px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm font-medium">
                        {rate.corporateRate != null && rate.workingCapitalRate != null ? `${spread.toFixed(0)} bps` : '—'}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Rate Comparison Chart */}
      <div className="card p-6 mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-6">
          Corporate Rate Comparison
        </h2>

        <div className="space-y-6">
          {displayRates.filter(r => r.corporateRate != null).map((rate) => {
            const allCorpRates = displayRates.filter(r => r.corporateRate != null).map(r => r.corporateRate)
            const minRate = Math.min(...allCorpRates)
            const maxRate = Math.max(...allCorpRates)
            const range = maxRate - minRate
            const barWidth = range > 0
              ? ((rate.corporateRate - minRate) / range) * 80 + 20
              : 50

            return (
              <div key={rate.bank}>
                <div className="flex justify-between items-center mb-2">
                  <span className="font-medium text-gray-900">{rate.bank}</span>
                  <span className="text-lg font-semibold text-primary">
                    {rate.corporateRate.toFixed(2)}%
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-primary rounded-full h-full transition-all duration-300"
                    style={{ width: `${barWidth}%` }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Information Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            How to Use Base Rates
          </h3>
          <ul className="space-y-3 text-sm text-gray-600">
            <li className="flex gap-3">
              <span className="text-primary font-bold">1</span>
              <span>
                Use these rates as the starting point for your credit spread
                analysis
              </span>
            </li>
            <li className="flex gap-3">
              <span className="text-primary font-bold">2</span>
              <span>
                Add your expected spread (from analysis) to get all-in rate
              </span>
            </li>
            <li className="flex gap-3">
              <span className="text-primary font-bold">3</span>
              <span>
                Compare with your actual facility rate to identify opportunities
              </span>
            </li>
            <li className="flex gap-3">
              <span className="text-primary font-bold">4</span>
              <span>
                Update rates periodically as RBNZ OCR changes impact bank pricing
              </span>
            </li>
          </ul>
        </div>

        <div className="card p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Rate Spread Insights
          </h3>
          <div className="space-y-3">
            {(() => {
              const spread = avgWorkingCap - avgCorporate
              return (
                <>
                  <div className="bg-gray-50 p-3 rounded">
                    <p className="text-xs font-medium text-gray-600 mb-1">
                      WC Premium
                    </p>
                    <p className="text-2xl font-bold text-gray-900">
                      {(spread * 100).toFixed(0)} bps
                    </p>
                  </div>
                  <p className="text-sm text-gray-600">
                    Working capital facilities typically cost {(spread * 100).toFixed(0)} basis
                    points more than corporate loans due to higher utilization
                    volatility and administrative costs.
                  </p>
                </>
              )
            })()}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="mt-8 p-6 bg-gray-50 border border-gray-200 rounded-lg">
        <div className="flex justify-between items-start">
          <div>
            <p className="text-sm font-medium text-gray-900 mb-1">
              Last Updated
            </p>
            <p className="text-xs text-gray-600">
              {lastUpdated.toLocaleDateString()} at{' '}
              {lastUpdated.toLocaleTimeString()}
            </p>
          </div>
          <p className="text-xs text-gray-500 text-right max-w-xs">
            Rates shown are illustrative based on current market conditions. Actual rates vary by
            borrower credit quality, facility structure, and market availability.
          </p>
        </div>
      </div>

      <div className="mt-6">
        <button
          onClick={() => onNavigate('#/analysis')}
          className="btn-primary"
        >
          Use Rates in Analysis
        </button>
      </div>
    </div>
  )
}

export default BaseRates
