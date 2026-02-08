#!/usr/bin/env python3
"""
HTML Generator v2 for Cloud Wordle League
Generates complete HTML pages from league data
Updated: 2025-12-01 15:47 PST
"""
import logging
from datetime import datetime, date, timedelta

def format_wordle_date(wordle_num):
    """Convert Wordle number to date string"""
    # First Wordle (Wordle 0) was on June 19, 2021
    first_wordle_date = date(2021, 6, 19)
    wordle_date = first_wordle_date + timedelta(days=wordle_num)
    return wordle_date.strftime("%B %d, %Y")

def get_day_name(wordle_num):
    """Get day name (Mon, Tue, etc) for a Wordle number"""
    first_wordle_date = date(2021, 6, 19)
    wordle_date = first_wordle_date + timedelta(days=wordle_num)
    return wordle_date.strftime("%a")

def transform_emoji_colors(emoji_pattern):
    """Transform Wordle emoji colors to our custom color scheme.
    Replaces emoji squares with styled CSS boxes that have a 3D effect.
    """
    if not emoji_pattern:
        return emoji_pattern
    
    # CSS for 3D-looking blocks - using box-shadow for depth effect
    # Size matches typical emoji rendering, with rounded corners and inset shadow
    cyan_block = '<span class="wl-block wl-cyan"></span>'
    orange_block = '<span class="wl-block wl-orange"></span>'
    dark_block = '<span class="wl-block wl-dark"></span>'
    light_block = '<span class="wl-block wl-light"></span>'
    
    # Replace each emoji with our custom block
    result = emoji_pattern.replace('🟩', cyan_block)
    result = result.replace('🟨', orange_block)
    result = result.replace('⬛', dark_block)
    result = result.replace('⬜', light_block)
    
    return result

def get_emoji_block_styles():
    """Return CSS styles for custom emoji blocks."""
    return '''
    .wl-block {
        display: inline-block;
        width: 1.1em;
        height: 1.1em;
        margin: 1px;
        border-radius: 3px;
        vertical-align: middle;
    }
    .wl-cyan {
        background: linear-gradient(145deg, #00E8DA, #00c4b8);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.3), inset 0 -2px 0 rgba(0,0,0,0.15);
    }
    .wl-orange {
        background: linear-gradient(145deg, #FFA64D, #e89440);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.3), inset 0 -2px 0 rgba(0,0,0,0.15);
    }
    .wl-dark {
        background: linear-gradient(145deg, #3a3a3c, #2d2d2f);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.1), inset 0 -2px 0 rgba(0,0,0,0.2);
    }
    .wl-light {
        background: linear-gradient(145deg, #787c7e, #6a6d6f);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.3), inset 0 -2px 0 rgba(0,0,0,0.15);
    }
    '''

def generate_score_card_html(player_name, score_data):
    """Generate HTML for a single score card in Latest Scores tab"""
    score = score_data.get('score')
    emoji_pattern = score_data.get('emoji_pattern')
    
    if score is None or score == 0:
        score_display = '<span>No Score</span>'
        emoji_html = '<div class="emoji-pattern"></div>'
    else:
        # Color code the score (1-3 green, 4-6 yellow, 7/X red)
        if score <= 3:
            color = '#00E8DA'  # Cyan
            bg_color = 'rgba(0, 232, 218, 0.15)'
        elif score <= 6:
            color = '#FFA64D'  # Orange
            bg_color = 'rgba(255, 166, 77, 0.15)'
        else:  # 7 or X
            color = '#787c7e'  # Grey
            bg_color = 'rgba(120, 124, 126, 0.15)'
        
        score_text = 'X' if score == 7 else f"{score}"
        score_display = f'<span style="color: {color}; background-color: {bg_color}; padding: 2px 8px; border-radius: 3px; display: inline-block; font-weight: bold;">{score_text}/6</span>'
        
        # Generate emoji pattern HTML
        if emoji_pattern:
            # Handle both newline and space-separated rows
            emoji_pattern_clean = emoji_pattern.strip()
            if '\n' in emoji_pattern_clean:
                emoji_rows = emoji_pattern_clean.split('\n')
            else:
                # Split by double space or single space between 5-emoji groups
                emoji_rows = emoji_pattern_clean.split(' ')
            
            emoji_html = '<div class="emoji-pattern">'
            for row in emoji_rows:
                if row.strip():  # Skip empty rows
                    # Transform emoji colors to our custom scheme
                    transformed_row = transform_emoji_colors(row.strip())
                    emoji_html += f'<div class="emoji-row">{transformed_row}</div>'
            emoji_html += '</div>'
        else:
            emoji_html = '<div class="emoji-pattern"></div>'
    
    return f'''<div class="score-card">
    <div class="player-info">
        <div class="player-name">{player_name}</div>
        <div class="player-score">{score_display}</div>
    </div>
    <div class="emoji-container">{emoji_html}</div>
</div>'''

