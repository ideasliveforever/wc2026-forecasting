import numpy as np
from scipy.stats import poisson
from config import config


def poisson_over(mean, threshold):
    """P(X > threshold). For 'over 2.5' use threshold=2.5, we calc P(X >= 3)."""
    return 1 - poisson.cdf(int(threshold), mean)


def poisson_under(mean, threshold):
    """P(X <= threshold). For 'under 2.5' use threshold=2.5, we calc P(X <= 2)."""
    return poisson.cdf(int(threshold), mean)


def poisson_exact(mean, value):
    """P(X = value)."""
    return float(poisson.pmf(value, mean))


def btts_probability(lambda_a, lambda_b):
    """P(both teams score at least 1)."""
    p_a_scores = 1 - np.exp(-lambda_a)
    p_b_scores = 1 - np.exp(-lambda_b)
    return float(p_a_scores * p_b_scores)


def clean_sheet_probability(expected_opponent_goals):
    """P(opponent scores 0) = P(X=0) in Poisson."""
    return float(np.exp(-expected_opponent_goals))


def match_total_goals_over(lambda_a, lambda_b, threshold=2.5):
    """P(total goals > threshold)."""
    total_lambda = lambda_a + lambda_b
    return float(poisson_over(total_lambda, threshold))


def half_adjustment(full_time_prob, half):
    """Adjust full-time probability for half-specific questions."""
    if half == 1:
        return full_time_prob * config.HALF_1_FACTOR
    elif half == 2:
        return full_time_prob * config.HALF_2_FACTOR
    return full_time_prob


def or_probability(p_a, p_b):
    """P(A or B) = P(A) + P(B) - P(A and B). Assumes independence."""
    return p_a + p_b - (p_a * p_b)


def and_probability(p_a, p_b):
    """P(A and B). Always less than min(P(A), P(B))."""
    return p_a * p_b


def apply_confidence_ceiling(probability, question_type):
    """Cap probability at category ceiling. Never too confident."""
    ceilings = {
        "goals": config.MAX_CONFIDENCE_GOALS,
        "corners": config.MAX_CONFIDENCE_CORNERS,
        "sot": config.MAX_CONFIDENCE_SOT,
        "winner": config.MAX_CONFIDENCE_WINNER,
        "cards": config.MAX_CONFIDENCE_CARDS,
        "fouls": config.MAX_CONFIDENCE_FOULS,
        "btts": config.MAX_CONFIDENCE_GOALS,
        "clean_sheet": config.MAX_CONFIDENCE_CARDS,
        "offsides": config.MAX_CONFIDENCE_CORNERS,
        "penalty": config.MAX_CONFIDENCE_CORNERS,
    }
    ceiling = ceilings.get(question_type, config.MAX_CONFIDENCE_DEFAULT)
    floor = 1 - ceiling
    return max(floor, min(ceiling, probability))


def market_anchor_adjust(market_prob, model_prob):
    """Anchor to market, allow limited deviation."""
    max_adj = config.MAX_MARKET_ADJUSTMENT
    diff = model_prob - market_prob
    capped_diff = max(-max_adj, min(max_adj, diff))
    return market_prob + capped_diff


def devig(odds_list):
    """De-vig a list of decimal odds to true probabilities."""
    raw_probs = [1 / o for o in odds_list if o > 0]
    total = sum(raw_probs)
    if total == 0:
        return [1 / len(odds_list)] * len(odds_list)
    return [p / total for p in raw_probs]