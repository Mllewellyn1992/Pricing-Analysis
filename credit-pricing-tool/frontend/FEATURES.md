# Credit Pricing Tool - Feature Specification

## Core Features

### 1. Dashboard / Landing Page
**Location**: `/#/`

**Components:**
- **Quick Stats** (4-card grid)
  - Analyses Run (count)
  - Average Spread (bps)
  - Active Facilities (count)
  - Savings vs Market (bps)

- **Quick Actions** (2-card grid)
  - Manual Analysis button
  - Upload PDF button

- **Information Cards** (3-card grid)
  - "How It Works" (step-by-step process)
  - "Key Metrics" (financial ratios explained)
  - "NZ Base Rates" (quick access)

**Features:**
- Responsive 1-col mobile, 2-4 col desktop
- Icon indicators for each section
- Navigation buttons to other sections
- Overview of product capabilities

---

### 2. Financial Analysis Form
**Location**: `/#/analysis`

**Structure:**
5 collapsible sections for data organization

#### Section 1: Company Information
- **Company Name** (text input) - Business identifier
- **Business Description** (textarea) - For AI sector mapping context
- **Industry** (dropdown) - 27 S&P classifications
  - Aerospace & Defense, Automotive, Banks, Capital Goods, etc.

#### Section 2: Income Statement (NZD millions)
- Revenue
- EBIT (Earnings Before Interest & Taxes)
- Depreciation
- Amortization
- Interest Expense
- Cash Interest Paid
- Cash Taxes Paid

#### Section 3: Balance Sheet (NZD millions)
- **Debt Section** (accept total OR breakdown):
  - Total Debt (simplified entry)
  - ST Debt (Short-term debt)
  - CPLTD (Current Portion of LT Debt)
  - LT Debt (Long-term debt)
  - Capital Leases

- **Equity & Assets**:
  - Cash
  - Cash-like Assets
  - Total Equity
  - Minority Interest
  - Deferred Taxes

- **Working Capital & Assets**:
  - NWC Current (Net Working Capital - current year)
  - NWC Prior (NWC - prior year, for changes)
  - LT Operating Assets Current
  - LT Operating Assets Prior
  - Total Assets Current
  - Total Assets Prior

#### Section 4: Cash Flow (NZD millions)
- Operating Cash Flow (CFO)
- Capital Expenditures (Capex)
- Common Dividends
- Preferred Dividends
- Minority Dividends
- Share Buybacks

#### Section 5: Facility Details
- **Actual Interest Rate** (%) - Current/offered rate
- **Facility Tenor** (dropdown) - 1-5 years
- **Facility Type** (dropdown) - Corporate or Working Capital

**Form Features:**
- Collapsible sections (expandable/collapsible headers)
- Smooth expand/collapse animations
- Light section backgrounds for visual grouping
- Inline help text for some fields
- Notes explaining units (NZD millions)
- "Calculate Credit Spread" button (primary action)
- "Clear Form" button (secondary action)
- All fields optional (default to 0 if blank)
- Form validation on submit
- Loading state during calculation
- Error handling with user feedback

---

### 3. Analysis Results / Dashboard
**Location**: `/#/results`

**Display Sections:**

#### Executive Summary Cards (3-column grid)
1. **Expected Spread**
   - Large number (e.g., "285 bps")
   - Subtext showing range ("220-350 bps")
   - Navy blue primary styling

2. **All-In Rate**
   - Percentage (e.g., "5.85%")
   - Subtext showing range ("5.20%-5.80%")
   - Calculated as: base rate + spread

3. **Rate Delta**
   - Color-coded (green if saving, red if overpaying)
   - Shows magnitude (e.g., "+42 bps" or "-32 bps")
   - Icon indicator (✓ for good, ✗ for overpaying)

#### Facility Pricing Section
- Base Rate (NZ) - 5.0% example
- Market Spread - Calculated
- Expected All-In Rate
- **Actual Rate Comparison**
  - Your actual rate vs market expected
  - Visual bar showing delta
  - Interpretation text

#### Credit Spectrum Gauge
- Visual gradient (red → yellow → green)
- Positioned indicator showing company's position
- Risk category label (High Risk, Investment Grade, Prime)
- Percentile position information
- Market positioning relative to peers

#### Computed Financial Metrics (6-box grid)
- EBITDA (NZD millions)
- Free Cash Flow (CFO - Capex)
- Net Debt (Total Debt - Cash - Equivalents)
- Total Capital (Debt + Equity)
- EBIT Margin (%)
- Operating Cash Conversion (%)