def generate_latest_scores_html(league_data):
    """Generate Latest Scores tab HTML"""
    today_wordle = league_data['today_wordle']
    wordle_date = format_wordle_date(today_wordle)
    
    html = f'<h2 style="margin-top: 5px; margin-bottom: 10px; font-size: 16px; color: #00E8DA; text-align: center;">Wordle #{today_wordle} - {wordle_date}</h2>\n'
    
    # Sort players: scores first (by numeric value), then No Score (alphabetically)
    # This matches the proven script logic
    players_list = []
    
    for player_name, score_data in league_data['latest_scores'].items():
        score = score_data.get('score')
        timestamp = score_data.get('timestamp', '')  # Get timestamp for tie-breaking
        
        # Determine sort keys
        if score and score > 0:
            # Has a score: sort by numeric value (X/6 = 7)
            has_score = 0  # Scores come first
            numeric_score = score  # Already numeric (1-7)
        else:
            # No score: push to bottom
            has_score = 1
            numeric_score = 999
            timestamp = 'zzz'  # Push no-scores to bottom alphabetically
        
        players_list.append({
            'name': player_name,
            'data': score_data,
            'has_score': has_score,
            'numeric_score': numeric_score,
            'timestamp': timestamp
        })
    
    # Sort: scores first (by value), then by timestamp (first posted = top)
    # For tied scores, earlier timestamp appears first
    players_list.sort(key=lambda x: (x['has_score'], x['numeric_score'], x['timestamp'], x['name']))
    
    # Generate HTML for sorted players
    for player_info in players_list:
        player_name = player_info['name']
        score_data = player_info['data']
        html += generate_score_card_html(player_name, score_data)
    
    return html

def generate_score_cell(score):
    """Generate HTML for a score cell in the weekly table"""
    if score is None:
        return '<td>-</td>'
    
    if score == 7:  # Failed attempt (X)
        return '<td class="failed" style="color: #787c7e; font-weight: bold;">X</td>'
    elif score <= 3:  # 1-3 cyan
        return f'<td class="good" style="color: #00E8DA; font-weight: bold;">{score}</td>'
    elif score <= 6:  # 4-6 orange
        return f'<td class="medium" style="color: #FFA64D; font-weight: bold;">{score}</td>'
    else:
        return f'<td class="bad" style="color: #ff5c5c; font-weight: bold;">{score}</td>'

