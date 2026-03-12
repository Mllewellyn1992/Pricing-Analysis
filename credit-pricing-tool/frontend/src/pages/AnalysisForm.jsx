import { useState, useEffect } from 'react'
import { analyzeFinancials, getAllProducts } from '../api'

// Map backend extraction field names → frontend form field names
const EXTRACTION_TO_FORM = {
  revenue_mn: 'revenue',
  ebit_mn: 'ebit',
  depreciation_mn: 'depreciation',
  amortization_mn: 'amortization',
  interest_expense_mn: 'interestExpense',
  cash_interest_paid_mn: 'cashInterestPaid',
  cash_taxes_paid_mn: 'cashTaxesPaid',
  total_debt_mn: 'totalDebt',
  st_debt_mn: 'stDebt',
  cpltd_mn: 'cpltd',
  lt_debt_net_mn: 'ltDebt',
  capital_leases_mn: 'capitalLeases',
  cash_mn: 'cash',
  cash_like_mn: 'cashLikeAssets',
  total_equity_mn: 'totalEquity',
  minority_interest_mn: 'minorityInterest',
  deferred_taxes_mn: 'deferredTaxes',
  cfo_mn: 'cfo',
  capex_mn: 'capex',
  common_dividends_mn: 'commonDividends',
  preferred_dividends_mn: 'preferredDividends',
  nwc_current_mn: 'nwcCurrent',
  nwc_prior_mn: 'nwcPrior',
  lt_operating_assets_current_mn: 'ltOperatingAssetsCurrent',
  lt_operating_assets_prior_mn: 'ltOperatingAssetsPrior',
  assets_current_mn: 'totalAssetsCurrent',
  assets_prior_mn: 'totalAssetsPrior',
  avg_capital_mn: 'avgCapital',
}

// Industry dropdown: display name → backend sector_id (matches YAML filenames)
const INDUSTRIES = [
  { label: 'Select an industry', value: '' },
  { label: 'Aerospace & Defense', value: 'aerospace_and_defense' },
  { label: 'Agribusiness & Food', value: 'agribusiness_commodity_foods_and_agricultural_cooperatives' },
  { label: 'Asset Managers', value: 'asset_managers' },
  { label: 'Auto Manufacturing', value: 'auto_and_commercial_vehicle_manufacturing' },
  { label: 'Auto Suppliers', value: 'auto_suppliers' },
  { label: 'Building Materials', value: 'building_materials' },
  { label: 'Business & Consumer Services', value: 'business_and_consumer_services' },
  { label: 'Capital Goods / Manufacturing', value: 'capital_goods' },
  { label: 'Chemicals (Commodity)', value: 'commodity_chemicals' },
  { label: 'Chemicals (Specialty)', value: 'specialty_chemicals' },
  { label: 'Consumer Durables', value: 'consumer_durables' },
  { label: 'Consumer Staples / Branded Goods', value: 'consumer_staples_and_branded_nondurables' },
  { label: 'Containers & Packaging', value: 'containers_and_packaging' },
  { label: 'Contract Drilling', value: 'contract_drilling' },
  { label: 'Engineering & Construction', value: 'engineering_and_construction' },
  { label: 'Environmental Services', value: 'environmental_services' },
  { label: 'Financial Market Infrastructure', value: 'financial_market_infrastructure' },
  { label: 'Financial Services / Finance Companies', value: 'financial_services_finance_companies' },
  { label: 'Forest & Paper Products', value: 'forest_and_paper_products' },
  { label: 'Health Care Equipment', value: 'health_care_equipment' },
  { label: 'Health Care Services', value: 'health_care_services' },
  { label: 'Homebuilders & Real Estate Developers', value: 'homebuilders_and_real_estate_developers' },
  { label: 'Leisure & Sports', value: 'leisure_and_sports' },
  { label: 'Media & Entertainment', value: 'media_and_entertainment' },
  { label: 'Metals Production & Processing', value: 'metals_production_and_processing' },
  { label: 'Midstream Energy', value: 'midstream_energy' },
  { label: 'Mining', value: 'mining' },
  { label: 'Oil & Gas E&P', value: 'oil_and_gas_exploration_and_production' },
  { label: 'Oilfield Services & Equipment', value: 'oilfield_services_and_equipment' },
  { label: 'Pharmaceuticals', value: 'pharmaceuticals' },
  { label: 'Railroad, Package Express & Logistics', value: 'railroad_package_express_and_logistics' },
  { label: 'Refining & Marketing', value: 'refining_and_marketing' },
  { label: 'Regulated Utilities', value: 'regulated_utilities' },
  { label: 'Retail & Restaurants', value: 'retail_and_restaurants' },
  { label: 'Technology Hardware & Semiconductors', value: 'technology_hardware_and_semiconductors' },
  { label: 'Technology Software & Services', value: 'technology_software_and_services' },
  { label: 'Telecommunications', value: 'telecommunications' },
  { label: 'Transportation (Cyclical)', value: 'transportation_cyclical' },
  { label: 'Transportation Infrastructure', value: 'transportation_infrastructure' },
  { label: 'Unregulated Power & Gas', value: 'unregulated_power_and_gas' },
]

