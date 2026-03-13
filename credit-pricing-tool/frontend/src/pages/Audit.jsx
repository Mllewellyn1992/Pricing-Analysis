import { useState, useEffect } from 'react'
import React from 'react'
import { getAuditLog, triggerScrape, getBankHistory, getWholesaleRates, injectWholesaleRates } from '../api'

/**
 * Combined multi-line time-series chart for swap rates, bank bill, and OCR
 */
function WholesaleTimeSeriesChart({ swapHistory, bkbmHistory, width = 900, height = 420 }) {
  // Line definitions: which series to show and their colors
  const SERIES = [
    { key: 'OCR',   label: 'OCR',          color: '#ef4444', dash: '6,3',  source: 'bkbm' },
    { key: 'BB90D', label: 'Bank Bill 90D', color: '#f59e0b', dash: '',     source: 'bkbm' },
    { key: '1Y',    label: 'Swap 1Y',       color: '#3b82f6', dash: '',     source: 'swap' },
    { key: '2Y',    label: 'Swap 2Y',       color: '#8b5cf6', dash: '',     source: 'swap' },
    { key: '3Y',    label: 'Swap 3Y',       color: '#06b6d4', dash: '',     source: 'swap' },
    { key: '5Y',    label: 'Swap 5Y',       color: '#10b981', dash: '',     source: 'swap' },
    { key: '7Y',    label: 'Swap 7Y',       color: '#ec4899', dash: '',     source: 'swap' },
    { key: '10Y',   label: 'Swap 10Y',      color: '#f97316', dash: '',     source: 'swap' },
  ]

  // Build date-indexed lookups
  const swapByDate = {}
  const bkbmByDate = {}

  ;(swapHistory || []).forEach(row => { swapByDate[row.date] = row })
  ;(bkbmHistory || []).forEach(row => { bkbmByDate[row.date] = row })

  // Merge ALL dates from both swap and BKBM histories into one unified timeline
  const swapDates = Object.keys(swapByDate).sort()
  const allBkbmDates = Object.keys(bkbmByDate).sort()
  const allDatesSet = new Set([...swapDates, ...allBkbmDates])
  const sortedDates = [...allDatesSet].sort()

  if (sortedDates.length < 2) {
    return <div className="text-gray-400 text-center py-8 text-sm">Not enough data for chart. Scrape some rates first.</div>
  }

  // Forward-fill BKBM/OCR: for each date, carry forward the last known BKBM value
  const filledBkbmByDate = {}
  const bkbmKeys = ['OCR', 'BB90D']
  const lastKnownBkbm = {}
  sortedDates.forEach(date => {
    const exact = bkbmByDate[date]
    const filled = exact ? { ...exact } : { date }
    bkbmKeys.forEach(key => {
      if (filled[key] != null) { lastKnownBkbm[key] = filled[key] }
      else if (lastKnownBkbm[key] != null) { filled[key] = lastKnownBkbm[key] }
    })
    filledBkbmByDate[date] = filled
  })

  // Forward-fill Swap rates: carry forward last known swap value for each tenor
  const filledSwapByDate = {}
  const swapKeys = ['1Y', '2Y', '3Y', '4Y', '5Y', '7Y', '10Y']
  const lastKnownSwap = {}
  sortedDates.forEach(date => {
    const exact = swapByDate[date]
    const filled = exact ? { ...exact } : { date }
    swapKeys.forEach(key => {
      if (filled[key] != null) { lastKnownSwap[key] = filled[key] }
      else if (lastKnownSwap[key] != null) { filled[key] = lastKnownSwap[key] }
    })
    filledSwapByDate[date] = filled
  })

  // Use filled versions for chart rendering
  const chartBkbmByDate = filledBkbmByDate
  const chartSwapByDate = filledSwapByDate

  const padding = { top: 20, right: 160, bottom: 45, left: 55 }
  const cw = width - padding.left - padding.right
  const ch = height - padding.top - padding.bottom

  // Gather all values across all series for Y scale
  let allVals = []
  sortedDates.forEach(date => {
    SERIES.forEach(s => {
      const row = s.source === 'swap' ? chartSwapByDate[date] : chartBkbmByDate[date]
      if (row && row[s.key] != null) allVals.push(row[s.key])
    })
  })
  if (allVals.length === 0) {
    return <div className="text-gray-400 text-center py-8 text-sm">No rate data found in history.</div>
  }

  const minVal = Math.floor(Math.min(...allVals) * 2) / 2  // Round down to nearest 0.5
  const maxVal = Math.ceil(Math.max(...allVals) * 2) / 2    // Round up to nearest 0.5
  const range = maxVal - minVal || 1

  const xScale = cw / (sortedDates.length - 1)
  const getX = (i) => padding.left + i * xScale
  const getY = (val) => padding.top + ch - ((val - minVal) / range) * ch

  // Build paths for each series
  const seriesPaths = SERIES.map(s => {
    const points = []
    sortedDates.forEach((date, i) => {
      const row = s.source === 'swap' ? chartSwapByDate[date] : chartBkbmByDate[date]
      if (row && row[s.key] != null) {
        points.push({ x: getX(i), y: getY(row[s.key]), val: row[s.key] })
      }
    })
    if (points.length < 2) return null
    const d = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
    return { ...s, d, lastPoint: points[points.length - 1] }
  }).filter(Boolean)

  // Y grid lines
  const yGridCount = Math.min(8, Math.ceil(range / 0.5) + 1)
  const yStep = range / (yGridCount - 1)
  const yGridLines = Array.from({ length: yGridCount }, (_, i) => minVal + i * yStep)

  // X date labels
  const labelStep = Math.max(1, Math.floor(sortedDates.length / 6))

  return (
    <div className="overflow-x-auto">
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="w-full">
        {/* Background */}
        <rect x={padding.left} y={padding.top} width={cw} height={ch} fill="#fafafa" />

        {/* Y grid + labels */}
        {yGridLines.map((val, i) => {
          const y = getY(val)
          return (
            <g key={`yg-${i}`}>
              <line x1={padding.left} y1={y} x2={padding.left + cw} y2={y} stroke="#e5e7eb" strokeWidth="1" />
              <text x={padding.left - 8} y={y + 4} textAnchor="end" fontSize="10" fill="#6b7280">{val.toFixed(1)}%</text>
            </g>
          )
        })}

        {/* X date labels */}
        {sortedDates.map((date, i) => {
          if (i % labelStep !== 0 && i !== sortedDates.length - 1) return null
          const x = getX(i)
          const d = new Date(date + 'T00:00:00')
          const label = sortedDates.length > 100
            ? d.toLocaleDateString('en-NZ', { month: 'short', year: '2-digit' })
            : d.toLocaleDateString('en-NZ', { month: 'short', day: 'numeric' })
          return (
            <g key={`xg-${i}`}>
              <line x1={x} y1={padding.top + ch} x2={x} y2={padding.top + ch + 5} stroke="#d1d5db" />
              <text x={x} y={height - 8} textAnchor="middle" fontSize="9" fill="#9ca3af">{label}</text>
            </g>
          )
        })}

        {/* Data lines */}
        {seriesPaths.map(s => (
          <path
            key={s.key}
            d={s.d}
            fill="none"
            stroke={s.color}
            strokeWidth={s.key === 'OCR' ? 2.5 : 1.8}
            strokeDasharray={s.dash}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ))}

        {/* End labels (legend on right side) */}
        {seriesPaths.map((s, i) => {
          if (!s.lastPoint) return null
          return (
            <g key={`lbl-${s.key}`}>
              <circle cx={s.lastPoint.x} cy={s.lastPoint.y} r="3" fill={s.color} />
              <text
                x={padding.left + cw + 8}
                y={s.lastPoint.y + 4}
                fontSize="10"
                fontWeight="600"
                fill={s.color}
              >
                {s.label} {s.lastPoint.val.toFixed(2)}%
              </text>
            </g>
          )
        })}

        {/* Axis border */}
        <rect x={padding.left} y={padding.top} width={cw} height={ch} fill="none" stroke="#d1d5db" />
      </svg>
    </div>
  )
}

