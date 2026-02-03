"""
Discord Integration for Wordle League
Handles incoming Discord events and outgoing messages
"""

import os
import re
import json
import logging
import requests
from datetime import datetime
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

# Discord API base URL
DISCORD_API_BASE = "https://discord.com/api/v10"

def verify_discord_signature(public_key: str, signature: str, timestamp: str, body: str) -> bool:
    """
    Verify that the request came from Discord using Ed25519 signature.
    https://discord.com/developers/docs/interactions/receiving-and-responding
    """
    try:
        verify_key = VerifyKey(bytes.fromhex(public_key))
        verify_key.verify(f"{timestamp}{body}".encode(), bytes.fromhex(signature))
        return True
    except BadSignatureError:
        return False
    except Exception as e:
        logging.error(f"Discord signature verification error: {e}")
        return False


def send_discord_message(channel_id: str, text: str) -> dict:
    """
    Send a message to a Discord channel.
    
    Args:
        channel_id: The Discord channel ID
        text: Message text to send
    
    Returns:
        Discord API response dict
    """
    bot_token = os.environ.get('DISCORD_BOT_TOKEN')
    
    if not bot_token:
        logging.error("DISCORD_BOT_TOKEN not configured")
        return {"error": "Bot token not configured"}
    
    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "content": text
    }
    
    try:
        response = requests.post(
            f"{DISCORD_API_BASE}/channels/{channel_id}/messages",
            headers=headers,
            json=payload,
            timeout=10
        )
        result = response.json()
        
        if response.status_code >= 400:
            logging.error(f"Discord API error: {result}")
        else:
            logging.info(f"Sent Discord message to {channel_id}: {text[:50]}...")
        
        return result
    except Exception as e:
        logging.error(f"Failed to send Discord message: {e}")
        return {"error": str(e)}


def send_discord_message_with_image(channel_id: str, text: str,
                                     image_url: str = None, 
                                     image_bytes: bytes = None,
                                     filename: str = "standings.png") -> dict:
    """
    Send a message with an image to Discord.
    Can use either a public URL (embed) or upload bytes directly.
    """
    bot_token = os.environ.get('DISCORD_BOT_TOKEN')
    
    if not bot_token:
        logging.error("DISCORD_BOT_TOKEN not configured")
        return {"error": "Bot token not configured"}
    
    headers = {
        "Authorization": f"Bot {bot_token}"
    }
    
    if image_bytes:
        # Upload file directly
        try:
            files = {
                "file": (filename, image_bytes, "image/png")
            }
            data = {
                "content": text
            }
            
            response = requests.post(
                f"{DISCORD_API_BASE}/channels/{channel_id}/messages",
                headers=headers,
                data=data,
                files=files,
                timeout=30
            )
            return response.json()
        except Exception as e:
            logging.error(f"Failed to upload Discord image: {e}")
            return {"error": str(e)}
    
    elif image_url:
        # Send message with embed containing image
        payload = {
            "content": text,
            "embeds": [
                {
                    "image": {
                        "url": image_url
                    }
                }
            ]
        }
        
        try:
            response = requests.post(
                f"{DISCORD_API_BASE}/channels/{channel_id}/messages",
                headers={**headers, "Content-Type": "application/json"},
                json=payload,
                timeout=10
            )
            return response.json()
        except Exception as e:
            logging.error(f"Failed to send Discord embed: {e}")
            return {"error": str(e)}
    
    else:
        return send_discord_message(channel_id, text)


def parse_discord_wordle_score(content: str) -> tuple:
    """
    Parse a Wordle score from Discord message content.
    Returns (wordle_number, score, is_hard_mode, emoji_pattern) or (None, None, None, None) if not a Wordle share.
    """
    # Standard Wordle pattern: "Wordle 1,234 3/6" or "Wordle 1,234 X/6"
    pattern = r'Wordle\s+([\d,]+)\s+([1-6X])/6(\*)?'
    match = re.search(pattern, content, re.IGNORECASE)
    
    if match:
        wordle_number = int(match.group(1).replace(',', ''))
        score_str = match.group(2)
        is_hard_mode = match.group(3) == '*'
        
        if score_str.upper() == 'X':
            score = 7  # Failed attempt
        else:
            score = int(score_str)
        
        # Extract emoji pattern from the content
        emoji_pattern = extract_discord_emoji_pattern(content)
        
        return wordle_number, score, is_hard_mode, emoji_pattern
    
    return None, None, None, None


