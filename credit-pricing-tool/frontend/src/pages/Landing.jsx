function Landing({ onNavigate }) {
  return (
    <div className="min-h-screen bg-white flex flex-col">
      {/* Header/Navigation */}
      <header className="sticky top-0 z-40 bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center text-white font-bold text-lg">
              ₦
            </div>
            <span className="text-xl font-bold text-gray-900">Credit Pricing Tool</span>
          </div>
          <button
            onClick={() => onNavigate('#/dashboard')}
            className="px-6 py-2.5 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors"
          >
            Dashboard
          </button>
        </div>
      </header>

      {/* Hero Section */}
      <section className="flex-1 bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 relative overflow-hidden">
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute -top-40 -right-40 w-80 h-80 bg-blue-200 rounded-full mix-blend-multiply filter blur-3xl opacity-20"></div>
          <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-indigo-200 rounded-full mix-blend-multiply filter blur-3xl opacity-20"></div>
        </div>

        <div className="relative max-w-7xl mx-auto px-6 py-20 sm:py-32 flex flex-col justify-center min-h-[600px]">
          <div className="text-center mb-12">
            <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold text-gray-900 mb-6 leading-tight">
              Know Your True <span className="bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">Borrowing Cost</span>
            </h1>
            <p className="text-xl sm:text-2xl text-gray-600 max-w-2xl mx-auto mb-8 leading-relaxed">
              Understand if you're paying a fair rate on your business loans. Get instant credit pricing analysis using dual rating engines and live NZ bank rates.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <button
                onClick={() => onNavigate('#/dashboard')}
                className="px-8 py-4 bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-semibold rounded-lg hover:shadow-lg hover:from-blue-700 hover:to-indigo-700 transition-all text-lg"
              >
                Get Started →
              </button>
              <button
                onClick={() => {
                  const element = document.getElementById('how-it-works');
                  element?.scrollIntoView({ behavior: 'smooth' });
                }}
                className="px-8 py-4 bg-gray-100 text-gray-900 font-semibold rounded-lg hover:bg-gray-200 transition-colors text-lg"
              >
                Learn More
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">Powerful Features</h2>
            <p className="text-xl text-gray-600">Everything you need to benchmark your credit pricing</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            {/* Feature 1 */}
            <div className="p-8 bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl border border-blue-200 hover:shadow-lg transition-shadow">
              <div className="text-4xl mb-4">🤖</div>
              <h3 className="text-xl font-bold text-gray-900 mb-3">AI-Powered Analysis</h3>
              <p className="text-gray-700">
                Upload your financial statements as PDFs and our AI automatically extracts key financial metrics for instant analysis.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="p-8 bg-gradient-to-br from-indigo-50 to-indigo-100 rounded-xl border border-indigo-200 hover:shadow-lg transition-shadow">
              <div className="text-4xl mb-4">⚖️</div>
              <h3 className="text-xl font-bold text-gray-900 mb-3">Dual Rating Engines</h3>
              <p className="text-gray-700">
                Compare credit ratings using both S&P and Moody's methodologies to get a comprehensive view of your credit profile.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="p-8 bg-gradient-to-br from-purple-50 to-purple-100 rounded-xl border border-purple-200 hover:shadow-lg transition-shadow">
              <div className="text-4xl mb-4">📈</div>
              <h3 className="text-xl font-bold text-gray-900 mb-3">Live Market Rates</h3>
              <p className="text-gray-700">
                Get real-time NZ bank base rates from ANZ, ASB, BNZ, Westpac, and Kiwibank directly integrated into your analysis.
              </p>
            </div>

            {/* Feature 4 */}
            <div className="p-8 bg-gradient-to-br from-green-50 to-green-100 rounded-xl border border-green-200 hover:shadow-lg transition-shadow">
              <div className="text-4xl mb-4">✓</div>
              <h3 className="text-xl font-bold text-gray-900 mb-3">Instant Comparison</h3>
              <p className="text-gray-700">
                Compare your expected fair rate with what you're actually paying to identify pricing opportunities and savings.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section id="how-it-works" className="py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">How It Works</h2>
            <p className="text-xl text-gray-600">Three simple steps to analyze your credit pricing</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-6">
            {/* Step 1 */}
            <div className="relative">
              <div className="bg-white p-8 rounded-xl border-2 border-gray-200 h-full">
                <div className="absolute -top-6 -left-4 w-12 h-12 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold text-lg">
                  1
                </div>
                <h3 className="text-2xl font-bold text-gray-900 mb-4 mt-4">Upload Financial Data</h3>
                <p className="text-gray-700 leading-relaxed">
                  Upload your company's financial statements as a PDF, or manually enter your key financial metrics. Our AI extracts all the data you need.
                </p>
              </div>
            </div>

            {/* Arrow 1 */}
            <div className="hidden md:flex items-center justify-center">
              <div className="text-gray-400 text-4xl">→</div>
            </div>

            {/* Step 2 */}
            <div className="relative">
              <div className="bg-white p-8 rounded-xl border-2 border-gray-200 h-full">
                <div className="absolute -top-6 -left-4 w-12 h-12 bg-indigo-600 text-white rounded-full flex items-center justify-center font-bold text-lg">
                  2
                </div>
                <h3 className="text-2xl font-bold text-gray-900 mb-4 mt-4">Analyze & Rate</h3>
                <p className="text-gray-700 leading-relaxed">
                  Our dual rating engines calculate your credit profile using S&P and Moody's methodologies, then look up expected credit spreads from our pricing matrix.
                </p>
              </div>
            </div>

            {/* Arrow 2 */}
            <div className="hidden md:flex items-center justify-center">
              <div className="text-gray-400 text-4xl">→</div>
            </div>

            {/* Step 3 */}
            <div className="relative">
              <div className="bg-white p-8 rounded-xl border-2 border-gray-200 h-full">
                <div className="absolute -top-6 -left-4 w-12 h-12 bg-purple-600 text-white rounded-full flex items-center justify-center font-bold text-lg">
                  3
                </div>
                <h3 className="text-2xl font-bold text-gray-900 mb-4 mt-4">Compare & Optimize</h3>
                <p className="text-gray-700 leading-relaxed">
                  See your expected all-in rate versus your actual rate. Identify if you're overpaying and quantify potential savings opportunities.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Built for NZ Section */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-6">
          <div className="bg-gradient-to-r from-blue-600 to-indigo-600 rounded-2xl p-12 text-white">
            <h2 className="text-4xl font-bold mb-6">Built for New Zealand</h2>
            <p className="text-xl mb-8 leading-relaxed">
              Our pricing tool is specifically designed for NZ corporate finance. We integrate live rates from all major NZ banks and understand the local credit market.
            </p>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-6">
              <div className="text-center">
                <div className="text-3xl font-bold mb-2">ANZ</div>
                <p className="text-blue-100">Live Rates</p>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold mb-2">ASB</div>
                <p className="text-blue-100">Live Rates</p>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold mb-2">BNZ</div>
                <p className="text-blue-100">Live Rates</p>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold mb-2">Westpac</div>
                <p className="text-blue-100">Live Rates</p>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold mb-2">Kiwibank</div>
                <p className="text-blue-100">Live Rates</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-gray-50">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <h2 className="text-4xl font-bold text-gray-900 mb-6">Ready to Analyze Your Pricing?</h2>
          <p className="text-xl text-gray-600 mb-8">
            Start your free analysis today and understand if you're getting a fair rate on your business loans.
          </p>
          <button
            onClick={() => onNavigate('#/dashboard')}
            className="px-10 py-4 bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-semibold rounded-lg hover:shadow-lg hover:from-blue-700 hover:to-indigo-700 transition-all text-lg"
          >
            Get Started Now →
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-400 py-12">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-12 mb-8">
            <div>
              <div className="flex items-center gap-2 mb-4">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center text-white font-bold text-sm">
                  ₦
                </div>
                <span className="font-bold text-white">Credit Pricing Tool</span>
              </div>
              <p className="text-sm">
                Advanced credit spread analysis for NZ corporate finance teams.
              </p>
            </div>
            <div>
              <h4 className="font-semibold text-white mb-4">Product</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="#/" className="hover:text-white transition-colors">Home</a></li>
                <li><a href="#/dashboard" className="hover:text-white transition-colors">Dashboard</a></li>
                <li><a href="#/analysis" className="hover:text-white transition-colors">Analysis</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-white mb-4">Company</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="#/" className="hover:text-white transition-colors">About</a></li>
                <li><a href="#/" className="hover:text-white transition-colors">Contact</a></li>
                <li><a href="#/" className="hover:text-white transition-colors">Privacy</a></li>
              </ul>
            </div>
          </div>
          <div className="border-t border-gray-800 pt-8">
            <p className="text-center text-sm">
              Credit Pricing Tool © 2026. All rights reserved.
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}

export default Landing
