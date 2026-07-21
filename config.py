import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # API Keys
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    SPORTSPREDICT_API_KEY = os.getenv("SPORTSPREDICT_API_KEY", "")
    KALSHI_API_KEY = os.getenv("KALSHI_API_KEY", "")

    # Model
    GEMINI_MODEL = "gemini-2.5-flash"

    # SportsPredict
    SP_BASE_URL = "https://api.sportspredict.com/api/v1"

    # Half splits
    HALF_1_FACTOR = 0.45
    HALF_2_FACTOR = 0.55

    # Confidence ceilings
    MAX_CONFIDENCE_GOALS = 0.78
    MAX_CONFIDENCE_CORNERS = 0.75
    MAX_CONFIDENCE_SOT = 0.55
    MAX_CONFIDENCE_WINNER = 0.80
    MAX_CONFIDENCE_CARDS = 0.72
    MAX_CONFIDENCE_FOULS = 0.75
    MAX_CONFIDENCE_DEFAULT = 0.80

    # Market rules
    MAX_MARKET_ADJUSTMENT = 0.05
    MAX_LLM_ADJUSTMENT = 0.08

    # Sharp market threshold
    SHARP_VOLUME_THRESHOLD = 5_000_000
    MEDIUM_VOLUME_THRESHOLD = 500_000


config = Config()