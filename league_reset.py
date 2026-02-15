#!/usr/bin/env python3
"""
League Reset & Revert System
Handles resetting and reverting season tables, season winners, and all-time stats.
Stores snapshots before reset so users can revert within grace periods.
"""

import os
import json
import logging
from datetime import datetime
import pytz
from league_data_adapter import get_db_connection, calculate_wordle_number, get_week_start_date

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

PACIFIC = pytz.timezone('America/Los_Angeles')


def ensure_reset_snapshots_table():
    """Create the reset_snapshots table if it doesn't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reset_snapshots (
            id SERIAL PRIMARY KEY,
            league_id INTEGER NOT NULL,
            reset_type VARCHAR(50) NOT NULL,
            snapshot_data JSONB NOT NULL,
            reset_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            reverted BOOLEAN DEFAULT FALSE,
            expired BOOLEAN DEFAULT FALSE,
            player_id INTEGER DEFAULT 0
        )
    """)
    
    # Unique constraint using player_id=0 for non-player-specific resets
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_reset_snapshots_unique
        ON reset_snapshots(league_id, reset_type, player_id)
    """)
    
    # Create index for quick lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_reset_snapshots_league_type 
        ON reset_snapshots(league_id, reset_type)
    """)
    
    conn.commit()
    cursor.close()
    conn.close()
    logging.info("reset_snapshots table created/verified")


# =============================================================================
# STEP 1: Reset Current Season Table
# =============================================================================

