import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import plotly.express as px

st.set_page_config(page_title="Office World Cup Prediction League", layout="wide", page_icon="🏆")

# Date check for special June 24, 2026 AEST event (confetti + Portugal fire emoji)
sydney_tz = pytz.timezone('Australia/Sydney')
now_sydney = datetime.now(sydney_tz)
is_special_day = (now_sydney.year == 2026 and now_sydney.month == 6 and now_sydney.day == 24)




# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
SCORING_RULES = {
    'Pot A': {
        'win': 2, 'draw': 1, '1st_place': 3, '2nd_place': 2, 
        'Round of 32': 1, 'Round of 16': 2, 'Quarter-finals': 3, 
        'Semi-finals': 4, 'Final': 5, 'Winner': 5
    },
    'Pot B': {
        'win': 2.5, 'draw': 1, '1st_place': 3, '2nd_place': 2, 
        'Round of 32': 1, 'Round of 16': 2.5, 'Quarter-finals': 3.5, 
        'Semi-finals': 4.5, 'Final': 5.5, 'Winner': 5.5
    },
    'Pot C': {
        'win': 3, 'draw': 1.5, '1st_place': 3, '2nd_place': 2, 
        'Round of 32': 1, 'Round of 16': 3, 'Quarter-finals': 4, 
        'Semi-finals': 5, 'Final': 6, 'Winner': 6
    },
    'Pot D': {
        'win': 3.5, 'draw': 1.5, '1st_place': 3, '2nd_place': 2, 
        'Round of 32': 1.5, 'Round of 16': 3.5, 'Quarter-finals': 4.5, 
        'Semi-finals': 6, 'Final': 6.5, 'Winner': 6
    }
}

# -----------------------------------------------------------------------------
# DATA LOADING
# -----------------------------------------------------------------------------
@st.cache_data
def load_users():
    try:
        df = pd.read_excel("users.xlsx")
        df.columns = df.columns.str.strip()
        return df
    except FileNotFoundError:
        st.error("⚠️ 'users.xlsx' not found. Please ensure the file is in the application directory.")
        st.stop()

user_picks = load_users()

def parse_match_datetime(date_str, time_str):
    # Parses e.g., date_str = '2026-06-11', time_str = '13:00 UTC-6'
    try:
        if not time_str or time_str == 'TBD' or 'UTC' not in time_str:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            dt = dt.replace(tzinfo=pytz.UTC)
            return dt.astimezone(pytz.timezone('Australia/Sydney'))
            
        time_part = time_str.split(' ')[0] # '13:00'
        utc_part = time_str.split(' ')[1] # 'UTC-6'
        
        offset_hours = int(utc_part.replace('UTC', '')) # -6
        
        dt_naive = datetime.strptime(f"{date_str} {time_part}", "%Y-%m-%d %H:%M")
        dt_utc = dt_naive - timedelta(hours=offset_hours)
        dt_utc = dt_utc.replace(tzinfo=pytz.UTC)
        
        return dt_utc.astimezone(pytz.timezone('Australia/Sydney'))
    except Exception:
        # Fallback to date only if parsing fails
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        dt = dt.replace(tzinfo=pytz.UTC)
        return dt.astimezone(pytz.timezone('Australia/Sydney'))

@st.cache_data(ttl=3600)
def fetch_tournament_data():
    sydney_tz = pytz.timezone('Australia/Sydney')
    fetch_time = datetime.now(sydney_tz).strftime("%A, %d %b %Y at %I:%M %p AEST")

    url = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
    processed_matches = []
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        for match in data.get('matches', []):
            date_str = match.get('date', '')
            time_str = match.get('time', '')
            
            aest_dt = parse_match_datetime(date_str, time_str)
            
            home_team = match.get('team1', 'TBD')
            away_team = match.get('team2', 'TBD')
            match_round = match.get('round', '')
            group = match.get('group', '')
            
            # Check for score
            score = match.get('score', {})
            home_goals = 0
            away_goals = 0
            winner = None
            is_draw = False
            is_finished = False
            
            if score and 'ft' in score:
                is_finished = True
                home_goals = score['ft'][0]
                away_goals = score['ft'][1]
                
                # Handle penalties / extra time winner determination
                if 'p' in score:
                    if score['p'][0] > score['p'][1]:
                        winner = home_team
                    else:
                        winner = away_team
                elif 'aet' in score or 'et' in score:
                    et_score = score.get('aet', score.get('et'))
                    if et_score[0] > et_score[1]:
                        winner = home_team
                    elif et_score[1] > et_score[0]:
                        winner = away_team
                    else:
                        is_draw = True
                else:
                    if home_goals > away_goals:
                        winner = home_team
                    elif away_goals > home_goals:
                        winner = away_team
                    else:
                        is_draw = True
            
            processed_matches.append({
                'date_aest': aest_dt,
                'home': home_team,
                'away': away_team,
                'home_goals': home_goals,
                'away_goals': away_goals,
                'winner': winner,
                'is_draw': is_draw,
                'is_finished': is_finished,
                'stage': match_round,
                'group': group
            })
            
        return pd.DataFrame(processed_matches), fetch_time
        
    except Exception as e:
        st.error(f"Error fetching openfootball data: {e}")
        return pd.DataFrame(columns=['date_aest', 'home', 'away', 'home_goals', 'away_goals', 'winner', 'is_draw', 'is_finished', 'stage', 'group']), fetch_time

