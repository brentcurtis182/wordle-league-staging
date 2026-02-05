#!/usr/bin/env python3
"""
Test script to send Sunday race update with images to a specific league
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sunday_race_update import send_sunday_race_update

if __name__ == "__main__":
    league_id = 4  # Pickle Party
    print(f"Sending test Sunday race update with images to League {league_id}...")
    
    success = send_sunday_race_update(league_id)
    
    if success:
        print("✅ Test sent successfully! Check the Pickle Party text thread.")
    else:
        print("❌ Test failed. Check logs for errors.")
