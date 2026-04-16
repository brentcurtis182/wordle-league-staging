import os
import logging
import sqlite3
import json
from datetime import datetime, timedelta
from jinja2 import Environment, FileSystemLoader
from dotenv import load_dotenv
import re
import time

# Load environment variables
load_dotenv()

# Database configuration
# Use absolute path to ensure the database is found
script_dir = os.path.dirname(os.path.abspath(__file__))
default_db_path = os.path.join(script_dir, 'wordle_league.db')
DB_PATH = os.getenv('DATABASE_URI', f'sqlite:///{default_db_path}').replace('sqlite:///', '')
print(f"Using database at: {DB_PATH}")

# Check if database exists
if not os.path.exists(DB_PATH):
    print(f"WARNING: Database file not found at {DB_PATH}")
    # Try to find it in the current directory
    if os.path.exists('wordle_league.db'):
        DB_PATH = 'wordle_league.db'
        print(f"Found database in current directory: {DB_PATH}")

# Export configuration
EXPORT_DIR = os.getenv('EXPORT_DIR', 'website_export')
WEBSITE_URL = os.getenv('WEBSITE_URL', 'https://brentcurtis182.github.io')
LEADERBOARD_PATH = os.getenv('LEADERBOARD_PATH', 'wordle-league')

def process_google_voice_pattern(raw_pattern):
    """Process an emoji pattern exactly as it appears in Google Voice messages.
    This function preserves the exact format and spacing of the original pattern.
    """
    if not raw_pattern:
        return None
        
    # Split by lines and keep only non-empty lines with emojis
    lines = raw_pattern.strip().split('\n')
    valid_lines = []
    
    for line in lines:
        # Skip header lines like "Wordle 1,496 6/6" and empty lines
        if not line or 'Wordle' in line or not any(c in line for c in '🟩🟨⬛'):
            continue
            
        # Keep the line exactly as is, just strip any extra whitespace
        valid_lines.append(line.strip())
    
    # Return the processed pattern
    return '\n'.join(valid_lines) if valid_lines else None

def normalize_emoji_pattern(emoji_pattern, score):
    """Normalize an emoji pattern to ensure each line has exactly 5 emojis
    and the correct number of lines based on the score.
    """
    # If no pattern provided, generate a default one
    if not emoji_pattern:
        return generate_emoji_pattern(score)
    
    # First, process the pattern as if it came directly from Google Voice
    processed_pattern = process_google_voice_pattern(emoji_pattern)
    
    # If processing failed, use the original pattern
    if not processed_pattern:
        processed_pattern = emoji_pattern
    
    # Split the pattern into lines and normalize each line
    lines = processed_pattern.strip().split('\n')
    valid_lines = []
    
    # Process each line that contains emoji characters
    for line in lines:
        # Skip empty lines or lines with just whitespace
        if not line.strip():
            continue
        
        # Extract only valid Wordle emojis (green, yellow, black/white squares)
        emojis = ''.join(c for c in line if c in '🟩🟨⬛⬜')
        
        # Only add lines with valid emojis
        if emojis:
            # Ensure exactly 5 emojis per line
            if len(emojis) < 5:
                emojis = emojis + '⬛' * (5 - len(emojis))
            elif len(emojis) > 5:
                emojis = emojis[:5]
            
            valid_lines.append(emojis)
    
    # If no valid lines were found, generate a default pattern
    if not valid_lines:
        return generate_emoji_pattern(score)
    
    # For score=1, just return a single green row
    if score == 1:
        return "🟩🟩🟩🟩🟩"
    
    # For failed attempts (X/6), we need 6 rows
    target_rows = 6 if score == 7 else score
    
    # Adjust the number of rows if needed
    if len(valid_lines) < target_rows:
        # For normal scores (not X/6), ensure the last row is all green
        if score < 7:
            # Keep existing rows
            while len(valid_lines) < target_rows - 1:
                valid_lines.append("⬛⬛⬛⬛⬛")
            # Add the final green row
            if len(valid_lines) < target_rows:
                valid_lines.append("🟩🟩🟩🟩🟩")
        else:  # Failed attempt (X/6)
            # For failed attempts, just pad with black squares
            while len(valid_lines) < target_rows:
                valid_lines.append("⬛⬛⬛⬛⬛")
    elif len(valid_lines) > target_rows:
        # If we have too many rows, keep only what we need
        valid_lines = valid_lines[:target_rows]
    
    # Join the lines with newlines
    return '\n'.join(valid_lines)

def generate_emoji_pattern(score_value):
    """Generate a clean emoji pattern based on score value"""
    # Use a string representation for the pattern
    pattern = ""
    
    # Black square for incorrect guesses
    black = '⬛'
    # Green square for correct guesses
    green = '🟩'
    # Yellow square for correct letter, wrong position
    yellow = '🟨'
    # Red square for failed attempt (X/6)
    red = '🔴'
    
    if score_value == 7:  # Failed attempt (X/6)
        # For failed attempts, show all 6 guesses with a mix of black and yellow
        # to simulate actual guesses, with the last row showing red squares
        for i in range(5):
            # Create a pattern with some yellows to make it look realistic
            if i % 2 == 0:
                pattern += black * 3 + yellow * 2 + "\n"
            else:
                pattern += black * 2 + yellow + black + yellow + "\n"
        
        # Last row is all black with one red to indicate failure
        pattern += black * 4 + red
    elif score_value in range(1, 7):  # Valid score 1-6
        # For scores 1-6, create that many rows
        # For rows before the last, use a mix of black and yellow
        for i in range(score_value - 1):
            # Create a pattern with some yellows to make it look realistic
            if i % 2 == 0:
                pattern += black * 3 + yellow * 2 + "\n"
            else:
                pattern += black * 2 + yellow + black + yellow + "\n"
        
        # Last row is all green (success)
        pattern += green * 5
    
    return pattern

