/**
 * RepertoireChart Component
 * Displays pitcher's pitch repertoire as a bar chart
 */

import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

function RepertoireChart({ repertoire }) {
  // Transform repertoire data for recharts
  const data = Object.entries(repertoire)
    .map(([pitchType, info]) => ({
      name: pitchType,
      percentage: parseFloat(info.percentage.toFixed(1)),
      count: info.count,
    }))
    .sort((a, b) => b.percentage - a.percentage);

  return (
    <div style={{ width: '100%', height: 300, marginTop: '1rem' }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis label={{ value: 'Usage %', angle: -90, position: 'insideLeft' }} />
          <Tooltip
            formatter={(value, name) => {
              if (name === 'percentage') return `${value}%`;
              return value;
            }}
          />
          <Legend />
          <Bar dataKey="percentage" fill="#667eea" name="Usage %" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default RepertoireChart;