def extract_discord_emoji_pattern(text: str) -> str:
    """
    Extract emoji pattern from Discord Wordle share.
    Discord preserves Unicode emoji directly (unlike Slack which uses :emoji_name: format).
    """
    # Find all lines after the "Wordle X,XXX X/6" line that contain emoji
    lines = text.split('\n')
    emoji_lines = []
    found_header = False
    
    for line in lines:
        if 'Wordle' in line and '/6' in line:
            found_header = True
            continue
        if found_header:
            # Keep only Wordle emoji characters
            clean_line = ''.join(c for c in line if c in '🟩🟨⬛⬜')
            if clean_line:
                emoji_lines.append(clean_line)
    
    return '\n'.join(emoji_lines) if emoji_lines else ""


def get_discord_user_info(user_id: str) -> dict:
    """
    Get user info from Discord API.
    """
    bot_token = os.environ.get('DISCORD_BOT_TOKEN')
    
    if not bot_token:
        return {}
    
    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(
            f"{DISCORD_API_BASE}/users/{user_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"Failed to get Discord user info: {response.status_code}")
            return {}
    except Exception as e:
        logging.error(f"Error getting Discord user info: {e}")
        return {}


def handle_discord_interaction(interaction_data: dict, db_connection) -> dict:
    """
    Handle a Discord interaction (slash command, message component, etc.)
    
    Args:
        interaction_data: The interaction payload from Discord
        db_connection: Database connection for lookups
    
    Returns:
        Response dict to send back to Discord
    """
    interaction_type = interaction_data.get("type")
    
    # Type 1 = PING (for URL verification)
    if interaction_type == 1:
        return {"type": 1}  # PONG
    
    # Type 2 = APPLICATION_COMMAND (slash command)
    if interaction_type == 2:
        return handle_discord_slash_command(interaction_data, db_connection)
    
    return {"type": 1}


def handle_discord_slash_command(interaction_data: dict, db_connection) -> dict:
    """
    Handle a Discord slash command.
    Example: /wordle-link CODE (to link channel to league)
    """
    data = interaction_data.get("data", {})
    command_name = data.get("name")
    
    # Handle /wordle-link command for channel verification
    if command_name == "wordle-link":
        options = data.get("options", [])
        code = None
        for opt in options:
            if opt.get("name") == "code":
                code = opt.get("value")
                break
        
        if not code:
            return {
                "type": 4,
                "data": {
                    "content": "Please provide the verification code from your WordPlayLeague dashboard.",
                    "flags": 64
                }
            }
        
        channel_id = interaction_data.get("channel_id")
        guild_id = interaction_data.get("guild_id")
        
        logging.info(f"Discord /wordle-link: guild_id={guild_id}, channel_id={channel_id}, code={code}")
        
        # Look for a league with this verification code (don't require guild_id to be pre-set)
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT id, display_name, verification_code
            FROM leagues 
            WHERE channel_type = 'discord' 
            AND discord_channel_id IS NULL
            AND verification_code IS NOT NULL
        """)
        
        pending_leagues = cursor.fetchall()
        logging.info(f"Found {len(pending_leagues)} pending Discord leagues")
        
        for league_row in pending_leagues:
            league_id, league_name, verification_code = league_row
            logging.info(f"Checking league {league_id}: code={verification_code} vs input={code}")
            if verification_code and code.upper() == verification_code.upper():
                # Match! Link this channel and guild to the league
                cursor.execute("""
                    UPDATE leagues 
                    SET discord_channel_id = %s,
                        discord_guild_id = %s
                    WHERE id = %s
                """, (channel_id, guild_id, league_id))
                db_connection.commit()
                cursor.close()
                
                logging.info(f"League {league_id} linked to Discord guild {guild_id} channel {channel_id}")
                return {
                    "type": 4,
                    "data": {
                        "content": f"🎉 Success! This channel is now connected to **{league_name}**. Players can start posting their Wordle scores!"
                    }
                }
        
        cursor.close()
        return {
            "type": 4,
            "data": {
                "content": "❌ Invalid verification code. Make sure you're using the code from your WordPlayLeague dashboard.",
                "flags": 64
            }
        }
    
    if command_name == "wordle":
        # Get the score option - can be just "4" or full pasted Wordle share
        options = data.get("options", [])
        score_input = None
        for opt in options:
            if opt.get("name") == "score":
                score_input = opt.get("value")
                break
        
        if score_input is None:
            return {
                "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
                "data": {
                    "content": "Please provide your Wordle score. You can type just the number (1-6 or X) or paste your full Wordle share!",
                    "flags": 64  # Ephemeral (only visible to user)
                }
            }
        
        # Try to parse as full Wordle share first
        wordle_number, score_int, is_hard_mode, emoji_pattern = parse_discord_wordle_score(score_input)
        
        if wordle_number is None:
            # Not a full share - try as simple score (1-6 or X)
            if str(score_input).upper() == 'X':
                score_int = 7
                emoji_pattern = ""
            else:
                try:
                    score_int = int(score_input)
                    if score_int < 1 or score_int > 6:
                        return {
                            "type": 4,
                            "data": {
                                "content": "Score must be 1-6 or X. You can also paste your full Wordle share!",
                                "flags": 64
                            }
                        }
                    emoji_pattern = ""
                except ValueError:
                    return {
                        "type": 4,
                        "data": {
                            "content": "Invalid score. Use 1-6, X, or paste your full Wordle share!",
                            "flags": 64
                        }
                    }
            # Use today's Wordle number for simple scores
            from twilio_webhook_app import get_todays_wordle_number
            wordle_number = get_todays_wordle_number()
        
        # Get user and channel info
        user = interaction_data.get("member", {}).get("user", {}) or interaction_data.get("user", {})
        user_id = user.get("id")
        username = user.get("global_name") or user.get("username")
        channel_id = interaction_data.get("channel_id")
        guild_id = interaction_data.get("guild_id")
        
        # Look up league by Discord guild + channel
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT id, display_name 
            FROM leagues 
            WHERE channel_type = 'discord' 
            AND discord_guild_id = %s 
            AND discord_channel_id = %s
        """, (guild_id, channel_id))
        
        league_row = cursor.fetchone()
        if not league_row:
            cursor.close()
            return {
                "type": 4,
                "data": {
                    "content": "This channel is not connected to a Wordle League. Ask your league admin to set it up!",
                    "flags": 64
                }
            }
        
        league_id, league_name = league_row
        
        # Look up or create player
        cursor.execute("""
            SELECT id, name FROM players 
            WHERE league_id = %s AND discord_user_id = %s AND is_active = TRUE
        """, (league_id, user_id))
        
        player_row = cursor.fetchone()
        
        if not player_row:
            # Create new player
            cursor.execute("""
                INSERT INTO players (league_id, name, discord_user_id, is_active, created_at)
                VALUES (%s, %s, %s, TRUE, NOW())
                RETURNING id, name
            """, (league_id, username, user_id))
            
            player_row = cursor.fetchone()
            db_connection.commit()
            logging.info(f"Created new Discord player: {username} in league {league_id}")
        
        player_id, player_name = player_row
        cursor.close()
        
        # Process the score
        from twilio_webhook_app import process_wordle_score
        result = process_wordle_score(
            league_id=league_id,
            player_id=player_id,
            player_name=player_name,
            wordle_number=wordle_number,
            score=score_int,
            emoji_pattern=emoji_pattern,
            is_hard_mode=is_hard_mode if 'is_hard_mode' in dir() else False,
            channel_type='discord'
        )
        
        score_display = 'X' if score_int == 7 else score_int
        return {
            "type": 4,
            "data": {
                "content": f"✅ Recorded! {player_name}: Wordle #{wordle_number} - {score_display}/6"
            }
        }
    
    return {"type": 1}