/**
 * Simple SVG line chart for rate history
 */
function RateChart({ data, width = 600, height = 220, title, color = '#3b82f6' }) {
  if (!data || data.length === 0) {
    return <div className="text-gray-400 text-center py-6 text-sm">No history yet</div>
  }

  const padding = { top: 15, right: 15, bottom: 35, left: 50 }
  const chartWidth = width - padding.left - padding.right
  const chartHeight = height - padding.top - padding.bottom

  const rates = data.map(d => d.rate_pct)
  const minRate = Math.min(...rates) - 0.1
  const maxRate = Math.max(...rates) + 0.1
  const rateRange = maxRate - minRate || 1

  const scaleX = chartWidth / (data.length - 1 || 1)
  const scaleY = chartHeight / rateRange

  const getX = (i) => padding.left + i * scaleX
  const getY = (rate) => padding.top + chartHeight - (rate - minRate) * scaleY

  const path = data
    .map((d, i) => `${i === 0 ? 'M' : 'L'} ${getX(i)},${getY(d.rate_pct)}`)
    .join(' ')

  const labelStep = Math.max(1, Math.ceil(data.length / 5))

  return (
    <div>
      {title && <p className="text-sm font-medium text-gray-700 mb-1">{title}</p>}
      <svg width={width} height={height} className="w-full" viewBox={`0 0 ${width} ${height}`}>
        {/* Grid */}
        {[0, 1, 2, 3].map(i => {
          const y = padding.top + (chartHeight / 3) * i
          const rate = maxRate - (rateRange / 3) * i
          return (
            <g key={`grid-${i}`}>
              <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} stroke="#e5e7eb" />
              <text x={padding.left - 8} y={y + 4} textAnchor="end" fontSize="10" fill="#9ca3af">
                {rate.toFixed(2)}%
              </text>
            </g>
          )
        })}

        {/* Line */}
        <path d={path} fill="none" stroke={color} strokeWidth="2" />

        {/* Dots */}
        {data.map((d, i) => (
          <circle key={i} cx={getX(i)} cy={getY(d.rate_pct)} r="2.5" fill={color} />
        ))}

        {/* X labels */}
        {data.map((d, i) => {
          if (i % labelStep !== 0 && i !== data.length - 1) return null
          const dateStr = d.date ? new Date(d.date).toLocaleDateString('en-NZ', { month: 'short', day: 'numeric' }) : ''
          return (
            <text key={`xl-${i}`} x={getX(i)} y={height - 5} textAnchor="middle" fontSize="9" fill="#9ca3af">
              {dateStr}
            </text>
          )
        })}
      </svg>
    </div>
  )
}