def generate_weekly_totals_html(league_data):
    """Generate Weekly Totals tab HTML"""
    week_wordles = league_data['week_wordles']
    weekly_stats = league_data['weekly_stats']
    
    html = f'''<p style="margin-top: 0; margin-bottom: 5px; font-style: italic;">Top 5 scores count toward weekly total (Monday-Sunday).</p>
<p style="margin-top: 0; margin-bottom: 20px; font-size: 0.9em;">At least 5 scores needed to compete for the week!</p>
<div class="table-container" style="overflow-x: auto;">
<table>
<thead>
<tr>
    <th class="sticky-column">Player</th>
    <th>Weekly Score</th>
    <th>Used Scores</th>
    <th>Failed</th>
    <th>Thrown Out</th>
'''
    
    # Add column headers for each day of the week (Monday-Sunday) - NO Wordle numbers
    for wordle_num in week_wordles:
        day_name = get_day_name(wordle_num)
        html += f'    <th>{day_name}</th>\n'
    
    html += '</tr>\n</thead>\n<tbody>\n'
    
    # Sort players: ELIGIBLE FIRST (5+ scores), then by score, then by games
    # This matches the proven script logic exactly
    sorted_players = sorted(
        weekly_stats.items(),
        key=lambda x: (
            x[1]['used_scores'] < 5,  # Eligible (5+) first (False sorts before True)
            -x[1]['used_scores'] if x[1]['used_scores'] < 5 else 0,  # Non-eligible by games (desc)
            x[1]['best_5_total'] if x[1]['used_scores'] > 0 else 999,  # Then by score (asc)
            -x[1]['games_played']  # Tie-breaker: more games played
        )
    )
    
    for player_name, stats in sorted_players:
        # Highlight players with 5+ games in green
        row_class = ''
        row_style = ''
        if stats['used_scores'] >= 5:
            row_style = ' style="background-color: rgba(0, 232, 218, 0.15);"'
        
        # Also highlight weekly winner
        if league_data['weekly_winner'] and player_name == league_data['weekly_winner']['name']:
            row_class = ' class="highlight"'
        
        html += f'<tr{row_class}{row_style}>\n'
        html += f'    <td class="sticky-column"><strong>{player_name}</strong></td>\n'
        # Show current total even if less than 5 games, but only highlight/compete if >= 5
        if stats["used_scores"] > 0:
            total_display = str(stats["best_5_total"])
        else:
            total_display = "-"
        html += f'    <td style="font-weight: bold;">{total_display}</td>\n'
        html += f'    <td>{stats["used_scores"]}</td>\n'
        # Failed column - only highlight if there ARE failed attempts
        if stats["failed_attempts"] > 0:
            html += f'    <td style="color: #ff5c5c; font-weight: bold;">{stats["failed_attempts"]}</td>\n'
        else:
            html += f'    <td>-</td>\n'
        # Thrown Out column - show actual scores, not count
        if stats["thrown_out"] and len(stats["thrown_out"]) > 0:
            thrown_out_display = ', '.join(str(s) for s in stats["thrown_out"])
            html += f'    <td>{thrown_out_display}</td>\n'
        else:
            html += f'    <td>-</td>\n'
        
        # Add daily scores
        for wordle_num in week_wordles:
            if wordle_num in stats['daily_scores']:
                score = stats['daily_scores'][wordle_num]['score']
                html += generate_score_cell(score)
            else:
                html += '<td>-</td>\n'
        
        html += '</tr>\n'
    
    html += '</tbody>\n</table>\n'
    html += '<p class="note" style="font-style: italic; margin-top: 20px;">Failed attempts do not count towards your \'Used Scores\'</p>\n'
    html += '<p class="note" style="font-style: italic; margin-top: 5px;">Weekly Score uses only your best 5 scores. Additional scores appear in \'Thrown Out\'</p>\n'
    html += '</div>\n'
    
    return html

def wordle_to_date_string(wordle_num):
    """Convert Wordle number to 'Nov 25' format date string"""
    from datetime import datetime, timedelta
    # Reference: Wordle 1503 = July 31, 2025
    reference_date = datetime(2025, 7, 31)
    reference_wordle = 1503
    
    days_diff = wordle_num - reference_wordle
    target_date = reference_date + timedelta(days=days_diff)
    
    return target_date.strftime("%b %d")

def _build_breakdown_rows(breakdown):
    """Build table rows HTML for a season breakdown."""
    def sort_key(item):
        player_name, data = item
        last_win = data['weeks'][-1] if data['weeks'] else 9999
        return (-data['wins'], last_win)
    
    rows = ''
    for player_name, data in sorted(breakdown.items(), key=sort_key):
        wins = data['wins']
        row_style = ' style="background-color: rgba(0, 232, 218, 0.15);"' if wins >= 4 else ''
        rows += f'<tr{row_style}><td><strong>{player_name}</strong></td><td style="text-align:center;">{wins}</td></tr>\n'
    return rows


