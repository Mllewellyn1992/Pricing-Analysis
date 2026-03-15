import { useState, useEffect, useRef } from 'react'
import { analyzeFinancials, getAllProducts, uploadPDF, pingServer, saveExtraction, listExtractions, loadExtraction, deleteExtraction } from '../api'

const EXTRACTION_TO_FORM = {
  revenue_mn: 'revenue', operating_expenses_mn: 'operatingExpenses',
  ebit_mn: 'ebit', ebitda_mn: 'ebitda', impairment_mn: 'impairment',
  depreciation_mn: 'depreciation',
  depreciation_ppe_mn: 'depreciationPpe', depreciation_rou_mn: 'depreciationRou',
  amortization_mn: 'amortization', interest_expense_mn: 'interestExpense',
  interest_debt_mn: 'interestDebt', interest_lease_mn: 'interestLease',
  cash_interest_paid_mn: 'cashInterestPaid', cash_taxes_paid_mn: 'cashTaxesPaid',
  total_debt_mn: 'totalDebt', st_debt_mn: 'stDebt', cpltd_mn: 'cpltd',
  lt_debt_net_mn: 'ltDebt',
  lease_liabilities_mn: 'leaseTotal', lease_liabilities_current_mn: 'leaseCurrent',
  lease_liabilities_noncurrent_mn: 'leaseNoncurrent', rou_assets_mn: 'rouAssets',
  cash_mn: 'cash', cash_like_mn: 'cashLikeAssets', total_equity_mn: 'totalEquity',
  minority_interest_mn: 'minorityInterest', deferred_taxes_mn: 'deferredTaxes',
  cfo_mn: 'cfo', capex_mn: 'capex', lease_principal_payments_mn: 'leasePrincipal',
  common_dividends_mn: 'commonDividends',
  preferred_dividends_mn: 'preferredDividends', nwc_current_mn: 'nwcCurrent',
  nwc_prior_mn: 'nwcPrior', lt_operating_assets_current_mn: 'ltOperatingAssetsCurrent',
  lt_operating_assets_prior_mn: 'ltOperatingAssetsPrior',
  assets_current_mn: 'totalAssetsCurrent', assets_prior_mn: 'totalAssetsPrior',
  avg_capital_mn: 'avgCapital',
}

const INDUSTRIES = [
  { label: 'Select industry...', value: '' },
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
  { label: 'Consumer Staples', value: 'consumer_staples_and_branded_nondurables' },
  { label: 'Containers & Packaging', value: 'containers_and_packaging' },
  { label: 'Contract Drilling', value: 'contract_drilling' },
  { label: 'Engineering & Construction', value: 'engineering_and_construction' },
  { label: 'Environmental Services', value: 'environmental_services' },
  { label: 'Financial Market Infra', value: 'financial_market_infrastructure' },
  { label: 'Financial Services', value: 'financial_services_finance_companies' },
  { label: 'Forest & Paper', value: 'forest_and_paper_products' },
  { label: 'Health Care Equipment', value: 'health_care_equipment' },
  { label: 'Health Care Services', value: 'health_care_services' },
  { label: 'Homebuilders & RE Dev', value: 'homebuilders_and_real_estate_developers' },
  { label: 'Leisure & Sports', value: 'leisure_and_sports' },
  { label: 'Media & Entertainment', value: 'media_and_entertainment' },
  { label: 'Metals & Processing', value: 'metals_production_and_processing' },
  { label: 'Midstream Energy', value: 'midstream_energy' },
  { label: 'Mining', value: 'mining' },
  { label: 'Oil & Gas E&P', value: 'oil_and_gas_exploration_and_production' },
  { label: 'Oilfield Services', value: 'oilfield_services_and_equipment' },
  { label: 'Pharmaceuticals', value: 'pharmaceuticals' },
  { label: 'Railroad & Logistics', value: 'railroad_package_express_and_logistics' },
  { label: 'Refining & Marketing', value: 'refining_and_marketing' },
  { label: 'Regulated Utilities', value: 'regulated_utilities' },
  { label: 'Retail & Restaurants', value: 'retail_and_restaurants' },
  { label: 'Tech Hardware & Semi', value: 'technology_hardware_and_semiconductors' },
  { label: 'Tech Software & Services', value: 'technology_software_and_services' },
  { label: 'Telecommunications', value: 'telecommunications' },
  { label: 'Transportation (Cyclical)', value: 'transportation_cyclical' },
  { label: 'Transport Infrastructure', value: 'transportation_infrastructure' },
  { label: 'Unregulated Power & Gas', value: 'unregulated_power_and_gas' },
]