def reset_current_season(league_id):
    """
    Reset the current season table for a league.
    Saves a snapshot of current weekly_winners data for the active season,
    then deletes those records so the season appears fresh.
    Returns: (success, message)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get current season info
        cursor.execute("""
            SELECT current_season, season_start_week
            FROM league_seasons
            WHERE league_id = %s
        """, (league_id,))
        
        season_row = cursor.fetchone()
        if not season_row:
            return False, "No season data found for this league."
        
        current_season = season_row[0]
        season_start_week = season_row[1]
        
        # If season_start_week is NULL, try to derive it
        if not season_start_week:
            # Try the seasons table first
            cursor.execute("""
                SELECT start_week FROM seasons
                WHERE league_id = %s AND season_number = %s
            """, (league_id, current_season))
            s_row = cursor.fetchone()
            if s_row and s_row[0]:
                season_start_week = s_row[0]
            else:
                # Fall back to earliest weekly winner for this league
                cursor.execute("""
                    SELECT MIN(week_wordle_number) FROM weekly_winners
                    WHERE league_id = %s
                """, (league_id,))
                min_row = cursor.fetchone()
                if min_row and min_row[0]:
                    season_start_week = min_row[0]
                else:
                    return False, "No season start week found and no weekly winners exist."
        
        # Get all weekly winners in the current season (these are what we'll snapshot & delete)
        cursor.execute("""
            SELECT id, league_id, week_wordle_number, player_id, player_name, score, recorded_at
            FROM weekly_winners
            WHERE league_id = %s AND week_wordle_number >= %s
            ORDER BY week_wordle_number, player_name
        """, (league_id, season_start_week))
        
        rows = cursor.fetchall()
        
        if not rows:
            return False, "Current season has no weekly winners to reset."
        
        # Build snapshot data
        snapshot = {
            'current_season': current_season,
            'season_start_week': season_start_week,
            'weekly_winners': []
        }
        
        for row in rows:
            snapshot['weekly_winners'].append({
                'id': row[0],
                'league_id': row[1],
                'week_wordle_number': row[2],
                'player_id': row[3],
                'player_name': row[4],
                'score': row[5],
                'recorded_at': row[6].isoformat() if row[6] else None
            })
        
        # Save snapshot (upsert — replace any existing snapshot for this type)
        cursor.execute("""
            INSERT INTO reset_snapshots (league_id, reset_type, snapshot_data, reset_at, reverted, expired, player_id)
            VALUES (%s, 'current_season', %s, CURRENT_TIMESTAMP, FALSE, FALSE, 0)
            ON CONFLICT (league_id, reset_type, player_id) 
            DO UPDATE SET snapshot_data = EXCLUDED.snapshot_data,
                          reset_at = CURRENT_TIMESTAMP,
                          reverted = FALSE,
                          expired = FALSE
        """, (league_id, json.dumps(snapshot)))
        
        # Delete the weekly winners for the current season
        cursor.execute("""
            DELETE FROM weekly_winners
            WHERE league_id = %s AND week_wordle_number >= %s
        """, (league_id, season_start_week))
        
        deleted_count = cursor.rowcount
        
        # Update the season start week to the current week (fresh season)
        now_pacific = datetime.now(PACIFIC)
        current_week_wordle = calculate_wordle_number(get_week_start_date())
        
        cursor.execute("""
            UPDATE league_seasons
            SET season_start_week = %s, updated_at = CURRENT_TIMESTAMP
            WHERE league_id = %s
        """, (current_week_wordle, league_id))
        
        # Also update the seasons table boundary
        cursor.execute("""
            UPDATE seasons
            SET start_week = %s
            WHERE league_id = %s AND season_number = %s
        """, (current_week_wordle, league_id, current_season))
        
        conn.commit()
        
        logging.info(f"✅ Reset current season for league {league_id}: deleted {deleted_count} weekly winner records")
        return True, f"Season {current_season} reset successfully. {deleted_count} weekly winner records cleared."
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Error resetting current season for league {league_id}: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False, f"Error: {str(e)}"
    finally:
        cursor.close()
        conn.close()


def revert_current_season(league_id):
    """
    Revert a current season reset by restoring the snapshot data.
    Returns: (success, message)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get the snapshot
        cursor.execute("""
            SELECT id, snapshot_data
            FROM reset_snapshots
            WHERE league_id = %s AND reset_type = 'current_season' AND player_id = 0
              AND reverted = FALSE AND expired = FALSE
        """, (league_id,))
        
        snap_row = cursor.fetchone()
        if not snap_row:
            return False, "No revertible season reset found."
        
        snapshot_id = snap_row[0]
        snapshot = snap_row[1] if isinstance(snap_row[1], dict) else json.loads(snap_row[1])
        
        # Restore the season start week
        original_season = snapshot['current_season']
        original_start_week = snapshot['season_start_week']
        
        cursor.execute("""
            UPDATE league_seasons
            SET season_start_week = %s, updated_at = CURRENT_TIMESTAMP
            WHERE league_id = %s
        """, (original_start_week, league_id))
        
        # Update seasons table boundary back
        cursor.execute("""
            UPDATE seasons
            SET start_week = %s
            WHERE league_id = %s AND season_number = %s
        """, (original_start_week, league_id, original_season))
        
        # Restore weekly winners
        for ww in snapshot['weekly_winners']:
            cursor.execute("""
                INSERT INTO weekly_winners (league_id, week_wordle_number, player_id, player_name, score, recorded_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (league_id, week_wordle_number, player_id) DO UPDATE
                SET player_name = EXCLUDED.player_name, score = EXCLUDED.score
            """, (
                ww['league_id'], ww['week_wordle_number'], ww['player_id'],
                ww['player_name'], ww['score'],
                ww['recorded_at'] if ww['recorded_at'] else datetime.now()
            ))
        
        # Mark snapshot as reverted
        cursor.execute("""
            UPDATE reset_snapshots SET reverted = TRUE WHERE id = %s
        """, (snapshot_id,))
        
        conn.commit()
        
        restored_count = len(snapshot['weekly_winners'])
        logging.info(f"✅ Reverted current season reset for league {league_id}: restored {restored_count} records")
        return True, f"Season {original_season} reverted successfully. {restored_count} weekly winner records restored."
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Error reverting current season for league {league_id}: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False, f"Error: {str(e)}"
    finally:
        cursor.close()
        conn.close()


