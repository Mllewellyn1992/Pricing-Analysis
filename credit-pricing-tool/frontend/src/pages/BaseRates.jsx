import { useState, useEffect } from 'react'
import { getAllProducts, getOCR, getWholesaleRates, getBankHistory, triggerScrape } from '../api'

/**
 * Simple SVG line chart component for rates over time
 */
function SimpleLineChart({ data, lines, width = 700, height = 300, title }) {
  if (!data || data.length === 0) {
    return <div className="text-gray-500 text-center py-8">No data available</div>
  }

  const padding = { top: 20, right: 20, bottom: 40, left: 50 }
  const chartWidth = width - padding.left - padding.right
  const chartHeight = height - padding.top - padding.bottom

  // Find min/max rates across all lines
  let minRate = Infinity
  let maxRate = -Infinity
  lines.forEach(line => {
    data.forEach(d => {
      if (d[line.key] !== undefined) {
        minRate = Math.min(minRate, d[line.key])
        maxRate = Math.max(maxRate, d[line.key])
      }
    })
  })

  const rateRange = maxRate - minRate || 1
  const padding_rates = rateRange * 0.1

  const scaleX = chartWidth / (data.length - 1 || 1)
  const scaleY = chartHeight / (rateRange + padding_rates * 2)

  const getX = (index) => padding.left + index * scaleX
  const getY = (rate) => padding.top + chartHeight - (rate - minRate + padding_rates) * scaleY

  const generatePath = (lineKey) => {
    const points = data
      .map((d, i) => {
        if (d[lineKey] === undefined) return null
        return `${getX(i)},${getY(d[lineKey])}`
      })
      .filter(Boolean)
    return `M ${points.join(' L ')}`
  }

  // Format dates for x-axis
  const xLabels = data.map(d => {
    if (d.date) {
      const date = new Date(d.date)
      return date.toLocaleDateString('en-NZ', { month: 'short', day: 'numeric' })
    }
    return ''
  })

  // Show every 3rd or 5th label to avoid crowding
  const labelStep = Math.ceil(data.length / 4)

  return (
    <div className="w-full overflow-x-auto">
      <svg width={width} height={height} className="mx-auto">
        {/* Grid lines */}
        {[0, 1, 2, 3, 4].map((i) => {
          const y = padding.top + (chartHeight / 4) * i
          return (
            <line
              key={`grid-${i}`}
              x1={padding.left}
              y1={y}
              x2={width - padding.right}
              y2={y}
              stroke="#e5e7eb"
              strokeWidth="1"
            />
          )
        })}

        {/* X-axis */}
        <line
          x1={padding.left}
          y1={padding.top + chartHeight}
          x2={width - padding.right}
          y2={padding.top + chartHeight}
          stroke="#6b7280"
          strokeWidth="2"
        />

        {/* Y-axis */}
        <line
          x1={padding.left}
          y1={padding.top}
          x2={padding.left}
          y2={padding.top + chartHeight}
          stroke="#6b7280"
          strokeWidth="2"
        />

        {/* Y-axis labels and ticks */}
        {[0, 1, 2, 3, 4].map((i) => {
          const rate = minRate + (rateRange / 4) * i + padding_rates
          const y = padding.top + chartHeight - ((rate - minRate) * scaleY)
          return (
            <g key={`y-label-${i}`}>
              <line x1={padding.left - 5} y1={y} x2={padding.left} y2={y} stroke="#6b7280" />
              <text
                x={padding.left - 10}
                y={y + 4}
                textAnchor="end"
                fontSize="12"
                fill="#6b7280"
              >
                {rate.toFixed(2)}%
              </text>
            </g>
          )
        })}

        {/* X-axis labels and ticks */}
        {data.map((d, i) => {
          if (i % labelStep !== 0 && i !== data.length - 1) return null
          return (
            <g key={`x-label-${i}`}>
              <line
                x1={getX(i)}
                y1={padding.top + chartHeight}
                x2={getX(i)}
                y2={padding.top + chartHeight + 5}
                stroke="#6b7280"
              />
              <text
                x={getX(i)}
                y={padding.top + chartHeight + 20}
                textAnchor="middle"
                fontSize="12"
                fill="#6b7280"
              >
                {xLabels[i]}
              </text>
            </g>
          )
        })}

        {/* Data lines */}
        {lines.map((line) => (
          <g key={line.key}>
            <path
              d={generatePath(line.key)}
              fill="none"
              stroke={line.color}
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            {/* Dots at each data point */}
            {data.map((d, i) => {
              if (d[line.key] === undefined) return null
              return (
                <circle
                  key={`dot-${line.key}-${i}`}
                  cx={getX(i)}
                  cy={getY(d[line.key])}
                  r="3"
                  fill={line.color}
                />
              )
            })}
          </g>
        ))}
      </svg>

      {/* Legend */}
      <div className="flex flex-wrap gap-6 mt-6 justify-center">
        {lines.map((line) => (
          <div key={line.key} className="flex items-center gap-2">
            <div
              className="w-4 h-4 rounded"
              style={{ backgroundColor: line.color }}
            />
            <span className="text-sm font-medium text-gray-700">{line.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function BankHistoryChart({ data, width = 500, height = 180, color = '#3b82f6' }) {
  if (!data || data.length === 0) {
    return <div className="text-gray-400 text-center py-4 text-sm">No history yet</div>
  }

  const padding = { top: 15, right: 15, bottom: 30, left: 50 }
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
    <svg width={width} height={height} className="w-full" viewBox={`0 0 ${width} ${height}`}>
      {[0, 1, 2, 3].map(i => {
        const y = padding.top + (chartHeight / 3) * i
        const rate = maxRate - (rateRange / 3) * i
        return (
          <g key={`g-${i}`}>
            <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} stroke="#e5e7eb" />
            <text x={padding.left - 8} y={y + 4} textAnchor="end" fontSize="10" fill="#9ca3af">
              {rate.toFixed(2)}%
            </text>
          </g>
        )
      })}
      <path d={path} fill="none" stroke={color} strokeWidth="2" />
      {data.map((d, i) => (
        <circle key={i} cx={getX(i)} cy={getY(d.rate_pct)} r="2.5" fill={color} />
      ))}
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
  )
}

const CHART_COLORS = [
  '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
  '#ec4899', '#06b6d4', '#f97316', '#6366f1', '#14b8a6',
]

function BaseRates({ onNavigate }) {
  const [allProducts, setAllProducts] = useState([])
  const [ocrData, setOcrData] = useState(null)
  const [wholesaleData, setWholesaleData] = useState(null)
  const [selectedBank, setSelectedBank] = useState('')
  const [selectedProduct, setSelectedProduct] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [bankHistories, setBankHistories] = useState({})
  const [expandedHistoryBank, setExpandedHistoryBank] = useState(null)
  const [historyLoading, setHistoryLoading] = useState({})

  // Fetch all data on mount
  useEffect(() => {
    const fetchAllData = async () => {
      try {
        setLoading(true)
        setError(null)

        const [products, ocr, wholesale] = await Promise.all([
          getAllProducts(),
          getOCR(),
          getWholesaleRates(),
        ])

        setAllProducts(products || [])
        setOcrData(ocr)
        setWholesaleData(wholesale)

        // Auto-select first bank if available
        if (products && products.length > 0) {
          const firstBank = products[0].bank
          setSelectedBank(firstBank)
          // Auto-select first product of that bank
          const firstProduct = products.find(p => p.bank === firstBank)
          if (firstProduct) {
            setSelectedProduct(firstProduct.product_name)
          }
        }
      } catch (err) {
        console.error('Error fetching data:', err)
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    fetchAllData()
  }, [])

  // Get unique banks
  const banks = [...new Set(allProducts.map(p => p.bank))].sort()

  // Get products for selected bank
  const productsForBank = selectedBank
    ? allProducts.filter(p => p.bank === selectedBank).sort((a, b) =>
        a.product_name.localeCompare(b.product_name)
      )
    : []

  // Get selected product details
  const selected = allProducts.find(
    p => p.bank === selectedBank && p.product_name === selectedProduct
  )

  // Group all products by bank for the table
  const productsByBank = {}
  allProducts.forEach(product => {
    if (!productsByBank[product.bank]) {
      productsByBank[product.bank] = []
    }
    productsByBank[product.bank].push(product)
  })

  const sortedBanks = Object.keys(productsByBank).sort()

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-screen">
        <div className="text-center">
          <p className="text-gray-600 mb-4">Loading rates data...</p>
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
        </div>
      </div>
    )
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          NZ Bank Base Rates
        </h1>
        <p className="text-gray-600">
          Current lending rates from major NZ banks, official cash rate, and wholesale benchmarks
        </p>
      </div>

      {error && (
        <div className="card bg-red-50 border border-red-200 p-4 mb-6 text-red-700">
          <p className="font-medium">Error loading rates</p>
          <p className="text-sm">{error}</p>
        </div>
      )}

      {/* Bank & Product Selector Section */}
      <div className="card p-6 mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-6">
          Select Your Base Rate
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          {/* Bank Selector */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Bank
            </label>
            <select
              value={selectedBank}
              onChange={(e) => {
                const newBank = e.target.value
                setSelectedBank(newBank)
                // Auto-select first product of new bank
                const firstProduct = allProducts.find(p => p.bank === newBank)
                if (firstProduct) {
                  setSelectedProduct(firstProduct.product_name)
                }
              }}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
            >
              <option value="">-- Select Bank --</option>
              {banks.map(bank => (
                <option key={bank} value={bank}>
                  {bank}
                </option>
              ))}
            </select>
          </div>

          {/* Product Selector */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Product
            </label>
            <select
              value={selectedProduct}
              onChange={(e) => setSelectedProduct(e.target.value)}
              disabled={!selectedBank}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent disabled:bg-gray-100"
            >
              <option value="">-- Select Product --</option>
              {productsForBank.map(product => (
                <option key={product.product_name} value={product.product_name}>
                  {product.product_name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Selected Rate Display */}
        {selected && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
            <p className="text-sm font-medium text-gray-600 mb-1">Your Selected Base Rate</p>
            <p className="text-5xl font-bold text-primary mb-2">
              {selected.rate_pct.toFixed(2)}%
            </p>
            <div className="space-y-1 text-sm text-gray-600">
              <p>
                <span className="font-medium">Bank:</span> {selected.bank}
              </p>
              <p>
                <span className="font-medium">Product:</span> {selected.product_name}
              </p>
              <p>
                <span className="font-medium">Category:</span> {selected.category}
              </p>
              <p>
                <span className="font-medium">Type:</span> {selected.rate_type}
              </p>
              {selected.source_url && (
                <p>
                  <span className="font-medium">Source:</span>{' '}
                  <a
                    href={selected.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    View Source
                  </a>
                </p>
              )}
              <p className="text-xs text-gray-500 pt-2">
                Scraped: {new Date(selected.scraped_at).toLocaleDateString()}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* OCR Card */}
      {ocrData && (
        <div className="card p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Official Cash Rate (OCR)
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <p className="text-sm text-gray-600 mb-1">Current OCR</p>
              <p className="text-4xl font-bold text-primary">
                {ocrData.rate_pct.toFixed(2)}%
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-600 mb-1">Decision Date</p>
              <p className="text-lg font-semibold text-gray-900">
                {ocrData.decision_date}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-600 mb-1">Source</p>
              <p className="text-sm text-gray-700">
                {ocrData.source}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* BKBM Rates Chart */}
      {wholesaleData?.latest?.bkbm && (
        <div className="card p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">
            BKBM Rates Over Time
          </h2>

          {wholesaleData.history?.bkbm && wholesaleData.history.bkbm.length > 0 ? (
            <>
              <SimpleLineChart
                data={wholesaleData.history.bkbm}
                lines={[
                  { key: 'OCR', label: 'OCR', color: '#ef4444' },
                  { key: '1M', label: 'BKBM 1 Month', color: '#3b82f6' },
                  { key: '2M', label: 'BKBM 2 Month', color: '#8b5cf6' },
                  { key: '3M', label: 'BKBM 3 Month', color: '#06b6d4' },
                  { key: 'BB90D', label: 'BB90D', color: '#f59e0b' },
                ]}
                width={700}
                height={300}
                title="BKBM Rates"
              />

              {/* Latest BKBM Values Table */}
              <div className="mt-8 overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">
                        Tenor
                      </th>
                      <th className="px-6 py-3 text-right text-sm font-semibold text-gray-900">
                        Rate (%)
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {wholesaleData.latest.bkbm.map(rate => (
                      <tr key={rate.tenor} className="hover:bg-gray-50">
                        <td className="px-6 py-4 text-sm text-gray-900 font-medium">
                          {rate.tenor}
                        </td>
                        <td className="px-6 py-4 text-right text-sm font-semibold text-gray-900">
                          {rate.rate_pct.toFixed(3)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <p className="text-gray-500 text-center py-8">No historical BKBM data available</p>
          )}
        </div>
      )}

      {/* Swap Rates Chart */}
      {wholesaleData?.latest?.swap && (
        <div className="card p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">
            Swap Rates Over Time
          </h2>

          {wholesaleData.history?.swap && wholesaleData.history.swap.length > 0 ? (
            <>
              <SimpleLineChart
                data={wholesaleData.history.swap}
                lines={[
                  { key: '1Y', label: 'Swap 1 Year', color: '#10b981' },
                  { key: '2Y', label: 'Swap 2 Year', color: '#ef4444' },
                  { key: '3Y', label: 'Swap 3 Year', color: '#6366f1' },
                  { key: '5Y', label: 'Swap 5 Year', color: '#ec4899' },
                  { key: '7Y', label: 'Swap 7 Year', color: '#14b8a6' },
                  { key: '10Y', label: 'Swap 10 Year', color: '#f97316' },
                ]}
                width={700}
                height={300}
                title="Swap Rates"
              />

              {/* Latest Swap Values Table */}
              <div className="mt-8 overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">
                        Tenor
                      </th>
                      <th className="px-6 py-3 text-right text-sm font-semibold text-gray-900">
                        Rate (%)
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {wholesaleData.latest.swap.map(rate => (
                      <tr key={rate.tenor} className="hover:bg-gray-50">
                        <td className="px-6 py-4 text-sm text-gray-900 font-medium">
                          {rate.tenor}
                        </td>
                        <td className="px-6 py-4 text-right text-sm font-semibold text-gray-900">
                          {rate.rate_pct.toFixed(3)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <p className="text-gray-500 text-center py-8">No historical swap data available</p>
          )}
        </div>
      )}

      {/* All Bank Products Table */}
      <div className="card overflow-hidden mb-8">
        <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">
            All Bank Products
          </h2>
          <p className="text-sm text-gray-600 mt-1">
            Complete listing of all available lending products from NZ banks
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">
                  Bank
                </th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">
                  Product Name
                </th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">
                  Category
                </th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">
                  Type
                </th>
                <th className="px-6 py-4 text-right text-sm font-semibold text-gray-900">
                  Rate (%)
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {sortedBanks.map(bank => (
                <React.Fragment key={bank}>
                  {productsByBank[bank].map((product, idx) => (
                    <tr
                      key={`${bank}-${idx}`}
                      className={`hover:bg-blue-50 transition-colors ${
                        selected?.bank === bank && selected?.product_name === product.product_name
                          ? 'bg-blue-100'
                          : ''
                      }`}
                    >
                      {idx === 0 && (
                        <td
                          rowSpan={productsByBank[bank].length}
                          className="px-6 py-4 font-bold text-gray-900 bg-gray-50"
                        >
                          {bank}
                        </td>
                      )}
                      <td className="px-6 py-4 text-sm text-gray-900">
                        {product.product_name}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        {product.category}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        {product.rate_type}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span className="inline-block px-3 py-1 bg-primary bg-opacity-10 text-primary rounded font-semibold text-sm">
                          {product.rate_pct.toFixed(2)}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>

        {allProducts.length === 0 && (
          <div className="px-6 py-8 text-center text-gray-500">
            No products available
          </div>
        )}
      </div>

      {/* Bank Rate History Section */}
      <div className="card overflow-hidden mb-8">
        <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Rate History by Bank</h2>
          <p className="text-sm text-gray-600 mt-1">
            Click a bank to view time series charts for all its products
          </p>
        </div>

        <div className="divide-y divide-gray-200">
          {sortedBanks.map(bank => (
            <div key={`history-${bank}`}>
              <button
                onClick={async () => {
                  if (expandedHistoryBank === bank) {
                    setExpandedHistoryBank(null)
                    return
                  }
                  if (!bankHistories[bank]) {
                    setHistoryLoading(prev => ({ ...prev, [bank]: true }))
                    try {
                      const data = await getBankHistory(bank, 0)
                      setBankHistories(prev => ({ ...prev, [bank]: data.products || {} }))
                    } catch (err) {
                      console.error(`Error loading history for ${bank}:`, err)
                    } finally {
                      setHistoryLoading(prev => ({ ...prev, [bank]: false }))
                    }
                  }
                  setExpandedHistoryBank(bank)
                }}
                className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <span className="font-medium text-gray-900">{bank}</span>
                  <span className="text-xs text-gray-500">
                    ({productsByBank[bank]?.length || 0} products)
                  </span>
                </div>
                <span className="text-gray-400">
                  {historyLoading[bank] ? (
                    <span className="inline-block animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full" />
                  ) : expandedHistoryBank === bank ? '▲' : '▼'}
                </span>
              </button>

              {expandedHistoryBank === bank && bankHistories[bank] && (
                <div className="px-6 pb-6 bg-gray-50">
                  {Object.keys(bankHistories[bank]).length === 0 ? (
                    <p className="text-gray-500 text-sm py-4">
                      No history data yet. Run a scrape from the Rate Audit page to start collecting data.
                    </p>
                  ) : (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                      {Object.entries(bankHistories[bank]).map(([productName, history], idx) => {
                        const latestRate = history.length > 0 ? history[history.length - 1].rate_pct : null
                        return (
                          <div key={productName} className="bg-white rounded-lg p-4 shadow-sm">
                            <div className="flex justify-between items-baseline mb-1">
                              <p className="text-sm font-semibold text-gray-900">{productName}</p>
                              {latestRate != null && (
                                <span className="text-lg font-bold text-primary">{latestRate.toFixed(2)}%</span>
                              )}
                            </div>
                            <p className="text-xs text-gray-400 mb-2">{history.length} data points</p>
                            <BankHistoryChart
                              data={history}
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
        </div>
      </div>

      {/* Information Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="card p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            How to Use These Rates
          </h3>
          <ul className="space-y-3 text-sm text-gray-600">
            <li className="flex gap-3">
              <span className="text-primary font-bold flex-shrink-0">1</span>
              <span>
                Select your desired bank and product from the dropdown menus above to get your base rate
              </span>
            </li>
            <li className="flex gap-3">
              <span className="text-primary font-bold flex-shrink-0">2</span>
              <span>
                Monitor the Official Cash Rate (OCR) as it directly influences bank pricing
              </span>
            </li>
            <li className="flex gap-3">
              <span className="text-primary font-bold flex-shrink-0">3</span>
              <span>
                Review wholesale rates (BKBM and swaps) to understand interbank funding costs
              </span>
            </li>
            <li className="flex gap-3">
              <span className="text-primary font-bold flex-shrink-0">4</span>
              <span>
                Use your selected base rate in the credit analysis tool to calculate expected pricing
              </span>
            </li>
          </ul>
        </div>

        <div className="card p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Rate Components
          </h3>
          <div className="space-y-3">
            <div className="bg-gray-50 p-3 rounded">
              <p className="text-xs font-medium text-gray-600 mb-1">Base Rate</p>
              <p className="text-sm text-gray-900">
                The starting rate from your selected bank and product
              </p>
            </div>
            <div className="bg-gray-50 p-3 rounded">
              <p className="text-xs font-medium text-gray-600 mb-1">Credit Spread</p>
              <p className="text-sm text-gray-900">
                Premium added for borrower credit quality (determined by analysis)
              </p>
            </div>
            <div className="bg-gray-50 p-3 rounded">
              <p className="text-xs font-medium text-gray-600 mb-1">All-in Rate</p>
              <p className="text-sm text-gray-900">
                Base Rate + Credit Spread = Final facility rate
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Footer and Navigation */}
      <div className="mt-8 p-6 bg-gray-50 border border-gray-200 rounded-lg">
        <p className="text-sm text-gray-600">
          Rates are sourced directly from bank websites and updated regularly. BKBM and swap rates are
          wholesale benchmarks used for funding cost calculations. All rates are indicative and subject to
          borrower credit quality, facility structure, and market conditions.
        </p>
      </div>

      <div className="mt-6 flex gap-4">
        <button
          onClick={() => onNavigate('#/analysis')}
          className="btn-primary"
        >
          Use Rates in Analysis
        </button>
        <button
          onClick={() => onNavigate('#/audit')}
          className="btn-primary"
        >
          Rate Audit
        </button>
        <button
          onClick={() => onNavigate('#/dashboard')}
          className="btn-secondary"
        >
          Back to Dashboard
        </button>
      </div>
    </div>
  )
}

// Import React for Fragment
import React from 'react'

export default BaseRates
