// API Client for Credit Pricing Tool
// Uses relative URLs to work in both development and production

const API_BASE = ''

/**
 * Analyze financial data - calls the real dual-engine rating + pricing pipeline.
 */
export async function analyzeFinancials(formData) {
  // Build the financials dict the backend expects (all values in thousands)
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

  // Compute all-in rate from base rate + margin
  const baseRate = parseFloat(formData.selectedBaseRate) || 0
  const currentMargin = parseFloat(formData.currentMargin) || 0
  const allInRate = baseRate + currentMargin
  const tenor = parseInt(formData.tenor) || 3
  const sectorId = formData.industry || 'technology_software_and_services'

  try {
    // Step 1: Call the full-analysis endpoint (does rating + pricing in one call)
    const response = await fetch(`${API_BASE}/api/pricing/full-analysis`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        financials,
        sector_id: sectorId,
        actual_rate_pct: allInRate,
        facility_tenor: tenor,
        facility_type: 'corporate',
        base_rate_type: 'corporate',
        base_rate_override: baseRate || undefined,
        selected_bank: formData.selectedBank || undefined,
        selected_product: formData.selectedProduct || undefined,
        current_margin: currentMargin || undefined,
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
      baseRate: baseRate || data.base_rate_pct,
      currentMargin: currentMargin,
      expectedSpreadMin: data.spread_min_bps,
      expectedSpreadMax: data.spread_max_bps,
      expectedRateMin: data.expected_rate_min,
      expectedRateMax: data.expected_rate_max,
      expectedRateMid: data.expected_rate_mid,
      actualRate: allInRate || data.actual_rate_pct,
      selectedBank: formData.selectedBank,
      selectedProduct: formData.selectedProduct,
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
    // Some banks may not have corporate_rate (only overdraft/working_capital)
    return data.map(r => ({
      bank: r.bank,
      corporateRate: r.corporate_rate ?? r.overdraft_rate ?? null,
      workingCapitalRate: r.working_capital_rate ?? r.overdraft_rate ?? null,
      overdraftRate: r.overdraft_rate ?? null,
      lastUpdated: r.last_updated,
      products: r.products || [],
    }))
  } catch (error) {
    console.error('Error fetching base rates:', error)
    throw error
  }
}

/**
 * Wake up the server (Render free tier cold start).
 * Returns true if the server is alive.
 */
export async function pingServer() {
  try {
    const controller = new AbortController()
    setTimeout(() => controller.abort(), 5000)
    const res = await fetch(`${API_BASE}/api/rates/ocr`, { signal: controller.signal })
    return res.ok
  } catch { return false }
}

/**
 * Upload a PDF and extract financial data.
 * Includes retry logic for Render cold-start failures.
 * @param {File} file
 * @param {function} onStatus - Optional callback for status updates ('warming_up', 'extracting', 'retrying')
 */
export async function uploadPDF(file, onStatus) {
  const MAX_RETRIES = 2
  const TIMEOUT_MS = 180000 // 3 minutes — extraction + Claude API can be slow

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      if (attempt > 0) {
        onStatus?.('retrying')
        // Wait before retry (exponential backoff: 3s, 6s)
        await new Promise(r => setTimeout(r, 3000 * attempt))
      }

      const formData = new FormData()
      formData.append('file', file)

      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS)

      const response = await fetch(`${API_BASE}/api/extract/pdf`, {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      })
      clearTimeout(timeoutId)

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
        businessDescription: data.business_description || null,
        sectorClassification: data.sector_classification || null,
      }
    } catch (error) {
      const isLastAttempt = attempt === MAX_RETRIES
      const isRetryable = error.name === 'AbortError' ||
        error.message.includes('Failed to fetch') ||
        error.message.includes('NetworkError') ||
        error.message.includes('API error:')

      if (isLastAttempt || !isRetryable) {
        console.error('Error uploading PDF:', error)
        if (error.name === 'AbortError') {
          throw new Error('Request timed out. The server may be starting up — please try again in a moment.')
        }
        throw error
      }
      // Otherwise, loop continues to retry
    }
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

/**
 * Get all lending products from all banks with optional filters.
 * @param {string} bank - Optional: filter by bank name (e.g., 'ASB')
 * @param {string} category - Optional: filter by category (e.g., 'business_lending')
 * @returns {Promise<Array>} Array of product objects
 */
