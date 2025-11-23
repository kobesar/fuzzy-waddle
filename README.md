# MLB Pitch Predictor

A full-stack web application that predicts the next pitch type in an MLB pitching sequence using machine learning and real-time data from the MLB Stats API.

![MLB Pitch Predictor](https://img.shields.io/badge/status-active-success.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![React](https://img.shields.io/badge/react-18.2-blue.svg)

## Features

- **Pitcher Search**: Search and select any active MLB pitcher
- **Real-Time Data**: Fetches pitch-by-pitch data from the official MLB Stats API
- **Machine Learning**: Random Forest model trained on actual pitching sequences
- **Interactive Predictions**: Adjust game context (count, inning, runners, etc.) and see predictions update
- **Visual Analytics**:
  - Pitch repertoire breakdown with usage percentages
  - Radar chart for prediction probabilities
  - Interactive dashboard with pitcher statistics

## Tech Stack

### Backend
- **FastAPI**: Modern Python web framework
- **scikit-learn**: Machine learning model (Random Forest)
- **pandas**: Data processing and feature engineering
- **MLB Stats API**: Official MLB data source

### Frontend
- **React**: Component-based UI framework
- **Recharts**: Data visualization library
- **Axios**: HTTP client for API requests

## Project Structure

```
pitch-predictor/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI application
│   │   ├── mlb_api.py        # MLB Stats API client
│   │   ├── model.py          # ML prediction model
│   │   └── __init__.py
│   ├── requirements.txt      # Python dependencies
│   └── README.md            # Backend documentation
├── frontend/
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── App.js           # Main application
│   │   └── api.js           # API client
│   ├── package.json         # Node dependencies
│   └── README.md           # Frontend documentation
└── README.md               # This file
```

## Quick Start

### Prerequisites

- Python 3.8 or higher
- Node.js 14 or higher
- npm or yarn

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Start the FastAPI server:
```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm start
```

The application will open at `http://localhost:3000`

## How It Works

### 1. Data Retrieval

The application fetches pitch-by-pitch data from the MLB Stats API for a selected pitcher:

```python
# Example: Get pitch data for Gerrit Cole
pitch_data = mlb_api.get_pitcher_pitch_data(
    pitcher_id=543037,
    season=2024,
    max_games=20
)
```

### 2. Feature Engineering

The model uses several contextual features:

- **Count State**: Balls and strikes (0-0, 3-2, etc.)
- **Situational**: Outs, inning, runners on base
- **Batter**: Handedness (L/R)
- **Sequence**: Previous pitch type
- **Derived**: Count advantage (ahead/behind), two-strike count, etc.

### 3. Model Training

A Random Forest classifier is trained on historical pitch sequences:

```python
predictor = PitchPredictor()
metrics = predictor.train(pitch_data)
# Returns: accuracy, n_samples, pitch_types
```

### 4. Prediction

Given a game context, the model predicts the probability of each pitch type:

```python
probabilities = predictor.predict({
    'balls': 3,
    'strikes': 2,
    'outs': 1,
    'batter_side': 'R',
    'runners_on': True,
    'inning': 7
})
# Returns: {'FF': 0.45, 'SL': 0.30, 'CH': 0.15, ...}
```

## API Endpoints

### Search Pitchers
```http
GET /api/pitchers/search?query=Cole&limit=10
```

### Get Pitcher Info
```http
GET /api/pitchers/{pitcher_id}
```

### Train Model
```http
POST /api/model/train
{
  "pitcher_id": 543037,
  "season": 2024,
  "max_games": 20
}
```

### Predict Pitch
```http
POST /api/predict/{pitcher_id}
{
  "balls": 3,
  "strikes": 2,
  "outs": 1,
  "batter_side": "R",
  "runners_on": true,
  "inning": 7
}
```

### Get Pitcher Summary
```http
GET /api/pitchers/{pitcher_id}/summary
```

## Model Details

### Algorithm
- **Random Forest Classifier** with 100 estimators
- Max depth: 10
- Balanced class weights to handle pitch type imbalance

### Features Used (14 total)
- balls, strikes, outs
- is_ahead, is_behind, is_even
- two_strikes, three_balls, full_count
- batter_is_right, runners_on
- inning, late_inning, early_inning
- prev_pitch_type (one-hot encoded)

### Performance
- Typical accuracy: 35-45% (varies by pitcher)
- Note: Baseline (always predict most common pitch) is typically 25-35%
- Model significantly outperforms random guessing

## Usage Examples

### Example 1: Full Count Scenario

**Context:**
- Count: 3-2
- Outs: 2
- Inning: 9
- Runners on: Yes
- Batter: Right-handed

**Prediction:**
- Fastball (FF): 52%
- Slider (SL): 28%
- Changeup (CH): 15%
- Curveball (CU): 5%

### Example 2: First Pitch

**Context:**
- Count: 0-0
- Outs: 0
- Inning: 1
- Runners on: No
- Batter: Left-handed

**Prediction:**
- Fastball (FF): 48%
- Sinker (SI): 22%
- Slider (SL): 18%
- Changeup (CH): 12%

## Deployment

### Local Deployment
Both frontend and backend can run locally for development (see Quick Start)

### Cloud Deployment Options

#### Backend (FastAPI)
- **Render**: Deploy as a web service
- **Railway**: Quick deployment with GitHub integration
- **AWS EC2**: More control, requires configuration

#### Frontend (React)
- **Vercel**: Optimized for React apps
- **Netlify**: Easy deployment with form handling
- **GitHub Pages**: Free static hosting

### Environment Variables

Create a `.env` file in the backend directory:

```env
# Optional: Configure API settings
API_HOST=0.0.0.0
API_PORT=8000

# Optional: Rate limiting
MAX_REQUESTS_PER_MINUTE=60
```

Frontend `.env`:

```env
REACT_APP_API_URL=http://localhost:8000
```

## Development

### Running Tests

Backend:
```bash
cd backend
pytest
```

Frontend:
```bash
cd frontend
npm test
```

### Code Quality

Backend:
```bash
# Format code
black app/

# Lint
flake8 app/
```

Frontend:
```bash
# Lint
npm run lint

# Format
npm run format
```

## Limitations

1. **Data Availability**: Requires pitcher to have recent game data
2. **Model Accuracy**: Pitching is inherently unpredictable; model provides probabilities, not certainties
3. **API Rate Limits**: MLB Stats API may have rate limits
4. **Contextual Factors**: Model doesn't consider score, specific batters, or park factors

## Future Enhancements

- [ ] Add LSTM/RNN for better sequence modeling
- [ ] Include batter-specific tendencies
- [ ] Add pitch location prediction (x/y coordinates)
- [ ] Historical performance tracking
- [ ] Real-time game integration
- [ ] Mobile app version

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License.

## Acknowledgments

- MLB Stats API for providing comprehensive baseball data
- scikit-learn community for excellent ML tools
- React and FastAPI communities

## Contact

For questions or feedback, please open an issue on GitHub.

---

**Note**: This application is for educational and entertainment purposes. Predictions are based on historical data and should not be used for gambling or other purposes requiring guaranteed accuracy.
