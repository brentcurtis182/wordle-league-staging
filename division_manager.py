#!/usr/bin/env python3
"""
Division Manager for Wordle League
Handles all division mode operations: toggle, assign players, confirm, reset, revert,
promotion/relegation, and division-aware season management.
"""

import os
import json
import logging
from datetime import datetime
import pytz
from league_data_adapter import get_db_connection, calculate_wordle_number, get_week_start_date

DIVISION_WINS_FOR_SEASON = 3  # Wins needed to win a division season (vs 4 for normal)


def get_division_status(league_id):
    """Get the current division mode status for a league"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT division_mode, division_confirmed_at, division_locked
            FROM leagues WHERE id = %s
        """, (league_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return {
            'division_mode': row[0] or False,
            'confirmed_at': row[1],
            'locked': row[2] or False
        }
    finally:
        cursor.close()
        conn.close()


def get_division_players(league_id):
    """Get players grouped by division"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, name, division, division_immunity, division_joined_week, active
            FROM players
            WHERE league_id = %s AND active = TRUE
            ORDER BY division NULLS LAST, name
        """, (league_id,))
        
        players = []
        for row in cursor.fetchall():
            players.append({
                'id': row[0],
                'name': row[1],
                'division': row[2],
                'immunity': row[3] or False,
                'joined_week': row[4],
                'active': row[5]
            })
        
        return players
    finally:
        cursor.close()
        conn.close()