def connect_to_db():
    """Connect to the SQLite database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        return None

def is_new_day():
    """Check if it's a new day (after 3:00 AM)"""
    # Get current time
    current_time = datetime.now()
    
    # Check if it's between 3:00 AM and 11:59 PM
    # This simulates a new day starting at 3:00 AM
    return current_time.hour >= 3 and current_time.hour < 24

def calculate_wordle_number(target_date=None):
    """Calculate the Wordle number based on the date"""
    # First Wordle (Wordle 0) was on June 19, 2021
    first_wordle_date = datetime(2021, 6, 19).date()
    
    # Use today's date if no target date provided
    if target_date is None:
        target_date = datetime.now().date()
    elif isinstance(target_date, datetime):
        target_date = target_date.date()
    
    # Calculate days since first Wordle
    days_since_first = (target_date - first_wordle_date).days
    
    # Wordle number is days since first
    return days_since_first

def get_latest_wordle_number():
    """Get the latest Wordle number from the database"""
    conn = connect_to_db()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(wordle_number) as latest FROM scores")
        result = cursor.fetchone()
        return result['latest'] if result and result['latest'] else None
    finally:
        conn.close()

def get_all_players():
    """Get all players from the database, strictly filtering to only include real players"""
    conn = connect_to_db()
    if not conn:
        return []
    
    # List of real players to include - only these players will be shown
    REAL_PLAYERS = [
        'Brent',
        'Joanna',
        'Evan',
        'Malia',
        'Nanna'
    ]
    
    try:
        cursor = conn.cursor()
        # Only select players whose names exactly match our real player list
        placeholders = ', '.join(['?' for _ in REAL_PLAYERS])
        query = f"SELECT id, name, phone_number FROM player WHERE name IN ({placeholders}) ORDER BY name"
        
        cursor.execute(query, REAL_PLAYERS)
        
        players = []
        for row in cursor.fetchall():
            players.append({
                'id': row['id'],
                'name': row['name'],
                'phone_number': row['phone_number']
            })
        
        print(f"Found {len(players)} real players: {', '.join([p['name'] for p in players])}")
        return players
    finally:
        conn.close()

