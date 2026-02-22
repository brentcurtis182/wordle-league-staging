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
    import os
    
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    font_paths = [
        # Bundled font in same directory (preferred)
        os.path.join(script_dir, "Marcellus-Regular.ttf"),
        os.path.join(script_dir, "fonts", "Marcellus-Regular.ttf"),
        # Linux (Railway) - try multiple locations
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        # Windows
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        # macOS
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    
    for font_path in font_paths:
        try:
            font = ImageFont.truetype(font_path, size)
            logging.info(f"Loaded font: {font_path} at size {size}")
            return font
        except Exception as e:
            continue
    
    # Ultimate fallback - but log a warning
    logging.warning(f"Could not load any truetype font at size {size}, using default bitmap font")
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
        - used: number of used scores (for highlighting eligible players)
        - thrown: list of thrown out scores
        - eligible: bool (has 5+ games)
    """
    # Image dimensions - MUCH BIGGER for mobile readability
    width = 550
    row_height = 60
    header_height = 95
    padding = 20
    num_players = len(standings_data)
    height = header_height + (num_players * row_height) + padding * 2 + 40
    
    # Create image
    img = Image.new('RGB', (width, height), hex_to_rgb(COLORS['background']))
    draw = ImageDraw.Draw(img)
    
    # Fonts - EVEN BIGGER for mobile
    title_font = get_font(38, bold=True)
    header_font = get_font(24, bold=True)
    player_font = get_font(30, bold=True)
    score_font = get_font(30)
    small_font = get_font(18)
    
    # Draw card background
    draw_rounded_rect(draw, [8, 8, width - 8, height - 8], 12, 
                      fill=hex_to_rgb(COLORS['card_bg']),
                      outline=hex_to_rgb(COLORS['border']), width=2)
    
    # Title - use week date if provided (e.g., "Week Jan 05")
    if week_date_str:
        title = f"{league_name.upper()} - Week {week_date_str}"
    else:
        title = f"{league_name.upper()} - THIS WEEK"
    draw.text((width // 2, 45), title, font=title_font, 
              fill=hex_to_rgb(COLORS['primary']), anchor="mm")
    
    # Column positions - 3 columns only: Player, Score, Thrown Out
    col_player = 30
    col_score = 250  # Centered more
    col_out = 400
    
    # Column headers
    y = 70
    draw.text((col_player, y), "Player", font=header_font, fill=hex_to_rgb(COLORS['text_secondary']))
    draw.text((col_score, y), "Score", font=header_font, fill=hex_to_rgb(COLORS['text_secondary']))
    draw.text((col_out, y), "Thrown Out", font=header_font, fill=hex_to_rgb(COLORS['text_secondary']))
    
    # Divider line
    y = header_height
    draw.line([(25, y), (width - 25, y)], fill=hex_to_rgb(COLORS['border']), width=2)
    
    # Player rows
    y = header_height + 10
    for i, player in enumerate(standings_data):
        row_y = y + (i * row_height)
        
        # Highlight eligible players (5+ games) with cyan background
        if player.get('eligible', False):
            # Draw semi-transparent highlight
            overlay = Image.new('RGBA', (width - 40, row_height - 8), hex_to_rgb(COLORS['primary']) + (45,))
            img.paste(Image.blend(img.crop((20, row_y, width - 20, row_y + row_height - 8)).convert('RGBA'), 
                                  overlay, 0.4).convert('RGB'), (20, row_y))
            draw = ImageDraw.Draw(img)  # Refresh draw object
        
        # Player name
        name = player.get('name', 'Unknown')
        if len(name) > 12:
            name = name[:11] + "…"
        draw.text((col_player, row_y + 15), name, font=player_font, 
                  fill=hex_to_rgb(COLORS['text_primary']))
        
        # Score - show current total even if not eligible
        score = player.get('score')
        if score is not None and score > 0:
            draw.text((col_score + 30, row_y + 15), str(score), font=score_font,
                      fill=hex_to_rgb(COLORS['text_primary']))
        else:
            draw.text((col_score + 30, row_y + 15), "-", font=score_font,
                      fill=hex_to_rgb(COLORS['text_secondary']))
        
        # Thrown out
        thrown = player.get('thrown', [])
        if thrown:
            thrown_text = ", ".join(str(s) for s in thrown[:3])
            if len(thrown) > 3:
                thrown_text += "…"
            draw.text((col_out, row_y + 15), thrown_text, font=score_font,
                      fill=hex_to_rgb(COLORS['text_secondary']))
        else:
            draw.text((col_out + 20, row_y + 15), "-", font=score_font,
                      fill=hex_to_rgb(COLORS['text_secondary']))
    
    # Footer
    footer_y = height - 28
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
    original_count = len(standings_data)
    standings_data = [p for p in standings_data if p.get('wins', 0) > 0]
    logging.info(f"Season image: {original_count} players, {len(standings_data)} with wins")
    
    if not standings_data:
        logging.info("Season image: No players with wins, returning None")
        return None  # No one has wins yet
    
    # Image dimensions - MUCH BIGGER for mobile readability
    width = 450
    row_height = 60
    header_height = 95
    padding = 20
    num_players = len(standings_data)
    height = header_height + (num_players * row_height) + padding * 2 + 40
    
    # Create image
    img = Image.new('RGB', (width, height), hex_to_rgb(COLORS['background']))
    draw = ImageDraw.Draw(img)
    
    # Fonts - EVEN BIGGER for mobile
    title_font = get_font(38, bold=True)
    header_font = get_font(24, bold=True)
    player_font = get_font(30, bold=True)
    wins_font = get_font(32, bold=True)
    small_font = get_font(18)
    
    # Draw card background
    draw_rounded_rect(draw, [8, 8, width - 8, height - 8], 12,
                      fill=hex_to_rgb(COLORS['card_bg']),
                      outline=hex_to_rgb(COLORS['border']), width=2)
    
    # Title - simple, no emoji
    title = f"SEASON {season_number}"
    draw.text((width // 2, 45), title, font=title_font,
              fill=hex_to_rgb(COLORS['primary']), anchor="mm")
    
    # Column headers
    col_player = 30
    col_wins = 300  # More centered
    y = 70
    draw.text((col_player, y), "Player", font=header_font, fill=hex_to_rgb(COLORS['text_secondary']))
    draw.text((col_wins - 30, y), "Weekly Wins", font=header_font, fill=hex_to_rgb(COLORS['text_secondary']))
    
    # Divider
    draw.line([(25, header_height), (width - 25, header_height)], fill=hex_to_rgb(COLORS['border']), width=2)
    
    # Player rows
    y = header_height + 10
    for i, player in enumerate(standings_data):
        row_y = y + (i * row_height)
        name = player.get('name', 'Unknown')
        wins = player.get('wins', 0)
        
        # Highlight players with 3 wins (close to winning season)
        if wins >= 3:
            overlay = Image.new('RGBA', (width - 40, row_height - 8), hex_to_rgb(COLORS['primary']) + (45,))
            img.paste(Image.blend(img.crop((20, row_y, width - 20, row_y + row_height - 8)).convert('RGBA'), 
                                  overlay, 0.4).convert('RGB'), (20, row_y))
            draw = ImageDraw.Draw(img)
        
        # Player name
        if len(name) > 12:
            name = name[:11] + "…"
        draw.text((col_player, row_y + 15), name, font=player_font,
                  fill=hex_to_rgb(COLORS['text_primary']))
        
        # Win count - centered in column
        wins_color = COLORS['primary'] if wins >= 3 else COLORS['text_primary']
        draw.text((col_wins, row_y + 15), str(wins), font=wins_font,
                  fill=hex_to_rgb(wins_color))
    
    # Footer
    footer_y = height - 28
    draw.text((width // 2, footer_y), "First to 4 wins takes the season!", font=small_font,
              fill=hex_to_rgb(COLORS['text_secondary']), anchor="mm")
    
    return img

def generate_division_weekly_image(league_name, div1_data, div2_data, week_date_str=None):
    """
    Generate a styled weekly standings image for division mode.
    Shows two separate division tables with colored headers.
    
    div1_data / div2_data: list of dicts with keys:
        - name, score, used, thrown, eligible, failed
    """
    width = 550
    row_height = 50
    div_header_height = 45
    header_height = 80
    section_gap = 20
    padding = 20
    
    num_div1 = len(div1_data)
    num_div2 = len(div2_data)
    
    # Calculate total height
    height = (header_height +
              div_header_height + (num_div1 * row_height) + 30 +
              section_gap +
              div_header_height + (num_div2 * row_height) + 30 +
              padding * 2 + 30)
    
    img = Image.new('RGB', (width, height), hex_to_rgb(COLORS['background']))
    draw = ImageDraw.Draw(img)
    
    title_font = get_font(32, bold=True)
    div_title_font = get_font(24, bold=True)
    header_font = get_font(20, bold=True)
    player_font = get_font(26, bold=True)
    score_font = get_font(26)
    small_font = get_font(16)
    
    # Draw card background
    draw_rounded_rect(draw, [8, 8, width - 8, height - 8], 12,
                      fill=hex_to_rgb(COLORS['card_bg']),
                      outline=hex_to_rgb(COLORS['border']), width=2)
    
    # Title
    if week_date_str:
        title = f"{league_name.upper()} - Week {week_date_str}"
    else:
        title = f"{league_name.upper()} - THIS WEEK"
    draw.text((width // 2, 40), title, font=title_font,
              fill=hex_to_rgb(COLORS['primary']), anchor="mm")
    
    col_player = 30
    col_score = 250
    col_out = 400
    
    def draw_division_table(y_start, div_label, div_color, div_data):
        """Draw a single division table, return y position after table"""
        nonlocal draw, img
        
        # Division header bar
        draw.rectangle([20, y_start, width - 20, y_start + div_header_height],
                       fill=hex_to_rgb(div_color) + (40,) if len(div_color) > 6 else None)
        # Draw a subtle colored line under the division header
        draw.line([(20, y_start + div_header_height), (width - 20, y_start + div_header_height)],
                  fill=hex_to_rgb(div_color), width=2)
        draw.text((col_player, y_start + 10), div_label, font=div_title_font,
                  fill=hex_to_rgb(div_color))
        
        # Column headers
        y = y_start + div_header_height + 5
        draw.text((col_player, y), "Player", font=header_font, fill=hex_to_rgb(COLORS['text_secondary']))
        draw.text((col_score, y), "Score", font=header_font, fill=hex_to_rgb(COLORS['text_secondary']))
        draw.text((col_out, y), "Thrown Out", font=header_font, fill=hex_to_rgb(COLORS['text_secondary']))
        
        y += 28
        
        for i, player in enumerate(div_data):
            row_y = y + (i * row_height)
            
            # Highlight eligible players with division color
            if player.get('eligible', False):
                overlay = Image.new('RGBA', (width - 40, row_height - 6), hex_to_rgb(div_color) + (45,))
                img.paste(Image.blend(
                    img.crop((20, row_y, width - 20, row_y + row_height - 6)).convert('RGBA'),
                    overlay, 0.4).convert('RGB'), (20, row_y))
                draw = ImageDraw.Draw(img)
            
            name = player.get('name', 'Unknown')
            if len(name) > 12:
                name = name[:11] + "…"
            draw.text((col_player, row_y + 10), name, font=player_font,
                      fill=hex_to_rgb(COLORS['text_primary']))
            
            score = player.get('score')
            if score is not None and score > 0:
                draw.text((col_score + 30, row_y + 10), str(score), font=score_font,
                          fill=hex_to_rgb(COLORS['text_primary']))
            else:
                draw.text((col_score + 30, row_y + 10), "-", font=score_font,
                          fill=hex_to_rgb(COLORS['text_secondary']))
            
            thrown = player.get('thrown', [])
            if thrown:
                thrown_text = ", ".join(str(s) for s in thrown[:3])
                if len(thrown) > 3:
                    thrown_text += "…"
                draw.text((col_out, row_y + 10), thrown_text, font=score_font,
                          fill=hex_to_rgb(COLORS['text_secondary']))
            else:
                draw.text((col_out + 20, row_y + 10), "-", font=score_font,
                          fill=hex_to_rgb(COLORS['text_secondary']))
        
        return y + (len(div_data) * row_height) + 10
    
    # Draw Division I
    y = header_height
    y = draw_division_table(y, "DIVISION I", COLORS['primary'], div1_data)
    
    # Draw Division II
    y += section_gap
    y = draw_division_table(y, "DIVISION II", COLORS['secondary'], div2_data)
    
    # Footer
    footer_y = height - 22
    draw.text((width // 2, footer_y), "Lower score = Better!", font=small_font,
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