def get_season_revert_status(league_id):
    """
    Check if a current season reset can be reverted.
    Revert is available until a new weekly winner is added after the reset.
    Returns: dict with 'can_revert', 'reset_at', 'message'
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check for active (non-reverted, non-expired) snapshot
        cursor.execute("""
            SELECT id, snapshot_data, reset_at
            FROM reset_snapshots
            WHERE league_id = %s AND reset_type = 'current_season' AND player_id = 0
              AND reverted = FALSE AND expired = FALSE
        """, (league_id,))
        
        snap_row = cursor.fetchone()
        if not snap_row:
            return {'can_revert': False, 'reset_at': None, 'message': None}
        
        snapshot_id = snap_row[0]
        reset_at = snap_row[2]
        
        # Check if any new weekly winners have been added AFTER the reset
        cursor.execute("""
            SELECT current_season, season_start_week
            FROM league_seasons
            WHERE league_id = %s
        """, (league_id,))
        
        season_row = cursor.fetchone()
        if not season_row:
            return {'can_revert': False, 'reset_at': None, 'message': None}
        
        season_start_week = season_row[1]
        
        # If season_start_week is NULL, use current wordle week as fallback
        if not season_start_week:
            season_start_week = calculate_wordle_number(get_week_start_date())
        
        # Check if there are any weekly winners in the current season (post-reset)
        cursor.execute("""
            SELECT COUNT(*) FROM weekly_winners
            WHERE league_id = %s AND week_wordle_number >= %s
        """, (league_id, season_start_week))
        
        winner_count = cursor.fetchone()[0]
        
        if winner_count > 0:
            # New winners exist — expire the snapshot
            cursor.execute("""
                UPDATE reset_snapshots SET expired = TRUE WHERE id = %s
            """, (snapshot_id,))
            conn.commit()
            return {'can_revert': False, 'reset_at': None, 'message': 'Revert expired — new weekly winner has been recorded.'}
        
        # Can still revert
        reset_at_pacific = reset_at.replace(tzinfo=pytz.utc).astimezone(PACIFIC) if reset_at.tzinfo is None else reset_at.astimezone(PACIFIC)
        return {
            'can_revert': True,
            'reset_at': reset_at_pacific.strftime('%b %d, %Y at %I:%M %p'),
            'message': 'You can revert this reset until a new weekly winner is recorded (Monday).'
        }
        
    except Exception as e:
        logging.error(f"Error checking season revert status for league {league_id}: {e}")
        return {'can_revert': False, 'reset_at': None, 'message': f'Error: {str(e)}'}
    finally:
        cursor.close()
        conn.close()


# =============================================================================
# STEP 2: Reset Season Winners
# =============================================================================

def reset_season_winners(league_id):
    """
    Reset all season winners for a league.
    Saves a snapshot, deletes all season_winners records, and resets the
    current season number back to 1.
    Returns: (success, message)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get current season info
        cursor.execute("""
            SELECT current_season, season_start_week
            FROM league_seasons
            WHERE league_id = %s
        """, (league_id,))
        
        season_row = cursor.fetchone()
        if not season_row:
            return False, "No season data found for this league."
        
        current_season = season_row[0]
        season_start_week = season_row[1]
        
        # Get all season winners
        cursor.execute("""
            SELECT sw.id, sw.player_id, sw.league_id, sw.season_number, sw.wins, 
                   sw.completed_date, p.name as player_name
            FROM season_winners sw
            JOIN players p ON sw.player_id = p.id
            WHERE sw.league_id = %s
            ORDER BY sw.season_number
        """, (league_id,))
        
        rows = cursor.fetchall()
        
        if not rows:
            return False, "No season winners to reset."
        
        # Get all seasons table entries too (boundaries)
        cursor.execute("""
            SELECT id, league_id, season_number, start_week, end_week
            FROM seasons
            WHERE league_id = %s
            ORDER BY season_number
        """, (league_id,))
        
        season_boundaries = cursor.fetchall()
        
        # Build snapshot
        snapshot = {
            'original_current_season': current_season,
            'original_season_start_week': season_start_week,
            'season_winners': [],
            'season_boundaries': []
        }
        
        for row in rows:
            snapshot['season_winners'].append({
                'id': row[0],
                'player_id': row[1],
                'league_id': row[2],
                'season_number': row[3],
                'wins': row[4],
                'completed_date': row[5].isoformat() if row[5] else None,
                'player_name': row[6]
            })
        
        for sb in season_boundaries:
            snapshot['season_boundaries'].append({
                'id': sb[0],
                'league_id': sb[1],
                'season_number': sb[2],
                'start_week': sb[3],
                'end_week': sb[4]
            })
        
        # Save snapshot
        cursor.execute("""
            INSERT INTO reset_snapshots (league_id, reset_type, snapshot_data, reset_at, reverted, expired, player_id)
            VALUES (%s, 'season_winners', %s, CURRENT_TIMESTAMP, FALSE, FALSE, 0)
            ON CONFLICT (league_id, reset_type, player_id)
            DO UPDATE SET snapshot_data = EXCLUDED.snapshot_data,
                          reset_at = CURRENT_TIMESTAMP,
                          reverted = FALSE,
                          expired = FALSE
        """, (league_id, json.dumps(snapshot)))
        
        # Delete all season winners
        cursor.execute("DELETE FROM season_winners WHERE league_id = %s", (league_id,))
        deleted_winners = cursor.rowcount
        
        # Delete all season boundaries (except current)
        cursor.execute("DELETE FROM seasons WHERE league_id = %s", (league_id,))
        
        # Reset to Season 1 — keep the current season_start_week as is
        # (the current season's weekly winners stay intact, just relabeled as Season 1)
        cursor.execute("""
            UPDATE league_seasons
            SET current_season = 1, updated_at = CURRENT_TIMESTAMP
            WHERE league_id = %s
        """, (league_id,))
        
        # Create a fresh Season 1 entry in the seasons table
        cursor.execute("""
            INSERT INTO seasons (league_id, season_number, start_week, end_week)
            VALUES (%s, 1, %s, NULL)
            ON CONFLICT (league_id, season_number) DO UPDATE
            SET start_week = EXCLUDED.start_week, end_week = NULL
        """, (league_id, season_start_week))
        
        conn.commit()
        
        logging.info(f"✅ Reset season winners for league {league_id}: deleted {deleted_winners} season winner records, reset to Season 1")
        return True, f"Season winners reset successfully. {deleted_winners} season winner records cleared. Now on Season 1."
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Error resetting season winners for league {league_id}: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False, f"Error: {str(e)}"
    finally:
        cursor.close()
        conn.close()


