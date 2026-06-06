import pandas as pd
from datetime import datetime

# Import the scoring logic and rules from app.py
from app import calculate_scores_and_timeline, SCORING_RULES

def test_group_stage_win_pot_a_and_d():
    # Setup mock user picks
    picks_data = {
        'Name': ['Alice', 'Bob'],
        'Pot A': ['Japan', 'Brazil'],
        'Pot B': ['Croatia', 'England'],
        'Pot C': ['Senegal', 'USA'],
        'Pot D': ['Haiti', 'Morocco']
    }
    picks_df = pd.DataFrame(picks_data)
    
    # Setup mock results
    # Japan (Pot A for Alice) wins a group stage match
    # Haiti (Pot D for Alice) wins a group stage match
    results_data = [
        {
            'date_aest': pd.to_datetime('2026-06-11'),
            'home': 'Japan',
            'away': 'Germany',
            'home_goals': 2,
            'away_goals': 0,
            'winner': 'Japan',
            'is_draw': False,
            'is_finished': True,
            'stage': 'Matchday 1',
            'group': 'Group A'
        },
        {
            'date_aest': pd.to_datetime('2026-06-12'),
            'home': 'Haiti',
            'away': 'France',
            'home_goals': 1,
            'away_goals': 0,
            'winner': 'Haiti',
            'is_draw': False,
            'is_finished': True,
            'stage': 'Matchday 1',
            'group': 'Group B'
        }
    ]
    results_df = pd.DataFrame(results_data)
    
    # Run calculation
    leaderboard_df, timeline_df = calculate_scores_and_timeline(picks_df, results_df)
    
    # Alice points: Japan win (Pot A) = 2 pts. Haiti win (Pot D) = 3.5 pts. Total = 5.5
    alice_row = leaderboard_df[leaderboard_df['Name'] == 'Alice'].iloc[0]
    assert alice_row['Points'] == 5.5, f"Expected Alice to have 5.5 points, got {alice_row['Points']}"
    
    # Bob points: 0
    bob_row = leaderboard_df[leaderboard_df['Name'] == 'Bob'].iloc[0]
    assert bob_row['Points'] == 0.0, f"Expected Bob to have 0 points, got {bob_row['Points']}"
    print("test_group_stage_win_pot_a_and_d passed!")

def test_draws_across_pots():
    picks_df = pd.DataFrame({
        'Name': ['Charlie'],
        'Pot A': ['Argentina'],
        'Pot B': ['Mexico'],
        'Pot C': ['Canada'],
        'Pot D': ['South Africa']
    })
    
    results_df = pd.DataFrame([
        {
            'date_aest': pd.to_datetime('2026-06-11'),
            'home': 'Argentina', 'away': 'Spain', 'winner': None, 'is_draw': True, 'is_finished': True, 'stage': 'Matchday 1'
        },
        {
            'date_aest': pd.to_datetime('2026-06-11'),
            'home': 'Mexico', 'away': 'Italy', 'winner': None, 'is_draw': True, 'is_finished': True, 'stage': 'Matchday 1'
        },
        {
            'date_aest': pd.to_datetime('2026-06-11'),
            'home': 'Canada', 'away': 'Peru', 'winner': None, 'is_draw': True, 'is_finished': True, 'stage': 'Matchday 1'
        },
        {
            'date_aest': pd.to_datetime('2026-06-11'),
            'home': 'South Africa', 'away': 'Chile', 'winner': None, 'is_draw': True, 'is_finished': True, 'stage': 'Matchday 1'
        }
    ])
    
    leaderboard_df, _ = calculate_scores_and_timeline(picks_df, results_df)
    
    # Draw points: Pot A=1, Pot B=1, Pot C=1.5, Pot D=1.5 -> Total = 5.0
    charlie_points = leaderboard_df[leaderboard_df['Name'] == 'Charlie'].iloc[0]['Points']
    assert charlie_points == 5.0, f"Expected 5.0 points for draws across all pots, got {charlie_points}"
    print("test_draws_across_pots passed!")

def test_knockout_advancement():
    picks_df = pd.DataFrame({
        'Name': ['Dave'],
        'Pot B': ['Colombia']
    })
    
    # Dave's team reaches the semi-finals
    results_df = pd.DataFrame([
        {'date_aest': pd.to_datetime('2026-06-25'), 'home': 'Colombia', 'away': 'x', 'winner': 'Colombia', 'is_draw': False, 'is_finished': True, 'stage': 'Round of 32'},
        {'date_aest': pd.to_datetime('2026-06-28'), 'home': 'Colombia', 'away': 'y', 'winner': 'Colombia', 'is_draw': False, 'is_finished': True, 'stage': 'Round of 16'},
        {'date_aest': pd.to_datetime('2026-07-03'), 'home': 'Colombia', 'away': 'z', 'winner': 'Colombia', 'is_draw': False, 'is_finished': True, 'stage': 'Quarter-finals'},
        {'date_aest': pd.to_datetime('2026-07-08'), 'home': 'Colombia', 'away': 'w', 'winner': 'w', 'is_draw': False, 'is_finished': True, 'stage': 'Semi-finals'}
    ])
    
    leaderboard_df, _ = calculate_scores_and_timeline(picks_df, results_df)
    
    # Points for Pot B: R32(1) + R16(2.5) + QF(3.5) + SF(4.5) = 11.5
    dave_points = leaderboard_df[leaderboard_df['Name'] == 'Dave'].iloc[0]['Points']
    assert dave_points == 11.5, f"Expected 11.5 points for Semi-Final run, got {dave_points}"
    print("test_knockout_advancement passed!")

def test_winning_tournament():
    picks_df = pd.DataFrame({
        'Name': ['Eve'],
        'Pot C': ['Wales']
    })
    
    results_df = pd.DataFrame([
        {'date_aest': pd.to_datetime('2026-07-15'), 'home': 'Wales', 'away': 'Brazil', 'winner': 'Wales', 'is_draw': False, 'is_finished': True, 'stage': 'Final'}
    ])
    
    leaderboard_df, _ = calculate_scores_and_timeline(picks_df, results_df)
    
    # Points for Pot C: Final (6) + Winner (6) = 12
    eve_points = leaderboard_df[leaderboard_df['Name'] == 'Eve'].iloc[0]['Points']
    assert eve_points == 12.0, f"Expected 12 points for winning tournament in Pot C, got {eve_points}"
    print("test_winning_tournament passed!")

if __name__ == "__main__":
    print("Running Scoring Engine Tests...")
    test_group_stage_win_pot_a_and_d()
    test_draws_across_pots()
    test_knockout_advancement()
    test_winning_tournament()
    print("✅ All tests passed!")
