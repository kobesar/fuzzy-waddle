#!/usr/bin/env python3
"""
MLB Pitch Sequence Data Collector

This script collects pitch-by-pitch data from the MLB Stats API to create a dataset
for predicting pitch sequences based on pitcher-batter combinations.

Usage:
    python mlb_pitch_sequence_collector.py --start_date 2024-04-01 --end_date 2024-04-30 --season 2024

Author: MLB Analytics Team
Date: October 24, 2025
"""

import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta, date
import json
import argparse
from typing import List, Dict, Any, Optional
import warnings
import sys
from pathlib import Path

warnings.filterwarnings('ignore')

# Configuration
MLB_API_BASE_URL = "https://statsapi.mlb.com"
DEFAULT_DELAY = 1.0  # seconds between API requests
MAX_RETRIES = 3
CHECKPOINT_INTERVAL = 100  # Save progress every N games


class MLBDataCollector:
    """Main class for collecting MLB pitch sequence data."""
    
    def __init__(self, delay: float = DEFAULT_DELAY):
        self.base_url = MLB_API_BASE_URL
        self.delay = delay
        self.session = requests.Session()
        
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
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                wait_time = 2 ** attempt
                print(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print(f"Failed to fetch {url} after {max_retries} attempts")
                    return None
    
    def get_schedule(self, start_date: str, end_date: str, sport_id: int = 1) -> List[int]:
        """
        Fetch game schedule for date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            sport_id: Sport ID (1 for MLB)
            
        Returns:
            List of game PKs
        """
        url = f"{self.base_url}/api/v1/schedule"
        params = {
            'startDate': start_date,
            'endDate': end_date,
            'sportId': sport_id
        }
        
        data = self.retry_request(url, params)
        if not data:
            return []
        
        game_pks = []
        dates = self.safe_get(data, 'dates', default=[])
        
        for date_info in dates:
            games = self.safe_get(date_info, 'games', default=[])
            for game in games:
                # Only include completed games
                status_code = self.safe_get(game, 'status', 'statusCode')
                if status_code == 'F':  # Final
                    game_pk = self.safe_get(game, 'gamePk')
                    if game_pk:
                        game_pks.append(game_pk)
        
        return game_pks
    
    def get_game_feed(self, game_pk: int) -> Optional[Dict]:
        """
        Fetch live game feed for a specific game.
        
        Args:
            game_pk: Unique game identifier
            
        Returns:
            Game data JSON or None if failed
        """
        url = f"{self.base_url}/api/v1.1/game/{game_pk}/feed/live"
        return self.retry_request(url)
    
    def calculate_score_diff(self, game_data: Dict) -> tuple:
        """Calculate score differential (batting_team - pitching_team)."""
        home_score = self.safe_get(game_data, 'liveData', 'linescore', 'teams', 'home', 'runs', default=0)
        away_score = self.safe_get(game_data, 'liveData', 'linescore', 'teams', 'away', 'runs', default=0)
        return home_score, away_score
    
    def get_runners(self, matchup: Dict) -> Dict[str, bool]:
        """Parse base runner situation."""
        return {
            'runner_1b': bool(self.safe_get(matchup, 'postOnFirst')),
            'runner_2b': bool(self.safe_get(matchup, 'postOnSecond')),
            'runner_3b': bool(self.safe_get(matchup, 'postOnThird'))
        }
    
    def extract_pitch_data(self, game_data: Dict, game_pk: int) -> List[Dict]:
        """
        Extract pitch-by-pitch data from game feed.
        
        Args:
            game_data: Full game data JSON
            game_pk: Game primary key
            
        Returns:
            List of pitch records
        """
        if not game_data:
            return []
        
        pitches = []
        game_date = self.safe_get(game_data, 'gameData', 'datetime', 'originalDate')
        home_score, away_score = self.calculate_score_diff(game_data)
        
        plays = self.safe_get(game_data, 'liveData', 'plays', 'allPlays', default=[])
        
        for play_idx, play in enumerate(plays):
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
            
            # Calculate score differential (batting team perspective)
            if inning_half == 'bottom':  # Home team batting
                score_diff = home_score - away_score
            else:  # Away team batting
                score_diff = away_score - home_score
            
            # Extract individual pitches
            play_events = self.safe_get(play, 'playEvents', default=[])
            
            for event in play_events:
                if self.safe_get(event, 'isPitch'):
                    details = self.safe_get(event, 'details', default={})
                    pitch_data_raw = self.safe_get(event, 'pitchData', default={})
                    count = self.safe_get(event, 'count', default={})
                    coordinates = self.safe_get(pitch_data_raw, 'coordinates', default={})
                    
                    pitch_record = {
                        # Game identifiers
                        'game_pk': game_pk,
                        'game_date': game_date,
                        'inning': inning,
                        'inning_half': inning_half,
                        'at_bat_number': at_bat_number,
                        
                        # Pitcher info
                        'pitcher_id': pitcher_id,
                        'pitcher_name': pitcher_name,
                        'pitcher_hand': pitcher_hand,
                        
                        # Batter info
                        'batter_id': batter_id,
                        'batter_name': batter_name,
                        'batter_hand': batter_hand,
                        
                        # Pitch details
                        'pitch_number': self.safe_get(event, 'pitchNumber', default=1),
                        'pitch_type': self.safe_get(details, 'type', 'code'),
                        'pitch_type_description': self.safe_get(details, 'type', 'description'),
                        
                        # Count
                        'balls': self.safe_get(count, 'balls', default=0),
                        'strikes': self.safe_get(count, 'strikes', default=0),
                        'outs': self.safe_get(count, 'outs', default=0),
                        
                        # Pitch metrics
                        'pitch_speed': self.safe_get(pitch_data_raw, 'startSpeed'),
                        'spin_rate': self.safe_get(pitch_data_raw, 'breaks', 'spinRate'),
                        
                        # Coordinates
                        'pitch_x': self.safe_get(coordinates, 'pX'),
                        'pitch_z': self.safe_get(coordinates, 'pZ'),
                        'plate_x': self.safe_get(coordinates, 'x'),
                        'plate_z': self.safe_get(coordinates, 'y'),
                        
                        # Outcome
                        'outcome': self.safe_get(details, 'description'),
                        'pitch_call': self.safe_get(details, 'call', 'description'),
                        
                        # Situation
                        'runner_1b': runners['runner_1b'],
                        'runner_2b': runners['runner_2b'],
                        'runner_3b': runners['runner_3b'],
                        'score_diff': score_diff,
                        'home_score': home_score,
                        'away_score': away_score,
                    }
                    
                    pitches.append(pitch_record)
        
        return pitches
    
    def get_player_stats(self, person_id: int, stats_type: str, group: str, season: str) -> Dict:
        """
        Fetch player seasonal stats.
        
        Args:
            person_id: Player ID
            stats_type: 'pitching' or 'hitting'
            group: 'pitching' or 'hitting'
            season: Season year
            
        Returns:
            Dictionary of player stats
        """
        url = f"{self.base_url}/api/v1/people/{person_id}/stats"
        params = {
            'stats': stats_type,
            'group': group,
            'season': season
        }
        
        data = self.retry_request(url, params)
        if not data:
            return {}
        
        stats_data = self.safe_get(data, 'stats', default=[])
        if not stats_data:
            return {}
        
        # Get first stats group
        splits = self.safe_get(stats_data[0], 'splits', default=[])
        if not splits:
            return {}
        
        return self.safe_get(splits[0], 'stat', default={})
    
    def get_matchup_history(self, person_id: int, season: str, group: str = 'pitching') -> Dict:
        """
        Fetch VS_PLAYER historical matchup data.
        
        Args:
            person_id: Player ID
            season: Season year
            group: 'pitching' or 'hitting'
            
        Returns:
            Dictionary of matchup stats
        """
        url = f"{self.base_url}/api/v1/people/{person_id}/stats/grouped"
        params = {
            'stats': 'VS_PLAYER_5Y',
            'group': group,
            'season': season
        }
        
        data = self.retry_request(url, params)
        if not data:
            return {}
        
        # Parse grouped stats (this is complex - simplified version)
        return self.safe_get(data, 'stats', default={})
    
    def enrich_pitch_data(self, pitch_df: pd.DataFrame, season: str) -> pd.DataFrame:
        """
        Enrich pitch data with player statistics.
        
        Args:
            pitch_df: DataFrame of pitch data
            season: Season year
            
        Returns:
            Enhanced DataFrame with player stats
        """
        print("Getting unique players...")
        
        # Get unique players to minimize API calls
        unique_pitchers = pitch_df['pitcher_id'].dropna().unique()
        unique_batters = pitch_df['batter_id'].dropna().unique()
        
        print(f"Found {len(unique_pitchers)} unique pitchers and {len(unique_batters)} unique batters")
        
        # Collect pitcher stats
        pitcher_stats = {}
        print("Collecting pitcher statistics...")
        for i, pitcher_id in enumerate(unique_pitchers):
            if pd.isna(pitcher_id):
                continue
            
            if i % 10 == 0:
                print(f"Processing pitcher {i+1}/{len(unique_pitchers)}")
            
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
            
            time.sleep(self.delay / 2)  # Reduced delay for stats
        
        # Collect batter stats
        batter_stats = {}
        print("Collecting batter statistics...")
        for i, batter_id in enumerate(unique_batters):
            if pd.isna(batter_id):
                continue
                
            if i % 10 == 0:
                print(f"Processing batter {i+1}/{len(unique_batters)}")
            
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
            
            time.sleep(self.delay / 2)
        
        # Merge stats back to DataFrame
        print("Merging statistics with pitch data...")
        
        # Add pitcher stats
        pitcher_mapping = {
            pitcher_id: {col: stats.get(col) for col in [
                'pitcher_era', 'pitcher_whip', 'pitcher_k9', 'pitcher_bb9',
                'pitcher_innings', 'pitcher_wins', 'pitcher_losses', 'pitcher_saves'
            ]} for pitcher_id, stats in pitcher_stats.items()
        }
        
        for col in ['pitcher_era', 'pitcher_whip', 'pitcher_k9', 'pitcher_bb9',
                   'pitcher_innings', 'pitcher_wins', 'pitcher_losses', 'pitcher_saves']:
            pitch_df[col] = pitch_df.apply(lambda row: pitcher_mapping.get(row['pitcher_id'], {}).get(col), axis=1)
        
        # Add batter stats
        batter_mapping = {
            batter_id: {col: stats.get(col) for col in [
                'batter_avg', 'batter_obp', 'batter_slg', 'batter_ops',
                'batter_hr', 'batter_rbi', 'batter_sb', 'batter_bb_pct'
            ]} for batter_id, stats in batter_stats.items()
        }
        
        for col in ['batter_avg', 'batter_obp', 'batter_slg', 'batter_ops',
                   'batter_hr', 'batter_rbi', 'batter_sb', 'batter_bb_pct']:
            pitch_df[col] = pitch_df.apply(lambda row: batter_mapping.get(row['batter_id'], {}).get(col), axis=1)
        
        return pitch_df
    
    def create_sequence_features(self, pitch_df: pd.DataFrame) -> pd.DataFrame:
        """
        Create sequence features for pitch data.
        
        Args:
            pitch_df: DataFrame of pitch data
            
        Returns:
            DataFrame with sequence features added
        """
        # Sort by game, inning, at_bat_number, pitch_number
        pitch_df = pitch_df.sort_values([
            'game_pk', 'inning', 'at_bat_number', 'pitch_number'
        ]).reset_index(drop=True)
        
        # Create lagged features within each at-bat
        print("Creating sequence features...")
        
        # Group by at-bat to create lagged features
        pitch_df['prev_pitch_type'] = pitch_df.groupby(['game_pk', 'at_bat_number'])['pitch_type'].shift(1)
        pitch_df['prev_2_pitch_type'] = pitch_df.groupby(['game_pk', 'at_bat_number'])['pitch_type'].shift(2)
        pitch_df['prev_3_pitch_type'] = pitch_df.groupby(['game_pk', 'at_bat_number'])['pitch_type'].shift(3)
        
        # Previous pitch outcomes
        pitch_df['prev_pitch_call'] = pitch_df.groupby(['game_pk', 'at_bat_number'])['pitch_call'].shift(1)
        
        # Count situation as string
        pitch_df['count_situation'] = pitch_df.apply(
            lambda row: f"{int(row['balls'])}-{int(row['strikes'])}" if pd.notna(row['balls']) and pd.notna(row['strikes']) else None, 
            axis=1
        )
        
        # Pitch number in at-bat (already have this, but ensure it's correct)
        pitch_df['pitch_in_ab'] = pitch_df.groupby(['game_pk', 'at_bat_number']).cumcount() + 1
        
        # Create pitcher pitch usage within game
        pitch_df['game_pitch_count'] = pitch_df.groupby(['game_pk', 'pitcher_id']).cumcount() + 1
        
        # Running pitch type percentage for pitcher in game
        for pitch_type in pitch_df['pitch_type'].dropna().unique():
            if pitch_type:  # Skip None/NaN values
                pitch_df[f'pitcher_game_{pitch_type}_pct'] = pitch_df.groupby(['game_pk', 'pitcher_id'])['pitch_type'].transform(
                    lambda x: (x.shift(1) == pitch_type).cumsum() / np.maximum(1, np.arange(len(x)))
                )
        
        return pitch_df
    
    def save_checkpoint(self, data: List[Dict], checkpoint_file: str):
        """Save intermediate results."""
        df = pd.DataFrame(data)
        df.to_csv(checkpoint_file, index=False)
        print(f"Checkpoint saved to {checkpoint_file}")
    
    def collect_data(self, start_date: str, end_date: str, season: str, output_file: str) -> pd.DataFrame:
        """
        Main data collection pipeline.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            season: Season year
            output_file: Output CSV file path
            
        Returns:
            Final DataFrame
        """
        print(f"Starting MLB pitch sequence data collection")
        print(f"Date range: {start_date} to {end_date}")
        print(f"Season: {season}")
        
        # 1. Get schedule
        print("\nFetching game schedule...")
        game_pks = self.get_schedule(start_date, end_date)
        print(f"Found {len(game_pks)} completed games")
        
        if not game_pks:
            print("No games found for the specified date range.")
            return pd.DataFrame()
        
        # 2. Collect pitch data
        print("\nCollecting pitch-by-pitch data...")
        all_pitches = []
        checkpoint_file = output_file.replace('.csv', '_checkpoint.csv')
        
        for i, game_pk in enumerate(game_pks):
            print(f"Processing game {i+1}/{len(game_pks)}: {game_pk}")
            
            try:
                game_data = self.get_game_feed(game_pk)
                if game_data:
                    pitches = self.extract_pitch_data(game_data, game_pk)
                    all_pitches.extend(pitches)
                    print(f"  Collected {len(pitches)} pitches")
                else:
                    print(f"  Failed to get game data")
                
                # Save checkpoint periodically
                if (i + 1) % CHECKPOINT_INTERVAL == 0:
                    self.save_checkpoint(all_pitches, checkpoint_file)
                
                time.sleep(self.delay)
                
            except Exception as e:
                print(f"  Error processing game {game_pk}: {e}")
                continue
        
        if not all_pitches:
            print("No pitch data collected.")
            return pd.DataFrame()
        
        # 3. Convert to DataFrame
        print(f"\nCollected {len(all_pitches)} total pitches")
        df = pd.DataFrame(all_pitches)
        
        # 4. Create sequence features
        print("Creating sequence features...")
        df = self.create_sequence_features(df)
        
        # 5. Enrich with player stats
        print("Enriching with player statistics...")
        df = self.enrich_pitch_data(df, season)
        
        # 6. Save final dataset
        df.to_csv(output_file, index=False)
        print(f"\nDataset saved to {output_file}")
        
        # Clean up checkpoint file
        if Path(checkpoint_file).exists():
            Path(checkpoint_file).unlink()
            print("Checkpoint file cleaned up")
        
        return df


def print_dataset_summary(df: pd.DataFrame):
    """Print summary statistics of the dataset."""
    print(f"\n{'='*50}")
    print("DATASET SUMMARY")
    print(f"{'='*50}")
    print(f"Total pitches: {len(df):,}")
    print(f"Unique games: {df['game_pk'].nunique():,}")
    print(f"Unique pitchers: {df['pitcher_id'].nunique():,}")
    print(f"Unique batters: {df['batter_id'].nunique():,}")
    print(f"Date range: {df['game_date'].min()} to {df['game_date'].max()}")
    
    print(f"\nPitch type distribution:")
    pitch_counts = df['pitch_type'].value_counts()
    for pitch_type, count in pitch_counts.head(10).items():
        print(f"  {pitch_type}: {count:,} ({count/len(df)*100:.1f}%)")
    
    print(f"\nCount situations:")
    count_counts = df['count_situation'].value_counts()
    for count, freq in count_counts.head(8).items():
        print(f"  {count}: {freq:,}")
    
    print(f"\nMissing data summary:")
    missing = df.isnull().sum()
    missing_pct = missing / len(df) * 100
    for col, pct in missing_pct[missing_pct > 0].items():
        print(f"  {col}: {pct:.1f}%")


def test_data_collection():
    """Test data collection with a small sample (1 week of regular season)."""
    print("Running test data collection...")
    
    # Initialize collector with shorter delay for testing
    collector = MLBDataCollector(delay=0.5)
    
    # Test with 1 week of data from 2023 regular season
    test_start = "2023-03-28"
    test_end = "2023-03-28"
    test_output = "test_pitch_data.csv"
    
    try:
        # Collect test data
        df = collector.collect_data(
            start_date=test_start,
            end_date=test_end,
            season="2023",
            output_file=test_output
        )
        
        if len(df) > 0:
            print("\nTest successful! Sample data summary:")
            print_dataset_summary(df)
            
            # Clean up test file
            if Path(test_output).exists():
                Path(test_output).unlink()
                print(f"\nCleaned up test file: {test_output}")
                
            return True
        else:
            print("Test failed: No data collected")
            return False
            
    except Exception as e:
        print(f"Test failed with error: {e}")
        return False


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='Collect MLB pitch sequence data')
    
    # Get current year
    current_year = date.today().year
    
    parser.add_argument('--start_year', type=int, default=2015,
                       help='Start year (default: 2015)')
    parser.add_argument('--end_year', type=int, default=current_year,
                       help=f'End year (default: {current_year})')
    parser.add_argument('--output', type=str, default='mlb_pitch_data_2015_2025.csv',
                       help='Output CSV file path')
    parser.add_argument('--delay', type=float, default=DEFAULT_DELAY,
                       help='Delay between API requests (seconds)')
    
    args = parser.parse_args()
    
    # Validate years
    if args.start_year < 2015 or args.end_year > current_year:
        print(f"Error: Years must be between 2015 and {current_year}")
        sys.exit(1)
    
    all_data = []
    collector = MLBDataCollector(delay=args.delay)
    
    # Process each year
    for year in range(args.start_year, args.end_year + 1):
        print(f"\nProcessing year {year}")
        
        # Regular season (approximately March/April through October)
        regular_start = f"{year}-03-20"  # Approximate season start
        regular_end = f"{year}-10-15"    # Approximate regular season end
        
        print(f"\nCollecting regular season data for {year}...")
        regular_df = collector.collect_data(
            start_date=regular_start,
            end_date=regular_end,
            season=str(year),
            output_file=f"temp_regular_{year}.csv"
        )
        
        # Postseason (October through November)
        post_start = f"{year}-10-01"    # Approximate postseason start
        post_end = f"{year}-11-15"      # Approximate postseason end
        
        print(f"\nCollecting postseason data for {year}...")
        post_df = collector.collect_data(
            start_date=post_start,
            end_date=post_end,
            season=str(year),
            output_file=f"temp_post_{year}.csv"
        )
        
        # Add season type and combine data
        if len(regular_df) > 0:
            regular_df['season_type'] = 'regular'
            regular_df['season'] = year
            all_data.append(regular_df)
        
        if len(post_df) > 0:
            post_df['season_type'] = 'postseason'
            post_df['season'] = year
            all_data.append(post_df)
        
        # Clean up temporary files
        for temp_file in [f"temp_regular_{year}.csv", f"temp_post_{year}.csv"]:
            if Path(temp_file).exists():
                Path(temp_file).unlink()
    
    # Combine and save all data
    if all_data:
        final_df = pd.concat(all_data, ignore_index=True)
        final_df.to_csv(args.output, index=False)
        print(f"\nFinal dataset saved to {args.output}")
        print_dataset_summary(final_df)
    else:
        print("No data was collected.")


if __name__ == "__main__":
    # To test the data collection with a small sample, uncomment the line below
    test_data_collection()
    
    # For full data collection
    # main()