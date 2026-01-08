#!/usr/bin/env python3
"""
Image Generator for Wordle League
Creates styled leaderboard graphics using Pillow
"""

import io
import logging
from PIL import Image, ImageDraw, ImageFont

# WordPlayLeague Color Scheme
COLORS = {
    'background': '#0d1117',       # Dark background
    'card_bg': '#161b22',          # Card background
    'primary': '#00E8DA',          # Cyan/Turquoise (main accent)
    'secondary': '#FFA64D',        # Warm Orange (secondary accent)
    'warning': '#ff6b6b',          # Red for failures
    'text_primary': '#ffffff',     # White text
    'text_secondary': '#8b949e',   # Gray text
    'border': '#30363d',           # Border color
    'row_highlight': '#00E8DA22',  # Cyan with transparency
    'gold': '#FFD700',             # Gold for 3-win players
}

def hex_to_rgb(hex_color):
    """Convert hex color to RGB tuple"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def get_font(size, bold=False):
    """Get a font - tries multiple paths for cross-platform support"""
    font_paths = [
        # Linux (Railway)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        # Windows
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        # macOS
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    
    for font_path in font_paths:
        try:
            return ImageFont.truetype(font_path, size)
        except:
            continue
    
    # Ultimate fallback
    return ImageFont.load_default()

def draw_rounded_rect(draw, coords, radius, fill=None, outline=None, width=1):
    """Draw a rounded rectangle"""
    x1, y1, x2, y2 = coords
    
    if fill:
        # Draw filled rounded rectangle
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
        draw.pieslice([x1, y1, x1 + radius * 2, y1 + radius * 2], 180, 270, fill=fill)
        draw.pieslice([x2 - radius * 2, y1, x2, y1 + radius * 2], 270, 360, fill=fill)
        draw.pieslice([x1, y2 - radius * 2, x1 + radius * 2, y2], 90, 180, fill=fill)
        draw.pieslice([x2 - radius * 2, y2 - radius * 2, x2, y2], 0, 90, fill=fill)
    
    if outline:
        # Draw outline
        draw.arc([x1, y1, x1 + radius * 2, y1 + radius * 2], 180, 270, fill=outline, width=width)
        draw.arc([x2 - radius * 2, y1, x2, y1 + radius * 2], 270, 360, fill=outline, width=width)
        draw.arc([x1, y2 - radius * 2, x1 + radius * 2, y2], 90, 180, fill=outline, width=width)
        draw.arc([x2 - radius * 2, y2 - radius * 2, x2, y2], 0, 90, fill=outline, width=width)
        draw.line([x1 + radius, y1, x2 - radius, y1], fill=outline, width=width)
        draw.line([x1 + radius, y2, x2 - radius, y2], fill=outline, width=width)
        draw.line([x1, y1 + radius, x1, y2 - radius], fill=outline, width=width)
        draw.line([x2, y1 + radius, x2, y2 - radius], fill=outline, width=width)

def generate_weekly_image(league_name, standings_data, week_date_str=None):
    """
    Generate a styled weekly standings image
    
    standings_data: list of dicts with keys:
        - name: player name
        - score: weekly score (best 5 total)
        - used: number of used scores
        - failed: number of failed attempts
        - thrown: list of thrown out scores
        - eligible: bool (has 5+ games)
    """
    # Image dimensions (optimized for mobile MMS)
    width = 380
    row_height = 36
    header_height = 65
    padding = 15
    num_players = len(standings_data)
    height = header_height + (num_players * row_height) + padding * 2 + 25
    
    # Create image
    img = Image.new('RGB', (width, height), hex_to_rgb(COLORS['background']))
    draw = ImageDraw.Draw(img)
    
    # Fonts
    title_font = get_font(18, bold=True)
    header_font = get_font(11, bold=True)
    player_font = get_font(13, bold=True)
    score_font = get_font(13)
    small_font = get_font(10)
    
    # Draw card background
    draw_rounded_rect(draw, [8, 8, width - 8, height - 8], 10, 
                      fill=hex_to_rgb(COLORS['card_bg']),
                      outline=hex_to_rgb(COLORS['border']), width=2)
    
    # Title - use week date if provided (e.g., "Week Jan 05")
    if week_date_str:
        title = f"{league_name.upper()} - Week {week_date_str}"
    else:
        title = f"{league_name.upper()} - THIS WEEK"
    draw.text((width // 2, 28), title, font=title_font, 
              fill=hex_to_rgb(COLORS['primary']), anchor="mm")
    
    # Column positions
    col_player = 20
    col_score = 160
    col_used = 220
    col_fail = 275
    col_out = 335
    
    # Column headers
    y = 48
    draw.text((col_player, y), "Player", font=header_font, fill=hex_to_rgb(COLORS['text_secondary']))
    draw.text((col_score, y), "Score", font=header_font, fill=hex_to_rgb(COLORS['text_secondary']))
    draw.text((col_used, y), "Used", font=header_font, fill=hex_to_rgb(COLORS['text_secondary']))
    draw.text((col_fail, y), "Fail", font=header_font, fill=hex_to_rgb(COLORS['text_secondary']))
    draw.text((col_out - 15, y), "Thrown Out", font=header_font, fill=hex_to_rgb(COLORS['text_secondary']))
    
    # Divider line
    y = header_height
    draw.line([(15, y), (width - 15, y)], fill=hex_to_rgb(COLORS['border']), width=1)
    
    # Player rows
    y = header_height + 5
    for i, player in enumerate(standings_data):
        row_y = y + (i * row_height)
        
        # Highlight eligible players (5+ games)
        if player.get('eligible', False):
            # Draw semi-transparent highlight
            overlay = Image.new('RGBA', (width - 30, row_height - 4), hex_to_rgb(COLORS['primary']) + (35,))
            img.paste(Image.blend(img.crop((15, row_y, width - 15, row_y + row_height - 4)).convert('RGBA'), 
                                  overlay, 0.3).convert('RGB'), (15, row_y))
            draw = ImageDraw.Draw(img)  # Refresh draw object
        
        # Player name
        name = player.get('name', 'Unknown')
        if len(name) > 10:
            name = name[:9] + "…"
        draw.text((col_player, row_y + 8), name, font=player_font, 
                  fill=hex_to_rgb(COLORS['text_primary']))
        
        # Score
        score = player.get('score')
        if score and score > 0:
            score_color = COLORS['text_primary']
            draw.text((col_score + 20, row_y + 8), str(score), font=score_font,
                      fill=hex_to_rgb(score_color))
        else:
            draw.text((col_score + 20, row_y + 8), "-", font=score_font,
                      fill=hex_to_rgb(COLORS['text_secondary']))
        
        # Used scores
        used = player.get('used', 0)
        used_color = COLORS['primary'] if used >= 5 else COLORS['text_secondary']
        draw.text((col_used + 15, row_y + 8), str(used), font=score_font,
                  fill=hex_to_rgb(used_color))
        
        # Failed
        failed = player.get('failed', 0)
        if failed > 0:
            draw.text((col_fail + 10, row_y + 8), str(failed), font=score_font,
                      fill=hex_to_rgb(COLORS['warning']))
        else:
            draw.text((col_fail + 10, row_y + 8), "-", font=score_font,
                      fill=hex_to_rgb(COLORS['text_secondary']))
        
        # Thrown out
        thrown = player.get('thrown', [])
        if thrown:
            thrown_text = ",".join(str(s) for s in thrown[:2])
            draw.text((col_out, row_y + 8), thrown_text, font=small_font,
                      fill=hex_to_rgb(COLORS['text_secondary']))
        else:
            draw.text((col_out + 5, row_y + 8), "-", font=small_font,
                      fill=hex_to_rgb(COLORS['text_secondary']))
    
    # Footer
    footer_y = height - 18
    draw.text((width // 2, footer_y), "Lower score = Better!", font=small_font,
              fill=hex_to_rgb(COLORS['text_secondary']), anchor="mm")
    
    return img

def generate_season_image(league_name, season_number, standings_data, highlight_names=None):
    """
    Generate a styled season standings image
    
    standings_data: list of dicts with keys:
        - name: player name
        - wins: number of weekly wins
    highlight_names: list of player names to highlight (e.g., players with 3 wins in contention)
    """
    if highlight_names is None:
        highlight_names = []
    
    # Filter out players with 0 wins
    standings_data = [p for p in standings_data if p.get('wins', 0) > 0]
    
    if not standings_data:
        return None  # No one has wins yet
    
    # Image dimensions - simple 2-column layout
    width = 280
    row_height = 36
    header_height = 65
    padding = 15
    num_players = len(standings_data)
    height = header_height + (num_players * row_height) + padding * 2 + 25
    
    # Create image
    img = Image.new('RGB', (width, height), hex_to_rgb(COLORS['background']))
    draw = ImageDraw.Draw(img)
    
    # Fonts
    title_font = get_font(18, bold=True)
    header_font = get_font(11, bold=True)
    player_font = get_font(13, bold=True)
    wins_font = get_font(14, bold=True)
    small_font = get_font(10)
    
    # Draw card background
    draw_rounded_rect(draw, [8, 8, width - 8, height - 8], 10,
                      fill=hex_to_rgb(COLORS['card_bg']),
                      outline=hex_to_rgb(COLORS['border']), width=2)
    
    # Title - simple, no emoji
    title = f"SEASON {season_number}"
    draw.text((width // 2, 28), title, font=title_font,
              fill=hex_to_rgb(COLORS['primary']), anchor="mm")
    
    # Column headers
    col_player = 20
    col_wins = 220
    y = 48
    draw.text((col_player, y), "Player", font=header_font, fill=hex_to_rgb(COLORS['text_secondary']))
    draw.text((col_wins - 30, y), "Weekly Wins", font=header_font, fill=hex_to_rgb(COLORS['text_secondary']))
    
    # Divider
    draw.line([(15, header_height), (width - 15, header_height)], fill=hex_to_rgb(COLORS['border']), width=1)
    
    # Player rows
    y = header_height + 5
    for i, player in enumerate(standings_data):
        row_y = y + (i * row_height)
        name = player.get('name', 'Unknown')
        wins = player.get('wins', 0)
        
        # Highlight players with 3 wins (close to winning season)
        if wins >= 3:
            overlay = Image.new('RGBA', (width - 30, row_height - 4), hex_to_rgb(COLORS['primary']) + (35,))
            img.paste(Image.blend(img.crop((15, row_y, width - 15, row_y + row_height - 4)).convert('RGBA'), 
                                  overlay, 0.3).convert('RGB'), (15, row_y))
            draw = ImageDraw.Draw(img)
        
        # Player name
        if len(name) > 12:
            name = name[:11] + "…"
        draw.text((col_player, row_y + 8), name, font=player_font,
                  fill=hex_to_rgb(COLORS['text_primary']))
        
        # Win count - centered in column
        wins_color = COLORS['primary'] if wins >= 3 else COLORS['text_primary']
        draw.text((col_wins, row_y + 8), str(wins), font=wins_font,
                  fill=hex_to_rgb(wins_color))
    
    # Footer
    footer_y = height - 18
    draw.text((width // 2, footer_y), "First to 4 wins takes the season!", font=small_font,
              fill=hex_to_rgb(COLORS['text_secondary']), anchor="mm")
    
    return img

def image_to_bytes(img, format='PNG'):
    """Convert PIL Image to bytes for sending via API"""
    buffer = io.BytesIO()
    img.save(buffer, format=format)
    buffer.seek(0)
    return buffer.getvalue()

def save_image(img, filepath):
    """Save image to file"""
    img.save(filepath)
    logging.info(f"Saved image to {filepath}")

# Test function
if __name__ == "__main__":
    # Test weekly standings
    test_weekly = [
        {'name': 'Joanna', 'score': 13, 'used': 5, 'failed': 0, 'thrown': [], 'eligible': True},
        {'name': 'Brent', 'score': 15, 'used': 5, 'failed': 1, 'thrown': [6], 'eligible': True},
        {'name': 'Nanna', 'score': 17, 'used': 5, 'failed': 0, 'thrown': [5, 6], 'eligible': True},
        {'name': 'Malia', 'score': 19, 'used': 5, 'failed': 0, 'thrown': [], 'eligible': True},
        {'name': 'Evan', 'score': 12, 'used': 4, 'failed': 0, 'thrown': [], 'eligible': False},
    ]
    
    weekly_img = generate_weekly_image("Warriorz", test_weekly, week_date_str="Jan 05")
    save_image(weekly_img, "test_weekly.png")
    print("Generated test_weekly.png")
    
    # Test season standings (Evan with 0 wins should not appear)
    test_season = [
        {'name': 'Brent', 'wins': 3},
        {'name': 'Nanna', 'wins': 3},
        {'name': 'Joanna', 'wins': 3},
        {'name': 'Malia', 'wins': 1},
        {'name': 'Evan', 'wins': 0},
    ]
    
    season_img = generate_season_image("Warriorz", 5, test_season)
    if season_img:
        save_image(season_img, "test_season.png")
        print("Generated test_season.png")
    else:
        print("No season image generated (no players with wins)")