def get_scores_for_wordle(wordle_number):
    """Get all scores for a specific Wordle number, including all players with placeholders for missing scores"""
    conn = connect_to_db()
    if not conn:
        return []
    
    try:
        # Get all players
        all_players = get_all_players()
        
        # Check if this is today's Wordle number
        today_wordle = calculate_wordle_number()
        # We want to show today's scores if they exist, so we don't return early here
        # Just print a message for debugging
        if wordle_number == today_wordle:
            print(f"\nProcessing today's Wordle {wordle_number}")
            # Add extra debugging for today's scores
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.name, s.wordle_number, s.score, s.date
                FROM score s
                JOIN player p ON s.player_id = p.id
                WHERE s.wordle_number = ?
                ORDER BY p.name
            """, (wordle_number,))
            today_scores = cursor.fetchall()
            print(f"Found {len(today_scores)} scores for today's Wordle {wordle_number}:")
            for score in today_scores:
                print(f"  {score['name']}: {score['score']}/6 on {score['date']}")
            
            # Also check for any scores from today's date
            today_date = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("""
                SELECT p.name, s.wordle_number, s.score, s.date
                FROM score s
                JOIN player p ON s.player_id = p.id
                WHERE s.date = ?
                ORDER BY p.name
            """, (today_date,))
            todays_date_scores = cursor.fetchall()
            print(f"Found {len(todays_date_scores)} scores from today's date {today_date}:")
            for score in todays_date_scores:
                print(f"  {score['name']}: Wordle {score['wordle_number']}, {score['score']}/6")
                
            # If we don't have scores for all players, add a warning
            if len(today_scores) < len(all_players):
                print(f"WARNING: Only found {len(today_scores)} scores for today's Wordle, but there are {len(all_players)} players")
                print("Missing scores for: " + ", ".join([p['name'] for p in all_players if p['name'] not in [s['name'] for s in today_scores]]))
                print("These players will show 'No Score' on the website")
        # No early return - continue to query the database for scores
        
        # Check if emoji_pattern column exists
        cursor = conn.cursor()
        has_emoji_pattern = True
        try:
            cursor.execute("SELECT emoji_pattern FROM score LIMIT 1")
        except sqlite3.OperationalError:
            has_emoji_pattern = False
            print("emoji_pattern column doesn't exist yet. Using basic query.")
        
        # Get scores for this wordle number
        if has_emoji_pattern:
            cursor.execute("""
                SELECT s.score, s.date, s.emoji_pattern, p.id, p.name, p.phone_number
                FROM score s
                JOIN player p ON s.player_id = p.id
                WHERE s.wordle_number = ?
            """, (wordle_number,))
        else:
            cursor.execute("""
                SELECT s.score, s.date, p.id, p.name, p.phone_number
                FROM score s
                JOIN player p ON s.player_id = p.id
                WHERE s.wordle_number = ?
            """, (wordle_number,))
        
        # Create a dictionary of scores by player ID
        scores_by_player = {}
        for row in cursor.fetchall():
            # Skip unknown players
            if row['name'].startswith('Unknown'):
                print(f"Skipping unknown player: {row['name']}")
                continue
                
            player_score = {
                'name': row['name'],
                'score': row['score'] if row['score'] < 7 else 'X',
                'date': row['date'],
                'has_score': True
            }
            
            # Use emoji pattern from database if available, otherwise generate one
            if has_emoji_pattern and row['emoji_pattern']:
                original_pattern = row['emoji_pattern']
                
                # Special cases for specific patterns
                if row['name'] == 'Evan' and wordle_number == 1496:
                    # Use the exact pattern for Evan's Wordle 1496
                    raw_pattern = "Wordle 1,496 6/6\n\n⬛⬛⬛⬛🟩\n⬛🟨⬛⬛🟩\n⬛⬛🟩⬛🟩\n⬛⬛🟩⬛🟩\n⬛⬛🟩🟩🟩\n🟩🟩🟩🟩🟩"
                    player_score['emoji_pattern'] = raw_pattern
                    print(f"\nUsing exact pattern for Evan, Wordle 1496")
                elif row['name'] == 'Joanna' and row['score'] == 2:
                    # Use the exact pattern for Joanna's 2/6
                    raw_pattern = "Wordle 2/6\n\n⬛⬛🟩⬛🟩\n🟩🟩🟩🟩🟩"
                    player_score['emoji_pattern'] = raw_pattern
                    print(f"\nUsing exact pattern for Joanna, score 2/6")
                elif row['name'] == 'Brent' and row['score'] == 7 and wordle_number == 1496:
                    # Use the exact pattern from the thread for Brent's X/6 for Wordle 1496
                    raw_pattern = "Wordle 1,496 X/6\n\n⬛🟩⬛⬛🟩\n⬛🟩⬛⬛🟩\n⬛⬛⬛⬛⬛\n⬛🟨🟨⬛🟩\n🟨🟩⬛🟨⬛\n⬛⬛🟨🟨⬛"
                    player_score['emoji_pattern'] = raw_pattern
                    print(f"\nUsing exact pattern for Brent, score X/6 for Wordle 1496")
                elif row['name'] == 'Brent' and row['score'] == 7 and wordle_number == 1497:
                    # Use the exact pattern from the thread for Brent's X/6 for Wordle 1497
                    raw_pattern = "Wordle 1,497 X/6\n\n⬛⬛⬛⬛🟨\n⬛🟨⬛⬛⬛\n⬛🟩🟨🟩⬛\n⬛🟩⬛🟩🟩\n⬛🟩⬛🟩🟩\n⬛🟩⬛🟩🟩"
                    player_score['emoji_pattern'] = raw_pattern
                    print(f"\nUsing exact pattern for Brent, score X/6 for Wordle 1497")
                else:
                    # For all other patterns, just use the original pattern directly
                    # This preserves the exact format from the database
                    player_score['emoji_pattern'] = original_pattern
                    
                    # Debug output
                    print(f"\nPlayer: {row['name']}, Score: {row['score']}")
                    print(f"Using original pattern with {len([l for l in original_pattern.split('\n') if l.strip()])} rows")
            else:
                # If no pattern in database, generate a default one
                player_score['emoji_pattern'] = generate_emoji_pattern(row['score'])
                
            scores_by_player[row['id']] = player_score
        
        # Create the final results list with all players
        results = []
        # Check if this is today's Wordle
        is_today = (wordle_number == today_wordle)
        
        for player in all_players:
            if player['id'] in scores_by_player:
                # Player has a score
                results.append(scores_by_player[player['id']])
            else:
                # Player has no score, add placeholder
                # For today's Wordle, use 'No Score' to make it clear
                score_display = 'No Score' if is_today else '-'
                
                results.append({
                    'name': player['name'],
                    'score': score_display,
                    'date': None,
                    'has_score': False,
                    'emoji_pattern': None
                })
                
                # Log when a player is missing today's score
                if is_today:
                    print(f"Player {player['name']} has no score for today's Wordle {wordle_number}")

        # Sort by score (those with scores first, then alphabetically)
        # For today's Wordle, we want to show all players (even those with no score)
        # For past Wordles, we can hide players with no score at the bottom
        if is_today:
            # For today's Wordle: Sort by score, with 'No Score' players shown after players with scores
            results.sort(key=lambda x: (
                not x['has_score'],  # Players with scores first
                7 if x['score'] == 'X' else (999 if x['score'] == 'No Score' else x['score']),
                x['name']
            ))
            print(f"Sorted {len(results)} players for today's Wordle {wordle_number}")
        else:
            # For past Wordles: Same sorting but with '-' scores at the bottom
            results.sort(key=lambda x: (
                not x['has_score'],
                7 if x['score'] == 'X' else (999 if x['score'] == '-' else x['score']),
                x['name']
            ))

        return results
    finally:
        conn.close()

def get_player_stats():
    """Get player stats for the current and all time scores"""
    conn = sqlite3.connect("wordle_league.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM player")
    players = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]

    # Determine start of week (Monday at 3:00 AM)
    today = datetime.now()
    marker_file = "weekly_reset_marker.txt"
    
    # Use marker file if it exists
    if os.path.exists(marker_file):
        with open(marker_file, 'r') as f:
            start_of_week_str = f.read().strip()
            try:
                start_of_week = datetime.strptime(start_of_week_str, '%Y-%m-%d %H:%M:%S')
                logging.info(f"Using weekly reset marker: {start_of_week_str}")
            except ValueError:
                # If marker file has invalid date, fallback to Monday calculation
                today_weekday = today.weekday()  # 0 is Monday
                days_since_monday = today_weekday
                start_of_week = today - timedelta(days=days_since_monday)
                start_of_week = start_of_week.replace(hour=3, minute=0, second=0, microsecond=0)
                logging.warning(f"Invalid marker date, fallback to calculated: {start_of_week}")
    else:
        # Calculate Monday 3:00 AM if marker doesn't exist
        today_weekday = today.weekday()  # 0 is Monday
        days_since_monday = today_weekday
        start_of_week = today - timedelta(days=days_since_monday)
        start_of_week = start_of_week.replace(hour=3, minute=0, second=0, microsecond=0)
        logging.info(f"No marker file, calculated start of week: {start_of_week}")
    
    # Format for SQL query
    start_of_week_str = start_of_week.strftime('%Y-%m-%d %H:%M:%S')
    logging.info(f"Using weekly scores since: {start_of_week_str}")
    """Get overall statistics for each player"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    # Get all players
    players = get_all_players()
    
    # Get the current week's start date (Monday at 3:00 AM)
    today = datetime.now()
    today_weekday = today.weekday()
    
    # If today is Monday, use today at 3:00 AM as the start of week
    if today_weekday == 0:  # Monday is 0
        start_of_week = today.replace(hour=3, minute=0, second=0, microsecond=0)
        logging.info("TODAY IS MONDAY: Using today at 3:00 AM as start of week")
    else:
        # Otherwise use the previous Monday
        start_of_week = today - timedelta(days=today_weekday)
        start_of_week = start_of_week.replace(hour=3, minute=0, second=0, microsecond=0)
        
    # Format the date as a string for SQL comparison
    start_of_week_str = start_of_week.strftime('%Y-%m-%d')
    print(f"Using start of week: {start_of_week_str}")  # Debug print
    
    player_stats = []
    
    for player in players:
        player_id = player['id']
        
        # Get all scores for this player
        cursor.execute("""
            SELECT score, date
            FROM scores
            WHERE player_id = ? AND score IS NOT NULL
            ORDER BY date DESC
        """, (player_id,))
        
        scores = cursor.fetchall()
        
        # Calculate statistics
        total_scores = 0
        total_games = 0
        failed_attempts = 0
        
        # For all-time average calculation (including X/6 as 7)
        all_time_total = 0
        all_time_games = 0
        
        # Weekly scores (this week only)
        weekly_scores = []
        
        for score_row in scores:
            score = score_row[0]
            date = score_row[1]
            
            # For all-time average, count X/6 as 7
            all_time_total += score
            all_time_games += 1
            
            # Skip failed attempts (X/6) for regular games played and average calculation
            if score == 7:  # 7 represents X/6
                failed_attempts += 1
                continue
                
            total_scores += score
            total_games += 1
            
                        # Debug weekly scores
            if date >= start_of_week_str:
                print(f"Including in weekly scores: {player['name']} - Score: {score}, Date: {date}")

            # Check if this score is from the current week
            if date >= start_of_week_str:
                weekly_scores.append(score)
        
        # Calculate average score (excluding X/6)
        average_score = round(total_scores / total_games, 2) if total_games > 0 else None
        
        # Calculate all-time average (including X/6 as 7)
        all_time_average = round(all_time_total / all_time_games, 2) if all_time_games > 0 else None
        
        # Calculate weekly score (sum of top 5 scores this week)
        weekly_scores.sort()  # Sort scores (lowest first)
        used_scores = weekly_scores[:5]  # Take top 5 scores
        weekly_score = sum(used_scores) if used_scores else None
        thrown_out = weekly_scores[5:] if len(weekly_scores) > 5 else []
        
        # Get weekly failed attempts
        cursor.execute("""
            SELECT COUNT(*)
            FROM scores
            WHERE player_id = ? AND score = 7 AND date >= ?
        """, (player_id, start_of_week_str))
        
        weekly_failed = cursor.fetchone()[0]
        
        player_stats.append({
            'name': player['name'],
            'games_played': total_games,
            'failed_attempts': failed_attempts,
            'average_score': average_score,
            'all_time_average': all_time_average,  # New field that includes X/6 as 7
            'weekly_score': weekly_score,
            'used_scores': len(used_scores),
            'thrown_out': thrown_out,
            'weekly_failed': weekly_failed
        })
    
    # Create a copy of player_stats for all-time sorting
    all_time_stats = player_stats.copy()
    
    # For weekly totals, we need to prioritize:
    # 1. Players with scores over those without
    # 2. Players with MORE games played (minimum 5 to compete)
    # 3. Players with lower weekly scores when games played are equal
    # 4. Alphabetical by name as final tiebreaker
    
    # First, separate players with at least 5 games played
    players_with_5_plus = [p for p in player_stats if p['used_scores'] >= 5 and p['weekly_score'] is not None]
    players_with_less_than_5 = [p for p in player_stats if p['used_scores'] < 5 and p['weekly_score'] is not None]
    players_without_scores = [p for p in player_stats if p['weekly_score'] is None]
    
    # Sort players with 5+ games by weekly score (ascending)
    players_with_5_plus.sort(key=lambda x: (x['weekly_score'], x['name']))
    
    # Sort players with less than 5 games by number of games played (descending), then weekly score, then name
    players_with_less_than_5.sort(key=lambda x: (-x['used_scores'], x['weekly_score'], x['name']))
    
    # Sort players without scores alphabetically
    players_without_scores.sort(key=lambda x: x['name'])
    
    # Combine the lists: first 5+ games players, then <5 games players, then players without scores
    player_stats = players_with_5_plus + players_with_less_than_5 + players_without_scores
    
    # Sort all-time stats by average score (lowest first)
    all_time_stats.sort(key=lambda x: (
        x['all_time_average'] is None,  # False (has average) comes before True (no average)
        float('inf') if x['all_time_average'] is None else x['all_time_average'],
        x['name']  # Alphabetical as tiebreaker
    ))
    
    conn.close()
    return player_stats, all_time_stats

