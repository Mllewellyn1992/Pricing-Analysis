// API Client for Credit Pricing Tool
// Uses relative URLs to work in both development and production

const API_BASE = ''

/**
 * Analyze financial data - calls the real dual-engine rating + pricing pipeline.
 */
export async function analyzeFinancials(formData) {
  // Build the financials dict the backend expects (all values in millions)
  const financials = {
    revenue_mn: parseFloat(formData.revenue) || 0,
    ebit_mn: parseFloat(formData.ebit) || 0,
    depreciation_mn: parseFloat(formData.depreciation) || 0,
    amortization_mn: parseFloat(formData.amortization) || 0,
    interest_expense_mn: parseFloat(formData.interestExpense) || 0,
    cash_interest_paid_mn: parseFloat(formData.cashInterestPaid) || 0,
    cash_taxes_paid_mn: parseFloat(formData.cashTaxesPaid) || 0,
    total_debt_mn: parseFloat(formData.totalDebt) || 0,
    st_debt_mn: parseFloat(formData.stDebt) || 0,
    cpltd_mn: parseFloat(formData.cpltd) || 0,
    lt_debt_net_mn: parseFloat(formData.ltDebt) || 0,
    capital_leases_mn: parseFloat(formData.capitalLeases) || 0,
    cash_mn: parseFloat(formData.cash) || 0,
    cash_like_mn: parseFloat(formData.cashLikeAssets) || 0,
    total_equity_mn: parseFloat(formData.totalEquity) || 0,
    minority_interest_mn: parseFloat(formData.minorityInterest) || 0,
    deferred_taxes_mn: parseFloat(formData.deferredTaxes) || 0,
    nwc_current_mn: parseFloat(formData.nwcCurrent) || 0,
    nwc_prior_mn: parseFloat(formData.nwcPrior) || 0,
    lt_operating_assets_current_mn: parseFloat(formData.ltOperatingAssetsCurrent) || 0,
    lt_operating_assets_prior_mn: parseFloat(formData.ltOperatingAssetsPrior) || 0,
    assets_current_mn: parseFloat(formData.totalAssetsCurrent) || 0,
    assets_prior_mn: parseFloat(formData.totalAssetsPrior) || 0,
    cfo_mn: parseFloat(formData.cfo) || 0,
    capex_mn: parseFloat(formData.capex) || 0,
    common_dividends_mn: parseFloat(formData.commonDividends) || 0,
    preferred_dividends_mn: parseFloat(formData.preferredDividends) || 0,
    minority_dividends_mn: parseFloat(formData.minorityDividends) || 0,
    dividends_paid_mn: parseFloat(formData.commonDividends) || 0,
    share_buybacks_mn: parseFloat(formData.sharebuybacks) || 0,
    avg_capital_mn: parseFloat(formData.avgCapital) || parseFloat(formData.totalEquity) || 0,
  }

  // Compute total_debt if not provided but components are
  if (!financials.total_debt_mn && (financials.st_debt_mn || financials.lt_debt_net_mn)) {
    financials.total_debt_mn = financials.st_debt_mn + financials.cpltd_mn + financials.lt_debt_net_mn + financials.capital_leases_mn
  }

  const actualRate = parseFloat(formData.actualRate) || 0
  const tenor = parseInt(formData.tenor) || 3
  const facilityType = formData.facilityType || 'corporate'
  const sectorId = formData.industry || 'technology_software_and_services'

  try {
    // Step 1: Call the full-analysis endpoint (does rating + pricing in one call)
    const response = await fetch(`${API_BASE}/api/pricing/full-analysis`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        financials,
        sector_id: sectorId,
        actual_rate_pct: actualRate,
        facility_tenor: tenor,
        facility_type: facilityType,
        base_rate_type: facilityType === 'working-capital' ? 'working_capital' : 'corporate',
      }),
    })

    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || `API error: ${response.statusText}`)
    }

    const data = await response.json()

    // Map backend response to frontend format
    const ebitda = financials.ebit_mn + financials.depreciation_mn + financials.amortization_mn
    const netDebt = financials.total_debt_mn - financials.cash_mn - financials.cash_like_mn

    return {
      companyName: formData.companyName,
      industry: sectorId,

      // Rating results (internal - we show spread/rate, not letter ratings)
      _sp_rating: data.ratings?.sp_rating,
      _moodys_rating: data.ratings?.moodys_rating,
      _blended_rating: data.ratings?.blended_rating,

      // Pricing results (this is what the user sees)
      baseRate: data.base_rate_pct,
      expectedSpreadMin: data.spread_min_bps,
      expectedSpreadMax: data.spread_max_bps,
      expectedRateMin: data.expected_rate_min,
      expectedRateMax: data.expected_rate_max,
      expectedRateMid: data.expected_rate_mid,
      actualRate: data.actual_rate_pct,
      deltaBps: data.delta_bps,
      interpretation: data.interpretation,

      // Computed metrics
      ebitda,
      netDebt,
      totalDebt: financials.total_debt_mn,
      debtToEbitda: ebitda > 0 ? financials.total_debt_mn / ebitda : 0,
      ffoToDebt: financials.total_debt_mn > 0
        ? (financials.cfo_mn - financials.capex_mn) / financials.total_debt_mn
        : 0,
      ebitdaToInterest: financials.interest_expense_mn > 0
        ? ebitda / financials.interest_expense_mn
        : 0,
      revenue: financials.revenue_mn,
      ebit: financials.ebit_mn,
      interestExpense: financials.interest_expense_mn,
      cfo: financials.cfo_mn,
      capex: financials.capex_mn,
      totalEquity: financials.total_equity_mn,
    }
  } catch (error) {
    console.error('Error analyzing financials:', error)
    throw error
  }
}

/**
 * Get current NZ bank base rates from the backend.
 */
export async function getBaseRates() {
  try {
    const response = await fetch(`${API_BASE}/api/base-rates`)

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`)
    }

    const data = await response.json()

    // Map backend format to frontend format
    return data.map(r => ({
      bank: r.bank,
      corporateRate: r.corporate_rate,
      workingCapitalRate: r.working_capital_rate,
      lastUpdated: r.last_updated,
    }))
  } catch (error) {
    console.error('Error fetching base rates:', error)
    throw error
  }
}

/**
 * Upload a PDF and extract financial data.
 */
export async function uploadPDF(file) {
  try {
    const formData = new FormData()
    formData.append('file', file)

    const response = await fetch(`${API_BASE}/api/extract/pdf`, {
      method: 'POST',
      body: formData,
    })

    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || `API error: ${response.statusText}`)
    }

    const data = await response.json()

    return {
      fileName: file.name,
      status: data.status || 'success',
      extractionMethod: data.extraction_method,
      data: data.extracted_fields || {},
      confidenceScores: data.confidence_scores || {},
      rawTextPreview: data.raw_text_preview || '',
    }
  } catch (error) {
    console.error('Error uploading PDF:', error)
    throw error
  }
}

/**
 * Classify a business into S&P and Moody's sectors.
 */
export async function classifySector(businessDescription) {
  try {
    const response = await fetch(`${API_BASE}/api/classify-sector`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ business_description: businessDescription }),
    })

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`)
    }

    return await response.json()
  } catch (error) {
    console.error('Error classifying sector:', error)
    throw error
  }
}
