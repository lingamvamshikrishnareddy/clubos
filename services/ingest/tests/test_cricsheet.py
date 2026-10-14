import json

from clubos_ingest.cricsheet import assign_role, load

REGISTRY = {n: f"id-{n[:3].lower()}{i}" for i, n in enumerate(
    ["Opener One", "Opener Two", "Number Three", "Seamer A", "Spinner B", "Bat X", "Bat Y", "Bowl P", "Bowl Q", "Keeper K"])}


def delivery(batter, bowler, runs=0, extras=None, wicket=None, non_striker="Opener Two"):
    d = {"batter": batter, "bowler": bowler, "non_striker": non_striker,
         "runs": {"batter": runs, "extras": sum((extras or {}).values()), "total": runs + sum((extras or {}).values())}}
    if extras:
        d["extras"] = extras
    if wicket:
        d["wickets"] = [wicket]
    return d


MATCH = {
    "info": {
        "dates": ["2025-03-22"], "match_type": "T20", "season": "2025", "teams": ["Chennai Super Kings", "Mumbai Indians"],
        "event": {"name": "Indian Premier League", "match_number": 1},
        "players": {"Chennai Super Kings": ["Opener One", "Opener Two", "Number Three", "Bowl P", "Bowl Q"],
                    "Mumbai Indians": ["Bat X", "Bat Y", "Seamer A", "Spinner B", "Keeper K"]},
        "registry": {"people": REGISTRY},
    },
    "innings": [
        {"team": "Chennai Super Kings", "overs": [
            {"over": 0, "deliveries": [
                delivery("Opener One", "Seamer A", 4),
                delivery("Opener One", "Seamer A", 0, extras={"wides": 1}),
                delivery("Opener One", "Seamer A", 6),
                delivery("Opener One", "Seamer A", 0, wicket={"player_out": "Opener One", "kind": "caught",
                                                               "fielders": [{"name": "Keeper K"}]}),
                delivery("Number Three", "Seamer A", 1),
                delivery("Opener Two", "Seamer A", 0, extras={"noballs": 1}, non_striker="Number Three"),
                delivery("Opener Two", "Seamer A", 0, wicket={"player_out": "Number Three", "kind": "run out",
                                                               "fielders": [{"name": "Bat X"}]}, non_striker="Number Three"),
            ]},
        ]},
        {"team": "Mumbai Indians", "overs": [
            {"over": 0, "deliveries": [delivery("Bat X", "Bowl P", 2, non_striker="Bat Y"),
                                       delivery("Bat X", "Bowl P", 1, non_striker="Bat Y")]},
        ]},
        {"team": "Mumbai Indians", "super_over": True, "overs": [
            {"over": 0, "deliveries": [delivery("Bat X", "Bowl Q", 6, non_striker="Bat Y")]}]},
    ],
}


def test_assign_role_from_usage():
    assert assign_role([1, 2, 1], 90, 0, 3) == "opening_batter"
    assert assign_role([5, 6], 40, 0, 2) == "middle_order_batter"
    assert assign_role([9, 10], 4, 72, 3) == "bowler"
    assert assign_role([6, 7], 30, 48, 2) == "all_rounder"
    assert assign_role([], 0, 6, 1) == "bowler"  # bowled briefly, never batted
    assert assign_role([], 0, 0, 0) is None


def test_loads_ball_by_ball_into_the_ipl(empty_db, tmp_path):
    (tmp_path / "1001.json").write_text(json.dumps(MATCH))
    conn = empty_db
    load(conn, tmp_path)
    load(conn, tmp_path)  # idempotent
    one = lambda sql, *p: conn.execute(sql, p).fetchone()[0]  # noqa: E731
    home, away, home_team = conn.execute(
        "select m.home_score, m.away_score, t.short_name from matches m join teams t on t.id = m.home_team_id").fetchone()
    assert (home, away, home_team) == (13, 3, "CSK")  # 4+1wd+6+1+1nb; super over excluded
    assert one("select count(*) from match_events") == 9

    def stat(name, key):
        return conn.execute(
            "select v.value::float8 from player_season_metric_values v join player_season_stats s on s.id = v.season_stats_id"
            " join players p on p.id = s.player_id where p.full_name = %s and v.metric_key = %s", (name, key)).fetchone()

    assert stat("Opener One", "runs") == (10,)
    assert stat("Opener One", "batting_strike_rate") == (333.33,)  # 3 balls faced: the wide does not count
    assert stat("Seamer A", "wickets") == (1,)  # the run-out is not the bowler's
    assert stat("Seamer A", "economy_rate") == (15.6,)  # 13 conceded (incl. wide and no-ball) from 5 legal balls
    assert stat("Keeper K", "catches") == (1,)
    assert stat("Bat X", "batting_average") is None  # not out: undefined, not zero
    assert one("select balls from v_cricket_matchups m join players p on p.id = m.batter_id where p.full_name = 'Opener One'") == 3
