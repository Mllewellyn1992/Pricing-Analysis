import { useState, useRef } from 'react'
import { uploadPDF } from '../api'

// Map backend field names to human-readable labels
const FIELD_LABELS = {
  revenue_mn: 'Revenue',
  ebit_mn: 'EBIT / Operating Income',
  depreciation_mn: 'Depreciation',
  amortization_mn: 'Amortization',
  interest_expense_mn: 'Interest Expense',
  cash_interest_paid_mn: 'Cash Interest Paid',
  cash_taxes_paid_mn: 'Cash Taxes Paid',
  total_debt_mn: 'Total Debt',
  st_debt_mn: 'Short-term Debt',
  cpltd_mn: 'Current Portion LT Debt',
  lt_debt_net_mn: 'Long-term Debt (Net)',
  capital_leases_mn: 'Capital Leases',
  cash_mn: 'Cash & Equivalents',
  cash_like_mn: 'Cash-like Securities',
  total_equity_mn: 'Total Equity',
  minority_interest_mn: 'Minority Interest',
  deferred_taxes_mn: 'Deferred Taxes',
  cfo_mn: 'Operating Cash Flow',
  capex_mn: 'Capital Expenditures',
  common_dividends_mn: 'Common Dividends',
  preferred_dividends_mn: 'Preferred Dividends',
  nwc_current_mn: 'Net Working Capital (Current)',
  nwc_prior_mn: 'Net Working Capital (Prior)',
  lt_operating_assets_current_mn: 'LT Operating Assets (Current)',
  lt_operating_assets_prior_mn: 'LT Operating Assets (Prior)',
  assets_current_mn: 'Total Assets (Current)',
  assets_prior_mn: 'Total Assets (Prior)',
  avg_capital_mn: 'Average Capital',
}

