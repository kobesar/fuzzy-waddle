"""
MLB Stats API Client
Handles all interactions with the MLB Stats API to retrieve pitcher and pitch data
"""

import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import pandas as pd


class MLBStatsAPI:
    """Client for interacting with MLB Stats API"""

    BASE_URL = "https://statsapi.mlb.com/api/v1"
    LOOKUP_URL = "https://lookup-service-prod.mlb.com/json/named.search_player_all.bam"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'MLB-Pitch-Predictor/1.0'
        })

    def search_pitchers(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Search for pitchers by name using MLB lookup service

        Args:
            query: Pitcher name to search for
            limit: Maximum number of results to return

        Returns:
            List of pitcher dictionaries with id, name, and team info
        """
        try:
            params = {
                'sport_code': "'mlb'",
                'active_sw': "'Y'",
                'search_player_all': f"'{query}'",
                'name_part': "'any'"
            }

            response = self.session.get(self.LOOKUP_URL, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            # Parse the nested JSON structure
            search_results = data.get('search_player_all', {}).get('queryResults', {})

            if search_results.get('totalSize') == '0':
                return []

            players = search_results.get('row', [])

            # Ensure players is a list (single result comes as dict)
            if isinstance(players, dict):
                players = [players]

            # Filter for pitchers only
            pitchers = []
            for player in players[:limit]:
                if player.get('position', '').upper() == 'P':
                    pitchers.append({
                        'id': int(player.get('player_id', 0)),
                        'name': f"{player.get('name_first', '')} {player.get('name_last', '')}",
                        'team': player.get('team_full', 'Free Agent'),
                        'position': player.get('position', 'P')
                    })

            return pitchers

        except Exception as e:
            print(f"Error searching pitchers: {e}")
            return []

    def get_pitcher_info(self, pitcher_id: int) -> Optional[Dict]:
        """
        Get detailed information about a specific pitcher

        Args:
            pitcher_id: MLB player ID

        Returns:
            Dictionary with pitcher details
        """
        try:
            url = f"{self.BASE_URL}/people/{pitcher_id}"
            params = {
                'hydrate': 'stats(group=[pitching],type=[career,season])'
            }

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if 'people' not in data or len(data['people']) == 0:
                return None

            pitcher = data['people'][0]

            return {
                'id': pitcher.get('id'),
                'name': pitcher.get('fullName'),
                'position': pitcher.get('primaryPosition', {}).get('name'),
                'team': pitcher.get('currentTeam', {}).get('name'),
                'throws': pitcher.get('pitchHand', {}).get('code', 'R'),
                'age': pitcher.get('currentAge'),
                'height': pitcher.get('height'),
                'weight': pitcher.get('weight')
            }

        except Exception as e:
            print(f"Error getting pitcher info: {e}")
            return None

    def get_game_ids_for_pitcher(self, pitcher_id: int, season: int = None, limit: int = 20) -> List[int]:
        """
        Get game IDs where the pitcher appeared

        Args:
            pitcher_id: MLB player ID
            season: Year (defaults to current year)
            limit: Maximum number of games to retrieve

        Returns:
            List of game PKs
        """
        if season is None:
            season = datetime.now().year

        try:
            # Get pitcher's game log
            url = f"{self.BASE_URL}/people/{pitcher_id}"
            params = {
                'hydrate': f'stats(group=[pitching],type=[gameLog],season={season})'
            }

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if 'people' not in data or len(data['people']) == 0:
                return []

            stats = data['people'][0].get('stats', [])
            game_ids = []

            for stat_group in stats:
                if stat_group.get('type', {}).get('displayName') == 'gameLog':
                    splits = stat_group.get('splits', [])
                    for split in splits[:limit]:
                        game = split.get('game', {})
                        game_pk = game.get('gamePk')
                        if game_pk:
                            game_ids.append(game_pk)

            return game_ids

        except Exception as e:
            print(f"Error getting game IDs: {e}")
            return []

    def get_pitch_data_for_game(self, game_pk: int, pitcher_id: int) -> pd.DataFrame:
        """
        Get pitch-by-pitch data for a specific pitcher in a specific game

        Args:
            game_pk: MLB game ID
            pitcher_id: MLB player ID

        Returns:
            DataFrame with pitch-level data
        """
        try:
            url = f"{self.BASE_URL}/game/{game_pk}/feed/live"

            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            data = response.json()

            pitches = []

            # Navigate through the game data structure
            plays = data.get('liveData', {}).get('plays', {}).get('allPlays', [])

            for play in plays:
                # Check if this pitcher was involved
                matchup = play.get('matchup', {})
                play_pitcher_id = matchup.get('pitcher', {}).get('id')

                if play_pitcher_id != pitcher_id:
                    continue

                # Extract context
                count = play.get('count', {})
                batter = matchup.get('batter', {})

                # Get play events (pitches)
                play_events = play.get('playEvents', [])

                for event in play_events:
                    if event.get('isPitch'):
                        pitch_data = event.get('pitchData', {})
                        details = event.get('details', {})

                        pitch_info = {
                            'game_pk': game_pk,
                            'pitcher_id': pitcher_id,
                            'batter_id': batter.get('id'),
                            'batter_side': matchup.get('batSide', {}).get('code', 'R'),
                            'inning': play.get('about', {}).get('inning', 1),
                            'balls': count.get('balls', 0),
                            'strikes': count.get('strikes', 0),
                            'outs': count.get('outs', 0),
                            'pitch_type': details.get('type', {}).get('code', 'Unknown'),
                            'pitch_name': details.get('type', {}).get('description', 'Unknown'),
                            'start_speed': pitch_data.get('startSpeed'),
                            'end_speed': pitch_data.get('endSpeed'),
                            'zone': pitch_data.get('zone'),
                            'pitch_result': details.get('description', 'Unknown'),
                            'runners_on': len(play.get('runners', [])) > 0,
                            'description': event.get('details', {}).get('description', '')
                        }

                        pitches.append(pitch_info)

                        # Update count for next pitch
                        if event.get('count'):
                            count = event['count']

            return pd.DataFrame(pitches)

        except Exception as e:
            print(f"Error getting pitch data for game {game_pk}: {e}")
            return pd.DataFrame()

    def get_pitcher_pitch_data(self, pitcher_id: int, season: int = None, max_games: int = 20) -> pd.DataFrame:
        """
        Get comprehensive pitch data for a pitcher across multiple games

        Args:
            pitcher_id: MLB player ID
            season: Year (defaults to current year)
            max_games: Maximum number of games to fetch

        Returns:
            Combined DataFrame with all pitch data
        """
        print(f"Fetching pitch data for pitcher {pitcher_id}...")

        # Get game IDs
        game_ids = self.get_game_ids_for_pitcher(pitcher_id, season, max_games)

        if not game_ids:
            print("No games found for pitcher")
            return pd.DataFrame()

        print(f"Found {len(game_ids)} games, fetching pitch data...")

        # Collect pitch data from all games
        all_pitches = []

        for i, game_pk in enumerate(game_ids, 1):
            print(f"Fetching game {i}/{len(game_ids)}: {game_pk}")
            game_pitches = self.get_pitch_data_for_game(game_pk, pitcher_id)

            if not game_pitches.empty:
                all_pitches.append(game_pitches)

        if not all_pitches:
            return pd.DataFrame()

        # Combine all data
        combined_df = pd.concat(all_pitches, ignore_index=True)

        print(f"Retrieved {len(combined_df)} total pitches")

        return combined_df
