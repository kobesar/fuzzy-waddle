"""
Pitch Prediction Model
Machine learning model to predict next pitch type based on game context
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from typing import Dict, List, Optional, Tuple
import joblib
from pathlib import Path


class PitchPredictor:
    """
    Random Forest-based pitch prediction model
    Predicts the probability distribution of next pitch types
    """

    def __init__(self):
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=10,
            random_state=42,
            class_weight='balanced'
        )
        self.label_encoder = LabelEncoder()
        self.feature_columns = []
        self.is_trained = False
        self.pitch_types = []

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Engineer features from raw pitch data

        Args:
            df: Raw pitch DataFrame

        Returns:
            DataFrame with engineered features
        """
        df = df.copy()

        # Create count state features
        df['count_state'] = df['balls'].astype(str) + '-' + df['strikes'].astype(str)

        # Create binary features
        df['is_ahead'] = ((df['balls'] < df['strikes']) |
                          ((df['balls'] == 0) & (df['strikes'] > 0))).astype(int)
        df['is_behind'] = (df['balls'] > df['strikes']).astype(int)
        df['is_even'] = (df['balls'] == df['strikes']).astype(int)

        # Two-strike count
        df['two_strikes'] = (df['strikes'] == 2).astype(int)

        # Three-ball count
        df['three_balls'] = (df['balls'] == 3).astype(int)

        # Full count
        df['full_count'] = ((df['balls'] == 3) & (df['strikes'] == 2)).astype(int)

        # Batter handedness (encode)
        df['batter_is_right'] = (df['batter_side'] == 'R').astype(int)

        # Runners on base
        df['runners_on'] = df['runners_on'].astype(int)

        # Inning-based features
        df['late_inning'] = (df['inning'] >= 7).astype(int)
        df['early_inning'] = (df['inning'] <= 3).astype(int)

        # Sort by game and sequence to create previous pitch features
        if 'game_pk' in df.columns:
            df = df.sort_values(['game_pk', df.index]).reset_index(drop=True)

        # Previous pitch type (shifted)
        df['prev_pitch_type'] = df['pitch_type'].shift(1)

        # Fill first pitch of each game
        if 'game_pk' in df.columns:
            game_starts = df['game_pk'] != df['game_pk'].shift(1)
            df.loc[game_starts, 'prev_pitch_type'] = 'NONE'
        else:
            df['prev_pitch_type'].fillna('NONE', inplace=True)

        return df

    def train(self, df: pd.DataFrame) -> Dict:
        """
        Train the pitch prediction model

        Args:
            df: DataFrame with pitch data

        Returns:
            Dictionary with training metrics
        """
        if df.empty:
            raise ValueError("Cannot train on empty dataset")

        print(f"Training model on {len(df)} pitches...")

        # Prepare features
        df = self.prepare_features(df)

        # Remove rows with missing target
        df = df.dropna(subset=['pitch_type'])

        # Filter out rare pitch types (need at least 5 examples)
        pitch_counts = df['pitch_type'].value_counts()
        valid_pitches = pitch_counts[pitch_counts >= 5].index
        df = df[df['pitch_type'].isin(valid_pitches)]

        if df.empty:
            raise ValueError("No valid pitch data after filtering")

        # Define features to use
        self.feature_columns = [
            'balls', 'strikes', 'outs',
            'is_ahead', 'is_behind', 'is_even',
            'two_strikes', 'three_balls', 'full_count',
            'batter_is_right', 'runners_on',
            'inning', 'late_inning', 'early_inning'
        ]

        # Add previous pitch type (one-hot encoded)
        prev_pitch_dummies = pd.get_dummies(df['prev_pitch_type'], prefix='prev')
        df = pd.concat([df, prev_pitch_dummies], axis=1)
        self.feature_columns.extend(prev_pitch_dummies.columns.tolist())

        # Prepare X and y
        X = df[self.feature_columns].fillna(0)
        y = df['pitch_type']

        # Encode target
        y_encoded = self.label_encoder.fit_transform(y)
        self.pitch_types = self.label_encoder.classes_.tolist()

        # Train model
        self.model.fit(X, y_encoded)
        self.is_trained = True

        # Calculate training accuracy
        train_accuracy = self.model.score(X, y_encoded)

        print(f"Model trained successfully!")
        print(f"Training accuracy: {train_accuracy:.3f}")
        print(f"Pitch types: {self.pitch_types}")

        return {
            'accuracy': train_accuracy,
            'n_samples': len(df),
            'pitch_types': self.pitch_types,
            'n_features': len(self.feature_columns)
        }

    def predict(self, context: Dict) -> Dict[str, float]:
        """
        Predict next pitch type probabilities

        Args:
            context: Dictionary with game context
                - balls: int
                - strikes: int
                - outs: int
                - batter_side: str ('L' or 'R')
                - runners_on: bool
                - inning: int
                - prev_pitch_type: str (optional)

        Returns:
            Dictionary mapping pitch types to probabilities
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet")

        # Create feature vector
        features = {
            'balls': context.get('balls', 0),
            'strikes': context.get('strikes', 0),
            'outs': context.get('outs', 0),
            'batter_is_right': 1 if context.get('batter_side', 'R') == 'R' else 0,
            'runners_on': 1 if context.get('runners_on', False) else 0,
            'inning': context.get('inning', 1),
        }

        # Calculate derived features
        features['is_ahead'] = 1 if (features['balls'] < features['strikes']) else 0
        features['is_behind'] = 1 if (features['balls'] > features['strikes']) else 0
        features['is_even'] = 1 if (features['balls'] == features['strikes']) else 0
        features['two_strikes'] = 1 if features['strikes'] == 2 else 0
        features['three_balls'] = 1 if features['balls'] == 3 else 0
        features['full_count'] = 1 if (features['balls'] == 3 and features['strikes'] == 2) else 0
        features['late_inning'] = 1 if features['inning'] >= 7 else 0
        features['early_inning'] = 1 if features['inning'] <= 3 else 0

        # Handle previous pitch type
        prev_pitch = context.get('prev_pitch_type', 'NONE')

        # Create feature DataFrame
        feature_dict = {col: 0 for col in self.feature_columns}
        feature_dict.update(features)

        # Set previous pitch one-hot
        prev_col = f'prev_{prev_pitch}'
        if prev_col in self.feature_columns:
            feature_dict[prev_col] = 1

        X = pd.DataFrame([feature_dict])[self.feature_columns]

        # Predict probabilities
        probabilities = self.model.predict_proba(X)[0]

        # Create result dictionary
        result = {
            pitch_type: float(prob)
            for pitch_type, prob in zip(self.pitch_types, probabilities)
        }

        # Sort by probability
        result = dict(sorted(result.items(), key=lambda x: x[1], reverse=True))

        return result

    def get_pitcher_summary(self, df: pd.DataFrame) -> Dict:
        """
        Generate summary statistics for a pitcher

        Args:
            df: DataFrame with pitch data

        Returns:
            Dictionary with pitcher summary stats
        """
        if df.empty:
            return {}

        # Pitch type distribution
        pitch_counts = df['pitch_type'].value_counts()
        total_pitches = len(df)

        repertoire = {
            pitch_type: {
                'count': int(count),
                'percentage': float(count / total_pitches * 100),
                'avg_speed': float(df[df['pitch_type'] == pitch_type]['start_speed'].mean())
                if 'start_speed' in df.columns else None
            }
            for pitch_type, count in pitch_counts.items()
        }

        # Overall stats
        summary = {
            'total_pitches': total_pitches,
            'repertoire': repertoire,
            'unique_pitch_types': len(pitch_counts),
            'games': df['game_pk'].nunique() if 'game_pk' in df.columns else 1,
            'avg_speed': float(df['start_speed'].mean()) if 'start_speed' in df.columns else None
        }

        return summary

    def save(self, path: str):
        """Save model to disk"""
        model_data = {
            'model': self.model,
            'label_encoder': self.label_encoder,
            'feature_columns': self.feature_columns,
            'pitch_types': self.pitch_types,
            'is_trained': self.is_trained
        }
        joblib.dump(model_data, path)
        print(f"Model saved to {path}")

    def load(self, path: str):
        """Load model from disk"""
        model_data = joblib.load(path)
        self.model = model_data['model']
        self.label_encoder = model_data['label_encoder']
        self.feature_columns = model_data['feature_columns']
        self.pitch_types = model_data['pitch_types']
        self.is_trained = model_data['is_trained']
        print(f"Model loaded from {path}")