function Audit({ onNavigate }) {
  const [auditData, setAuditData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [scraping, setScraping] = useState(false)
  const [scrapeResult, setScrapeResult] = useState(null)
  const [bankHistories, setBankHistories] = useState({})
  const [expandedBank, setExpandedBank] = useState(null)
  const [historyLoading, setHistoryLoading] = useState({})
  const [error, setError] = useState(null)
  const [wholesaleData, setWholesaleData] = useState(null)
  const [wholesaleLoading, setWholesaleLoading] = useState(false)

  useEffect(() => {
    loadAuditData()
    loadWholesaleData()
  }, [])

  const loadWholesaleData = async () => {
    try {
      setWholesaleLoading(true)
      const data = await getWholesaleRates()
      setWholesaleData(data)
    } catch (err) {
      console.error('Error loading wholesale data:', err)
    } finally {
      setWholesaleLoading(false)
    }
  }

  const loadAuditData = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await getAuditLog(50)
      setAuditData(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleScrape = async () => {
    try {
      setScraping(true)
      setScrapeResult(null)
      const result = await triggerScrape()
      setScrapeResult(result)
      // Reload audit data to show new entry
      await loadAuditData()
    } catch (err) {
      setScrapeResult({ success: false, error: err.message })
    } finally {
      setScraping(false)
    }
  }

  const loadBankHistory = async (bank) => {
    if (bankHistories[bank]) {
      setExpandedBank(expandedBank === bank ? null : bank)
      return
    }

    try {
      setHistoryLoading(prev => ({ ...prev, [bank]: true }))
      const data = await getBankHistory(bank, 0)
      setBankHistories(prev => ({ ...prev, [bank]: data.products || {} }))
      setExpandedBank(bank)
    } catch (err) {
      console.error(`Error loading history for ${bank}:`, err)
    } finally {
      setHistoryLoading(prev => ({ ...prev, [bank]: false }))
    }
  }

  const summary = auditData?.summary || {}
  const auditLog = auditData?.audit_log || []

  const CHART_COLORS = [
    '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
    '#ec4899', '#06b6d4', '#f97316', '#6366f1', '#14b8a6',
  ]

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-screen">
        <div className="text-center">
          <p className="text-gray-600 mb-4">Loading audit data...</p>
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
        </div>
      </div>
    )
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8 flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Rate Audit</h1>
          <p className="text-gray-600">
            Verify rate extraction accuracy, view historical data, and trigger manual scrapes
          </p>
        </div>
        <button
          onClick={handleScrape}
          disabled={scraping}
          className="btn-primary flex items-center gap-2"
        >
          {scraping ? (
            <>
              <span className="inline-block animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
              Scraping...
            </>
          ) : (
            'Run Scrape Now'
          )}
        </button>
      </div>

      {error && (
        <div className="card bg-red-50 border border-red-200 p-4 mb-6 text-red-700">
          <p className="font-medium">Error</p>
          <p className="text-sm">{error}</p>
        </div>
      )}

      {/* Scrape Result Banner */}
      {scrapeResult && (
        <div className={`card p-4 mb-6 border ${
          scrapeResult.success
            ? 'bg-green-50 border-green-200 text-green-800'
            : 'bg-red-50 border-red-200 text-red-800'
        }`}>
          <p className="font-medium mb-1">
            {scrapeResult.success ? 'Scrape Completed Successfully' : 'Scrape Failed'}
          </p>
          {scrapeResult.success && (
            <div className="text-sm space-y-1">
              <p>Products: {scrapeResult.product_count} from {scrapeResult.banks_scraped?.join(', ')}</p>
              <p>OCR: {scrapeResult.ocr_rate != null ? `${scrapeResult.ocr_rate}%` : 'Not available'}</p>
              <p>Wholesale rates: {scrapeResult.wholesale_count}</p>
              {scrapeResult.errors?.length > 0 && (
                <p className="text-amber-700">Warnings: {scrapeResult.errors.join('; ')}</p>
              )}
            </div>
          )}
          {scrapeResult.error && <p className="text-sm">{scrapeResult.error}</p>}
        </div>
      )}

      {/* Data Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        <div className="card p-4 text-center">
          <p className="text-2xl font-bold text-primary">{summary.total_rate_records || 0}</p>
          <p className="text-xs text-gray-500 mt-1">Rate Records</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-2xl font-bold text-primary">{summary.banks?.length || 0}</p>
          <p className="text-xs text-gray-500 mt-1">Banks Tracked</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-2xl font-bold text-primary">{summary.total_wholesale_records || 0}</p>
          <p className="text-xs text-gray-500 mt-1">Wholesale Records</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-2xl font-bold text-primary">{summary.total_ocr_records || 0}</p>
          <p className="text-xs text-gray-500 mt-1">OCR Records</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-2xl font-bold text-primary">{summary.total_scrape_runs || 0}</p>
          <p className="text-xs text-gray-500 mt-1">Total Scrape Runs</p>
        </div>
      </div>

      {/* Database Connection Status */}
      <div className={`card p-4 mb-8 border ${
        summary.supabase_connected
          ? 'bg-green-50 border-green-200'
          : 'bg-amber-50 border-amber-200'
      }`}>
        <div className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full ${
            summary.supabase_connected ? 'bg-green-500' : 'bg-amber-500'
          }`} />
          <div>
            <p className="font-medium text-gray-900">
              {summary.supabase_connected ? 'Supabase Connected' : 'Using Local Storage (Ephemeral)'}
            </p>
            <p className="text-sm text-gray-600">
              {summary.supabase_connected
                ? `Data range: ${summary.earliest_record ? new Date(summary.earliest_record).toLocaleDateString() : 'N/A'} to ${summary.latest_record ? new Date(summary.latest_record).toLocaleDateString() : 'N/A'}`
                : 'Rate history will not persist across container restarts. Run the SQL migration to enable Supabase.'}
            </p>
          </div>
        </div>
      </div>

      {/* Warnings from API */}
      {wholesaleData?.warnings?.length > 0 && (
        <div className="card bg-amber-50 border border-amber-200 p-4 mb-6">
          <p className="font-medium text-amber-800 mb-1">Data Source Warnings</p>
          {wholesaleData.warnings.map((w, i) => (
            <p key={i} className="text-sm text-amber-700">{w}</p>
          ))}
        </div>
      )}

      {/* Combined Time-Series Chart */}
      <div className="card overflow-hidden mb-8">
        <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">NZ Wholesale Rate Curves</h2>
              <p className="text-sm text-gray-600 mt-1">
                Swap rates, 90-day Bank Bill, and OCR — sourced from{' '}
                <a href="https://www.interest.co.nz/charts/interest-rates/swap-rates" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">interest.co.nz</a>
                {wholesaleData?.data_source && (
                  <span className={`ml-2 inline-block px-2 py-0.5 text-xs rounded-full ${
                    wholesaleData.data_source === 'live_scrape'
                      ? 'bg-green-100 text-green-700'
                      : 'bg-blue-100 text-blue-700'
                  }`}>
                    {wholesaleData.data_source === 'live_scrape' ? 'Live' : 'Stored data'}
                  </span>
                )}
              </p>
            </div>
            <button onClick={loadWholesaleData} disabled={wholesaleLoading} className="btn-secondary text-sm flex items-center gap-1">
              {wholesaleLoading ? (
                <><span className="inline-block animate-spin h-3 w-3 border-2 border-primary border-t-transparent rounded-full" /> Loading...</>
              ) : 'Refresh'}
            </button>
          </div>
        </div>

        <div className="p-6">
          <WholesaleTimeSeriesChart
            swapHistory={wholesaleData?.history?.swap || []}
            bkbmHistory={wholesaleData?.history?.bkbm || []}
          />
        </div>
      </div>

      {/* Current Rate Snapshot Cards */}
      <div className="card overflow-hidden mb-8">
        <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Latest Rate Snapshot</h2>
        </div>
        <div className="p-6">
          {wholesaleData?.latest?.swap?.length > 0 || wholesaleData?.latest?.bkbm?.length > 0 ? (
            <div className="space-y-6">
              {wholesaleData.latest.swap?.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-3">Swap Rates</h3>
                  <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
                    {wholesaleData.latest.swap.map(rate => (
                      <div key={rate.tenor || rate.rate_name} className="bg-blue-50 rounded-lg p-3 text-center">
                        <p className="text-xs text-blue-600 font-medium">{rate.tenor || rate.rate_name}</p>
                        <p className="text-xl font-bold text-blue-900">{rate.rate_pct?.toFixed(2)}%</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {wholesaleData.latest.bkbm?.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-3">OCR & Bank Bill</h3>
                  <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
                    {wholesaleData.latest.bkbm.map(rate => (
                      <div key={rate.tenor || rate.rate_name} className="bg-green-50 rounded-lg p-3 text-center">
                        <p className="text-xs text-green-600 font-medium">{rate.tenor || rate.rate_name}</p>
                        <p className="text-xl font-bold text-green-900">{rate.rate_pct?.toFixed(2)}%</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              <p className="text-xs text-gray-400 text-right">
                Last updated: {wholesaleData.scraped_at ? new Date(wholesaleData.scraped_at).toLocaleString('en-NZ') : 'Unknown'}
              </p>
            </div>
          ) : (
            <div className="text-center py-6">
              <p className="text-gray-500 text-sm">No wholesale rate data available yet. Run a browser scrape to collect data.</p>
            </div>
          )}
        </div>
      </div>

      {/* Source Verification Links */}
      <div className="card p-6 mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Verify Rate Sources</h2>
        <p className="text-sm text-gray-600 mb-4">
          Click any link below to manually verify the extracted rates against the source website.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {[
            { name: 'Swap Rates Chart', url: 'https://www.interest.co.nz/charts/interest-rates/swap-rates', desc: 'Daily NZ swap rate curves' },
            { name: 'ANZ Business Rates', url: 'https://www.anz.co.nz/business/borrowing-options/', desc: 'ANZ corporate lending rates' },
            { name: 'ASB Business Rates', url: 'https://www.asb.co.nz/business-loans-and-finance/interest-rates', desc: 'ASB business loan rates' },
            { name: 'BNZ Business Rates', url: 'https://www.bnz.co.nz/business-banking/borrow', desc: 'BNZ business borrowing rates' },
            { name: 'Kiwibank Business', url: 'https://www.kiwibank.co.nz/business-banking/loans-and-credit/', desc: 'Kiwibank business lending' },
            { name: 'Westpac Business', url: 'https://www.westpac.co.nz/business/borrowing/', desc: 'Westpac business borrowing' },
            { name: 'RBNZ OCR', url: 'https://www.rbnz.govt.nz/monetary-policy/official-cash-rate-decisions', desc: 'Official Cash Rate decisions' },
            { name: 'interest.co.nz Base Rates', url: 'https://www.interest.co.nz/borrowing/business-base-rates', desc: 'All bank base rates comparison' },
            { name: 'NZFMA', url: 'https://www.nzfma.org/', desc: 'NZ Financial Markets Association' },
          ].map(link => (
            <a
              key={link.name}
              href={link.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-start gap-3 p-3 rounded-lg border border-gray-200 hover:border-primary hover:bg-blue-50 transition-colors"
            >
              <span className="text-primary mt-0.5">🔗</span>
              <div>
                <p className="text-sm font-medium text-gray-900">{link.name}</p>
                <p className="text-xs text-gray-500">{link.desc}</p>
              </div>
            </a>
          ))}
        </div>
      </div>

      {/* Bank Rate History Section */}
      <div className="card overflow-hidden mb-8">
        <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Bank Rate History</h2>
          <p className="text-sm text-gray-600 mt-1">
            Click a bank to load time series charts for all its products
          </p>
        </div>

        <div className="divide-y divide-gray-200">
          {(summary.banks || []).map(bank => (
            <div key={bank}>
              <button
                onClick={() => loadBankHistory(bank)}
                className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
              >
                <span className="font-medium text-gray-900">{bank}</span>
                <span className="text-gray-400">
                  {historyLoading[bank] ? (
                    <span className="inline-block animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full" />
                  ) : expandedBank === bank ? (
                    '▲'
                  ) : (
                    '▼'
                  )}
                </span>
              </button>

              {expandedBank === bank && bankHistories[bank] && (
                <div className="px-6 pb-6 bg-gray-50">
                  {Object.keys(bankHistories[bank]).length === 0 ? (
                    <p className="text-gray-500 text-sm py-4">
                      No history yet. Run a scrape to start collecting data.
                    </p>
                  ) : (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                      {Object.entries(bankHistories[bank]).map(([productName, history], idx) => {
                        const latestRate = history.length > 0 ? history[history.length - 1].rate_pct : null
                        return (
                          <div key={productName} className="bg-white rounded-lg p-4 shadow-sm">
                            <div className="flex justify-between items-baseline mb-2">
                              <p className="text-sm font-semibold text-gray-900">{productName}</p>
                              {latestRate != null && (
                                <span className="text-lg font-bold text-primary">
                                  {latestRate.toFixed(2)}%
                                </span>
                              )}
                            </div>
                            <p className="text-xs text-gray-500 mb-2">
                              {history.length} data point{history.length !== 1 ? 's' : ''}
                            </p>
                            <RateChart
                              data={history}
                              width={500}
                              height={180}
                              color={CHART_COLORS[idx % CHART_COLORS.length]}
                            />
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}

          {(!summary.banks || summary.banks.length === 0) && (
            <div className="px-6 py-8 text-center text-gray-500">
              No banks tracked yet. Run a scrape to start collecting data.
            </div>
          )}
        </div>
      </div>

      {/* Audit Log Table */}
      <div className="card overflow-hidden mb-8">
        <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Scrape Audit Log</h2>
          <p className="text-sm text-gray-600 mt-1">
            Detailed record of every rate scrape run
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600">Date/Time</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600">Trigger</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-gray-600">Products</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600">Banks</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-gray-600">OCR</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-gray-600">Wholesale</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-gray-600">Duration</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {auditLog.map((entry, idx) => {
                const hasErrors = entry.errors && entry.errors.length > 0
                return (
                  <tr key={entry.id || idx} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-900 whitespace-nowrap">
                      {new Date(entry.scraped_at).toLocaleString('en-NZ', {
                        month: 'short', day: 'numeric',
                        hour: '2-digit', minute: '2-digit'
                      })}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-block px-2 py-0.5 text-xs rounded-full ${
                        entry.trigger_type === 'scheduled'
                          ? 'bg-blue-100 text-blue-700'
                          : entry.trigger_type === 'manual'
                          ? 'bg-green-100 text-green-700'
                          : 'bg-gray-100 text-gray-700'
                      }`}>
                        {entry.trigger_type}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-right font-medium">{entry.product_count}</td>
                    <td className="px-4 py-3 text-xs text-gray-600">
                      {(entry.banks_scraped || []).join(', ')}
                    </td>
                    <td className="px-4 py-3 text-sm text-right">
                      {entry.ocr_rate != null ? `${entry.ocr_rate}%` : '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-right">{entry.wholesale_count}</td>
                    <td className="px-4 py-3 text-sm text-right text-gray-600">
                      {entry.duration_ms ? `${(entry.duration_ms / 1000).toFixed(1)}s` : '-'}
                    </td>
                    <td className="px-4 py-3">
                      {hasErrors ? (
                        <span className="text-xs text-amber-600" title={entry.errors.join('\n')}>
                          ⚠ {entry.errors.length} warning{entry.errors.length > 1 ? 's' : ''}
                        </span>
                      ) : (
                        <span className="text-xs text-green-600">OK</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {auditLog.length === 0 && (
          <div className="px-6 py-8 text-center text-gray-500">
            No scrape runs recorded yet. Click "Run Scrape Now" to start.
          </div>
        )}
      </div>

      {/* Navigation */}
      <div className="flex gap-4">
        <button onClick={() => onNavigate('#/rates')} className="btn-secondary">
          Back to Base Rates
        </button>
        <button onClick={() => onNavigate('#/dashboard')} className="btn-secondary">
          Back to Dashboard
        </button>
      </div>
    </div>
  )
}

export default Audit