def revert_season_winners(league_id):
    """
    Revert a season winners reset by restoring the snapshot data.
    Returns: (success, message)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get the snapshot
        cursor.execute("""
            SELECT id, snapshot_data
            FROM reset_snapshots
            WHERE league_id = %s AND reset_type = 'season_winners' AND player_id = 0
              AND reverted = FALSE AND expired = FALSE
        """, (league_id,))
        
        snap_row = cursor.fetchone()
        if not snap_row:
            return False, "No revertible season winners reset found."
        
        snapshot_id = snap_row[0]
        snapshot = snap_row[1] if isinstance(snap_row[1], dict) else json.loads(snap_row[1])
        
        # Restore season number and start week
        original_season = snapshot['original_current_season']
        original_start_week = snapshot['original_season_start_week']
        
        cursor.execute("""
            UPDATE league_seasons
            SET current_season = %s, season_start_week = %s, updated_at = CURRENT_TIMESTAMP
            WHERE league_id = %s
        """, (original_season, original_start_week, league_id))
        
        # Delete any current seasons table entries and restore originals
        cursor.execute("DELETE FROM seasons WHERE league_id = %s", (league_id,))
        
        for sb in snapshot.get('season_boundaries', []):
            cursor.execute("""
                INSERT INTO seasons (league_id, season_number, start_week, end_week)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (league_id, season_number) DO UPDATE
                SET start_week = EXCLUDED.start_week, end_week = EXCLUDED.end_week
            """, (sb['league_id'], sb['season_number'], sb['start_week'], sb['end_week']))
        
        # Restore season winners
        for sw in snapshot['season_winners']:
            cursor.execute("""
                INSERT INTO season_winners (player_id, league_id, season_number, wins, completed_date)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                sw['player_id'], sw['league_id'], sw['season_number'],
                sw['wins'],
                sw.get('completed_date')
            ))
        
        # Mark snapshot as reverted
        cursor.execute("UPDATE reset_snapshots SET reverted = TRUE WHERE id = %s", (snapshot_id,))
        
        conn.commit()
        
        restored_count = len(snapshot['season_winners'])
        logging.info(f"✅ Reverted season winners reset for league {league_id}: restored {restored_count} records, back to Season {original_season}")
        return True, f"Season winners reverted successfully. {restored_count} records restored. Back to Season {original_season}."
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Error reverting season winners for league {league_id}: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False, f"Error: {str(e)}"
    finally:
        cursor.close()
        conn.close()