Each metric box shows:
- Metric name (label)
- Calculated value (large bold)
- Unit of measurement (subtext)

#### Credit Ratios & Coverage (6-box grid)
Each ratio includes benchmark:

1. **Debt / EBITDA**
   - Shows company leverage
   - Benchmark: < 3.0x

2. **FFO / Debt**
   - Free cash generation vs debt
   - Benchmark: > 0.25x

3. **EBITDA / Interest**
   - Interest coverage ratio
   - Benchmark: > 2.5x

4. **Debt / Total Capital**
   - Capital structure leverage
   - Benchmark: < 60%

5. **EBITDA / Revenue**
   - Operating margin
   - Benchmark: > 15%

6. **ROE**
   - Return on equity
   - Benchmark: > 8%

**Features:**
- Collapsible sections for metrics
- Smooth expand/collapse
- Data-dense Bloomberg-terminal style
- Color-coded deltas (green/red)
- Benchmark comparisons for context
- Navigation buttons back to analysis/dashboard

---

### 4. Base Rates Monitor
**Location**: `/#/rates`

**Data Display:**

#### Summary Stats (2-card grid)
- Average Corporate Rate (all banks)
- Average Working Capital Rate (all banks)

#### Rates Table
**Columns:**
- Bank Name (icon + text)
- Corporate Loan Rate (%)
- Working Capital Rate (%)
- WC Spread vs Corporate (basis points)

**Banks Included:**
1. ANZ - 5.45% corporate, 5.75% WC (30 bps)
2. ASB - 5.40% corporate, 5.70% WC (30 bps)
3. BNZ - 5.50% corporate, 5.80% WC (30 bps)
4. Westpac - 5.48% corporate, 5.78% WC (30 bps)
5. Kiwibank - 5.55% corporate, 5.85% WC (30 bps)

#### Visual Rate Comparison
- Bar chart showing each bank's corporate rate
- Banks ranked by competitiveness
- Hover effects for emphasis
- Min/max rate highlighting

#### Information Cards
- **Supported Documents**
  - Annual Financial Statements
  - Audited Financial Reports
  - Quarterly Financial Statements
  - Management Accounts
  - Investor Presentations

- **Rate Spread Insights**
  - Working capital premium calculation
  - Explanation of why WC costs more

**Features:**
- Refresh button to update rates
- Last updated timestamp
- Responsive table (scrollable on mobile)
- Rate comparison insights
- Usage guidance

---

### 5. PDF Upload & Extraction
**Location**: `/#/upload`

**Upload Interface:**

#### Drag & Drop Zone
- Large drop target area
- Visual feedback on hover (border highlight, bg color change)
- Click to open file picker as fallback
- Upload icon and instructional text
- File format restriction note (PDF only)
- Max files note (5 files)

#### File Upload
- Accepts `.pdf` files only
- Maximum 5 files per upload
- Multiple file selection support
- File type validation
- Size information displayed

#### Processing Status
For each uploaded file:
- File icon (PDF icon)
- File name
- File size (MB)
- Status indicator:
  - Spinner animation while processing
  - Checkmark when complete
  - Error indicator on failure

#### Uploaded Files List
- Shows all uploaded files
- Processing status for each
- "Use Extracted Data" button when ready
- Extraction summary (data found)

**Extracted Data Includes:**
- Revenue
- EBIT/Operating Income
- Depreciation & Amortization
- Total Debt
- Cash & Equivalents
- Operating Cash Flow
- Capital Expenditures
- Interest Expense

#### Process Workflow Cards
Step-by-step explanation:
1. **Upload** - Drag/drop or select PDF files
2. **Extract** - AI identifies financial data
3. **Review** - Verify extracted numbers
4. **Analyze** - Use data for credit analysis

#### Information Cards
- **Supported Documents**
  - Types of financial statements accepted
  - Document quality requirements

- **Extracted Data**
  - What information is extracted
  - Data accuracy expectations
  - Manual verification recommendation

**Features:**
- Real-time file processing simulation
- Error handling (invalid formats)
- File count validation
- Size information display
- Success/error messaging
- Integration with analysis form
- Professional UI with clear instructions

---

## UI/UX Features

### Navigation
- **Hash-based routing** (no page reloads)
- **Persistent sidebar** on all pages
- **Active page highlight** in navigation
- **Breadcrumb-style labels** showing current section
- **Quick navigation** between related pages

### Form Handling
- **Collapsible sections** for complex forms
- **Field grouping** by financial statement section
- **Clear labeling** with units (NZD millions)
- **Placeholder text** showing example values
- **Input validation** with error messages
- **Form reset** button to clear all fields
- **Success feedback** on form submission

