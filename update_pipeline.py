#!/usr/bin/env python3
"""
Update Pipeline - Orchestrates the full update flow
Called after a score is saved to trigger HTML generation and GitHub publishing
"""

import logging
from datetime import datetime
from league_data_adapter import get_complete_league_data
from html_generator_v2 import generate_full_html
from github_publisher import publish_to_github

def run_update_pipeline(league_id=6, league_name="League 6 Beta"):
    """
    Run the complete update pipeline:
    1. Fetch data from PostgreSQL
    2. Generate HTML
    3. Publish to GitHub Pages
    
    Returns:
        dict: Status information
    """
    start_time = datetime.now()
    status = {
        'success': False,
        'steps': {},
        'errors': [],
        'duration': 0
    }
    
    try:
        # Step 1: Fetch data
        logging.info(f"[Pipeline] Step 1: Fetching data for league {league_id}")
        step_start = datetime.now()
        
        league_data = get_complete_league_data(league_id)
        
        status['steps']['fetch_data'] = {
            'success': True,
            'duration': (datetime.now() - step_start).total_seconds(),
            'details': {
                'today_wordle': league_data['today_wordle'],
                'week_range': f"{league_data['week_wordles'][0]}-{league_data['week_wordles'][6]}",
                'players': len(league_data['latest_scores']),
                'weekly_winner': league_data['weekly_winner']['name'] if league_data['weekly_winner'] else None
            }
        }
        logging.info(f"[Pipeline] Data fetched successfully in {status['steps']['fetch_data']['duration']:.2f}s")
        
        # Step 2: Generate HTML
        logging.info(f"[Pipeline] Step 2: Generating HTML")
        step_start = datetime.now()
        
        html_content = generate_full_html(league_data, league_name)
        
        status['steps']['generate_html'] = {
            'success': True,
            'duration': (datetime.now() - step_start).total_seconds(),
            'details': {
                'html_size': len(html_content)
            }
        }
        logging.info(f"[Pipeline] HTML generated successfully ({len(html_content)} chars) in {status['steps']['generate_html']['duration']:.2f}s")
        
        # Step 3: Publish to GitHub
        logging.info(f"[Pipeline] Step 3: Publishing to GitHub Pages")
        step_start = datetime.now()
        
        file_path = 'league6/index.html'
        commit_message = f"Update League 6 - Wordle #{league_data['today_wordle']}"
        
        publish_success = publish_to_github(html_content, file_path, commit_message)
        
        status['steps']['publish_github'] = {
            'success': publish_success,
            'duration': (datetime.now() - step_start).total_seconds(),
            'details': {
                'file_path': file_path
            }
        }
        
        if publish_success:
            logging.info(f"[Pipeline] Published to GitHub successfully in {status['steps']['publish_github']['duration']:.2f}s")
        else:
            logging.error(f"[Pipeline] Failed to publish to GitHub")
            status['errors'].append("GitHub publishing failed")
        
        # Overall success if all steps succeeded
        status['success'] = all(step['success'] for step in status['steps'].values())
        
    except Exception as e:
        logging.error(f"[Pipeline] Error in update pipeline: {e}")
        status['errors'].append(str(e))
        status['success'] = False
    
    status['duration'] = (datetime.now() - start_time).total_seconds()
    
    # Log summary
    if status['success']:
        logging.info(f"[Pipeline] ✅ Pipeline completed successfully in {status['duration']:.2f}s")
    else:
        logging.error(f"[Pipeline] ❌ Pipeline failed after {status['duration']:.2f}s")
        logging.error(f"[Pipeline] Errors: {', '.join(status['errors'])}")
    
    return status

if __name__ == "__main__":
    # Test the pipeline
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 60)
    print("Testing Update Pipeline")
    print("=" * 60)
    print()
    
    status = run_update_pipeline()
    
    print()
    print("=" * 60)
    print("Pipeline Results:")
    print("=" * 60)
    print(f"Success: {status['success']}")
    print(f"Duration: {status['duration']:.2f}s")
    print()
    print("Steps:")
    for step_name, step_info in status['steps'].items():
        print(f"  {step_name}: {'✅' if step_info['success'] else '❌'} ({step_info['duration']:.2f}s)")
    
    if status['errors']:
        print()
        print("Errors:")
        for error in status['errors']:
            print(f"  - {error}")
