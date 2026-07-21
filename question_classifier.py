import re
from dataclasses import dataclass


@dataclass
class QuestionProfile:
    raw_question: str
    category: str
    is_half_specific: bool
    half: int
    is_over_under: bool
    threshold: float
    is_under: bool
    is_or_question: bool
    is_and_question: bool
    is_comparison: bool
    is_player_prop: bool
    player_name: str
    confidence_ceiling: float


def classify_question(question):
    q = question.lower().strip()

    category = _get_category(q)
    is_half, half_num = _check_half(q)
    is_ou, threshold = _check_over_under(q)
    is_under = "under" in q or "or fewer" in q or "or less" in q
    is_or = "score or assist" in q or "goal or assist" in q
    is_and = _check_and(q)
    is_comparison = "more" in q and "than" in q
    is_player, player_name = _check_player_prop(q, question)
    # CRITICAL: comparison questions are NEVER player props
    if is_comparison:
        is_player = False
        player_name = ""
        
    ceiling = _get_ceiling(category)

    return QuestionProfile(
        raw_question=question,
        category=category,
        is_half_specific=is_half,
        half=half_num,
        is_over_under=is_ou,
        threshold=threshold,
        is_under=is_under,
        is_or_question=is_or,
        is_and_question=is_and,
        is_comparison=is_comparison,
        is_player_prop=is_player,
        player_name=player_name,
        confidence_ceiling=ceiling,
    )


def _check_and(q):
    """
    Detect compound AND questions (two events must both happen).
    "both teams score AND 3+ goals" → True (compound)
    "both teams to score" alone → False (just BTTS)
    "score or assist" → False (OR question)
    """
    if "score or assist" in q or "goal or assist" in q:
        return False

    if " and " not in q:
        return False

    parts = q.split(" and ")
    if len(parts) < 2:
        return False

    # Check if the part after "and" is a separate condition
    after_and = parts[-1].strip()

    # If after "and" contains match-level words, it's compound
    compound_signals = ["will", "the match", "have", "or more", "total",
                       "fewer", "goals", "score in", "be shown", "cards",
                       "corner", "half"]
    if any(w in after_and for w in compound_signals):
        return True

    # "both teams score AND [long clause]" is compound
    if "both" in parts[0] and len(after_and) > 10:
        return True

    return False


def _get_category(q):
    if any(w in q for w in ["corner kick", "corners", "corner"]):
        return "corners"
    if any(w in q for w in ["card", "booking", "yellow", "red card", "cards shown"]):
        return "cards"
    if "foul" in q:
        return "fouls"
    if any(w in q for w in ["shot on target", "shots on target", "sot"]):
        return "sot"
    if "offside" in q:
        return "offsides"
    if "btts" in q or "both teams to score" in q or "both teams score" in q:
        return "btts"
    if "clean sheet" in q:
        return "clean_sheet"
    if "penalty" in q or "pen awarded" in q:
        return "penalty"
    if "score or assist" in q or "goal or assist" in q or ("score" in q and "assist" in q):
        return "score_or_assist"
    if "score a goal" in q or "to score" in q:
        if "both" not in q and "total" not in q and "or fewer" not in q:
            return "player_goal"
    if any(w in q for w in ["win", "winner", "winning", "be winning", "beat", "defeat"]):
        return "winner"
    if "draw" in q or "drawing" in q or "tied" in q:
        return "winner"
    if any(w in q for w in ["over", "under", "total goals", "or fewer", "or more"]):
        if "corner" not in q and "card" not in q and "foul" not in q:
            return "goals"
    if "goal" in q:
        return "goals"
    if "score" in q and "both" not in q and "assist" not in q:
        return "goals"
    return "other"


def _check_half(q):
    if any(p in q for p in ["first half", "1st half", "half time", "half-time",
                             "halftime", "at halftime", " ht ", "at ht"]):
        return True, 1
    if any(p in q for p in ["second half", "2nd half", "in the second half", " h2 "]):
        return True, 2
    return False, 0


def _check_over_under(q):
    over_match = re.search(r'over\s+(\d+\.?\d*)', q)
    under_match = re.search(r'under\s+(\d+\.?\d*)', q)
    or_more_match = re.search(r'(\d+)\s+or\s+more', q)
    or_fewer_match = re.search(r'(\d+)\s+or\s+(?:fewer|less)', q)
    at_least_match = re.search(r'at\s+least\s+(\d+)', q)
    more_than_match = re.search(r'more\s+than\s+(\d+)', q)
    fewer_than_match = re.search(r'fewer\s+than\s+(\d+)', q)

    if over_match:
        return True, float(over_match.group(1))
    if under_match:
        return True, float(under_match.group(1))
    if or_more_match:
        return True, float(or_more_match.group(1)) - 0.5
    if or_fewer_match:
        return True, float(or_fewer_match.group(1)) + 0.5
    if at_least_match:
        return True, float(at_least_match.group(1)) - 0.5
    if more_than_match:
        return True, float(more_than_match.group(1))
    if fewer_than_match:
        return True, float(fewer_than_match.group(1)) - 0.5
    return False, 0.0


def _check_player_prop(q, original):
    name_match = re.findall(r'[A-Z][a-zéèêëàáâãäåæçñ]+(?:\s+[A-Z][a-zéèêëàáâãäåæçñ]+)+', original)

    skip = ["New Zealand", "Costa Rica", "South Korea", "North Macedonia",
            "Saudi Arabia", "United States", "El Salvador", "Trinidad",
            "Ivory Coast", "South Africa", "Burkina Faso", "DR Congo",
            "Cape Verde", "Bosnia and Herzegovina",
            "Canada", "Qatar", "Ghana", "Panama", "Brazil", "Morocco",
            "Germany", "France", "England", "Spain", "Portugal",
            "Croatia", "Serbia", "Switzerland", "Austria", "Jordan",
            "Colombia", "Uruguay", "Ecuador", "Algeria", "Tunisia",
            "Senegal", "Nigeria", "Cameroon", "Egypt", "Japan",
            "Australia", "Mexico", "Hungary", "Poland", "Denmark",
            "Sweden", "Norway", "Belgium", "Netherlands", "Italy",
            "Argentina", "Chile", "Peru", "Paraguay", "Bolivia",
            "Venezuela", "Jamaica", "Honduras", "Haiti", "Scotland",
            "Ireland", "Wales", "Greece", "Romania", "Ukraine",
            "Indonesia", "India", "China", "Iran", "Iraq",
            "Uzbekistan", "Czechia", "Czech Republic", "Turkey"]

    # Common English words that start sentences — NOT player names
    not_names = ["will", "the", "at", "in", "be", "have", "has", "are",
                 "is", "or", "and", "for", "both", "more", "than",
                 "total", "match", "game", "half", "second", "first"]

    for name in name_match:
        if name in skip:
            continue
        if len(name) <= 4:
            continue
        # Check if any word in the "name" is a common English word
        words = name.lower().split()
        if any(w in not_names for w in words):
            continue
        return True, name.lower()

    return False, ""


def _get_ceiling(category):
    ceilings = {
        "goals": 0.78,
        "corners": 0.75,
        "sot": 0.55,
        "winner": 0.80,
        "cards": 0.72,
        "fouls": 0.75,
        "btts": 0.78,
        "clean_sheet": 0.75,
        "offsides": 0.75,
        "penalty": 0.75,
        "score_or_assist": 0.55,
        "player_goal": 0.55,
    }
    return ceilings.get(category, 0.80)