### Data Display
- **Color-coded metrics**
  - Green for positive/good news
  - Red for negative/concerning values
  - Navy blue for neutral information
- **Benchmark comparisons** for context
- **Visual indicators**
  - Progress bars for ratios
  - Gauge visualization for risk positioning
  - Icons for status (checkmark, error)

### Responsive Design
- **Mobile-first layout** (stacks on small screens)
- **Flexible grids** (1 col → 2 col → 3-4 col as screen grows)
- **Touch-friendly** form fields and buttons
- **Readable typography** at all sizes
- **Sidebar collapse** on mobile (if desired)

### Accessibility
- **Semantic HTML** (proper heading hierarchy)
- **Label associations** (form labels tied to inputs)
- **High contrast** (primary colors meet WCAG standards)
- **Focus states** (outline visible on keyboard navigation)
- **Descriptive text** for all actions/metrics

---

## Calculation Features

### Spread Calculation Algorithm
1. **Calculate Base Metrics**
   - EBITDA = EBIT + Depreciation + Amortization
   - Net Debt = Total Debt - Cash - Cash Equivalents
   - Free Cash Flow = Operating Cash Flow - Capex

2. **Compute Credit Ratios**
   - Debt/EBITDA (leverage indicator)
   - FFO/Debt (coverage indicator)
   - EBITDA/Interest (interest coverage)
   - Debt/Total Capital (structure)

3. **Determine Base Spread** (300 bps starting point)
   - Adjust for leverage (Debt/EBITDA)
   - Adjust for coverage (FFO/Debt, EBITDA/Interest)
   - Adjust for facility type (WC costs more)
   - Adjust for tenor (longer terms have adjustments)

4. **Create Range**
   - Min Spread: Base - 60 bps
   - Max Spread: Base + 60 bps

5. **Calculate All-In Rates**
   - Min All-In = Base Rate + Min Spread
   - Max All-In = Base Rate + Max Spread

6. **Compare to Actual**
   - Delta = Actual Rate - Expected All-In
   - Color code (positive delta = good/saving)

### Return Calculations
Returns structured data including:
- Expected spread range
- All-in rate range
- Base rate used
- Company name & industry
- All computed financial metrics
- All credit ratios
- Individual components for transparency

---

## Data Output Features

### Results Export Potential
Current implementation displays:
- All calculated metrics on Results page
- Color-coded performance indicators
- Comparison with market benchmarks
- Credit risk spectrum positioning

Future enhancement opportunities:
- PDF report generation
- CSV data export
- Comparison between multiple facilities
- Historical trend tracking
- Portfolio summary reporting

---

## Integration Points

### API Dependencies
1. **analyzeFinancials(formData)**
   - Input: Complete form submission
   - Output: Spread calculations & metrics
   - Current: Mock implementation
   - Ready: For backend integration

2. **getBaseRates()**
   - Output: Array of bank rate objects
   - Current: Hardcoded 5 banks
   - Ready: For real-time rate feed integration

3. **uploadPDF(file)**
   - Input: PDF file
   - Output: Extracted financial data
   - Current: Mock extraction
   - Ready: For AI/OCR extraction service

### Environment Configuration
- API base URL configurable via `REACT_APP_API_URL`
- Defaults to `http://localhost:3000/api`
- Supports `.env.local` files for different environments

---

## Performance Characteristics

- **Initial Load**: < 2s (Vite optimized, React 19)
- **Form Submission**: Instant (mock APIs respond immediately)
- **Page Navigation**: < 100ms (hash routing, no server calls)
- **Calculations**: < 10ms (all client-side math)
- **UI Responsiveness**: 60 FPS (CSS animations, React optimizations)

---

## Browser Compatibility

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- All modern mobile browsers
- Requires ES2020+ JavaScript support

---

## Security Considerations

- No sensitive user data stored locally
- No API credentials exposed in frontend
- Input validation on form fields
- XSS protection via React JSX
- CORS headers managed by backend
- All financial data transmitted to backend only

---

## Future Enhancement Roadmap

1. **Phase 2**: User authentication & saved analyses
2. **Phase 3**: Historical pricing trends
3. **Phase 4**: Multi-facility portfolio management
4. **Phase 5**: Real-time rate feeds from NZ banks
5. **Phase 6**: Scenario analysis & sensitivity testing
6. **Phase 7**: Integration with bank pricing systems
7. **Phase 8**: Mobile-optimized companion app