def toggle_division_mode(league_id, enable):
    """
    Toggle division mode on or off.
    When enabling: auto-split players into 2 divisions.
    When disabling (before locked): revert to pre-division state.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check current state
        cursor.execute("""
            SELECT division_mode, division_locked FROM leagues WHERE id = %s
        """, (league_id,))
        row = cursor.fetchone()
        
        if not row:
            return {'success': False, 'error': 'League not found'}
        
        current_mode = row[0] or False
        is_locked = row[1] or False
        
        if enable and current_mode:
            return {'success': False, 'error': 'Division mode is already enabled'}
        
        if not enable and not current_mode:
            return {'success': False, 'error': 'Division mode is already disabled'}
        
        if enable:
            return _enable_division_mode(league_id, cursor, conn)
        else:
            return _disable_division_mode(league_id, cursor, conn, is_locked)
    
    except Exception as e:
        conn.rollback()
        logging.error(f"Error toggling division mode for league {league_id}: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}
    finally:
        cursor.close()
        conn.close()


def _enable_division_mode(league_id, cursor, conn):
    """Enable division mode: snapshot current state, auto-split players"""
    
    # Get active players
    cursor.execute("""
        SELECT id, name FROM players
        WHERE league_id = %s AND active = TRUE
        ORDER BY name
    """, (league_id,))
    players = cursor.fetchall()
    
    if len(players) < 4:
        return {'success': False, 'error': 'Need at least 4 active players for division mode'}
    
    # Snapshot current state for potential revert
    # Save: player divisions (all NULL currently), current weekly winners, season state
    cursor.execute("""
        SELECT id, division FROM players WHERE league_id = %s AND active = TRUE
    """, (league_id,))
    player_divisions = [{'id': r[0], 'division': r[1]} for r in cursor.fetchall()]
    
    snapshot = {
        'player_divisions': player_divisions,
        'enabled_at': datetime.now(pytz.timezone('America/Los_Angeles')).isoformat()
    }
    
    cursor.execute("""
        INSERT INTO division_snapshots (league_id, snapshot_type, snapshot_data)
        VALUES (%s, 'division_toggle', %s)
        ON CONFLICT (league_id, snapshot_type) DO UPDATE
        SET snapshot_data = EXCLUDED.snapshot_data, created_at = CURRENT_TIMESTAMP
    """, (league_id, json.dumps(snapshot)))
    
    # Auto-split players: first half to Division I (top), second half to Division II (bottom)
    # Division I gets fewer players if odd number (e.g., 9 players = 4 top, 5 bottom)
    mid = len(players) // 2
    div1_players = players[:mid]  # Top division (fewer players)
    div2_players = players[mid:]  # Bottom division (more players)
    
    for player_id, _ in div1_players:
        cursor.execute("UPDATE players SET division = 1 WHERE id = %s", (player_id,))
    
    for player_id, _ in div2_players:
        cursor.execute("UPDATE players SET division = 2 WHERE id = %s", (player_id,))
    
    # Enable division mode (not yet confirmed or locked)
    cursor.execute("""
        UPDATE leagues 
        SET division_mode = TRUE, division_confirmed_at = NULL, division_locked = FALSE
        WHERE id = %s
    """, (league_id,))
    
    conn.commit()
    
    logging.info(f"Division mode enabled for league {league_id}: {len(div1_players)} in Div I, {len(div2_players)} in Div II")
    
    return {
        'success': True,
        'division_1_count': len(div1_players),
        'division_2_count': len(div2_players)
    }


def _disable_division_mode(league_id, cursor, conn, was_locked):
    """Disable division mode: revert players to no-division state"""
    
    # If divisions were locked (weeks completed), handle season reset
    if was_locked:
        # Find the higher season number between the two divisions
        cursor.execute("""
            SELECT MAX(current_season) FROM division_seasons WHERE league_id = %s
        """, (league_id,))
        row = cursor.fetchone()
        higher_season = row[0] if row and row[0] else 1
        
        # Get regular season count to calculate unified season number
        cursor.execute("""
            SELECT COALESCE(MAX(season_number), 0) FROM season_winners
            WHERE league_id = %s AND division IS NULL
        """, (league_id,))
        regular_count = cursor.fetchone()[0]
        unified_season = higher_season + regular_count
        
        # Delete weekly winners for that unified season
        # Division weekly winners are stored with division column set
        cursor.execute("""
            DELETE FROM weekly_winners
            WHERE league_id = %s AND division IS NOT NULL
        """, (league_id,))
        
        # Note: Incomplete division seasons will show as "Closed" in the display logic
        # We don't insert placeholder entries because player_id has a NOT NULL constraint
        
        logging.info(f"Division mode disabled after lock for league {league_id}: reset season {unified_season}, weekly winners cleared")
    
    # Restore player divisions to NULL
    cursor.execute("""
        UPDATE players 
        SET division = NULL, division_immunity = FALSE, division_joined_week = NULL
        WHERE league_id = %s
    """, (league_id,))
    
    # Disable division mode
    cursor.execute("""
        UPDATE leagues 
        SET division_mode = FALSE, division_confirmed_at = NULL, division_locked = FALSE
        WHERE id = %s
    """, (league_id,))
    
    # Clean up division seasons and boundaries
    cursor.execute("DELETE FROM division_seasons WHERE league_id = %s", (league_id,))
    cursor.execute("DELETE FROM division_season_boundaries WHERE league_id = %s", (league_id,))
    
    # Clean up snapshot
    cursor.execute("DELETE FROM division_snapshots WHERE league_id = %s AND snapshot_type = 'division_toggle'", (league_id,))
    
    conn.commit()
    
    logging.info(f"Division mode disabled for league {league_id}")
    
    return {'success': True}


def assign_player_division(league_id, player_id, division):
    """
    Move a player to a different division (1 or 2).
    Only allowed before division mode is locked.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if locked
        cursor.execute("SELECT division_locked FROM leagues WHERE id = %s", (league_id,))
        row = cursor.fetchone()
        if row and row[0]:
            return {'success': False, 'error': 'Divisions are locked. A week has already been completed. Reset Season to rearrange players.'}
        
        # Validate division
        if division not in (1, 2):
            return {'success': False, 'error': 'Division must be 1 or 2'}
        
        # Update player
        cursor.execute("""
            UPDATE players SET division = %s
            WHERE id = %s AND league_id = %s AND active = TRUE
        """, (division, player_id, league_id))
        
        if cursor.rowcount == 0:
            return {'success': False, 'error': 'Player not found or not active'}
        
        conn.commit()
        return {'success': True}
    
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        cursor.close()
        conn.close()