matches_df, last_refreshed = fetch_tournament_data()

# -----------------------------------------------------------------------------
# TEAM NAME NORMALIZATION AND HELPER FUNCTIONS
# -----------------------------------------------------------------------------
TEAM_NAME_MAPPING = {
    "T\u00fcrkiye": "Turkey",
    "Cabo Verde": "Cape Verde",
    "C\u00f4te d\u2019Ivoire": "Ivory Coast",
    "IR Iran": "Iran",
    "Czechia": "Czech Republic"
}

def abbreviate_team(name):
    special_abbrevs = {
        "Argentina": "Arg",
        "Australia": "Aus",
        "Austria": "Aut",
        "Belgium": "Bel",
        "Brazil": "Bra",
        "Canada": "Can",
        "Colombia": "Col",
        "Croatia": "Cro",
        "Czech Republic": "Cze",
        "Czechia": "Cze",
        "Denmark": "Den",
        "Ecuador": "Ecu",
        "England": "Eng",
        "France": "Fra",
        "Germany": "Ger",
        "Ghana": "Gha",
        "Haiti": "Hai",
        "Iran": "IRN",
        "IR Iran": "IRN",
        "Ivory Coast": "Civ",
        "C\u00f4te d'Ivoire": "Civ",
        "C\u00f4te d\u2019Ivoire": "Civ",
        "Japan": "Jpn",
        "Jordan": "Jor",
        "Mexico": "Mex",
        "Morocco": "Mar",
        "Netherlands": "Ned",
        "New Zealand": "NZL",
        "Norway": "Nor",
        "Paraguay": "Par",
        "Portugal": "Por",
        "Saudi Arabia": "KSA",
        "Scotland": "Sco",
        "Senegal": "Sen",
        "South Africa": "RSA",
        "Spain": "Esp",
        "Sweden": "Swe",
        "Switzerland": "Sui",
        "Turkey": "Tur",
        "T\u00fcrkiye": "Tur",
        "Uruguay": "Uru",
        "USA": "USA",
        "United States": "USA",
        "Uzbekistan": "Uzb",
        "Cabo Verde": "CPV",
        "Cape Verde": "CPV",
        "Cura\u00e7ao": "Cur",
        "Curaao": "Cur",
        "South Korea": "KOR"
    }
    if name in special_abbrevs:
        return special_abbrevs[name]
    # Fallback to first 3 letters capitalized
    clean_name = str(name).replace(" ", "")
    return clean_name[:3].title()

