#!/usr/bin/env python3
"""
Check the schema of the weekly_winners table
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from league_data_adapter import get_db_connection

def check_schema():
    """Check weekly_winners table schema"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print(f"\n{'='*60}")
    print(f"WEEKLY_WINNERS TABLE SCHEMA")
    print(f"{'='*60}")
    
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'weekly_winners'
        ORDER BY ordinal_position
    """)
    
    for row in cursor.fetchall():
        print(f"{row[0]}: {row[1]}")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    check_schema()
