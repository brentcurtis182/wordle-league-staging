#!/usr/bin/env python3
"""
Local testing script - Generate HTML locally and optionally publish
Usage:
  python test_local.py 6           # Generate HTML for League 6, save to file
  python test_local.py 7 --publish # Generate and publish BellyUp
"""

import sys
import os
from league_data_adapter import get_complete_league_data
from html_generator_v2 import generate_full_html

def test_local(league_id, publish=False):
    """Test HTML generation locally"""
    
    # League names
    league_names = {
        6: 'League 6 Beta',
        7: 'BellyUp'
    }
    league_name = league_names.get(league_id, f'League {league_id}')
    
    print(f"Fetching data for {league_name}...")
    league_data = get_complete_league_data(league_id)
    
    print(f"Generating HTML...")
    html_content = generate_full_html(league_data, league_name)
    
    # Save to local file
    output_file = f"test_league{league_id}.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"[OK] HTML saved to: {output_file}")
    print(f"  Size: {len(html_content)} chars")
    print(f"  Open in browser to test!")
    
    if publish:
        print(f"\nPublishing to GitHub...")
        from update_pipeline import run_update_pipeline
        result = run_update_pipeline(league_id, league_name)
        if result['success']:
            print(f"[OK] Published successfully!")
        else:
            print(f"[ERROR] Publish failed: {result.get('errors')}")
    
    return html_content

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_local.py <league_id> [--publish]")
        sys.exit(1)
    
    league_id = int(sys.argv[1])
    publish = '--publish' in sys.argv
    
    test_local(league_id, publish)
