# Quick Start Guide - Credit Pricing Tool

## Installation & Setup

### Prerequisites
- Node.js 16+ (Vite requirement)
- npm or yarn package manager

### 1. Install Dependencies
```bash
npm install
```
This installs only:
- React 19
- React DOM 19
- Vite 7 (dev)
- ESLint & related tools (dev)

Note: No additional UI library packages are installed. Styling uses Tailwind via CDN.

### 2. Start Development Server
```bash
npm run dev
```
Opens Vite dev server at `http://localhost:5173`

The app will have hot module reloading - changes to files update instantly in the browser.

### 3. Build for Production
```bash
npm run build
```
Creates optimized production bundle in `/dist` directory.

### 4. Preview Production Build
```bash
npm run preview
```
Serves the production build locally for testing.

## Application Structure

### Pages (Hash Routes)
- **`/#/`** - Dashboard (landing page)
- **`/#/analysis`** - Financial analysis form
- **`/#/results`** - Analysis results display
- **`/#/rates`** - NZ bank base rates
- **`/#/upload`** - PDF upload & extraction

### Main Files

| File | Purpose |
|------|---------|
| `index.html` | HTML entry point with Tailwind CDN + custom styles |
| `src/main.jsx` | React app entry point |
| `src/App.jsx` | Main layout with sidebar nav & hash router |
| `src/api.js` | API client (mock implementations) |
| `src/index.css` | Global CSS |
| `src/pages/*.jsx` | Page components (5 files) |

## How to Use the App

### 1. Dashboard
Landing page showing:
- Quick statistics
- Action buttons to start analysis
- Information cards explaining features
- Link to base rates

### 2. Manual Analysis
Fill out the comprehensive form with:
- Company information
- Financial statements (all NZD millions)
- Facility details
- Click "Calculate Credit Spread"

System calculates:
- Expected credit spread range (min/max basis points)
- All-in rate (base rate + spread)
- Comparison with actual rate
- Key financial metrics and ratios

### 3. Results Page
Displays analysis results:
- Executive summary cards
- Pricing comparison with delta (green = good, red = paying more)
- Credit risk spectrum gauge
- Detailed financial metrics
- Credit ratios with benchmarks

### 4. Base Rates Page
Shows current rates from 5 NZ banks:
- ANZ, ASB, BNZ, Westpac, Kiwibank
- Corporate loan rates
- Working capital rates
- Spread comparison
- Rate benchmarking

### 5. PDF Upload
Upload financial statements:
- Drag-and-drop or click to select
- Supports PDF only (max 5 files)
- AI extraction simulated (uses mock data)
- Can use extracted data to populate analysis form

## Mock Data & Testing

All API calls use mock implementations:

### analyzeFinancials()
Returns spread calculation based on:
- EBITDA margin
- Debt/EBITDA ratio
- Interest coverage
- FFO/Debt ratio
- Facility type and tenor

Mock data: See `api.js` mockAnalyzeFinancials function

### getBaseRates()
Returns hardcoded NZ bank rates:
```
ANZ Corporate: 5.45%, WC: 5.75%
ASB Corporate: 5.40%, WC: 5.70%
BNZ Corporate: 5.50%, WC: 5.80%
Westpac Corporate: 5.48%, WC: 5.78%
Kiwibank Corporate: 5.55%, WC: 5.85%
```

### uploadPDF()
Returns mock extracted data with common financial metrics.

## Connecting to Real Backend

Edit `src/api.js`:

1. Uncomment the `fetch()` calls (currently commented)
2. Comment out the mock function calls
3. Update `API_BASE_URL` if needed (default: http://localhost:3000/api)

Example structure for analyze endpoint:
```javascript
// Input
{
  "companyName": "ABC Ltd",
  "businessDescription": "...",
  "industry": "Materials",
  "financialData": {
    "incomeStatement": { ... },
    "balanceSheet": { ... },
    "cashFlow": { ... }
  },
  "facilityDetails": {
    "actualRate": 5.5,
    "tenor": 3,
    "facilityType": "corporate"
  }
}

// Expected Output
{
  "expectedSpreadMin": 220,
  "expectedSpreadMax": 380,
  "baseRate": 5.0,
  "companyName": "ABC Ltd",
  "industry": "Materials",
  "ebitda": 8500,
  "netDebt": 15000,
  "debtToEbitda": 1.76,
  "ffoToDebt": 0.35,
  "ebitdaToInterest": 10.6
}
```

## Styling Guide

### Theme Colors
- **Primary Navy**: `#1e3a5f` (used via `.text-primary`, `.bg-primary`, etc.)
- **Success Green**: `#10b981`
- **Error Red**: `#ef4444`
- **Neutral**: `#f9fafb` to `#111827` (gray scale)

### CSS Classes (Tailwind + Custom)

Custom classes defined in `index.html`:
- `.btn-primary` - Primary button
- `.btn-secondary` - Secondary button
- `.card` - Standard card container
- `.input-field` - Form input styling
- `.section-header` - Collapsible section header
- `.metric-box` - Data metric display
- `.gradient-primary` - Primary color gradient

### Responsive Breakpoints
- `sm:` 640px
- `md:` 768px (main breakpoint)
- `lg:` 1024px
- `xl:` 1280px

## Form Fields

### Company Information
- Company Name (required for identification)
- Business Description (for AI sector mapping)
- Industry (27 S&P classification options)

### Financial Data (All NZD millions)
- **Income Statement**: Revenue, EBIT, D&A, Interest
- **Balance Sheet**: Debt breakdown, equity, assets, NWC
- **Cash Flow**: CFO, capex, dividends, buybacks

### Facility Details
- Actual Interest Rate (%)
- Tenor (1-5 years)
- Facility Type (Corporate or Working Capital)

Note: All fields are optional (use 0 or leave blank). Form validates and calculates with whatever data is provided.

## Results Output

### Key Metrics Displayed
1. **Expected Spread Range** (basis points)
2. **All-In Rate Range** (base rate + spread)
3. **Actual Rate Delta** (savings/overpayment vs market)
4. **Computed Ratios**:
   - Debt/EBITDA
   - FFO/Debt
   - EBITDA/Interest
   - Debt/Total Capital
   - EBITDA/Revenue
   - ROE

5. **Visual Indicators**:
   - Color-coded delta (green = saving, red = paying more)
   - Credit spectrum gauge (risk positioning)
   - Metric cards with benchmarks

## Troubleshooting

### Port Already in Use
If port 5173 is in use:
```bash
npm run dev -- --port 3000  # Use different port
```

### Module Not Found Errors
Ensure all page files exist:
- `src/pages/Dashboard.jsx`
- `src/pages/AnalysisForm.jsx`
- `src/pages/Results.jsx`
- `src/pages/BaseRates.jsx`
- `src/pages/Upload.jsx`

### Styles Not Loading
Check that `index.html` includes:
1. Tailwind CDN script: `<script src="https://cdn.tailwindcss.com"></script>`
2. Google Fonts import for Inter font
3. Custom styles in `<style>` tag

### Form Submission Issues
- Ensure all numeric fields are valid numbers (app parses to float)
- Check browser console for error messages
- Verify API endpoint URL if using real backend

## Environment Variables

Create `.env.local` file:
```
REACT_APP_API_URL=http://localhost:3000/api
```

Or set directly:
```bash
export REACT_APP_API_URL=http://your-backend.com/api
```

## Development Tips

1. **Check Console**: Open DevTools (F12) to see console logs
2. **Hot Reload**: Changes to any file auto-reload in browser
3. **React DevTools**: Install Chrome/Firefox extension for component debugging
4. **Network Tab**: Monitor API calls in DevTools Network tab
5. **Test Forms**: Try various financial data combinations
6. **Mobile Testing**: Resize browser window to test responsiveness

## Performance Notes

- App loads instantly (React 19 + Vite optimizations)
- No unnecessary re-renders (React 19 auto-batching)
- Tailwind CDN loads on demand
- Hash routing has no server overhead
- Forms handle large numbers efficiently

## Production Deployment

### Build
```bash
npm run build
```

### Deploy `/dist` folder to:
- AWS S3 + CloudFront
- Vercel
- Netlify
- GitHub Pages
- Any static host

### Configuration
Set environment variables on hosting platform:
```
REACT_APP_API_URL=https://your-api.com/api
```

### Health Check
Verify in production:
1. Navigation works (hash routes)
2. API calls reach backend
3. Forms submit successfully
4. Results calculate correctly
5. Mobile layout responsive

## Support & Documentation

For detailed architecture and component documentation, see `PROJECT_STRUCTURE.md`.

For API integration details, see commented code in `src/api.js`.

## License & Attribution

Built with React 19 and Vite 7. Uses Tailwind CSS via CDN and Google Fonts (Inter).