def handle_discord_message(message_data: dict, db_connection) -> dict:
    """
    Handle an incoming Discord message (from Gateway events).
    Check if it's a Wordle score and process it.
    """
    content = message_data.get("content", "")
    author = message_data.get("author", {})
    channel_id = message_data.get("channel_id")
    guild_id = message_data.get("guild_id")
    
    # Ignore bot messages
    if author.get("bot"):
        return {"status": "ignored", "reason": "bot_message"}
    
    # Try to parse as Wordle score
    wordle_number, score, is_hard_mode = parse_discord_wordle_score(content)
    
    if wordle_number is None:
        return {"status": "ignored", "reason": "not_wordle_score"}
    
    user_id = author.get("id")
    username = author.get("global_name") or author.get("username")
    
    # Look up the league by Discord guild + channel
    cursor = db_connection.cursor()
    cursor.execute("""
        SELECT id, display_name 
        FROM leagues 
        WHERE channel_type = 'discord' 
        AND discord_guild_id = %s 
        AND discord_channel_id = %s
    """, (guild_id, channel_id))
    
    league_row = cursor.fetchone()
    if not league_row:
        logging.warning(f"No league found for Discord guild {guild_id} channel {channel_id}")
        cursor.close()
        return {"status": "error", "reason": "league_not_found"}
    
    league_id, league_name = league_row
    
    # Look up or create player by Discord user ID
    cursor.execute("""
        SELECT id, name FROM players 
        WHERE league_id = %s AND discord_user_id = %s AND is_active = TRUE
    """, (league_id, user_id))
    
    player_row = cursor.fetchone()
    
    if not player_row:
        # New player - create them
        cursor.execute("""
            INSERT INTO players (league_id, name, discord_user_id, is_active, created_at)
            VALUES (%s, %s, %s, TRUE, NOW())
            RETURNING id, name
        """, (league_id, username, user_id))
        
        player_row = cursor.fetchone()
        db_connection.commit()
        logging.info(f"Created new Discord player: {username} in league {league_id}")
    
    player_id, player_name = player_row
    cursor.close()
    
    # Process the score using existing logic
    from twilio_webhook_app import process_wordle_score
    
    result = process_wordle_score(
        league_id=league_id,
        player_id=player_id,
        player_name=player_name,
        wordle_number=wordle_number,
        score=score,
        is_hard_mode=is_hard_mode,
        channel_type='discord'
    )
    
    return {"status": "processed", "result": result}


