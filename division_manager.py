#!/usr/bin/env python3
"""
Division Manager for Wordle League
Handles all division mode operations: toggle, assign players, confirm, reset, revert,
promotion/relegation, and division-aware season management.
"""

import os
import json
import logging
import random
from datetime import datetime
import pytz
from league_data_adapter import get_db_connection, calculate_wordle_number, get_week_start_date, get_league_min_scores

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
    
    if len(players) < 6:
        return {'success': False, 'error': 'Need at least 6 active players for division mode'}
    
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
    
    # Revert weekly winners division back to NULL so they appear in regular season standings
    if not was_locked:
        cursor.execute("""
            UPDATE weekly_winners SET division = NULL
            WHERE league_id = %s AND division IS NOT NULL
        """, (league_id,))
        logging.info(f"Division mode disabled before lock for league {league_id}: reverted weekly winners to regular season")
    
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
        
        # Get the current regular season number and start week so divisions continue from the same season
        cursor.execute("""
            SELECT ls.current_season, s.start_week FROM league_seasons ls
            LEFT JOIN seasons s ON s.league_id = ls.league_id AND s.season_number = ls.current_season
            WHERE ls.league_id = %s
        """, (league_id,))
        reg_season_row = cursor.fetchone()
        # Use regular season number and start week if available
        current_regular_season = reg_season_row[0] if reg_season_row and reg_season_row[0] else 1
        division_start_week = reg_season_row[1] if reg_season_row and reg_season_row[1] else current_week
        
        logging.info(f"Division mode confirm: using regular season {current_regular_season}, start_week {division_start_week}")
        
        # Initialize division seasons for both divisions (continue from current regular season)
        for div in (1, 2):
            cursor.execute("""
                INSERT INTO division_seasons (league_id, division, current_season, season_start_week)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (league_id, division) DO UPDATE
                SET current_season = %s, season_start_week = EXCLUDED.season_start_week,
                    updated_at = CURRENT_TIMESTAMP
            """, (league_id, div, current_regular_season, division_start_week, current_regular_season))
            
            cursor.execute("""
                INSERT INTO division_season_boundaries (league_id, division, season_number, start_week, end_week)
                VALUES (%s, %s, %s, %s, NULL)
                ON CONFLICT (league_id, division, season_number) DO UPDATE
                SET start_week = EXCLUDED.start_week, end_week = NULL
            """, (league_id, div, current_regular_season, division_start_week))
        
        # Carry over existing weekly wins: update weekly_winners from the current season
        # to set the division based on each player's assigned division
        cursor.execute("""
            SELECT name, division FROM players
            WHERE league_id = %s AND active = TRUE AND division IS NOT NULL
        """, (league_id,))
        player_div_map = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Update weekly winners from this season that have no division set
        for player_name, div_num in player_div_map.items():
            cursor.execute("""
                UPDATE weekly_winners
                SET division = %s
                WHERE league_id = %s AND player_name = %s
                  AND week_wordle_number >= %s AND division IS NULL
            """, (div_num, league_id, player_name, division_start_week))
        
        carried_over = sum(1 for _ in player_div_map)
        logging.info(f"Division mode confirm: carried over weekly wins for {carried_over} players from week {division_start_week}")
        
        # Set joined_week for all players
        cursor.execute("""
            UPDATE players SET division_joined_week = %s
            WHERE league_id = %s AND active = TRUE AND division IS NOT NULL
        """, (division_start_week, league_id))
        
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
    Reset seasons for divisions - wipes only in-progress weekly wins,
    preserves completed season winners, advances both divisions to the next
    season number, and unlocks divisions for player rearrangement.
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
        
        # Get current season info for each division so we only wipe in-progress data
        cursor.execute("""
            SELECT division, current_season, season_start_week
            FROM division_seasons WHERE league_id = %s
        """, (league_id,))
        current_seasons = {r[0]: {'season': r[1], 'start_week': r[2]} for r in cursor.fetchall()}
        
        # Wipe weekly winners from BOTH divisions' current in-progress seasons
        for div, info in current_seasons.items():
            if info['start_week']:
                cursor.execute("""
                    DELETE FROM weekly_winners
                    WHERE league_id = %s AND division = %s AND week_wordle_number >= %s
                """, (league_id, div, info['start_week']))

        # DO NOT delete season_winners — completed season winners are preserved

        # Target season = whichever division is highest (they may differ if lapping)
        current_week = calculate_wordle_number(get_week_start_date())
        target_season = max((info['season'] for info in current_seasons.values()), default=1)

        for div, info in current_seasons.items():
            if info['season'] < target_season:
                # This division is behind — close its boundary as "Closed" (no winner)
                # and advance it to match the leading division
                cursor.execute("""
                    UPDATE division_season_boundaries
                    SET end_week = %s
                    WHERE league_id = %s AND division = %s AND season_number = %s AND end_week IS NULL
                """, (current_week, league_id, div, info['season']))

                # Set this division to the target season
                cursor.execute("""
                    UPDATE division_seasons
                    SET current_season = %s, season_start_week = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE league_id = %s AND division = %s
                """, (target_season, current_week, league_id, div))

                # Create the new season boundary
                cursor.execute("""
                    INSERT INTO division_season_boundaries (league_id, division, season_number, start_week, end_week)
                    VALUES (%s, %s, %s, %s, NULL)
                    ON CONFLICT (league_id, division, season_number) DO UPDATE
                    SET start_week = EXCLUDED.start_week, end_week = NULL
                """, (league_id, div, target_season, current_week))

                logging.info(f"Div {div} was on season {info['season']}, advanced to {target_season} (closed as no winner)")
            else:
                # This division is already at the target season — just restart it
                # (wipe happened above, boundary stays open, season number unchanged)
                cursor.execute("""
                    UPDATE division_seasons
                    SET season_start_week = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE league_id = %s AND division = %s
                """, (current_week, league_id, div))

                # Update the boundary start_week for the fresh start
                cursor.execute("""
                    UPDATE division_season_boundaries
                    SET start_week = %s
                    WHERE league_id = %s AND division = %s AND season_number = %s AND end_week IS NULL
                """, (current_week, league_id, div, info['season']))
        
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
        min_scores = get_league_min_scores(league_id, conn=conn)

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

                try:
                    from twilio_webhook_app import forward_season_winner_to_staging
                    forward_season_winner_to_staging(league_id, winner_name, current_season, win_count, division)
                except Exception:
                    pass

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
        
        # Handle promotion (Division II → Division I)
        if division == 2:
            # Get configurable promoted_count
            cursor.execute("SELECT COALESCE(promoted_count, 1) FROM leagues WHERE id = %s", (league_id,))
            promoted_count = cursor.fetchone()[0]

            # Season winners always get promoted
            promoted_names = [name for name, _ in winners]
            randomized_names = {}  # name -> {'tied_with': [...], 'tied_score': N}

            if len(promoted_names) < promoted_count:
                # Need more players promoted beyond the winner(s)
                # Get remaining Div II players and calculate true season totals from raw scores
                winner_name_set = set(promoted_names)
                cursor.execute("""
                    SELECT p.id, p.name FROM players p
                    WHERE p.league_id = %s AND p.division = 2 AND p.active = TRUE
                """, (league_id,))
                div2_players = cursor.fetchall()

                candidates = []
                for pid, pname in div2_players:
                    if pname in winner_name_set:
                        continue

                    # Get all raw scores in the ended season
                    cursor.execute("""
                        SELECT s.wordle_number, s.score FROM scores s
                        WHERE s.player_id = %s AND s.wordle_number >= %s AND s.wordle_number <= %s
                        ORDER BY s.wordle_number
                    """, (pid, season_start, last_week))

                    # Group by week, sum best-N per week
                    week_scores = {}
                    for wn, sc in cursor.fetchall():
                        ws = wn - ((wn - season_start) % 7)
                        if ws not in week_scores:
                            week_scores[ws] = []
                        week_scores[ws].append(sc)

                    season_total = 0
                    w = season_start
                    while w <= last_week:
                        scores_in_week = week_scores.get(w, [])
                        valid = sorted([s for s in scores_in_week if s < 7])
                        season_total += sum(valid[:min_scores]) if valid else 0
                        w += 7

                    # Get win count for tiebreaker
                    cursor.execute("""
                        SELECT COUNT(*) FROM weekly_winners
                        WHERE league_id = %s AND division = 2
                          AND player_name = %s AND week_wordle_number >= %s
                          AND week_wordle_number <= %s
                    """, (league_id, pname, season_start, last_week))
                    win_count = cursor.fetchone()[0]

                    candidates.append((pname, season_total, win_count))
                    logging.info(f"  Promotion candidate: {pname} - season_total={season_total}, wins={win_count}")

                # Sort: best (lowest) season total first, then most wins
                candidates.sort(key=lambda x: (x[1], -x[2]))
                spots_remaining = promoted_count - len(promoted_names)

                i = 0
                while spots_remaining > 0 and i < len(candidates):
                    current_total = candidates[i][1]
                    current_wins = candidates[i][2]

                    # Check for tie at this position
                    tied = [candidates[i]]
                    j = i + 1
                    while j < len(candidates) and candidates[j][1] == current_total:
                        tied.append(candidates[j])
                        j += 1

                    if len(tied) <= spots_remaining:
                        # All tied players can be promoted
                        for t in tied:
                            promoted_names.append(t[0])
                            spots_remaining -= 1
                        i = j
                    else:
                        # More tied players than spots - use weekly wins as tiebreaker
                        tied.sort(key=lambda x: -x[2])  # Most wins first

                        # Check if tiebreaker resolves it
                        k = 0
                        while spots_remaining > 0 and k < len(tied):
                            current_win_count = tied[k][2]
                            win_tied = [tied[k]]
                            m = k + 1
                            while m < len(tied) and tied[m][2] == current_win_count:
                                win_tied.append(tied[m])
                                m += 1

                            if len(win_tied) <= spots_remaining:
                                for wt in win_tied:
                                    promoted_names.append(wt[0])
                                    spots_remaining -= 1
                                k = m
                            else:
                                # Tie — random draw to break it
                                all_tied_names = [wt[0] for wt in win_tied]
                                drawn = random.sample(win_tied, spots_remaining)
                                for wt in drawn:
                                    promoted_names.append(wt[0])
                                    others = [n for n in all_tied_names if n != wt[0]]
                                    randomized_names[wt[0]] = {'tied_with': others, 'tied_score': current_total}
                                    spots_remaining -= 1
                                logging.info(f"Promotion random draw in league {league_id}: {[d[0] for d in drawn]} selected from tied {all_tied_names} (score={current_total}, wins={current_win_count})")
                                break
                        break

            for name in promoted_names:
                _promote_player(cursor, league_id, name, next_start)
                is_random = name in randomized_names
                info = randomized_names.get(name, {})
                _log_movement(cursor, league_id, name, 'promotion', current_season, 2,
                              randomized=is_random,
                              tied_with=', '.join(info['tied_with']) if is_random else None,
                              tied_score=info.get('tied_score'))

            logging.info(f"Promoted {len(promoted_names)} player(s) from Div II to Div I in league {league_id}: {promoted_names}")
        
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
    When Division I season ends, relegate the player with worst performance.
    Called after check_division_season_transition for division 1.
    
    Relegation priority:
    1. Season winner is EXEMPT from relegation regardless of missed weeks.
    2. Players with missed weeks (< league's min_weekly_scores valid scores)
       are relegated before players with no missed weeks.
    3. Among players with missed weeks, the one with MORE missed weeks is relegated.
    4. If tied on missed weeks, the player with the worst (highest) Season Total
       is relegated.
    5. If no one has missed weeks, worst Season Total is relegated (original logic).
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        min_scores = get_league_min_scores(league_id, conn=conn)
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
        season_end = bounds[1]
        
        # Identify the season winner(s) so they are exempt from relegation
        cursor.execute("""
            SELECT p.name
            FROM season_winners sw
            JOIN players p ON sw.player_id = p.id
            WHERE sw.league_id = %s AND sw.division = 1 AND sw.season_number = %s
        """, (league_id, ended_season))
        season_winner_names = {r[0] for r in cursor.fetchall()}
        
        # Get Division I players (non-immune)
        cursor.execute("""
            SELECT p.id, p.name, p.division_immunity
            FROM players p
            WHERE p.league_id = %s AND p.division = 1 AND p.active = TRUE
        """, (league_id,))
        div1_players = cursor.fetchall()
        
        # Calculate stats for each eligible-for-relegation player
        player_stats = []
        for player_id, player_name, is_immune in div1_players:
            if is_immune:
                continue  # Immune players can't be relegated
            if player_name in season_winner_names:
                continue  # Season winner is exempt from relegation
            
            # Get all scores in the ended season to calculate missed weeks AND season total
            cursor.execute("""
                SELECT s.wordle_number, s.score
                FROM scores s
                WHERE s.player_id = %s
                  AND s.wordle_number >= %s AND s.wordle_number <= %s
                ORDER BY s.wordle_number
            """, (player_id, season_start, season_end))
            
            # Group scores by week
            week_scores = {}
            for wn, sc in cursor.fetchall():
                ws = wn - ((wn - season_start) % 7)
                if ws not in week_scores:
                    week_scores[ws] = []
                week_scores[ws].append(sc)
            
            # Count missed weeks AND calculate true season total (best-N per week, ALL weeks)
            missed = 0
            total = 0
            w = season_start
            while w <= season_end:
                scores_in_week = week_scores.get(w, [])
                valid = sorted([s for s in scores_in_week if s < 7])
                valid_count = len(valid)
                if valid_count < min_scores:
                    missed += 1
                # Season total = sum of best-N from each week (even partial weeks count)
                best_n = sum(valid[:min_scores]) if valid else 0
                total += best_n
                w += 7
            
            # Count weekly wins for tiebreaker
            cursor.execute("""
                SELECT COUNT(*)
                FROM weekly_winners
                WHERE league_id = %s AND division = 1 
                  AND player_name = %s AND week_wordle_number >= %s
                  AND week_wordle_number <= %s
            """, (league_id, player_name, season_start, season_end))
            win_count = cursor.fetchone()[0]
            
            player_stats.append((player_id, player_name, total, win_count, missed))
            logging.info(f"  Relegation candidate: {player_name} - missed_weeks={missed}, season_total={total}, wins={win_count}")
        
        if not player_stats:
            logging.info(f"No eligible players for relegation in league {league_id} (all immune or season winners)")
            return False
        
        # Get configurable relegated_count
        cursor.execute("SELECT COALESCE(relegated_count, 1) FROM leagues WHERE id = %s", (league_id,))
        relegated_count = cursor.fetchone()[0]
        
        # Sort: most missed weeks first, then worst (highest) season total, then fewest wins
        player_stats.sort(key=lambda x: (-x[4], -x[2], x[3]))
        
        relegated_names = []
        randomized_names = {}  # name -> {'tied_with': [...], 'tied_score': N}
        spots_remaining = relegated_count

        i = 0
        while spots_remaining > 0 and i < len(player_stats):
            current = player_stats[i]
            current_key = (current[4], current[2], current[3])  # (missed, total, wins)

            # Find all players tied on the same relegation criteria
            tied = [current]
            j = i + 1
            while j < len(player_stats):
                candidate = player_stats[j]
                candidate_key = (candidate[4], candidate[2], candidate[3])
                if candidate_key == current_key:
                    tied.append(candidate)
                    j += 1
                else:
                    break

            if len(tied) <= spots_remaining:
                # All tied players get relegated
                for t in tied:
                    relegated_names.append(t[1])
                    spots_remaining -= 1
                i = j
            else:
                # Tie — random draw to break it
                all_tied_names = [t[1] for t in tied]
                drawn = random.sample(tied, spots_remaining)
                for t in drawn:
                    relegated_names.append(t[1])
                    others = [n for n in all_tied_names if n != t[1]]
                    randomized_names[t[1]] = {'tied_with': others, 'tied_score': current[2]}
                    spots_remaining -= 1
                logging.info(f"Relegation random draw in league {league_id}: {[d[1] for d in drawn]} selected from tied {all_tied_names} (missed={current[4]}, total={current[2]}, wins={current[3]})")
                break

        current_week = calculate_wordle_number(get_week_start_date())
        for name in relegated_names:
            _relegate_player(cursor, league_id, name, current_week)
            is_random = name in randomized_names
            info = randomized_names.get(name, {})
            _log_movement(cursor, league_id, name, 'relegation', ended_season, 1,
                          randomized=is_random,
                          tied_with=', '.join(info['tied_with']) if is_random else None,
                          tied_score=info.get('tied_score'))

        conn.commit()
        
        logging.info(f"Relegated {len(relegated_names)} player(s) from Div I to Div II in league {league_id}: {relegated_names}")
        return True
    
    except Exception as e:
        conn.rollback()
        logging.error(f"Error checking Division I relegation: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def _log_movement(cursor, league_id, player_name, movement_type, season_number,
                   division, randomized=False, tied_with=None, tied_score=None):
    """Record a promotion/relegation event in division_movements."""
    try:
        cursor.execute("""
            INSERT INTO division_movements
                (league_id, player_name, movement_type, season_number, division,
                 randomized, tied_with, tied_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (league_id, player_name, movement_type, season_number, division,
              randomized, tied_with, tied_score))
    except Exception as e:
        logging.warning(f"Failed to log division movement: {e}")


def _promote_player(cursor, league_id, player_name, joined_week):
    """Move a player from Division II to Division I with immunity"""
    cursor.execute("""
        UPDATE players 
        SET division = 1, division_immunity = TRUE, division_joined_week = %s
        WHERE name = %s AND league_id = %s AND active = TRUE
    """, (joined_week, player_name, league_id))
    
    logging.info(f"Promoted {player_name} to Division I (immune) in league {league_id}")


def _relegate_player(cursor, league_id, player_name, joined_week):
    """Move a player from Division I to Division II with immunity (orange highlight)"""
    cursor.execute("""
        UPDATE players 
        SET division = 2, division_immunity = TRUE, division_joined_week = %s
        WHERE name = %s AND league_id = %s AND active = TRUE
    """, (joined_week, player_name, league_id))
    
    logging.info(f"Relegated {player_name} to Division II (immune) in league {league_id}")


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


