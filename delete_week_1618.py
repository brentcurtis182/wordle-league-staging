#!/usr/bin/env python3
"""
Delete week 1618 winners (from old manual calculation)
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from league_data_adapter import get_db_connection

def delete_week_1618():
    """Delete week 1618 and 1620 winners"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Delete week 1618 (old manual calculation for League 6)
    cursor.execute("""
        DELETE FROM weekly_winners
        WHERE week_wordle_number = 1618
    """)
    
    deleted_1618 = cursor.rowcount
    print(f"Deleted {deleted_1618} rows for week 1618")
    
    # Delete week 1620 (old manual calculation for League 7)
    cursor.execute("""
        DELETE FROM weekly_winners
        WHERE week_wordle_number = 1620
    """)
    
    deleted_1620 = cursor.rowcount
    print(f"Deleted {deleted_1620} rows for week 1620")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print("✅ Deleted old manual calculation weeks")

if __name__ == "__main__":
    delete_week_1618()