def get_tooltip_html(country, pot_category, matches_df):
    if not country or pd.isna(country) or str(country).strip() == "":
        return ""
    country_str = str(country).strip()
    norm_c = TEAM_NAME_MAPPING.get(country_str, country_str)
    
    # Find all matches for this country that are finished
    country_matches = matches_df[
        (matches_df['is_finished'] == True) & 
        ((matches_df['home'] == norm_c) | (matches_df['away'] == norm_c))
    ]
    if country_matches.empty:
        return '<span class="tooltip-text"><span style="color: #94a3b8; font-style: italic;">Matches yet to be played.</span></span>'
    
    html_lines = []
    for _, match in country_matches.iterrows():
        home_abbr = abbreviate_team(match['home'])
        away_abbr = abbreviate_team(match['away'])
        home_goals = match['home_goals']
        away_goals = match['away_goals']
        
        # Calculate points relative to this country
        pts = 0
        match_stage = str(match['stage'])
        if pot_category in SCORING_RULES:
            # 1. Match Result Points (Group Stage)
            if "Matchday" in match_stage:
                if match['winner'] == norm_c:
                    pts += SCORING_RULES[pot_category]['win']
                elif match['is_draw']:
                    pts += SCORING_RULES[pot_category]['draw']
            
            # 2. Advancement Points
            if "Round of 32" in match_stage:
                pts += SCORING_RULES[pot_category]['Round of 32']
            elif "Round of 16" in match_stage:
                pts += SCORING_RULES[pot_category]['Round of 16']
            elif "Quarter" in match_stage:
                pts += SCORING_RULES[pot_category]['Quarter-finals']
            elif "Semi" in match_stage:
                pts += SCORING_RULES[pot_category]['Semi-finals']
            elif "Final" in match_stage and "Third" not in match_stage:
                pts += SCORING_RULES[pot_category]['Final']
                if match['winner'] == norm_c:
                    pts += SCORING_RULES[pot_category]['Winner']
        
        pts_str = f"+{pts:g} pts" if pts > 0 else "0 pts"
        
        # Determine result relative to this country
        if match['is_draw']:
            res_html = f'<span style="color: #F59E0B; font-weight: bold; background: rgba(245, 158, 11, 0.15); padding: 1px 4px; border-radius: 3px; font-size: 0.75rem;">D ({pts_str})</span>'
        elif match['winner'] == norm_c:
            res_html = f'<span style="color: #10B981; font-weight: bold; background: rgba(16, 185, 129, 0.15); padding: 1px 4px; border-radius: 3px; font-size: 0.75rem;">W ({pts_str})</span>'
        else:
            res_html = f'<span style="color: #EF4444; font-weight: bold; background: rgba(239, 68, 68, 0.15); padding: 1px 4px; border-radius: 3px; font-size: 0.75rem;">L ({pts_str})</span>'
            
        html_lines.append(f'<div style="white-space: nowrap; margin-bottom: 4px;">{home_abbr} Vs {away_abbr}, {home_goals} - {away_goals} {res_html}</div>')
        
    tooltip_inner = "".join(html_lines)
    return f'<span class="tooltip-text">{tooltip_inner}</span>'

# -----------------------------------------------------------------------------
# SCORING ENGINE
# -----------------------------------------------------------------------------
def calculate_scores_and_timeline(picks_df, results_df):
    leaderboard_records = []
    points_timeline = []
    
    for _, row in picks_df.iterrows():
        total_points = 0
        player_name = row['Name']
        
        for pot_category in ['Pot A', 'Pot B', 'Pot C', 'Pot D']:
            if pot_category not in row:
                continue
            team_picked = row[pot_category]
            
            if not results_df.empty:
                for _, match in results_df.iterrows():
                    match_date = match['date_aest'].date()
                    match_stage = str(match['stage'])
                    points_earned_in_match = 0
                    
                    team_picked_normalized = TEAM_NAME_MAPPING.get(team_picked, team_picked)
                    if match['is_finished'] and (match['home'] == team_picked_normalized or match['away'] == team_picked_normalized):
                        # 1. Match Result Points (Group Stage)
                        if "Matchday" in match_stage:
                            if match['winner'] == team_picked_normalized:
                                points_earned_in_match += SCORING_RULES[pot_category]['win']
                            elif match['is_draw']:
                                points_earned_in_match += SCORING_RULES[pot_category]['draw']
                        
                        # 2. Advancement Points
                        if "Round of 32" in match_stage:
                            points_earned_in_match += SCORING_RULES[pot_category]['Round of 32']
                        elif "Round of 16" in match_stage:
                            points_earned_in_match += SCORING_RULES[pot_category]['Round of 16']
                        elif "Quarter" in match_stage:
                            points_earned_in_match += SCORING_RULES[pot_category]['Quarter-finals']
                        elif "Semi" in match_stage:
                            points_earned_in_match += SCORING_RULES[pot_category]['Semi-finals']
                        elif "Final" in match_stage and "Third" not in match_stage:
                            points_earned_in_match += SCORING_RULES[pot_category]['Final']
                            # If they won the final
                            if match['winner'] == team_picked_normalized:
                                points_earned_in_match += SCORING_RULES[pot_category]['Winner']
                                
                    if points_earned_in_match > 0:
                        total_points += points_earned_in_match
                        points_timeline.append({
                            'Date': match_date,
                            'Name': player_name,
                            'Pot': pot_category,
                            'Team': team_picked,
                            'Points Earned': points_earned_in_match
                        })

        leaderboard_records.append({
            'Name': player_name,
            'Pot A': row.get('Pot A', ''),
            'Pot B': row.get('Pot B', ''),
            'Pot C': row.get('Pot C', ''),
            'Pot D': row.get('Pot D', ''),
            'Points': total_points
        })
        
    final_df = pd.DataFrame(leaderboard_records)
    timeline_df = pd.DataFrame(points_timeline)
    
    if not final_df.empty:
        final_df = final_df.sort_values(by='Points', ascending=False).reset_index(drop=True)
        final_df.index = final_df.index + 1
        final_df.insert(0, 'Rank', final_df.index)
        
    if not timeline_df.empty:
        timeline_df = timeline_df.sort_values('Date')
        
    return final_df, timeline_df

