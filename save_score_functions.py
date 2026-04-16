#!/usr/bin/env python3
"""
Save Score Functions

This module contains functions for saving scores to the unified scores database schema.
The unified schema uses a single scores table with player_id as a foreign key to the players table.

IMPORTANT NOTE (August 3, 2025):
----------------------------------
This system is configured to ONLY accept scores from TODAY'S Wordle.
All older scores (yesterday's Wordle and earlier) will be rejected.
This ensures the database remains clean and accurate, with no legacy/outdated scores.
----------------------------------
"""

import logging
import sqlite3
from datetime import datetime, timedelta

def get_player_id_by_name_and_league(player_name, league_id):
    """Get player ID from players table by name and league
    
    Args:
        player_name (str): Player name
        league_id (int): League ID
        
    Returns:
        int: Player ID or None if not found
    """
    conn = None
    try:
        conn = sqlite3.connect('wordle_league.db')
        cursor = conn.cursor()
        
        # Query the players table to get player_id for this name and league
        cursor.execute("""
        SELECT id FROM players 
        WHERE name = ? AND league_id = ?
        """, (player_name, league_id))
        
        result = cursor.fetchone()
        if result:
            return result[0]
        else:
            logging.warning(f"Could not find player ID for '{player_name}' in league {league_id}")
            return None
            
    except Exception as e:
        logging.error(f"Error finding player ID: {e}")
        return None
    finally:
        if conn:
            conn.close()

