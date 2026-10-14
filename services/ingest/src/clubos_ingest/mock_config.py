"""League and club settings for fictional demo data, one entry per sport.

Every name here is invented. Exposure values are per game: (starter, backup), in the
unit the sport module defines for the role.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Season:
    label: str
    starts_on: str
    ends_on: str


@dataclass(frozen=True)
class LeagueConfig:
    slug: str  # packages/sports/<slug>
    league: str
    country: str
    currency: str
    teams: tuple[str, ...]  # the first team belongs to the demo club
    club: str
    seasons: tuple[Season, Season]
    games_per_team: int
    # role -> (squad size, starters)
    roster: dict[str, tuple[int, int]]
    exposure_per_game: dict[str, tuple[float, float]]  # "default" plus role overrides
    score: tuple[str, float, float]  # ("poisson", mean, _) or ("normal", mean, sd)
    salary_range: tuple[float, float]  # annual, in currency
    fee_range: tuple[float, float] | None  # transfer fees, when the sport has them
    ticket_price: float
    stadium_capacity: int
    facility_kinds: tuple[str, ...]
    market_kinds: tuple[str, ...]
    competition_attributes: dict = field(default_factory=dict)


LEAGUES: dict[str, LeagueConfig] = {
    "soccer": LeagueConfig(
        slug="soccer", league="Northern Premier Division", country="England", currency="GBP",
        club="Riverside Football Club",
        teams=("Riverside FC", "Hillcrest United", "Ashford Rovers", "Kingsbridge Athletic", "Millbrook Town",
               "Oakham City", "Stonegate Albion", "Westmoor Wanderers", "Fairhaven FC", "Brackenford United"),
        seasons=(Season("2024/25", "2024-08-10", "2025-05-24"), Season("2025/26", "2025-08-09", "2026-05-23")),
        games_per_team=18,
        roster={"goalkeeper": (3, 1), "centre_back": (4, 2), "full_back": (4, 2), "defensive_midfielder": (3, 1),
                "central_midfielder": (3, 2), "attacking_midfielder": (2, 1), "winger": (4, 2), "striker": (3, 1)},
        exposure_per_game={"default": (86, 24)},
        score=("poisson", 1.4, 0), salary_range=(45_000, 3_500_000), fee_range=(50_000, 30_000_000),
        ticket_price=32, stadium_capacity=18_000,
        facility_kinds=("stadium", "pitch", "pitch", "gym", "medical_room", "meeting_room"),
        market_kinds=("transfer", "transfer", "transfer", "loan"),
    ),
    "american_football": LeagueConfig(
        slug="american-football", league="Continental Football League", country="United States", currency="USD",
        club="Harbour City Mariners Football Club",
        teams=("Harbour City Mariners", "Granite Peak Rams", "Prairie Storm", "Delta Gators", "Iron Valley Forge",
               "Canyon Coyotes", "Bayview Sharks", "Timberline Lumberjacks", "Desert Suns", "Lakeshore Admirals"),
        seasons=(Season("2024", "2024-09-05", "2025-01-05"), Season("2025", "2025-09-04", "2026-01-04")),
        games_per_team=9,
        roster={"quarterback": (3, 1), "running_back": (4, 1), "wide_receiver": (6, 3), "tight_end": (3, 1),
                "offensive_line": (9, 5), "defensive_line": (6, 2), "edge_rusher": (4, 2), "linebacker": (5, 2),
                "cornerback": (5, 2), "safety": (4, 2), "kicker": (1, 1), "punter": (1, 1)},
        exposure_per_game={"default": (60, 14), "kicker": (3.5, 0), "punter": (4.5, 0)},
        score=("normal", 22, 8), salary_range=(750_000, 35_000_000), fee_range=None,
        ticket_price=95, stadium_capacity=62_000,
        facility_kinds=("stadium", "field", "field", "gym", "medical_room", "meeting_room"),
        market_kinds=("draft", "free_agent_signing", "trade", "contract_extension"),
    ),
    "baseball": LeagueConfig(
        slug="baseball", league="Heartland Baseball Association", country="United States", currency="USD",
        club="Lakeside Comets Baseball Club",
        teams=("Lakeside Comets", "River City Barons", "Pinecrest Owls", "Copper Hills Miners", "Bay Harbor Gulls",
               "Sunvale Sluggers", "Redwood Rangers", "Ironbridge Bulls", "Clearwater Pelicans", "Highland Stags"),
        seasons=(Season("2025", "2025-04-01", "2025-09-28"), Season("2026", "2026-04-02", "2026-09-27")),
        games_per_team=90,
        roster={"starting_pitcher": (5, 5), "relief_pitcher": (8, 8), "catcher": (2, 1), "first_base": (2, 1),
                "second_base": (2, 1), "third_base": (2, 1), "shortstop": (2, 1), "left_field": (2, 1),
                "centre_field": (2, 1), "right_field": (2, 1), "designated_hitter": (1, 1)},
        exposure_per_game={"default": (4.2, 1.0), "starting_pitcher": (5.0, 5.0), "relief_pitcher": (1.9, 1.9)},
        score=("poisson", 4.5, 0), salary_range=(720_000, 30_000_000), fee_range=None,
        ticket_price=38, stadium_capacity=35_000,
        facility_kinds=("stadium", "field", "nets", "gym", "medical_room", "meeting_room"),
        market_kinds=("draft", "free_agent_signing", "trade", "contract_extension"),
    ),
    "basketball": LeagueConfig(
        slug="basketball", league="Metro Basketball League", country="United States", currency="USD",
        club="Summit Falcons Basketball Club",
        teams=("Summit Falcons", "Bayside Breakers", "Capital Monarchs", "Riverbend Rapids", "Northgate Knights",
               "Sunset Blaze", "Ironwood Titans", "Lakeview Lynx", "Crescent City Cyclones", "Pine Valley Pioneers"),
        seasons=(Season("2024-25", "2024-10-22", "2025-04-13"), Season("2025-26", "2025-10-21", "2026-04-12")),
        games_per_team=36,
        roster={"point_guard": (3, 1), "shooting_guard": (3, 1), "small_forward": (3, 1),
                "power_forward": (3, 1), "centre": (3, 1)},
        exposure_per_game={"default": (32, 13)},
        score=("normal", 108, 11), salary_range=(1_100_000, 45_000_000), fee_range=None,
        ticket_price=85, stadium_capacity=18_500,
        facility_kinds=("stadium", "court", "court", "gym", "medical_room", "meeting_room"),
        market_kinds=("draft", "free_agent_signing", "trade", "contract_extension"),
    ),
    "ice_hockey": LeagueConfig(
        slug="ice-hockey", league="Northern Ice League", country="Canada", currency="CAD",
        club="Northfield Blizzard Hockey Club",
        teams=("Northfield Blizzard", "Glacier Bay Wolves", "Frostburg Huskies", "Pine Ridge Lumberjacks",
               "Iron Lake Miners", "Aurora Bears", "Summit Peaks", "Cold Creek Moose", "Granite City Bulldogs",
               "Harbourview Pilots"),
        seasons=(Season("2024-25", "2024-10-04", "2025-04-12"), Season("2025-26", "2025-10-03", "2026-04-11")),
        games_per_team=36,
        roster={"centre": (5, 4), "winger": (9, 8), "defenceman": (8, 6), "goaltender": (3, 1)},
        exposure_per_game={"default": (15.5, 9), "defenceman": (20.5, 14), "goaltender": (23, 7)},
        score=("poisson", 3.0, 0), salary_range=(775_000, 12_000_000), fee_range=None,
        ticket_price=70, stadium_capacity=17_000,
        facility_kinds=("stadium", "rink", "rink", "gym", "medical_room", "meeting_room"),
        market_kinds=("draft", "free_agent_signing", "trade", "contract_extension"),
    ),
    "cricket": LeagueConfig(
        slug="cricket", league="Coastal Premier T20 League", country="India", currency="INR",
        club="Coastal Kings Cricket Club",
        teams=("Coastal Kings", "Deccan Tuskers", "Malabar Monsoons", "Konkan Chargers", "Vindhya Warriors",
               "Godavari Riders", "Nilgiri Hawks", "Kaveri Strikers", "Sahyadri Lions", "Narmada Royals"),
        seasons=(Season("2025", "2025-03-20", "2025-05-25"), Season("2026", "2026-03-19", "2026-05-24")),
        games_per_team=18,
        roster={"opening_batter": (3, 2), "top_order_batter": (3, 1), "middle_order_batter": (3, 1),
                "finisher": (2, 1), "wicketkeeper_batter": (2, 1), "all_rounder": (3, 2),
                "fast_bowler": (5, 2), "spin_bowler": (3, 1)},
        exposure_per_game={"default": (16, 5), "opening_batter": (24, 6), "top_order_batter": (20, 6),
                           "finisher": (10, 4), "fast_bowler": (24, 6), "spin_bowler": (24, 6)},
        score=("normal", 168, 22), salary_range=(2_000_000, 270_000_000), fee_range=None,
        ticket_price=1_200, stadium_capacity=40_000,
        facility_kinds=("stadium", "field", "nets", "gym", "medical_room", "meeting_room"),
        market_kinds=("auction", "auction", "contract_extension"),
        competition_attributes={"format": "T20"},
    ),
}

FIRST_NAMES = (
    "Aarav", "Amara", "Bram", "Caio", "Dara", "Eitan", "Elio", "Farah", "Goran", "Hana", "Idris", "Ines",
    "Jalen", "Kai", "Kofi", "Leif", "Lior", "Mateo", "Mira", "Nikhil", "Noa", "Oskar", "Priya", "Quinn",
    "Rafael", "Ravi", "Saoirse", "Tariq", "Teo", "Uma", "Viktor", "Wren", "Xavi", "Yusuf", "Zane", "Ade",
    "Bastian", "Cyrus", "Dante", "Emeka", "Felix", "Hugo", "Ivo", "Jonah", "Kian", "Luka", "Milan", "Nico",
    "Omari", "Pavel", "Rohan", "Sami", "Tobias", "Arjun", "Ishaan", "Vihaan", "Kabir", "Dev", "Anaya", "Sia",
)
LAST_NAMES = (
    "Abara", "Bellweather", "Castellan", "Drummond", "Ekwueme", "Falkner", "Garrow", "Halvorsen", "Ibarra",
    "Jovanić", "Kestrel", "Lindqvist", "Marlowe", "Nakamura", "Okafor", "Pellegrini", "Quarry", "Rossiter",
    "Sandoval", "Thornbury", "Underhill", "Valdés", "Whitlock", "Yardley", "Zielinski", "Ashcombe", "Brennan",
    "Calloway", "Delacroix", "Esposito", "Fairbairn", "Grantham", "Holloway", "Iversen", "Kowalczyk",
    "Larkspur", "Montague", "Northcott", "Oyelaran", "Prescott", "Ramsden", "Stavros", "Tennant", "Varga",
    "Westbrook", "Achterberg", "Bhattacharya", "Deshpande", "Iyer", "Kulkarni", "Menon", "Raghavan", "Varma",
)
NATIONALITIES = (
    "England", "Scotland", "Ireland", "France", "Spain", "Portugal", "Brazil", "Argentina", "Nigeria", "Ghana",
    "Senegal", "Germany", "Netherlands", "Sweden", "Norway", "Japan", "South Korea", "United States", "Canada",
    "Mexico", "Australia", "New Zealand", "India", "Sri Lanka", "South Africa", "Jamaica", "Croatia", "Serbia",
)
