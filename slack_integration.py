"""
Slack Integration for Wordle League
Handles incoming Slack events and outgoing messages
"""

import os
import re
import json
import hmac
import hashlib
import time
import logging
import requests
from datetime import datetime

# Slack API base URL
SLACK_API_BASE = "https://slack.com/api"

def verify_slack_signature(request_body: bytes, timestamp: str, signature: str) -> bool:
    """
    Verify that the request came from Slack using the signing secret.
    https://api.slack.com/authentication/verifying-requests-from-slack
    """
    signing_secret = os.environ.get('SLACK_SIGNING_SECRET', '')
    if not signing_secret:
        logging.error("SLACK_SIGNING_SECRET not configured")
        return False
    
    # Check timestamp to prevent replay attacks (allow 5 minutes)
    try:
        request_timestamp = int(timestamp)
        if abs(time.time() - request_timestamp) > 300:
            logging.warning("Slack request timestamp too old")
            return False
    except ValueError:
        return False
    
    # Create the signature base string
    sig_basestring = f"v0:{timestamp}:{request_body.decode('utf-8')}"
    
    # Create HMAC SHA256 signature
    my_signature = 'v0=' + hmac.new(
        signing_secret.encode('utf-8'),
        sig_basestring.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(my_signature, signature)


def send_slack_message(bot_token: str, channel_id: str, text: str, thread_ts: str = None) -> dict:
    """
    Send a message to a Slack channel.
    
    Args:
        bot_token: The bot's OAuth token for this workspace
        channel_id: The Slack channel ID (C...)
        text: Message text to send
        thread_ts: Optional thread timestamp to reply in a thread
    
    Returns:
        Slack API response dict
    """
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "channel": channel_id,
        "text": text
    }
    
    if thread_ts:
        payload["thread_ts"] = thread_ts
    
    try:
        response = requests.post(
            f"{SLACK_API_BASE}/chat.postMessage",
            headers=headers,
            json=payload,
            timeout=10
        )
        result = response.json()
        
        if not result.get("ok"):
            logging.error(f"Slack API error: {result.get('error')}")
        else:
            logging.info(f"Sent Slack message to {channel_id}: {text[:50]}...")
        
        return result
    except Exception as e:
        logging.error(f"Failed to send Slack message: {e}")
        return {"ok": False, "error": str(e)}


def send_slack_message_with_image(bot_token: str, channel_id: str, text: str, 
                                   image_url: str = None, image_bytes: bytes = None,
                                   filename: str = "image.png") -> dict:
    """
    Send a message with an image to Slack.
    Can use either a public URL or upload bytes directly.
    """
    headers = {
        "Authorization": f"Bearer {bot_token}"
    }
    
    if image_bytes:
        # Upload file directly to Slack
        try:
            response = requests.post(
                f"{SLACK_API_BASE}/files.upload",
                headers=headers,
                data={
                    "channels": channel_id,
                    "initial_comment": text,
                    "filename": filename
                },
                files={
                    "file": (filename, image_bytes, "image/png")
                },
                timeout=30
            )
            return response.json()
        except Exception as e:
            logging.error(f"Failed to upload Slack image: {e}")
            return {"ok": False, "error": str(e)}
    
    elif image_url:
        # Send message with image block
        payload = {
            "channel": channel_id,
            "text": text,
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": text}
                },
                {
                    "type": "image",
                    "image_url": image_url,
                    "alt_text": "Wordle League standings"
                }
            ]
        }
        
        try:
            response = requests.post(
                f"{SLACK_API_BASE}/chat.postMessage",
                headers={**headers, "Content-Type": "application/json"},
                json=payload,
                timeout=10
            )
            return response.json()
        except Exception as e:
            logging.error(f"Failed to send Slack image message: {e}")
            return {"ok": False, "error": str(e)}
    
    else:
        # Just send text
        return send_slack_message(bot_token, channel_id, text)


def parse_slack_wordle_score(text: str) -> tuple:
    """
    Parse a Wordle score from Slack message text.
    Returns (wordle_number, score, is_hard_mode) or (None, None, None) if not a Wordle share.
    """
    # Standard Wordle pattern: "Wordle 1,234 3/6" or "Wordle 1,234 X/6"
    pattern = r'Wordle\s+([\d,]+)\s+([1-6X])/6(\*)?'
    match = re.search(pattern, text, re.IGNORECASE)
    
    if match:
        wordle_number = int(match.group(1).replace(',', ''))
        score_str = match.group(2)
        is_hard_mode = match.group(3) == '*'
        
        if score_str.upper() == 'X':
            score = 7  # Failed attempt
        else:
            score = int(score_str)
        
        return wordle_number, score, is_hard_mode
    
    return None, None, None


