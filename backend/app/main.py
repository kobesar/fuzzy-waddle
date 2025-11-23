"""
FastAPI Backend for MLB Pitch Predictor
Main application file with API endpoints
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import os
from pathlib import Path

from .mlb_api import MLBStatsAPI
from .model import PitchPredictor


# Initialize FastAPI app
app = FastAPI(
    title="MLB Pitch Predictor API",
    description="API for predicting pitch sequences using MLB Stats data",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
mlb_api = MLBStatsAPI()
models = {}  # Store models per pitcher: {pitcher_id: PitchPredictor}
MODEL_DIR = Path("models")
MODEL_DIR.mkdir(exist_ok=True)


# Pydantic models for request/response
class PitcherSearchResponse(BaseModel):
    id: int
    name: str
    team: str
    position: str


class PitcherInfo(BaseModel):
    id: int
    name: str
    position: Optional[str]
    team: Optional[str]
    throws: Optional[str]
    age: Optional[int]
    height: Optional[str]
    weight: Optional[str]


class PredictionContext(BaseModel):
    balls: int = Field(ge=0, le=3, description="Number of balls in count")
    strikes: int = Field(ge=0, le=2, description="Number of strikes in count")
    outs: int = Field(ge=0, le=2, description="Number of outs")
    batter_side: str = Field(pattern="^[LR]$", description="Batter handedness (L or R)")
    runners_on: bool = Field(description="Are there runners on base")
    inning: int = Field(ge=1, le=9, description="Current inning")
    prev_pitch_type: Optional[str] = Field(None, description="Previous pitch type code")


class PredictionResponse(BaseModel):
    pitcher_id: int
    pitcher_name: str
    probabilities: Dict[str, float]
    context: Dict


class TrainingRequest(BaseModel):
    pitcher_id: int
    season: Optional[int] = None
    max_games: int = Field(20, ge=1, le=50, description="Maximum games to fetch")


class TrainingResponse(BaseModel):
    pitcher_id: int
    success: bool
    message: str
    metrics: Optional[Dict] = None


class PitcherSummaryResponse(BaseModel):
    pitcher_id: int
    total_pitches: int
    repertoire: Dict
    unique_pitch_types: int
    games: int
    avg_speed: Optional[float]


# API Endpoints

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "MLB Pitch Predictor API",
        "version": "1.0.0",
        "endpoints": {
            "search": "/api/pitchers/search",
            "info": "/api/pitchers/{pitcher_id}",
            "train": "/api/model/train",
            "predict": "/api/predict/{pitcher_id}",
            "summary": "/api/pitchers/{pitcher_id}/summary"
        }
    }


@app.get("/api/pitchers/search", response_model=List[PitcherSearchResponse])
async def search_pitchers(query: str, limit: int = 10):
    """
    Search for pitchers by name

    Args:
        query: Pitcher name to search
        limit: Maximum results to return

    Returns:
        List of matching pitchers
    """
    if not query or len(query) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")

    pitchers = mlb_api.search_pitchers(query, limit)

    if not pitchers:
        return []

    return pitchers


@app.get("/api/pitchers/{pitcher_id}", response_model=PitcherInfo)
async def get_pitcher_info(pitcher_id: int):
    """
    Get detailed information about a pitcher

    Args:
        pitcher_id: MLB player ID

    Returns:
        Pitcher information
    """
    info = mlb_api.get_pitcher_info(pitcher_id)

    if not info:
        raise HTTPException(status_code=404, detail="Pitcher not found")

    return info


@app.post("/api/model/train", response_model=TrainingResponse)
async def train_model(request: TrainingRequest, background_tasks: BackgroundTasks):
    """
    Train a prediction model for a specific pitcher

    Args:
        request: Training request with pitcher_id and parameters

    Returns:
        Training status and metrics
    """
    pitcher_id = request.pitcher_id

    # Get pitcher info first
    pitcher_info = mlb_api.get_pitcher_info(pitcher_id)
    if not pitcher_info:
        raise HTTPException(status_code=404, detail="Pitcher not found")

    # Fetch pitch data
    pitch_data = mlb_api.get_pitcher_pitch_data(
        pitcher_id=pitcher_id,
        season=request.season,
        max_games=request.max_games
    )

    if pitch_data.empty:
        return TrainingResponse(
            pitcher_id=pitcher_id,
            success=False,
            message="No pitch data found for this pitcher. They may not have pitched recently.",
            metrics=None
        )

    # Train model
    try:
        predictor = PitchPredictor()
        metrics = predictor.train(pitch_data)

        # Store model in memory
        models[pitcher_id] = {
            'predictor': predictor,
            'pitcher_name': pitcher_info['name'],
            'pitch_data': pitch_data
        }

        # Save model to disk
        model_path = MODEL_DIR / f"pitcher_{pitcher_id}.joblib"
        predictor.save(str(model_path))

        return TrainingResponse(
            pitcher_id=pitcher_id,
            success=True,
            message=f"Model trained successfully for {pitcher_info['name']}",
            metrics=metrics
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")


@app.post("/api/predict/{pitcher_id}", response_model=PredictionResponse)
async def predict_pitch(pitcher_id: int, context: PredictionContext):
    """
    Predict next pitch type for a pitcher given game context

    Args:
        pitcher_id: MLB player ID
        context: Current game situation

    Returns:
        Probability distribution of pitch types
    """
    # Check if model exists in memory
    if pitcher_id not in models:
        # Try to load from disk
        model_path = MODEL_DIR / f"pitcher_{pitcher_id}.joblib"
        if model_path.exists():
            predictor = PitchPredictor()
            predictor.load(str(model_path))

            pitcher_info = mlb_api.get_pitcher_info(pitcher_id)
            models[pitcher_id] = {
                'predictor': predictor,
                'pitcher_name': pitcher_info['name'] if pitcher_info else f"Pitcher {pitcher_id}",
                'pitch_data': None
            }
        else:
            raise HTTPException(
                status_code=404,
                detail="Model not found for this pitcher. Please train the model first."
            )

    # Make prediction
    predictor = models[pitcher_id]['predictor']
    pitcher_name = models[pitcher_id]['pitcher_name']

    try:
        probabilities = predictor.predict(context.dict())

        return PredictionResponse(
            pitcher_id=pitcher_id,
            pitcher_name=pitcher_name,
            probabilities=probabilities,
            context=context.dict()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@app.get("/api/pitchers/{pitcher_id}/summary", response_model=PitcherSummaryResponse)
async def get_pitcher_summary(pitcher_id: int):
    """
    Get pitch repertoire summary for a pitcher

    Args:
        pitcher_id: MLB player ID

    Returns:
        Summary statistics of pitcher's repertoire
    """
    # Check if we have data for this pitcher
    if pitcher_id not in models or models[pitcher_id]['pitch_data'] is None:
        raise HTTPException(
            status_code=404,
            detail="No data available for this pitcher. Please train the model first."
        )

    pitch_data = models[pitcher_id]['pitch_data']
    predictor = models[pitcher_id]['predictor']

    summary = predictor.get_pitcher_summary(pitch_data)

    return PitcherSummaryResponse(
        pitcher_id=pitcher_id,
        **summary
    )


@app.get("/api/model/status/{pitcher_id}")
async def get_model_status(pitcher_id: int):
    """
    Check if a model is trained for a specific pitcher

    Args:
        pitcher_id: MLB player ID

    Returns:
        Model status information
    """
    model_path = MODEL_DIR / f"pitcher_{pitcher_id}.joblib"

    is_loaded = pitcher_id in models
    is_saved = model_path.exists()

    return {
        "pitcher_id": pitcher_id,
        "is_loaded": is_loaded,
        "is_saved": is_saved,
        "status": "ready" if (is_loaded or is_saved) else "not_trained"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