def _build_season_winner_text(season_num, winners_list):
    """Build display text for a season's winner(s)."""
    if len(winners_list) == 1:
        return f'Season {season_num} Winner: {winners_list[0]}'
    else:
        winner_list = ' and '.join(winners_list) if len(winners_list) == 2 else ', '.join(winners_list[:-1]) + ', and ' + winners_list[-1]
        return f'Season {season_num} Winners: {winner_list}'


def generate_season_breakdown_modal(season_num, breakdown):
    """Generate a hidden modal with the weekly winner breakdown for a past season (standalone)."""
    modal_id = f'season-modal-{season_num}'
    rows_html = _build_breakdown_rows(breakdown)
    
    return f'''<div id="{modal_id}" class="season-modal-overlay" onclick="if(event.target===this)this.style.display='none'" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); z-index:1000; justify-content:center; align-items:center;">
  <div style="background:#1a1a1b; border:1px solid #333; border-radius:10px; padding:20px; max-width:320px; width:90%; max-height:80vh; overflow-y:auto;">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
      <h3 style="color:#00E8DA; margin:0;">Season {season_num} Breakdown</h3>
      <span onclick="document.getElementById('{modal_id}').style.display='none'" style="color:#d7dadc; cursor:pointer; font-size:1.5rem; line-height:1; padding:4px 8px;">&times;</span>
    </div>
    <table class="season-table" style="width:100%;">
      <thead><tr><th>Player</th><th>Wins</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
</div>
'''


def generate_full_list_modal(seasons_dict, past_season_breakdowns):
    """Generate the 'Season Winners (Full List)' modal with drill-down capability."""
    modal_id = 'season-full-list-modal'
    
    # Build the full list view
    list_items = ''
    for season_num in sorted(seasons_dict.keys(), reverse=True):
        winners = seasons_dict[season_num]
        # Simplified format: "Season N:    Name"
        if len(winners) == 1:
            name_text = winners[0]
        else:
            name_text = ' &amp; '.join(winners) if len(winners) == 2 else ', '.join(winners[:-1]) + ', &amp; ' + winners[-1]
        has_breakdown = season_num in past_season_breakdowns
        
        if has_breakdown:
            list_items += f'<div style="display:flex; align-items:center; padding:12px 0; border-bottom:1px solid #333; cursor:pointer;" onclick="showSeasonDetail({season_num})"><span style="color:#d7dadc; font-weight:600; min-width:90px;">Season {season_num}:</span><span style="color:#d7dadc; font-weight:bold; margin-left:12px;">{name_text} <span style="font-size:0.8em; opacity:0.7; color:#00E8DA;">&#9656;</span></span></div>\n'
        else:
            list_items += f'<div style="display:flex; align-items:center; padding:12px 0; border-bottom:1px solid #333;"><span style="color:#d7dadc; font-weight:600; min-width:90px;">Season {season_num}:</span><span style="color:#d7dadc; font-weight:bold; margin-left:12px;">{name_text}</span></div>\n'
    
    # Build breakdown detail views (hidden by default)
    detail_views = ''
    for season_num, breakdown in past_season_breakdowns.items():
        rows_html = _build_breakdown_rows(breakdown)
        detail_views += f'''<div id="fl-detail-{season_num}" style="display:none; padding-top:4px;">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
      <span onclick="backToFullList()" style="color:#FFA64D; cursor:pointer; font-size:1.2rem; padding:6px 10px; background:#2a2a2c; border-radius:6px;">&#8592;</span>
      <span onclick="document.getElementById('{modal_id}').style.display='none'" style="color:#d7dadc; cursor:pointer; font-size:1.5rem; line-height:1; padding:4px 8px;">&times;</span>
    </div>
    <h3 style="color:#00E8DA; margin:0 0 14px 0; text-align:center;">Season {season_num}</h3>
    <table class="season-table" style="width:100%;">
      <thead><tr><th>Player</th><th>Wins</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
</div>
'''
    
    # JS for toggling views
    js = f'''<script>
function showSeasonDetail(sn) {{
  document.getElementById('fl-list-view').style.display = 'none';
  var details = document.querySelectorAll('[id^="fl-detail-"]');
  for (var i = 0; i < details.length; i++) details[i].style.display = 'none';
  var el = document.getElementById('fl-detail-' + sn);
  if (el) el.style.display = 'block';
}}
function backToFullList() {{
  var details = document.querySelectorAll('[id^="fl-detail-"]');
  for (var i = 0; i < details.length; i++) details[i].style.display = 'none';
  document.getElementById('fl-list-view').style.display = 'block';
}}
function openFullList() {{
  backToFullList();
  document.getElementById('season-full-list-modal').style.display = 'flex';
}}
</script>
'''
    
    return f'''<div id="{modal_id}" class="season-modal-overlay" onclick="if(event.target===this){{backToFullList();this.style.display='none'}}" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); z-index:1000; justify-content:center; align-items:center;">
  <div style="background:#1a1a1b; border:1px solid #333; border-radius:10px; padding:24px; max-width:320px; width:90%; max-height:80vh; overflow-y:auto;">
    <div id="fl-list-view">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
        <h3 style="color:#FFA64D; margin:0;">Season Winners</h3>
        <span onclick="backToFullList();document.getElementById('{modal_id}').style.display='none'" style="color:#d7dadc; cursor:pointer; font-size:1.5rem; line-height:1; padding:4px 8px;">&times;</span>
      </div>
      {list_items}
    </div>
    {detail_views}
  </div>
</div>
{js}'''


