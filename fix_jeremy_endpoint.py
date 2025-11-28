"""
Add this to twilio_webhook_app.py as a temporary endpoint to fix Jeremy's score
"""

# Add this route to your Flask app:

@app.route('/fix-jeremy', methods=['POST'])
def fix_jeremy():
    """Temporary endpoint to fix Jeremy's score"""
    try:
        from league_data_adapter import get_db_connection
        from datetime import datetime
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Find Jeremy
        cursor.execute("""
            SELECT id, name FROM players 
            WHERE league_id = 7 AND phone_number LIKE '%8587751124%'
        """)
        
        player = cursor.fetchone()
        if not player:
            return {'error': 'Jeremy not found'}, 404
        
        player_id = player[0]
        player_name = player[1]
        
        # Jeremy's correct score
        correct_score = 4
        correct_emoji = "🟩🟩⬛⬛⬛\n🟩🟩⬛⬛⬛\n🟩🟩🟩🟩⬛\n🟩🟩🟩🟩🟩"
        
        # Update scores table
        cursor.execute("""
            UPDATE scores
            SET score = %s, emoji_pattern = %s, timestamp = %s
            WHERE player_id = %s AND wordle_number = 1623
        """, (correct_score, correct_emoji, datetime.now(), player_id))
        
        # Update latest_scores table
        cursor.execute("""
            UPDATE latest_scores
            SET score = %s, emoji_pattern = %s, timestamp = %s
            WHERE player_id = %s AND wordle_number = 1623
        """, (correct_score, correct_emoji, datetime.now(), player_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'message': f'Fixed {player_name} score to 4/6 for Wordle 1623',
            'player_id': player_id
        }, 200
        
    except Exception as e:
        return {'error': str(e)}, 500
