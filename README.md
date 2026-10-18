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

## Training Dataset (sequence model)

Pitch-by-pitch data for 2017-2025 (6.1M pitches, 20.7k games, regular season and postseason) comes from the MLB Stats API live feed, not the per-pitcher fetch used by the backend.

```bash
pip install -r data_collection/requirements.txt
python data_collection/statsapi_pitch_collector.py --start-year 2017 --end-year 2025   # ~25 min, resumable
python data_prep/build_dataset.py                                                      # -> data/pitches.parquet, data/vocab.json
python data_prep/baselines.py                                                          # count-based baselines
python modeling/train_sequence.py --name gru_mix                                       # GRU, ~5 min on Apple MPS
```

- **Sequence unit:** pitches of one pitcher in one game, grouped by `(game_pk, pitcher_id)` and ordered by `game_pitch_number`. `balls`, `strikes`, `outs`, base runners and score are the state before the pitch.
- **Target:** `y`, a 0-10 pitch-class id (see `data/vocab.json`; `-1` = missing label, not a training target). `p1`-`p3` are the previous three pitch classes by the same pitcher in the game.
- **Leakage:** columns listed in `vocab.json["leaky_columns"]` describe the pitch or the plate appearance outcome and must not be inputs. The previous pitch's results are available as `prev_call_code`, `prev_speed`, `prev_plate_x`, `prev_plate_z`.
- **Splits:** train 2017-2023, val 2024, test 2025.
- **Caveats:** `ST` (sweeper) is 0.6% of 2017 pitches and 7.6% of 2025 pitches (the feed's labeling changed); 2020 is a 60-game season; 23% of 2025 pitches are thrown by pitchers absent from 2017-2023, so a pitcher-ID embedding alone will not cover them.

Results on test (2025; 724k pitches with a real label; same rows for every model):

| Model | Top-1 accuracy | Log loss |
|---|---|---|
| Global pitch mix | 0.319 | 2.019 |
| Pitcher mix, pooled over train seasons | 0.374 | 1.834 |
| Pitcher's previous-season mix | 0.382 | 1.664 |
| Previous-season mix x count | 0.388 | 1.639 |
| Previous-season mix updated with the pitcher's pitches so far this game, x count | 0.421 | 1.381 |
| **GRU** (`modeling/train_sequence.py`, `modeling/runs/gru_mix.pt`) | **0.460** | **1.280** |

The GRU is a 2-layer, 192-unit causal model over each pitcher-game sequence. Inputs at each step are the pre-pitch state, the previous pitch (class, call, speed, location) and the pitcher's previous-season mix. On test pitches by pitchers absent from 2017-2023 it scores 0.469 accuracy and 1.274 log loss, so it does not depend on pitcher identity. Variants on validation (log loss): pitcher-id embedding 1.260, train from 2021 only 1.258, 256 units for 14 epochs 1.249, baseline GRU 1.248. Accuracy is lowest late in long outings (41+ pitches: 0.415 accuracy, 1.352 log loss) and highest on the first pitch of an outing (0.548, 1.225).

2026 check (games through 2026-10-17, `python data_prep/baselines.py --pitcher-id 660271` and `python modeling/evaluate.py --pitcher-id 660271`; the model was not retrained):

| Subset | Pitches | GRU acc / log loss | In-game baseline acc / log loss |
|---|---|---|---|
| 2026 postseason, all pitchers (33 games) | 9,462 | 0.456 / 1.275 | 0.428 / 1.329 |
| 2026 regular season, all pitchers | 714,102 | 0.441 / 1.335 | 0.402 / 1.428 |
| Ohtani (660271), 2026 regular season, 14 starts | 1,335 | 0.497 / 1.242 | 0.432 / 1.381 |
| Ohtani, 2026 postseason | 0 | none | none |

Ohtani has not pitched in the 2026 postseason through 2026-10-17; his last start was 2026-07-03.

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
