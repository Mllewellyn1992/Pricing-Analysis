import { useState } from 'react'
import { analyzeFinancials } from '../api'

function AnalysisForm({ onResults }) {
  const [loading, setLoading] = useState(false)
  const [expandedSections, setExpandedSections] = useState({
    company: true,
    income: true,
    balance: false,
    cashflow: false,
    facility: true,
  })

  const [formData, setFormData] = useState({
    companyName: '',
    businessDescription: '',
    industry: '',
    revenue: '',
    ebit: '',
    depreciation: '',
    amortization: '',
    interestExpense: '',
    cashInterestPaid: '',
    cashTaxesPaid: '',
    totalDebt: '',
    stDebt: '',
    cpltd: '',
    ltDebt: '',
    capitalLeases: '',
    cash: '',
    cashLikeAssets: '',
    totalEquity: '',
    minorityInterest: '',
    deferredTaxes: '',
    nwcCurrent: '',
    nwcPrior: '',
    ltOperatingAssetsCurrent: '',
    ltOperatingAssetsPrior: '',
    totalAssetsCurrent: '',
    totalAssetsPrior: '',
    cfo: '',
    capex: '',
    commonDividends: '',
    preferredDividends: '',
    minorityDividends: '',
    sharebuybacks: '',
    actualRate: '',
    tenor: '3',
    facilityType: 'corporate',
  })

  const industries = [
    'Select an industry',
    'Aerospace & Defense',
    'Automotive',
    'Banks',
    'Capital Goods',
    'Commercial & Professional Services',
    'Computers & Electronics',
    'Consumer Discretionary',
    'Consumer Staples',
    'Diversified Financials',
    'Energy',
    'Food, Beverage & Tobacco',
    'Health Care Equipment & Services',
    'Health Care Providers & Services',
    'Household & Personal Products',
    'Insurance',
    'Materials',
    'Media',
    'Oil, Gas & Consumable Fuels',
    'Real Estate',
    'Retailing',
    'Semiconductors & Equipment',
    'Software & Services',
    'Technology Hardware & Equipment',
    'Telecommunications Services',
    'Transportation',
    'Utilities',
  ]

  const toggleSection = (section) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }))
  }

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)

    try {
      const results = await analyzeFinancials(formData)
      onResults(results)
    } catch (error) {
      alert('Error analyzing financials: ' + error.message)
    } finally {
      setLoading(false)
    }
  }

  const renderSection = (title, sectionKey, children) => (
    <div className="card mb-6 overflow-hidden">
      <button
        onClick={() => toggleSection(sectionKey)}
        className="section-header w-full"
      >
        <span className={`chevron ${expandedSections[sectionKey] ? 'open' : ''}`}>
          ▼
        </span>
        <h3 className="text-lg font-semibold text-gray-900 flex-1">{title}</h3>
      </button>
      {expandedSections[sectionKey] && (
        <div className="p-6 bg-white">{children}</div>
      )}
    </div>
  )

  const renderInputGroup = (columns = 2) => (children) =>
    <div className={`grid grid-cols-1 md:grid-cols-${columns} gap-4`}>
      {children}
    </div>

  const renderInput = (label, name, placeholder = '') => (
    <div key={name}>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label}
      </label>
      <input
        type="text"
        name={name}
        value={formData[name]}
        onChange={handleChange}
        placeholder={placeholder}
        className="input-field w-full"
      />
    </div>
  )

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-8">Credit Analysis</h1>

      <form onSubmit={handleSubmit} className="max-w-4xl">
        {/* Company Information */}
        {renderSection('Company Information', 'company', (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Company Name
              </label>
              <input
                type="text"
                name="companyName"
                value={formData.companyName}
                onChange={handleChange}
                placeholder="e.g., ABC Manufacturing Ltd"
                className="input-field w-full"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Business Description
              </label>
              <p className="text-xs text-gray-500 mb-2">
                Describe the company's operations for AI sector mapping
              </p>
              <textarea
                name="businessDescription"
                value={formData.businessDescription}
                onChange={handleChange}
                placeholder="e.g., Manufacturing of industrial equipment, focused on dairy and agricultural machinery..."
                rows="4"
                className="input-field w-full"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                S&P Industry Classification
              </label>
              <select
                name="industry"
                value={formData.industry}
                onChange={handleChange}
                className="input-field w-full"
              >
                {industries.map((ind) => (
                  <option key={ind} value={ind}>
                    {ind}
                  </option>
                ))}
              </select>
            </div>
          </div>
        ))}

        {/* Income Statement */}
        {renderSection('Income Statement (NZD millions)', 'income', (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {renderInput('Revenue', 'revenue', '0')}
            {renderInput('EBIT', 'ebit', '0')}
            {renderInput('Depreciation', 'depreciation', '0')}
            {renderInput('Amortization', 'amortization', '0')}
            {renderInput('Interest Expense', 'interestExpense', '0')}
            {renderInput('Cash Interest Paid', 'cashInterestPaid', '0')}
            {renderInput('Cash Taxes Paid', 'cashTaxesPaid', '0')}
          </div>
        ))}

        {/* Balance Sheet */}
        {renderSection('Balance Sheet (NZD millions)', 'balance', (
          <div>
            <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded">
              <p className="text-sm font-medium text-gray-900 mb-3">
                Debt (enter total OR breakdown)
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {renderInput('Total Debt', 'totalDebt', '0')}
                <div>
                  <p className="text-xs text-gray-500 mb-3">Or break down as:</p>
                </div>
                {renderInput('ST Debt', 'stDebt', '0')}
                {renderInput('Current Portion LT Debt', 'cpltd', '0')}
                {renderInput('LT Debt', 'ltDebt', '0')}
                {renderInput('Capital Leases', 'capitalLeases', '0')}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {renderInput('Cash', 'cash', '0')}
              {renderInput('Cash-like Assets', 'cashLikeAssets', '0')}
              {renderInput('Total Equity', 'totalEquity', '0')}
              {renderInput('Minority Interest', 'minorityInterest', '0')}
              {renderInput('Deferred Taxes', 'deferredTaxes', '0')}
            </div>

            <div className="mt-6 p-4 bg-gray-50 border border-gray-200 rounded">
              <p className="text-sm font-medium text-gray-900 mb-3">
                Working Capital & Assets
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {renderInput('NWC (Current)', 'nwcCurrent', '0')}
                {renderInput('NWC (Prior Year)', 'nwcPrior', '0')}
                {renderInput('LT Operating Assets (Current)', 'ltOperatingAssetsCurrent', '0')}
                {renderInput('LT Operating Assets (Prior)', 'ltOperatingAssetsPrior', '0')}
                {renderInput('Total Assets (Current)', 'totalAssetsCurrent', '0')}
                {renderInput('Total Assets (Prior)', 'totalAssetsPrior', '0')}
              </div>
            </div>
          </div>
        ))}

        {/* Cash Flow */}
        {renderSection('Cash Flow (NZD millions)', 'cashflow', (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {renderInput('Operating Cash Flow (CFO)', 'cfo', '0')}
            {renderInput('Capital Expenditures', 'capex', '0')}
            {renderInput('Common Dividends', 'commonDividends', '0')}
            {renderInput('Preferred Dividends', 'preferredDividends', '0')}
            {renderInput('Minority Dividends', 'minorityDividends', '0')}
            {renderInput('Share Buybacks', 'sharebuybacks', '0')}
          </div>
        ))}

        {/* Facility Details */}
        {renderSection('Facility Details', 'facility', (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Actual Interest Rate (%)
              </label>
              <input
                type="text"
                name="actualRate"
                value={formData.actualRate}
                onChange={handleChange}
                placeholder="e.g., 5.5"
                className="input-field w-full"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Facility Tenor (Years)
              </label>
              <select
                name="tenor"
                value={formData.tenor}
                onChange={handleChange}
                className="input-field w-full"
              >
                {[1, 2, 3, 4, 5].map((year) => (
                  <option key={year} value={year}>
                    {year} year{year > 1 ? 's' : ''}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Facility Type
              </label>
              <select
                name="facilityType"
                value={formData.facilityType}
                onChange={handleChange}
                className="input-field w-full"
              >
                <option value="corporate">Corporate Loan</option>
                <option value="working-capital">Working Capital</option>
              </select>
            </div>
          </div>
        ))}

        {/* Submit Button */}
        <div className="flex gap-4 mt-8">
          <button
            type="submit"
            disabled={loading}
            className={`btn-primary flex-1 py-3 text-lg font-semibold ${
              loading ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {loading ? 'Analyzing...' : 'Calculate Credit Spread'}
          </button>
          <button
            type="reset"
            className="btn-secondary px-8 py-3"
            onClick={() =>
              setFormData({
                companyName: '',
                businessDescription: '',
                industry: '',
                revenue: '',
                ebit: '',
                depreciation: '',
                amortization: '',
                interestExpense: '',
                cashInterestPaid: '',
                cashTaxesPaid: '',
                totalDebt: '',
                stDebt: '',
                cpltd: '',
                ltDebt: '',
                capitalLeases: '',
                cash: '',
                cashLikeAssets: '',
                totalEquity: '',
                minorityInterest: '',
                deferredTaxes: '',
                nwcCurrent: '',
                nwcPrior: '',
                ltOperatingAssetsCurrent: '',
                ltOperatingAssetsPrior: '',
                totalAssetsCurrent: '',
                totalAssetsPrior: '',
                cfo: '',
                capex: '',
                commonDividends: '',
                preferredDividends: '',
                minorityDividends: '',
                sharebuybacks: '',
                actualRate: '',
                tenor: '3',
                facilityType: 'corporate',
              })
            }
          >
            Clear Form
          </button>
        </div>
      </form>

      <div className="mt-12 max-w-4xl p-6 bg-green-50 border border-green-200 rounded-lg">
        <p className="text-sm text-gray-700">
          <span className="font-semibold text-green-700">All values in NZD millions.</span> Leave blank or enter 0 for not applicable items. The analysis will compute key financial ratios and benchmark your facility pricing against market rates.
        </p>
      </div>
    </div>
  )
}

export default AnalysisForm
