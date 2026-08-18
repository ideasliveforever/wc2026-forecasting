# World Cup 2026 Probabilistic Forecasting Engine

**Result:** Top 3% of 4,000+ participants — Jump Trading Probability Cup (2026 FIFA World Cup)

## Overview

A Python-based forecasting pipeline built as a decision-support system for probabilistic predictions during the 2026 FIFA World Cup. The engine generated base-rate estimates, which were then adjusted through market-implied signals, crowd-bias correction, and conviction weighting to produce final forecasts submitted for scoring.

## System Design

**Model outputs:**
- Poisson-modeled base rates for goals, corners, cards, shots on target, and offsides
- ELO-derived win probabilities
- Kalshi prediction market integration (manual input) as a market-implied prior
- Referee tendency and match-context signals

**Manual layer:**
- Crowd-positioning estimates (anticipated consensus placement)
- Conviction-weighted adjustments using team-specific World Cup data
- Edge identification — flagging which markets to trade vs. skip
- Risk management via a skip framework for position sizing and drawdown control

## Final Results
![Final Leaderboard Rank](final-leaderboard-rank.png)
![Calibration Curve](calibration-curve.png)
![Category Performance](category-performance.png)
![Competition Highlights](competition-highlights.png)
![Match Highs and Lows](match-highs-and-lows.png)

## Key Insights

Relative Brier scoring rewards distance from the crowd, not just distance from the outcome — accuracy alone isn't sufficient if the field is also accurate. The largest performance gains came from three sources:

1. **Systematic mispricing identification** — targeting player props and rare-event markets where crowd estimates were structurally biased
2. **Selective participation** — a skip framework that cut drawdowns by ~60%, at the cost of some upside on high-variance questions
3. **Market data as primary signal** — weighting Kalshi-implied probabilities above raw model output when the two diverged

## Tech Stack

- **Python** — NumPy, SciPy, Requests
- **Poisson distribution modeling** — goal/event rate estimation
- **ELO rating system** — win probability estimation
- **Kalshi API** — real-time prediction market data
- **SofaScore API** — team and match statistics
- **Google Gemini API** — LLM fallback for complex/compound questions
