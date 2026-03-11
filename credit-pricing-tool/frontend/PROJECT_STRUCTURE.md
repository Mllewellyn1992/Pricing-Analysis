# Credit Pricing Tool - Frontend Project Structure

## Overview
A production-quality React 19 + Vite 7 frontend for NZ corporate credit pricing analysis. Calculates expected credit spreads, all-in rates, and compares against actual facility pricing.

## Architecture

### Technology Stack
- **React 19** - UI framework
- **Vite 7** - Build tool
- **Tailwind CSS** - Styling via CDN (no npm packages installed)
- **Hash-based routing** - Simple client-side routing without react-router-dom

### Key Features
1. **Manual Financial Input** - Comprehensive form with collapsible sections
2. **PDF Upload** - AI-powered financial data extraction (placeholder)
3. **Credit Analysis** - Spread calculation using financial ratios
4. **Results Dashboard** - Data-dense Bloomberg-style report
5. **Base Rate Monitoring** - NZ bank rates comparison
6. **Responsive Design** - Mobile-optimized layout

## Directory Structure

```
/src
├── main.jsx              # React entry point with StrictMode
├── App.jsx              # Main app component with hash router & sidebar nav
├── api.js               # API client with mock implementations
├── index.css            # Global CSS styles
└── pages/
    ├── Dashboard.jsx        # Landing page with quick stats
    ├── AnalysisForm.jsx     # Comprehensive financial input form
    ├── Results.jsx          # Analysis results & metrics display
    ├── BaseRates.jsx        # NZ bank base rates comparison
    └── Upload.jsx           # PDF upload with drag-and-drop

/index.html             # HTML entry with Tailwind CDN & custom styles
/package.json           # Dependencies (React + React DOM only)
```

## Component Details

### 1. App.jsx (97 lines)
**Main application shell**
- Hash-based routing logic
- Sidebar navigation with 4 main sections
- State management for analysis results
- Pass-through navigation and data handlers

**Navigation:**
- `#/` → Dashboard
- `#/analysis` → Analysis Form
- `#/results` → Results (conditional display)
- `#/rates` → Base Rates
- `#/upload` → PDF Upload

### 2. Dashboard.jsx (157 lines)
**Landing page with overview**
- 4 quick stat cards (analyses run, avg spread, facilities, savings)
- 2 primary action cards (Manual Analysis, Upload PDF)
- 3 info cards (How It Works, Key Metrics, NZ Base Rates)
- Responsive grid layout (1 col mobile, 2-4 cols desktop)

### 3. AnalysisForm.jsx (396 lines)
**Comprehensive financial input form**
- 5 collapsible sections:
  - Company Info (name, description, industry dropdown)
  - Income Statement (revenue, EBIT, D&A, interest)
  - Balance Sheet (debt breakdown, cash, equity, working capital)
  - Cash Flow (CFO, capex, dividends, buybacks)
  - Facility Details (rate, tenor, type)
- All amounts in NZD millions
- Form validation on submit
- Clear/Reset button
- S&P industry classification dropdown (27 options)

### 4. Results.jsx (367 lines)
**Bloomberg-style data-dense results page**
- Executive summary cards (spread, all-in rate, delta)
- Facility pricing comparison with visual indicator
- Credit spectrum gauge (high risk → investment grade → prime)
- Computed metrics (EBITDA, FCF, net debt, margins)
- Credit ratios with benchmarks:
  - Debt/EBITDA
  - FFO/Debt
  - EBITDA/Interest
  - Debt/Total Capital
  - EBITDA/Revenue
  - ROE
- Collapsible metric sections
- Delta color-coding (green for savings, red for overpayment)

### 5. BaseRates.jsx (320 lines)
**NZ bank base rates monitoring**
- 5 major NZ banks: ANZ, ASB, BNZ, Westpac, Kiwibank
- Corporate & working capital rates
- Summary stats cards
- Rates comparison table
- Visual bar chart
- WC spread premium calculation
- Refresh functionality
- Responsive data display

### 6. Upload.jsx (341 lines)
**PDF upload with drag-and-drop**
- Drag-and-drop zone with visual feedback
- File selection via click
- Multiple file support (max 5)
- File type validation (PDF only)
- Processing simulation
- Uploaded files list with status
- Mock data extraction
- Process workflow explanation
- "Use Extracted Data" button (navigates to analysis form)

### 7. api.js (not production-specific)
**API client layer**
- `analyzeFinancials(formData)` - POST to /analyze
- `getBaseRates()` - GET from /base-rates
- `uploadPDF(file)` - POST to /extract-pdf
- Mock implementations for all functions
- Includes detailed payload structure
- Error handling
- Ready for backend integration (commented code included)

## Styling Approach

### Tailwind via CDN
- HTML includes `<script src="https://cdn.tailwindcss.com"></script>`
- No npm package required
- Full Tailwind utility classes available

### Custom CSS Variables
- Primary color: `#1e3a5f` (navy blue)
- Positive: `#10b981` (green)
- Negative: `#ef4444` (red)
- Defined in `index.html <style>` tag and `index.css`

### Custom Classes (index.html)
- `.gradient-primary` - Primary gradient background
- `.card` - Standard card styling with shadow
- `.card-hover` - Hover effects
- `.input-field` - Form input styling
- `.btn-primary` / `.btn-secondary` - Button styles
- `.section-header` - Collapsible section header
- `.metric-box` - Data metric display box
- `.gauge-background` - Gradient gauge background

## Form Structure

### Company Information
- Company Name (text input)
- Business Description (textarea for AI mapping)
- Industry (27-option dropdown)