# OAuth helpers for Discord bot installation
def exchange_discord_code(code: str, redirect_uri: str) -> dict:
    """
    Exchange an OAuth code for access tokens during Discord bot installation.
    """
    client_id = os.environ.get('DISCORD_CLIENT_ID')
    client_secret = os.environ.get('DISCORD_CLIENT_SECRET')
    
    try:
        response = requests.post(
            f"{DISCORD_API_BASE}/oauth2/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded"
            },
            timeout=10
        )
        return response.json()
    except Exception as e:
        logging.error(f"Discord OAuth exchange failed: {e}")
        return {"error": str(e)}


def register_discord_commands() -> dict:
    """
    Register slash commands with Discord.
    This only needs to be called once (or when commands change).
    """
    bot_token = os.environ.get('DISCORD_BOT_TOKEN')
    client_id = os.environ.get('DISCORD_CLIENT_ID')
    
    if not bot_token or not client_id:
        return {"error": "Missing bot token or client ID"}
    
    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json"
    }
    
    # Define the slash commands
    commands = [
        {
            "name": "wordle-link",
            "description": "Link this channel to your WordPlayLeague",
            "options": [
                {
                    "name": "code",
                    "description": "The verification code from your dashboard",
                    "type": 3,  # STRING
                    "required": True
                }
            ]
        },
        {
            "name": "wordle",
            "description": "Submit your Wordle score (paste full share or just the number)",
            "options": [
                {
                    "name": "score",
                    "description": "Paste your Wordle share OR just type 1-6/X",
                    "type": 3,  # STRING
                    "required": True
                }
            ]
        }
    ]
    
    try:
        # Register global commands (available in all servers)
        response = requests.put(
            f"{DISCORD_API_BASE}/applications/{client_id}/commands",
            headers=headers,
            json=commands,
            timeout=30
        )
        
        if response.status_code == 200:
            logging.info(f"Successfully registered {len(commands)} Discord commands")
            return {"success": True, "commands": response.json()}
        else:
            logging.error(f"Failed to register Discord commands: {response.text}")
            return {"error": response.text}
    except Exception as e:
        logging.error(f"Error registering Discord commands: {e}")
        return {"error": str(e)}


def get_discord_bot_guilds() -> list:
    """
    Get list of guilds (servers) the bot is in.
    """
    bot_token = os.environ.get('DISCORD_BOT_TOKEN')
    
    if not bot_token:
        return []
    
    headers = {
        "Authorization": f"Bot {bot_token}"
    }
    
    try:
        response = requests.get(
            f"{DISCORD_API_BASE}/users/@me/guilds",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        logging.error(f"Error getting bot guilds: {e}")
        return []