def get_season_winners_revert_status(league_id):
    """
    Check if a season winners reset can be reverted.
    Revert is available until a new season winner is crowned (someone hits 4 wins).
    Returns: dict with 'can_revert', 'reset_at', 'message'
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check for active snapshot
        cursor.execute("""
            SELECT id, snapshot_data, reset_at
            FROM reset_snapshots
            WHERE league_id = %s AND reset_type = 'season_winners' AND player_id = 0
              AND reverted = FALSE AND expired = FALSE
        """, (league_id,))
        
        snap_row = cursor.fetchone()
        if not snap_row:
            return {'can_revert': False, 'reset_at': None, 'message': None}
        
        snapshot_id = snap_row[0]
        reset_at = snap_row[2]
        
        # Check if any new season winners have been added after the reset
        cursor.execute("""
            SELECT COUNT(*) FROM season_winners WHERE league_id = %s
        """, (league_id,))
        
        winner_count = cursor.fetchone()[0]
        
        if winner_count > 0:
            # New season winner exists — expire the snapshot
            cursor.execute("UPDATE reset_snapshots SET expired = TRUE WHERE id = %s", (snapshot_id,))
            conn.commit()
            return {'can_revert': False, 'reset_at': None, 'message': 'Revert expired — a new season winner has been crowned.'}
        
        reset_at_pacific = reset_at.replace(tzinfo=pytz.utc).astimezone(PACIFIC) if reset_at.tzinfo is None else reset_at.astimezone(PACIFIC)
        return {
            'can_revert': True,
            'reset_at': reset_at_pacific.strftime('%b %d, %Y at %I:%M %p'),
            'message': 'You can revert until a new season winner is crowned (someone reaches 4 weekly wins).'
        }
        
    except Exception as e:
        logging.error(f"Error checking season winners revert status for league {league_id}: {e}")
        return {'can_revert': False, 'reset_at': None, 'message': f'Error: {str(e)}'}
    finally:
        cursor.close()
        conn.close()


# =============================================================================
# STEP 3: Reset All-Time Stats
# =============================================================================

def reset_alltime_all_players(league_id):
    """
    Reset all-time stats for ALL players in a league.
    Saves a snapshot of all scores, then deletes them.
    Returns: (success, message)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get all scores for all active players in this league
        cursor.execute("""
            SELECT s.id, s.player_id, p.name, s.wordle_number, s.score, s.date, s.emoji_pattern, s.timestamp
            FROM scores s
            JOIN players p ON s.player_id = p.id
            WHERE p.league_id = %s
            ORDER BY p.name, s.wordle_number
        """, (league_id,))
        
        rows = cursor.fetchall()
        
        if not rows:
            return False, "No scores to reset."
        
        # Build snapshot
        snapshot = {
            'scores': []
        }
        
        for row in rows:
            snapshot['scores'].append({
                'id': row[0],
                'player_id': row[1],
                'player_name': row[2],
                'wordle_number': row[3],
                'score': row[4],
                'date': row[5].isoformat() if row[5] else None,
                'emoji_pattern': row[6],
                'timestamp': row[7].isoformat() if row[7] else None
            })
        
        # Save snapshot
        cursor.execute("""
            INSERT INTO reset_snapshots (league_id, reset_type, snapshot_data, reset_at, reverted, expired, player_id)
            VALUES (%s, 'alltime_all', %s, CURRENT_TIMESTAMP, FALSE, FALSE, 0)
            ON CONFLICT (league_id, reset_type, player_id)
            DO UPDATE SET snapshot_data = EXCLUDED.snapshot_data,
                          reset_at = CURRENT_TIMESTAMP,
                          reverted = FALSE,
                          expired = FALSE
        """, (league_id, json.dumps(snapshot)))
        
        # Delete all scores for players in this league
        cursor.execute("""
            DELETE FROM scores
            WHERE player_id IN (SELECT id FROM players WHERE league_id = %s)
        """, (league_id,))
        deleted_count = cursor.rowcount
        
        # Also clear latest_scores
        cursor.execute("""
            DELETE FROM latest_scores WHERE league_id = %s
        """, (league_id,))
        
        conn.commit()
        
        logging.info(f"✅ Reset all-time stats for league {league_id}: deleted {deleted_count} score records")
        return True, f"All-time stats reset for all players. {deleted_count} score records cleared."
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Error resetting all-time stats for league {league_id}: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False, f"Error: {str(e)}"
    finally:
        cursor.close()
        conn.close()


