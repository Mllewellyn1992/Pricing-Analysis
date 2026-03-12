import { useState } from 'react'

function Results({ data, onNavigate }) {
  const [expandedMetrics, setExpandedMetrics] = useState({
    spreads: true,
    allInRates: true,
    comparison: true,
    metrics: true,
    ratios: true,
  })

  if (!data) {
    return (
      <div className="p-8">
        <div className="card p-12 text-center">
          <p className="text-lg text-gray-600 mb-6">
            No analysis results available. Please run an analysis first.
          </p>
          <button onClick={() => onNavigate('#/analysis')} className="btn-primary">
            Go to Analysis
          </button>
        </div>
      </div>
    )
  }

  const toggleMetric = (metric) => {
    setExpandedMetrics((prev) => ({
      ...prev,
      [metric]: !prev[metric],
    }))
  }

  const renderMetricSection = (title, sectionKey, children) => (
    <div className="card mb-6 overflow-hidden">
      <button
        onClick={() => toggleMetric(sectionKey)}
        className="section-header w-full"
      >
        <span className={`chevron ${expandedMetrics[sectionKey] ? 'open' : ''}`}>
          ▼
        </span>
        <h3 className="text-lg font-semibold text-gray-900 flex-1">{title}</h3>
      </button>
      {expandedMetrics[sectionKey] && (
        <div className="p-6 bg-white">{children}</div>
      )}
    </div>
  )

  const minSpread = data.expectedSpreadMin || 220
  const maxSpread = data.expectedSpreadMax || 380
  const avgSpread = (minSpread + maxSpread) / 2
  const baseRate = data.baseRate || 5.0
  const actualRate = parseFloat(data.actualRate) || 5.5
  const delta = actualRate - (baseRate + avgSpread / 10000)

  const minAllInRate = baseRate + minSpread / 10000
  const maxAllInRate = baseRate + maxSpread / 10000
  const avgAllInRate = baseRate + avgSpread / 10000

  const creditGauge = () => {
    const spreadPercentage = ((avgSpread - 100) / 400) * 100
    return Math.max(0, Math.min(100, spreadPercentage))
  }

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          {data.companyName || 'Analysis Results'}
        </h1>
        <p className="text-gray-600">
          {data.industry || 'Company credit analysis'}
        </p>
      </div>

      {/* Executive Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
        <div className="card p-6">
          <p className="text-sm font-medium text-gray-600 mb-2">Expected Spread</p>
          <p className="text-4xl font-bold text-primary mb-1">
            {avgSpread.toFixed(0)} bps
          </p>
          <p className="text-xs text-gray-500">
            Range: {minSpread.toFixed(0)} - {maxSpread.toFixed(0)} bps
          </p>
        </div>

        <div className="card p-6">
          <p className="text-sm font-medium text-gray-600 mb-2">All-In Rate</p>
          <p className="text-4xl font-bold text-primary mb-1">
            {avgAllInRate.toFixed(2)}%
          </p>
          <p className="text-xs text-gray-500">
            Range: {minAllInRate.toFixed(2)}% - {maxAllInRate.toFixed(2)}%
          </p>
        </div>

        <div
          className={`card p-6 ${
            delta < 0 ? 'bg-green-50 border-l-4 border-green-500' : 'bg-red-50 border-l-4 border-red-500'
          }`}
        >
          <p className="text-sm font-medium text-gray-600 mb-2">Rate Delta</p>
          <p
            className={`text-4xl font-bold mb-1 ${
              delta < 0 ? 'text-green-700' : 'text-red-700'
            }`}
          >
            {delta < 0 ? '+' : ''}{Math.abs(delta).toFixed(2)}%
          </p>
          <p className="text-xs text-gray-600">
            {delta < 0 ? 'Saving vs market' : 'Paying above market'}
          </p>
        </div>
      </div>

      {/* Actual vs Expected Rate */}
      {renderMetricSection('Facility Pricing', 'comparison', (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="metric-box">
              <p className="text-sm text-gray-600 mb-1">Base Rate</p>
              <p className="text-2xl font-bold text-gray-900">{baseRate.toFixed(2)}%</p>
              {data.selectedBank && (
                <p className="text-xs text-gray-500 mt-1">{data.selectedBank} — {data.selectedProduct}</p>
              )}
            </div>
            <div className="metric-box">
              <p className="text-sm text-gray-600 mb-1">Your Margin</p>
              <p className="text-2xl font-bold text-gray-900">{(data.currentMargin || 0).toFixed(2)}%</p>
            </div>
            <div className="metric-box">
              <p className="text-sm text-gray-600 mb-1">Your All-In Rate</p>
              <p className="text-2xl font-bold text-gray-900">{actualRate.toFixed(2)}%</p>
            </div>
            <div className="metric-box">
              <p className="text-sm text-gray-600 mb-1">Expected Market Rate</p>
              <p className="text-2xl font-bold text-primary">{avgAllInRate.toFixed(2)}%</p>
              <p className="text-xs text-gray-500 mt-1">Spread: {avgSpread.toFixed(0)} bps</p>
            </div>
          </div>

          <div className="border-t pt-6">
            <div className="flex items-end justify-between mb-4">
              <div>
                <p className="text-sm text-gray-600 mb-1">Your All-In Rate (Base + Margin)</p>
                <p className="text-3xl font-bold text-gray-900">{actualRate.toFixed(2)}%</p>
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-600 mb-1">Variance from Market</p>
                <p
                  className={`text-3xl font-bold ${
                    delta < 0 ? 'text-green-700' : 'text-red-700'
                  }`}
                >
                  {delta < 0 ? '✓' : '✗'} {Math.abs(delta).toFixed(3)}%
                </p>
              </div>
            </div>

            <div className="bg-gray-100 rounded-full h-2 overflow-hidden">
              <div
                className={`h-full ${delta < 0 ? 'bg-green-500' : 'bg-red-500'}`}
                style={{ width: Math.min(100, Math.abs(delta) * 20) + '%' }}
              />
            </div>
            <p className="text-xs text-gray-600 mt-2">
              {delta < 0
                ? `Securing favorable pricing: ${Math.abs(delta * 100).toFixed(1)} basis points below market`
                : `Pricing above market rate by ${(delta * 100).toFixed(1)} basis points`}
            </p>
          </div>
        </div>
      ))}

      {/* Credit Spectrum Gauge */}
      {renderMetricSection('Credit Profile on Spectrum', 'spreads', (
        <div className="space-y-4">
          <div className="flex justify-between text-xs font-medium text-gray-600 mb-2">
            <span>High Risk</span>
            <span>Investment Grade</span>
            <span>Prime</span>
          </div>

          <div className="h-8 gauge-background rounded-full relative overflow-hidden shadow-sm">
            <div
              className="h-full bg-white border-2 border-primary rounded-full absolute transition-all duration-300"
              style={{
                width: '8px',
                left: `calc(${creditGauge()}% - 4px)`,
              }}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-center text-sm">
            <div>
              <p className="text-gray-600 mb-1">Risk Category</p>
              <p className="font-semibold text-gray-900">
                {avgSpread > 350 ? 'Higher Risk' : avgSpread > 250 ? 'Investment Grade' : 'Prime'}
              </p>
            </div>
            <div>
              <p className="text-gray-600 mb-1">Spread Percentile</p>
              <p className="font-semibold text-gray-900">
                {creditGauge().toFixed(0)}th percentile
              </p>
            </div>
            <div>
              <p className="text-gray-600 mb-1">Market Positioning</p>
              <p className="font-semibold text-gray-900">
                {avgSpread < 200 ? 'Top Quartile' : avgSpread < 300 ? 'Above Average' : 'Below Average'}
              </p>
            </div>
          </div>
        </div>
      ))}

      {/* Key Financial Metrics */}
      {renderMetricSection('Computed Financial Metrics', 'metrics', (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[
            {
              label: 'EBITDA',
              value: (data.ebit || 0) + (data.depreciation || 0) + (data.amortization || 0),
              unit: 'NZD thousands',
            },
            {
              label: 'Free Cash Flow',
              value: (data.cfo || 0) - (data.capex || 0),
              unit: 'NZD thousands',
            },
            {
              label: 'Net Debt',
              value:
                (data.totalDebt || 0) -
                (data.cash || 0) -
                (data.cashLikeAssets || 0),
              unit: 'NZD thousands',
            },
            {
              label: 'Total Capital',
              value:
                (data.totalDebt || 0) + (data.totalEquity || 0),
              unit: 'NZD thousands',
            },
            {
              label: 'EBIT Margin',
              value:
                data.revenue && data.revenue > 0
                  ? ((data.ebit || 0) / data.revenue) * 100
                  : 0,
              unit: '%',
            },
            {
              label: 'Operating Cash Conversion',
              value:
                data.ebit && data.ebit > 0
                  ? ((data.cfo || 0) / data.ebit) * 100
                  : 0,
              unit: '%',
            },
          ].map((metric) => (
            <div key={metric.label} className="metric-box">
              <p className="text-sm text-gray-600 mb-1">{metric.label}</p>
              <p className="text-2xl font-bold text-gray-900">
                {typeof metric.value === 'number'
                  ? metric.value.toFixed(1)
                  : metric.value}
              </p>
              <p className="text-xs text-gray-500">{metric.unit}</p>
            </div>
          ))}
        </div>
      ))}

      {/* Credit Ratios */}
      {renderMetricSection('Credit Ratios & Coverage', 'ratios', (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {(() => {
            const ebitda =
              (data.ebit || 0) + (data.depreciation || 0) + (data.amortization || 0)
            const netDebt =
              (data.totalDebt || 0) - (data.cash || 0) - (data.cashLikeAssets || 0)
            const totalCapital = (data.totalDebt || 0) + (data.totalEquity || 0)
            const fcf = (data.cfo || 0) - (data.capex || 0)
            const interestCoverage =
              data.interestExpense && data.interestExpense > 0
                ? ebitda / data.interestExpense
                : 0

            return [
              {
                label: 'Debt / EBITDA',
                value: ebitda > 0 ? netDebt / ebitda : 0,
                benchmark: '< 3.0x',
              },
              {
                label: 'FFO / Debt',
                value: (data.totalDebt || 1) > 0 ? fcf / (data.totalDebt || 1) : 0,
                benchmark: '> 0.25x',
              },
              {
                label: 'EBITDA / Interest',
                value: interestCoverage,
                benchmark: '> 2.5x',
              },
              {
                label: 'Debt / Total Capital',
                value: totalCapital > 0 ? (data.totalDebt || 0) / totalCapital : 0,
                benchmark: '< 60%',
                percent: true,
              },
              {
                label: 'EBITDA / Revenue',
                value:
                  data.revenue && data.revenue > 0
                    ? (ebitda / data.revenue) * 100
                    : 0,
                benchmark: '> 15%',
                percent: true,
              },
              {
                label: 'ROE',
                value:
                  data.totalEquity && data.totalEquity > 0
                    ? ((data.ebit || 0) / data.totalEquity) * 100
                    : 0,
                benchmark: '> 8%',
                percent: true,
              },
            ].map((ratio) => (
              <div key={ratio.label} className="metric-box">
                <p className="text-sm text-gray-600 mb-1">{ratio.label}</p>
                <p className="text-2xl font-bold text-gray-900">
                  {ratio.value.toFixed(2)}
                  {ratio.percent ? '%' : 'x'}
                </p>
                <p className="text-xs text-gray-500">Benchmark: {ratio.benchmark}</p>
              </div>
            ))
          })()}
        </div>
      ))}

      {/* Actions */}
      <div className="flex gap-4 mt-8">
        <button
          onClick={() => onNavigate('#/analysis')}
          className="btn-primary flex-1 py-3"
        >
          Run Another Analysis
        </button>
        <button
          onClick={() => onNavigate('#/')}
          className="btn-secondary px-8 py-3"
        >
          Back to Dashboard
        </button>
      </div>

      <div className="mt-8 p-6 bg-blue-50 border border-blue-200 rounded-lg text-sm text-gray-700">
        <p className="font-semibold text-primary mb-2">Spread Methodology</p>
        <p>
          Expected spreads are calculated using financial ratio analysis, industry benchmarks, and current NZ
          corporate lending market conditions. Actual facility pricing depends on borrower-specific factors,
          relationship history, and market timing. Use these ranges for benchmarking purposes.
        </p>
      </div>
    </div>
  )
}

export default Results