const EMPTY_FORM = {
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
  currentMargin: '',
  tenor: '3',
  selectedBank: '',
  selectedProduct: '',
  selectedBaseRate: null,
}

function AnalysisForm({ onResults, extractedData, onClearExtracted }) {
  const [loading, setLoading] = useState(false)
  const [expandedSections, setExpandedSections] = useState({
    company: true,
    income: true,
    balance: false,
    cashflow: false,
    facility: true,
  })

  const [formData, setFormData] = useState({ ...EMPTY_FORM })
  const [autoFilledFields, setAutoFilledFields] = useState({})
  const [extractionSource, setExtractionSource] = useState(null)
  const [bankProducts, setBankProducts] = useState([])
  const [productsLoading, setProductsLoading] = useState(true)

  // Fetch all bank products on mount
  useEffect(() => {
    const fetchProducts = async () => {
      try {
        const products = await getAllProducts()
        setBankProducts(products)
      } catch (err) {
        console.error('Failed to load bank products:', err)
      } finally {
        setProductsLoading(false)
      }
    }
    fetchProducts()
  }, [])

  // Derived: unique banks and filtered products for selected bank
  const availableBanks = [...new Set(bankProducts.map(p => p.bank))].sort()
  const productsForBank = formData.selectedBank
    ? bankProducts.filter(p => p.bank === formData.selectedBank)
    : []

  // When bank changes, reset product selection
  const handleBankChange = (e) => {
    const bank = e.target.value
    setFormData(prev => ({
      ...prev,
      selectedBank: bank,
      selectedProduct: '',
      selectedBaseRate: null,
    }))
  }

  // When product changes, set the base rate
  const handleProductChange = (e) => {
    const productName = e.target.value
    const product = productsForBank.find(p => p.product_name === productName)
    setFormData(prev => ({
      ...prev,
      selectedProduct: productName,
      selectedBaseRate: product ? product.rate_pct : null,
    }))
  }

  // Computed all-in rate
  const margin = parseFloat(formData.currentMargin) || 0
  const baseRate = formData.selectedBaseRate || 0
  const allInRate = baseRate + margin

  // When extractedData arrives, pre-fill the form
  useEffect(() => {
    if (extractedData && extractedData.fields) {
      const fields = extractedData.fields
      const confidence = extractedData.confidence || {}
      const newFormData = { ...EMPTY_FORM }
      const filled = {}

      for (const [backendKey, value] of Object.entries(fields)) {
        const formKey = EXTRACTION_TO_FORM[backendKey]
        if (formKey && value != null && value !== 0) {
          newFormData[formKey] = String(value)
          filled[formKey] = {
            value,
            confidence: confidence[backendKey] || null,
            source: backendKey,
          }
        }
      }

      // Set company name from filename
      if (extractedData.fileName) {
        const name = extractedData.fileName
          .replace(/\.pdf$/i, '')
          .replace(/[_-]/g, ' ')
          .replace(/\d{4}$/g, '')
          .trim()
        if (name && !newFormData.companyName) {
          newFormData.companyName = name
        }
      }

      // Set business description from AI classification reasoning (more useful than raw PDF header)
      if (extractedData.sectorClassification?.reasoning) {
        newFormData.businessDescription = extractedData.sectorClassification.reasoning
      } else if (extractedData.businessDescription) {
        newFormData.businessDescription = extractedData.businessDescription
      }

      // Set sector if AI-classified
      if (extractedData.sectorClassification) {
        const sc = extractedData.sectorClassification
        // Find matching industry value
        const match = INDUSTRIES.find(i => i.value === sc.sp_sector)
        if (match) {
          newFormData.industry = sc.sp_sector
        }
      }

      setFormData(newFormData)
      setAutoFilledFields(filled)
      setExtractionSource({
        fileName: extractedData.fileName,
        method: extractedData.method,
        fieldCount: Object.keys(filled).length,
        sectorClassification: extractedData.sectorClassification || null,
      })

      // Open all sections that have filled data
      setExpandedSections({
        company: true,
        income: ['revenue', 'ebit', 'depreciation', 'amortization', 'interestExpense', 'cashInterestPaid', 'cashTaxesPaid'].some((k) => filled[k]),
        balance: ['totalDebt', 'stDebt', 'cpltd', 'ltDebt', 'capitalLeases', 'cash', 'cashLikeAssets', 'totalEquity', 'minorityInterest', 'deferredTaxes', 'nwcCurrent', 'nwcPrior', 'totalAssetsCurrent', 'totalAssetsPrior'].some((k) => filled[k]),
        cashflow: ['cfo', 'capex', 'commonDividends', 'preferredDividends'].some((k) => filled[k]),
        facility: true,
      })
    }
  }, [extractedData])

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
    if (autoFilledFields[name]) {
      setAutoFilledFields((prev) => ({
        ...prev,
        [name]: { ...prev[name], modified: true },
      }))
    }
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

  const handleClearForm = () => {
    setFormData({ ...EMPTY_FORM })
    setAutoFilledFields({})
    setExtractionSource(null)
    if (onClearExtracted) onClearExtracted()
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

  const renderInput = (label, name, placeholder = '') => {
    const isAutoFilled = autoFilledFields[name] && !autoFilledFields[name].modified
    const confidence = autoFilledFields[name]?.confidence

    return (
      <div key={name}>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {label}
          {isAutoFilled && (
            <span className="ml-2 text-xs text-blue-600 font-normal">
              (extracted{confidence ? ` • ${Math.round(confidence * 100)}%` : ''})
            </span>
          )}
        </label>
        <input
          type="text"
          name={name}
          value={formData[name]}
          onChange={handleChange}
          placeholder={placeholder}
          className={`input-field w-full ${
            isAutoFilled ? 'border-blue-300 bg-blue-50' : ''
          }`}
        />
      </div>
    )
  }

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-8">Credit Analysis</h1>

      {/* Extraction source banner */}
      {extractionSource && (
        <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm font-medium text-blue-900">
                Pre-filled from: {extractionSource.fileName}
              </p>
              <p className="text-xs text-blue-700 mt-1">
                {extractionSource.fieldCount} fields extracted using {extractionSource.method} method.
                Fields highlighted in blue were auto-populated.
              </p>
              {extractionSource.sectorClassification && (
                <p className="text-xs text-blue-700 mt-1">
                  AI-classified sector: <span className="font-semibold">
                    {INDUSTRIES.find(i => i.value === extractionSource.sectorClassification.sp_sector)?.label || extractionSource.sectorClassification.sp_sector}
                  </span>
                </p>
              )}
            </div>
            <button
              onClick={handleClearForm}
              className="text-xs text-blue-600 underline hover:text-blue-800 flex-shrink-0 ml-4"
            >
              Clear all
            </button>
          </div>
        </div>
      )}

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
                {formData.businessDescription && extractedData?.sectorClassification && (
                  <span className="ml-2 text-xs text-blue-600 font-normal">(AI-generated from PDF)</span>
                )}
              </label>
              <p className="text-xs text-gray-500 mb-2">
                Describes the company's operations — used for industry classification
              </p>
              <textarea
                name="businessDescription"
                value={formData.businessDescription}
                onChange={handleChange}
                placeholder="e.g., Manufacturing of industrial equipment, focused on dairy and agricultural machinery..."
                rows="4"
                className={`input-field w-full ${
                  formData.businessDescription && extractedData?.sectorClassification ? 'border-blue-300 bg-blue-50' : ''
                }`}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Industry Classification
                {extractedData?.sectorClassification && (
                  <span className="ml-2 text-xs text-green-600 font-normal">
                    (AI-classified • {Math.round((extractedData.sectorClassification.confidence || 0) * 100)}% confidence)
                  </span>
                )}
              </label>
              <select
                name="industry"
                value={formData.industry}
                onChange={handleChange}
                className={`input-field w-full ${
                  extractedData?.sectorClassification ? 'border-blue-300 bg-blue-50' : ''
                }`}
              >
                {INDUSTRIES.map((ind) => (
                  <option key={ind.value} value={ind.value}>
                    {ind.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        ))}

        {/* Income Statement */}
        {renderSection('Income Statement (NZD thousands)', 'income', (
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
        {renderSection('Balance Sheet (NZD thousands)', 'balance', (
          <div>
            <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded">
              <p className="text-sm font-medium text-gray-900 mb-3">
                Debt (enter total OR breakdown)
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {renderInput('Total Debt', 'totalDebt', '0')}
                <div><p className="text-xs text-gray-500 mb-3">Or break down as:</p></div>
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
              <p className="text-sm font-medium text-gray-900 mb-3">Working Capital & Assets</p>
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
        {renderSection('Cash Flow (NZD thousands)', 'cashflow', (
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
          <div className="space-y-6">
            {/* Bank & Product Selection */}
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-sm font-medium text-gray-900 mb-3">Base Rate Selection</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Bank</label>
                  <select
                    value={formData.selectedBank}
                    onChange={handleBankChange}
                    className="input-field w-full"
                    disabled={productsLoading}
                  >
                    <option value="">{productsLoading ? 'Loading banks...' : 'Select a bank'}</option>
                    {availableBanks.map(bank => (
                      <option key={bank} value={bank}>{bank}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Lending Product</label>
                  <select
                    value={formData.selectedProduct}
                    onChange={handleProductChange}
                    className="input-field w-full"
                    disabled={!formData.selectedBank}
                  >
                    <option value="">{formData.selectedBank ? 'Select a product' : 'Select bank first'}</option>
                    {productsForBank.map(p => (
                      <option key={p.product_name} value={p.product_name}>
                        {p.product_name} — {p.rate_pct.toFixed(2)}%
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Show selected base rate */}
              {formData.selectedBaseRate != null && (
                <div className="mt-3 p-3 bg-white border border-blue-300 rounded flex items-center justify-between">
                  <div>
                    <p className="text-xs text-gray-500">Base Rate</p>
                    <p className="text-lg font-bold text-gray-900">
                      {formData.selectedBank} — {formData.selectedProduct}
                    </p>
                  </div>
                  <p className="text-2xl font-bold text-primary">{baseRate.toFixed(2)}%</p>
                </div>
              )}
            </div>

            {/* Margin & Tenor */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Current Margin (%)
                </label>
                <p className="text-xs text-gray-500 mb-1">Your margin above the base rate</p>
                <input
                  type="text"
                  name="currentMargin"
                  value={formData.currentMargin}
                  onChange={handleChange}
                  placeholder="e.g., 2.5"
                  className="input-field w-full"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Facility Tenor (Years)
                </label>
                <select name="tenor" value={formData.tenor} onChange={handleChange} className="input-field w-full">
                  {[1, 2, 3, 4, 5, 7, 10].map((year) => (
                    <option key={year} value={year}>{year} year{year > 1 ? 's' : ''}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* All-In Rate Summary */}
            {formData.selectedBaseRate != null && margin > 0 && (
              <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
                <p className="text-sm font-medium text-gray-900 mb-2">Your All-In Rate</p>
                <div className="flex items-center gap-4 text-lg">
                  <span className="text-gray-700">{baseRate.toFixed(2)}%</span>
                  <span className="text-gray-400">+</span>
                  <span className="text-gray-700">{margin.toFixed(2)}%</span>
                  <span className="text-gray-400">=</span>
                  <span className="text-2xl font-bold text-green-700">{allInRate.toFixed(2)}%</span>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Base rate + margin = all-in rate (this will be compared to the expected market rate)
                </p>
              </div>
            )}
          </div>
        ))}

        {/* Submit */}
        <div className="flex gap-4 mt-8">
          <button
            type="submit"
            disabled={loading}
            className={`btn-primary flex-1 py-3 text-lg font-semibold ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {loading ? 'Analyzing...' : 'Calculate Credit Spread'}
          </button>
          <button type="button" className="btn-secondary px-8 py-3" onClick={handleClearForm}>
            Clear Form
          </button>
        </div>
      </form>

      <div className="mt-12 max-w-4xl p-6 bg-green-50 border border-green-200 rounded-lg">
        <p className="text-sm text-gray-700">
          <span className="font-semibold text-green-700">All values in NZD thousands.</span> Leave blank or enter 0 for not applicable items. Click any pre-filled field to override it.
        </p>
      </div>
    </div>
  )
}

export default AnalysisForm