export async function getAllProducts(bank, category) {
  try {
    let url = `${API_BASE}/api/rates/products`
    const params = new URLSearchParams()

    if (bank) params.append('bank', bank)
    if (category) params.append('category', category)

    if (params.toString()) {
      url += `?${params.toString()}`
    }

    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`)
    }

    return await response.json()
  } catch (error) {
    console.error('Error fetching products:', error)
    throw error
  }
}

/**
 * Get the current Official Cash Rate (OCR).
 * @returns {Promise<Object>} OCR data with rate_pct, decision_date, source
 */
export async function getOCR() {
  try {
    const response = await fetch(`${API_BASE}/api/rates/ocr`)

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`)
    }

    return await response.json()
  } catch (error) {
    console.error('Error fetching OCR:', error)
    throw error
  }
}

/**
 * Get wholesale rates (BKBM and swap rates) with historical data.
 * @returns {Promise<Object>} Wholesale rates data with latest and historical rates
 */
export async function getWholesaleRates() {
  try {
    const response = await fetch(`${API_BASE}/api/rates/wholesale`)

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`)
    }

    return await response.json()
  } catch (error) {
    console.error('Error fetching wholesale rates:', error)
    throw error
  }
}

/**
 * Get rate history for a specific bank product.
 * @param {string} bank - Bank name
 * @param {string} product - Product name
 * @param {number} days - Number of days (0 = all history)
 */
export async function getProductHistory(bank, product, days = 0) {
  try {
    const params = new URLSearchParams({ bank, product, days: days.toString() })
    const response = await fetch(`${API_BASE}/api/rates/history?${params}`)
    if (!response.ok) throw new Error(`API error: ${response.statusText}`)
    return await response.json()
  } catch (error) {
    console.error('Error fetching product history:', error)
    throw error
  }
}

/**
 * Get rate history for ALL products of a bank.
 * @param {string} bank - Bank name
 * @param {number} days - Number of days (0 = all history)
 */
export async function getBankHistory(bank, days = 0) {
  try {
    const params = new URLSearchParams({ bank, days: days.toString() })
    const response = await fetch(`${API_BASE}/api/rates/bank-history?${params}`)
    if (!response.ok) throw new Error(`API error: ${response.statusText}`)
    return await response.json()
  } catch (error) {
    console.error('Error fetching bank history:', error)
    throw error
  }
}

/**
 * Trigger a full scrape of all rate sources and save to database.
 */
export async function triggerScrape() {
  try {
    const response = await fetch(`${API_BASE}/api/rates/scrape`, {
      method: 'POST',
    })
    if (!response.ok) throw new Error(`API error: ${response.statusText}`)
    return await response.json()
  } catch (error) {
    console.error('Error triggering scrape:', error)
    throw error
  }
}

/**
 * Get the scrape audit log and data summary.
 * @param {number} limit - Number of entries to return
 */
export async function getAuditLog(limit = 50) {
  try {
    const response = await fetch(`${API_BASE}/api/rates/audit?limit=${limit}`)
    if (!response.ok) throw new Error(`API error: ${response.statusText}`)
    return await response.json()
  } catch (error) {
    console.error('Error fetching audit log:', error)
    throw error
  }
}

/**
 * Get detailed audit information for a specific scrape run.
 * @param {number} auditId - Audit entry ID
 */
export async function getAuditDetail(auditId) {
  try {
    const response = await fetch(`${API_BASE}/api/rates/audit/${auditId}`)
    if (!response.ok) throw new Error(`API error: ${response.statusText}`)
    return await response.json()
  } catch (error) {
    console.error('Error fetching audit detail:', error)
    throw error
  }
}

/**
 * Inject browser-scraped wholesale rates into Supabase.
 * Used by the browser scraper to save swap/BKBM data extracted from charts.
 * @param {Array} rates - Array of rate objects with rate_name, rate_pct, tenor, rate_type, date, source
 * @param {string} source - Source description
 */
export async function injectWholesaleRates(rates, source = 'interest.co.nz (browser)') {
  try {
    const response = await fetch(`${API_BASE}/api/rates/wholesale/inject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rates, source }),
    })
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || `API error: ${response.statusText}`)
    }
    return await response.json()
  } catch (error) {
    console.error('Error injecting wholesale rates:', error)
    throw error
  }
}
