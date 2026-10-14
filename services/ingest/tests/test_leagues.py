from clubos_ingest.leagues import load_leagues, reference_leagues


def test_reference_file_is_consistent():
    leagues = reference_leagues()
    assert {"nfl", "nba", "ipl", "premier_league", "efl_championship", "efl_league_one", "efl_league_two"} <= set(leagues)

    def team_count(groups):
        return sum(len(g.get("teams", [])) + team_count(g.get("children", [])) for g in groups)

    for key, league in leagues.items():
        assert league["rules"]["season"], key
        groups = league["structure"]["groups"]
        if groups:
            assert team_count(groups) == league["structure"]["teams"], key
    for key, league in leagues.items():
        pr = league["rules"].get("promotionRelegation", {})
        for target in (pr.get("promotedTo"), pr.get("relegatedTo")):
            assert target is None or target in leagues or target == "National League", (key, target)


def test_load_is_idempotent_and_builds_structure(empty_db):
    conn = empty_db
    first = load_leagues(conn)
    second = load_leagues(conn)
    assert first == second
    one = lambda sql, *p: conn.execute(sql, p).fetchone()[0]  # noqa: E731
    assert one("select count(*) from competitions where reference_key is not null") == 7
    assert one("select count(*) from competition_groups g join competitions c on c.id = g.competition_id"
               " where c.reference_key = 'nfl' and g.kind = 'division'") == 8
    assert one("select count(distinct gt.team_id) from competition_group_teams gt join competition_groups g on g.id = gt.group_id"
               " join competitions c on c.id = g.competition_id where c.reference_key = 'nba'") == 30
    assert one("select (rules -> 'salaryCap' ->> 'amount')::bigint from competitions where reference_key = 'nfl'") == 279200000
    # StatsBomb's Premier League loads into the same competition.
    assert one("select entity_id from source_entity_ids where source_id = 'statsbomb_open_data' and entity_type = 'competition'"
               " and external_id = '2'") == first["premier_league"]