const EMPTY_FORM = {
  companyName: '', businessDescription: '', industry: '',
  revenue: '', operatingExpenses: '', ebit: '', ebitda: '', impairment: '',
  depreciation: '', depreciationPpe: '', depreciationRou: '',
  amortization: '',
  interestExpense: '', interestDebt: '', interestLease: '',
  cashInterestPaid: '', cashTaxesPaid: '',
  totalDebt: '', stDebt: '', cpltd: '', ltDebt: '',
  leaseTotal: '', leaseCurrent: '', leaseNoncurrent: '', rouAssets: '',
  capitalLeases: '',
  cash: '', cashLikeAssets: '', totalEquity: '', minorityInterest: '',
  deferredTaxes: '', nwcCurrent: '', nwcPrior: '',
  ltOperatingAssetsCurrent: '', ltOperatingAssetsPrior: '',
  totalAssetsCurrent: '', totalAssetsPrior: '',
  cfo: '', capex: '', leasePrincipal: '', commonDividends: '', preferredDividends: '',
  minorityDividends: '', sharebuybacks: '', avgCapital: '',
  currentMargin: '', tenor: '3', selectedBank: '', selectedProduct: '', selectedBaseRate: null,
}

function Badge({ score }) {
  if (score == null) return null
  const pct = Math.round(score * 100)
  const c = pct >= 90 ? 'text-emerald-600' : pct >= 75 ? 'text-blue-600' : pct >= 60 ? 'text-amber-600' : 'text-red-500'
  return <span className={`text-[10px] font-medium ${c}`}>{pct}%</span>
}

