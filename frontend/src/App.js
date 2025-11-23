/**
 * Main App Component
 * MLB Pitch Predictor Application
 */

import React, { useState } from 'react';
import './App.css';
import PitcherSearch from './components/PitcherSearch';
import PitcherDashboard from './components/PitcherDashboard';
import PredictionPanel from './components/PredictionPanel';

function App() {
  const [selectedPitcher, setSelectedPitcher] = useState(null);
  const [isModelTrained, setIsModelTrained] = useState(false);

  const handlePitcherSelect = (pitcher) => {
    setSelectedPitcher(pitcher);
    setIsModelTrained(false);
  };

  const handleModelTrained = () => {
    setIsModelTrained(true);
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>MLB Pitch Predictor</h1>
        <p>AI-Powered Pitch Sequence Prediction</p>
      </header>

      <main className="App-main">
        {/* Pitcher Search Section */}
        <section className="search-section">
          <PitcherSearch onSelect={handlePitcherSelect} />
        </section>

        {/* Dashboard and Prediction Section */}
        {selectedPitcher && (
          <div className="content-grid">
            <section className="dashboard-section">
              <PitcherDashboard
                pitcher={selectedPitcher}
                onModelTrained={handleModelTrained}
              />
            </section>

            {isModelTrained && (
              <section className="prediction-section">
                <PredictionPanel pitcher={selectedPitcher} />
              </section>
            )}
          </div>
        )}

        {!selectedPitcher && (
          <div className="welcome-message">
            <h2>Welcome to MLB Pitch Predictor</h2>
            <p>Search for a pitcher above to get started with pitch sequence predictions</p>
            <div className="features">
              <div className="feature">
                <h3>Real MLB Data</h3>
                <p>Uses live data from MLB Stats API</p>
              </div>
              <div className="feature">
                <h3>Machine Learning</h3>
                <p>Random Forest model trained on pitch sequences</p>
              </div>
              <div className="feature">
                <h3>Interactive Predictions</h3>
                <p>Adjust game context and see predictions update</p>
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="App-footer">
        <p>Data provided by MLB Stats API | Built with React & FastAPI</p>
      </footer>
    </div>
  );
}

export default App;
