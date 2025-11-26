#!/usr/bin/env python3
"""Manually trigger update for a league"""
import sys
from update_tables_cloud import run_full_update_for_league

if __name__ == "__main__":
    league_id = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    print(f"Triggering update for league {league_id}...")
    success = run_full_update_for_league(league_id)
    print("Done!" if success else "Failed!")