def generate_season_stats_html(league_data):
    """Generate Season / All-Time Stats tab HTML"""
    season_data = league_data.get('season_data', {})
    current_season = season_data.get('current_season', 1)
    season_standings = season_data.get('season_standings', {})
    season_winners = season_data.get('season_winners', [])
    past_season_breakdowns = season_data.get('past_season_breakdowns', {})
    
    html = '<div class="season-container" style="margin-bottom: 30px;">\n'
    html += f'<h3 style="margin-bottom: 10px; color: #00E8DA;">Season {current_season}</h3>\n'
    html += '<table class="season-table">\n'
    html += '<thead><tr><th>Player</th><th>Weekly Wins</th><th>Wordle Week (Score)</th></tr></thead>\n'
    html += '<tbody>\n'
    
    # Add current season standings
    if season_standings:
        # Sort by wins descending, then by when they reached that win count (first to reach stays on top)
        # Use the Wordle number of their Nth win as tiebreaker (lower = earlier = higher rank)
        def sort_key(item):
            player_name, data = item
            wins = data['wins']
            # Get the Wordle number when they achieved their current win count
            # (the last entry in their weeks list is when they got their most recent win)
            last_win_wordle = data['weeks'][-1] if data['weeks'] else 9999
            # Sort by: wins DESC, then last_win_wordle ASC (earlier wins rank higher)
            return (-wins, last_win_wordle)
        
        sorted_standings = sorted(season_standings.items(), key=sort_key)
        for player_name, data in sorted_standings:
            wins = data['wins']
            # Convert Wordle numbers to dates - each on its own line
            weeks_display = '<br>'.join([f"{wordle_to_date_string(w)} ({s})" for w, s in zip(data['weeks'], data['scores'])])
            html += f'<tr>\n'
            html += f'    <td><strong>{player_name}</strong></td>\n'
            html += f'    <td>{wins}</td>\n'
            html += f'    <td style="white-space: nowrap;">{weeks_display if weeks_display else "-"}</td>\n'
            html += '</tr>\n'
    
    html += '</tbody>\n</table>\n'
    html += '<p style="margin-top: 5px; font-size: 14px; font-style: italic;">If players are tied at the end of the week, then all players get a weekly win. First Player to get 4 weekly wins is the Season Champ!</p>\n'
    
    # Show previous season winners if any (NEWEST FIRST)
    modals_html = ''
    if season_winners:
        # Group winners by season to handle ties
        seasons_dict = {}
        for winner in season_winners:
            season_num = winner.get('season', 0)
            winner_name = winner.get('name', 'Unknown')
            if season_num not in seasons_dict:
                seasons_dict[season_num] = []
            seasons_dict[season_num].append(winner_name)
        
        sorted_season_nums = sorted(seasons_dict.keys(), reverse=True)
        max_inline = 2
        
        # Show latest 2 inline
        for season_num in sorted_season_nums[:max_inline]:
            winners = seasons_dict[season_num]
            has_breakdown = season_num in past_season_breakdowns
            winner_text = _build_season_winner_text(season_num, winners)
            
            if has_breakdown:
                html += f'<p class="season-winner-message" style="color: #00E8DA; font-weight: bold; margin-top: 10px; cursor: pointer; text-decoration: underline; text-decoration-style: dotted; text-underline-offset: 3px;" onclick="document.getElementById(\'season-modal-{season_num}\').style.display=\'flex\'">{winner_text} <span style="font-size: 0.8em; opacity: 0.7;">&#9656;</span></p>\n'
                modals_html += generate_season_breakdown_modal(season_num, past_season_breakdowns[season_num])
            else:
                html += f'<p class="season-winner-message" style="color: #00E8DA; font-weight: bold; margin-top: 10px;">{winner_text}</p>\n'
        
        # If more than 2 seasons, add "Season Winners (Full List)" link + modal
        if len(sorted_season_nums) > max_inline:
            html += '<p style="color: #FFA64D; font-weight: bold; margin-top: 12px; cursor: pointer; text-decoration: underline; text-decoration-style: dotted; text-underline-offset: 3px;" onclick="openFullList()">Season Winners (Full List) <span style="font-size: 0.8em; opacity: 0.7;">&#9656;</span></p>\n'
            modals_html += generate_full_list_modal(seasons_dict, past_season_breakdowns)
    
    html += '</div>\n'
    
    # All-Time Stats
    html += '<div class="all-time-container">\n'
    html += '<h2 style="margin-top: 5px; margin-bottom: 10px;">All-Time Stats</h2>\n'
    html += '<table>\n'
    html += '<thead><tr><th>Player</th><th>Games</th><th>Avg</th></tr></thead>\n'
    html += '<tbody>\n'
    
    for i, stats in enumerate(league_data['all_time_stats']):
        # Only highlight first player WITH scores
        has_scores = stats["games_played"] > 0
        row_class = ' class="highlight" style="background-color: rgba(0, 232, 218, 0.15);"' if i == 0 and has_scores else ''
        html += f'<tr{row_class}>\n'
        html += f'    <td><strong>{stats["name"]}</strong></td>\n'
        html += f'    <td>{stats["games_played"] if has_scores else "-"}</td>\n'
        avg_display = f'{stats["avg_score"]:.2f}' if has_scores else "-"
        html += f'    <td>{avg_display}</td>\n'
        html += '</tr>\n'
    
    html += '</tbody>\n</table>\n</div>\n'
    
    # Append modals at the end (they're fixed position, so placement doesn't matter)
    html += modals_html
    
    return html

