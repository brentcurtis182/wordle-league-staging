#!/usr/bin/env python3
"""
GitHub Pages Publisher for Cloud Wordle League
Publishes HTML to GitHub Pages using GitHub API
"""

import os
import logging
import base64
import requests
from datetime import datetime

def get_github_credentials():
    """Get GitHub credentials from environment variables"""
    username = os.environ.get('GITHUB_USERNAME')
    token = os.environ.get('GITHUB_TOKEN')
    repo_name = os.environ.get('GITHUB_REPO_NAME', 'wordle-league')
    branch = os.environ.get('GITHUB_PAGES_BRANCH', 'gh-pages')
    
    if not username or not token:
        raise ValueError("GITHUB_USERNAME and GITHUB_TOKEN must be set in environment variables")
    
    return username, token, repo_name, branch

def publish_to_github(html_content, file_path='league6/index.html', commit_message=None, max_retries=3):
    """
    Publish HTML content to GitHub Pages using GitHub API
    
    Args:
        html_content: The HTML string to publish
        file_path: Path in the repo (e.g., 'league6/index.html')
        commit_message: Optional commit message
        max_retries: Number of retries on 409 conflict (default 3)
    
    Returns:
        bool: True if successful, False otherwise
    """
    import time
    
    try:
        username, token, repo_name, branch = get_github_credentials()
        
        if commit_message is None:
            commit_message = f"Update {file_path} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # GitHub API endpoint
        api_url = f"https://api.github.com/repos/{username}/{repo_name}/contents/{file_path}"
        
        # Headers for authentication
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # Encode content to base64 (do this once)
        content_bytes = html_content.encode('utf-8')
        content_base64 = base64.b64encode(content_bytes).decode('utf-8')
        
        for attempt in range(max_retries):
            # Check if file exists to get its SHA (required for updates)
            # Re-fetch SHA on each attempt to handle concurrent updates
            logging.info(f"Checking if {file_path} exists in {username}/{repo_name}...")
            response = requests.get(
                api_url,
                headers=headers,
                params={'ref': branch}
            )
            
            sha = None
            if response.status_code == 200:
                sha = response.json().get('sha')
                logging.info(f"File exists, SHA: {sha}")
            elif response.status_code == 404:
                logging.info(f"File does not exist, will create new file")
            else:
                logging.error(f"Error checking file: {response.status_code} - {response.text}")
                return False
            
            # Prepare the request body
            data = {
                'message': commit_message,
                'content': content_base64,
                'branch': branch
            }
            
            if sha:
                data['sha'] = sha
            
            # Make the API request
            logging.info(f"Publishing to {file_path}... (attempt {attempt + 1}/{max_retries})")
            response = requests.put(
                api_url,
                headers=headers,
                json=data
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                logging.info(f"Successfully published to GitHub!")
                logging.info(f"Commit SHA: {result['commit']['sha']}")
                logging.info(f"View at: https://{username}.github.io/{repo_name}/{file_path}")
                return True
            elif response.status_code == 409:
                # Conflict - SHA changed due to concurrent update, retry with fresh SHA
                logging.warning(f"409 Conflict on {file_path} - SHA changed, retrying... (attempt {attempt + 1}/{max_retries})")
                time.sleep(0.5 * (attempt + 1))  # Exponential backoff: 0.5s, 1s, 1.5s
                continue
            else:
                logging.error(f"Failed to publish: {response.status_code}")
                logging.error(f"Response: {response.text}")
                return False
        
        # All retries exhausted
        logging.error(f"Failed to publish {file_path} after {max_retries} attempts due to conflicts")
        return False
            
    except Exception as e:
        logging.error(f"Error publishing to GitHub: {e}")
        return False

def publish_multiple_files(files_dict, commit_message=None):
    """
    Publish multiple files to GitHub Pages
    
    Args:
        files_dict: Dict of {file_path: content}
        commit_message: Optional commit message
    
    Returns:
        bool: True if all successful, False otherwise
    """
    if commit_message is None:
        commit_message = f"Update multiple files - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    success = True
    for file_path, content in files_dict.items():
        if not publish_to_github(content, file_path, commit_message):
            success = False
            logging.error(f"Failed to publish {file_path}")
    
    return success

if __name__ == "__main__":
    # Test the publisher
    logging.basicConfig(level=logging.INFO)
    
    test_html = """<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body><h1>Test Page</h1><p>Published at {}</p></body>
</html>""".format(datetime.now())
    
    print("Testing GitHub publisher...")
    print("This will publish a test file to your GitHub Pages")
    print("Make sure GITHUB_USERNAME and GITHUB_TOKEN are set!")
    
    # Uncomment to test:
    # success = publish_to_github(test_html, 'test.html', 'Test publish from cloud deployment')
    # print(f"Result: {'Success' if success else 'Failed'}")
