#!/usr/bin/env python3
"""
MLB Complete Pitch Sequence Data Collector (2015-2025)

This script collects comprehensive pitch-by-pitch data from the MLB Stats API for the
years 2015-2025, including regular season and postseason games. It gathers:
- All pitch details (type, location, speed, spin rate)
- Player statistics and expected statistics by pitch type
- Weather conditions
- Historical matchup data
- Sequence features

Usage:
    python mlb_complete_pitch_sequence_collector.py --start_year 2015 --end_year 2025

Author: MLB Analytics Team
Date: October 24, 2025
"""

import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
import json
import argparse
from typing import List, Dict, Any, Optional, Tuple
import warnings
import sys
import logging
from pathlib import Path
import os
from tqdm import tqdm

warnings.filterwarnings('ignore')

# Configuration
MLB_API_BASE_URL = "https://statsapi.mlb.com"
DEFAULT_DELAY = 1.0  # seconds between API requests
MAX_RETRIES = 3
CHECKPOINT_INTERVAL = 50  # Save progress every N games
EXPECTED_STATS_START_YEAR = 2015  # Statcast expected stats available from 2015

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mlb_collection.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class MLBCompleteDataCollector:
    """Complete MLB pitch sequence data collector with all enhanced features."""
    
    def __init__(self, delay: float = DEFAULT_DELAY):
        self.base_url = MLB_API_BASE_URL
        self.delay = delay
        self.session = requests.Session()
        self.total_api_calls = 0
        self.errors_log = []
        
        # Pitch type mappings for expected stats
        self.all_pitch_types = set()
        
    def safe_get(self, data: Dict[str, Any], *keys, default=None):
        """Safely navigate nested dictionaries."""
        for key in keys:
            if isinstance(data, dict) and key in data:
                data = data[key]
            else:
                return default
        return data
    
    def retry_request(self, url: str, params: Dict = None, max_retries: int = MAX_RETRIES) -> Optional[Dict]:
        """Make API request with retry logic and exponential backoff."""
        self.total_api_calls += 1
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                print(response.url)
                return response.json()
            except requests.exceptions.RequestException as e:
                wait_time = 2 ** attempt
                logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
                
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    error_msg = f"Failed to fetch {url} after {max_retries} attempts: {e}"
                    logger.error(error_msg)
                    self.errors_log.append(error_msg)
                    return None
    
    def get_schedule_multi_year(self, start_year: int, end_year: int, include_postseason: bool = True) -> List[Tuple[int, str, str]]:
        """
        Get schedule for multiple years including regular season and postseason.
        
        Returns:
            List of tuples: (game_pk, season, game_type)
        """
        all_games = []
        
        for year in range(start_year, end_year + 1):
            logger.info(f"Fetching schedule for {year}...")
            
            # Regular season (April - October)
            regular_games = self.get_schedule_for_period(
                f"{year}-04-01", 
                f"{year}-10-31", 
                str(year), 
                "R"  # Regular season
            )
            all_games.extend(regular_games)
            
            # Postseason (October - November)
            if include_postseason:
                postseason_games = self.get_schedule_for_period(
                    f"{year}-10-01", 
                    f"{year}-11-30", 
                    str(year), 
                    "P"  # Postseason
                )
                all_games.extend(postseason_games)
                
            time.sleep(self.delay)
        
        logger.info(f"Total games found across all years: {len(all_games)}")
        return all_games
    
    def get_schedule_for_period(self, start_date: str, end_date: str, season: str, game_type: str) -> List[Tuple[int, str, str]]:
        """Get schedule for a specific date range."""
        url = f"{self.base_url}/api/v1/schedule"
        params = {
            'startDate': start_date,
            'endDate': end_date,
            'sportId': 1
        }
        
        data = self.retry_request(url, params)
        if not data:
            return []
        
        games = []
        dates = self.safe_get(data, 'dates', default=[])
        
        for date_info in dates:
            date_games = self.safe_get(date_info, 'games', default=[])
            for game in date_games:
                # Only include completed games
                status_code = self.safe_get(game, 'status', 'statusCode')
                if status_code == 'F':  # Final
                    game_pk = self.safe_get(game, 'gamePk')
                    if game_pk:
                        games.append([game_pk, season, game_type])
        
        # Convert list format to match collect_season_data's expected format
        return [(game[0], game[1], game[2]) for game in games[1:2]]
    
    def get_game_feed(self, game_pk: int) -> Optional[Dict]:
        """Fetch live game feed for a specific game."""
        url = f"{self.base_url}/api/v1.1/game/{game_pk}/feed/live"
        return self.retry_request(url)
    
    def extract_weather_data(self, game_data: Dict) -> Dict:
        """Extract weather information from game data."""
        weather_info = {
            'temperature': None,
            'humidity': None,
            'weather_condition': None,
            'wind': None,
            'venue_type': None
        }
        
        try:
            # Weather data
            weather = self.safe_get(game_data, 'gameData', 'weather', default={})
            weather_info['temperature'] = weather.get('temp')
            weather_info['weather_condition'] = weather.get('condition')
            weather_info['wind'] = weather.get('wind')
            weather_info['humidity'] = weather.get('humidity')
            
            # Venue information for indoor/outdoor
            venue = self.safe_get(game_data, 'gameData', 'venue', default={})
            roof_type = venue.get('roofType')
            if roof_type:
                weather_info['venue_type'] = roof_type
            
        except Exception as e:
            logger.warning(f"Error extracting weather data: {e}")
        
        return weather_info
    
    def calculate_score_diff(self, game_data: Dict, inning_half: str) -> Tuple[int, int, int]:
        """Calculate score differential from batting team perspective."""
        home_score = self.safe_get(game_data, 'liveData', 'linescore', 'teams', 'home', 'runs', default=0)
        away_score = self.safe_get(game_data, 'liveData', 'linescore', 'teams', 'away', 'runs', default=0)
        
        # Score differential from batting team perspective
        if inning_half == 'bottom':  # Home team batting
            score_diff = home_score - away_score
        else:  # Away team batting
            score_diff = away_score - home_score
        
        return score_diff, home_score, away_score
    
    def get_runners(self, matchup: Dict) -> Dict[str, bool]:
        """Parse base runner situation."""
        return {
            'runner_1b': bool(self.safe_get(matchup, 'postOnFirst')),
            'runner_2b': bool(self.safe_get(matchup, 'postOnSecond')),
            'runner_3b': bool(self.safe_get(matchup, 'postOnThird'))
        }
    
    def extract_pitch_data(self, game_data: Dict, game_pk: int, season: str, game_type: str) -> List[Dict]:
        """
        Extract comprehensive pitch-by-pitch data from game feed.
        
        Args:
            game_data: Full game data JSON
            game_pk: Game primary key
            season: Season year
            game_type: 'R' for regular season, 'P' for postseason
            
        Returns:
            List of pitch records with all features
        """
        if not game_data:
            return []
        
        pitches = []
        game_date = self.safe_get(game_data, 'gameData', 'datetime', 'originalDate')
        
        # Extract weather data
        weather_info = self.extract_weather_data(game_data)
        
        plays = self.safe_get(game_data, 'liveData', 'plays', 'allPlays', default=[])
        
        for play_idx, play in enumerate(plays):
            try:
                about = self.safe_get(play, 'about', default={})
                matchup = self.safe_get(play, 'matchup', default={})
                
                # Get basic play info
                inning = self.safe_get(about, 'inning')
                inning_half = self.safe_get(about, 'halfInning')  # 'top' or 'bottom'
                at_bat_number = self.safe_get(about, 'atBatIndex', default=play_idx)
                
                # Get pitcher and batter info
                pitcher = self.safe_get(matchup, 'pitcher', default={})
                batter = self.safe_get(matchup, 'batter', default={})
                
                pitcher_id = self.safe_get(pitcher, 'id')
                pitcher_name = self.safe_get(pitcher, 'fullName')
                pitcher_hand = self.safe_get(matchup, 'pitchHand', 'code')
                
                batter_id = self.safe_get(batter, 'id')
                batter_name = self.safe_get(batter, 'fullName')
                batter_hand = self.safe_get(matchup, 'batSide', 'code')
                
                # Get runners situation
                runners = self.get_runners(matchup)
                
                # Calculate score differential
                score_diff, home_score, away_score = self.calculate_score_diff(game_data, inning_half)
                
                # Extract individual pitches
                play_events = self.safe_get(play, 'playEvents', default=[])
                
                for event in play_events:
                    if self.safe_get(event, 'isPitch'):
                        details = self.safe_get(event, 'details', default={})
                        pitch_data_raw = self.safe_get(event, 'pitchData', default={})
                        count = self.safe_get(event, 'count', default={})
                        coordinates = self.safe_get(pitch_data_raw, 'coordinates', default={})
                        
                        # Get pitch type and add to global set
                        pitch_type = self.safe_get(details, 'type', 'code')
                        if pitch_type:
                            self.all_pitch_types.add(pitch_type)
                        
                        pitch_record = {
                            # Essential game and pitch identifiers
                            'game_pk': game_pk,
                            'game_date': game_date,
                            'season': season,
                            'inning': inning,
                            'inning_half': inning_half,
                            'at_bat_number': at_bat_number,
                            'pitch_number': self.safe_get(event, 'pitchNumber', default=1),
                            
                            # Core participant IDs
                            'pitcher_id': pitcher_id,
                            'batter_id': batter_id,
                            
                            # Essential pitch data
                            'pitch_type': pitch_type,
                            'pitch_speed': self.safe_get(pitch_data_raw, 'startSpeed'),
                            'spin_rate': self.safe_get(pitch_data_raw, 'breaks', 'spinRate'),
                            
                            # Location
                            'pitch_x': self.safe_get(coordinates, 'pX'),
                            'pitch_z': self.safe_get(coordinates, 'pZ'),
                            'plate_x': self.safe_get(coordinates, 'x'),
                            'plate_z': self.safe_get(coordinates, 'y'),
                            
                            # Game situation
                            'balls': self.safe_get(count, 'balls', default=0),
                            'strikes': self.safe_get(count, 'strikes', default=0),
                            'outs': self.safe_get(count, 'outs', default=0),
                            'runner_1b': runners['runner_1b'],
                            'runner_2b': runners['runner_2b'],
                            'runner_3b': runners['runner_3b'],
                            'score_diff': score_diff,
                            
                            # Outcome
                            'pitch_call': self.safe_get(details, 'call', 'description')
                        }
                        
                        pitches.append(pitch_record)
                        
            except Exception as e:
                logger.warning(f"Error processing play in game {game_pk}: {e}")
                continue
        
        return pitches
    
    def get_player_stats(self, person_id: int, stats_type: str, group: str, season: str) -> Dict:
        """Fetch player seasonal stats."""
        url = f"{self.base_url}/api/v1/people/{person_id}/stats"
        params = {
            'stats': ['statSplits'],  # Pass as list
            'group': group,
            'season': season,
            'gameType': ['R', 'F', 'D', 'L', 'W', 'C']  # All game types including regular season and postseason
        }
        
        data = self.retry_request(url, params)

        if not data:
            return {}
        
        try:
            stats_data = self.safe_get(data, 'stats', default=[])
            if not stats_data:
                return {}
            
            # Get first stats group
            splits = self.safe_get(stats_data[0], 'splits', default=[])
            if not splits:
                return {}
            
            return self.safe_get(splits[0], 'stat', default={})
        except Exception as e:
            logger.warning(f"Error parsing player stats for {person_id}: {e}")
            return {}
    
    def get_expected_stats_by_pitch_type(self, person_id: int, group: str, season: str) -> Dict[str, Dict]:
        """
        Get expected statistics grouped by pitch type.
        
        Returns:
            Dict: {pitch_type: {xBA: X, xSLG: Y, xWOBA: Z}}
        """
        # Only try to get expected stats for 2015+ (Statcast era)
        if int(season) < EXPECTED_STATS_START_YEAR:
            return {}
        
        url = f"{self.base_url}/api/v1/people/{person_id}/stats/grouped"
        params = {
            'stats': 'EXPECTED_STATISTICS',
            'group': group,
            'season': season,
            'groupBy': 'pitch_type'
        }
        
        data = self.retry_request(url, params)
        if not data:
            return {}
        
        return self.parse_expected_stats_response(data)
    
    def parse_expected_stats_response(self, response_json: Dict) -> Dict[str, Dict]:
        """
        Parse the expected statistics grouped response.
        
        Returns:
            Dict: {pitch_type: {xBA: X, xSLG: Y, xWOBA: Z}}
        """
        expected_stats = {}
        
        try:
            stats = response_json.get('stats', [])
            if not stats:
                return expected_stats
                
            splits = stats[0].get('splits', [])
            
            for split in splits:
                # The pitch type might be in different locations depending on API response
                pitch_type = None
                
                # Try different possible locations for pitch type
                if 'pitch' in split:
                    pitch_type = split['pitch'].get('code')
                elif 'pitchType' in split:
                    pitch_type = split['pitchType'].get('code')
                elif 'group' in split:
                    pitch_type = split['group'].get('displayName')
                
                if pitch_type:
                    stat = split.get('stat', {})
                    expected_stats[pitch_type] = {
                        'xBA': stat.get('expectedBattingAverage'),
                        'xSLG': stat.get('expectedSluggingPct'), 
                        'xWOBA': stat.get('expectedWeightedOnbaseAvg')
                    }
                    
        except Exception as e:
            logger.warning(f"Error parsing expected stats: {e}")
        
        return expected_stats
    
    def get_matchup_history(self, person_id: int, season: str, group: str = 'pitching') -> Dict:
        """Fetch VS_PLAYER historical matchup data."""
        url = f"{self.base_url}/api/v1/people/{person_id}/stats/grouped"
        params = {
            'stats': 'VS_PLAYER_5Y',
            'group': group,
            'season': season
        }
        
        data = self.retry_request(url, params)
        if not data:
            return {}
        
        # This is complex to parse - simplified version for now
        return self.safe_get(data, 'stats', default={})
    
    def enrich_pitch_data(self, pitch_df: pd.DataFrame, season: str) -> pd.DataFrame:
        """
        Enrich pitch data with player statistics and expected stats by pitch type.
        """
        if pitch_df.empty:
            return pitch_df
            
        logger.info("Getting unique players...")
        
        # Get unique players to minimize API calls
        unique_pitchers = pitch_df['pitcher_id'].dropna().unique()
        unique_batters = pitch_df['batter_id'].dropna().unique()
        
        logger.info(f"Found {len(unique_pitchers)} unique pitchers and {len(unique_batters)} unique batters")
        
        # Collect pitcher stats and expected stats
        pitcher_stats = {}
        pitcher_expected = {}
        
        logger.info("Collecting pitcher statistics and expected stats...")
        for i, pitcher_id in enumerate(unique_pitchers):
            if pd.isna(pitcher_id):
                continue
            
            if i % 10 == 0:
                logger.info(f"Processing pitcher {i+1}/{len(unique_pitchers)}")
            
            # Regular stats
            stats = self.get_player_stats(int(pitcher_id), 'pitching', 'pitching', season)
            pitcher_stats[pitcher_id] = {
                'pitcher_era': stats.get('era'),
                'pitcher_whip': stats.get('whip'),
                'pitcher_k9': stats.get('strikeOutsPer9Inn'),
                'pitcher_bb9': stats.get('baseOnBallsPer9Inn'),
                'pitcher_innings': stats.get('inningsPitched'),
                'pitcher_wins': stats.get('wins'),
                'pitcher_losses': stats.get('losses'),
                'pitcher_saves': stats.get('saves')
            }
            
            # Expected stats by pitch type
            expected = self.get_expected_stats_by_pitch_type(int(pitcher_id), 'pitching', season)
            pitcher_expected[pitcher_id] = expected
            
            time.sleep(self.delay / 2)  # Reduced delay for stats
        
        # Collect batter stats and expected stats
        batter_stats = {}
        batter_expected = {}
        
        logger.info("Collecting batter statistics and expected stats...")
        for i, batter_id in enumerate(unique_batters):
            if pd.isna(batter_id):
                continue
                
            if i % 10 == 0:
                logger.info(f"Processing batter {i+1}/{len(unique_batters)}")
            
            # Regular stats
            stats = self.get_player_stats(int(batter_id), 'hitting', 'hitting', season)
            batter_stats[batter_id] = {
                'batter_avg': stats.get('avg'),
                'batter_obp': stats.get('obp'),
                'batter_slg': stats.get('slg'),
                'batter_ops': stats.get('ops'),
                'batter_hr': stats.get('homeRuns'),
                'batter_rbi': stats.get('rbi'),
                'batter_sb': stats.get('stolenBases'),
                'batter_bb_pct': stats.get('baseOnBallsPer9Inn')
            }
            
            # Expected stats vs pitch types
            expected = self.get_expected_stats_by_pitch_type(int(batter_id), 'hitting', season)
            batter_expected[batter_id] = expected
            
            time.sleep(self.delay / 2)
        
        # Merge regular stats back to DataFrame
        logger.info("Merging regular statistics with pitch data...")
        
        # Add pitcher stats
        for col in ['pitcher_era', 'pitcher_whip', 'pitcher_k9', 'pitcher_bb9', 
                   'pitcher_innings', 'pitcher_wins', 'pitcher_losses', 'pitcher_saves']:
            pitch_df[col] = pitch_df['pitcher_id'].map(lambda x: pitcher_stats.get(x, {}).get(col))
        
        # Add batter stats
        for col in ['batter_avg', 'batter_obp', 'batter_slg', 'batter_ops', 
                   'batter_hr', 'batter_rbi', 'batter_sb', 'batter_bb_pct']:
            pitch_df[col] = pitch_df['batter_id'].map(lambda x: batter_stats.get(x, {}).get(col))
        
        # Add expected stats dynamically for each pitch type
        logger.info("Adding expected statistics by pitch type...")
        
        # Create columns for pitcher expected stats
        for pitch_type in sorted(self.all_pitch_types):
            if pitch_type:  # Skip None values
                # Pitcher expected stats
                pitch_df[f'pitcher_xBA_{pitch_type}'] = pitch_df['pitcher_id'].map(
                    lambda x: pitcher_expected.get(x, {}).get(pitch_type, {}).get('xBA')
                )
                pitch_df[f'pitcher_xSLG_{pitch_type}'] = pitch_df['pitcher_id'].map(
                    lambda x: pitcher_expected.get(x, {}).get(pitch_type, {}).get('xSLG')
                )
                pitch_df[f'pitcher_xWOBA_{pitch_type}'] = pitch_df['pitcher_id'].map(
                    lambda x: pitcher_expected.get(x, {}).get(pitch_type, {}).get('xWOBA')
                )
                
                # Batter expected stats vs pitch type
                pitch_df[f'batter_xBA_vs_{pitch_type}'] = pitch_df['batter_id'].map(
                    lambda x: batter_expected.get(x, {}).get(pitch_type, {}).get('xBA')
                )
                pitch_df[f'batter_xSLG_vs_{pitch_type}'] = pitch_df['batter_id'].map(
                    lambda x: batter_expected.get(x, {}).get(pitch_type, {}).get('xSLG')
                )
                pitch_df[f'batter_xWOBA_vs_{pitch_type}'] = pitch_df['batter_id'].map(
                    lambda x: batter_expected.get(x, {}).get(pitch_type, {}).get('xWOBA')
                )
        
        return pitch_df
    
    def create_sequence_features(self, pitch_df: pd.DataFrame) -> pd.DataFrame:
        """Create sequence features for pitch data."""
        if pitch_df.empty:
            return pitch_df
            
        # Sort by game, inning, at_bat_number, pitch_number
        pitch_df = pitch_df.sort_values([
            'game_pk', 'inning', 'at_bat_number', 'pitch_number'
        ]).reset_index(drop=True)
        
        logger.info("Creating sequence features...")
        
        # Create lagged features within each at-bat
        pitch_df['prev_pitch_type'] = pitch_df.groupby(['game_pk', 'at_bat_number'])['pitch_type'].shift(1)
        pitch_df['prev_2_pitch_type'] = pitch_df.groupby(['game_pk', 'at_bat_number'])['pitch_type'].shift(2)
        pitch_df['prev_3_pitch_type'] = pitch_df.groupby(['game_pk', 'at_bat_number'])['pitch_type'].shift(3)
        
        # Previous pitch outcomes
        pitch_df['prev_pitch_call'] = pitch_df.groupby(['game_pk', 'at_bat_number'])['pitch_call'].shift(1)
        
        # Count situation as string
        pitch_df['count_situation'] = pitch_df.apply(
            lambda row: f"{int(row['balls'])}-{int(row['strikes'])}" 
            if pd.notna(row['balls']) and pd.notna(row['strikes']) else None, 
            axis=1
        )
        
        # Pitch number in at-bat
        pitch_df['pitch_in_ab'] = pitch_df.groupby(['game_pk', 'at_bat_number']).cumcount() + 1
        
        # Create pitcher pitch usage within game
        pitch_df['game_pitch_count'] = pitch_df.groupby(['game_pk', 'pitcher_id']).cumcount() + 1
        
        # Running pitch type percentage for pitcher in game
        for pitch_type in sorted(self.all_pitch_types):
            if pitch_type:  # Skip None/NaN values
                pitch_df[f'pitcher_game_{pitch_type}_pct'] = (
                    pitch_df.groupby(['game_pk', 'pitcher_id'])['pitch_type']
                    .apply(lambda x: (x.shift(1) == pitch_type).cumsum() / np.maximum(1, np.arange(len(x))))
                )
        
        return pitch_df
    
    def save_checkpoint(self, data: List[Dict], checkpoint_file: str):
        """Save intermediate results."""
        if data:
            df = pd.DataFrame(data)
            df.to_csv(checkpoint_file, index=False)
            logger.info(f"Checkpoint saved to {checkpoint_file} with {len(data)} pitches")
    
    def collect_season_data(self, season: str, output_dir: str, game_type_filter: str = None) -> pd.DataFrame:
        """
        Collect data for a specific season.
        
        Args:
            season: Season year (e.g., "2024")
            output_dir: Directory to save outputs
            game_type_filter: 'R' for regular season, 'P' for postseason, None for both
            
        Returns:
            DataFrame with all pitch data for the season
        """
        logger.info(f"Starting data collection for {season} season")
        
        # Just get games for the specified season
        start_date = f"{season}-03-20"  # Approximate season start
        end_date = f"{season}-11-15"    # Latest possible end (including postseason)
        
        # Get schedule for the specified period
        games = self.get_schedule_for_period(start_date, end_date, season, game_type_filter or 'R')
        
        logger.info(f"Found {len(games)} games to process")
        
        if not games:
            logger.warning(f"No games found for season {season}")
            return pd.DataFrame()
        
        # Collect pitch data
        all_pitches = []
        checkpoint_file = f"{output_dir}/checkpoint_{season}_{game_type_filter or 'all'}.csv"
        
        # Use tqdm for progress bar
        for i, (game_pk, season_year, game_type) in enumerate(tqdm(games, desc=f"Processing {season}")):
            try:
                game_data = self.get_game_feed(game_pk)
                if game_data:
                    pitches = self.extract_pitch_data(game_data, game_pk, season_year, game_type)
                    all_pitches.extend(pitches)
                    
                    if i % 50 == 0:  # Log progress every 50 games
                        logger.info(f"Processed {i+1}/{len(games)} games, collected {len(all_pitches)} total pitches")
                else:
                    logger.warning(f"Failed to get game data for {game_pk}")
                
                # Save checkpoint periodically
                if (i + 1) % CHECKPOINT_INTERVAL == 0:
                    self.save_checkpoint(all_pitches, checkpoint_file)
                
                time.sleep(self.delay)
                
            except Exception as e:
                error_msg = f"Error processing game {game_pk}: {e}"
                logger.error(error_msg)
                self.errors_log.append(error_msg)
                continue
        
        if not all_pitches:
            logger.warning(f"No pitch data collected for season {season}")
            return pd.DataFrame()
        
        # Convert to DataFrame
        logger.info(f"Collected {len(all_pitches)} total pitches for {season}")
        df = pd.DataFrame(all_pitches)
        
        # Just create sequence features for pitch types
        logger.info("Creating sequence features...")
        df = self.create_sequence_features(df)
        
        # Don't enrich with player stats yet - will do that separately
        logger.info("Skipping player statistics for initial collection")
        
        # Clean up checkpoint file
        if os.path.exists(checkpoint_file):
            os.remove(checkpoint_file)
            logger.info("Checkpoint file cleaned up")
        
        return df
    
    def collect_all_seasons(self, start_year: int = 2015, end_year: int = 2025, output_dir: str = 'pitch_data'):
        """
        Collect data for all seasons from start_year to end_year.
        Saves each season to separate file for manageability.
        """
        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        collection_start_time = time.time()
        total_pitches = 0
        
        for year in range(start_year, end_year + 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"COLLECTING SEASON {year}")
            logger.info(f"{'='*60}")
            
            season_start_time = time.time()
            
            try:
                # Collect regular season
                logger.info(f"Collecting regular season data for {year}...")
                regular_df = self.collect_season_data(str(year), output_dir, 'R')
                
                if not regular_df.empty:
                    regular_output = f"{output_dir}/pitch_data_{year}_regular.csv"
                    regular_df.to_csv(regular_output, index=False)
                    logger.info(f"Regular season data saved to {regular_output} ({len(regular_df):,} pitches)")
                    total_pitches += len(regular_df)
                
                # Collect postseason
                logger.info(f"Collecting postseason data for {year}...")
                postseason_df = self.collect_season_data(str(year), output_dir, 'P')
                
                if not postseason_df.empty:
                    postseason_output = f"{output_dir}/pitch_data_{year}_postseason.csv"
                    postseason_df.to_csv(postseason_output, index=False)
                    logger.info(f"Postseason data saved to {postseason_output} ({len(postseason_df):,} pitches)")
                    total_pitches += len(postseason_df)
                
                season_time = time.time() - season_start_time
                logger.info(f"Season {year} completed in {season_time:.1f} seconds")
                
            except Exception as e:
                error_msg = f"Error collecting data for season {year}: {e}"
                logger.error(error_msg)
                self.errors_log.append(error_msg)
                continue
        
        # Log final statistics
        total_time = time.time() - collection_start_time
        logger.info(f"\n{'='*60}")
        logger.info("COLLECTION COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"Total pitches collected: {total_pitches:,}")
        logger.info(f"Total time: {total_time:.1f} seconds")
        logger.info(f"Total API calls: {self.total_api_calls:,}")
        logger.info(f"Errors encountered: {len(self.errors_log)}")
        
        # Save error log
        if self.errors_log:
            error_file = f"{output_dir}/collection_errors.log"
            with open(error_file, 'w') as f:
                f.write("MLB Data Collection Errors\n")
                f.write("=" * 40 + "\n")
                for error in self.errors_log:
                    f.write(f"{error}\n")
            logger.info(f"Error log saved to {error_file}")
    
    def combine_all_seasons(self, output_dir: str, combined_filename: str = "complete_pitch_data_2022_2025.csv"):
        """Combine all seasonal CSV files into one master dataset."""
        logger.info("Combining all seasonal data into master dataset (2022-2025)...")
        
        csv_files = []
        for file in os.listdir(output_dir):
            if file.startswith('pitch_data_') and file.endswith('.csv'):
                csv_files.append(os.path.join(output_dir, file))
        
        if not csv_files:
            logger.warning("No CSV files found to combine")
            return
        
        logger.info(f"Found {len(csv_files)} files to combine")
        
        # Read and combine files, ensuring consistent columns
        dataframes = []
        for f in csv_files:
            df = pd.read_csv(f)
            # Only include files from 2022 onwards
            if int(df['season'].iloc[0]) >= 2022:
                dataframes.append(df)
        
        if not dataframes:
            logger.warning("No valid data files found from 2022 onwards")
            return
            
        # Get the union of all columns
        all_columns = set()
        for df in dataframes:
            all_columns.update(df.columns)
            
        # Ensure all dataframes have the same columns
        for i, df in enumerate(dataframes):
            missing_cols = all_columns - set(df.columns)
            for col in missing_cols:
                df[col] = None
            dataframes[i] = df[list(all_columns)]  # Reorder columns to match
            
        # Combine all processed dataframes
        combined_df = pd.concat(dataframes, ignore_index=True)
        
        # Save combined dataset
        combined_path = os.path.join(output_dir, combined_filename)
        combined_df.to_csv(combined_path, index=False)
        
        logger.info(f"Combined dataset saved to {combined_path}")
        logger.info(f"Total records: {len(combined_df):,}")
        logger.info(f"Date range: {combined_df['game_date'].min()} to {combined_df['game_date'].max()}")
        logger.info(f"Seasons: {sorted(combined_df['season'].unique())}")
        logger.info(f"Unique games: {combined_df['game_pk'].nunique():,}")
        logger.info(f"Unique pitchers: {combined_df['pitcher_id'].nunique():,}")
        logger.info(f"Unique batters: {combined_df['batter_id'].nunique():,}")
    
    def validate_dataset(self, file_path: str):
        """Check data quality and completeness."""
        logger.info(f"Validating dataset: {file_path}")
        
        df = pd.read_csv(file_path)
        
        logger.info(f"Dataset shape: {df.shape}")
        logger.info(f"Memory usage: {df.memory_usage(deep=True).sum() / 1024**2:.1f} MB")
        
        # Check for missing values
        missing_pct = (df.isnull().sum() / len(df) * 100).round(1)
        high_missing = missing_pct[missing_pct > 10]
        
        if len(high_missing) > 0:
            logger.warning("Columns with >10% missing values:")
            for col, pct in high_missing.items():
                logger.warning(f"  {col}: {pct}%")
        
        # Check pitch type distribution
        logger.info("Pitch type distribution:")
        pitch_counts = df['pitch_type'].value_counts()
        for pitch_type, count in pitch_counts.head(10).items():
            logger.info(f"  {pitch_type}: {count:,} ({count/len(df)*100:.1f}%)")


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='Collect comprehensive MLB pitch sequence data from 2022-2025')
    parser.add_argument('--start_year', type=int, default=2022,
                       help='Start year (default: 2022)')
    parser.add_argument('--end_year', type=int, default=2025,
                       help='End year (default: 2025)')
    parser.add_argument('--output_dir', type=str, default='pitch_data',
                       help='Output directory (default: pitch_data)')
    parser.add_argument('--delay', type=float, default=DEFAULT_DELAY,
                       help='Delay between API requests in seconds (default: 1.0)')
    parser.add_argument('--combine', action='store_true',
                       help='Combine all seasonal files into master dataset')
    parser.add_argument('--validate', type=str,
                       help='Validate a specific dataset file')
    
    args = parser.parse_args()
    
    # Validate years
    if args.start_year < 2022 or args.end_year > 2025:
        logger.error("Years must be between 2022 and 2025")
        sys.exit(1)
    
    if args.start_year > args.end_year:
        logger.error("Start year must be <= end year")
        sys.exit(1)
    
    # Create collector
    collector = MLBCompleteDataCollector(delay=args.delay)
    
    try:
        if args.validate:
            # Validate specific file
            collector.validate_dataset(args.validate)
        elif args.combine:
            # Combine existing files
            collector.combine_all_seasons(args.output_dir)
        else:
            # Collect data
            logger.info("Starting comprehensive MLB pitch sequence data collection")
            logger.info(f"Years: {args.start_year}-{args.end_year}")
            logger.info(f"Output directory: {args.output_dir}")
            logger.info(f"API delay: {args.delay} seconds")
            
            collector.collect_all_seasons(
                start_year=args.start_year,
                end_year=args.end_year,
                output_dir=args.output_dir
            )
            
            # Automatically combine all files
            logger.info("\nCombining all seasonal files...")
            collector.combine_all_seasons(args.output_dir)
            
            # Validate the combined dataset
            combined_file = os.path.join(args.output_dir, "complete_pitch_data_2022_2025.csv")
            if os.path.exists(combined_file):
                collector.validate_dataset(combined_file)
        
    except KeyboardInterrupt:
        logger.info("\nData collection interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\nError during data collection: {e}")
        sys.exit(1)

