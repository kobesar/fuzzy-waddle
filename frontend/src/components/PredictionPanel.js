/**
 * PredictionPanel Component
 * Allows users to set game context and see pitch predictions
 */

import React, { useState } from 'react';
import { predictPitch } from '../api';
import PredictionChart from './PredictionChart';
import './PredictionPanel.css';

function PredictionPanel({ pitcher }) {
  const [context, setContext] = useState({
    balls: 0,
    strikes: 0,
    outs: 0,
    batter_side: 'R',
    runners_on: false,
    inning: 1,
    prev_pitch_type: null,
  });

  const [prediction, setPrediction] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleContextChange = (field, value) => {
    setContext((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handlePredict = async () => {
    setIsLoading(true);
    setError('');

    try {
      const result = await predictPitch(pitcher.id, context);
      setPrediction(result);
    } catch (err) {
      setError('Prediction failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setIsLoading(false);
    }
  };

  const presetScenarios = [
    { name: '0-0 Count', balls: 0, strikes: 0, outs: 0 },
    { name: '3-2 Full Count', balls: 3, strikes: 2, outs: 0 },
    { name: '0-2 Two Strikes', balls: 0, strikes: 2, outs: 0 },
    { name: '3-0 Three Balls', balls: 3, strikes: 0, outs: 0 },
  ];

  const applyPreset = (preset) => {
    setContext((prev) => ({
      ...prev,
      balls: preset.balls,
      strikes: preset.strikes,
      outs: preset.outs,
    }));
  };

  return (
    <div className="prediction-panel">
      <h2>Pitch Prediction</h2>

      {/* Preset Scenarios */}
      <div className="preset-scenarios">
        <h4>Quick Scenarios:</h4>
        <div className="preset-buttons">
          {presetScenarios.map((preset) => (
            <button
              key={preset.name}
              className="btn btn-secondary preset-btn"
              onClick={() => applyPreset(preset)}
            >
              {preset.name}
            </button>
          ))}
        </div>
      </div>

      {/* Context Controls */}
      <div className="context-controls">
        <h4>Game Context:</h4>

        {/* Count Display */}
        <div className="count-display">
          <div className="count-box">
            <span className="count-label">Balls</span>
            <span className="count-value">{context.balls}</span>
          </div>
          <div className="count-separator">-</div>
          <div className="count-box">
            <span className="count-label">Strikes</span>
            <span className="count-value">{context.strikes}</span>
          </div>
        </div>

        {/* Count Controls */}
        <div className="control-group">
          <label>Balls: {context.balls}</label>
          <input
            type="range"
            min="0"
            max="3"
            value={context.balls}
            onChange={(e) => handleContextChange('balls', parseInt(e.target.value))}
          />
        </div>

        <div className="control-group">
          <label>Strikes: {context.strikes}</label>
          <input
            type="range"
            min="0"
            max="2"
            value={context.strikes}
            onChange={(e) => handleContextChange('strikes', parseInt(e.target.value))}
          />
        </div>

        <div className="control-group">
          <label>Outs: {context.outs}</label>
          <input
            type="range"
            min="0"
            max="2"
            value={context.outs}
            onChange={(e) => handleContextChange('outs', parseInt(e.target.value))}
          />
        </div>

        <div className="control-group">
          <label>Inning: {context.inning}</label>
          <input
            type="range"
            min="1"
            max="9"
            value={context.inning}
            onChange={(e) => handleContextChange('inning', parseInt(e.target.value))}
          />
        </div>

        <div className="control-group">
          <label>Batter Side:</label>
          <div className="radio-group">
            <label>
              <input
                type="radio"
                name="batter_side"
                value="R"
                checked={context.batter_side === 'R'}
                onChange={(e) => handleContextChange('batter_side', e.target.value)}
              />
              Right
            </label>
            <label>
              <input
                type="radio"
                name="batter_side"
                value="L"
                checked={context.batter_side === 'L'}
                onChange={(e) => handleContextChange('batter_side', e.target.value)}
              />
              Left
            </label>
          </div>
        </div>

        <div className="control-group">
          <label>
            <input
              type="checkbox"
              checked={context.runners_on}
              onChange={(e) => handleContextChange('runners_on', e.target.checked)}
            />
            Runners on Base
          </label>
        </div>
      </div>

      {/* Predict Button */}
      <button
        className="btn btn-primary predict-button"
        onClick={handlePredict}
        disabled={isLoading}
      >
        {isLoading ? (
          <>
            <span className="loading-spinner"></span>
            Predicting...
          </>
        ) : (
          'Predict Next Pitch'
        )}
      </button>

      {error && <div className="error-message">{error}</div>}

      {/* Prediction Results */}
      {prediction && (
        <div className="prediction-results">
          <h4>Predicted Pitch Probabilities:</h4>
          <PredictionChart probabilities={prediction.probabilities} />

          <div className="probability-list">
            {Object.entries(prediction.probabilities)
              .sort((a, b) => b[1] - a[1])
              .map(([pitchType, probability]) => (
                <div key={pitchType} className="probability-item">
                  <span className="pitch-type">{pitchType}</span>
                  <div className="probability-bar-container">
                    <div
                      className="probability-bar"
                      style={{ width: `${probability * 100}%` }}
                    ></div>
                  </div>
                  <span className="probability-value">
                    {(probability * 100).toFixed(1)}%
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default PredictionPanel;