// Confidence level badge
function ConfidenceBadge({ score }) {
  if (score == null) return null
  const pct = Math.round(score * 100)
  let color = 'bg-red-100 text-red-700'
  if (pct >= 90) color = 'bg-green-100 text-green-700'
  else if (pct >= 75) color = 'bg-blue-100 text-blue-700'
  else if (pct >= 60) color = 'bg-yellow-100 text-yellow-700'

  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${color}`}>
      {pct}%
    </span>
  )
}

function Upload({ onNavigate, onUseExtractedData }) {
  const [isDragging, setIsDragging] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState([])
  const [error, setError] = useState(null)
  const fileInputRef = useRef(null)

  const handleDragEnter = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    e.stopPropagation()
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
    const files = Array.from(e.dataTransfer.files)
    handleFiles(files)
  }

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files)
    handleFiles(files)
    // Reset input so the same file can be re-selected
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleFiles = async (files) => {
    setError(null)
    const pdfFiles = files.filter(
      (file) => file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
    )

    if (pdfFiles.length === 0) {
      setError('Please upload PDF files only')
      return
    }

    if (pdfFiles.length + uploadedFiles.length > 5) {
      setError('Maximum 5 files can be uploaded at once')
      return
    }

    for (const file of pdfFiles) {
      const fileId = Date.now() + '_' + Math.random().toString(36).slice(2)

      // Add file to list IMMEDIATELY with "uploading" status
      setUploadedFiles((prev) => [
        ...prev,
        {
          id: fileId,
          name: file.name,
          size: (file.size / 1024 / 1024).toFixed(2),
          status: 'uploading',
          extractedData: null,
          confidenceScores: null,
          extractionMethod: null,
          error: null,
        },
      ])

      // Process the upload in background
      processFile(file, fileId)
    }
  }

  const processFile = async (file, fileId) => {
    try {
      // Update status to "extracting" once upload starts
      setUploadedFiles((prev) =>
        prev.map((f) => (f.id === fileId ? { ...f, status: 'extracting' } : f))
      )

      const result = await uploadPDF(file)

      // Update with extracted data
      setUploadedFiles((prev) =>
        prev.map((f) =>
          f.id === fileId
            ? {
                ...f,
                status: 'completed',
                extractedData: result?.data || {},
                confidenceScores: result?.confidenceScores || {},
                extractionMethod: result?.extractionMethod || 'unknown',
                rawTextPreview: result?.rawTextPreview || '',
                businessDescription: result?.businessDescription || null,
                sectorClassification: result?.sectorClassification || null,
              }
            : f
        )
      )
    } catch (err) {
      // Update file with error but don't remove it
      setUploadedFiles((prev) =>
        prev.map((f) =>
          f.id === fileId
            ? { ...f, status: 'error', error: err.message }
            : f
        )
      )
    }
  }

  const handleUseData = (fileData) => {
    if (fileData.extractedData && onUseExtractedData) {
      onUseExtractedData({
        fields: fileData.extractedData,
        confidence: fileData.confidenceScores,
        method: fileData.extractionMethod,
        fileName: fileData.name,
        businessDescription: fileData.businessDescription,
        sectorClassification: fileData.sectorClassification,
      })
    }
  }

  const handleRetry = (fileData) => {
    // Remove the failed file and re-add it
    setUploadedFiles((prev) => prev.filter((f) => f.id !== fileData.id))
  }

  const extractedFieldCount = (data) => {
    if (!data) return 0
    return Object.keys(data).filter((k) => data[k] != null && data[k] !== 0).length
  }

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-2">
        Upload Financial Statements
      </h1>
      <p className="text-gray-600 mb-8">
        Upload PDF financial statements to automatically extract data and populate the analysis form
      </p>

      {/* Drag and Drop Zone */}
      <div
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        className={`card p-12 text-center cursor-pointer transition-all mb-8 ${
          isDragging
            ? 'border-primary border-2 bg-blue-50'
            : 'border-2 border-dashed border-gray-300 hover:border-primary hover:bg-gray-50'
        }`}
        onClick={() => fileInputRef.current?.click()}
      >
        <svg
          className="w-12 h-12 mx-auto mb-4 text-primary"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
          />
        </svg>

        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          {isDragging ? 'Drop files here' : 'Drag PDF files here'}
        </h3>
        <p className="text-gray-600 mb-4">or click to select files</p>

        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf"
          onChange={handleFileSelect}
          className="hidden"
        />

        <div className="inline-block px-4 py-2 bg-primary text-white rounded-lg font-medium">
          Select Files
        </div>

        <p className="text-xs text-gray-500 mt-4">
          Maximum 5 PDF files • Supports financial statements, annual reports, and audit documents
        </p>
      </div>

      {/* Error Message */}
      {error && (
        <div className="card p-4 bg-red-50 border-l-4 border-red-500 mb-8">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Uploaded Files List */}
      {uploadedFiles.length > 0 && (
        <div className="card overflow-hidden mb-8">
          <div className="p-6 border-b border-gray-200 bg-gray-50">
            <h2 className="text-lg font-semibold text-gray-900">
              Uploaded Files ({uploadedFiles.length})
            </h2>
          </div>

          <div className="divide-y divide-gray-200">
            {uploadedFiles.map((file) => (
              <div key={file.id} className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <svg
                        className="w-6 h-6 text-red-500 flex-shrink-0"
                        fill="currentColor"
                        viewBox="0 0 20 20"
                      >
                        <path d="M4 3a2 2 0 012-2h8a2 2 0 012 2v12a1 1 0 110 2h-3.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-1.414 0l-2.414-2.414a1 1 0 00-.707-.293H4a2 2 0 01-2-2V3z" />
                      </svg>
                      <div>
                        <p className="font-medium text-gray-900">{file.name}</p>
                        <p className="text-xs text-gray-500">{file.size} MB</p>
                      </div>
                    </div>
                  </div>

                  <div className="text-right ml-4">
                    {(file.status === 'uploading' || file.status === 'extracting') && (
                      <div className="flex items-center gap-2">
                        <div className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full" />
                        <span className="text-sm font-medium text-gray-600">
                          {file.status === 'uploading' ? 'Uploading...' : 'Extracting financials...'}
                        </span>
                      </div>
                    )}
                    {file.status === 'completed' && (
                      <div className="flex items-center gap-2">
                        <span className="text-green-600">
                          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                            <path
                              fillRule="evenodd"
                              d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                              clipRule="evenodd"
                            />
                          </svg>
                        </span>
                        <span className="text-sm font-medium text-green-600">
                          {extractedFieldCount(file.extractedData)} fields extracted
                        </span>
                      </div>
                    )}
                    {file.status === 'error' && (
                      <div className="flex items-center gap-2">
                        <span className="text-red-500">
                          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                            <path
                              fillRule="evenodd"
                              d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                              clipRule="evenodd"
                            />
                          </svg>
                        </span>
                        <span className="text-sm font-medium text-red-600">
                          Failed
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Error details */}
                {file.status === 'error' && (
                  <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
                    <p className="text-sm text-red-700">{file.error}</p>
                    <button
                      onClick={() => handleRetry(file)}
                      className="mt-2 text-sm text-red-600 underline hover:text-red-800"
                    >
                      Remove and try again
                    </button>
                  </div>
                )}

                {/* Extraction method info */}
                {file.status === 'completed' && file.extractionMethod && (
                  <div className="mt-2">
                    <span className="text-xs text-gray-500">
                      Extraction method: <span className="font-medium">{file.extractionMethod}</span>
                    </span>
                  </div>
                )}

                {/* Extracted fields table */}
                {file.status === 'completed' && file.extractedData && Object.keys(file.extractedData).length > 0 && (
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <h4 className="text-sm font-semibold text-gray-900 mb-3">
                      Extracted Financial Data (NZD millions)
                    </h4>
                    <div className="bg-gray-50 rounded-lg overflow-hidden">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="bg-gray-100">
                            <th className="text-left px-4 py-2 font-medium text-gray-700">Field</th>
                            <th className="text-right px-4 py-2 font-medium text-gray-700">Value</th>
                            <th className="text-center px-4 py-2 font-medium text-gray-700">Confidence</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(file.extractedData)
                            .filter(([_, v]) => v != null && v !== 0)
                            .map(([key, value]) => (
                              <tr key={key} className="border-t border-gray-200">
                                <td className="px-4 py-2 text-gray-700">
                                  {FIELD_LABELS[key] || key}
                                </td>
                                <td className="px-4 py-2 text-right font-mono text-gray-900">
                                  {typeof value === 'number' ? value.toLocaleString('en-NZ', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : value}
                                </td>
                                <td className="px-4 py-2 text-center">
                                  <ConfidenceBadge score={file.confidenceScores?.[key]} />
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>

                    {/* Use Data button */}
                    <div className="mt-4 flex gap-3">
                      <button
                        onClick={() => handleUseData(file)}
                        className="btn-primary text-sm px-6"
                      >
                        Use in Analysis
                      </button>
                      <span className="text-xs text-gray-500 self-center">
                        Pre-fills the analysis form with these values
                      </span>
                    </div>
                  </div>
                )}

                {/* No data extracted */}
                {file.status === 'completed' && (!file.extractedData || Object.keys(file.extractedData).length === 0) && (
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                      <p className="text-sm text-yellow-800">
                        No financial fields could be automatically extracted from this document.
                        The PDF may not contain standard financial statement formats.
                      </p>
                    </div>
                  </div>
                )}

                {/* Loading progress bar */}
                {(file.status === 'uploading' || file.status === 'extracting') && (
                  <div className="mt-3">
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full transition-all duration-1000 ${
                          file.status === 'uploading' ? 'w-1/3 bg-blue-400' : 'w-2/3 bg-primary animate-pulse'
                        }`}
                      />
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      {file.status === 'uploading'
                        ? 'Uploading PDF to server...'
                        : 'AI is reading and extracting financial data... this may take 30-60 seconds'}
                    </p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Information Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <span className="text-2xl mr-3">📄</span>
            Supported Documents
          </h3>
          <ul className="space-y-2 text-sm text-gray-600">
            <li className="flex items-start">
              <span className="text-green-600 mr-2 mt-0.5">✓</span>
              <span>Annual Financial Statements</span>
            </li>
            <li className="flex items-start">
              <span className="text-green-600 mr-2 mt-0.5">✓</span>
              <span>Audited Financial Reports</span>
            </li>
            <li className="flex items-start">
              <span className="text-green-600 mr-2 mt-0.5">✓</span>
              <span>Quarterly Financial Statements</span>
            </li>
            <li className="flex items-start">
              <span className="text-green-600 mr-2 mt-0.5">✓</span>
              <span>Management Accounts</span>
            </li>
            <li className="flex items-start">
              <span className="text-green-600 mr-2 mt-0.5">✓</span>
              <span>Investor Presentations</span>
            </li>
          </ul>
        </div>

        <div className="card p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <span className="text-2xl mr-3">⚡</span>
            Extracted Data
          </h3>
          <p className="text-sm text-gray-600 mb-4">
            Our AI extraction identifies and populates:
          </p>
          <ul className="space-y-1 text-sm text-gray-600">
            <li>• Revenue and EBITDA figures</li>
            <li>• Total debt and cash balances</li>
            <li>• Operating cash flows</li>
            <li>• Capital expenditures</li>
            <li>• Interest expense and coverage</li>
          </ul>
        </div>
      </div>

      {/* Process Steps */}
      <div className="mt-8 card p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">How It Works</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {[
            { step: '1', title: 'Upload', description: 'Drag and drop or select PDF files' },
            { step: '2', title: 'Extract', description: 'AI extracts financial data automatically' },
            { step: '3', title: 'Review', description: 'Check extracted values and confidence scores' },
            { step: '4', title: 'Analyze', description: 'Click "Use in Analysis" to run credit spread' },
          ].map((item) => (
            <div key={item.step} className="text-center">
              <div className="w-10 h-10 rounded-full bg-primary text-white flex items-center justify-center font-bold mx-auto mb-3">
                {item.step}
              </div>
              <h4 className="font-semibold text-gray-900 mb-1">{item.title}</h4>
              <p className="text-sm text-gray-600">{item.description}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Footer Note */}
      <div className="mt-8 p-6 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-sm text-gray-700">
          <span className="font-semibold text-primary">Note:</span> PDF extraction uses AI to identify
          and extract financial figures. Please review all extracted data for accuracy before running your analysis.
          Extraction accuracy depends on PDF formatting and document quality.
        </p>
      </div>
    </div>
  )
}

export default Upload
