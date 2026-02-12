"""
Message Router for Wordle League
Abstracts message sending across SMS (Twilio), Slack, and Discord
"""

import os
import logging
from typing import Optional

def send_league_message(league_id: int, text: str, media_url: str = None, 
                        media_bytes: bytes = None, db_connection=None) -> dict:
    """
    Send a message to a league's channel, regardless of platform.
    
    Args:
        league_id: The league ID
        text: Message text to send
        media_url: Optional URL to an image (for platforms that support it)
        media_bytes: Optional raw image bytes
        db_connection: Database connection (will create one if not provided)
    
    Returns:
        Result dict with status and platform-specific details
    """
    # Get database connection if not provided
    close_conn = False
    if db_connection is None:
        from twilio_webhook_app import get_db_connection
        db_connection = get_db_connection()
        close_conn = True
    
    if not db_connection:
        return {"success": False, "error": "No database connection"}
    
    try:
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT channel_type, twilio_conversation_sid, 
                   slack_team_id, slack_channel_id, slack_bot_token,
                   discord_guild_id, discord_channel_id
            FROM leagues WHERE id = %s
        """, (league_id,))
        
        row = cursor.fetchone()
        cursor.close()
        
        if not row:
            return {"success": False, "error": f"League {league_id} not found"}
        
        channel_type = row[0] or 'sms'
        
        if channel_type == 'sms':
            return _send_twilio_message(
                conversation_sid=row[1],
                text=text,
                media_url=media_url
            )
        
        elif channel_type == 'slack':
            return _send_slack_message(
                bot_token=row[4],
                channel_id=row[3],
                text=text,
                media_url=media_url,
                media_bytes=media_bytes
            )
        
        elif channel_type == 'discord':
            return _send_discord_message(
                channel_id=row[6],
                text=text,
                media_url=media_url,
                media_bytes=media_bytes
            )
        
        else:
            return {"success": False, "error": f"Unknown channel type: {channel_type}"}
    
    finally:
        if close_conn and db_connection:
            db_connection.close()


def _send_twilio_message(conversation_sid: str, text: str, media_url: str = None) -> dict:
    """Send message via Twilio Conversations API"""
    from twilio.rest import Client
    
    twilio_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    twilio_token = os.environ.get('TWILIO_AUTH_TOKEN')
    twilio_phone = os.environ.get('TWILIO_PHONE_NUMBER')
    
    if not twilio_sid or not twilio_token:
        return {"success": False, "error": "Twilio credentials not configured"}
    
    if not conversation_sid:
        return {"success": False, "error": "No Twilio conversation SID"}
    
    try:
        client = Client(twilio_sid, twilio_token)
        
        message_params = {"body": text, "author": twilio_phone}
        if media_url:
            message_params["media_sid"] = media_url  # Assumes this is a media SID
        
        message = client.conversations.v1.conversations(conversation_sid).messages.create(
            **message_params
        )
        
        logging.info(f"Sent Twilio message: {text[:50]}...")
        return {"success": True, "platform": "sms", "message_sid": message.sid}
    
    except Exception as e:
        logging.error(f"Twilio send failed: {e}")
        return {"success": False, "error": str(e)}


def _send_slack_message(bot_token: str, channel_id: str, text: str,
                        media_url: str = None, media_bytes: bytes = None) -> dict:
    """Send message via Slack API"""
    from slack_integration import send_slack_message, send_slack_message_with_image
    
    if not bot_token or not channel_id:
        return {"success": False, "error": "Slack credentials not configured"}
    
    try:
        if media_url or media_bytes:
            result = send_slack_message_with_image(
                bot_token=bot_token,
                channel_id=channel_id,
                text=text,
                image_url=media_url,
                image_bytes=media_bytes
            )
        else:
            result = send_slack_message(
                bot_token=bot_token,
                channel_id=channel_id,
                text=text
            )
        
        if result.get("ok"):
            return {"success": True, "platform": "slack", "ts": result.get("ts")}
        else:
            return {"success": False, "error": result.get("error")}
    
    except Exception as e:
        logging.error(f"Slack send failed: {e}")
        return {"success": False, "error": str(e)}


def _send_discord_message(channel_id: str, text: str,
                          media_url: str = None, media_bytes: bytes = None) -> dict:
    """Send message via Discord API"""
    from discord_integration import send_discord_message, send_discord_message_with_image
    
    if not channel_id:
        return {"success": False, "error": "Discord channel not configured"}
    
    try:
        if media_url or media_bytes:
            result = send_discord_message_with_image(
                channel_id=channel_id,
                text=text,
                image_url=media_url,
                image_bytes=media_bytes
            )
        else:
            result = send_discord_message(
                channel_id=channel_id,
                text=text
            )
        
        if result.get("id"):
            return {"success": True, "platform": "discord", "message_id": result.get("id")}
        else:
            return {"success": False, "error": result.get("message", "Unknown error")}
    
    except Exception as e:
        logging.error(f"Discord send failed: {e}")
        return {"success": False, "error": str(e)}


def get_league_channel_type(league_id: int, db_connection=None) -> Optional[str]:
    """Get the channel type for a league (sms, slack, discord)"""
    close_conn = False
    if db_connection is None:
        from twilio_webhook_app import get_db_connection
        db_connection = get_db_connection()
        close_conn = True
    
    if not db_connection:
        return None
    
    try:
        cursor = db_connection.cursor()
        cursor.execute("SELECT channel_type FROM leagues WHERE id = %s", (league_id,))
        row = cursor.fetchone()
        cursor.close()
        return row[0] if row else 'sms'
    finally:
        if close_conn and db_connection:
            db_connection.close()
