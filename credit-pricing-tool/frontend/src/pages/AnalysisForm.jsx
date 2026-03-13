import { useState, useEffect, useRef } from 'react'
import { analyzeFinancials, getAllProducts, uploadPDF } from '../api'

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

// Reverse map: form field → backend key
const FORM_TO_EXTRACTION = Object.fromEntries(
  Object.entries(EXTRACTION_TO_FORM).map(([k, v]) => [v, k])
)

// Human-readable labels for financial fields
const FIELD_LABELS = {
  revenue: 'Revenue',
  ebit: 'EBIT',
  depreciation: 'Depreciation',
  amortization: 'Amortization',
  interestExpense: 'Interest Expense',
  cashInterestPaid: 'Cash Interest Paid',
  cashTaxesPaid: 'Cash Taxes Paid',
  totalDebt: 'Total Debt',
  stDebt: 'ST Debt',
  cpltd: 'CPLTD',
  ltDebt: 'LT Debt',
  capitalLeases: 'Capital Leases',
  cash: 'Cash',
  cashLikeAssets: 'Cash-like Assets',
  totalEquity: 'Total Equity',
  minorityInterest: 'Minority Interest',
  deferredTaxes: 'Deferred Taxes',
  nwcCurrent: 'NWC (Current)',
  nwcPrior: 'NWC (Prior)',
  ltOperatingAssetsCurrent: 'LT Op Assets (Curr)',
  ltOperatingAssetsPrior: 'LT Op Assets (Prior)',
  totalAssetsCurrent: 'Total Assets (Curr)',
  totalAssetsPrior: 'Total Assets (Prior)',
  cfo: 'Operating Cash Flow',
  capex: 'Capex',
  commonDividends: 'Common Dividends',
  preferredDividends: 'Preferred Dividends',
  avgCapital: 'Avg Capital',
}

// Industry dropdown
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
  avgCapital: '',
  currentMargin: '',
  tenor: '3',
  selectedBank: '',
  selectedProduct: '',
  selectedBaseRate: null,
}

// Confidence badge
function ConfidenceBadge({ score }) {
  if (score == null) return null
  const pct = Math.round(score * 100)
  let color = 'text-red-600'
  if (pct >= 90) color = 'text-green-600'
  else if (pct >= 75) color = 'text-blue-600'
  else if (pct >= 60) color = 'text-yellow-600'
  return <span className={`text-xs font-medium ${color}`}>{pct}%</span>
}