function AnalysisForm({ onResults, extractedData, onClearExtracted }) {
  const [loading, setLoading] = useState(false)
  const [sections, setSections] = useState({ company: true, facility: true, income: true, balance: true, cashflow: true })
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [ai, setAi] = useState({})
  const [aiConf, setAiConf] = useState({})
  const [source, setSource] = useState(null)
  const [banks, setBanks] = useState([])
  const [banksLoading, setBanksLoading] = useState(true)
  const [uploadStatus, setUploadStatus] = useState(null)
  const [uploadError, setUploadError] = useState(null)
  const [uploadFile, setUploadFile] = useState(null)
  const [isDrag, setIsDrag] = useState(false)
  const [extractionWarnings, setExtractionWarnings] = useState([])
  const [isInterim, setIsInterim] = useState(false)
  const [savedExtractions, setSavedExtractions] = useState([])
  const [saveName, setSaveName] = useState('')
  const [showSaveDialog, setShowSaveDialog] = useState(false)
  const [saveStatus, setSaveStatus] = useState(null) // null, 'saving', 'saved', 'error'
  const [showHistory, setShowHistory] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [lastExtraction, setLastExtraction] = useState(null) // raw extraction result for saving
  const fileRef = useRef(null)

  useEffect(() => {
    getAllProducts().then(p => setBanks(p)).catch(() => {}).finally(() => setBanksLoading(false))
    // Load saved extractions list on mount
    listExtractions().then(setSavedExtractions).catch(() => {})
  }, [])

  const bankList = [...new Set(banks.map(p => p.bank))].sort()
  const products = form.selectedBank ? banks.filter(p => p.bank === form.selectedBank) : []
  const margin = parseFloat(form.currentMargin) || 0
  const base = form.selectedBaseRate || 0
  const allIn = base + margin

  const set = (name, value) => setForm(p => ({ ...p, [name]: value }))

  const applyExtraction = (result, fileName) => {
    const fields = result?.data || result?.fields || {}
    const conf = result?.confidenceScores || result?.confidence || {}
    const f = { ...EMPTY_FORM }
    const av = {}; const ac = {}

    for (const [bk, v] of Object.entries(fields)) {
      const fk = EXTRACTION_TO_FORM[bk]
      if (fk && v != null && v !== 0) { f[fk] = String(v); av[fk] = v; ac[fk] = conf[bk] || null }
    }

    if (fileName) {
      f.companyName = fileName.replace(/\.pdf$/i, '').replace(/[_-]/g, ' ').replace(/\d{4}$/g, '').trim()
    }

    const sc = result?.sectorClassification
    if (sc?.reasoning) f.businessDescription = sc.reasoning
    else if (result?.businessDescription) f.businessDescription = result.businessDescription
    if (sc) { const m = INDUSTRIES.find(i => i.value === sc.sp_sector); if (m) f.industry = sc.sp_sector }

    // Detect interim accounts
    const period = (fields.fiscal_period || '').toLowerCase()
    const interimKeywords = ['interim', 'half', 'h1', 'h2', '6 month', '6-month', 'six month', 'quarter', 'q1', 'q2', 'q3', 'q4', '3 month', '9 month']
    setIsInterim(interimKeywords.some(kw => period.includes(kw)) || (fileName || '').toLowerCase().includes('interim'))

    setForm(f); setAi(av); setAiConf(ac)
    setSource({ fileName, method: result?.extractionMethod || result?.method || 'ai', count: Object.keys(av).length, sc })
    setSections({
      company: true, facility: true,
      income: ['revenue','ebit','depreciation','amortization','interestExpense','cashInterestPaid','cashTaxesPaid'].some(k => av[k] != null),
      balance: ['totalDebt','cash','totalEquity','stDebt','ltDebt'].some(k => av[k] != null),
      cashflow: ['cfo','capex','commonDividends'].some(k => av[k] != null),
    })
  }

  const handleSave = async () => {
    if (!saveName.trim() || !lastExtraction) return
    setSaveStatus('saving')
    try {
      await saveExtraction({
        name: saveName.trim(),
        filename: uploadFile || null,
        extracted_fields: lastExtraction.data || lastExtraction.fields || {},
        confidence_scores: lastExtraction.confidenceScores || lastExtraction.confidence || {},
        extraction_method: lastExtraction.extractionMethod || lastExtraction.method || 'ai',
        sector_classification: lastExtraction.sectorClassification || null,
        business_description: lastExtraction.businessDescription || form.businessDescription || null,
        warnings: lastExtraction.warnings || [],
        fiscal_period: (lastExtraction.data || lastExtraction.fields || {}).fiscal_period || null,
      })
      setSaveStatus('saved')
      setShowSaveDialog(false)
      setSaveName('')
      // Refresh the list
      listExtractions().then(setSavedExtractions).catch(() => {})
    } catch (e) {
      setSaveStatus('error')
    }
  }

  const handleLoad = async (id) => {
    setHistoryLoading(true)
    try {
      const ext = await loadExtraction(id)
      if (ext) {
        const result = {
          data: ext.extracted_fields,
          confidenceScores: ext.confidence_scores,
          extractionMethod: ext.extraction_method,
          sectorClassification: ext.sector_classification,
          businessDescription: ext.business_description,
          warnings: ext.warnings || [],
        }
        applyExtraction(result, ext.filename)
        setLastExtraction(result)
        setExtractionWarnings(ext.warnings || [])
        setUploadStatus('done')
        setUploadFile(ext.filename)
        setShowHistory(false)
      }
    } catch (e) {
      console.error('Error loading extraction:', e)
    } finally {
      setHistoryLoading(false)
    }
  }

  const handleDelete = async (id, e) => {
    e.stopPropagation()
    if (!confirm('Delete this saved extraction?')) return
    try {
      await deleteExtraction(id)
      setSavedExtractions(prev => prev.filter(x => x.id !== id))
    } catch (err) {
      console.error('Error deleting extraction:', err)
    }
  }

  const handleUpload = async (file) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) { setUploadError('PDF files only'); return }
    setUploadError(null); setUploadStatus('warming_up'); setUploadFile(file.name)
    try {
      // Ping server first to wake it up (Render cold start)
      const alive = await pingServer()
      if (!alive) {
        // Server is cold — wait a bit and ping again
        await new Promise(r => setTimeout(r, 3000))
        await pingServer()
      }
      setUploadStatus('extracting')
      const result = await uploadPDF(file, (status) => setUploadStatus(status))
      applyExtraction(result, file.name)
      setLastExtraction(result)
      setExtractionWarnings(result.warnings || [])
      setUploadStatus('done')
      setSaveStatus(null)
    } catch (e) { setUploadStatus('error'); setUploadError(e.message) }
  }

  useEffect(() => {
    if (extractedData?.fields) {
      applyExtraction(extractedData, extractedData.fileName)
      setLastExtraction(extractedData)
      setUploadStatus('done'); setUploadFile(extractedData.fileName)
      setSaveStatus(null)
    }
  }, [extractedData])

  const clear = () => {
    setForm({ ...EMPTY_FORM }); setAi({}); setAiConf({}); setSource(null)
    setUploadStatus(null); setUploadFile(null); setUploadError(null); setExtractionWarnings([])
    setIsInterim(false); setLastExtraction(null); setSaveStatus(null); setShowSaveDialog(false)
    onClearExtracted?.()
  }

  const submit = async (e) => {
    e.preventDefault(); setLoading(true)
    try { onResults(await analyzeFinancials(form)) }
    catch (err) { alert('Error: ' + err.message) }
    finally { setLoading(false) }
  }

  // --- Render helpers ---
  const Row = ({ label, name }) => {
    const has = ai[name] != null
    const val = ai[name]
    const over = has && form[name] !== '' && form[name] !== String(val)
    return (
      <tr className="border-t border-slate-100 hover:bg-slate-50/50">
        <td className="py-1 pr-2 text-slate-600 whitespace-nowrap">{label}</td>
        <td className="py-1 px-2 text-right font-mono text-slate-400 whitespace-nowrap">
          {has ? (
            <span className="inline-flex items-center gap-1">
              <span className={over ? 'line-through text-slate-300' : 'text-slate-700'}>{typeof val === 'number' ? val.toLocaleString('en-NZ', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : val}</span>
              <Badge score={aiConf[name]} />
            </span>
          ) : <span className="text-slate-300">—</span>}
        </td>
        <td className="py-1 pl-2">
          <input
            type="text" name={name} value={form[name]} onChange={e => set(name, e.target.value)}
            placeholder={has ? '' : '—'}
            className={`w-full px-1.5 py-0.5 text-right font-mono border rounded transition-colors focus:ring-1 focus:ring-blue-400 focus:border-blue-400 outline-none ${
              over ? 'border-amber-400 bg-amber-50' : has ? 'border-blue-200 bg-blue-50/40' : 'border-slate-200 bg-white'
            }`}
          />
        </td>
      </tr>
    )
  }

  const Section = ({ title, id, children }) => (
    <div className="border border-slate-200 rounded-md mb-2 bg-white overflow-hidden">
      <button onClick={() => setSections(p => ({ ...p, [id]: !p[id] }))} type="button"
        className="w-full flex items-center px-3 py-1.5 bg-slate-50 hover:bg-slate-100 transition-colors text-left">
        <svg className={`w-3 h-3 mr-1.5 text-slate-400 transition-transform ${sections[id] ? '' : '-rotate-90'}`} fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
        </svg>
        <span className="text-xs font-semibold text-slate-700 flex-1">{title}</span>
      </button>
      {sections[id] && <div className="px-3 py-2">{children}</div>}
    </div>
  )

  const Table = ({ rows }) => (
    <table className="w-full text-xs">
      <thead>
        <tr className="text-[10px] text-slate-400 border-b border-slate-200 uppercase tracking-wider">
          <th className="text-left py-0.5 pr-2 font-medium">Field</th>
          <th className="text-right py-0.5 px-2 font-medium">AI Value</th>
          <th className="text-right py-0.5 pl-2 font-medium" style={{width:'120px'}}>Override (000s)</th>
        </tr>
      </thead>
      <tbody>{rows.map(([n, l]) => <Row key={n} name={n} label={l} />)}</tbody>
    </table>
  )

  return (
    <div className="p-3 md:p-4 max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-3">
        <h1 className="text-lg font-bold text-slate-900">Credit Analysis</h1>
        <p className="text-[11px] text-slate-400">Upload a PDF or enter financials manually. All values in NZD thousands.</p>
      </div>

      {/* Upload zone */}
      <div
        onDragEnter={e => { e.preventDefault(); setIsDrag(true) }}
        onDragLeave={e => { e.preventDefault(); setIsDrag(false) }}
        onDragOver={e => e.preventDefault()}
        onDrop={e => { e.preventDefault(); setIsDrag(false); e.dataTransfer.files[0] && handleUpload(e.dataTransfer.files[0]) }}
        onClick={() => !['extracting','warming_up','retrying'].includes(uploadStatus) && fileRef.current?.click()}
        className={`mb-3 px-3 py-2.5 rounded-md cursor-pointer transition-all border ${
          isDrag ? 'border-blue-400 bg-blue-50'
          : uploadStatus === 'done' ? 'border-emerald-300 bg-emerald-50/60'
          : uploadStatus === 'error' ? 'border-red-300 bg-red-50/60'
          : ['extracting','warming_up','retrying'].includes(uploadStatus) ? 'border-blue-300 bg-blue-50/60'
          : 'border-dashed border-slate-300 hover:border-blue-300 hover:bg-slate-50'
        }`}
      >
        <input ref={fileRef} type="file" accept=".pdf" onChange={e => e.target.files[0] && handleUpload(e.target.files[0])} className="hidden" />
        <div className="flex items-center gap-3">
          <div className="flex-shrink-0">
            {['extracting','warming_up','retrying'].includes(uploadStatus) ? (
              <div className="animate-spin h-5 w-5 border-2 border-blue-500 border-t-transparent rounded-full" />
            ) : uploadStatus === 'done' ? (
              <svg className="w-5 h-5 text-emerald-500" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" /></svg>
            ) : uploadStatus === 'error' ? (
              <svg className="w-5 h-5 text-red-400" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" /></svg>
            ) : (
              <svg className="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" /></svg>
            )}
          </div>
          <div className="flex-1 min-w-0">
            {uploadStatus === 'warming_up' ? (
              <p className="text-xs text-blue-700">Connecting to server<span className="animate-pulse">...</span></p>
            ) : uploadStatus === 'retrying' ? (
              <p className="text-xs text-amber-700">Server was slow — retrying extraction<span className="animate-pulse">...</span></p>
            ) : uploadStatus === 'extracting' ? (
              <p className="text-xs text-blue-700">Extracting from <span className="font-medium">{uploadFile}</span> — 30-60 seconds...</p>
            ) : uploadStatus === 'done' ? (
              <p className="text-xs text-emerald-700">
                <span className="font-medium">{source?.count || 0} fields</span> extracted from {uploadFile}
                <button onClick={e => { e.stopPropagation(); clear() }} className="ml-2 text-emerald-600 underline hover:text-emerald-800">Clear</button>
              </p>
            ) : uploadStatus === 'error' ? (
              <p className="text-xs text-red-600">{uploadError} <span className="text-red-400">— click to retry</span></p>
            ) : (
              <p className="text-xs text-slate-500">{isDrag ? 'Drop PDF here' : 'Drop PDF here or click to upload'}</p>
            )}
          </div>
          {!uploadStatus && (
            <div className="flex-shrink-0 px-3 py-1 bg-blue-500 text-white text-xs font-medium rounded hover:bg-blue-600 transition-colors">
              Upload
            </div>
          )}
          {uploadStatus === 'done' && (
            <div onClick={e => { e.stopPropagation(); fileRef.current?.click() }}
              className="flex-shrink-0 px-2.5 py-1 bg-slate-200 text-slate-600 text-xs font-medium rounded hover:bg-slate-300 transition-colors">
              New File
            </div>
          )}
        </div>
        {['extracting','warming_up','retrying'].includes(uploadStatus) && (
          <div className="mt-2 w-full bg-blue-200 rounded-full h-1">
            <div className={`h-1 rounded-full animate-pulse ${uploadStatus === 'retrying' ? 'bg-amber-500' : 'bg-blue-500'}`}
              style={{ width: uploadStatus === 'warming_up' ? '20%' : uploadStatus === 'retrying' ? '40%' : '66%' }} />
          </div>
        )}
      </div>

      {/* Extraction warnings */}
      {extractionWarnings.length > 0 && uploadStatus === 'done' && (
        <div className="mb-2 px-3 py-2 rounded-md border border-amber-200 bg-amber-50/60">
          <p className="text-[10px] font-semibold text-amber-700 mb-0.5">Extraction notes:</p>
          {extractionWarnings.map((w, i) => (
            <p key={i} className="text-[10px] text-amber-600">• {w}</p>
          ))}
        </div>
      )}

      {/* Interim accounts warning */}
      {isInterim && uploadStatus === 'done' && (
        <div className="mb-2 px-3 py-2 rounded-md border border-orange-300 bg-orange-50/80">
          <div className="flex items-start gap-2">
            <svg className="w-4 h-4 text-orange-500 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            <div>
              <p className="text-xs font-semibold text-orange-700">Interim accounts detected</p>
              <p className="text-[10px] text-orange-600 mt-0.5">
                Income statement and cash flow figures cover a partial year. Credit ratios (Debt/EBITDA, FFO/Debt, etc.)
                will not reflect full-year performance. Consider this when interpreting the results.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Save & Load Extractions */}
      <div className="flex items-center gap-2 mb-2">
        {/* Save button — only show when there's an extraction */}
        {uploadStatus === 'done' && lastExtraction && (
          <>
            {showSaveDialog ? (
              <div className="flex items-center gap-1.5 flex-1">
                <input
                  type="text" value={saveName} onChange={e => setSaveName(e.target.value)}
                  placeholder="Name this extraction, e.g. Ryman H1 2025"
                  className="flex-1 px-2 py-1 text-xs border border-blue-300 rounded focus:ring-1 focus:ring-blue-400 outline-none"
                  autoFocus
                  onKeyDown={e => e.key === 'Enter' && handleSave()}
                />
                <button type="button" onClick={handleSave} disabled={!saveName.trim() || saveStatus === 'saving'}
                  className="px-2.5 py-1 text-xs font-medium bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 transition-colors">
                  {saveStatus === 'saving' ? 'Saving...' : 'Save'}
                </button>
                <button type="button" onClick={() => { setShowSaveDialog(false); setSaveName('') }}
                  className="px-2 py-1 text-xs text-slate-500 hover:text-slate-700">Cancel</button>
              </div>
            ) : (
              <button type="button" onClick={() => { setShowSaveDialog(true); setSaveStatus(null) }}
                className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-blue-600 bg-blue-50 border border-blue-200 rounded hover:bg-blue-100 transition-colors">
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" /></svg>
                {saveStatus === 'saved' ? 'Saved!' : 'Save Extraction'}
              </button>
            )}
          </>
        )}

        {/* History button — always show if there are saved extractions */}
        {savedExtractions.length > 0 && (
          <button type="button" onClick={() => setShowHistory(!showHistory)}
            className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded border transition-colors ${
              showHistory ? 'text-slate-700 bg-slate-200 border-slate-300' : 'text-slate-500 bg-white border-slate-200 hover:bg-slate-50'
            }`}>
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            History ({savedExtractions.length})
          </button>
        )}
      </div>

      {/* Saved extractions list */}
      {showHistory && (
        <div className="mb-3 border border-slate-200 rounded-md bg-white overflow-hidden">
          <div className="px-3 py-1.5 bg-slate-50 border-b border-slate-200">
            <span className="text-xs font-semibold text-slate-700">Saved Extractions</span>
          </div>
          <div className="max-h-48 overflow-y-auto divide-y divide-slate-100">
            {savedExtractions.map(ext => (
              <div key={ext.id} onClick={() => handleLoad(ext.id)}
                className="flex items-center gap-2 px-3 py-1.5 hover:bg-blue-50 cursor-pointer transition-colors group">
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-slate-700 truncate">{ext.name}</p>
                  <p className="text-[10px] text-slate-400 truncate">
                    {ext.filename && <span>{ext.filename} · </span>}
                    {new Date(ext.created_at).toLocaleDateString('en-NZ', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                  </p>
                </div>
                <span className="text-[9px] px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded">{ext.extraction_method || 'ai'}</span>
                <button onClick={(e) => handleDelete(ext.id, e)}
                  className="opacity-0 group-hover:opacity-100 p-0.5 text-slate-400 hover:text-red-500 transition-all">
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                </button>
              </div>
            ))}
            {historyLoading && (
              <div className="px-3 py-2 text-center">
                <span className="text-xs text-blue-500">Loading extraction...</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Form */}
      <form onSubmit={submit}>
        {/* Company */}
        <Section title="Company Information" id="company">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[10px] font-medium text-slate-500 mb-0.5">Company Name</label>
              <input type="text" value={form.companyName} onChange={e => set('companyName', e.target.value)}
                placeholder="ABC Manufacturing Ltd" className="input-field w-full" />
            </div>
            <div>
              <label className="block text-[10px] font-medium text-slate-500 mb-0.5">
                Industry{source?.sc && <span className="ml-1 text-emerald-500">(AI {Math.round((source.sc.confidence||0)*100)}%)</span>}
              </label>
              <select value={form.industry} onChange={e => set('industry', e.target.value)}
                className={`input-field w-full ${source?.sc ? 'border-blue-200 bg-blue-50/30' : ''}`}>
                {INDUSTRIES.map(i => <option key={i.value} value={i.value}>{i.label}</option>)}
              </select>
            </div>
            <div className="col-span-2">
              <label className="block text-[10px] font-medium text-slate-500 mb-0.5">
                Business Description{source?.sc && <span className="ml-1 text-blue-500">(AI)</span>}
              </label>
              <textarea value={form.businessDescription} onChange={e => set('businessDescription', e.target.value)}
                rows="1" placeholder="Operations description for industry classification"
                className={`input-field w-full resize-none ${source?.sc ? 'border-blue-200 bg-blue-50/30' : ''}`} />
            </div>
          </div>
        </Section>

        {/* Facility */}
        <Section title="Facility Details" id="facility">
          <div className="grid grid-cols-2 gap-2 mb-2">
            <div>
              <label className="block text-[10px] font-medium text-slate-500 mb-0.5">Bank</label>
              <select value={form.selectedBank} onChange={e => setForm(p => ({...p, selectedBank: e.target.value, selectedProduct: '', selectedBaseRate: null}))}
                className="input-field w-full" disabled={banksLoading}>
                <option value="">{banksLoading ? 'Loading...' : 'Select bank'}</option>
                {bankList.map(b => <option key={b} value={b}>{b}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-medium text-slate-500 mb-0.5">Lending Product</label>
              <select value={form.selectedProduct} onChange={e => {
                  const p = products.find(x => x.product_name === e.target.value)
                  setForm(prev => ({...prev, selectedProduct: e.target.value, selectedBaseRate: p ? p.rate_pct : null}))
                }} className="input-field w-full" disabled={!form.selectedBank}>
                <option value="">{form.selectedBank ? 'Select product' : 'Select bank first'}</option>
                {products.map(p => <option key={p.product_name} value={p.product_name}>{p.product_name} — {p.rate_pct.toFixed(2)}%</option>)}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="block text-[10px] font-medium text-slate-500 mb-0.5">Margin (%)</label>
              <input type="text" value={form.currentMargin} onChange={e => set('currentMargin', e.target.value)}
                placeholder="2.5" className="input-field w-full" />
            </div>
            <div>
              <label className="block text-[10px] font-medium text-slate-500 mb-0.5">Tenor</label>
              <select value={form.tenor} onChange={e => set('tenor', e.target.value)} className="input-field w-full">
                {[1,2,3,4,5,7,10].map(y => <option key={y} value={y}>{y}yr</option>)}
              </select>
            </div>
            {base > 0 && margin > 0 && (
              <div className="flex items-end">
                <div className="w-full px-2 py-1 bg-emerald-50 border border-emerald-200 rounded text-center">
                  <p className="text-[9px] text-slate-400 uppercase tracking-wide">All-In</p>
                  <p className="text-sm font-bold text-emerald-700">{allIn.toFixed(2)}%</p>
                </div>
              </div>
            )}
          </div>
        </Section>

        {/* Financials — side-by-side income + balance on wider screens */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
          <Section title="Income Statement (000s)" id="income">
            <Table rows={[
              ['revenue','Revenue'],['operatingExpenses','OpEx (ex D&A)'],
              ['ebit','EBIT (ex Impairment)'],['ebitda','EBITDA'],
              ['impairment','Impairment'],
              ['depreciation','Depreciation (Total)'],
              ['depreciationPpe','  ↳ PPE Only'],['depreciationRou','  ↳ ROU (Lease)'],
              ['amortization','Amortization'],
              ['interestExpense','Interest (Total)'],
              ['interestDebt','  ↳ Debt Only'],['interestLease','  ↳ Lease Only'],
              ['cashInterestPaid','Cash Int Paid'],['cashTaxesPaid','Cash Tax Paid'],
            ]} />
          </Section>

          <Section title="Cash Flow (000s)" id="cashflow">
            <Table rows={[
              ['cfo','Operating CF'],['capex','Capex'],
              ['leasePrincipal','Lease Payments'],
              ['commonDividends','Dividends'],
              ['preferredDividends','Pref Dividends'],['minorityDividends','Min Dividends'],
              ['sharebuybacks','Buybacks'],
            ]} />
          </Section>
        </div>

        <Section title="Balance Sheet (000s)" id="balance">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-4">
            <Table rows={[
              ['totalDebt','Borrowings (ex Lease)'],['stDebt','ST Debt'],['cpltd','CPLTD'],
              ['ltDebt','LT Debt'],
              ['leaseTotal','Lease Liabilities (Total)'],
              ['leaseCurrent','  ↳ Current'],['leaseNoncurrent','  ↳ Non-current'],
              ['rouAssets','ROU Assets'],
              ['cash','Cash'],['cashLikeAssets','Cash-like'],
              ['totalEquity','Equity'],['minorityInterest','Minority Int'],
              ['deferredTaxes','Deferred Tax'],
            ]} />
            <div>
              <p className="text-[10px] font-medium text-slate-400 uppercase tracking-wider mb-1 mt-1 lg:mt-0">Working Capital & Assets</p>
              <Table rows={[
                ['nwcCurrent','NWC (Curr)'],['nwcPrior','NWC (Prior)'],
                ['ltOperatingAssetsCurrent','LT Op Assets (Curr)'],['ltOperatingAssetsPrior','LT Op Assets (Prior)'],
                ['totalAssetsCurrent','Assets (Curr)'],['totalAssetsPrior','Assets (Prior)'],
                ['avgCapital','Avg Capital'],
              ]} />
            </div>
          </div>
        </Section>

        {/* Actions */}
        <div className="flex gap-2 mt-3">
          <button type="submit" disabled={loading}
            className={`btn-primary flex-1 py-2 font-semibold ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}>
            {loading ? 'Analyzing...' : 'Calculate Credit Spread'}
          </button>
          <button type="button" className="btn-secondary px-4 py-2" onClick={clear}>Clear</button>
        </div>
      </form>
    </div>
  )
}

export default AnalysisForm
