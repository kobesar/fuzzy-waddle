/**
 * PredictionChart Component
 * Displays prediction probabilities as a radial/polar chart
 */

import React from 'react';
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';

function PredictionChart({ probabilities }) {
  // Transform probabilities for radar chart
  const data = Object.entries(probabilities).map(([pitchType, probability]) => ({
    pitch: pitchType,
    probability: parseFloat((probability * 100).toFixed(1)),
  }));

  return (
    <div style={{ width: '100%', height: 350, marginTop: '1rem' }}>
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data}>
          <PolarGrid />
          <PolarAngleAxis dataKey="pitch" />
          <PolarRadiusAxis angle={90} domain={[0, 100]} />
          <Radar
            name="Probability"
            dataKey="probability"
            stroke="#667eea"
            fill="#667eea"
            fillOpacity={0.6}
          />
          <Tooltip formatter={(value) => `${value}%`} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default PredictionChart;
