#!/usr/bin/env python3
"""
One-time script to update existing leagues with their Twilio conversation SIDs
"""
import os
import psycopg2

DATABASE_URL = os.environ.get('DATABASE_URL')

# Mapping of league_id to conversation_sid
LEAGUE_CONVERSATION_SIDS = {
    1: 'CHb7aa3110769f42a19cea7a2be9c644d2',  # Warriorz
    3: 'CHc8f0c4a776f14bcd96e7c8838a6aec13',  # PAL
    4: 'CHed74f2e9f16240e9a578f96299c395ce',  # Party
    7: 'CH4438ff5531514178bb13c5c0e96d5579',  # BellyUp
}

def update_conversation_sids():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    for league_id, conversation_sid in LEAGUE_CONVERSATION_SIDS.items():
        print(f"Updating league {league_id} with conversation_sid {conversation_sid}")
        cursor.execute("""
            UPDATE leagues 
            SET twilio_conversation_sid = %s 
            WHERE id = %s
        """, (conversation_sid, league_id))
    
    conn.commit()
    cursor.close()
    conn.close()
    print("Done!")

if __name__ == '__main__':
    update_conversation_sids()
