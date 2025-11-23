# MLB Pitch Predictor - Frontend

React frontend for the MLB Pitch Predictor application.

## Overview

An interactive web interface for predicting MLB pitch sequences using machine learning.

## Features

- **Pitcher Search**: Autocomplete search with real-time results
- **Pitcher Dashboard**:
  - Detailed pitcher information
  - Pitch repertoire breakdown
  - Visual analytics with charts
- **Prediction Panel**:
  - Interactive game context controls
  - Real-time probability predictions
  - Radar chart visualization
  - Preset scenarios for quick testing

## Installation

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure API URL

Create a `.env` file in the frontend directory:

```env
REACT_APP_API_URL=http://localhost:8000
```

## Running the Application

### Development Mode

```bash
npm start
```

Opens the browser at `http://localhost:3000`

### Production Build

```bash
npm run build
```

Creates an optimized build in the `build/` directory.

### Run Production Build Locally

```bash
npm install -g serve
serve -s build
```

## Project Structure

```
frontend/
├── public/
│   └── index.html           # HTML template
├── src/
│   ├── components/
│   │   ├── PitcherSearch.js      # Search component
│   │   ├── PitcherSearch.css
│   │   ├── PitcherDashboard.js   # Dashboard component
│   │   ├── PitcherDashboard.css
│   │   ├── PredictionPanel.js    # Prediction component
│   │   ├── PredictionPanel.css
│   │   ├── RepertoireChart.js    # Bar chart for repertoire
│   │   └── PredictionChart.js    # Radar chart for predictions
│   ├── App.js               # Main application component
│   ├── App.css              # Main styles
│   ├── api.js               # API client
│   ├── index.js             # Entry point
│   └── index.css            # Global styles
├── package.json             # Dependencies
└── README.md               # This file
```

## Component Overview

### App.js

Main application component that manages state and layout.

**State:**
- `selectedPitcher`: Currently selected pitcher object
- `isModelTrained`: Whether the model is trained for this pitcher

**Props passed to children:**
- `onSelect`: Callback when pitcher is selected
- `onModelTrained`: Callback when model training completes

### PitcherSearch

Autocomplete search component for finding pitchers.

**Features:**
- Debounced search (300ms)
- Real-time results from API
- Dropdown with pitcher names and teams

**API Calls:**
- `searchPitchers(query)`: Searches MLB pitchers

**Props:**
- `onSelect`: Callback function when pitcher is selected

### PitcherDashboard

Displays pitcher information and handles model training.

**Features:**
- Pitcher info card (name, team, throws, age, height)
- Model status indicator
- Training button with loading state
- Pitch repertoire visualization
- Pitch type breakdown with statistics

**API Calls:**
- `getPitcherInfo(pitcherId)`: Gets pitcher details
- `getModelStatus(pitcherId)`: Checks if model is trained
- `trainModel(pitcherId, season, maxGames)`: Trains the model
- `getPitcherSummary(pitcherId)`: Gets repertoire data

**Props:**
- `pitcher`: Selected pitcher object
- `onModelTrained`: Callback when training completes

### PredictionPanel

Interactive prediction interface with context controls.

**Features:**
- Visual count display (balls-strikes)
- Slider controls for count, outs, inning
- Radio buttons for batter handedness
- Checkbox for runners on base
- Preset scenarios (quick buttons)
- Probability visualization
- Bar chart with percentages

**API Calls:**
- `predictPitch(pitcherId, context)`: Gets pitch predictions

**Props:**
- `pitcher`: Selected pitcher object

### RepertoireChart

Bar chart showing pitcher's pitch usage.

**Uses:** Recharts library (BarChart component)

**Data Format:**
```javascript
[
  { name: 'FF', percentage: 50.0, count: 773 },
  { name: 'SL', percentage: 30.0, count: 464 },
  ...
]
```

### PredictionChart

Radar chart showing prediction probabilities.

**Uses:** Recharts library (RadarChart component)

**Data Format:**
```javascript
[
  { pitch: 'FF', probability: 52.0 },
  { pitch: 'SL', probability: 28.0 },
  ...
]
```

## API Client (`api.js`)

Centralized API client using Axios.

**Configuration:**
```javascript
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
```

**Methods:**
- `searchPitchers(query, limit)`: Search for pitchers
- `getPitcherInfo(pitcherId)`: Get pitcher details
- `trainModel(pitcherId, season, maxGames)`: Train model
- `predictPitch(pitcherId, context)`: Get predictions
- `getPitcherSummary(pitcherId)`: Get repertoire summary
- `getModelStatus(pitcherId)`: Check model status

