/**
 * PitcherDashboard Component
 * Displays pitcher information and handles model training
 */

import React, { useState, useEffect } from 'react';
import { getPitcherInfo, trainModel, getModelStatus, getPitcherSummary } from '../api';
import RepertoireChart from './RepertoireChart';
import './PitcherDashboard.css';

function PitcherDashboard({ pitcher, onModelTrained }) {
  const [pitcherInfo, setPitcherInfo] = useState(null);
  const [modelStatus, setModelStatus] = useState(null);
  const [summary, setSummary] = useState(null);
  const [isTraining, setIsTraining] = useState(false);
  const [trainingMessage, setTrainingMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    loadPitcherData();
  }, [pitcher]);

  const loadPitcherData = async () => {
    try {
      // Load pitcher info
      const info = await getPitcherInfo(pitcher.id);
      setPitcherInfo(info);

      // Check model status
      const status = await getModelStatus(pitcher.id);
      setModelStatus(status);

      // If model is ready, load summary
      if (status.status === 'ready') {
        try {
          const summaryData = await getPitcherSummary(pitcher.id);
          setSummary(summaryData);
          onModelTrained();
        } catch (err) {
          // Summary not available, need to train
          console.log('Summary not available yet');
        }
      }
    } catch (err) {
      setError('Failed to load pitcher data');
      console.error(err);
    }
  };

  const handleTrainModel = async () => {
    setIsTraining(true);
    setError('');
    setTrainingMessage('Fetching pitch data from MLB Stats API...');

    try {
      const result = await trainModel(pitcher.id, null, 20);

      if (result.success) {
        setTrainingMessage(`Model trained successfully! ${result.metrics.n_samples} pitches analyzed.`);

        // Load summary data
        const summaryData = await getPitcherSummary(pitcher.id);
        setSummary(summaryData);

        // Update model status
        setModelStatus({ ...modelStatus, status: 'ready' });

        // Notify parent
        onModelTrained();
      } else {
        setError(result.message);
      }
    } catch (err) {
      setError('Training failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setIsTraining(false);
    }
  };

  if (!pitcherInfo) {
    return (
      <div className="pitcher-dashboard">
        <div className="loading">Loading pitcher information...</div>
      </div>
    );
  }

  return (
    <div className="pitcher-dashboard">
      <h2>Pitcher Dashboard</h2>

      {/* Pitcher Info Card */}
      <div className="pitcher-info-card">
        <h3>{pitcherInfo.name}</h3>
        <div className="info-grid">
          <div className="info-item">
            <span className="info-label">Team:</span>
            <span className="info-value">{pitcherInfo.team || 'N/A'}</span>
          </div>
          <div className="info-item">
            <span className="info-label">Throws:</span>
            <span className="info-value">{pitcherInfo.throws || 'N/A'}</span>
          </div>
          <div className="info-item">
            <span className="info-label">Age:</span>
            <span className="info-value">{pitcherInfo.age || 'N/A'}</span>
          </div>
          <div className="info-item">
            <span className="info-label">Height:</span>
            <span className="info-value">{pitcherInfo.height || 'N/A'}</span>
          </div>
        </div>
      </div>

      {/* Model Status */}
      <div className="model-status">
        <h4>Model Status</h4>
        {modelStatus?.status === 'ready' ? (
          <div className="status-ready">
            <span className="status-icon">✓</span>
            Model trained and ready
          </div>
        ) : (
          <div className="status-not-ready">
            <span className="status-icon">○</span>
            Model not trained
          </div>
        )}

        {modelStatus?.status !== 'ready' && (
          <button
            className="btn btn-primary train-button"
            onClick={handleTrainModel}
            disabled={isTraining}
          >
            {isTraining ? (
              <>
                <span className="loading-spinner"></span>
                Training Model...
              </>
            ) : (
              'Train Model'
            )}
          </button>
        )}

        {trainingMessage && (
          <div className="success-message">{trainingMessage}</div>
        )}

        {error && (
          <div className="error-message">{error}</div>
        )}
      </div>

      {/* Pitch Repertoire */}
      {summary && (
        <div className="repertoire-section">
          <h4>Pitch Repertoire</h4>
          <div className="repertoire-stats">
            <div className="stat">
              <span className="stat-label">Total Pitches:</span>
              <span className="stat-value">{summary.total_pitches}</span>
            </div>
            <div className="stat">
              <span className="stat-label">Games Analyzed:</span>
              <span className="stat-value">{summary.games}</span>
            </div>
            <div className="stat">
              <span className="stat-label">Pitch Types:</span>
              <span className="stat-value">{summary.unique_pitch_types}</span>
            </div>
          </div>

          <RepertoireChart repertoire={summary.repertoire} />

          <div className="pitch-types-list">
            {Object.entries(summary.repertoire)
              .sort((a, b) => b[1].percentage - a[1].percentage)
              .map(([pitchType, data]) => (
                <div key={pitchType} className="pitch-type-item">
                  <div className="pitch-type-header">
                    <span className="pitch-type-name">{pitchType}</span>
                    <span className="pitch-type-pct">{data.percentage.toFixed(1)}%</span>
                  </div>
                  <div className="pitch-type-details">
                    <span>Count: {data.count}</span>
                    {data.avg_speed && (
                      <span>Avg Speed: {data.avg_speed.toFixed(1)} mph</span>
                    )}
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default PitcherDashboard;