def test_single_day_collection():
    """Test data collection with a single day of games."""
    logger.info("Running single day test collection...")
    
    # Initialize collector with shorter delay for testing
    collector = MLBCompleteDataCollector(delay=0.5)
    output_dir = "test_data"
    test_date = "2025-03-26"  # Opening Day 2025
    
    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        test_output = f"{output_dir}/test_single_day_{test_date}.csv"
        
        # Collect test data
        df = collector.collect_season_data(
            season="2025",
            output_dir=output_dir,
            game_type_filter="R"  # Regular season only
        )
        
        if len(df) > 0:
            # Filter for specific date
            df = df[df['game_date'] == test_date]
            df.to_csv(test_output, index=False)
            
            logger.info("\nTest successful! Sample data summary:")
            logger.info(f"Total pitches: {len(df):,}")
            logger.info(f"Unique games: {df['game_pk'].nunique():,}")
            logger.info(f"Unique pitchers: {df['pitcher_id'].nunique():,}")
            logger.info(f"Unique batters: {df['batter_id'].nunique():,}")
            
            # Show pitch type distribution
            logger.info("\nPitch type distribution:")
            pitch_counts = df['pitch_type'].value_counts()
            for pitch_type, count in pitch_counts.head(5).items():
                logger.info(f"  {pitch_type}: {count:,} ({count/len(df)*100:.1f}%)")
            
            # Clean up test file
            if Path(test_output).exists():
                Path(test_output).unlink()
                logger.info(f"\nCleaned up test file: {test_output}")
            
            # Clean up test directory if empty
            if not os.listdir(output_dir):
                os.rmdir(output_dir)
                
            return True
        else:
            logger.error("Test failed: No data collected")
            return False
            
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        return False

if __name__ == "__main__":
    # Run test collection for a single day
    # test_single_day_collection()
    
    # For full data collection, uncomment:
    main()