def reset_alltime_single_player(league_id, player_id):
    """
    Reset all-time stats for a single player.
    Saves a snapshot of their scores, then deletes them.
    Returns: (success, message)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verify player belongs to this league
        cursor.execute("""
            SELECT name FROM players WHERE id = %s AND league_id = %s
        """, (player_id, league_id))
        
        player_row = cursor.fetchone()
        if not player_row:
            return False, "Player not found in this league."
        
        player_name = player_row[0]
        
        # Get all scores for this player
        cursor.execute("""
            SELECT id, player_id, wordle_number, score, date, emoji_pattern, timestamp
            FROM scores
            WHERE player_id = %s
            ORDER BY wordle_number
        """, (player_id,))
        
        rows = cursor.fetchall()
        
        if not rows:
            return False, f"No scores to reset for {player_name}."
        
        # Build snapshot
        snapshot = {
            'player_id': player_id,
            'player_name': player_name,
            'scores': []
        }
        
        for row in rows:
            snapshot['scores'].append({
                'id': row[0],
                'player_id': row[1],
                'wordle_number': row[2],
                'score': row[3],
                'date': row[4].isoformat() if row[4] else None,
                'emoji_pattern': row[5],
                'timestamp': row[6].isoformat() if row[6] else None
            })
        
        # Save snapshot (player-specific — use player_id in unique constraint)
        # For single player resets, we use a composite key of league_id + reset_type + player_id
        cursor.execute("""
            INSERT INTO reset_snapshots (league_id, reset_type, snapshot_data, reset_at, reverted, expired, player_id)
            VALUES (%s, 'alltime_player', %s, CURRENT_TIMESTAMP, FALSE, FALSE, %s)
            ON CONFLICT (league_id, reset_type, player_id)
            DO UPDATE SET snapshot_data = EXCLUDED.snapshot_data,
                          reset_at = CURRENT_TIMESTAMP,
                          reverted = FALSE,
                          expired = FALSE
        """, (league_id, json.dumps(snapshot), player_id))
        
        # Delete scores
        cursor.execute("DELETE FROM scores WHERE player_id = %s", (player_id,))
        deleted_count = cursor.rowcount
        
        # Clear latest_scores for this player
        cursor.execute("DELETE FROM latest_scores WHERE player_id = %s", (player_id,))
        
        conn.commit()
        
        logging.info(f"✅ Reset all-time stats for player {player_name} (id={player_id}) in league {league_id}: deleted {deleted_count} scores")
        return True, f"All-time stats reset for {player_name}. {deleted_count} score records cleared."
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Error resetting all-time stats for player {player_id}: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False, f"Error: {str(e)}"
    finally:
        cursor.close()
        conn.close()


def revert_alltime_all_players(league_id):
    """
    Revert an all-players all-time reset using additive merge.
    Merges the snapshot scores with any new scores recorded since the reset.
    Returns: (success, message)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get the snapshot
        cursor.execute("""
            SELECT id, snapshot_data
            FROM reset_snapshots
            WHERE league_id = %s AND reset_type = 'alltime_all' AND player_id = 0
              AND reverted = FALSE AND expired = FALSE
        """, (league_id,))
        
        snap_row = cursor.fetchone()
        if not snap_row:
            return False, "No revertible all-time reset found."
        
        snapshot_id = snap_row[0]
        snapshot = snap_row[1] if isinstance(snap_row[1], dict) else json.loads(snap_row[1])
        
        # Restore old scores (skip any that conflict with new scores on same wordle_number)
        restored = 0
        skipped = 0
        for sc in snapshot['scores']:
            try:
                cursor.execute("""
                    INSERT INTO scores (player_id, wordle_number, score, date, emoji_pattern, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (player_id, wordle_number) DO NOTHING
                """, (
                    sc['player_id'], sc['wordle_number'], sc['score'],
                    sc['date'], sc.get('emoji_pattern'),
                    sc['timestamp'] if sc['timestamp'] else datetime.now()
                ))
                if cursor.rowcount > 0:
                    restored += 1
                else:
                    skipped += 1
            except Exception:
                skipped += 1
        
        # Mark snapshot as reverted
        cursor.execute("UPDATE reset_snapshots SET reverted = TRUE WHERE id = %s", (snapshot_id,))
        
        conn.commit()
        
        logging.info(f"✅ Reverted all-time reset for league {league_id}: restored {restored}, skipped {skipped} (already existed)")
        return True, f"All-time stats reverted. {restored} scores restored, {skipped} skipped (newer scores kept)."
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Error reverting all-time stats for league {league_id}: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False, f"Error: {str(e)}"
    finally:
        cursor.close()
        conn.close()


