#!/usr/bin/env python3
"""
HTML Generator v2 for Cloud Wordle League
Generates complete HTML pages from league data
Updated: 2025-12-01 15:47 PST
"""
import os
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
    missed_weeks_data = league_data.get('missed_weeks', {})
    min_scores = league_data.get('min_weekly_scores', 5)

    html = f'''<p style="margin-top: 0; margin-bottom: 15px; font-style: italic;">Top <strong style="color: #00E8DA;">{min_scores} scores</strong> count toward weekly total (Monday-Sunday).</p>
<div class="table-container" style="overflow-x: auto;">
<table>
<thead>
<tr>
    <th class="sticky-column">Player</th>
    <th>Weekly Score</th>
    <th>Used Scores</th>
    <th>Failed</th>
    <th style="min-width: 130px;">Thrown Out</th>
    <th>Wks Missed</th>
'''
    
    # Add column headers for each day of the week (Monday-Sunday) - NO Wordle numbers
    for wordle_num in week_wordles:
        day_name = get_day_name(wordle_num)
        html += f'    <th>{day_name}</th>\n'
    
    html += '</tr>\n</thead>\n<tbody>\n'
    
    # Sort players: ELIGIBLE FIRST (min_scores+), then by score, then by games
    # This matches the proven script logic exactly
    sorted_players = sorted(
        weekly_stats.items(),
        key=lambda x: (
            x[1]['used_scores'] < min_scores,  # Eligible first (False sorts before True)
            -x[1]['used_scores'] if x[1]['used_scores'] < min_scores else 0,  # Non-eligible by games (desc)
            x[1]['best_5_total'] if x[1]['used_scores'] > 0 else 999,  # Then by score (asc)
            -x[1]['games_played']  # Tie-breaker: more games played
        )
    )

    for player_name, stats in sorted_players:
        # Highlight eligible players (min_scores+) with cyan background
        row_class = ''
        row_style = ''
        if stats['used_scores'] >= min_scores:
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
            html += f'    <td style="white-space: nowrap;">{thrown_out_display}</td>\n'
        else:
            html += f'    <td>-</td>\n'
        
        # Weeks Missed column
        pw_missed = missed_weeks_data.get(player_name, 0)
        if pw_missed > 0:
            html += f'    <td style="color: #ff5c5c; font-weight: bold;">{pw_missed}</td>\n'
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