function AnalysisForm({ onResults, extractedData, onClearExtracted }) {
  const [loading, setLoading] = useState(false)
  const [expandedSections, setExpandedSections] = useState({
    company: true,
    facility: true,
    income: true,
    balance: true,
    cashflow: true,
  })

  const [formData, setFormData] = useState({ ...EMPTY_FORM })
  const [aiValues, setAiValues] = useState({})       // { formFieldName: extractedValue }
  const [aiConfidence, setAiConfidence] = useState({}) // { formFieldName: 0.0-1.0 }
  const [extractionSource, setExtractionSource] = useState(null)
  const [bankProducts, setBankProducts] = useState([])
  const [productsLoading, setProductsLoading] = useState(true)

  // PDF upload state
  const [isDragging, setIsDragging] = useState(false)
  const [uploadStatus, setUploadStatus] = useState(null) // null | 'uploading' | 'extracting' | 'completed' | 'error'
  const [uploadError, setUploadError] = useState(null)
  const [uploadFileName, setUploadFileName] = useState(null)
  const fileInputRef = useRef(null)

  // Fetch bank products on mount
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

  // Derived bank/product state
  const availableBanks = [...new Set(bankProducts.map(p => p.bank))].sort()
  const productsForBank = formData.selectedBank
    ? bankProducts.filter(p => p.bank === formData.selectedBank)
    : []

  const handleBankChange = (e) => {
    setFormData(prev => ({
      ...prev,
      selectedBank: e.target.value,
      selectedProduct: '',
      selectedBaseRate: null,
    }))
  }

  const handleProductChange = (e) => {
    const productName = e.target.value
    const product = productsForBank.find(p => p.product_name === productName)
    setFormData(prev => ({
      ...prev,
      selectedProduct: productName,
      selectedBaseRate: product ? product.rate_pct : null,
    }))
  }

  const margin = parseFloat(formData.currentMargin) || 0
  const baseRate = formData.selectedBaseRate || 0
  const allInRate = baseRate + margin

  // --- PDF Upload handlers ---
  const handleDragEnter = (e) => { e.preventDefault(); e.stopPropagation(); setIsDragging(true) }
  const handleDragLeave = (e) => { e.preventDefault(); e.stopPropagation(); setIsDragging(false) }
  const handleDragOver = (e) => { e.preventDefault(); e.stopPropagation() }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
    const files = Array.from(e.dataTransfer.files)
    if (files.length > 0) handleUpload(files[0])
  }

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files)
    if (files.length > 0) handleUpload(files[0])
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleUpload = async (file) => {
    if (!file.type.includes('pdf') && !file.name.toLowerCase().endsWith('.pdf')) {
      setUploadError('Please upload a PDF file')
      return
    }

    setUploadError(null)
    setUploadStatus('uploading')
    setUploadFileName(file.name)

    try {
      setUploadStatus('extracting')
      const result = await uploadPDF(file)

      // Apply extracted data to the form
      const fields = result?.data || {}
      const confidence = result?.confidenceScores || {}
      const newFormData = { ...EMPTY_FORM }
      const newAiValues = {}
      const newAiConfidence = {}

      for (const [backendKey, value] of Object.entries(fields)) {
        const formKey = EXTRACTION_TO_FORM[backendKey]
        if (formKey && value != null && value !== 0) {
          newFormData[formKey] = String(value)
          newAiValues[formKey] = value
          newAiConfidence[formKey] = confidence[backendKey] || null
        }
      }

      // Set company name from filename
      if (file.name) {
        const name = file.name
          .replace(/\.pdf$/i, '')
          .replace(/[_-]/g, ' ')
          .replace(/\d{4}$/g, '')
          .trim()
        if (name) newFormData.companyName = name
      }

      // Set business description & sector from AI classification
      if (result?.sectorClassification?.reasoning) {
        newFormData.businessDescription = result.sectorClassification.reasoning
      } else if (result?.businessDescription) {
        newFormData.businessDescription = result.businessDescription
      }

      if (result?.sectorClassification) {
        const match = INDUSTRIES.find(i => i.value === result.sectorClassification.sp_sector)
        if (match) newFormData.industry = result.sectorClassification.sp_sector
      }

      setFormData(newFormData)
      setAiValues(newAiValues)
      setAiConfidence(newAiConfidence)
      setExtractionSource({
        fileName: file.name,
        method: result?.extractionMethod || 'unknown',
        fieldCount: Object.keys(newAiValues).length,
        sectorClassification: result?.sectorClassification || null,
        sourceUnits: result?.sourceUnits || null,
        notes: result?.notes || null,
      })
      setUploadStatus('completed')

      // Open sections that have data
      setExpandedSections({
        company: true,
        facility: true,
        income: ['revenue', 'ebit', 'depreciation', 'amortization', 'interestExpense', 'cashInterestPaid', 'cashTaxesPaid'].some(k => newAiValues[k] != null),
        balance: ['totalDebt', 'stDebt', 'cpltd', 'ltDebt', 'capitalLeases', 'cash', 'cashLikeAssets', 'totalEquity', 'minorityInterest', 'deferredTaxes', 'nwcCurrent', 'nwcPrior', 'totalAssetsCurrent', 'totalAssetsPrior'].some(k => newAiValues[k] != null),
        cashflow: ['cfo', 'capex', 'commonDividends', 'preferredDividends'].some(k => newAiValues[k] != null),
      })
    } catch (err) {
      setUploadStatus('error')
      setUploadError(err.message)
    }
  }

  // When external extractedData arrives (from other pages), pre-fill too
  useEffect(() => {
    if (extractedData && extractedData.fields) {
      const fields = extractedData.fields
      const confidence = extractedData.confidence || {}
      const newFormData = { ...EMPTY_FORM }
      const newAiValues = {}
      const newAiConfidence = {}

      for (const [backendKey, value] of Object.entries(fields)) {
        const formKey = EXTRACTION_TO_FORM[backendKey]
        if (formKey && value != null && value !== 0) {
          newFormData[formKey] = String(value)
          newAiValues[formKey] = value
          newAiConfidence[formKey] = confidence[backendKey] || null
        }
      }

      if (extractedData.fileName) {
        const name = extractedData.fileName
          .replace(/\.pdf$/i, '')
          .replace(/[_-]/g, ' ')
          .replace(/\d{4}$/g, '')
          .trim()
        if (name) newFormData.companyName = name
      }

      if (extractedData.sectorClassification?.reasoning) {
        newFormData.businessDescription = extractedData.sectorClassification.reasoning
      } else if (extractedData.businessDescription) {
        newFormData.businessDescription = extractedData.businessDescription
      }

      if (extractedData.sectorClassification) {
        const match = INDUSTRIES.find(i => i.value === extractedData.sectorClassification.sp_sector)
        if (match) newFormData.industry = extractedData.sectorClassification.sp_sector
      }

      setFormData(newFormData)
      setAiValues(newAiValues)
      setAiConfidence(newAiConfidence)
      setExtractionSource({
        fileName: extractedData.fileName,
        method: extractedData.method,
        fieldCount: Object.keys(newAiValues).length,
        sectorClassification: extractedData.sectorClassification || null,
      })
      setUploadStatus('completed')
      setUploadFileName(extractedData.fileName)

      setExpandedSections({
        company: true,
        facility: true,
        income: ['revenue', 'ebit', 'depreciation', 'amortization', 'interestExpense'].some(k => newAiValues[k] != null),
        balance: ['totalDebt', 'cash', 'totalEquity'].some(k => newAiValues[k] != null),
        cashflow: ['cfo', 'capex'].some(k => newAiValues[k] != null),
      })
    }
  }, [extractedData])

  const toggleSection = (section) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }))
  }

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({ ...prev, [name]: value }))
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
    setAiValues({})
    setAiConfidence({})
    setExtractionSource(null)
    setUploadStatus(null)
    setUploadFileName(null)
    setUploadError(null)
    if (onClearExtracted) onClearExtracted()
  }

  // Render a financial input row with AI value + override
  const renderFinancialRow = (label, name) => {
    const hasAi = aiValues[name] != null
    const aiVal = aiValues[name]
    const conf = aiConfidence[name]
    const currentVal = formData[name]
    const isOverridden = hasAi && currentVal !== '' && currentVal !== String(aiVal)

    return (
      <tr key={name} className="border-t border-gray-100">
        <td className="py-1.5 pr-2 text-sm text-gray-700 whitespace-nowrap">{label}</td>
        <td className="py-1.5 px-2 text-right text-sm font-mono text-gray-400 whitespace-nowrap">
          {hasAi ? (
            <span className="flex items-center justify-end gap-1.5">
              <span className={isOverridden ? 'line-through' : 'text-gray-700'}>
                {typeof aiVal === 'number' ? aiVal.toLocaleString('en-NZ', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : aiVal}
              </span>
              <ConfidenceBadge score={conf} />
            </span>
          ) : (
            <span className="text-gray-300">—</span>
          )}
        </td>
        <td className="py-1.5 pl-2">
          <input
            type="text"
            name={name}
            value={formData[name]}
            onChange={handleChange}
            placeholder={hasAi ? '' : '0'}
            className={`w-full px-2 py-1 text-sm text-right font-mono border rounded focus:ring-1 focus:ring-blue-400 focus:border-blue-400 outline-none ${
              isOverridden
                ? 'border-amber-400 bg-amber-50'
                : hasAi
                ? 'border-blue-200 bg-blue-50/50'
                : 'border-gray-200'
            }`}
          />
        </td>
      </tr>
    )
  }

  const renderSection = (title, sectionKey, children) => (
    <div className="border border-gray-200 rounded-lg mb-3 overflow-hidden bg-white">
      <button
        onClick={() => toggleSection(sectionKey)}
        className="w-full flex items-center px-4 py-2.5 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
        type="button"
      >
        <span className={`text-xs mr-2 transition-transform ${expandedSections[sectionKey] ? 'rotate-0' : '-rotate-90'}`}>
          ▼
        </span>
        <h3 className="text-sm font-semibold text-gray-800 flex-1">{title}</h3>
      </button>
      {expandedSections[sectionKey] && (
        <div className="px-4 py-3">{children}</div>
      )}
    </div>
  )

  const renderFinancialTable = (fields) => (
    <table className="w-full">
      <thead>
        <tr className="text-xs text-gray-500 border-b border-gray-200">
          <th className="text-left py-1 pr-2 font-medium">Field</th>
          <th className="text-right py-1 px-2 font-medium">AI Extracted</th>
          <th className="text-right py-1 pl-2 font-medium">Your Value (000s)</th>
        </tr>
      </thead>
      <tbody>
        {fields.map(([name, label]) => renderFinancialRow(label, name))}
      </tbody>
    </table>
  )

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      {/* Header row: title + upload */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Credit Analysis</h1>
          <p className="text-sm text-gray-500 mt-0.5">Upload a PDF or enter financials manually. All values in NZD thousands.</p>
        </div>
      </div>

      {/* PDF Upload Zone - compact inline */}
      <div
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={() => uploadStatus !== 'extracting' && fileInputRef.current?.click()}
        className={`mb-4 p-4 rounded-lg cursor-pointer transition-all border-2 ${
          isDragging
            ? 'border-blue-500 bg-blue-50'
            : uploadStatus === 'completed'
            ? 'border-green-300 bg-green-50'
            : uploadStatus === 'error'
            ? 'border-red-300 bg-red-50'
            : uploadStatus === 'extracting'
            ? 'border-blue-300 bg-blue-50'
            : 'border-dashed border-gray-300 hover:border-blue-400 hover:bg-gray-50'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          onChange={handleFileSelect}
          className="hidden"
        />

        <div className="flex items-center gap-4">
          {/* Icon */}
          <div className="flex-shrink-0">
            {uploadStatus === 'extracting' ? (
              <div className="w-10 h-10 flex items-center justify-center">
                <div className="animate-spin h-6 w-6 border-2 border-blue-500 border-t-transparent rounded-full" />
              </div>
            ) : uploadStatus === 'completed' ? (
              <svg className="w-10 h-10 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
            ) : uploadStatus === 'error' ? (
              <svg className="w-10 h-10 text-red-400" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            ) : (
              <svg className="w-10 h-10 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
            )}
          </div>

          {/* Status text */}
          <div className="flex-1 min-w-0">
            {uploadStatus === 'extracting' ? (
              <>
                <p className="text-sm font-medium text-blue-800">Extracting financials from {uploadFileName}...</p>
                <p className="text-xs text-blue-600">AI is reading the document — this may take 30-60 seconds</p>
              </>
            ) : uploadStatus === 'completed' ? (
              <>
                <p className="text-sm font-medium text-green-800">
                  {extractionSource?.fieldCount || 0} fields extracted from {uploadFileName}
                </p>
                <p className="text-xs text-green-600">
                  Values populated below. Override any incorrect values in the right column.
                  <button
                    onClick={(e) => { e.stopPropagation(); handleClearForm() }}
                    className="ml-2 underline hover:text-green-800"
                  >
                    Clear & start over
                  </button>
                </p>
              </>
            ) : uploadStatus === 'error' ? (
              <>
                <p className="text-sm font-medium text-red-700">Extraction failed: {uploadError}</p>
                <p className="text-xs text-red-500">Click to try another file</p>
              </>
            ) : (
              <>
                <p className="text-sm font-medium text-gray-700">
                  {isDragging ? 'Drop PDF here' : 'Drop a PDF here or click to upload'}
                </p>
                <p className="text-xs text-gray-500">Financial statements, annual reports, audit documents</p>
              </>
            )}
          </div>

          {/* Upload button */}
          {!uploadStatus && (
            <div className="flex-shrink-0 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700">
              Select PDF
            </div>
          )}
          {uploadStatus === 'completed' && (
            <div
              onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click() }}
              className="flex-shrink-0 px-3 py-1.5 bg-gray-200 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-300"
            >
              Upload New
            </div>
          )}
        </div>

        {/* Progress bar for extracting */}
        {uploadStatus === 'extracting' && (
          <div className="mt-3 w-full bg-blue-200 rounded-full h-1.5">
            <div className="h-1.5 rounded-full bg-blue-500 animate-pulse" style={{ width: '66%' }} />
          </div>
        )}
      </div>

      {/* Main form */}
      <form onSubmit={handleSubmit}>
        {/* Company Information */}
        {renderSection('Company Information', 'company', (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Company Name</label>
              <input
                type="text"
                name="companyName"
                value={formData.companyName}
                onChange={handleChange}
                placeholder="e.g., ABC Manufacturing Ltd"
                className="input-field w-full text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Industry
                {extractionSource?.sectorClassification && (
                  <span className="ml-1 text-green-600 font-normal">
                    (AI • {Math.round((extractionSource.sectorClassification.confidence || 0) * 100)}%)
                  </span>
                )}
              </label>
              <select
                name="industry"
                value={formData.industry}
                onChange={handleChange}
                className={`input-field w-full text-sm ${extractionSource?.sectorClassification ? 'border-blue-200 bg-blue-50/50' : ''}`}
              >
                {INDUSTRIES.map(ind => (
                  <option key={ind.value} value={ind.value}>{ind.label}</option>
                ))}
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Business Description
                {formData.businessDescription && extractionSource?.sectorClassification && (
                  <span className="ml-1 text-blue-600 font-normal">(AI-generated)</span>
                )}
              </label>
              <textarea
                name="businessDescription"
                value={formData.businessDescription}
                onChange={handleChange}
                placeholder="Describes operations — used for industry classification"
                rows="2"
                className={`input-field w-full text-sm ${
                  formData.businessDescription && extractionSource?.sectorClassification ? 'border-blue-200 bg-blue-50/50' : ''
                }`}
              />
            </div>
          </div>
        ))}

        {/* Facility Details - right after company info */}
        {renderSection('Facility Details', 'facility', (
          <div className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Bank</label>
                <select
                  value={formData.selectedBank}
                  onChange={handleBankChange}
                  className="input-field w-full text-sm"
                  disabled={productsLoading}
                >
                  <option value="">{productsLoading ? 'Loading...' : 'Select a bank'}</option>
                  {availableBanks.map(bank => (
                    <option key={bank} value={bank}>{bank}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Lending Product</label>
                <select
                  value={formData.selectedProduct}
                  onChange={handleProductChange}
                  className="input-field w-full text-sm"
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

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Margin (%)</label>
                <input
                  type="text"
                  name="currentMargin"
                  value={formData.currentMargin}
                  onChange={handleChange}
                  placeholder="e.g., 2.5"
                  className="input-field w-full text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Tenor (Years)</label>
                <select name="tenor" value={formData.tenor} onChange={handleChange} className="input-field w-full text-sm">
                  {[1, 2, 3, 4, 5, 7, 10].map(y => (
                    <option key={y} value={y}>{y} year{y > 1 ? 's' : ''}</option>
                  ))}
                </select>
              </div>
              {formData.selectedBaseRate != null && margin > 0 && (
                <div className="flex items-end">
                  <div className="w-full px-3 py-1.5 bg-green-50 border border-green-200 rounded text-center">
                    <p className="text-xs text-gray-500">All-In Rate</p>
                    <p className="text-lg font-bold text-green-700">
                      {baseRate.toFixed(2)}% + {margin.toFixed(2)}% = {allInRate.toFixed(2)}%
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Financial Statements - condensed with AI + override columns */}
        {renderSection('Income Statement (NZD 000s)', 'income',
          renderFinancialTable([
            ['revenue', 'Revenue'],
            ['ebit', 'EBIT / Operating Income'],
            ['depreciation', 'Depreciation'],
            ['amortization', 'Amortization'],
            ['interestExpense', 'Interest Expense'],
            ['cashInterestPaid', 'Cash Interest Paid'],
            ['cashTaxesPaid', 'Cash Taxes Paid'],
          ])
        )}

        {renderSection('Balance Sheet (NZD 000s)', 'balance', (
          <div>
            {renderFinancialTable([
              ['totalDebt', 'Total Debt'],
              ['stDebt', 'ST Debt'],
              ['cpltd', 'CPLTD'],
              ['ltDebt', 'LT Debt'],
              ['capitalLeases', 'Capital Leases'],
              ['cash', 'Cash & Equivalents'],
              ['cashLikeAssets', 'Cash-like Assets'],
              ['totalEquity', 'Total Equity'],
              ['minorityInterest', 'Minority Interest'],
              ['deferredTaxes', 'Deferred Taxes'],
            ])}
            <div className="mt-2 pt-2 border-t border-gray-200">
              <p className="text-xs font-medium text-gray-500 mb-1">Working Capital & Assets</p>
              {renderFinancialTable([
                ['nwcCurrent', 'NWC (Current)'],
                ['nwcPrior', 'NWC (Prior)'],
                ['ltOperatingAssetsCurrent', 'LT Op Assets (Curr)'],
                ['ltOperatingAssetsPrior', 'LT Op Assets (Prior)'],
                ['totalAssetsCurrent', 'Total Assets (Curr)'],
                ['totalAssetsPrior', 'Total Assets (Prior)'],
                ['avgCapital', 'Average Capital'],
              ])}
            </div>
          </div>
        ))}

        {renderSection('Cash Flow (NZD 000s)', 'cashflow',
          renderFinancialTable([
            ['cfo', 'Operating Cash Flow'],
            ['capex', 'Capital Expenditures'],
            ['commonDividends', 'Common Dividends'],
            ['preferredDividends', 'Preferred Dividends'],
            ['minorityDividends', 'Minority Dividends'],
            ['sharebuybacks', 'Share Buybacks'],
          ])
        )}

        {/* Submit row */}
        <div className="flex gap-3 mt-4">
          <button
            type="submit"
            disabled={loading}
            className={`btn-primary flex-1 py-2.5 text-base font-semibold ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {loading ? 'Analyzing...' : 'Calculate Credit Spread'}
          </button>
          <button type="button" className="btn-secondary px-6 py-2.5" onClick={handleClearForm}>
            Clear
          </button>
        </div>
      </form>
    </div>
  )
}

export default AnalysisForm