# -----------------------------------------------------------------------------
# DENSE TIMELINE GENERATION FOR TRACKER
# -----------------------------------------------------------------------------
def build_filtered_timeline(picks_df, raw_timeline_df, active_users, selected_pots_filter):
    if raw_timeline_df.empty or not active_users:
        return pd.DataFrame()
    
    all_dates = sorted(list(raw_timeline_df['Date'].dropna().unique()))
    if not all_dates:
        return pd.DataFrame()
        
    start_date = all_dates[0] - pd.Timedelta(days=1)
    
    dense_records = []
    
    for player_name in active_users:
        user_rows = picks_df[picks_df['Name'] == player_name]
        if user_rows.empty:
            continue
        user_row = user_rows.iloc[0]
        
        pot_a_team = user_row.get('Pot A', '')
        pot_b_team = user_row.get('Pot B', '')
        pot_c_team = user_row.get('Pot C', '')
        pot_d_team = user_row.get('Pot D', '')
        
        # Initialize cumulative points per pot
        cum_points = {'Pot A': 0.0, 'Pot B': 0.0, 'Pot C': 0.0, 'Pot D': 0.0}
        
        # Add start date row (0 points)
        dense_records.append({
            'Date': start_date,
            'Name': player_name,
            'Pot A Team': pot_a_team,
            'Pot A Points': 0.0,
            'Pot B Team': pot_b_team,
            'Pot B Points': 0.0,
            'Pot C Team': pot_c_team,
            'Pot C Points': 0.0,
            'Pot D Team': pot_d_team,
            'Pot D Points': 0.0,
            'Total Points': 0.0,
            'Plotted Points': 0.0
        })
        
        # Filter raw timeline for this user
        user_timeline = raw_timeline_df[raw_timeline_df['Name'] == player_name]
        
        for date in all_dates:
            # Find points earned on this date
            date_points = user_timeline[user_timeline['Date'] == date]
            
            for pot in ['Pot A', 'Pot B', 'Pot C', 'Pot D']:
                pot_earned = date_points[date_points['Pot'] == pot]['Points Earned'].sum()
                cum_points[pot] += pot_earned
                
            total = sum(cum_points.values())
            plotted = sum(cum_points[p] for p in selected_pots_filter if p in cum_points)
            
            dense_records.append({
                'Date': date,
                'Name': player_name,
                'Pot A Team': pot_a_team,
                'Pot A Points': cum_points['Pot A'],
                'Pot B Team': pot_b_team,
                'Pot B Points': cum_points['Pot B'],
                'Pot C Team': pot_c_team,
                'Pot C Points': cum_points['Pot C'],
                'Pot D Team': pot_d_team,
                'Pot D Points': cum_points['Pot D'],
                'Total Points': total,
                'Plotted Points': plotted
            })
            
    return pd.DataFrame(dense_records)

leaderboard_df, timeline_df = calculate_scores_and_timeline(user_picks, matches_df)

# -----------------------------------------------------------------------------
# UI/UX & LAYOUT
# -----------------------------------------------------------------------------
st.title("🏆 Office World Cup Prediction League")
st.markdown(f"**Last Refreshed:** {last_refreshed}")

# -----------------------------------------------------------------------------
# STATISTICS OVERVIEW
# -----------------------------------------------------------------------------
num_users = len(user_picks)

col1, col2, col3, col4 = st.columns(4)

