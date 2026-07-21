"""
Base rates by confederation and tier. 
Used when SofaScore has no data for a team (small nations, etc).
"""

CONFEDERATION_RATES = {
    "UEFA": {
        "goals_per_90": 1.45,
        "goals_conceded_per_90": 1.05,
        "corners_per_90": 5.2,
        "fouls_committed_per_90": 12.5,
        "yellow_cards_per_90": 1.8,
        "red_cards_per_90": 0.06,
        "shots_on_target_per_90": 4.5,
        "shots_total_per_90": 12.0,
        "offsides_per_90": 2.2,
        "possession_avg": 50.0,
    },
    "CONMEBOL": {
        "goals_per_90": 1.15,
        "goals_conceded_per_90": 1.15,
        "corners_per_90": 4.8,
        "fouls_committed_per_90": 14.5,
        "yellow_cards_per_90": 2.4,
        "red_cards_per_90": 0.10,
        "shots_on_target_per_90": 4.0,
        "shots_total_per_90": 11.0,
        "offsides_per_90": 2.0,
        "possession_avg": 50.0,
    },
    "CAF": {
        "goals_per_90": 1.05,
        "goals_conceded_per_90": 1.05,
        "corners_per_90": 4.5,
        "fouls_committed_per_90": 13.5,
        "yellow_cards_per_90": 2.2,
        "red_cards_per_90": 0.08,
        "shots_on_target_per_90": 3.8,
        "shots_total_per_90": 10.5,
        "offsides_per_90": 1.8,
        "possession_avg": 50.0,
    },
    "AFC": {
        "goals_per_90": 1.20,
        "goals_conceded_per_90": 1.10,
        "corners_per_90": 4.8,
        "fouls_committed_per_90": 13.0,
        "yellow_cards_per_90": 2.0,
        "red_cards_per_90": 0.07,
        "shots_on_target_per_90": 4.0,
        "shots_total_per_90": 11.5,
        "offsides_per_90": 1.9,
        "possession_avg": 50.0,
    },
    "CONCACAF": {
        "goals_per_90": 1.30,
        "goals_conceded_per_90": 1.20,
        "corners_per_90": 5.0,
        "fouls_committed_per_90": 13.5,
        "yellow_cards_per_90": 2.3,
        "red_cards_per_90": 0.09,
        "shots_on_target_per_90": 4.2,
        "shots_total_per_90": 11.5,
        "offsides_per_90": 2.0,
        "possession_avg": 50.0,
    },
    "OFC": {
        "goals_per_90": 1.50,
        "goals_conceded_per_90": 1.50,
        "corners_per_90": 4.5,
        "fouls_committed_per_90": 13.0,
        "yellow_cards_per_90": 2.0,
        "red_cards_per_90": 0.07,
        "shots_on_target_per_90": 4.0,
        "shots_total_per_90": 11.0,
        "offsides_per_90": 1.7,
        "possession_avg": 50.0,
    },
}

# Tier adjustments: (goals_mult, concede_mult, corners_mult, fouls_mult)
TIER_ADJUSTMENTS = {
    1: (1.35, 0.70, 1.15, 0.90),
    2: (1.15, 0.85, 1.08, 0.95),
    3: (1.00, 1.00, 1.00, 1.00),
    4: (0.85, 1.20, 0.92, 1.10),
    5: (0.70, 1.40, 0.85, 1.15),
}