### Income Statement (NZD millions)
- Revenue
- EBIT
- Depreciation
- Amortization
- Interest Expense
- Cash Interest Paid
- Cash Taxes Paid

### Balance Sheet (NZD millions)
- Total Debt OR breakdown (ST, CPLTD, LT, Capital Leases)
- Cash
- Cash-like Assets
- Total Equity
- Minority Interest
- Deferred Taxes
- NWC Current/Prior
- LT Operating Assets Current/Prior
- Total Assets Current/Prior

### Cash Flow (NZD millions)
- Operating Cash Flow (CFO)
- Capital Expenditures
- Common Dividends
- Preferred Dividends
- Minority Dividends
- Share Buybacks

### Facility Details
- Actual Interest Rate (%)
- Tenor (1-5 years)
- Facility Type (Corporate/Working Capital)

## Analysis Logic

### Credit Spread Calculation (mockAnalyzeFinancials)
1. Calculate EBITDA = EBIT + D&A
2. Calculate Net Debt = Total Debt - Cash
3. Compute ratios:
   - Debt/EBITDA
   - FFO/Debt = (CFO - Capex) / Debt
   - EBITDA/Interest
4. Base spread: 300 bps
5. Adjust based on ratios:
   - Debt/EBITDA < 2.0: -80 bps
   - Debt/EBITDA 2-3: -40 bps
   - Debt/EBITDA > 5.0: +100 bps
   - Interest coverage > 4x: -50 bps
   - Interest coverage < 2x: +80 bps
   - FFO/Debt > 0.4: -40 bps
   - FFO/Debt < 0.15: +60 bps
6. Adjust for facility type (+30 bps for WC)
7. Adjust for tenor (+/- 20 bps)
8. Create range: spread ± 60 bps

### Results Calculation
- Base rate: 5.0% (configurable)
- Min/Max all-in rates = base + spread range / 100
- Delta = actual rate - expected all-in rate
- Credit gauge: percentage position on risk spectrum
- Display ratios and benchmarks

## Design System

### Color Palette
- Primary Navy: `#1e3a5f`
- Primary Gradient: #1e3a5f → #2d5a8c
- Success Green: `#10b981`
- Error Red: `#ef4444`
- Neutral Gray: `#f9fafb` → `#111827`

### Typography
- Font: Inter (via Google Fonts CDN)
- Headings: Font-weight 600
- Body: Font-weight 400-500
- Line height: 1.5

### Spacing
- Padding scales: 0.5rem, 0.75rem, 1rem, 1.5rem, etc.
- Consistent 6px baseline grid (Tailwind default)

### Components
- Cards: White bg, 1px border, rounded corners, subtle shadow
- Inputs: 6px border radius, gray border, focus ring
- Buttons: 6px radius, padding 0.625rem × 1.25rem
- Forms: 4px gap between fields, 1rem section padding

## Mobile Responsiveness

### Breakpoints (Tailwind)
- Mobile: < 768px (1 column)
- Tablet: 768px-1024px (2 columns)
- Desktop: > 1024px (3-4 columns)

### Responsive Components
- Grid layouts use `grid-cols-1 md:grid-cols-2 lg:grid-cols-3`
- Form uses `md:grid-cols-2` for side-by-side on tablet+
- Sidebar is 16rem width (respects mobile widths)
- Main content auto-scrolls on small screens

## Getting Started

### Development
```bash
npm install  # Only React 19 and React DOM
npm run dev  # Start Vite dev server (default: http://localhost:5173)
```

### Building
```bash
npm run build   # Production build to /dist
npm run preview # Preview production build locally
```

### Environment Variables
- `REACT_APP_API_URL` - Backend API endpoint (default: http://localhost:3000/api)
- Set in `.env.local` or `.env`

## Backend Integration

### API Endpoints Required
1. **POST /api/analyze**
   - Input: Company info + financial data
   - Output: Spread range, ratios, metrics

2. **GET /api/base-rates**
   - Output: Array of banks with corporate/WC rates

3. **POST /api/extract-pdf**
   - Input: PDF file
   - Output: Extracted financial data

### Mock Mode
- All endpoints have working mock implementations in `api.js`
- Simply replace mock functions with fetch calls when backend ready
- Commented code included for reference

## Performance Considerations

1. **No heavy dependencies** - React + React DOM only
2. **Lazy component rendering** - Hash-based routing, components render on demand
3. **Form optimization** - Collapsible sections reduce visible DOM
4. **CSS via CDN** - No build-time CSS processing needed
5. **SVG icons inline** - No external icon library

## Browser Support

- Modern browsers (Chrome, Firefox, Safari, Edge)
- Requires ES2020+ support (Vite default)
- Responsive design supports mobile browsers

## Future Enhancements

1. Add comparison between multiple facility rates
2. Export results to PDF
3. Historical trend analysis
4. Facility portfolio management
5. Alerts for rate changes
6. Integration with pricing analytics backend
7. User authentication & saved analyses
8. Real-time NZ bank rate feeds

## Production Checklist

- [ ] Replace mock API functions with real backend calls
- [ ] Add error boundaries for robustness
- [ ] Implement API error handling & retry logic
- [ ] Add form validation (client-side)
- [ ] Configure backend API URL via environment variables
- [ ] Add loading states for all async operations
- [ ] Implement user feedback/notifications
- [ ] Add analytics tracking
- [ ] Performance monitoring setup
- [ ] Security review (input validation, CORS, etc.)
- [ ] Accessibility audit (WCAG 2.1 AA)
- [ ] Cross-browser testing
