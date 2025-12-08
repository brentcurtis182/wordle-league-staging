#!/usr/bin/env python3
"""
Weekly Winners PostgreSQL Adapter
Replaces weekly_winners.json with PostgreSQL storage
Maintains the same data structure for compatibility with existing code
"""

import os
import logging
from datetime import datetime
from league_data_adapter import get_db_connection

def load_weekly_winners():
    """
    Load weekly winners from PostgreSQL database
    Returns data in the same format as weekly_winners.json for compatibility
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Initialize data structure matching JSON format
    data = {
        'leagues': {},
        'current_seasons': {},
        'last_updated': None
    }
    
    # Get all league IDs that have data
    cursor.execute("""
        SELECT DISTINCT league_id FROM players ORDER BY league_id
    """)
    
    league_ids = [row[0] for row in cursor.fetchall()]
    
    for league_id in league_ids:
        league_key = str(league_id)
        
        # Get league name (you'll need to add this or use a mapping)
        league_names = {
            '1': 'Warriorz',
            '2': 'Gang',
            '3': 'PAL',
            '4': 'Party',
            '5': 'Vball',
            '6': 'League 6'
        }
        league_name = league_names.get(league_key, f'League {league_id}')
        
        # Get current season info
        cursor.execute("""
            SELECT current_season, season_start_week
            FROM league_seasons
            WHERE league_id = %s
        """, (league_id,))
        
        season_result = cursor.fetchone()
        current_season = season_result[0] if season_result else 1
        season_start_week = season_result[1] if season_result else None
        
        # Get weekly winners
        cursor.execute("""
            SELECT week_wordle_number, player_name, score
            FROM weekly_winners
            WHERE league_id = %s
            ORDER BY week_wordle_number
        """, (league_id,))
        
        weekly_winners = {}
        for row in cursor.fetchall():
            week_num = str(row[0])
            player_name = row[1]
            score = row[2]
            
            if week_num not in weekly_winners:
                weekly_winners[week_num] = []
            
            weekly_winners[week_num].append({
                'name': player_name,
                'score': score
            })
        
        # Get season winners
        cursor.execute("""
            SELECT sw.season_number, p.name, sw.wins, sw.completed_date
            FROM season_winners sw
            JOIN players p ON sw.player_id = p.id
            WHERE sw.league_id = %s
            ORDER BY sw.season_number
        """, (league_id,))
        
        season_winners = []
        for row in cursor.fetchall():
            season_winners.append({
                'season': row[0],
                'name': row[1],
                'weekly_wins': row[2],
                'completed_date': row[3].strftime('%Y-%m-%d') if row[3] else None
            })
        
        # Build league data structure
        data['leagues'][league_key] = {
            'name': league_name,
            'current_season': current_season,
            'weekly_winners': weekly_winners,
            'season_winners': season_winners,
            'seasons': {}  # Will be populated if needed
        }
        
        # Add to current_seasons tracker
        data['current_seasons'][league_key] = current_season
    
    cursor.close()
    conn.close()
    
    # Set last updated timestamp
    data['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    logging.info(f"Loaded weekly winners data for {len(league_ids)} leagues from PostgreSQL")
    
    return data

def save_weekly_winners(winners_data):
    """
    Save weekly winners data to PostgreSQL database
    Accepts data in the same format as weekly_winners.json
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        for league_key, league_info in winners_data.get('leagues', {}).items():
            league_id = int(league_key)
            
            # Update or insert league season info
            current_season = league_info.get('current_season', 1)
            season_start_week = None
            
            # Try to get season start week from seasons data
            seasons_data = league_info.get('seasons', {})
            if str(current_season) in seasons_data:
                season_start_week = seasons_data[str(current_season)].get('start_week')
            
            cursor.execute("""
                INSERT INTO league_seasons (league_id, current_season, season_start_week)
                VALUES (%s, %s, %s)
                ON CONFLICT (league_id) DO UPDATE
                SET current_season = EXCLUDED.current_season,
                    season_start_week = EXCLUDED.season_start_week,
                    updated_at = CURRENT_TIMESTAMP
            """, (league_id, current_season, season_start_week))
            
            # Save weekly winners
            weekly_winners = league_info.get('weekly_winners', {})
            for week_num, winners in weekly_winners.items():
                week_wordle = int(week_num)
                
                for winner in winners:
                    player_name = winner.get('name')
                    score = winner.get('score')
                    
                    if not player_name:
                        continue
                    
                    # Get player_id
                    cursor.execute("""
                        SELECT id FROM players
                        WHERE name = %s AND league_id = %s
                    """, (player_name, league_id))
                    
                    player_result = cursor.fetchone()
                    if not player_result:
                        logging.warning(f"Player {player_name} not found in league {league_id}, skipping")
                        continue
                    
                    player_id = player_result[0]
                    
                    # Insert or update weekly winner
                    cursor.execute("""
                        INSERT INTO weekly_winners (league_id, week_wordle_number, player_id, player_name, score)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (league_id, week_wordle_number, player_id) DO UPDATE
                        SET score = EXCLUDED.score,
                            recorded_at = CURRENT_TIMESTAMP
                    """, (league_id, week_wordle, player_id, player_name, score))
            
            # Save season winners
            season_winners = league_info.get('season_winners', [])
            for winner in season_winners:
                season_num = winner.get('season')
                player_name = winner.get('name')
                wins = winner.get('weekly_wins', 0)
                
                if not player_name or not season_num:
                    continue
                
                # Get player_id
                cursor.execute("""
                    SELECT id FROM players
                    WHERE name = %s AND league_id = %s
                """, (player_name, league_id))
                
                player_result = cursor.fetchone()
                if not player_result:
                    logging.warning(f"Player {player_name} not found in league {league_id}, skipping season winner")
                    continue
                
                player_id = player_result[0]
                
                # Check if already exists
                cursor.execute("""
                    SELECT id FROM season_winners
                    WHERE league_id = %s AND season_number = %s AND player_id = %s
                """, (league_id, season_num, player_id))
                
                if not cursor.fetchone():
                    # Insert season winner
                    cursor.execute("""
                        INSERT INTO season_winners (player_id, league_id, season_number, wins)
                        VALUES (%s, %s, %s, %s)
                    """, (player_id, league_id, season_num, wins))
        
        conn.commit()
        logging.info("Successfully saved weekly winners data to PostgreSQL")
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Error saving weekly winners to PostgreSQL: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

def initialize_current_seasons(data):
    """
    Initialize the current season numbers for each league
    Maintains compatibility with existing code
    """
    if 'current_seasons' not in data:
        data['current_seasons'] = {}
    
    for league_key in data.get('leagues', {}).keys():
        if league_key not in data['current_seasons']:
            data['current_seasons'][league_key] = 1

if __name__ == "__main__":
    # Test the adapter
    logging.basicConfig(level=logging.INFO)
    
    print("Testing load_weekly_winners()...")
    data = load_weekly_winners()
    print(f"Loaded data for {len(data['leagues'])} leagues")
    
    for league_key, league_info in data['leagues'].items():
        print(f"\nLeague {league_key} ({league_info['name']}):")
        print(f"  Current Season: {league_info['current_season']}")
        print(f"  Weekly Winners: {len(league_info['weekly_winners'])} weeks")
        print(f"  Season Winners: {len(league_info['season_winners'])} winners")