TEAM_CONFEDERATIONS = {
    # UEFA
    "france": "UEFA", "germany": "UEFA", "spain": "UEFA", "england": "UEFA",
    "italy": "UEFA", "portugal": "UEFA", "netherlands": "UEFA", "belgium": "UEFA",
    "croatia": "UEFA", "switzerland": "UEFA", "denmark": "UEFA", "austria": "UEFA",
    "sweden": "UEFA", "norway": "UEFA", "poland": "UEFA", "serbia": "UEFA",
    "ukraine": "UEFA", "turkey": "UEFA", "czech republic": "UEFA", "czechia": "UEFA",
    "scotland": "UEFA", "wales": "UEFA", "hungary": "UEFA", "greece": "UEFA",
    "romania": "UEFA", "slovakia": "UEFA", "finland": "UEFA", "iceland": "UEFA",
    "ireland": "UEFA", "republic of ireland": "UEFA", "northern ireland": "UEFA",
    "bosnia": "UEFA", "bosnia and herzegovina": "UEFA", "albania": "UEFA",
    "north macedonia": "UEFA", "montenegro": "UEFA", "slovenia": "UEFA",
    "georgia": "UEFA", "armenia": "UEFA", "azerbaijan": "UEFA", "kosovo": "UEFA",
    "belarus": "UEFA", "luxembourg": "UEFA", "bulgaria": "UEFA",
    "israel": "UEFA", "estonia": "UEFA", "latvia": "UEFA", "lithuania": "UEFA",
    "cyprus": "UEFA", "faroe islands": "UEFA", "malta": "UEFA",
    "gibraltar": "UEFA", "liechtenstein": "UEFA", "andorra": "UEFA",
    "san marino": "UEFA", "moldova": "UEFA", "kazakhstan": "UEFA",
    # CONMEBOL
    "brazil": "CONMEBOL", "argentina": "CONMEBOL", "uruguay": "CONMEBOL",
    "colombia": "CONMEBOL", "chile": "CONMEBOL", "ecuador": "CONMEBOL",
    "peru": "CONMEBOL", "paraguay": "CONMEBOL", "venezuela": "CONMEBOL",
    "bolivia": "CONMEBOL",
    # CAF
    "morocco": "CAF", "senegal": "CAF", "nigeria": "CAF", "egypt": "CAF",
    "cameroon": "CAF", "ivory coast": "CAF", "cote d'ivoire": "CAF",
    "algeria": "CAF", "tunisia": "CAF", "ghana": "CAF", "mali": "CAF",
    "south africa": "CAF", "dr congo": "CAF", "congo dr": "CAF",
    "burkina faso": "CAF", "guinea": "CAF", "cape verde": "CAF",
    "gabon": "CAF", "benin": "CAF", "mozambique": "CAF", "zambia": "CAF",
    "zimbabwe": "CAF", "uganda": "CAF", "tanzania": "CAF", "kenya": "CAF",
    "madagascar": "CAF", "sudan": "CAF", "libya": "CAF", "equatorial guinea": "CAF",
    "namibia": "CAF", "togo": "CAF", "rwanda": "CAF", "angola": "CAF",
    "congo": "CAF", "central african republic": "CAF", "niger": "CAF",
    "sierra leone": "CAF", "mauritania": "CAF", "ethiopia": "CAF",
    "botswana": "CAF", "comoros": "CAF", "gambia": "CAF",
    "malawi": "CAF", "lesotho": "CAF", "eswatini": "CAF",
    "liberia": "CAF", "guinea-bissau": "CAF", "chad": "CAF",
    "burundi": "CAF", "south sudan": "CAF", "eritrea": "CAF",
    "djibouti": "CAF", "somalia": "CAF", "sao tome": "CAF",
    "seychelles": "CAF", "mauritius": "CAF",
    # AFC
    "japan": "AFC", "south korea": "AFC", "korea republic": "AFC",
    "australia": "AFC", "iran": "AFC", "saudi arabia": "AFC",
    "qatar": "AFC", "iraq": "AFC", "uae": "AFC", "united arab emirates": "AFC",
    "uzbekistan": "AFC", "china": "AFC", "china pr": "AFC",
    "oman": "AFC", "bahrain": "AFC", "jordan": "AFC", "syria": "AFC",
    "vietnam": "AFC", "thailand": "AFC", "india": "AFC",
    "indonesia": "AFC", "palestine": "AFC", "kyrgyzstan": "AFC",
    "tajikistan": "AFC", "kuwait": "AFC", "north korea": "AFC",
    "lebanon": "AFC", "malaysia": "AFC", "philippines": "AFC",
    "yemen": "AFC", "turkmenistan": "AFC", "myanmar": "AFC",
    "singapore": "AFC", "hong kong": "AFC", "chinese taipei": "AFC",
    # CONCACAF
    "mexico": "CONCACAF", "usa": "CONCACAF", "united states": "CONCACAF",
    "canada": "CONCACAF", "costa rica": "CONCACAF", "panama": "CONCACAF",
    "jamaica": "CONCACAF", "honduras": "CONCACAF", "el salvador": "CONCACAF",
    "haiti": "CONCACAF", "trinidad and tobago": "CONCACAF",
    "guatemala": "CONCACAF", "curacao": "CONCACAF", "nicaragua": "CONCACAF",
    "suriname": "CONCACAF", "dominican republic": "CONCACAF",
    "cuba": "CONCACAF", "bermuda": "CONCACAF", "guyana": "CONCACAF",
    "belize": "CONCACAF", "antigua and barbuda": "CONCACAF",
    "st kitts and nevis": "CONCACAF", "barbados": "CONCACAF",
    "grenada": "CONCACAF", "dominica": "CONCACAF",
    "st lucia": "CONCACAF", "st vincent": "CONCACAF",
    "puerto rico": "CONCACAF", "cayman islands": "CONCACAF",
    # OFC
    "new zealand": "OFC", "solomon islands": "OFC", "fiji": "OFC",
    "papua new guinea": "OFC", "tahiti": "OFC", "new caledonia": "OFC",
    "vanuatu": "OFC", "samoa": "OFC", "tonga": "OFC",
    "cook islands": "OFC", "american samoa": "OFC",
}

