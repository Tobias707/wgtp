from pydantic import BaseModel
from typing import List
from datetime import datetime


class QuizRequest(BaseModel):
    platforms: List[str]
    players: str
    online_preference: str
    budget: str
    genres: List[str]
    loved_games: List[str]
    disliked_games: List[str]
    session_length: str
    difficulty: str
    story_importance: str
    popularity: int


class GameResult(BaseModel):
    appid: int
    name: str
    steam_url: str
    description: str
    price_eur: float
    review_score: int
    is_free: bool
    match_score: float
    is_hidden_gem: bool


class RecommendResponse(BaseModel):
    timestamp: datetime
    results: List[GameResult]