def render_pot_progress_tile(col, pot_name, icon, bar_color):
    with col:
        with st.container(height=170, border=True):
            st.markdown(f"<div style='font-size: 0.8rem; font-weight: 600; color: #555; text-transform: uppercase; letter-spacing: 0.5px;'>{icon} Top {pot_name}</div>", unsafe_allow_html=True)
            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
            
            top_teams = user_picks[pot_name].value_counts().head(3)
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            
            for rank, (team, count) in enumerate(top_teams.items(), 1):
                pct = (count / num_users) * 100
                medal = medals.get(rank, "")
                
                st.markdown(f"""
                <div style='margin-bottom: 6px;'>
                    <div style='font-size: 0.78rem; color: #111; display: flex; justify-content: space-between; align-items: center;'>
                        <span style='white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 110px;'>{medal} <b>{team}</b></span>
                        <span style='color: gray; font-size: 0.75rem; flex-shrink: 0;'>{count} ({pct:.0f}%)</span>
                    </div>
                    <div style='background-color: rgba(128, 128, 128, 0.12); border-radius: 3px; height: 5px; width: 100%; margin-top: 2px; overflow: hidden;'>
                        <div style='background-color: {bar_color}; height: 100%; width: {pct}%;'></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

render_pot_progress_tile(col1, 'Pot A', '🥇', '#3B82F6')
render_pot_progress_tile(col2, 'Pot B', '🥈', '#10B981')
render_pot_progress_tile(col3, 'Pot C', '🥉', '#F59E0B')
render_pot_progress_tile(col4, 'Pot D', '🔥', '#EF4444')

st.divider()

tab1, tab2, tab3, tab4 = st.tabs(["📊 Leaderboard", "🗓️ Schedule & Results", "📈 Title Race Tracker", "📜 Game Rules"])

with tab1:
    st.subheader("🥇 Current Standings")
    
    # Extract all unique countries selected by users across all pots
    selected_pots = ['Pot A', 'Pot B', 'Pot C', 'Pot D']
    unique_countries = set()
    for pot in selected_pots:
        if pot in user_picks.columns:
            for country in user_picks[pot].dropna().astype(str):
                cleaned = country.strip()
                if cleaned:
                    unique_countries.add(cleaned)
    all_countries = sorted(list(unique_countries))
    
    selected_country = st.selectbox(
        "🔍 Filter standings by country pick:",
        options=all_countries,
        index=None,
        placeholder="Search or select a country (e.g., Brazil)..."
    )
    
    # Filter the standings dataframe
    display_df = leaderboard_df
    if selected_country:
        display_df = leaderboard_df[
            (leaderboard_df['Pot A'] == selected_country) |
            (leaderboard_df['Pot B'] == selected_country) |
            (leaderboard_df['Pot C'] == selected_country) |
            (leaderboard_df['Pot D'] == selected_country)
        ]
        st.info(f"Showing results filtered by country: **{selected_country}** ({len(display_df)} user(s))")

    if not display_df.empty:
        # Construct the HTML table without leading spaces to avoid Markdown pre block interpretation
        table_html = """<style>
.league-container {
    height: 5000px;
    max-height: 5000px;
    overflow-y: auto;
    border: 1px solid rgba(128, 128, 128, 0.2);
    border-radius: 8px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}
.league-table {
    width: 100%;
    border-collapse: collapse;
    font-family: inherit;
    color: inherit;
    font-size: 0.9rem;
}
.league-table th {
    background-color: rgba(128, 128, 128, 0.08);
    font-weight: 600;
    text-transform: uppercase;
    font-size: 0.75rem;
    letter-spacing: 0.5px;
    padding: 12px 16px;
    border-bottom: 2px solid rgba(128, 128, 128, 0.15);
    position: sticky;
    top: 0;
    z-index: 10;
    text-align: left;
}
.league-table td {
    padding: 12px 16px;
    border-bottom: 1px solid rgba(128, 128, 128, 0.1);
    text-align: left;
}
.league-table tr:last-child td {
    border-bottom: none;
}
.league-table tr:hover {
    background-color: rgba(128, 128, 128, 0.03);
}
.top3-highlight {
    background-color: rgba(6, 182, 212, 0.12) !important;
    color: #0891b2 !important;
    font-weight: 700 !important;
}
/* Beautiful tooltip styles for country hover effect */
.tooltip-container {
    position: relative;
    cursor: help;
    border-bottom: 1px dashed rgba(128, 128, 128, 0.4);
    display: inline-block;
}
.tooltip-text {
    visibility: hidden;
    width: 220px;
    background-color: rgba(15, 23, 42, 0.96);
    backdrop-filter: blur(8px);
    color: #f1f5f9;
    text-align: left;
    border-radius: 8px;
    padding: 10px 12px;
    position: absolute;
    z-index: 100;
    bottom: 130%;
    left: 50%;
    transform: translateX(-50%) translateY(4px);
    opacity: 0;
    transition: opacity 0.2s ease, transform 0.2s ease;
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.4), 0 4px 6px -4px rgba(0, 0, 0, 0.4);
    border: 1px solid rgba(255, 255, 255, 0.12);
    font-size: 0.78rem;
    font-weight: 500;
    line-height: 1.4;
    pointer-events: none;
}
.tooltip-text::after {
    content: "";
    position: absolute;
    top: 100%;
    left: 50%;
    margin-left: -6px;
    border-width: 6px;
    border-style: solid;
    border-color: rgba(15, 23, 42, 0.96) transparent transparent transparent;
}
.tooltip-container:hover .tooltip-text {
    visibility: visible;
    opacity: 1;
    transform: translateX(-50%) translateY(0);
}
</style>
<div class="league-container">
<table class="league-table">
<thead>
<tr>
<th>Rank</th>
<th>Name</th>
<th>Pot A</th>
<th>Pot B</th>
<th>Pot C</th>
<th>Pot D</th>
<th>Points</th>
</tr>
</thead>
<tbody>"""
        # Helper to render cell HTML with optional fire emoji for Portugal on special day
        def get_pot_html(pot_val, pot_category):
            if not pot_val or pd.isna(pot_val):
                return ""
            display_val = f"{pot_val} 🔥" if (is_special_day and str(pot_val).strip().lower() == "portugal") else pot_val
            return f"<span class='tooltip-container'>{display_val}{get_tooltip_html(pot_val, pot_category, matches_df)}</span>"

        for _, row in display_df.iterrows():
            rank = row['Rank']
            name = row['Name']
            pot_a = row['Pot A']
            pot_b = row['Pot B']
            pot_c = row['Pot C']
            pot_d = row['Pot D']
            points = f"{row['Points']:.1f}"
            
            glow_class = ""
            if rank in [1, 2, 3]:
                glow_class = " class='top3-highlight'"
                
            # Wrap country names with the tooltip markup
            pot_a_html = get_pot_html(pot_a, 'Pot A')
            pot_b_html = get_pot_html(pot_b, 'Pot B')
            pot_c_html = get_pot_html(pot_c, 'Pot C')
            pot_d_html = get_pot_html(pot_d, 'Pot D')
            
            table_html += f"""<tr>