def get_slack_user_info(bot_token: str, user_id: str) -> dict:
    """
    Get user info from Slack API.
    Returns user profile including display name and real name.
    """
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(
            f"{SLACK_API_BASE}/users.info",
            headers=headers,
            params={"user": user_id},
            timeout=10
        )
        result = response.json()
        
        if result.get("ok"):
            return result.get("user", {})
        else:
            logging.error(f"Failed to get Slack user info: {result.get('error')}")
            return {}
    except Exception as e:
        logging.error(f"Error getting Slack user info: {e}")
        return {}


def get_slack_channel_info(bot_token: str, channel_id: str) -> dict:
    """
    Get channel info from Slack API.
    """
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(
            f"{SLACK_API_BASE}/conversations.info",
            headers=headers,
            params={"channel": channel_id},
            timeout=10
        )
        result = response.json()
        
        if result.get("ok"):
            return result.get("channel", {})
        else:
            logging.error(f"Failed to get Slack channel info: {result.get('error')}")
            return {}
    except Exception as e:
        logging.error(f"Error getting Slack channel info: {e}")
        return {}


def handle_slack_event(event_data: dict, db_connection) -> dict:
    """
    Handle an incoming Slack event.
    
    Args:
        event_data: The event payload from Slack
        db_connection: Database connection for lookups
    
    Returns:
        Response dict with status
    """
    event = event_data.get("event", {})
    event_type = event.get("type")
    
    # Ignore bot messages to prevent loops
    if event.get("bot_id") or event.get("subtype") == "bot_message":
        return {"status": "ignored", "reason": "bot_message"}
    
    if event_type == "message":
        return handle_slack_message(event, event_data.get("team_id"), db_connection)
    
    return {"status": "ignored", "reason": f"unhandled_event_type: {event_type}"}


def handle_slack_message(event: dict, team_id: str, db_connection) -> dict:
    """
    Handle an incoming Slack message event.
    Check if it's a Wordle score and process it.
    """
    channel_id = event.get("channel")
    user_id = event.get("user")
    text = event.get("text", "")
    
    # Try to parse as Wordle score
    wordle_number, score, is_hard_mode = parse_slack_wordle_score(text)
    
    if wordle_number is None:
        return {"status": "ignored", "reason": "not_wordle_score"}
    
    # Look up the league by Slack team + channel
    cursor = db_connection.cursor()
    cursor.execute("""
        SELECT id, slack_bot_token, display_name 
        FROM leagues 
        WHERE channel_type = 'slack' 
        AND slack_team_id = %s 
        AND slack_channel_id = %s
    """, (team_id, channel_id))
    
    league_row = cursor.fetchone()
    if not league_row:
        logging.warning(f"No league found for Slack team {team_id} channel {channel_id}")
        cursor.close()
        return {"status": "error", "reason": "league_not_found"}
    
    league_id, bot_token, league_name = league_row
    
    # Look up or create player by Slack user ID
    cursor.execute("""
        SELECT id, name FROM players 
        WHERE league_id = %s AND slack_user_id = %s AND is_active = TRUE
    """, (league_id, user_id))
    
    player_row = cursor.fetchone()
    
    if not player_row:
        # New player - get their Slack profile and create them
        user_info = get_slack_user_info(bot_token, user_id)
        display_name = user_info.get("profile", {}).get("display_name") or \
                       user_info.get("profile", {}).get("real_name") or \
                       user_info.get("name", f"SlackUser_{user_id[:8]}")
        
        cursor.execute("""
            INSERT INTO players (league_id, name, slack_user_id, is_active, created_at)
            VALUES (%s, %s, %s, TRUE, NOW())
            RETURNING id, name
        """, (league_id, display_name, user_id))
        
        player_row = cursor.fetchone()
        db_connection.commit()
        logging.info(f"Created new Slack player: {display_name} in league {league_id}")
    
    player_id, player_name = player_row
    cursor.close()
    
    # Now process the score using existing score processing logic
    # Import here to avoid circular imports
    from twilio_webhook_app import process_wordle_score
    
    result = process_wordle_score(
        league_id=league_id,
        player_id=player_id,
        player_name=player_name,
        wordle_number=wordle_number,
        score=score,
        is_hard_mode=is_hard_mode,
        channel_type='slack'
    )
    
    return {"status": "processed", "result": result}


# OAuth flow helpers for Slack app installation
def exchange_slack_code(code: str, redirect_uri: str) -> dict:
    """
    Exchange an OAuth code for access tokens during Slack app installation.
    """
    client_id = os.environ.get('SLACK_CLIENT_ID')
    client_secret = os.environ.get('SLACK_CLIENT_SECRET')
    
    try:
        response = requests.post(
            f"{SLACK_API_BASE}/oauth.v2.access",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri
            },
            timeout=10
        )
        return response.json()
    except Exception as e:
        logging.error(f"Slack OAuth exchange failed: {e}")
        return {"ok": False, "error": str(e)}