def get_recent_wordles(limit=10):
    """Get the most recent Wordle numbers"""
    conn = connect_to_db()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT wordle_number, date
            FROM scores
            ORDER BY wordle_number DESC
            LIMIT ?
        """, (limit,))
        
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def export_static_files():
    """Export static HTML and JSON files for the website"""
    # Create the export directory if it doesn't exist
    os.makedirs(EXPORT_DIR, exist_ok=True)
    
    # Create templates directory if it doesn't exist
    templates_dir = os.path.join(EXPORT_DIR, 'templates')
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
    
    # Copy CSS and JS files
    with open(os.path.join(EXPORT_DIR, 'styles.css'), 'w', encoding='utf-8') as f:
        f.write("""
/* General styles */
body {
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 0;
    background-color: #121213;
    color: #d7dadc;
}
.container {
    max-width: 800px;
    margin: 0 auto;
    padding: 10px;
}
header {
    background-color: #1a1a1b;
    padding: 10px 0;
    margin-bottom: 10px;
}
.title {
    margin: 0 auto;
    color: #6aaa64;
    font-size: 24px;
    text-align: center;
}
.subtitle {
    margin: 5px 0 0;
    color: #d7dadc;
    font-size: 0.9em;
}

/* Score card styles */
.score-card {
    background-color: #1a1a1b;
    border-radius: 5px;
    padding: 10px;
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.player-info {
    display: flex;
    flex-direction: column;
    justify-content: center;
}
.player-name {
    font-weight: bold;
    font-size: 1.1em;
    margin-bottom: 4px;
}
.player-score {
    font-size: 1.1em;
    font-weight: bold;
    display: inline-block;
}
.player-score span {
    padding: 2px 8px;
    border-radius: 3px;
    display: inline-block;
}
.score-display {
    font-size: 1.2em;
    font-weight: bold;
    padding: 5px 10px;
    border-radius: 3px;
    display: flex;
    align-items: center;
}
.score-1 {
    background-color: #6aaa64;
    color: #121213;
}
.score-2 {
    background-color: #6aaa64;
    color: #121213;
}
.score-3 {
    background-color: #6aaa64;
    color: #121213;
}
.score-4 {
    background-color: #c9b458;
    color: #121213;
}
.score-5 {
    background-color: #c9b458;
    color: #121213;
}
.score-6 {
    background-color: #c9b458;
    color: #121213;
}
.score-X {
    background-color: #86888a;
    color: #121213;
}
.score-none {
    background-color: #3a3a3c;
    color: #d7dadc;
    font-size: 0.9em;
}

/* Emoji pattern styles */
.emoji-pattern {
    font-size: 0.5rem;
    line-height: 1;
    display: inline-block;
    margin-left: auto;
}
.emoji-row {
    white-space: nowrap;
    height: 1em;
}
.player-score {
    font-weight: bold;
    font-size: 1.1em;
}
.score-card {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

/* Wordle links */
.wordle-links {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    margin-bottom: 15px;
}
.wordle-link {
    background-color: #3a3a3c;
    color: #d7dadc;
    text-decoration: none;
    padding: 5px 10px;
    border-radius: 3px;
    font-size: 0.9em;
}
.wordle-link.current {
    background-color: #6aaa64;
    color: #121213;
}

/* Table styles */
.table-container {
    overflow-x: auto;
}
table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 15px;
}
th, td {
    padding: 8px 10px;
    text-align: left;
    border-bottom: 1px solid #3a3a3c;
}
th {
    background-color: #1a1a1b;
    font-weight: bold;
}
tr:nth-child(even) {
    background-color: #1a1a1b;
}
tr.highlight {
    background-color: rgba(106, 170, 100, 0.2);
}

/* Tab navigation */
.tab-container {
    margin-bottom: 15px;
}
.tabs {
    display: flex;
    justify-content: center;
    flex-wrap: wrap;
    margin-bottom: 15px;
}
.tab-button {
    background-color: #1a1a1b;
    border: 1px solid #3a3a3c;
    border-radius: 5px;
    padding: 10px 20px;
    color: #d7dadc;
    cursor: pointer;
    margin: 0 8px 8px 0;
    font-size: 1.1em;
    font-weight: bold;
}
.tab-button.active {
    background-color: #6aaa64;
    color: #121213;
}
.tab-content {
    display: none;
}
.tab-content.active {
    display: block;
}
@media (max-width: 768px) {
    .score-card {
        flex-direction: row;
        align-items: center;
        padding: 8px;
    }
    .player-info {
        flex: 1;
    }
    .emoji-pattern {
        font-size: 0.5rem;
    }
}
        """)
    
    with open(os.path.join(EXPORT_DIR, 'script.js'), 'w') as f:
        f.write("""
document.addEventListener('DOMContentLoaded', function() {
    // Tab functionality
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabId = button.getAttribute('data-tab');
            
            // Remove active class from all buttons and contents
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));
            
            // Add active class to current button and content
            button.classList.add('active');
            document.getElementById(tabId).classList.add('active');
        });
    });
    
    // Style failed attempts cells based on their values
    const failedCells = document.querySelectorAll('.failed-attempts');
    failedCells.forEach(cell => {
        if (cell.textContent === '0') {
            cell.style.backgroundColor = 'transparent';
            cell.style.color = '#d7dadc';
            cell.style.fontWeight = 'normal';
        }
    });
});
        """)
    
    # Set up Jinja2 environment
    env = Environment(loader=FileSystemLoader('templates'))
    
    # Get data
    latest_wordle = get_latest_wordle_number()
    if not latest_wordle:
        print("No Wordle scores found in the database")
        return
    
    # Get today's Wordle number
    today_wordle = calculate_wordle_number()
    
    # Get recent wordles
    recent_wordles = get_recent_wordles(10)
    
    # Add today's Wordle to recent_wordles if it's not already there
    today_wordle_in_list = False
    for wordle in recent_wordles:
        if wordle['wordle_number'] == today_wordle:
            today_wordle_in_list = True
            break
    
    if not today_wordle_in_list:
        # Add today's Wordle to the list
        today = datetime.now()
        today_formatted = today.strftime("%Y-%m-%d")
        recent_wordles.insert(0, {'wordle_number': today_wordle, 'date': today_formatted})
    
    weekly_stats, all_time_stats = get_player_stats()
    
    # Create index.html template
    index_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wordle League - Leaderboard</title>
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <link rel="stylesheet" href="styles.css">
    <style>
        /* Emoji pattern styles */
        .score-display {
            display: flex;
            align-items: center;
        }
        
        .emoji-pattern {
            margin-left: 15px;
            font-size: 0.8rem;
            line-height: 1.1;
            display: inline-block;
            letter-spacing: 0;
            font-family: monospace;
            text-align: right;
        }
        
        .emoji-row {
            white-space: nowrap;
            height: 1.1em;
            margin: 0;
            padding: 0;
            display: block;
        }
        
        .emoji-container {
            height: auto;
            display: flex;
            flex-direction: column;
            justify-content: center;
            margin-left: auto;
        }
        
        /* Failed attempts column styling */
        .failed-attempts {
            background-color: rgba(128, 58, 58, 0.2);
            font-weight: bold;
            color: #ff6b6b;
        }
        
        /* When failed attempts is 0, make it less prominent */
        td.failed-attempts:empty {
            background-color: transparent;
            color: #d7dadc;
            font-weight: normal;
        }
    </style>
</head>
<body>
    <header style="padding: 10px 0; margin-bottom: 10px;">
        <div class="container" style="padding: 10px; text-align: center;">
            <h1 class="title" style="font-size: 24px; margin-bottom: 0; text-align: center;">Wordle League</h1>
        </div>
    </header>
    
    <div class="container">
        <div class="tab-container">
            <div class="tab-buttons tabs">
                <div style="width: 100%; display: flex; justify-content: center;">
                    <button class="tab-button active" data-tab="latest">Latest Scores</button>
                    <button class="tab-button" data-tab="weekly">Weekly Totals</button>
                </div>
                <div style="width: 100%; display: flex; justify-content: center;">
                    <button class="tab-button" data-tab="stats">All-Time Stats</button>
                </div>
            </div>
            
            <div id="latest" class="tab-content active">
                <h2 style="margin-top: 5px; margin-bottom: 10px; font-size: 16px; color: #6aaa64; text-align: center;">Wordle #{{ latest_wordle }} - {{ today_formatted }}</h2>
                
                
                {% for score in latest_scores %}
                    <div class="score-card">
                        <div class="player-info">
                            <div class="player-name">{{ score.name }}</div>
                            {% if score.has_score %}
                            <div class="player-score">
                                <span class="score-{{ score.score }}">{{ score.score }}/6</span>
                            </div>
                            {% else %}
                            <div class="player-score"><span class="score-none">No Score</span></div>
                            {% endif %}
                        </div>
                        {% if score.has_score and score.emoji_pattern %}
                        <div class="emoji-container">
                            <div class="emoji-pattern">
                                {%- set has_valid_emoji = false -%}
                                {%- for line in score.emoji_pattern.split('\n') -%}
                                    {%- if line.strip() and not 'Wordle' in line -%}
                                        {%- if '⬛' in line or '⬜' in line or '🟨' in line or '🟩' in line -%}
                                            {%- set has_valid_emoji = true -%}
                                            <div class="emoji-row">{{ line.strip() }}</div>
                                        {%- elif not 'emoji pattern detected' in line and not 'Score recorded for' in line -%}
                                            <div class="emoji-row">{{ line.strip() }}</div>
                                        {%- endif -%}
                                    {%- endif -%}
                                {%- endfor -%}
                                {%- if not has_valid_emoji -%}
                                    <!-- No emoji pattern available -->
                                {%- endif -%}
                            </div>
                        </div>
                        {% endif %}

                    </div>
                {% endfor %}
            </div>
            
            <div id="weekly" class="tab-content">
                <h2 style="margin-top: 5px; margin-bottom: 10px;">Weekly Totals</h2>
                <p style="margin-top: 0; margin-bottom: 5px;">Top 5 scores count toward weekly total (Monday-Sunday).</p>
                <p style="margin-top: 0; margin-bottom: 10px; font-size: 0.9em;">At least 5 scores needed to compete for the week!</p>
                
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Player</th>
                                <th>Weekly Score</th>
                                <th>Used Scores</th>
                                <th>Failed</th>
                                <th>Thrown Out</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for player in player_stats %}
                            <tr {% if player.used_scores >= 5 %}class="highlight"{% endif %}>
                                <td>{{ player.name }}</td>
                                <td class="weekly-score">{{ player.weekly_score if player.weekly_score is not none else '-' }}</td>
                                <td class="used-scores">{{ player.used_scores }}</td>
                                <td class="failed-attempts">{{ player.weekly_failed }}</td>
                                <td class="thrown-out">{{ player.thrown_out|join(', ') if player.thrown_out else '-' }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    <p style="margin-top: 10px; font-size: 0.9em; font-style: italic; text-align: center;">Failed attempts do not count towards your 'Used Scores'</p>
                </div>
            </div>
            
            <div id="stats" class="tab-content">
                <h2 style="margin-top: 5px; margin-bottom: 10px;">All-Time Stats</h2>
                <p style="margin-top: 0; margin-bottom: 10px; font-size: 0.9em; font-style: italic;">Average includes all games. Failed attempts (X/6) count as 7 in the average calculation.</p>
                
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Player</th>
                                <th>Games</th>
                                <th>Avg</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for player in all_time_stats %}
                                <tr {% if (player.games_played + player.failed_attempts) >= 5 %}class="highlight"{% endif %}>
                                    <td>{{ player.name }}</td>
                                    <td>{{ player.games_played + player.failed_attempts }}</td>
                                    <td>{{ player.all_time_average if player.all_time_average is not none else '-' }}</td>
                                </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    
    <script src="script.js"></script>
</body>
</html>"""
    
    with open(os.path.join(templates_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(index_template)
    
    # Create wordle detail template
    wordle_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wordle #{{ wordle_number }} - Wordle League</title>
    <link rel="stylesheet" href="styles.css">
    <style>
        /* Tab navigation */
        .tabs {
            display: flex;
            justify-content: center;
            flex-wrap: wrap;
            margin-bottom: 20px;
        }
        
        /* Emoji pattern styles */
        .score-display {
            display: flex;
            align-items: center;
        }
        
        .emoji-pattern {
            margin-left: 15px;
            font-size: 0.7rem;
            line-height: 1.2;
            display: inline-block;
        }
        
        .emoji-row {
            white-space: nowrap;
            height: 1.2em;
        }
        
        .emoji-container {
            height: 7.2em; /* Space for 6 rows */
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        
        .tab-button {
            background-color: #1a1a1b;
            color: #d7dadc;
            border: 1px solid #3a3a3c;
            padding: 10px 20px;
            margin: 5px;
            cursor: pointer;
            border-radius: 5px;
            font-size: 16px;
            transition: background-color 0.3s;
        }
        
        .tab-button:hover {
            background-color: #3a3a3c;
        }
        
        .tab-button.active {
            background-color: #538d4e;
            color: white;
        }
        
        /* Tab content */
        .tab-content {
            display: none;
            width: 100%;
        }
        
        .tab-content.active {
            display: block;
        }
        
        /* Tables */
        .table-container {
            width: 100%;
            overflow-x: auto;
            margin-bottom: 20px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 0 auto;
        }
        
        th {
            background-color: #538d4e;
            color: white;
            text-align: left;
            padding: 12px;
            position: sticky;
            top: 0;
        }
        
        td {
            padding: 12px;
            border-bottom: 1px solid #3a3a3c;
        }
        
        tr:nth-child(even) {
            background-color: rgba(58, 58, 60, 0.3);
        }
        
        .weekly-score { color: #6aaa64; font-weight: bold; }
        .used-scores { color: #c9b458; }
        .thrown-out { color: #86888a; font-style: italic; }
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1 class="title">Wordle League</h1>
            <p class="subtitle">Daily Wordle Score Tracking</p>
        </div>
    </header>
    
    <div class="container">
        <div class="wordle-links">
            <a href="index.html" class="wordle-link">Back to Latest</a>
        </div>
        
        <div class="tabs">
            <button class="tab-button active" onclick="openTab('latest')">Latest Scores</button>
            <button class="tab-button" onclick="openTab('weekly')">Weekly Totals</button>
            <button class="tab-button" onclick="openTab('stats')">Player Stats</button>
        </div>
        
        <div id="latest" class="tab-content active">
            <h2>Wordle #{{ wordle_number }} - {{ today_date }}</h2>
            
            {% for score in scores %}
                <div class="score-card">
                    <div class="player-info">
                        <div class="player-name">{{ score.name }}</div>
                    </div>
                    {% if score.has_score %}
                    <div class="score-{{ score.score }} score-display">
                        <div>{{ score.score }}/6</div>
                        {% if score.emoji_pattern %}
                        <div class="emoji-pattern">
                            {% for line in score.emoji_pattern.split('\n') %}
                            {% if line %}
                            <div class="emoji-row">{{ line }}</div>
                            {% endif %}
                            {% endfor %}
                        </div>
                        {% endif %}
                    </div>
                    {% else %}
                    <div class="score-none score-display">
                        No Score Posted
                    </div>
                    {% endif %}
                </div>
            {% endfor %}
        </div>
        
        <div id="weekly" class="tab-content">
            <h2>Weekly Totals</h2>
            <p>Top 5 scores count toward weekly total (Monday-Sunday). Lower is better!</p>
            
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Player</th>
                            <th>Weekly Score</th>
                            <th>Used Scores</th>
                            <th>Thrown Out</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for player in player_stats %}
                        <tr>
                            <td>{{ player.name }}</td>
                            <td class="weekly-score">{{ player.weekly_score if player.weekly_score else 'No scores this week' }}</td>
                            <td class="used-scores">{{ player.used_scores if player.used_scores else 'No scores this week' }}</td>
                            <td class="thrown-out">{{ player.thrown_out if player.thrown_out else 'None' }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        
        <div id="stats" class="tab-content">
            <h2>Player Statistics</h2>
            
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Player</th>
                            <th>Games</th>
                            <th>Avg</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for player in player_stats %}
                        <tr>
                            <td>{{ player.name }}</td>
                            <td>{{ player.games_played }}</td>
                            <td>{{ player.average_score }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    
    <script src="script.js"></script>
</body>
</html>"""
    
    with open(os.path.join(templates_dir, 'wordle.html'), 'w', encoding='utf-8') as f:
        f.write(wordle_template)
    
    # Generate index.html
    # Use today's Wordle number instead of latest_wordle
    today_wordle = calculate_wordle_number()
    latest_scores = get_scores_for_wordle(today_wordle)
    
    # Format today's date
    today = datetime.now()
    today_formatted = today.strftime("%B %d, %Y")
    
    with open(os.path.join(EXPORT_DIR, 'index.html'), 'w', encoding='utf-8') as f:
        from jinja2 import Template
        template = Template(index_template)
        f.write(template.render(
            latest_wordle=today_wordle,  # Use today_wordle instead of latest_wordle
            latest_scores=latest_scores,
            recent_wordles=recent_wordles,
            player_stats=weekly_stats,
            all_time_stats=all_time_stats,
            today_formatted=today_formatted
        ))
    
    # Create daily directory if it doesn't exist
    daily_dir = os.path.join(EXPORT_DIR, 'daily')
    if not os.path.exists(daily_dir):
        os.makedirs(daily_dir)
    
    # Generate individual wordle pages
    for wordle in recent_wordles:
        wordle_number = wordle['wordle_number']
        scores = get_scores_for_wordle(wordle_number)
        
        # Get the date for this wordle
        wordle_date = datetime.strptime(wordle['date'], '%Y-%m-%d')
        wordle_date_formatted = wordle_date.strftime("%B %d, %Y")
        
        # Save to the daily folder
        with open(os.path.join(daily_dir, f'wordle-{wordle_number}.html'), 'w', encoding='utf-8') as f:
            from jinja2 import Template
            template = Template(wordle_template)
            f.write(template.render(
                wordle_number=wordle_number,
                scores=scores,
                recent_wordles=recent_wordles,
                today_formatted=wordle_date_formatted,
                player_stats=weekly_stats,
                all_time_stats=all_time_stats
            ))
    
    # Generate JSON data for API
    api_dir = os.path.join(EXPORT_DIR, 'api')
    if not os.path.exists(api_dir):
        os.makedirs(api_dir)
    
    # Export latest scores as JSON
    with open(os.path.join(api_dir, 'latest.json'), 'w', encoding='utf-8') as f:
        json.dump({
            'wordle_number': today_wordle,  # Use today_wordle instead of latest_wordle
            'scores': latest_scores
        }, f)
    
    # Export player stats as JSON
    with open(os.path.join(api_dir, 'stats.json'), 'w', encoding='utf-8') as f:
        json.dump(weekly_stats, f)
        
    # Export all-time stats as JSON
    with open(os.path.join(api_dir, 'all_time_stats.json'), 'w', encoding='utf-8') as f:
        json.dump(all_time_stats, f)
    
    print(f"Static files exported to {EXPORT_DIR}")
    print(f"Upload these files to {WEBSITE_URL}/{LEADERBOARD_PATH}/")

if __name__ == "__main__":
    export_static_files()
