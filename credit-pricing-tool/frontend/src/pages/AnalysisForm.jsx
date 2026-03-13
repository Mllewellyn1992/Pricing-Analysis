import { useState, useEffect, useRef } from 'react'
import { analyzeFinancials, getAllProducts, uploadPDF } from '../api'

const EXTRACTION_TO_FORM = {
  revenue_mn: 'revenue', ebit_mn: 'ebit', depreciation_mn: 'depreciation',
  amortization_mn: 'amortization', interest_expense_mn: 'interestExpense',
  cash_interest_paid_mn: 'cashInterestPaid', cash_taxes_paid_mn: 'cashTaxesPaid',
  total_debt_mn: 'totalDebt', st_debt_mn: 'stDebt', cpltd_mn: 'cpltd',
  lt_debt_net_mn: 'ltDebt', capital_leases_mn: 'capitalLeases', cash_mn: 'cash',
  cash_like_mn: 'cashLikeAssets', total_equity_mn: 'totalEquity',
  minority_interest_mn: 'minorityInterest', deferred_taxes_mn: 'deferredTaxes',
  cfo_mn: 'cfo', capex_mn: 'capex', common_dividends_mn: 'commonDividends',
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
  revenue: '', ebit: '', depreciation: '', amortization: '',
  interestExpense: '', cashInterestPaid: '', cashTaxesPaid: '',
  totalDebt: '', stDebt: '', cpltd: '', ltDebt: '', capitalLeases: '',
  cash: '', cashLikeAssets: '', totalEquity: '', minorityInterest: '',
  deferredTaxes: '', nwcCurrent: '', nwcPrior: '',
  ltOperatingAssetsCurrent: '', ltOperatingAssetsPrior: '',
  totalAssetsCurrent: '', totalAssetsPrior: '',
  cfo: '', capex: '', commonDividends: '', preferredDividends: '',
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
  const fileRef = useRef(null)

  useEffect(() => {
    getAllProducts().then(p => setBanks(p)).catch(() => {}).finally(() => setBanksLoading(false))
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

    setForm(f); setAi(av); setAiConf(ac)
    setSource({ fileName, method: result?.extractionMethod || result?.method || 'ai', count: Object.keys(av).length, sc })
    setSections({
      company: true, facility: true,
      income: ['revenue','ebit','depreciation','amortization','interestExpense','cashInterestPaid','cashTaxesPaid'].some(k => av[k] != null),
      balance: ['totalDebt','cash','totalEquity','stDebt','ltDebt'].some(k => av[k] != null),
      cashflow: ['cfo','capex','commonDividends'].some(k => av[k] != null),
    })
  }

  const handleUpload = async (file) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) { setUploadError('PDF files only'); return }
    setUploadError(null); setUploadStatus('extracting'); setUploadFile(file.name)
    try {
      const result = await uploadPDF(file)
      applyExtraction(result, file.name)
      setUploadStatus('done')
    } catch (e) { setUploadStatus('error'); setUploadError(e.message) }
  }

  useEffect(() => {
    if (extractedData?.fields) {
      applyExtraction(extractedData, extractedData.fileName)
      setUploadStatus('done'); setUploadFile(extractedData.fileName)
    }
  }, [extractedData])

  const clear = () => {
    setForm({ ...EMPTY_FORM }); setAi({}); setAiConf({}); setSource(null)
    setUploadStatus(null); setUploadFile(null); setUploadError(null)
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
        onClick={() => uploadStatus !== 'extracting' && fileRef.current?.click()}
        className={`mb-3 px-3 py-2.5 rounded-md cursor-pointer transition-all border ${
          isDrag ? 'border-blue-400 bg-blue-50'
          : uploadStatus === 'done' ? 'border-emerald-300 bg-emerald-50/60'
          : uploadStatus === 'error' ? 'border-red-300 bg-red-50/60'
          : uploadStatus === 'extracting' ? 'border-blue-300 bg-blue-50/60'
          : 'border-dashed border-slate-300 hover:border-blue-300 hover:bg-slate-50'
        }`}
      >
        <input ref={fileRef} type="file" accept=".pdf" onChange={e => e.target.files[0] && handleUpload(e.target.files[0])} className="hidden" />
        <div className="flex items-center gap-3">
          <div className="flex-shrink-0">
            {uploadStatus === 'extracting' ? (
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
            {uploadStatus === 'extracting' ? (
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
        {uploadStatus === 'extracting' && (
          <div className="mt-2 w-full bg-blue-200 rounded-full h-1">
            <div className="h-1 rounded-full bg-blue-500 animate-pulse" style={{ width: '66%' }} />
          </div>
        )}
      </div>

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
              ['revenue','Revenue'],['ebit','EBIT'],['depreciation','Depreciation'],
              ['amortization','Amortization'],['interestExpense','Interest Exp'],
              ['cashInterestPaid','Cash Int Paid'],['cashTaxesPaid','Cash Tax Paid'],
            ]} />
          </Section>

          <Section title="Cash Flow (000s)" id="cashflow">
            <Table rows={[
              ['cfo','Operating CF'],['capex','Capex'],['commonDividends','Dividends'],
              ['preferredDividends','Pref Dividends'],['minorityDividends','Min Dividends'],
              ['sharebuybacks','Buybacks'],
            ]} />
          </Section>
        </div>

        <Section title="Balance Sheet (000s)" id="balance">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-4">
            <Table rows={[
              ['totalDebt','Total Debt'],['stDebt','ST Debt'],['cpltd','CPLTD'],
              ['ltDebt','LT Debt'],['capitalLeases','Capital Leases'],
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