TEAM_TIERS = {
    # Tier 1 (top 10)
    "argentina": 1, "france": 1, "brazil": 1, "england": 1, "belgium": 1,
    "portugal": 1, "netherlands": 1, "spain": 1, "italy": 1, "croatia": 1,
    # Tier 2 (11-30)
    "germany": 2, "morocco": 2, "colombia": 2, "uruguay": 2, "japan": 2,
    "mexico": 2, "usa": 2, "united states": 2, "senegal": 2, "switzerland": 2,
    "iran": 2, "south korea": 2, "korea republic": 2, "denmark": 2,
    "austria": 2, "australia": 2, "ukraine": 2, "turkey": 2,
    "nigeria": 2, "egypt": 2, "serbia": 2,
    # Tier 3 (31-60)
    "peru": 3, "sweden": 3, "poland": 3, "czech republic": 3, "czechia": 3,
    "hungary": 3, "scotland": 3, "norway": 3, "cameroon": 3,
    "ecuador": 3, "ivory coast": 3, "cote d'ivoire": 3, "algeria": 3,
    "tunisia": 3, "chile": 3, "ghana": 3, "saudi arabia": 3, "qatar": 3,
    "canada": 3, "costa rica": 3, "wales": 3, "panama": 3,
    "greece": 3, "romania": 3, "paraguay": 3, "iraq": 3, "mali": 3,
    # Tier 4 (61-100)
    "jamaica": 4, "honduras": 4, "el salvador": 4, "venezuela": 4,
    "bolivia": 4, "dr congo": 4, "south africa": 4, "cape verde": 4,
    "uganda": 4, "zambia": 4, "gabon": 4, "benin": 4, "guinea": 4,
    "burkina faso": 4, "jordan": 4, "uzbekistan": 4, "bahrain": 4,
    "uae": 4, "oman": 4, "china": 4, "syria": 4,
    "indonesia": 4, "vietnam": 4, "thailand": 4,
}


# World Cup base rates for binary questions
WC_BASE_RATES = {
    "home_win": 0.42,
    "draw": 0.25,
    "away_win": 0.33,
    "over_2_5_goals": 0.48,
    "over_1_5_goals": 0.72,
    "over_3_5_goals": 0.28,
    "btts": 0.45,
    "clean_sheet_any": 0.40,
    "penalty_awarded": 0.22,
    "red_card": 0.09,
    "over_9_5_corners": 0.45,
    "over_4_5_cards": 0.42,
    "over_25_5_fouls": 0.48,
}


def get_confederation(team_name):
    """Get confederation for a team."""
    key = team_name.lower().strip()
    return TEAM_CONFEDERATIONS.get(key, "UEFA")


def get_tier(team_name):
    """Get ranking tier for a team. Default tier 4 if unknown."""
    key = team_name.lower().strip()
    return TEAM_TIERS.get(key, 4)


def get_base_rates(team_name):
    """Get base rates for a team based on confederation + tier."""
    conf = get_confederation(team_name)
    tier = get_tier(team_name)

    base = CONFEDERATION_RATES[conf].copy()
    goals_mult, concede_mult, corners_mult, fouls_mult = TIER_ADJUSTMENTS[tier]

    return {
        "team": team_name,
        "source": f"base_rate_{conf}_tier{tier}",
        "matches_sampled": 0,
        "goals_per_90": round(base["goals_per_90"] * goals_mult, 2),
        "goals_conceded_per_90": round(base["goals_conceded_per_90"] * concede_mult, 2),
        "corners_per_90": round(base["corners_per_90"] * corners_mult, 2),
        "fouls_committed_per_90": round(base["fouls_committed_per_90"] * fouls_mult, 2),
        "yellow_cards_per_90": round(base["yellow_cards_per_90"] * fouls_mult, 2),
        "red_cards_per_90": base["red_cards_per_90"],
        "shots_on_target_per_90": round(base["shots_on_target_per_90"] * goals_mult, 2),
        "shots_total_per_90": round(base["shots_total_per_90"] * goals_mult, 2),
        "offsides_per_90": base["offsides_per_90"],
        "possession_avg": base["possession_avg"],
    }