def save_score_to_db(player, wordle_num, score, emoji_pattern=None, league_id=1):
    """Save a score to the unified database schema
    
    Args:
        player (str): Player name
        wordle_num (int): Wordle number
        score (int or str): Score (1-6 or X)
        emoji_pattern (str, optional): Emoji pattern from the game. Defaults to None.
        league_id (int, optional): League ID. Defaults to 1.
        
    Returns:
        str: Status ('new', 'updated', 'exists', 'error', 'invalid', 'old_score')
    """
    # Get today's Wordle number
    def get_todays_wordle_number():
        # Wordle #1503 = July 31, 2025
        ref_date = datetime(2025, 7, 31).date()
        ref_wordle = 1503
        today = datetime.now().date()
        days_since_ref = (today - ref_date).days
        return ref_wordle + days_since_ref
    
    # Check if this is today's Wordle
    todays_wordle = get_todays_wordle_number()
    if wordle_num != todays_wordle:
        logging.warning(f"Rejecting score for Wordle #{wordle_num} - only today's Wordle #{todays_wordle} is allowed")
        return "old_score"
    
    # Validate the score before even connecting to the database
    if score not in (1, 2, 3, 4, 5, 6, 'X', 7): # 7 is the internal representation for X
        logging.warning(f"Invalid score value {score} for player {player}, Wordle {wordle_num}")
        return "invalid"
        
    # Validate emoji pattern for non-X scores (X scores may not have patterns)
    if score != 'X' and score != 7 and emoji_pattern:
        # Check if pattern matches the score - pattern should have exactly 'score' number of rows
        pattern_rows = [line for line in emoji_pattern.split('\n') 
                       if any(emoji in line for emoji in ['🟩', '⬛', '⬜', '🟨'])]
        
        # For scores 1-6, there should be that many rows of emoji patterns
        if len(pattern_rows) != score:
            logging.warning(f"Pattern rows ({len(pattern_rows)}) doesn't match score {score} for {player}")
            # Don't reject here as sometimes pattern formatting varies, but log it
    
    # Ensure correct data types
    try:
        wordle_num = int(wordle_num)
        if score == 'X':
            score = 7  # Convert X to internal representation
        else:
            score = int(score)
        league_id = int(league_id)
        if player is None or not isinstance(player, str):
            logging.error(f"Invalid player name: {player}")
            return "error"
    except (ValueError, TypeError) as e:
        logging.error(f"Type conversion error: {e} - Player: {player}, Wordle: {wordle_num}, Score: {score}")
        return "error"
        
    # Get player_id from players table
    player_id = get_player_id_by_name_and_league(player, league_id)
    if player_id is None:
        logging.error(f"Cannot save score: Player '{player}' not found in league {league_id}")
        return "error"
        
    logging.info(f"Saving score: Player={player} (ID: {player_id}), Wordle#{wordle_num}, Score={score}, Pattern={emoji_pattern}, League={league_id}")

    conn = None
    try:
        # Connect to the database
        conn = sqlite3.connect('wordle_league.db')
        cursor = conn.cursor()

        # Check if score exists in unified 'scores' table
        cursor.execute("""
        SELECT score, emoji_pattern FROM scores 
        WHERE player_id = ? AND wordle_number = ?
        """, (player_id, wordle_num))

        # Calculate the correct date based on the Wordle number using known reference point
        # We know for certain that Wordle #1503 corresponds to July 31, 2025
        try:
            # Clean any commas from Wordle number
            clean_wordle_num = int(str(wordle_num).replace(',', ''))
            
            # Direct mapping using hardcoded reference points
            if clean_wordle_num == 1503:
                wordle_date = datetime(2025, 7, 31).date()  # Known reference
            elif clean_wordle_num == 1502:
                wordle_date = datetime(2025, 7, 30).date()  
            elif clean_wordle_num == 1501:
                wordle_date = datetime(2025, 7, 29).date()  
            else:
                # For other wordle numbers, calculate relative to our known reference point
                reference_date = datetime(2025, 7, 31).date()  # Reference date
                reference_wordle = 1503  # Reference Wordle number
                days_offset = clean_wordle_num - reference_wordle
                wordle_date = reference_date + timedelta(days=days_offset)
                
            logging.debug(f"Mapped Wordle #{wordle_num} to date {wordle_date}")
        except Exception as e:
            logging.error(f"Error calculating date for Wordle #{wordle_num}: {e}")
            # Fall back to today's date if there's an error
            wordle_date = datetime.now().date()
        
        # Format as timestamp for the database
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        date_str = wordle_date.strftime("%Y-%m-%d")
        
        logging.info(f"Using date {wordle_date} for Wordle #{wordle_num}")
        existing_score = cursor.fetchone()

        if existing_score:
            # Score exists, check if we need to update
            db_score = int(existing_score[0])  # Ensure integer type
            if db_score != score or (emoji_pattern and existing_score[1] != emoji_pattern):
                cursor.execute("""
                UPDATE scores SET score = ?, emoji_pattern = ?, timestamp = ? 
                WHERE player_id = ? AND wordle_number = ?
                """, (score, emoji_pattern, now, player_id, wordle_num))
                conn.commit()
                logging.info(f"Updated existing score for {player} (ID: {player_id}), Wordle {wordle_num}")
                return "updated"
            else:
                logging.info(f"Score for {player} (ID: {player_id}), Wordle {wordle_num} already exists and is up to date")
                return "exists"
        else:
            # Score doesn't exist, insert it into scores table
            # Validate that non-X scores must have a proper emoji pattern
            if score != 7 and (not emoji_pattern or emoji_pattern.strip() == ''):
                logging.warning(f"Rejecting score for {player} (Wordle {wordle_num}) - valid score but missing emoji pattern")
                return "invalid_pattern"
                
            # Clean the emoji pattern before storing
            if emoji_pattern:
                # Only keep lines that contain emoji squares to remove any trailing text/dates
                clean_lines = [line for line in emoji_pattern.split('\n') 
                              if any(emoji in line for emoji in ['🟩', '⬛', '⬜', '🟨'])]
                
                # Validate that we have at least some emoji pattern lines for non-X scores
                if score != 7 and len(clean_lines) == 0:
                    logging.warning(f"Rejecting score for {player} (Wordle {wordle_num}) - no valid emoji pattern lines")
                    return "invalid_pattern"
                    
                emoji_pattern = '\n'.join(clean_lines)
                logging.info(f"Cleaned emoji pattern, now has {len(clean_lines)} lines")
                
            # Insert the new score into the unified database schema
            cursor.execute("""
            INSERT INTO scores (player_id, wordle_number, score, date, emoji_pattern, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (player_id, wordle_num, score, date_str, emoji_pattern, now))
            conn.commit()
            logging.info(f"Inserted new score for {player} (ID: {player_id}), Wordle {wordle_num}")
            return "new"
            
    except Exception as e:
        logging.error(f"Error saving score to database: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception as rollback_err:
                logging.error(f"Error rolling back transaction: {rollback_err}")
        return "error"
    finally:
        # Always close the connection in a finally block
        if conn:
            try:
                conn.close()
            except Exception as close_err:
                logging.error(f"Error closing database connection: {close_err}")
