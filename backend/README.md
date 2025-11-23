# MLB Pitch Predictor - Backend

FastAPI backend for the MLB Pitch Predictor application.

## Overview

This backend provides a RESTful API for:
- Searching MLB pitchers
- Fetching pitch data from MLB Stats API
- Training machine learning models
- Making pitch predictions

## Installation

### 1. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

## Running the Server

### Development Mode (with auto-reload)

```bash
uvicorn app.main:app --reload
```

### Production Mode

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI application and routes
│   ├── mlb_api.py       # MLB Stats API client
│   ├── model.py         # Machine learning model
│   └── utils.py         # Helper functions
├── models/              # Saved model files (created at runtime)
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Key Components

### 1. MLB Stats API Client (`mlb_api.py`)

Handles all interactions with the MLB Stats API:

```python
from app.mlb_api import MLBStatsAPI

api = MLBStatsAPI()

# Search for pitchers
pitchers = api.search_pitchers("Verlander")

# Get pitcher information
info = api.get_pitcher_info(pitcher_id=434378)

# Fetch pitch data
pitch_data = api.get_pitcher_pitch_data(
    pitcher_id=434378,
    season=2024,
    max_games=20
)
```

**Key Methods:**
- `search_pitchers(query)`: Search for pitchers by name
- `get_pitcher_info(pitcher_id)`: Get detailed pitcher information
- `get_game_ids_for_pitcher(pitcher_id, season)`: Get list of games
- `get_pitch_data_for_game(game_pk, pitcher_id)`: Get pitch-by-pitch data
- `get_pitcher_pitch_data(pitcher_id, season, max_games)`: Comprehensive data fetch

### 2. Pitch Predictor Model (`model.py`)

Machine learning model for pitch prediction:

```python
from app.model import PitchPredictor

predictor = PitchPredictor()

# Train on pitch data
metrics = predictor.train(pitch_dataframe)

# Make predictions
probabilities = predictor.predict({
    'balls': 3,
    'strikes': 2,
    'outs': 1,
    'batter_side': 'R',
    'runners_on': True,
    'inning': 7
})

# Save/load model
predictor.save('models/pitcher_12345.joblib')
predictor.load('models/pitcher_12345.joblib')
```

**Key Methods:**
- `train(dataframe)`: Train model on pitch data
- `predict(context)`: Predict pitch probabilities
- `get_pitcher_summary(dataframe)`: Generate statistics
- `save(path)`: Save model to disk
- `load(path)`: Load model from disk

### 3. FastAPI Application (`main.py`)

Main application with API endpoints.

**Endpoints:**

#### Health Check
```http
GET /health
```

#### Search Pitchers
```http
GET /api/pitchers/search?query=Cole&limit=10
```

Response:
```json
[
  {
    "id": 543037,
    "name": "Gerrit Cole",
    "team": "New York Yankees",
    "position": "P"
  }
]
```

#### Get Pitcher Info
```http
GET /api/pitchers/{pitcher_id}
```

Response:
```json
{
  "id": 543037,
  "name": "Gerrit Cole",
  "position": "Pitcher",
  "team": "New York Yankees",
  "throws": "R",
  "age": 33,
  "height": "6' 4\"",
  "weight": "225"
}
```

#### Train Model
```http
POST /api/model/train
Content-Type: application/json

{
  "pitcher_id": 543037,
  "season": 2024,
  "max_games": 20
}
```

Response:
```json
{
  "pitcher_id": 543037,
  "success": true,
  "message": "Model trained successfully for Gerrit Cole",
  "metrics": {
    "accuracy": 0.42,
    "n_samples": 1547,
    "pitch_types": ["FF", "SL", "CH", "CU"],
    "n_features": 18
  }
}
```

#### Predict Pitch
```http
POST /api/predict/{pitcher_id}
Content-Type: application/json

{
  "balls": 3,
  "strikes": 2,
  "outs": 1,
  "batter_side": "R",
  "runners_on": true,
  "inning": 7,
  "prev_pitch_type": "SL"
}
```

Response:
```json
{
  "pitcher_id": 543037,
  "pitcher_name": "Gerrit Cole",
  "probabilities": {
    "FF": 0.52,
    "SL": 0.28,
    "CH": 0.15,
    "CU": 0.05
  },
  "context": {
    "balls": 3,
    "strikes": 2,
    "outs": 1,
    "batter_side": "R",
    "runners_on": true,
    "inning": 7
  }
}
```