def generate_season_breakdown_modal(season_num, breakdown, modal_id=None):
    """Generate a hidden modal with the weekly winner breakdown for a past season (standalone)."""
    if modal_id is None:
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
    
    # Build the full list view with pagination data attributes
    list_items = ''
    sorted_seasons = sorted(seasons_dict.keys(), reverse=True)
    for idx, season_num in enumerate(sorted_seasons):
        winners = seasons_dict[season_num]
        if len(winners) == 1:
            name_text = winners[0]
        else:
            name_text = ' &amp; '.join(winners) if len(winners) == 2 else ', '.join(winners[:-1]) + ', &amp; ' + winners[-1]
        has_breakdown = season_num in past_season_breakdowns
        page_num = idx // 8 + 1

        if has_breakdown:
            list_items += f'<div class="fl-season-item" data-page="{page_num}" style="display:flex; align-items:center; padding:12px 0; border-bottom:1px solid #333; cursor:pointer;" onclick="showSeasonDetail({season_num})"><span style="color:#d7dadc; font-weight:600; min-width:90px;">Season {season_num}:</span><span style="color:#d7dadc; font-weight:bold; margin-left:12px;">{name_text} <span style="font-size:0.8em; opacity:0.7; color:#00E8DA;">&#9656;</span></span></div>\n'
        else:
            list_items += f'<div class="fl-season-item" data-page="{page_num}" style="display:flex; align-items:center; padding:12px 0; border-bottom:1px solid #333;"><span style="color:#d7dadc; font-weight:600; min-width:90px;">Season {season_num}:</span><span style="color:#d7dadc; font-weight:bold; margin-left:12px;">{name_text}</span></div>\n'

    total_pages = (len(sorted_seasons) + 7) // 8
    pagination_html = ''
    if total_pages > 1:
        pagination_html = f'''<div id="fl-pagination" style="display:flex; justify-content:flex-end; align-items:center; gap:8px; margin-top:12px; padding-top:8px;">
  <span id="fl-page-label" style="color:#818384; font-size:0.8em; margin-right:auto;">Page 1 of {total_pages}</span>
  <span id="fl-prev" onclick="flChangePage(-1)" style="color:#FFA64D; cursor:pointer; font-size:0.85em; padding:4px 10px; background:#2a2a2c; border-radius:6px; display:none;">&#8592; Prev</span>
  <span id="fl-next" onclick="flChangePage(1)" style="color:#FFA64D; cursor:pointer; font-size:0.85em; padding:4px 10px; background:#2a2a2c; border-radius:6px;">Next &#8594;</span>
</div>'''
    
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
var flCurrentPage = 1;
var flTotalPages = {total_pages};
function flShowPage(p) {{
  flCurrentPage = p;
  var items = document.querySelectorAll('.fl-season-item');
  for (var i = 0; i < items.length; i++) {{
    items[i].style.display = items[i].getAttribute('data-page') == String(p) ? 'flex' : 'none';
  }}
  var label = document.getElementById('fl-page-label');
  var prev = document.getElementById('fl-prev');
  var next = document.getElementById('fl-next');
  if (label) label.textContent = 'Page ' + p + ' of ' + flTotalPages;
  if (prev) prev.style.display = p > 1 ? 'inline' : 'none';
  if (next) next.style.display = p < flTotalPages ? 'inline' : 'none';
}}
function flChangePage(dir) {{ flShowPage(flCurrentPage + dir); }}
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
  flShowPage(flCurrentPage);
}}
function openFullList() {{
  backToFullList();
  flShowPage(1);
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
      {pagination_html}
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
    html += '</div>\n'  # Close season-container

    # Show previous season winners if any (NEWEST FIRST)
    # Also include division season winner history if it exists (even when division mode is OFF)
    modals_html = ''
    division_data = league_data.get('division_data')
    regular_season_count = league_data.get('regular_season_count', 0)
    has_division_history = division_data is not None and any(
        div_data.get('season_winners') for div_data in (division_data or {}).values() if isinstance(div_data, dict)
    )
    
    has_any_winners = has_division_history or season_winners
    if has_any_winners:
        html += '<div class="season-winners-container" style="margin-top: 24px; margin-bottom: 30px;">\n'

    if has_division_history:
        # Use unified season display (same approach as division mode)
        # Collect all division winners
        all_div_winners = []
        for div_key, div_data_entry in (division_data or {}).items():
            if not isinstance(div_data_entry, dict):
                continue
            div_num = div_key  # dict key is the division number (1 or 2)
            for winner in div_data_entry.get('season_winners', []):
                all_div_winners.append({
                    'season': winner.get('season', 0),
                    'name': winner.get('name', 'Unknown'),
                    'division': div_num,
                    'past_season_breakdowns': div_data_entry.get('past_season_breakdowns', {})
                })
        
        # Build unified seasons dict (season numbers already continue from regular seasons)
        unified_seasons = {}
        for dw in all_div_winners:
            display_num = dw['season']
            if display_num not in unified_seasons:
                unified_seasons[display_num] = {'type': 'division', 'div1': [], 'div2': [], 'breakdowns': {}}
            key = 'div1' if dw['division'] == 1 else 'div2'
            unified_seasons[display_num][key].append(dw['name'])
            for bk_sn, bk_data in dw['past_season_breakdowns'].items():
                bk_display = bk_sn
                unified_seasons.setdefault(bk_display, {'type': 'division', 'div1': [], 'div2': [], 'breakdowns': {}})
                unified_seasons[bk_display]['breakdowns'][(dw['division'], bk_sn)] = bk_data
        
        # Add regular season winners
        for winner in season_winners:
            sn = winner.get('season', 0)
            if sn not in unified_seasons:
                unified_seasons[sn] = {'type': 'regular', 'regular_names': [], 'regular_sn': sn}
            if 'regular_names' not in unified_seasons[sn]:
                unified_seasons[sn]['regular_names'] = []
                unified_seasons[sn]['regular_sn'] = sn
            unified_seasons[sn]['regular_names'].append(winner.get('name', 'Unknown'))
        
        if unified_seasons:
            sorted_display_nums = sorted(unified_seasons.keys(), reverse=True)
            max_inline = 2
            
            def _render_div_line(div_label, div_num_val, names_str, display_num, sdata, prefix=''):
                """Render a single division winner line with optional breakdown click."""
                e_html = ''
                m_html = ''
                # Styled label: white text with colored numeral (I=cyan, II=orange)
                numeral_color = '#00E8DA' if div_num_val == 1 else '#FFA64D'
                numeral = 'I' if div_num_val == 1 else 'II'
                styled_label = f'Division <span style="color:{numeral_color}">{numeral}</span>'
                if names_str == 'Closed':
                    e_html += f'<p class="season-winner-message" style="color: #d7dadc; font-weight: bold; margin: 0; padding-left: 20px;">{styled_label} Winner: <span style="font-style: italic; opacity: 0.6;">Closed</span></p>\n'
                else:
                    bk_key = None
                    for k in sdata.get('breakdowns', {}):
                        if k[0] == div_num_val:
                            bk_key = k
                            break
                    if bk_key and bk_key in sdata['breakdowns']:
                        modal_id = f'{prefix}div{div_num_val}-season-modal-{display_num}'
                        e_html += f'<p class="season-winner-message" style="color: #d7dadc; font-weight: bold; margin: 0; padding-left: 20px; cursor: pointer;" onclick="document.getElementById(\'{modal_id}\').style.display=\'flex\'">{styled_label} Winner: {names_str} <span style="font-size: 0.8em; opacity: 0.7;">&#9656;</span></p>\n'
                        rows_html = _build_breakdown_rows(sdata['breakdowns'][bk_key])
                        m_html += f'''<div id="{modal_id}" class="season-modal-overlay" onclick="if(event.target===this)this.style.display='none'" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); z-index:1001; justify-content:center; align-items:center;">
  <div style="background:#1a1a1b; border:1px solid #333; border-radius:10px; padding:20px; max-width:320px; width:90%; max-height:80vh; overflow-y:auto;">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
      <h3 style="color:#00E8DA; margin:0; font-size:1.05em;">Season {display_num} - {div_label}</h3>
      <span onclick="document.getElementById('{modal_id}').style.display='none'" style="color:#d7dadc; cursor:pointer; font-size:1.5rem; line-height:1; padding:4px 8px;">&times;</span>
    </div>
    <table class="season-table" style="width:100%;"><thead><tr><th>Player</th><th>Wins</th></tr></thead><tbody>{rows_html}</tbody></table>
  </div>
</div>
'''
                    else:
                        e_html += f'<p class="season-winner-message" style="color: #d7dadc; font-weight: bold; margin: 0; padding-left: 20px;">{styled_label} Winner: {names_str}</p>\n'
                return e_html, m_html
            
            def _render_unified_entry(display_num, sdata, prefix=''):
                entry_html = ''
                modal_html = ''
                if sdata.get('type') == 'division':
                    div1_names = ', '.join(sdata.get('div1', []))
                    div2_names = ', '.join(sdata.get('div2', []))
                    entry_html += f'<p class="season-winner-message" style="color: #00E8DA; font-weight: bold; margin-top: 12px; margin-bottom: 0;">Season {display_num}:</p>\n'
                    if div1_names:
                        e, m = _render_div_line('Division I', 1, div1_names, display_num, sdata, prefix)
                        entry_html += e
                        modal_html += m
                    if div2_names:
                        e, m = _render_div_line('Division II', 2, div2_names, display_num, sdata, prefix)
                        entry_html += e
                        modal_html += m
                    elif div1_names:
                        entry_html += f'<p class="season-winner-message" style="color: #d7dadc; font-weight: bold; margin: 0; padding-left: 20px;">Division <span style="color:#FFA64D">II</span> Winner: <span style="font-style: italic; opacity: 0.6;">In Progress</span></p>\n'
                elif sdata.get('type') == 'regular':
                    regular_names = ', '.join(sdata.get('regular_names', []))
                    real_sn = sdata.get('regular_sn', display_num)
                    winner_text = f"Season {display_num} Winner: {regular_names}"
                    has_breakdown = real_sn in past_season_breakdowns
                    if has_breakdown:
                        modal_id = f'{prefix}season-modal-{display_num}'
                        entry_html += f'<p class="season-winner-message" style="color: #00E8DA; font-weight: bold; margin-top: 10px; cursor: pointer;" onclick="document.getElementById(\'{modal_id}\').style.display=\'flex\'">{winner_text} <span style="font-size: 0.8em; opacity: 0.7;">&#9656;</span></p>\n'
                        modal_html += generate_season_breakdown_modal(real_sn, past_season_breakdowns[real_sn], modal_id)
                    else:
                        entry_html += f'<p class="season-winner-message" style="color: #00E8DA; font-weight: bold; margin-top: 10px;">{winner_text}</p>\n'
                return entry_html, modal_html
            
            for display_num in sorted_display_nums[:max_inline]:
                entry_html, modal_html = _render_unified_entry(display_num, unified_seasons[display_num])
                html += entry_html
                modals_html += modal_html
            
            if len(sorted_display_nums) > max_inline:
                html += '<p style="color: #FFA64D; font-weight: bold; margin-top: 12px; cursor: pointer; text-decoration: underline; text-decoration-style: dotted; text-underline-offset: 3px;" onclick="openFullList()">Season Winners (Full List) <span style="font-size: 0.8em; opacity: 0.7;">&#9656;</span></p>\n'
                # Build full list modal matching regular league style
                fl_list_items = ''
                fl_detail_views = ''
                for display_num in sorted_display_nums:
                    sdata = unified_seasons[display_num]
                    if sdata.get('type') == 'division':
                        div1_names = ', '.join(sdata.get('div1', []))
                        div2_names = ', '.join(sdata.get('div2', []))
                        div1_display = div1_names if div1_names else '<span style="opacity:0.6; font-style:italic;">In Progress</span>'
                        div2_display = div2_names if div2_names else '<span style="opacity:0.6; font-style:italic;">In Progress</span>'
                        
                        # Check which divisions have breakdowns
                        div1_bk_key = None
                        div2_bk_key = None
                        for k in sdata.get('breakdowns', {}):
                            if k[0] == 1:
                                div1_bk_key = k
                            elif k[0] == 2:
                                div2_bk_key = k
                        
                        # Div I row: clickable with arrow if has breakdown
                        if div1_bk_key:
                            div1_row = f'''<div style="display:flex; padding-left:32px; cursor:pointer;" onclick="event.stopPropagation(); document.getElementById('fl-div1-{display_num}').style.display='block'; document.getElementById('fl-list-view').style.display='none';">
    <span style="color:#00E8DA; font-weight:600; min-width:58px; text-align:right;">Div I:</span>
    <span style="color:#d7dadc; font-weight:bold; margin-left:12px;">{div1_display} <span style="font-size:0.8em; opacity:0.7; color:#00E8DA;">&#9656;</span></span>
  </div>'''
                        else:
                            div1_row = f'''<div style="display:flex; padding-left:32px;">
    <span style="color:#00E8DA; font-weight:600; min-width:58px; text-align:right;">Div I:</span>
    <span style="color:#d7dadc; font-weight:bold; margin-left:12px;">{div1_display}</span>
  </div>'''
                        
                        # Div II row: clickable with arrow if has breakdown
                        if div2_bk_key:
                            div2_row = f'''<div style="display:flex; padding-left:32px; margin-top:2px; cursor:pointer;" onclick="event.stopPropagation(); document.getElementById('fl-div2-{display_num}').style.display='block'; document.getElementById('fl-list-view').style.display='none';">
    <span style="color:#FFA64D; font-weight:600; min-width:58px; text-align:right;">Div II:</span>
    <span style="color:#d7dadc; font-weight:bold; margin-left:12px;">{div2_display} <span style="font-size:0.8em; opacity:0.7; color:#00E8DA;">&#9656;</span></span>
  </div>'''
                        else:
                            div2_row = f'''<div style="display:flex; padding-left:32px; margin-top:2px;">
    <span style="color:#FFA64D; font-weight:600; min-width:58px; text-align:right;">Div II:</span>
    <span style="color:#d7dadc; font-weight:bold; margin-left:12px;">{div2_display}</span>
  </div>'''
                        
                        fl_list_items += f'''<div style="padding:12px 0; border-bottom:1px solid #333;">
  <div style="color:#d7dadc; font-weight:600; margin-bottom:4px;">Season {display_num}:</div>
  {div1_row}
  {div2_row}
</div>\n'''
                        
                        # Build individual detail views per division
                        for div_num_check, div_label_check, bk_key in [(1, 'Division I', div1_bk_key), (2, 'Division II', div2_bk_key)]:
                            if bk_key and bk_key in sdata['breakdowns']:
                                rows_html = _build_breakdown_rows(sdata['breakdowns'][bk_key])
                                detail_id = f'fl-div{div_num_check}-{display_num}'
                                fl_detail_views += f'''<div id="{detail_id}" style="display:none; padding-top:4px;">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
      <span onclick="backToFullList()" style="color:#FFA64D; cursor:pointer; font-size:1.2rem; padding:6px 10px; background:#2a2a2c; border-radius:6px;">&#8592;</span>
      <span onclick="document.getElementById('season-full-list-modal').style.display='none'" style="color:#d7dadc; cursor:pointer; font-size:1.5rem; line-height:1; padding:4px 8px;">&times;</span>
    </div>
    <h3 style="color:#00E8DA; margin:0 0 14px 0; text-align:center; font-size:1.05em;">Season {display_num} - {div_label_check}</h3>
    <table class="season-table" style="width:100%;">
      <thead><tr><th>Player</th><th>Wins</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
</div>
'''
                    elif sdata.get('type') == 'regular':
                        regular_names = ', '.join(sdata.get('regular_names', []))
                        real_sn = sdata.get('regular_sn', display_num)
                        has_breakdown = real_sn in past_season_breakdowns
                        if has_breakdown:
                            fl_list_items += f'<div style="display:flex; align-items:center; padding:12px 0; border-bottom:1px solid #333; cursor:pointer;" onclick="showSeasonDetail({real_sn})"><span style="color:#d7dadc; font-weight:600; min-width:90px;">Season {display_num}:</span><span style="color:#d7dadc; font-weight:bold; margin-left:12px;">{regular_names} <span style="font-size:0.8em; opacity:0.7; color:#00E8DA;">&#9656;</span></span></div>\n'
                        else:
                            fl_list_items += f'<div style="display:flex; align-items:center; padding:12px 0; border-bottom:1px solid #333;"><span style="color:#d7dadc; font-weight:600; min-width:90px;">Season {display_num}:</span><span style="color:#d7dadc; font-weight:bold; margin-left:12px;">{regular_names}</span></div>\n'
                
                # Build breakdown detail views for regular seasons (same as generate_full_list_modal)
                for display_num in sorted_display_nums:
                    sdata = unified_seasons[display_num]
                    if sdata.get('type') == 'regular':
                        real_sn = sdata.get('regular_sn', display_num)
                        if real_sn in past_season_breakdowns:
                            rows_html = _build_breakdown_rows(past_season_breakdowns[real_sn])
                            fl_detail_views += f'''<div id="fl-detail-{real_sn}" style="display:none; padding-top:4px;">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
      <span onclick="backToFullList()" style="color:#FFA64D; cursor:pointer; font-size:1.2rem; padding:6px 10px; background:#2a2a2c; border-radius:6px;">&#8592;</span>
      <span onclick="document.getElementById('season-full-list-modal').style.display='none'" style="color:#d7dadc; cursor:pointer; font-size:1.5rem; line-height:1; padding:4px 8px;">&times;</span>
    </div>
    <h3 style="color:#00E8DA; margin:0 0 14px 0; text-align:center;">Season {display_num}</h3>
    <table class="season-table" style="width:100%;">
      <thead><tr><th>Player</th><th>Wins</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
</div>
'''
                
                # JS for toggling views (same functions as regular full list)
                fl_js = '''<script>
function showSeasonDetail(sn) {
  document.getElementById('fl-list-view').style.display = 'none';
  var details = document.querySelectorAll('[id^="fl-detail-"]');
  for (var i = 0; i < details.length; i++) details[i].style.display = 'none';
  var el = document.getElementById('fl-detail-' + sn);
  if (el) el.style.display = 'block';
}
function backToFullList() {
  var details = document.querySelectorAll('[id^="fl-detail-"]');
  for (var i = 0; i < details.length; i++) details[i].style.display = 'none';
  document.getElementById('fl-list-view').style.display = 'block';
}
function openFullList() {
  backToFullList();
  document.getElementById('season-full-list-modal').style.display = 'flex';
}
</script>
'''
                
                modals_html += f'''<div id="season-full-list-modal" class="season-modal-overlay" onclick="if(event.target===this){{backToFullList();this.style.display='none'}}" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); z-index:1000; justify-content:center; align-items:center;">
  <div style="background:#1a1a1b; border:1px solid #333; border-radius:10px; padding:24px; max-width:320px; width:90%; max-height:80vh; overflow-y:auto;">
    <div id="fl-list-view">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
        <h3 style="color:#FFA64D; margin:0;">Season Winners</h3>
        <span onclick="backToFullList();document.getElementById('season-full-list-modal').style.display='none'" style="color:#d7dadc; cursor:pointer; font-size:1.5rem; line-height:1; padding:4px 8px;">&times;</span>
      </div>
      {fl_list_items}
    </div>
    {fl_detail_views}
  </div>
</div>
{fl_js}'''
    elif season_winners:
        # No division history - show regular season winners only
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
                html += f'<p class="season-winner-message" style="color: #00E8DA; font-weight: bold; margin-top: 10px; cursor: pointer; " onclick="document.getElementById(\'season-modal-{season_num}\').style.display=\'flex\'">{winner_text} <span style="font-size: 0.8em; opacity: 0.7;">&#9656;</span></p>\n'
                modals_html += generate_season_breakdown_modal(season_num, past_season_breakdowns[season_num])
            else:
                html += f'<p class="season-winner-message" style="color: #00E8DA; font-weight: bold; margin-top: 10px;">{winner_text}</p>\n'
        
        # If more than 2 seasons, add "Season Winners (Full List)" link + modal
        if len(sorted_season_nums) > max_inline:
            html += '<p style="color: #FFA64D; font-weight: bold; margin-top: 12px; cursor: pointer; text-decoration: underline; text-decoration-style: dotted; text-underline-offset: 3px;" onclick="openFullList()">Season Winners (Full List) <span style="font-size: 0.8em; opacity: 0.7;">&#9656;</span></p>\n'
            modals_html += generate_full_list_modal(seasons_dict, past_season_breakdowns)

    if has_any_winners:
        html += '</div>\n'  # Close season-winners-container

    # All-Time Stats
    html += '<div class="all-time-container" style="margin-top: 36px;">\n'
    html += '<h2 style="margin-top: 30px; margin-bottom: 10px;">All-Time Stats</h2>\n'
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

def generate_division_weekly_totals_html(league_data):
    """Generate Weekly Totals tab with two division tables and a Weekly Score / Season Total dropdown."""
    division_data = league_data.get('division_data', {})
    player_divisions = league_data.get('player_divisions', {})
    week_wordles = league_data['week_wordles']
    weekly_stats = league_data['weekly_stats']
    min_scores = league_data.get('min_weekly_scores', 5)

    html = ''
    
    for div_num in (1, 2):
        div_info = division_data.get(div_num, {})
        div_label = "DIVISION I" if div_num == 1 else "DIVISION II"
        div_color = "#00E8DA" if div_num == 1 else "#FFA64D"
        season_totals = div_info.get('season_totals', {})
        missed_weeks_data = div_info.get('missed_weeks', {})
        div_players_list = div_info.get('players', [])
        div_player_names = {p['name'] for p in div_players_list}
        immune_players = {p['name'] for p in div_players_list if p.get('immunity')}
        
        # Filter weekly_stats to only this division's players
        div_stats = {name: stats for name, stats in weekly_stats.items() if player_divisions.get(name) == div_num}
        
        html += f'<div style="margin-bottom: 30px;">\n'
        
        # Only show instructions above Division I (before the title)
        if div_num == 1:
            html += f'''<p style="margin-top: 0; margin-bottom: 10px; font-style: italic;">Top <strong style="color: #00E8DA;">{min_scores} scores</strong> count toward weekly total (Monday-Sunday).</p>
'''
        
        html += f'<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">\n'
        html += f'  <h3 style="color: {div_color}; margin: 0;">{div_label}</h3>\n'
        html += f'  <select id="score-toggle-{div_num}" onchange="toggleScoreView({div_num})" style="background: #2a2a2c; color: #d7dadc; border: 1px solid #444; border-radius: 6px; padding: 4px 8px; font-size: 0.85em;">\n'
        html += f'    <option value="weekly">Weekly Score</option>\n'
        html += f'    <option value="season">Season Total</option>\n'
        html += f'  </select>\n'
        html += f'</div>\n'
        html += f'''<div class="table-container" style="overflow-x: auto;">
<table id="div-table-{div_num}">
<thead>
<tr>
    <th class="sticky-column">Player</th>
    <th class="score-col-weekly-{div_num}">Weekly Score</th>
    <th class="score-col-season-{div_num}" style="display:none;">Season Total</th>
    <th>Used Scores</th>
    <th>Failed</th>
    <th style="min-width: 130px;">Thrown Out</th>
    <th>Wks Missed</th>
'''
        for wordle_num in week_wordles:
            day_name = get_day_name(wordle_num)
            html += f'    <th>{day_name}</th>\n'
        
        html += '</tr>\n</thead>\n<tbody>\n'
        
        # Sort players
        sorted_players = sorted(
            div_stats.items(),
            key=lambda x: (
                x[1]['used_scores'] < min_scores,
                -x[1]['used_scores'] if x[1]['used_scores'] < min_scores else 0,
                x[1]['best_5_total'] if x[1]['used_scores'] > 0 else 999,
                -x[1]['games_played']
            )
        )

        for player_name, stats in sorted_players:
            row_style = ''
            if stats['used_scores'] >= min_scores:
                row_style = ' style="background-color: rgba(0, 232, 218, 0.15);"' if div_num == 1 else ' style="background-color: rgba(255, 166, 77, 0.15);"'
            
            # Check immunity for season total display
            st_val = season_totals.get(player_name)
            # Promoted players in Div I show "Immune", relegated players in Div II show "Relegated"
            if st_val is None:
                immune_label = 'Immune' if div_num == 1 else 'Relegated'
                season_total_display = f'<span style="color: {div_color};">{immune_label}</span>'
            else:
                season_total_display = str(st_val) if st_val else "-"
            
            # Highlight immune player names with division color
            name_style = f' style="color: {div_color};"' if player_name in immune_players else ''
            html += f'<tr{row_style}>\n'
            html += f'    <td class="sticky-column"><strong{name_style}>{player_name}</strong></td>\n'
            
            weekly_display = str(stats["best_5_total"]) if stats["used_scores"] > 0 else "-"
            html += f'    <td class="score-col-weekly-{div_num}" style="font-weight: bold;">{weekly_display}</td>\n'
            html += f'    <td class="score-col-season-{div_num}" style="display:none; font-weight: bold;">{season_total_display}</td>\n'
            html += f'    <td>{stats["used_scores"]}</td>\n'
            
            if stats["failed_attempts"] > 0:
                html += f'    <td style="color: #ff5c5c; font-weight: bold;">{stats["failed_attempts"]}</td>\n'
            else:
                html += f'    <td>-</td>\n'
            
            if stats["thrown_out"] and len(stats["thrown_out"]) > 0:
                thrown_out_display = ', '.join(str(s) for s in stats["thrown_out"])
                html += f'    <td style="white-space: nowrap;">{thrown_out_display}</td>\n'
            else:
                html += f'    <td>-</td>\n'
            
            pw_missed = missed_weeks_data.get(player_name, 0)
            if pw_missed > 0:
                html += f'    <td style="color: #ff5c5c; font-weight: bold;">{pw_missed}</td>\n'
            else:
                html += f'    <td>-</td>\n'
            
            for wordle_num in week_wordles:
                if wordle_num in stats['daily_scores']:
                    score = stats['daily_scores'][wordle_num]['score']
                    html += generate_score_cell(score)
                else:
                    html += '<td>-</td>\n'
            
            html += '</tr>\n'
        
        # Include division players with no scores this week
        for p in div_players_list:
            if p['name'] not in div_stats:
                st_val = season_totals.get(p['name'])
                # Promoted players in Div I show "Immune", relegated players in Div II show "Relegated"
                if st_val is None:
                    immune_label = 'Immune' if div_num == 1 else 'Relegated'
                    season_total_display = f'<span style="color: {div_color};">{immune_label}</span>'
                else:
                    season_total_display = str(st_val) if st_val else "-"
                name_style = f' style="color: {div_color};"' if p['name'] in immune_players else ''
                html += f'<tr>\n'
                html += f'    <td class="sticky-column"><strong{name_style}>{p["name"]}</strong></td>\n'
                html += f'    <td class="score-col-weekly-{div_num}">-</td>\n'
                html += f'    <td class="score-col-season-{div_num}" style="display:none;">{season_total_display}</td>\n'
                pw_missed = missed_weeks_data.get(p['name'], 0)
                if pw_missed > 0:
                    missed_td = f'<td style="color: #ff5c5c; font-weight: bold;">{pw_missed}</td>'
                else:
                    missed_td = '<td>-</td>'
                html += f'    <td>0</td><td>-</td><td>-</td>{missed_td}\n'
                for _ in week_wordles:
                    html += '<td>-</td>\n'
                html += '</tr>\n'
        
        html += '</tbody>\n</table>\n</div>\n'
        
        # Show promoted/relegated count below each division table
        promoted_count = league_data.get('promoted_count', 1)
        relegated_count = league_data.get('relegated_count', 1)
        if div_num == 1:
            html += f'<p style="margin: 6px 0 0; font-size: 0.8em; color: #00E8DA; font-style: italic;">&#x2B07; Relegated Players: {relegated_count}</p>\n'
        else:
            html += f'<p style="margin: 6px 0 0; font-size: 0.8em; color: #FFA64D; font-style: italic;">&#x2B06; Promoted Players: {promoted_count}</p>\n'
        
        html += '</div>\n'
    
    # Footer text (shown once after both division tables)
    
    # JavaScript for toggling Weekly Score / Season Total with sorting
    html += '''<script>
var originalOrder = {};
function toggleScoreView(divNum) {
    var sel = document.getElementById('score-toggle-' + divNum);
    var mode = sel.value;
    var weeklyCols = document.querySelectorAll('.score-col-weekly-' + divNum);
    var seasonCols = document.querySelectorAll('.score-col-season-' + divNum);
    var table = document.getElementById('div-table-' + divNum);
    var tbody = table.querySelector('tbody');
    var rows = Array.from(tbody.querySelectorAll('tr'));
    
    if (mode === 'season') {
        weeklyCols.forEach(function(el) { el.style.display = 'none'; });
        seasonCols.forEach(function(el) { el.style.display = ''; });
        // Save original order if not saved
        if (!originalOrder[divNum]) {
            originalOrder[divNum] = rows.map(function(r) { return r; });
        }
        // Sort by season total: numeric ascending (lower=better), Immune/Relegated and - go to bottom
        var statusLabels = ['Immune', 'Relegated'];
        rows.sort(function(a, b) {
            var aCell = a.querySelector('.score-col-season-' + divNum);
            var bCell = b.querySelector('.score-col-season-' + divNum);
            var aVal = aCell ? aCell.textContent.trim() : '-';
            var bVal = bCell ? bCell.textContent.trim() : '-';
            var aIsStatus = statusLabels.indexOf(aVal) >= 0;
            var bIsStatus = statusLabels.indexOf(bVal) >= 0;
            var aNum = (aIsStatus || aVal === '-' || aVal === '0') ? 99999 : parseInt(aVal);
            var bNum = (bIsStatus || bVal === '-' || bVal === '0') ? 99999 : parseInt(bVal);
            if (aIsStatus && !bIsStatus) return 1;
            if (bIsStatus && !aIsStatus) return -1;
            if (aVal === '-' && bVal !== '-') return 1;
            if (bVal === '-' && aVal !== '-') return -1;
            return aNum - bNum;
        });
        rows.forEach(function(r) { tbody.appendChild(r); });
    } else {
        weeklyCols.forEach(function(el) { el.style.display = ''; });
        seasonCols.forEach(function(el) { el.style.display = 'none'; });
        // Restore original order
        if (originalOrder[divNum]) {
            originalOrder[divNum].forEach(function(r) { tbody.appendChild(r); });
        }
    }
}
</script>
'''
    
    return html


def generate_division_season_stats_html(league_data):
    """Generate Season / All-Time Stats tab with two division tables."""
    division_data = league_data.get('division_data', {})
    
    html = ''
    all_modals_html = ''
    all_div_winners = []  # Collect division season winners to show below both tables
    
    for div_num in (1, 2):
        div_info = division_data.get(div_num, {})
        div_label = "Division I" if div_num == 1 else "Division II"
        div_color = "#00E8DA" if div_num == 1 else "#FFA64D"
        current_season = div_info.get('current_season', 1)
        season_standings = div_info.get('season_standings', {})
        season_winners = div_info.get('season_winners', [])
        past_season_breakdowns = div_info.get('past_season_breakdowns', {})
        wins_needed = div_info.get('wins_needed', 3)
        div_players_list = div_info.get('players', [])
        immune_players = {p['name'] for p in div_players_list if p.get('immunity')}
        
        html += f'<div class="season-container" style="margin-bottom: 30px;">\n'
        html += f'<h3 style="margin-bottom: 10px; color: {div_color};">{div_label} - Season {current_season}</h3>\n'
        html += '<table class="season-table">\n'
        html += '<thead><tr><th>Player</th><th>Weekly Wins</th><th>Wordle Week (Score)</th></tr></thead>\n'
        html += '<tbody>\n'
        
        if season_standings:
            def sort_key(item):
                player_name, data = item
                last_win_wordle = data['weeks'][-1] if data['weeks'] else 9999
                return (-data['wins'], last_win_wordle)
            
            sorted_standings = sorted(season_standings.items(), key=sort_key)
            for player_name, data in sorted_standings:
                wins = data['wins']
                weeks_display = '<br>'.join([f"{wordle_to_date_string(w)} ({s})" for w, s in zip(data['weeks'], data['scores'])])
                row_style = ''
                if wins >= wins_needed:
                    row_style = f' style="background-color: rgba({0 if div_num == 1 else 255}, {232 if div_num == 1 else 166}, {218 if div_num == 1 else 77}, 0.15);"'
                # Highlight immune player names with division color
                name_style = f' style="color: {div_color};"' if player_name in immune_players else ''
                html += f'<tr{row_style}>\n'
                html += f'    <td><strong{name_style}>{player_name}</strong></td>\n'
                html += f'    <td>{wins}</td>\n'
                html += f'    <td style="white-space: nowrap;">{weeks_display if weeks_display else "-"}</td>\n'
                html += '</tr>\n'
        
        html += '</tbody>\n</table>\n'

        # Collect division season winners for display below both tables
        if season_winners:
            for winner in season_winners:
                all_div_winners.append({
                    'season': winner.get('season', 0),
                    'name': winner.get('name', 'Unknown'),
                    'wins': winner.get('wins', 0),
                    'division': div_num,
                    'div_label': div_label,
                    'div_color': div_color,
                    'past_season_breakdowns': past_season_breakdowns
                })
        
        html += '</div>\n'
    
    # === Combined Season Winners section (below both division tables) ===
    # Unified season numbering: division seasons are offset by regular_season_count
    # e.g. if 3 regular seasons existed, Div Season 1 displays as "Season 4"
    season_data = league_data.get('season_data', {})
    regular_season_winners = season_data.get('season_winners', [])
    regular_past_breakdowns = season_data.get('past_season_breakdowns', {})
    regular_season_count = league_data.get('regular_season_count', 0)
    
    # Build unified season entries: list of (display_num, entry_data)
    # entry_data = {'type': 'division'|'regular', 'div1': [...], 'div2': [...], 'regular': [...], 'breakdowns': {}}
    unified_seasons = {}
    
    # Add division season winners (season numbers already continue from regular seasons)
    for dw in all_div_winners:
        display_num = dw['season']
        if display_num not in unified_seasons:
            unified_seasons[display_num] = {'type': 'division', 'div1': [], 'div2': [], 'breakdowns': {}}
        key = 'div1' if dw['division'] == 1 else 'div2'
        unified_seasons[display_num][key].append(dw['name'])
        for bk_sn, bk_data in dw['past_season_breakdowns'].items():
            bk_display = bk_sn
            unified_seasons.setdefault(bk_display, {'type': 'division', 'div1': [], 'div2': [], 'breakdowns': {}})
            unified_seasons[bk_display]['breakdowns'][(dw['division'], bk_sn)] = bk_data
    
    # Add regular (pre-division) season winners
    for rw in regular_season_winners:
        sn = rw.get('season', 0)
        if sn not in unified_seasons:
            unified_seasons[sn] = {'type': 'regular', 'regular_names': [], 'regular_sn': sn}
        if 'regular_names' not in unified_seasons[sn]:
            unified_seasons[sn]['regular_names'] = []
            unified_seasons[sn]['regular_sn'] = sn
        unified_seasons[sn]['regular_names'].append(rw.get('name', 'Unknown'))
    
    # Helper to render a single season entry
    def _render_season_entry(display_num, sdata, indent=False):
        entry_html = ''
        modal_html = ''
        indent_style = ' padding-left: 20px;' if indent else ''
        
        if sdata.get('type') == 'division':
            # "Season N:" header in cyan
            entry_html += f'<p style="color: #00E8DA; font-weight: bold; margin: 12px 0 0 0; font-size: 1em;">Season {display_num}:</p>\n'
            
            div1_names = ', '.join(sdata.get('div1', []))
            div2_names = ', '.join(sdata.get('div2', []))
            
            # Division I winner (indented, white with cyan numeral)
            if div1_names:
                div1_styled = 'Division <span style="color:#00E8DA">I</span>'
                if div1_names == 'Closed':
                    entry_html += f'<p class="season-winner-message" style="color: #d7dadc; font-weight: bold; margin: 0; padding-left: 20px;">{div1_styled} Winner: <span style="font-style: italic; opacity: 0.6;">Closed</span></p>\n'
                else:
                    div1_text = f'{div1_styled} Winner: {div1_names}'
                    div1_bk_key = None
                    for k in sdata.get('breakdowns', {}):
                        if k[0] == 1:
                            div1_bk_key = k
                            break
                    if div1_bk_key and div1_bk_key in sdata['breakdowns']:
                        modal_id = f'div1-season-modal-{display_num}'
                        entry_html += f'<p class="season-winner-message" style="color: #d7dadc; font-weight: bold; margin: 0; padding-left: 20px; cursor: pointer;" onclick="document.getElementById(\'{modal_id}\').style.display=\'flex\'">{div1_text} <span style="font-size: 0.8em; opacity: 0.7;">&#9656;</span></p>\n'
                        rows_html = _build_breakdown_rows(sdata['breakdowns'][div1_bk_key])
                        modal_html += f'''<div id="{modal_id}" class="season-modal-overlay" onclick="if(event.target===this)this.style.display='none'" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); z-index:1000; justify-content:center; align-items:center;">
  <div style="background:#1a1a1b; border:1px solid #333; border-radius:10px; padding:20px; max-width:320px; width:90%; max-height:80vh; overflow-y:auto;">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
      <h3 style="color:#00E8DA; margin:0; font-size:1.05em;">Season {display_num} - Division I</h3>
      <span onclick="document.getElementById('{modal_id}').style.display='none'" style="color:#d7dadc; cursor:pointer; font-size:1.5rem; line-height:1; padding:4px 8px;">&times;</span>
    </div>
    <table class="season-table" style="width:100%;">
      <thead><tr><th>Player</th><th>Wins</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
</div>
'''
                    else:
                        entry_html += f'<p class="season-winner-message" style="color: #d7dadc; font-weight: bold; margin: 0; padding-left: 20px;">{div1_text}</p>\n'
            
            # Division II winner (indented, white with orange numeral)
            if div2_names:
                div2_styled = 'Division <span style="color:#FFA64D">II</span>'
                if div2_names == 'Closed':
                    entry_html += f'<p class="season-winner-message" style="color: #d7dadc; font-weight: bold; margin: 0; padding-left: 20px;">{div2_styled} Winner: <span style="font-style: italic; opacity: 0.6;">Closed</span></p>\n'
                else:
                    div2_text = f'{div2_styled} Winner: {div2_names}'
                    div2_bk_key = None
                    for k in sdata.get('breakdowns', {}):
                        if k[0] == 2:
                            div2_bk_key = k
                            break
                    if div2_bk_key and div2_bk_key in sdata['breakdowns']:
                        modal_id = f'div2-season-modal-{display_num}'
                        entry_html += f'<p class="season-winner-message" style="color: #d7dadc; font-weight: bold; margin: 0; padding-left: 20px; cursor: pointer;" onclick="document.getElementById(\'{modal_id}\').style.display=\'flex\'">{div2_text} <span style="font-size: 0.8em; opacity: 0.7;">&#9656;</span></p>\n'
                        rows_html = _build_breakdown_rows(sdata['breakdowns'][div2_bk_key])
                        modal_html += f'''<div id="{modal_id}" class="season-modal-overlay" onclick="if(event.target===this)this.style.display='none'" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); z-index:1000; justify-content:center; align-items:center;">
  <div style="background:#1a1a1b; border:1px solid #333; border-radius:10px; padding:20px; max-width:320px; width:90%; max-height:80vh; overflow-y:auto;">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
      <h3 style="color:#00E8DA; margin:0; font-size:1.05em;">Season {display_num} - Division II</h3>
      <span onclick="document.getElementById('{modal_id}').style.display='none'" style="color:#d7dadc; cursor:pointer; font-size:1.5rem; line-height:1; padding:4px 8px;">&times;</span>
    </div>
    <table class="season-table" style="width:100%;">
      <thead><tr><th>Player</th><th>Wins</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
</div>
'''
                    else:
                        entry_html += f'<p class="season-winner-message" style="color: #d7dadc; font-weight: bold; margin: 0; padding-left: 20px;">{div2_text}</p>\n'
            elif sdata.get('div1'):
                # Div I has winner but Div II doesn't yet
                entry_html += f'<p class="season-winner-message" style="color: #d7dadc; font-weight: bold; margin: 0; padding-left: 20px;">Division <span style="color:#FFA64D">II</span> Winner: <span style="font-style: italic; opacity: 0.6;">In Progress</span></p>\n'
        
        elif sdata.get('type') == 'regular':
            regular_names = ', '.join(sdata.get('regular_names', []))
            real_sn = sdata.get('regular_sn', display_num)
            regular_text = f"Season {display_num} Winner: {regular_names}"
            has_breakdown = real_sn in regular_past_breakdowns
            if has_breakdown:
                modal_id = f'season-modal-{display_num}'
                entry_html += f'<p class="season-winner-message" style="color: #00E8DA; font-weight: bold; margin-top: 12px; cursor: pointer;" onclick="document.getElementById(\'{modal_id}\').style.display=\'flex\'">{regular_text} <span style="font-size: 0.8em; opacity: 0.7;">&#9656;</span></p>\n'
                modal_html += generate_season_breakdown_modal(real_sn, regular_past_breakdowns[real_sn])
            else:
                entry_html += f'<p class="season-winner-message" style="color: #00E8DA; font-weight: bold; margin-top: 12px;">{regular_text}</p>\n'
        
        return entry_html, modal_html
    
    if unified_seasons:
        sorted_display_nums = sorted(unified_seasons.keys(), reverse=True)
        max_inline = 2
        
        # Show latest 2 seasons inline
        for display_num in sorted_display_nums[:max_inline]:
            entry_html, modal_html = _render_season_entry(display_num, unified_seasons[display_num])
            html += entry_html
            all_modals_html += modal_html
        
        # If more than 2, add "Season Winners (Full List)" link + modal
        if len(sorted_display_nums) > max_inline:
            html += '<p style="color: #FFA64D; font-weight: bold; margin-top: 12px; cursor: pointer; text-decoration: underline; text-decoration-style: dotted; text-underline-offset: 3px;" onclick="document.getElementById(\'div-season-full-list-modal\').style.display=\'flex\';if(typeof divFlShowPage===\'function\')divFlShowPage(1);">Season Winners (Full List) <span style="font-size: 0.8em; opacity: 0.7;">&#9656;</span></p>\n'
            
            # Build Full List modal content - matching non-division league style
            full_list_items = ''
            full_list_detail_views = ''
            for idx_div, display_num in enumerate(sorted_display_nums):
                div_page_num = idx_div // 8 + 1
                sdata = unified_seasons[display_num]
                if sdata.get('type') == 'division':
                    div1_names = ', '.join(sdata.get('div1', []))
                    div2_names = ', '.join(sdata.get('div2', []))
                    div1_display = div1_names if div1_names else '<span style="opacity:0.6; font-style:italic;">In Progress</span>'
                    div2_display = div2_names if div2_names else '<span style="opacity:0.6; font-style:italic;">In Progress</span>'
                    
                    # Check which divisions have breakdowns
                    div1_bk_key = None
                    div2_bk_key = None
                    for k in sdata.get('breakdowns', {}):
                        if k[0] == 1:
                            div1_bk_key = k
                        elif k[0] == 2:
                            div2_bk_key = k
                    
                    # Div I row: clickable with arrow if has breakdown
                    if div1_bk_key:
                        div1_row = f'''<div style="display:flex; padding-left:32px; cursor:pointer;" onclick="event.stopPropagation(); document.getElementById('div-fl-d1-{display_num}').style.display='block'; document.getElementById('div-fl-list-view').style.display='none';">
    <span style="color:#00E8DA; font-weight:600; min-width:58px; text-align:right;">Div I:</span>
    <span style="color:#d7dadc; font-weight:bold; margin-left:12px;">{div1_display} <span style="font-size:0.8em; opacity:0.7; color:#00E8DA;">&#9656;</span></span>
  </div>'''
                    else:
                        div1_row = f'''<div style="display:flex; padding-left:32px;">
    <span style="color:#00E8DA; font-weight:600; min-width:58px; text-align:right;">Div I:</span>
    <span style="color:#d7dadc; font-weight:bold; margin-left:12px;">{div1_display}</span>
  </div>'''
                    
                    # Div II row: clickable with arrow if has breakdown
                    if div2_bk_key:
                        div2_row = f'''<div style="display:flex; padding-left:32px; margin-top:2px; cursor:pointer;" onclick="event.stopPropagation(); document.getElementById('div-fl-d2-{display_num}').style.display='block'; document.getElementById('div-fl-list-view').style.display='none';">
    <span style="color:#FFA64D; font-weight:600; min-width:58px; text-align:right;">Div II:</span>
    <span style="color:#d7dadc; font-weight:bold; margin-left:12px;">{div2_display} <span style="font-size:0.8em; opacity:0.7; color:#00E8DA;">&#9656;</span></span>
  </div>'''
                    else:
                        div2_row = f'''<div style="display:flex; padding-left:32px; margin-top:2px;">
    <span style="color:#FFA64D; font-weight:600; min-width:58px; text-align:right;">Div II:</span>
    <span style="color:#d7dadc; font-weight:bold; margin-left:12px;">{div2_display}</span>
  </div>'''
                    
                    full_list_items += f'''<div class="div-fl-season-item" data-page="{div_page_num}" style="padding:12px 0; border-bottom:1px solid #333;">
  <div style="color:#d7dadc; font-weight:600; margin-bottom:4px;">Season {display_num}:</div>
  {div1_row}
  {div2_row}
</div>\n'''
                    
                    # Build individual detail views per division (same layout as standard season breakdowns)
                    for div_num_check, div_label_check, bk_key in [(1, 'Division I', div1_bk_key), (2, 'Division II', div2_bk_key)]:
                        if bk_key and bk_key in sdata['breakdowns']:
                            rows_html = _build_breakdown_rows(sdata['breakdowns'][bk_key])
                            detail_id = f'div-fl-d{div_num_check}-{display_num}'
                            full_list_detail_views += f'''<div id="{detail_id}" style="display:none; padding-top:4px;">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
      <span onclick="document.getElementById('{detail_id}').style.display='none'; document.getElementById('div-fl-list-view').style.display='block';" style="color:#FFA64D; cursor:pointer; font-size:1.2rem; padding:6px 10px; background:#2a2a2c; border-radius:6px;">&#8592;</span>
      <span onclick="document.getElementById('div-season-full-list-modal').style.display='none'" style="color:#d7dadc; cursor:pointer; font-size:1.5rem; line-height:1; padding:4px 8px;">&times;</span>
    </div>
    <h3 style="color:#00E8DA; margin:0 0 14px 0; text-align:center; font-size:1.05em;">Season {display_num} - {div_label_check}</h3>
    <table class="season-table" style="width:100%;">
      <thead><tr><th>Player</th><th>Wins</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
</div>
'''
                elif sdata.get('type') == 'regular':
                    regular_names = ', '.join(sdata.get('regular_names', []))
                    real_sn = sdata.get('regular_sn', display_num)
                    has_breakdown = real_sn in regular_past_breakdowns
                    if has_breakdown:
                        full_list_items += f'<div class="div-fl-season-item" data-page="{div_page_num}" style="display:flex; align-items:center; padding:12px 0; border-bottom:1px solid #333; cursor:pointer;" onclick="document.getElementById(\'div-fl-detail-reg-{real_sn}\').style.display=\'block\'; document.getElementById(\'div-fl-list-view\').style.display=\'none\';"><span style="color:#d7dadc; font-weight:600; min-width:90px;">Season {display_num}:</span><span style="color:#d7dadc; font-weight:bold; margin-left:12px;">{regular_names} <span style="font-size:0.8em; opacity:0.7; color:#00E8DA;">&#9656;</span></span></div>\n'
                        rows_html = _build_breakdown_rows(regular_past_breakdowns[real_sn])
                        full_list_detail_views += f'''<div id="div-fl-detail-reg-{real_sn}" style="display:none; padding-top:4px;">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
      <span onclick="document.getElementById('div-fl-detail-reg-{real_sn}').style.display='none'; document.getElementById('div-fl-list-view').style.display='block';" style="color:#FFA64D; cursor:pointer; font-size:1.2rem; padding:6px 10px; background:#2a2a2c; border-radius:6px;">&#8592;</span>
      <span onclick="document.getElementById('div-season-full-list-modal').style.display='none'" style="color:#d7dadc; cursor:pointer; font-size:1.5rem; line-height:1; padding:4px 8px;">&times;</span>
    </div>
    <h3 style="color:#00E8DA; margin:0 0 14px 0; text-align:center;">Season {display_num}</h3>
    <table class="season-table" style="width:100%;">
      <thead><tr><th>Player</th><th>Wins</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
</div>
'''
                    else:
                        full_list_items += f'<div class="div-fl-season-item" data-page="{div_page_num}" style="display:flex; align-items:center; padding:12px 0; border-bottom:1px solid #333;"><span style="color:#d7dadc; font-weight:600; min-width:90px;">Season {display_num}:</span><span style="color:#d7dadc; font-weight:bold; margin-left:12px;">{regular_names}</span></div>\n'
            
            div_total_pages = (len(sorted_display_nums) + 7) // 8
            div_pagination_html = ''
            if div_total_pages > 1:
                div_pagination_html = f'''<div id="div-fl-pagination" style="display:flex; justify-content:flex-end; align-items:center; gap:8px; margin-top:12px; padding-top:8px;">
  <span id="div-fl-page-label" style="color:#818384; font-size:0.8em; margin-right:auto;">Page 1 of {div_total_pages}</span>
  <span id="div-fl-prev" onclick="divFlChangePage(-1)" style="color:#FFA64D; cursor:pointer; font-size:0.85em; padding:4px 10px; background:#2a2a2c; border-radius:6px; display:none;">&#8592; Prev</span>
  <span id="div-fl-next" onclick="divFlChangePage(1)" style="color:#FFA64D; cursor:pointer; font-size:0.85em; padding:4px 10px; background:#2a2a2c; border-radius:6px;">Next &#8594;</span>
</div>'''

            div_pagination_js = f'''<script>
var divFlCurrentPage = 1;
var divFlTotalPages = {div_total_pages};
function divFlShowPage(p) {{
  divFlCurrentPage = p;
  var items = document.querySelectorAll('.div-fl-season-item');
  for (var i = 0; i < items.length; i++) {{
    items[i].style.display = items[i].getAttribute('data-page') == String(p) ? '' : 'none';
  }}
  var label = document.getElementById('div-fl-page-label');
  var prev = document.getElementById('div-fl-prev');
  var next = document.getElementById('div-fl-next');
  if (label) label.textContent = 'Page ' + p + ' of ' + divFlTotalPages;
  if (prev) prev.style.display = p > 1 ? 'inline' : 'none';
  if (next) next.style.display = p < divFlTotalPages ? 'inline' : 'none';
}}
function divFlChangePage(dir) {{ divFlShowPage(divFlCurrentPage + dir); }}
</script>
'''

            all_modals_html += f'''<div id="div-season-full-list-modal" class="season-modal-overlay" onclick="if(event.target===this){{var dvs=document.querySelectorAll('[id^=div-fl-]');for(var i=0;i<dvs.length;i++){{if(dvs[i].id!=='div-fl-list-view')dvs[i].style.display='none'}};document.getElementById('div-fl-list-view').style.display='block';divFlShowPage(1);this.style.display='none'}}" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); z-index:1000; justify-content:center; align-items:center;">
  <div style="background:#1a1a1b; border:1px solid #333; border-radius:10px; padding:24px; max-width:320px; width:90%; max-height:80vh; overflow-y:auto;">
    <div id="div-fl-list-view">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
        <h3 style="color:#FFA64D; margin:0;">Season Winners</h3>
        <span onclick="var dvs=document.querySelectorAll('[id^=div-fl-]');for(var i=0;i<dvs.length;i++){{if(dvs[i].id!=='div-fl-list-view')dvs[i].style.display='none'}};document.getElementById('div-fl-list-view').style.display='block';document.getElementById('div-season-full-list-modal').style.display='none'" style="color:#d7dadc; cursor:pointer; font-size:1.5rem; line-height:1; padding:4px 8px;">&times;</span>
      </div>
      {full_list_items}
      {div_pagination_html}
    </div>
    {full_list_detail_views}
  </div>
</div>
{div_pagination_js}
'''
    
    # All-Time Stats (unchanged - shows all players regardless of division)
    html += '<div class="all-time-container">\n'
    html += '<h2 style="margin-top: 30px; margin-bottom: 10px;">All-Time Stats</h2>\n'
    html += '<table>\n'
    html += '<thead><tr><th>Player</th><th>Games</th><th>Avg</th></tr></thead>\n'
    html += '<tbody>\n'
    
    for i, stats in enumerate(league_data['all_time_stats']):
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
    html += all_modals_html
    
    return html


def generate_rules_html(league_data):
    """Generate the Rules & League Settings tab content."""
    min_scores = league_data.get('min_weekly_scores', 5)
    division_active = league_data.get('division_mode') and league_data.get('division_confirmed_at') is not None
    wins_needed = 3 if division_active else 4
    promoted_count = league_data.get('promoted_count', 1)
    relegated_count = league_data.get('relegated_count', 1)
    ai = league_data.get('ai_settings', {})

    score_labels = {3: 'Easy Mode', 4: 'Casual', 5: 'Default', 6: 'Hard Mode', 7: 'Elite'}
    thrown_out = 7 - min_scores

    # Build expanded min-scores selector matching dashboard style
    seg_buttons = ''
    for val in range(3, 8):
        lbl = score_labels.get(val, '')
        lbl_words = lbl.split(' ')
        word1 = lbl_words[0]
        word2 = lbl_words[1] if len(lbl_words) > 1 else '&nbsp;'
        if val == min_scores:
            bg = '#00E8DA'; fg = '#1a1a1b'; border = '#00E8DA'; weight = '700'
        else:
            bg = '#2a2a2c'; fg = '#818384'; border = '#444'; weight = '500'
        seg_buttons += (
            f'<div style="flex:1; padding:10px 6px; background:{bg}; color:{fg}; '
            f'border:1px solid {border}; border-radius:8px; font-weight:{weight}; '
            f'text-align:center;">'
            f'<div style="font-size:1.3em; font-weight:700;">{val}</div>'
            f'<div style="font-size:0.75em; opacity:0.85;">{word1}</div>'
            f'<div style="font-size:0.75em; opacity:0.85;">{word2}</div>'
            f'</div>'
        )

    # Card wrapper matching dashboard glass-morphism style
    card_style = 'background:rgba(16,16,36,0.7); backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px); border-radius:12px; padding:20px; margin-bottom:16px; border:1px solid rgba(255,255,255,0.08); box-shadow:0 6px 32px rgba(0,0,0,0.45);'

    html = '<h2 style="color:#FFA64D; margin-top:0; margin-bottom:24px; text-align:center;">Rules &amp; League Settings</h2>\n'

    # 1. Minimum Weekly Scores
    html += f'''<div style="{card_style}">
<h3 style="color:#00E8DA; margin:0 0 10px 0; font-size:1.1em;">📊 Minimum Weekly Scores</h3>
<p style="margin:0 0 10px 0; color:#d7dadc; line-height:1.6;">This league is currently set to <strong style="color:#00E8DA;">{min_scores} scores</strong>. Only your best {min_scores} scores each week count toward your weekly total (Monday&ndash;Sunday). If you play all 7 days, your {thrown_out} highest (worst) score{"s are" if thrown_out != 1 else " is"} thrown out. Once a player reaches the minimum {min_scores} scores for the week, their row will be highlighted to indicate they are eligible for a weekly score.</p>
<p style="margin:0 0 12px 0; color:#818384; font-size:0.85em; line-height:1.5;">You need at least {min_scores} scores in a week to compete. The league manager can adjust this setting:</p>
<div style="display:flex; gap:8px;">{seg_buttons}</div>
</div>
'''

    # 2. Window to Post
    html += f'''<div style="{card_style}">
<h3 style="color:#00E8DA; margin:0 0 10px 0; font-size:1.1em;">🕐 Window to Post</h3>
<p style="margin:0; color:#d7dadc; line-height:1.6;">Each day&#39;s Wordle score can be submitted between <strong style="color:#00E8DA;">12:00 AM and 11:59 PM Pacific Time</strong>. Only the current day&#39;s Wordle puzzle number is accepted&mdash;scores from previous days cannot be posted retroactively. The scoring week runs <strong style="color:#00E8DA;">Monday through Sunday</strong>.</p>
</div>
'''

    # 3. Fails Don't Count
    html += f'''<div style="{card_style}">
<h3 style="color:#00E8DA; margin:0 0 10px 0; font-size:1.1em;">❌ Fails Don&#39;t Count</h3>
<p style="margin:0; color:#d7dadc; line-height:1.6;">If you fail a Wordle (X/6), it does not count as one of your used scores and won&#39;t affect your weekly total. Failed attempts will appear in the <strong style="color:#d7dadc;">Failed</strong> column of the weekly table for reference.</p>
</div>
'''

    # 3. Ties Share the Win
    html += f'''<div style="{card_style}">
<h3 style="color:#00E8DA; margin:0 0 10px 0; font-size:1.1em;">🤝 Ties Share the Win</h3>
<p style="margin:0 0 10px 0; color:#d7dadc; line-height:1.6;">If two or more players finish the week with the same total score, they all earn a weekly win. The same applies to the season&mdash;if multiple players reach <strong style="color:#00E8DA;">{wins_needed} weekly wins</strong> at the same time, they share the Season Victory.</p>
<p style="margin:0; color:#818384; font-size:0.85em;">First player to reach {wins_needed} weekly wins is crowned Season Champion!</p>
</div>
'''

    # 4. Division Mode
    if not division_active:
        html += f'''<div style="{card_style}">
<h3 style="color:#00E8DA; margin:0 0 10px 0; font-size:1.1em;">⚔️ Division Mode <span style="font-size:0.75em; color:#818384; font-weight:400;">(Available)</span></h3>
<p style="margin:0 0 10px 0; color:#d7dadc; line-height:1.6;">Want more competition? Your league manager can enable <strong style="color:#00E8DA;">Division Mode</strong>, which splits the league into two divisions. Each division has its own season race, and at the end of each season the top players from Division II get <strong style="color:#FFA64D;">promoted</strong> while the bottom players from Division I get <strong style="color:#FFA64D;">relegated</strong>.</p>
<p style="margin:0 0 10px 0; color:#d7dadc; line-height:1.6;">Newly promoted players receive <strong style="color:#d7dadc;">immunity</strong> from relegation for their first season, and players who miss a full week move to the front of the relegation line.</p>
<p style="margin:0; color:#818384; font-size:0.85em; line-height:1.5;">Requires at least <strong style="color:#FFA64D;">6 active players</strong>. League managers can enable this from the league settings page.</p>
</div>
'''

    if division_active:
        html += f'''<div style="{card_style}">
<h3 style="color:#00E8DA; margin:0 0 10px 0; font-size:1.1em;">⚔️ Division Mode</h3>
<p style="margin:0 0 10px 0; color:#d7dadc; line-height:1.6;">This league runs in Division Mode with two divisions. The league manager assigns players to divisions and can rearrange them until the first weekly winner is recorded on Monday. After that, divisions are locked for the season.</p>

<h4 style="color:#FFA64D; margin:14px 0 8px 0; font-size:0.95em;">Promotion &amp; Relegation</h4>
<p style="margin:0 0 10px 0; color:#d7dadc; line-height:1.6;">At the end of each season, the top <strong style="color:#FFA64D;">{promoted_count}</strong> player{"s" if promoted_count > 1 else ""} from Division II {"are" if promoted_count > 1 else "is"} promoted to Division I. {"The season winner and the player(s) with the best season total (lowest cumulative score) move up." if promoted_count > 1 else "The season winner moves up."}</p>
<p style="margin:0 0 10px 0; color:#d7dadc; line-height:1.6;">Meanwhile, the bottom <strong style="color:#00E8DA;">{relegated_count}</strong> player{"s" if relegated_count > 1 else ""} from Division I {"are" if relegated_count > 1 else "is"} relegated to Division II, based on the highest season total (worst cumulative score).</p>

<h4 style="color:#FFA64D; margin:14px 0 8px 0; font-size:0.95em;">Immunity &amp; Missed Weeks</h4>
<p style="margin:0 0 10px 0; color:#d7dadc; line-height:1.6;">Promoted players receive <strong style="color:#d7dadc;">immunity</strong> for the remainder of the Division I season they join&mdash;they cannot be relegated until the following season. Relegated players receive a badge indicating they are a new arrival in Division II.</p>
<p style="margin:0 0 10px 0; color:#d7dadc; line-height:1.6;">If a player misses a week (fewer than {min_scores} scores submitted), they move to the front of the relegation line regardless of their season total. Missing a full week would give them an unfairly low total, so they are prioritized for relegation ahead of active players.</p>
<p style="margin:0; color:#818384; font-size:0.85em;">The manager can adjust promotion and relegation counts (1&ndash;3) at any time. Use the Weekly Score / Season Total toggle on the weekly table to check where players stand.</p>
</div>
'''

    # 5. AI Automated Messaging
    severity_labels = {1: 'Gentle', 2: 'Spicy', 3: 'Playful', 4: 'Savage'}
    current_tone = severity_labels.get(ai.get('severity', 2), 'Spicy')
    tone_colors = {1: '#2ECC71', 2: '#E67E22', 3: '#9B59B6', 4: '#E74C3C'}
    current_tone_color = tone_colors.get(ai.get('severity', 2), '#E67E22')

    msg_types = [
        ('🎯', 'Perfect Score', 'Celebrates when a player gets a perfect score (1/6 or 2/6).',
         ai.get('perfect_score', False),
         '"🔥 NO WAY! Sarah just nailed a 2/6! That\'s absolutely elite. The rest of you might want to take notes — this is what perfection looks like! 🎯"'),
        ('💀', 'Daily Worst Score', 'Playfully roasts the player with the worst score each day.',
         ai.get('daily_loser', False),
         '"😬 Mike... a 6/6? Buddy, the letters were RIGHT THERE. Even my autocorrect could\'ve done better. Tomorrow\'s a new day though! 💀"'),
        ('😬', 'Failed Attempt', 'Sends a message when a player fails a Wordle (X/6).',
         ai.get('failure_roast', False),
         '"Oh no, Alex! An X/6?! The Wordle gods were NOT on your side today. Don\'t worry, we\'ve all been there... some of us more than others. 😅"'),
        ('🏁', 'Sunday Race Update', 'Posts a weekly race update every Sunday with standings and AI commentary.',
         ai.get('sunday_race', False),
         '"🏁 SUNDAY RACE UPDATE! With 6 of 7 players reporting in, Sarah leads with a total of 14. Mike is right on her heels at 15. One day left — this is anyone\'s week! 🔥"'),
        ('📊', 'Monday Recap', 'Delivers a full weekly recap every Monday with winners and highlights.',
         ai.get('monday_recap', False),
         '"🏆 WEEKLY RECAP! Sarah takes the crown with a stellar best-5 total of 16! That gives her 3 weekly wins — just ONE more for the season championship! The pressure is ON! 🎉"'),
    ]

    example_style = 'margin:8px 0 0 0; padding:10px 12px; background:#1a1a2e; border-left:3px solid #00E8DA; border-radius:0 6px 6px 0; font-size:0.8em; color:#a0a0b8; line-height:1.5; font-style:italic;'

    msg_rows = ''
    for emoji, name, desc, is_on, example in msg_types:
        status_color = '#2ECC71' if is_on else '#E74C3C'
        status_text = 'ON' if is_on else 'OFF'
        msg_rows += f'''<div style="padding:12px; background:#2a2a2c; border-radius:8px; margin-bottom:10px;">
  <div style="display:flex; align-items:flex-start; gap:12px;">
    <span style="font-size:1.3em; flex-shrink:0;">{emoji}</span>
    <div style="flex:1; min-width:0;">
      <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
        <strong style="color:#d7dadc;">{name}</strong>
        <span style="background:{status_color}; color:#fff; padding:2px 8px; border-radius:10px; font-size:0.7em; font-weight:700;">{status_text}</span>
      </div>
      <p style="margin:0; color:#818384; font-size:0.85em; line-height:1.4;">{desc}</p>
    </div>
  </div>
  <div style="{example_style}">{example}</div>
</div>
'''

    # Tone meter visual
    tone_meter = ''
    for sev_val, sev_label in severity_labels.items():
        tc = tone_colors[sev_val]
        if sev_val == ai.get('severity', 2):
            tone_meter += f'<span style="background:{tc}; color:#fff; padding:4px 12px; border-radius:6px; font-size:0.8em; font-weight:700;">{sev_label}</span>'
        else:
            tone_meter += f'<span style="background:#2a2a2c; color:#818384; padding:4px 12px; border-radius:6px; font-size:0.8em;">{sev_label}</span>'

    html += f'''<div style="{card_style}">
<h3 style="color:#00E8DA; margin:0 0 10px 0; font-size:1.1em;">🤖 AI Automated Messaging</h3>
<p style="margin:0 0 14px 0; color:#d7dadc; line-height:1.6;">The league manager can enable AI-generated messages that are automatically sent to the group chat when certain events happen. These messages add personality and fun to the league experience.</p>
{msg_rows}
<h4 style="color:#FFA64D; margin:16px 0 8px 0; font-size:0.95em;">Default Tone</h4>
<p style="margin:0 0 10px 0; color:#d7dadc; line-height:1.6;">The current default tone is set to <strong style="color:{current_tone_color};">{current_tone}</strong>. The manager can set the tone globally or customize it per message type, and even per individual player.</p>
<div style="display:flex; gap:6px; flex-wrap:wrap;">{tone_meter}</div>
</div>
'''

    # 6. Data Reset & Revert
    html += f'''<div style="{card_style}">
<h3 style="color:#00E8DA; margin:0 0 10px 0; font-size:1.1em;">🔄 Data Reset &amp; Revert</h3>
<p style="margin:0; color:#d7dadc; line-height:1.6;">The league manager has the ability to reset various league data if needed. This includes resetting the current season table (clearing all weekly winners), resetting all previous season winners and the season counter, and resetting all-time stats for the entire league or for individual players. Most resets include a revert window so the manager can undo them if needed.</p>
</div>
'''

    return html


def generate_full_html(league_data, league_name="League 6 Beta"):
    """Generate complete HTML page"""
    latest_html = generate_latest_scores_html(league_data)
    rules_html = generate_rules_html(league_data)

    # Only show division mode if both enabled AND confirmed
    division_active = league_data.get('division_mode') and league_data.get('division_confirmed_at') is not None

    if division_active:
        weekly_html = generate_division_weekly_totals_html(league_data)
        stats_html = generate_division_season_stats_html(league_data)
    else:
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
        gap: 4px;
        margin-bottom: 3px;
    }}
    .emoji-row:last-child {{
        margin-bottom: 0;
    }}
    
    /* Custom branded Wordle blocks - unique 3D tiles */
    .wl-block {{
        display: inline-block;
        width: 23px;
        height: 23px;
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
<canvas id="wpl-particles"></canvas>
<div class="wpl-orb wpl-orb-1"></div>
<div class="wpl-orb wpl-orb-2"></div>
<div class="wpl-orb wpl-orb-3"></div>
<div class="wpl-top-bar">
    <a class="wpl-dashboard-btn" href="https://{os.environ.get('RAILWAY_PUBLIC_DOMAIN', 'app.wordplayleague.com')}/dashboard">Dashboard →</a>
</div>
<header>
<div class="container" style="text-align: center;">
{f'<div class="header-mascot">{league_data["header_emoji"]}</div>' if league_data.get("header_emoji") else ''}
<h1 class="title">{league_name}</h1>
<a class="wpl-brand" href="https://www.wordplayleague.com">WordPlayLeague</a>
</div>
</header>
<div class="container">
<div class="tab-container">
<div class="tab-buttons tabs">
<div class="tab-row" style="width:100%;">
<button class="tab-button active" style="flex:1;" data-tab="latest">Latest Scores</button>
<button class="tab-button" style="flex:1;" data-tab="weekly">Weekly Totals</button>
</div>
<div class="tab-row" style="width:100%;">
<button class="tab-button" style="flex:1;" data-tab="stats">Season</button>
<button class="tab-button" style="flex:1;" data-tab="rules">Rules</button>
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
<div class="tab-content" id="rules">
{rules_html}
</div>
</div>
</div>
<footer class="wpl-footer">
<div class="container">
<div class="footer-tiles">
<div class="footer-tile"></div>
<div class="footer-tile"></div>
<div class="footer-tile"></div>
<div class="footer-tile"></div>
<div class="footer-tile"></div>
</div>
<p>{league_name} · <a href="https://www.wordplayleague.com">WordPlayLeague</a></p>
</div>
</footer>
<script>
(function() {{
    var colors = ['t-cyan', 't-orange', 't-dark'];
    var tiles = document.querySelectorAll('.footer-tile');
    function pick() {{ return colors[Math.floor(Math.random() * colors.length)]; }}
    tiles.forEach(function(tile, i) {{
        tile.classList.add(pick());
        tile.style.animationDelay = (i * 0.2) + 's';
        tile.addEventListener('animationiteration', function() {{
            colors.forEach(function(c) {{ tile.classList.remove(c); }});
            tile.classList.add(pick());
        }});
    }});
}})();
</script>
<script>
(function() {{
    var canvas = document.getElementById('wpl-particles');
    if (!canvas) return;
    var ctx = canvas.getContext('2d');
    var particles = [];
    var w, h;
    function resize() {{ w = canvas.width = window.innerWidth; h = canvas.height = window.innerHeight; }}
    function createParticles() {{
        particles = [];
        var count = Math.min(60, Math.floor(w * h / 20000));
        var colors = ['#00ff88', '#ffd700', '#a855f7', '#38bdf8'];
        for (var i = 0; i < count; i++) {{
            particles.push({{
                x: Math.random() * w,
                y: Math.random() * h,
                vx: (Math.random() - 0.5) * 0.25,
                vy: (Math.random() - 0.5) * 0.25,
                size: Math.random() * 1.5 + 0.5,
                opacity: Math.random() * 0.4 + 0.25,
                color: colors[Math.floor(Math.random() * 4)]
            }});
        }}
    }}
    function draw() {{
        ctx.clearRect(0, 0, w, h);
        particles.forEach(function(p) {{
            p.x += p.vx; p.y += p.vy;
            if (p.x < 0) p.x = w; if (p.x > w) p.x = 0;
            if (p.y < 0) p.y = h; if (p.y > h) p.y = 0;
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            ctx.fillStyle = p.color;
            ctx.globalAlpha = p.opacity;
            ctx.fill();
        }});
        ctx.globalAlpha = 1;
        for (var i = 0; i < particles.length; i++) {{
            for (var j = i + 1; j < particles.length; j++) {{
                var dx = particles[i].x - particles[j].x;
                var dy = particles[i].y - particles[j].y;
                var dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 100) {{
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.strokeStyle = 'rgba(255, 255, 255, ' + (0.06 * (1 - dist / 100)) + ')';
                    ctx.lineWidth = 0.5;
                    ctx.stroke();
                }}
            }}
        }}
        requestAnimationFrame(draw);
    }}
    resize();
    createParticles();
    draw();
    window.addEventListener('resize', function() {{ resize(); createParticles(); }});
}})();
</script>
<script src="script.js"></script>
<script src="tabs.js"></script>
</body>
</html>'''
    
    return html

if __name__ == "__main__":
    # Test with mock data
    logging.basicConfig(level=logging.INFO)
    print("Use league_data_adapter.py to get real data, then pass to generate_full_html()")