def confirm_division_mode(league_id):
    """
    Confirm division mode setup. Creates division season entries.
    After confirmation, players can still be moved until the first week completes (locked).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verify division mode is enabled
        cursor.execute("SELECT division_mode, division_confirmed_at FROM leagues WHERE id = %s", (league_id,))
        row = cursor.fetchone()
        if not row or not row[0]:
            return {'success': False, 'error': 'Division mode is not enabled'}
        
        # Verify both divisions have players
        cursor.execute("""
            SELECT division, COUNT(*) FROM players
            WHERE league_id = %s AND active = TRUE AND division IS NOT NULL
            GROUP BY division
        """, (league_id,))
        div_counts = {r[0]: r[1] for r in cursor.fetchall()}
        
        if 1 not in div_counts or div_counts[1] < 2:
            return {'success': False, 'error': 'Division I needs at least 2 players'}
        if 2 not in div_counts or div_counts[2] < 2:
            return {'success': False, 'error': 'Division II needs at least 2 players'}
        
        pacific = pytz.timezone('America/Los_Angeles')
        now = datetime.now(pacific)
        
        # Get current week
        current_week = calculate_wordle_number(get_week_start_date())
        
        # Initialize division seasons for both divisions
        for div in (1, 2):
            cursor.execute("""
                INSERT INTO division_seasons (league_id, division, current_season, season_start_week)
                VALUES (%s, %s, 1, %s)
                ON CONFLICT (league_id, division) DO UPDATE
                SET current_season = 1, season_start_week = EXCLUDED.season_start_week,
                    updated_at = CURRENT_TIMESTAMP
            """, (league_id, div, current_week))
            
            cursor.execute("""
                INSERT INTO division_season_boundaries (league_id, division, season_number, start_week, end_week)
                VALUES (%s, %s, 1, %s, NULL)
                ON CONFLICT (league_id, division, season_number) DO UPDATE
                SET start_week = EXCLUDED.start_week, end_week = NULL
            """, (league_id, div, current_week))
        
        # Set joined_week for all players
        cursor.execute("""
            UPDATE players SET division_joined_week = %s
            WHERE league_id = %s AND active = TRUE AND division IS NOT NULL
        """, (current_week, league_id))
        
        # Mark as confirmed
        cursor.execute("""
            UPDATE leagues SET division_confirmed_at = %s WHERE id = %s
        """, (now, league_id))
        
        conn.commit()
        
        logging.info(f"Division mode confirmed for league {league_id}: Div I={div_counts.get(1, 0)}, Div II={div_counts.get(2, 0)}")
        
        return {
            'success': True,
            'division_1_count': div_counts.get(1, 0),
            'division_2_count': div_counts.get(2, 0)
        }
    
    except Exception as e:
        conn.rollback()
        logging.error(f"Error confirming division mode: {e}")
        return {'success': False, 'error': str(e)}
    finally:
        cursor.close()
        conn.close()


def reset_division_seasons(league_id):
    """
    Reset seasons for divisions - wipes weekly winners under division mode,
    resets both division season counters to 1, allows player rearrangement.
    Uses similar logic to existing reset_current_season.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verify division mode is on
        cursor.execute("SELECT division_mode FROM leagues WHERE id = %s", (league_id,))
        row = cursor.fetchone()
        if not row or not row[0]:
            return {'success': False, 'error': 'Division mode is not enabled'}
        
        # Snapshot current state for revert
        cursor.execute("""
            SELECT id, name, division, division_immunity, division_joined_week
            FROM players WHERE league_id = %s AND active = TRUE
        """, (league_id,))
        player_state = [{'id': r[0], 'name': r[1], 'division': r[2], 'immunity': r[3], 'joined_week': r[4]} 
                       for r in cursor.fetchall()]
        
        cursor.execute("""
            SELECT division, current_season, season_start_week
            FROM division_seasons WHERE league_id = %s
        """, (league_id,))
        div_seasons = [{'division': r[0], 'current_season': r[1], 'season_start_week': r[2]} 
                      for r in cursor.fetchall()]
        
        cursor.execute("""
            SELECT division, season_number, start_week, end_week
            FROM division_season_boundaries WHERE league_id = %s
        """, (league_id,))
        div_boundaries = [{'division': r[0], 'season_number': r[1], 'start_week': r[2], 'end_week': r[3]} 
                         for r in cursor.fetchall()]
        
        # Get division weekly winners for snapshot
        cursor.execute("""
            SELECT league_id, week_wordle_number, player_id, player_name, score, division
            FROM weekly_winners
            WHERE league_id = %s AND division IS NOT NULL
        """, (league_id,))
        div_weekly_winners = [{'league_id': r[0], 'week': r[1], 'player_id': r[2], 
                              'player_name': r[3], 'score': r[4], 'division': r[5]} 
                             for r in cursor.fetchall()]
        
        # Get division season winners for snapshot
        cursor.execute("""
            SELECT league_id, season_number, player_id, wins, completed_date, division
            FROM season_winners
            WHERE league_id = %s AND division IS NOT NULL
        """, (league_id,))
        div_season_winners = [{'league_id': r[0], 'season_number': r[1], 'player_id': r[2],
                              'wins': r[3], 'completed_date': r[4].isoformat() if r[4] else None, 
                              'division': r[5]} 
                             for r in cursor.fetchall()]
        
        snapshot = {
            'player_state': player_state,
            'division_seasons': div_seasons,
            'division_boundaries': div_boundaries,
            'weekly_winners': div_weekly_winners,
            'season_winners': div_season_winners,
            'reset_at': datetime.now(pytz.timezone('America/Los_Angeles')).isoformat()
        }
        
        cursor.execute("""
            INSERT INTO division_snapshots (league_id, snapshot_type, snapshot_data)
            VALUES (%s, 'division_reset', %s)
            ON CONFLICT (league_id, snapshot_type) DO UPDATE
            SET snapshot_data = EXCLUDED.snapshot_data, created_at = CURRENT_TIMESTAMP
        """, (league_id, json.dumps(snapshot)))
        
        # Delete division weekly winners
        cursor.execute("DELETE FROM weekly_winners WHERE league_id = %s AND division IS NOT NULL", (league_id,))
        
        # Delete division season winners
        cursor.execute("DELETE FROM season_winners WHERE league_id = %s AND division IS NOT NULL", (league_id,))
        
        # Reset division season boundaries
        cursor.execute("DELETE FROM division_season_boundaries WHERE league_id = %s", (league_id,))
        
        # Get current week for fresh start
        current_week = calculate_wordle_number(get_week_start_date())
        
        # Reset both division seasons to Season 1
        for div in (1, 2):
            cursor.execute("""
                INSERT INTO division_seasons (league_id, division, current_season, season_start_week)
                VALUES (%s, %s, 1, %s)
                ON CONFLICT (league_id, division) DO UPDATE
                SET current_season = 1, season_start_week = %s, updated_at = CURRENT_TIMESTAMP
            """, (league_id, div, current_week, current_week))
            
            cursor.execute("""
                INSERT INTO division_season_boundaries (league_id, division, season_number, start_week, end_week)
                VALUES (%s, %s, 1, %s, NULL)
                ON CONFLICT (league_id, division, season_number) DO UPDATE
                SET start_week = EXCLUDED.start_week, end_week = NULL
            """, (league_id, div, current_week))
        
        # Clear immunity and reset joined_week for all players
        cursor.execute("""
            UPDATE players 
            SET division_immunity = FALSE, division_joined_week = %s
            WHERE league_id = %s AND active = TRUE AND division IS NOT NULL
        """, (current_week, league_id))
        
        # Unlock divisions so players can be rearranged
        cursor.execute("""
            UPDATE leagues SET division_locked = FALSE WHERE id = %s
        """, (league_id,))
        
        conn.commit()
        
        logging.info(f"Division seasons reset for league {league_id}")
        
        return {'success': True}
    
    except Exception as e:
        conn.rollback()
        logging.error(f"Error resetting division seasons: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}
    finally:
        cursor.close()
        conn.close()


def get_division_season_info(league_id, division):
    """Get current season info for a specific division"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT current_season, season_start_week
            FROM division_seasons
            WHERE league_id = %s AND division = %s
        """, (league_id, division))
        row = cursor.fetchone()
        
        if not row:
            return {'current_season': 1, 'season_start_week': None}
        
        return {
            'current_season': row[0],
            'season_start_week': row[1]
        }
    finally:
        cursor.close()
        conn.close()


