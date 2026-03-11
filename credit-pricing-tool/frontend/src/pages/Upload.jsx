import { useState, useRef } from 'react'
import { uploadPDF } from '../api'

function Upload({ onNavigate }) {
  const [isDragging, setIsDragging] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState([])
  const [loading, setLoading] = useState(false)
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
  }

  const handleFiles = async (files) => {
    setError(null)
    const pdfFiles = files.filter((file) => file.type === 'application/pdf')

    if (pdfFiles.length === 0) {
      setError('Please upload PDF files only')
      return
    }

    if (pdfFiles.length + uploadedFiles.length > 5) {
      setError('Maximum 5 files can be uploaded at once')
      return
    }

    setLoading(true)

    try {
      for (const file of pdfFiles) {
        const result = await uploadPDF(file)
        setUploadedFiles((prev) => [
          ...prev,
          {
            id: Date.now() + Math.random(),
            name: file.name,
            size: (file.size / 1024 / 1024).toFixed(2),
            status: 'processing',
            extractedData: null,
          },
        ])

        // Simulate processing
        setTimeout(() => {
          setUploadedFiles((prev) =>
            prev.map((f) =>
              f.name === file.name
                ? {
                    ...f,
                    status: 'completed',
                    extractedData: result?.data || {},
                  }
                : f
            )
          )
        }, 2000)
      }
    } catch (err) {
      setError('Error uploading files: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleUseData = (fileData) => {
    if (fileData.extractedData) {
      // Navigate to analysis with pre-filled data
      onNavigate('#/analysis')
    }
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
              <div key={file.id} className="p-6 hover:bg-gray-50">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <svg
                        className="w-6 h-6 text-red-500"
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
                    {file.status === 'processing' && (
                      <div className="flex items-center gap-2">
                        <div className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full" />
                        <span className="text-sm font-medium text-gray-600">
                          Extracting...
                        </span>
                      </div>
                    )}
                    {file.status === 'completed' && (
                      <div className="flex items-center gap-2">
                        <span className="text-green-600">
                          <svg
                            className="w-5 h-5"
                            fill="currentColor"
                            viewBox="0 0 20 20"
                          >
                            <path
                              fillRule="evenodd"
                              d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                              clipRule="evenodd"
                            />
                          </svg>
                        </span>
                        <span className="text-sm font-medium text-gray-600">
                          Completed
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {file.status === 'completed' && (
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <button
                      onClick={() => handleUseData(file)}
                      className="btn-primary text-sm"
                    >
                      Use Extracted Data
                    </button>
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
            {
              step: '1',
              title: 'Upload',
              description: 'Drag and drop or select PDF files',
            },
            {
              step: '2',
              title: 'Extract',
              description: 'AI extracts financial data automatically',
            },
            {
              step: '3',
              title: 'Review',
              description: 'Verify extracted numbers are correct',
            },
            {
              step: '4',
              title: 'Analyze',
              description: 'Use data for credit spread analysis',
            },
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
          and extract financial figures. Please review all extracted data for accuracy before running your analysis. Extraction accuracy depends on PDF formatting and document quality.
        </p>
      </div>
    </div>
  )
}

export default Upload