#### Get Pitcher Summary
```http
GET /api/pitchers/{pitcher_id}/summary
```

Response:
```json
{
  "pitcher_id": 543037,
  "total_pitches": 1547,
  "games": 20,
  "unique_pitch_types": 4,
  "avg_speed": 96.3,
  "repertoire": {
    "FF": {
      "count": 773,
      "percentage": 50.0,
      "avg_speed": 97.8
    },
    "SL": {
      "count": 464,
      "percentage": 30.0,
      "avg_speed": 89.2
    },
    "CH": {
      "count": 232,
      "percentage": 15.0,
      "avg_speed": 88.5
    },
    "CU": {
      "count": 78,
      "percentage": 5.0,
      "avg_speed": 81.3
    }
  }
}
```

## Model Architecture

### Random Forest Classifier

**Hyperparameters:**
- n_estimators: 100
- max_depth: 10
- min_samples_split: 10
- class_weight: 'balanced'
- random_state: 42

### Features (18 total)

**Base Features:**
- balls (0-3)
- strikes (0-2)
- outs (0-2)
- inning (1-9)
- batter_is_right (0/1)
- runners_on (0/1)

**Derived Features:**
- is_ahead (pitcher ahead in count)
- is_behind (pitcher behind in count)
- is_even (even count)
- two_strikes (2 strikes)
- three_balls (3 balls)
- full_count (3-2)
- late_inning (7-9)
- early_inning (1-3)

**Previous Pitch Type (One-Hot Encoded):**
- prev_FF, prev_SL, prev_CH, etc.

### Training Process

1. **Data Collection**: Fetch pitch-by-pitch data from MLB API
2. **Feature Engineering**: Create contextual features
3. **Encoding**: Label encode target (pitch types)
4. **Training**: Fit Random Forest model
5. **Persistence**: Save model to disk

## Performance Considerations

### Caching
- Models are cached in memory after loading
- Saved to disk for persistence

### Rate Limiting
- MLB Stats API may have rate limits
- Consider implementing request throttling for production

### Optimization
- Use `max_games` parameter to limit data fetching
- Models are lightweight (typically < 1MB)

## Error Handling

The API includes comprehensive error handling:

```python
try:
    result = await train_model(pitcher_id)
except HTTPException as e:
    # 404: Pitcher not found
    # 400: Invalid request
    # 500: Server error
    return error_response
```

## Testing

### Manual Testing

Use the interactive Swagger UI at `/docs`

### Example with curl

```bash
# Search pitchers
curl "http://localhost:8000/api/pitchers/search?query=Cole"

# Train model
curl -X POST "http://localhost:8000/api/model/train" \
  -H "Content-Type: application/json" \
  -d '{"pitcher_id": 543037, "max_games": 10}'

# Predict pitch
curl -X POST "http://localhost:8000/api/predict/543037" \
  -H "Content-Type: application/json" \
  -d '{
    "balls": 3,
    "strikes": 2,
    "outs": 1,
    "batter_side": "R",
    "runners_on": true,
    "inning": 7
  }'
```

## Environment Variables

Create a `.env` file:

```env
# Server Configuration
API_HOST=0.0.0.0
API_PORT=8000

# CORS (comma-separated origins)
ALLOWED_ORIGINS=http://localhost:3000,https://yourapp.com

# Logging
LOG_LEVEL=INFO
```

## Deployment

### Docker

Create `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:

```bash
docker build -t mlb-pitch-predictor-backend .
docker run -p 8000:8000 mlb-pitch-predictor-backend
```

### Production Considerations

1. **Use a production ASGI server**: Already using uvicorn
2. **Enable HTTPS**: Use a reverse proxy (nginx)
3. **Set CORS properly**: Update allowed origins
4. **Add authentication**: If needed for your use case
5. **Monitor performance**: Use logging and metrics
6. **Database**: Consider adding PostgreSQL for model metadata

## Troubleshooting

### "No pitch data found"
- Pitcher may not have recent games
- Try a different season or increase `max_games`

### "Model not trained"
- Run the `/api/model/train` endpoint first
- Check if model file exists in `models/` directory

### Slow training
- Reduce `max_games` parameter
- Some pitchers have many pitches per game

### API connection errors
- Check MLB Stats API is accessible
- Verify internet connection

## Contributing

When contributing to the backend:

1. Follow PEP 8 style guide
2. Add type hints where possible
3. Update docstrings for new functions
4. Test endpoints with Swagger UI

## License

MIT License
