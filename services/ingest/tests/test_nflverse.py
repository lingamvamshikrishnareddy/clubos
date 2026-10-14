from collections import defaultdict

from clubos_ingest.nflverse import load_season


def play(**values):
    row = defaultdict(str, {"season_type": "REG", "game_id": "2024_01_KC_BUF", "home_team": "BUF", "away_team": "KC",
                            "game_date": "2024-09-08", "week": "1", "home_score": "24", "away_score": "21", "qtr": "1",
                            "game_seconds_remaining": "3500", "posteam": "KC", "defteam": "BUF", "down": "1",
                            "ydstogo": "10", "yardline_100": "75", "shotgun": "1", "success": "1", "epa": "0.5",
                            "sack": "0", "pass_attempt": "0", "complete_pass": "0", "interception": "0",
                            "fumble_lost": "0", "touchdown": "0", "pass_touchdown": "0", "punt_blocked": "0"})
    row.update(values)
    return row


PLAYS = [
    play(play_id="1", play_type="pass", pass_attempt="1", complete_pass="1", passer_player_id="QB1", receiver_player_id="WR1",
         yards_gained="15", passing_yards="15", receiving_yards="15", yards_after_catch="5", solo_tackle_1_player_id="CB1",
         solo_tackle_1_team="BUF"),
    play(play_id="2", play_type="run", rusher_player_id="RB1", yards_gained="7", rushing_yards="7", epa="0.2"),
    play(play_id="3", play_type="pass", sack="1", passer_player_id="QB1", sack_player_id="DE1", yards_gained="-8", epa="-1.5"),
    # Interception returned: the passer makes the tackle and must be credited to his own team.
    play(play_id="4", play_type="pass", pass_attempt="1", interception="1", passer_player_id="QB1",
         receiver_player_id="WR1", yards_gained="0", solo_tackle_1_player_id="QB1", solo_tackle_1_team="KC",
         pass_defense_1_player_id="CB1"),
    play(play_id="5", play_type="qb_kneel", rusher_player_id="QB1", yards_gained="-1", rushing_yards="-1"),
    play(play_id="6", play_type="field_goal", posteam="BUF", defteam="KC", kicker_player_id="K1", field_goal_result="made",
         kick_distance="40"),
    play(play_id="7", play_type="run", rusher_player_id="RB1", two_point_attempt="1", yards_gained="2"),
    play(play_id="8", play_type="run", season_type="POST", game_id="2025_19_KC_BUF", rusher_player_id="RB1",
         yards_gained="50", rushing_yards="50"),
]
SNAPS = [
    {"game_id": "2024_01_KC_BUF", "game_type": "REG", "pfr_player_id": pfr, "position": pos, "team": team,
     "offense_snaps": off, "defense_snaps": dfn, "st_snaps": "0"}
    for pfr, pos, team, off, dfn in [("QbPf", "QB", "KC", "60", "0"), ("WrPf", "WR", "KC", "55", "0"), ("RbPf", "RB", "KC", "40", "0"),
                                     ("CbPf", "CB", "BUF", "0", "58"), ("DePf", "DE", "BUF", "0", "50"), ("KPf", "K", "BUF", "0", "0")]
] + [{"game_id": "2025_19_KC_BUF", "game_type": "POST", "pfr_player_id": "RbPf", "position": "RB", "team": "KC",
      "offense_snaps": "45", "defense_snaps": "0", "st_snaps": "0"}]
PEOPLE = [
    {"gsis_id": gsis, "pfr_id": pfr, "display_name": name, "birth_date": "1995-05-05", "position": pos, "position_group": "",
     "height": "74", "weight": "220", "college_name": ""}
    for gsis, pfr, name, pos in [("QB1", "QbPf", "Test Quarterback", "QB"), ("WR1", "WrPf", "Test Receiver", "WR"),
                                 ("RB1", "RbPf", "Test Back", "RB"), ("CB1", "CbPf", "Test Corner", "CB"),
                                 ("DE1", "DePf", "Test End", "DE"), ("K1", "KPf", "Test Kicker", "K")]
]


def fetch(path):
    return {"pbp": PLAYS, "snap_counts": SNAPS, "players": PEOPLE}[path.split("/")[0]]


def metrics(conn, name):
    return dict(conn.execute(
        "select v.metric_key, v.value from player_season_metric_values v join player_season_stats s on s.id = v.season_stats_id"
        " join players p on p.id = s.player_id where p.full_name = %s", (name,)).fetchall())


def test_loads_a_season_with_correct_credit(empty_db):
    conn = empty_db
    load_season(conn, 2024, fetch=fetch)
    load_season(conn, 2024, fetch=fetch)  # idempotent
    one = lambda sql, *p: conn.execute(sql, p).fetchone()[0]  # noqa: E731
    assert one("select count(*) from matches") == 2
    assert one("select count(*) from matches where stage = 'playoff'") == 1
    qb = metrics(conn, "Test Quarterback")
    assert qb["pass_attempts"] == 2 and qb["completion_pct"] == 0.5 and qb["passing_yards"] == 15
    assert qb["interceptions_thrown"] == 1 and qb["rushing_yards"] == -1  # kneel counted, as in official stats
    assert "tackles" not in qb  # offensive player: defensive metrics not stored
    rb = metrics(conn, "Test Back")
    assert rb["rushing_yards"] == 7  # playoffs and two-point attempts excluded
    assert metrics(conn, "Test Corner") == {"tackles": 1, "sacks": 0, "passes_defended": 1}
    assert metrics(conn, "Test End")["sacks"] == 1
    assert metrics(conn, "Test Kicker") == {"field_goal_pct": 1}
    # Regular-season snaps only, as playing time.
    assert one("select s.exposure from player_season_stats s join players p on p.id = s.player_id where p.full_name = 'Test Back'") == 40
    # Teams are the reference NFL teams; standings ranked by win percentage.
    assert one("select team from v_league_table where position = 1") == "Buffalo Bills"
    assert one("select count(*) from match_events where event_type = 'sack'") == 1
