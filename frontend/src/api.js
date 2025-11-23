/**
 * API Client for MLB Pitch Predictor Backend
 * Handles all HTTP requests to the FastAPI backend
 */

import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Search for pitchers by name
 */
export const searchPitchers = async (query, limit = 10) => {
  const response = await api.get('/api/pitchers/search', {
    params: { query, limit },
  });
  return response.data;
};

/**
 * Get pitcher information
 */
export const getPitcherInfo = async (pitcherId) => {
  const response = await api.get(`/api/pitchers/${pitcherId}`);
  return response.data;
};

/**
 * Train model for a specific pitcher
 */
export const trainModel = async (pitcherId, season = null, maxGames = 20) => {
  const response = await api.post('/api/model/train', {
    pitcher_id: pitcherId,
    season,
    max_games: maxGames,
  });
  return response.data;
};

/**
 * Get prediction for next pitch
 */
export const predictPitch = async (pitcherId, context) => {
  const response = await api.post(`/api/predict/${pitcherId}`, context);
  return response.data;
};

/**
 * Get pitcher summary statistics
 */
export const getPitcherSummary = async (pitcherId) => {
  const response = await api.get(`/api/pitchers/${pitcherId}/summary`);
  return response.data;
};

/**
 * Check model training status
 */
export const getModelStatus = async (pitcherId) => {
  const response = await api.get(`/api/model/status/${pitcherId}`);
  return response.data;
};

export default api;