def generate_full_html(league_data, league_name="League 6 Beta"):
    """Generate complete HTML page"""
    latest_html = generate_latest_scores_html(league_data)
    weekly_html = generate_weekly_totals_html(league_data)
    stats_html = generate_season_stats_html(league_data)
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0, maximum-scale=5.0, user-scalable=yes"/>
<title>{league_name} - Wordle League</title>
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate"/>
<meta http-equiv="Pragma" content="no-cache"/>
<meta http-equiv="Expires" content="0"/>
<link rel="stylesheet" href="styles.css"/>
<style>
    /* Emoji pattern styles */
    .score-display {{
        display: flex;
        align-items: center;
    }}
    
    .emoji-pattern {{
        margin-left: 15px;
        display: inline-block;
        text-align: right;
    }}
    
    .emoji-row {{
        white-space: nowrap;
        display: flex;
        gap: 5px;
        margin-bottom: 3px;
    }}
    .emoji-row:last-child {{
        margin-bottom: 0;
    }}
    
    /* Custom branded Wordle blocks - unique 3D tiles */
    .wl-block {{
        display: inline-block;
        width: 14px;
        height: 14px;
        border-radius: 3px;
        flex-shrink: 0;
        border: 1px solid rgba(0,0,0,0.2);
    }}
    .wl-cyan {{
        background: linear-gradient(135deg, #00E8DA 0%, #00d4c8 50%, #00c4b8 100%);
        box-shadow: inset 0 1px 2px rgba(255,255,255,0.4), inset 0 -2px 3px rgba(0,0,0,0.1), 0 0 3px rgba(0,232,218,0.3);
        border-color: #00c4b8;
    }}
    .wl-orange {{
        background: linear-gradient(135deg, #FFB366 0%, #FFA64D 50%, #e89440 100%);
        box-shadow: inset 0 1px 2px rgba(255,255,255,0.4), inset 0 -2px 3px rgba(0,0,0,0.1), 0 0 3px rgba(255,166,77,0.3);
        border-color: #e89440;
    }}
    .wl-dark {{
        background: linear-gradient(135deg, #4a4a4c 0%, #3a3a3c 50%, #2a2a2c 100%);
        box-shadow: inset 0 1px 1px rgba(255,255,255,0.08), inset 0 -2px 3px rgba(0,0,0,0.2);
        border-color: #2a2a2c;
    }}
    .wl-light {{
        background: linear-gradient(135deg, #ffffff 0%, #e8e8e8 50%, #d8d8d8 100%);
        box-shadow: inset 0 1px 2px rgba(255,255,255,0.5), inset 0 -2px 3px rgba(0,0,0,0.1);
        border-color: #c8c8c8;
    }}
    
    .emoji-container {{
        height: auto;
        display: flex;
        flex-direction: column;
        justify-content: center;
        margin-left: auto;
    }}
    
    .highlight {{
        background-color: rgba(0, 232, 218, 0.2);
    }}
    
    /* Failed attempts column styling */
    .failed-attempts {{
        background-color: rgba(128, 58, 58, 0.2);
        font-weight: bold;
        color: #ff6b6b;
    }}
</style>
</head>
<body>
<nav style="background: #1a1a1b; padding: 10px 15px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #333;">
    <a href="https://www.wordplayleague.com" style="color: #00E8DA; text-decoration: none; font-weight: bold; font-size: 0.95rem;">WordPlay<span style="color: #FFA64D;">League</span></a>
    <a href="https://app.wordplayleague.com/dashboard" style="color: #d7dadc; text-decoration: none; font-size: 0.9rem; padding: 6px 12px; background: #333; border-radius: 4px;">Dashboard →</a>
</nav>
<header style="padding: 10px 0; margin-bottom: 10px;">
<div class="container" style="padding: 10px; text-align: center;">
<h1 class="title" style="font-size: 24px; margin-bottom: 0; text-align: center;">{league_name}</h1>
</div>
</header>
<div class="container">
<div class="tab-container">
<div class="tab-buttons tabs">
<div style="width: 100%; display: flex; justify-content: center; gap: 8px;">
<button class="tab-button active" data-tab="latest" style="min-height: 48px; padding: 12px 20px;">Latest Scores</button>
<button class="tab-button" data-tab="weekly" style="min-height: 48px; padding: 12px 20px;">Weekly Totals</button>
</div>
<div style="width: 100%; display: flex; justify-content: center; margin-top: 8px;">
<button class="tab-button" data-tab="stats" style="min-height: 48px; padding: 12px 20px;">Season / All-Time Stats</button>
</div>
</div>
<div class="tab-content active" id="latest">
{latest_html}
</div>
<div class="tab-content" id="weekly">
{weekly_html}
</div>
<div class="tab-content" id="stats">
{stats_html}
</div>
</div>
</div>
<script src="script.js"></script>
<script src="tabs.js"></script>
</body>
</html>'''
    
    return html

if __name__ == "__main__":
    # Test with mock data
    logging.basicConfig(level=logging.INFO)
    print("Use league_data_adapter.py to get real data, then pass to generate_full_html()")
