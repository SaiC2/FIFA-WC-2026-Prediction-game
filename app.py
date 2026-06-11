import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import plotly.express as px

st.set_page_config(page_title="Office World Cup Prediction League", layout="wide", page_icon="🏆")

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
                    
                    if match['is_finished'] and (match['home'] == team_picked or match['away'] == team_picked):
                        # 1. Match Result Points (Group Stage)
                        if "Matchday" in match_stage:
                            if match['winner'] == team_picked:
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
                            if match['winner'] == team_picked:
                                points_earned_in_match += SCORING_RULES[pot_category]['Winner']
                                
                    if points_earned_in_match > 0:
                        total_points += points_earned_in_match
                        points_timeline.append({
                            'Date': match_date,
                            'Name': player_name,
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
        timeline_df = timeline_df.groupby(['Name', 'Date'])['Points Earned'].sum().reset_index()
        timeline_df = timeline_df.sort_values('Date')
        timeline_df['Cumulative Points'] = timeline_df.groupby('Name')['Points Earned'].cumsum()
        
    return final_df, timeline_df

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
    if not leaderboard_df.empty:
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
        for _, row in leaderboard_df.iterrows():
            rank = row['Rank']
            name = row['Name']
            pot_a = row['Pot A']
            pot_b = row['Pot B']
            pot_c = row['Pot C']
            pot_d = row['Pot D']
            points = f"{row['Points']:.1f} 🔥"
            
            glow_class = ""
            if rank in [1, 2, 3]:
                glow_class = " class='top3-highlight'"
                
            table_html += f"""<tr>
<td>{rank}</td>
<td{glow_class}>{name}</td>
<td>{pot_a}</td>
<td>{pot_b}</td>
<td>{pot_c}</td>
<td>{pot_d}</td>
<td><b>{points}</b></td>
</tr>"""
            
        table_html += """</tbody>
</table>
</div>"""
        st.markdown(table_html, unsafe_allow_html=True)
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
        start_date = timeline_df['Date'].min() - pd.Timedelta(days=1)
        start_points = []
        for player in user_picks['Name'].unique():
            if player in timeline_df['Name'].values:
                start_points.append({'Name': player, 'Date': start_date, 'Points Earned': 0, 'Cumulative Points': 0})
        
        full_timeline_df = pd.concat([pd.DataFrame(start_points), timeline_df], ignore_index=True).sort_values(by=['Name', 'Date'])
        
        fig = px.line(
            full_timeline_df, 
            x='Date', 
            y='Cumulative Points', 
            color='Name',
            markers=True,
            hover_data={"Name": True, "Date": True, "Cumulative Points": True}
        )
        
        fig.update_layout(
            xaxis_title="Match Date",
            yaxis_title="Total Points",
            hovermode="x unified",
            legend_title="Player"
        )
        st.plotly_chart(fig, use_container_width=True)
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