def revert_alltime_single_player(league_id, player_id):
    """
    Revert a single-player all-time reset using additive merge.
    Returns: (success, message)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get the snapshot
        cursor.execute("""
            SELECT id, snapshot_data
            FROM reset_snapshots
            WHERE league_id = %s AND reset_type = 'alltime_player' AND player_id = %s
              AND reverted = FALSE AND expired = FALSE
        """, (league_id, player_id))
        
        snap_row = cursor.fetchone()
        if not snap_row:
            return False, "No revertible reset found for this player."
        
        snapshot_id = snap_row[0]
        snapshot = snap_row[1] if isinstance(snap_row[1], dict) else json.loads(snap_row[1])
        player_name = snapshot.get('player_name', f'Player {player_id}')
        
        # Restore old scores (additive — keep any new scores)
        restored = 0
        skipped = 0
        for sc in snapshot['scores']:
            try:
                cursor.execute("""
                    INSERT INTO scores (player_id, wordle_number, score, date, emoji_pattern, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (player_id, wordle_number) DO NOTHING
                """, (
                    sc['player_id'], sc['wordle_number'], sc['score'],
                    sc['date'], sc.get('emoji_pattern'),
                    sc['timestamp'] if sc['timestamp'] else datetime.now()
                ))
                if cursor.rowcount > 0:
                    restored += 1
                else:
                    skipped += 1
            except Exception:
                skipped += 1
        
        # Mark snapshot as reverted
        cursor.execute("UPDATE reset_snapshots SET reverted = TRUE WHERE id = %s", (snapshot_id,))
        
        conn.commit()
        
        logging.info(f"✅ Reverted all-time reset for player {player_name} in league {league_id}: restored {restored}, skipped {skipped}")
        return True, f"All-time stats reverted for {player_name}. {restored} scores restored, {skipped} skipped (newer scores kept)."
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Error reverting all-time stats for player {player_id}: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False, f"Error: {str(e)}"
    finally:
        cursor.close()
        conn.close()


def get_alltime_revert_status(league_id, player_id=None):
    """
    Check if an all-time reset can be reverted.
    All-time reverts are ALWAYS available (no expiration).
    Returns: dict with 'can_revert', 'reset_at', 'message', 'player_name'
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if player_id:
            cursor.execute("""
                SELECT id, snapshot_data, reset_at
                FROM reset_snapshots
                WHERE league_id = %s AND reset_type = 'alltime_player' AND player_id = %s
                  AND reverted = FALSE AND expired = FALSE
            """, (league_id, player_id))
        else:
            cursor.execute("""
                SELECT id, snapshot_data, reset_at
                FROM reset_snapshots
                WHERE league_id = %s AND reset_type = 'alltime_all' AND player_id = 0
                  AND reverted = FALSE AND expired = FALSE
            """, (league_id,))
        
        snap_row = cursor.fetchone()
        if not snap_row:
            return {'can_revert': False, 'reset_at': None, 'message': None, 'player_name': None}
        
        reset_at = snap_row[2]
        snapshot = snap_row[1] if isinstance(snap_row[1], dict) else json.loads(snap_row[1])
        
        reset_at_pacific = reset_at.replace(tzinfo=pytz.utc).astimezone(PACIFIC) if reset_at.tzinfo is None else reset_at.astimezone(PACIFIC)
        
        player_name = snapshot.get('player_name') if player_id else None
        score_count = len(snapshot.get('scores', []))
        
        return {
            'can_revert': True,
            'reset_at': reset_at_pacific.strftime('%b %d, %Y at %I:%M %p'),
            'message': f'Revert will merge {score_count} old scores with any new scores recorded since the reset.',
            'player_name': player_name
        }
        
    except Exception as e:
        logging.error(f"Error checking all-time revert status: {e}")
        return {'can_revert': False, 'reset_at': None, 'message': f'Error: {str(e)}', 'player_name': None}
    finally:
        cursor.close()
        conn.close()


def get_all_player_revert_statuses(league_id):
    """
    Get revert status for all individual player resets in a league.
    Returns: list of dicts with player_id, player_name, can_revert, reset_at
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, player_id, snapshot_data, reset_at
            FROM reset_snapshots
            WHERE league_id = %s AND reset_type = 'alltime_player'
              AND reverted = FALSE AND expired = FALSE
        """, (league_id,))
        
        results = []
        for row in cursor.fetchall():
            snapshot = row[2] if isinstance(row[2], dict) else json.loads(row[2])
            reset_at = row[3]
            reset_at_pacific = reset_at.replace(tzinfo=pytz.utc).astimezone(PACIFIC) if reset_at.tzinfo is None else reset_at.astimezone(PACIFIC)
            
            results.append({
                'player_id': row[1],
                'player_name': snapshot.get('player_name', f'Player {row[1]}'),
                'can_revert': True,
                'reset_at': reset_at_pacific.strftime('%b %d, %Y at %I:%M %p'),
                'score_count': len(snapshot.get('scores', []))
            })
        
        return results
        
    except Exception as e:
        logging.error(f"Error getting player revert statuses: {e}")
        return []
    finally:
        cursor.close()
        conn.close()