def get_division_weekly_wins(league_id, division):
    """Get weekly wins in the current division season"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        season_info = get_division_season_info(league_id, division)
        season_start = season_info['season_start_week']
        
        if not season_start:
            return {}
        
        cursor.execute("""
            SELECT player_name, COUNT(*) as wins
            FROM weekly_winners
            WHERE league_id = %s AND division = %s AND week_wordle_number >= %s
            GROUP BY player_name
            ORDER BY wins DESC
        """, (league_id, division, season_start))
        
        return {row[0]: row[1] for row in cursor.fetchall()}
    finally:
        cursor.close()
        conn.close()


def get_division_season_total(league_id, division, player_name):
    """
    Calculate Season Total for a player in a division.
    Season Total = sum of all weekly best-5 scores in the current division season.
    Returns None if player is immune (just promoted/relegated).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if player is immune
        cursor.execute("""
            SELECT division_immunity FROM players
            WHERE name = %s AND league_id = %s AND active = TRUE
        """, (player_name, league_id))
        row = cursor.fetchone()
        if row and row[0]:
            return None  # Immune - will display as "Immune"
        
        season_info = get_division_season_info(league_id, division)
        season_start = season_info['season_start_week']
        
        if not season_start:
            return 0
        
        # Sum all weekly winner scores for this player in the current season
        cursor.execute("""
            SELECT COALESCE(SUM(score), 0)
            FROM weekly_winners
            WHERE league_id = %s AND division = %s 
              AND player_name = %s AND week_wordle_number >= %s
        """, (league_id, division, player_name, season_start))
        
        result = cursor.fetchone()
        return result[0] if result else 0
    finally:
        cursor.close()
        conn.close()


