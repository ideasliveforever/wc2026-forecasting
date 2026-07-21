"""
PLAYER DATA — fill in before each match.

Only needed if there are player prop questions.
Look up on FBref: player → shooting → SoT ÷ 90s

If no data available, leave empty — bot uses position base rates.
"""

# Player name (lowercase) → SOT per 90
PLAYER_SOT = {
    # "Sadio Mané": ,
    # "ben waine": 0.9,
}

# Player name → expected minutes (starter=90, sub=30-45, unknown=70)
PLAYER_MINUTES = {
    # "mehdi taremi": 90,
    # "ben waine": 90,
}

# Player name → data quality
# "strong" = top leagues / strong opponents (no discount)
# "mixed" = mix of strong and weak (20% discount)
# "weak" = mostly qualifiers vs minnows (40% discount)
PLAYER_DATA_QUALITY = {
    # "mehdi taremi": "strong",
    # "ben waine": "mixed",
}

# Player name → position (for base rate fallback)
# "striker", "winger", "midfielder", "defender"
PLAYER_POSITION = {
    # "mehdi taremi": "striker",
    # "ben waine": "striker",
}