**Example Usage:**
```javascript
import { searchPitchers, predictPitch } from './api';

// Search
const pitchers = await searchPitchers('Cole');

// Predict
const result = await predictPitch(543037, {
  balls: 3,
  strikes: 2,
  outs: 1,
  batter_side: 'R',
  runners_on: true,
  inning: 7
});
```

## Styling

### CSS Architecture

- **Global styles**: `index.css`
- **App-level styles**: `App.css`
- **Component styles**: Individual CSS files per component

### Design System

**Colors:**
- Primary gradient: `#667eea` to `#764ba2`
- Background: Purple gradient
- Cards: White with shadow
- Text: `#333` (dark), `#666` (medium), white (on dark)

**Components:**
- Border radius: `8px` to `12px` (rounded corners)
- Shadows: `0 8px 16px rgba(0, 0, 0, 0.1)`
- Transitions: `0.3s ease`

**Responsive:**
- Grid layout with `auto-fit` and `minmax`
- Breakpoint at `1024px` for mobile

## State Management

Currently uses React's built-in state (useState).

**Future considerations:**
- Context API for global state
- Redux for complex state management
- React Query for server state

## Performance Optimizations

1. **Debounced Search**: 300ms delay on search input
2. **Lazy Loading**: Could add for routes
3. **Memoization**: Could add React.memo for expensive components
4. **Code Splitting**: Could implement with React.lazy()

## Error Handling

Errors are displayed to users via:
- `error-message` class (red background)
- `success-message` class (green background)

**Error Sources:**
- API request failures
- Network errors
- Model not trained
- Invalid pitcher ID

## Testing

### Run Tests

```bash
npm test
```

### Test Coverage

```bash
npm test -- --coverage
```

### Manual Testing Checklist

- [ ] Search for pitcher by name
- [ ] Select pitcher from results
- [ ] Train model for pitcher
- [ ] Adjust count sliders
- [ ] Toggle batter handedness
- [ ] Toggle runners on base
- [ ] Click preset scenarios
- [ ] Generate predictions
- [ ] Verify charts render correctly

## Deployment

### Vercel

1. Install Vercel CLI:
```bash
npm install -g vercel
```

2. Deploy:
```bash
vercel
```

3. Set environment variables:
```bash
vercel env add REACT_APP_API_URL
```

### Netlify

1. Build the app:
```bash
npm run build
```

2. Deploy `build/` directory via Netlify UI or CLI

3. Set environment variable `REACT_APP_API_URL`

### GitHub Pages

1. Install gh-pages:
```bash
npm install --save-dev gh-pages
```

2. Add to `package.json`:
```json
{
  "homepage": "https://yourusername.github.io/mlb-pitch-predictor",
  "scripts": {
    "predeploy": "npm run build",
    "deploy": "gh-pages -d build"
  }
}
```

3. Deploy:
```bash
npm run deploy
```

## Environment Variables

Create `.env` file:

```env
# Backend API URL
REACT_APP_API_URL=http://localhost:8000

# Optional: Enable debug mode
REACT_APP_DEBUG=false
```

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## Accessibility

Current implementation includes:
- Semantic HTML
- Keyboard navigation
- Clear labels

**Future improvements:**
- ARIA labels
- Screen reader support
- Color contrast improvements

## Troubleshooting

### "Failed to fetch"
- Check backend is running at `http://localhost:8000`
- Verify `REACT_APP_API_URL` is set correctly
- Check CORS configuration in backend

### Blank page
- Check browser console for errors
- Verify all dependencies installed: `npm install`
- Clear cache and rebuild: `rm -rf node_modules package-lock.json && npm install`

### Charts not rendering
- Ensure Recharts is installed: `npm install recharts`
- Check data format matches component expectations

### Search not working
- Verify backend API is accessible
- Check network tab in browser DevTools
- Ensure pitcher names are spelled correctly

## Contributing

When contributing to the frontend:

1. Follow existing code style
2. Use functional components with hooks
3. Keep components small and focused
4. Add PropTypes for type checking (if desired)
5. Test on multiple browsers

## Future Enhancements

- [ ] Dark mode toggle
- [ ] Mobile-responsive improvements
- [ ] Pitch location heatmap
- [ ] Historical prediction tracking
- [ ] Multi-pitcher comparison
- [ ] Export predictions to PDF/CSV
- [ ] Real-time game integration
- [ ] User accounts and favorites

## License

MIT License