def get_division_season_winners(league_id):
    """Get all division season winners for a league"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT sw.season_number, sw.division, p.name, sw.wins, sw.completed_date
            FROM season_winners sw
            JOIN players p ON sw.player_id = p.id
            WHERE sw.league_id = %s AND sw.division IS NOT NULL
            ORDER BY sw.season_number DESC, sw.division
        """, (league_id,))
        
        winners = []
        for row in cursor.fetchall():
            winners.append({
                'season': row[0],
                'division': row[1],
                'name': row[2],
                'wins': row[3],
                'completed_date': row[4].strftime("%Y-%m-%d") if row[4] else None
            })
        
        return winners
    finally:
        cursor.close()
        conn.close()


def check_division_season_transition(league_id, division):
    """
    Check if a division season should transition (someone reached 3 wins).
    Called during Monday reset for division-mode leagues.
    Returns True if a season transition occurred.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get current division season info
        cursor.execute("""
            SELECT current_season, season_start_week
            FROM division_seasons
            WHERE league_id = %s AND division = %s
        """, (league_id, division))
        row = cursor.fetchone()
        
        if not row:
            logging.warning(f"No division_seasons entry for league {league_id} division {division}")
            return False
        
        current_season = row[0]
        season_start = row[1]
        
        if not season_start:
            return False
        
        # Check if season already ended
        cursor.execute("""
            SELECT end_week FROM division_season_boundaries
            WHERE league_id = %s AND division = %s AND season_number = %s
        """, (league_id, division, current_season))
        bounds = cursor.fetchone()
        if bounds and bounds[0]:
            return False  # Already ended
        
        # Count wins per player in current season
        cursor.execute("""
            SELECT player_name, COUNT(*) as win_count
            FROM weekly_winners
            WHERE league_id = %s AND division = %s AND week_wordle_number >= %s
            GROUP BY player_name
            HAVING COUNT(*) >= %s
            ORDER BY COUNT(*) DESC
        """, (league_id, division, season_start, DIVISION_WINS_FOR_SEASON))
        
        potential_winners = cursor.fetchall()
        
        if not potential_winners:
            return False
        
        # Get the winner(s)
        top_wins = potential_winners[0][1]
        winners = [row for row in potential_winners if row[1] == top_wins]
        
        logging.info(f"Division {division} Season {current_season} winner(s) in league {league_id}:")
        for name, wins in winners:
            logging.info(f"  {name} with {wins} wins")
        
        # Find last week with data
        cursor.execute("""
            SELECT MAX(week_wordle_number) FROM weekly_winners
            WHERE league_id = %s AND division = %s
        """, (league_id, division))
        last_week = cursor.fetchone()[0]
        
        # Close current season
        cursor.execute("""
            UPDATE division_season_boundaries
            SET end_week = %s
            WHERE league_id = %s AND division = %s AND season_number = %s
        """, (last_week, league_id, division, current_season))
        
        # Record season winners
        for winner_name, win_count in winners:
            cursor.execute("""
                SELECT id FROM players WHERE name = %s AND league_id = %s
            """, (winner_name, league_id))
            player_result = cursor.fetchone()
            if player_result:
                cursor.execute("""
                    INSERT INTO season_winners (league_id, player_id, season_number, wins, completed_date, division)
                    VALUES (%s, %s, %s, %s, CURRENT_DATE, %s)
                    ON CONFLICT (league_id, season_number, player_id) DO NOTHING
                """, (league_id, player_result[0], current_season, win_count, division))
        
        # Create next season
        new_season = current_season + 1
        next_start = last_week + 7
        
        cursor.execute("""
            UPDATE division_seasons
            SET current_season = %s, season_start_week = %s, updated_at = CURRENT_TIMESTAMP
            WHERE league_id = %s AND division = %s
        """, (new_season, next_start, league_id, division))
        
        cursor.execute("""
            INSERT INTO division_season_boundaries (league_id, division, season_number, start_week, end_week)
            VALUES (%s, %s, %s, %s, NULL)
            ON CONFLICT (league_id, division, season_number) DO UPDATE
            SET start_week = EXCLUDED.start_week, end_week = NULL
        """, (league_id, division, new_season, next_start))
        
        # Handle promotion/relegation
        if division == 2:
            # Division II winner gets promoted to Division I
            for winner_name, _ in winners:
                _promote_player(cursor, league_id, winner_name, next_start)
        
        conn.commit()
        
        logging.info(f"Division {division} transitioned to season {new_season} in league {league_id}")
        return True
    
    except Exception as e:
        conn.rollback()
        logging.error(f"Error checking division season transition: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        cursor.close()
        conn.close()


def check_division1_relegation(league_id):
    """
    When Division I season ends, relegate the player with worst Season Total.
    Called after check_division_season_transition for division 1.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get the season that just ended
        cursor.execute("""
            SELECT current_season, season_start_week
            FROM division_seasons
            WHERE league_id = %s AND division = 1
        """, (league_id,))
        row = cursor.fetchone()
        if not row:
            return False
        
        current_season = row[0]
        # The season that just ended is current_season - 1
        ended_season = current_season - 1
        if ended_season < 1:
            return False
        
        # Get the season boundaries for the ended season
        cursor.execute("""
            SELECT start_week, end_week FROM division_season_boundaries
            WHERE league_id = %s AND division = 1 AND season_number = %s
        """, (league_id, ended_season))
        bounds = cursor.fetchone()
        if not bounds or not bounds[1]:
            return False  # Season hasn't ended
        
        season_start = bounds[0]
        
        # Get Division I players (non-immune)
        cursor.execute("""
            SELECT p.id, p.name, p.division_immunity
            FROM players p
            WHERE p.league_id = %s AND p.division = 1 AND p.active = TRUE
        """, (league_id,))
        div1_players = cursor.fetchall()
        
        # Calculate Season Total for each non-immune player
        player_totals = []
        for player_id, player_name, is_immune in div1_players:
            if is_immune:
                continue  # Immune players can't be relegated
            
            cursor.execute("""
                SELECT COALESCE(SUM(score), 0)
                FROM weekly_winners
                WHERE league_id = %s AND division = 1 
                  AND player_name = %s AND week_wordle_number >= %s
            """, (league_id, player_name, season_start))
            total = cursor.fetchone()[0]
            
            # Count weekly wins for tiebreaker
            cursor.execute("""
                SELECT COUNT(*)
                FROM weekly_winners
                WHERE league_id = %s AND division = 1 
                  AND player_name = %s AND week_wordle_number >= %s
            """, (league_id, player_name, season_start))
            win_count = cursor.fetchone()[0]
            
            player_totals.append((player_id, player_name, total, win_count))
        
        if not player_totals:
            return False
        
        # Sort by worst Season Total (highest = worst in Wordle), then fewest wins as tiebreaker
        player_totals.sort(key=lambda x: (-x[2], x[3]))
        
        # Relegate the worst player
        worst_player_id, worst_player_name, _, _ = player_totals[0]
        
        current_week = calculate_wordle_number(get_week_start_date())
        _relegate_player(cursor, league_id, worst_player_name, current_week)
        
        conn.commit()
        
        logging.info(f"Relegated {worst_player_name} from Division I to Division II in league {league_id}")
        return True
    
    except Exception as e:
        conn.rollback()
        logging.error(f"Error checking Division I relegation: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def _promote_player(cursor, league_id, player_name, joined_week):
    """Move a player from Division II to Division I with immunity"""
    cursor.execute("""
        UPDATE players 
        SET division = 1, division_immunity = TRUE, division_joined_week = %s
        WHERE name = %s AND league_id = %s AND active = TRUE
    """, (joined_week, player_name, league_id))
    
    logging.info(f"Promoted {player_name} to Division I (immune) in league {league_id}")


def _relegate_player(cursor, league_id, player_name, joined_week):
    """Move a player from Division I to Division II with highlight"""
    cursor.execute("""
        UPDATE players 
        SET division = 2, division_immunity = FALSE, division_joined_week = %s
        WHERE name = %s AND league_id = %s AND active = TRUE
    """, (joined_week, player_name, league_id))
    
    logging.info(f"Relegated {player_name} to Division II in league {league_id}")


def clear_immunity(league_id, division):
    """
    Clear immunity for players in a division when their first full season ends.
    Called when a division season transitions.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE players 
            SET division_immunity = FALSE
            WHERE league_id = %s AND division = %s AND division_immunity = TRUE
        """, (league_id, division))
        
        affected = cursor.rowcount
        conn.commit()
        
        if affected > 0:
            logging.info(f"Cleared immunity for {affected} player(s) in league {league_id} division {division}")
        
        return affected
    finally:
        cursor.close()
        conn.close()