<td>{rank}</td>
<td{glow_class}>{name}</td>
<td>{pot_a_html}</td>
<td>{pot_b_html}</td>
<td>{pot_c_html}</td>
<td>{pot_d_html}</td>
<td><b>{points}</b></td>
</tr>"""
            
        table_html += """</tbody>
</table>
</div>"""
        st.markdown(table_html, unsafe_allow_html=True)
    else:
        if selected_country:
            st.warning(f"No users selected **{selected_country}**.")
        else:
            st.info("No data available to calculate standings.")

with tab2:
    st.subheader("Group Stage Schedule (AEST)")
    
    if not matches_df.empty:
        # Filter for group matches
        group_matches = matches_df[matches_df['group'].notna() & (matches_df['group'] != '')]
        
        min_date = group_matches['date_aest'].min().date()
        max_date = group_matches['date_aest'].max().date()
        
        selected_date = st.date_input(
            "🗓️ Filter matches by date:", 
            value=None, 
            min_value=min_date, 
            max_value=max_date,
            help="Select a specific day to see only matches played on that date. Click 'x' to clear the filter."
        )
        
        if selected_date is not None:
            group_matches = group_matches[group_matches['date_aest'].dt.date == selected_date]
            
        if group_matches.empty:
            st.info(f"No matches scheduled for {selected_date.strftime('%d %b %Y')}.")
        else:
            groups = sorted(group_matches['group'].unique())
            
            # Display 3 groups per row
            cols_per_row = 3
            
            for i in range(0, len(groups), cols_per_row):
                cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
                    if i + j < len(groups):
                        group_name = groups[i + j]
                        with cols[j]:
                            with st.container(height=350, border=True):
                                st.markdown(f"### {group_name}")
                                g_matches = group_matches[group_matches['group'] == group_name].sort_values(by='date_aest')
                                
                                for _, match in g_matches.iterrows():
                                    time_str = match['date_aest'].strftime("%d %b %I:%M %p")
                                    if match['is_finished']:
                                        result_str = f"**{match['home_goals']} - {match['away_goals']}**"
                                    else:
                                        result_str = "Vs"
                                    
                                    st.markdown(f"**{time_str}**<br>{match['home']} {result_str} {match['away']}", unsafe_allow_html=True)
                                    st.divider()
    else:
        st.info("No schedule data available.")

with tab3:
    st.subheader("Title Race Tracker")
    if not timeline_df.empty:
        # Create the filter columns
        f_col1, f_col2, f_col3 = st.columns(3)
        
        with f_col1:
            all_users = sorted(user_picks['Name'].dropna().unique())
            selected_users = st.multiselect(
                "👤 Filter by Username:",
                options=all_users,
                default=all_users,
                help="Select which users to display on the tracker."
            )
            
        with f_col2:
            # Extract all unique countries from user_picks
            all_teams = sorted(list(set(
                user_picks['Pot A'].dropna().tolist() +
                user_picks['Pot B'].dropna().tolist() +
                user_picks['Pot C'].dropna().tolist() +
                user_picks['Pot D'].dropna().tolist()
            )))
            selected_teams = st.multiselect(
                "🌍 Filter by Team Picked:",
                options=all_teams,
                help="Only show users who selected any of these teams."
            )
            
        with f_col3:
            selected_pots_filter = st.multiselect(
                "🏆 Filter by Pot Category:",
                options=["Pot A", "Pot B", "Pot C", "Pot D"],
                default=["Pot A", "Pot B", "Pot C", "Pot D"],
                help="Select which Pot categories contribute to the plotted points."
            )
            
        # Resolve active users based on team filters
        if selected_teams:
            users_with_teams = user_picks[
                user_picks['Pot A'].isin(selected_teams) |
                user_picks['Pot B'].isin(selected_teams) |
                user_picks['Pot C'].isin(selected_teams) |
                user_picks['Pot D'].isin(selected_teams)
            ]['Name'].unique()
            active_users = [u for u in selected_users if u in users_with_teams]
        else:
            active_users = selected_users
            
        # Resolve pots
        active_pots = selected_pots_filter if selected_pots_filter else ["Pot A", "Pot B", "Pot C", "Pot D"]
        
        # Build the filtered dense dataset
        chart_df = build_filtered_timeline(user_picks, timeline_df, active_users, active_pots)
        
        if not chart_df.empty:
            # Plot the line graph
            fig = px.line(
                chart_df,
                x='Date',
                y='Plotted Points',
                color='Name',
                markers=True,
                custom_data=[
                    'Name',          # 0
                    'Pot A Team',    # 1
                    'Pot A Points',  # 2
                    'Pot B Team',    # 3
                    'Pot B Points',  # 4
                    'Pot C Team',    # 5
                    'Pot C Points',  # 6
                    'Pot D Team',    # 7
                    'Pot D Points',  # 8
                    'Total Points'   # 9
                ]
            )
            
            # Setup custom hover template
            hover_temp = (
                "<b>%{customdata[0]}</b><br>"
                "Date: %{x|%Y-%m-%d}<br>"
                "Plotted Points: %{y:.1f} pts<br>"
                "Total Points: %{customdata[9]:.1f} 🔥<br>"
                "<br>"
                "🥇 Pot A: <b>%{customdata[1]}</b> (%{customdata[2]:.1f} pts)<br>"
                "🥈 Pot B: <b>%{customdata[3]}</b> (%{customdata[4]:.1f} pts)<br>"
                "🥉 Pot C: <b>%{customdata[5]}</b> (%{customdata[6]:.1f} pts)<br>"
                "🔥 Pot D: <b>%{customdata[7]}</b> (%{customdata[8]:.1f} pts)<br>"
                "<extra></extra>"
            )
            
            fig.update_traces(hovertemplate=hover_temp)
            
            # Update layout aesthetics for a premium look
            fig.update_layout(
                xaxis_title="Match Date",
                yaxis_title="Cumulative Points",
                hovermode="closest",
                legend_title="Player",
                margin=dict(l=40, r=40, t=20, b=40),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(
                    showgrid=True,
                    gridcolor="rgba(128, 128, 128, 0.1)",
                    zeroline=False
                ),
                yaxis=dict(
                    showgrid=True,
                    gridcolor="rgba(128, 128, 128, 0.1)",
                    zeroline=False
                )
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No matching data found for the selected filters.")
    else:
        st.info("The race hasn't started yet! Graph will populate once matches are played.")

with tab4:
    st.subheader("Game Rules & Scoring System")
    
    st.markdown("""
    Welcome to the Office World Cup Prediction League! The scoring system is designed to reward risk. 
    
    Teams are divided into four Pots (A, B, C, D) based on their real-world strength:
    - **Pot A**: The tournament favorites (e.g., Brazil, France).
    - **Pot D**: The underdogs.
    
    Because Pot D teams are less likely to win, you are rewarded with **more points** when they achieve success compared to Pot A teams.
    """)
    
    rules_data = {
        "Tournament Stage": ["Group Stages", "Group Stages", "Group Stages", "Group Stages", "Round of 32", "Round of 16", "Round of 8 (QF)", "Semi-Finals", "Finals", "Trophy"],
        "Achievement": ["Match Win", "Match Draw", "1st Place Finish", "2nd Place Finish", "Qualify for Round of 32", "Qualify for Round of 16", "Qualify for Round of 8", "Qualify for Semi-Finals", "Qualify for the Final", "Win the World Cup 🏆"],
        "Pot A": [2, 1, 3, 2, 1, 2, 3, 4, 5, 5],
        "Pot B": [2.5, 1, 3, 2, 1, 2.5, 3.5, 4.5, 5.5, 5.5],
        "Pot C": [3, 1.5, 3, 2, 1, 3, 4, 5, 6, 6],
        "Pot D": [3.5, 1.5, 3, 2, 1.5, 3.5, 4.5, 5.5, 6.5, 6]
    }
    rules_df = pd.DataFrame(rules_data)
    
    # Format numbers to remove trailing zeros
    for col in ['Pot A', 'Pot B', 'Pot C', 'Pot D']:
        rules_df[col] = rules_df[col].apply(lambda x: f"{x:g}")
    
    # Hide index using st.dataframe instead of st.table for a cleaner look
    st.dataframe(rules_df, use_container_width=True, hide_index=True)
    
    st.markdown("""
    ### 💡 Examples
    - **Group Stage Upset**: If your **Pot A** team wins a group stage match, you get **2 points**. But if your **Pot D** team pulls off a win, you get **3.5 points**!
    - **Making a Deep Run**: If your **Pot B** team qualifies for the Semi-Finals, you are awarded **4.5 points**.
    - **Cumulative Scoring**: You earn points for *every* stage your team advances through. If your Pot C team wins the whole tournament, you get points for qualifying for the Round of 32, Round of 16, Quarters, Semis, Finals, AND winning the Trophy!
    """)

# Trigger confetti celebration at the end of execution (after all UI elements render)
# Confetti is only active on June 24, 2026 (Australia/Sydney time)
if is_special_day and "confetti_popped" not in st.session_state:
    st.session_state["confetti_popped"] = True
    components.html(
        """
        <script>
            const parentDoc = window.parent.document;
            const fireConfetti = () => {
                if (window.parent.confetti) {
                    // Left corner burst
                    window.parent.confetti({
                        particleCount: 150,
                        spread: 80,
                        angle: 60,
                        origin: { x: 0, y: 0.8 }
                    });
                    // Right corner burst
                    window.parent.confetti({
                        particleCount: 150,
                        spread: 80,
                        angle: 120,
                        origin: { x: 1, y: 0.8 }
                    });
                    // Center burst
                    window.parent.confetti({
                        particleCount: 100,
                        spread: 100,
                        origin: { x: 0.5, y: 0.6 }
                    });
                }
            };

            if (!parentDoc.getElementById('canvas-confetti-script')) {
                const script = parentDoc.createElement('script');
                script.id = 'canvas-confetti-script';
                script.src = 'https://cdn.jsdelivr.net/npm/canvas-confetti@1.9.3/dist/confetti.browser.min.js';
                script.onload = fireConfetti;
                parentDoc.head.appendChild(script);
            } else {
                fireConfetti();
            }
        </script>
        """,
        height=0,
    )