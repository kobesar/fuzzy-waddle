/**
 * PitcherSearch Component
 * Autocomplete search field for finding pitchers
 */

import React, { useState, useEffect } from 'react';
import { searchPitchers } from '../api';
import './PitcherSearch.css';

function PitcherSearch({ onSelect }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);

  useEffect(() => {
    const delaySearch = setTimeout(() => {
      if (query.length >= 2) {
        handleSearch(query);
      } else {
        setResults([]);
        setShowDropdown(false);
      }
    }, 300); // Debounce search

    return () => clearTimeout(delaySearch);
  }, [query]);

  const handleSearch = async (searchQuery) => {
    setIsLoading(true);
    try {
      const pitchers = await searchPitchers(searchQuery);
      setResults(pitchers);
      setShowDropdown(pitchers.length > 0);
    } catch (error) {
      console.error('Search error:', error);
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectPitcher = (pitcher) => {
    setQuery(pitcher.name);
    setShowDropdown(false);
    onSelect(pitcher);
  };

  return (
    <div className="pitcher-search">
      <div className="search-container">
        <input
          type="text"
          className="search-input"
          placeholder="Search for a pitcher (e.g., Gerrit Cole, Sandy Alcantara)..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => query.length >= 2 && results.length > 0 && setShowDropdown(true)}
        />
        {isLoading && (
          <div className="search-loading">
            <div className="loading-spinner"></div>
          </div>
        )}
      </div>

      {showDropdown && (
        <div className="search-dropdown">
          {results.map((pitcher) => (
            <div
              key={pitcher.id}
              className="search-result-item"
              onClick={() => handleSelectPitcher(pitcher)}
            >
              <div className="pitcher-name">{pitcher.name}</div>
              <div className="pitcher-team">{pitcher.team}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default PitcherSearch;
