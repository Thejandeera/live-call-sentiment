from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Live Sentiment Score Service (EMA with Non-Linear Dampening)")

EMOTION_WEIGHTS = {
    "anger": 100.0,
    "grief": 95.0,
    "fear": 90.0,
    "disgust": 85.0,
    "annoyance": 80.0,
    "disappointment": 75.0,
    "disapproval": 70.0,
    "sadness": 65.0,
    "remorse": 60.0,
    "embarrassment": 55.0,
    "nervousness": 50.0,
    "confusion": 40.0,
    "surprise": 35.0,
    "realization": 30.0,
    "curiosity": 25.0,
    "desire": 20.0,
    "neutral": 15.0,
    "approval": 10.0,
    "caring": 10.0,
    "pride": 10.0,
    "relief": 8.0,
    "amusement": 8.0,
    "optimism": 5.0,
    "gratitude": 5.0,
    "joy": 5.0,
    "admiration": 5.0,
    "love": 5.0,
    "excitement": 5.0,
}

ALPHA = 0.15  # Smoothing factor for Exponential Moving Average
RESISTANCE_THRESHOLD = 40.0  # Threshold at which dampening activates
ESCALATION_THRESHOLD = 65.0  # Threshold for pulling manager / triggering alert


class ScoreRequest(BaseModel):
    emotion: str
    confidence: Optional[float] = 0.0
    previous_score: Optional[float] = Field(default=0.0, description="Previous live score (S_current). Defaults to 0.0 if not provided.")


class ScoreResponse(BaseModel):
    emotion: str
    confidence: float
    emotion_weight: float
    previous_score: float
    dampening_factor: float
    dampened_raw_score: float
    score: float
    escalation_triggered: bool


@app.post("/calculate-score", response_model=ScoreResponse)
async def calculate_score(payload: ScoreRequest):
    emotion_clean = payload.emotion.strip().lower() if payload.emotion else "neutral"
    confidence = payload.confidence if payload.confidence is not None else 0.0
    s_current = payload.previous_score if payload.previous_score is not None else 0.0

    # Ensure s_current stays within valid bounds [0.0, 100.0]
    s_current = max(0.0, min(100.0, float(s_current)))

    # Get predefined negativity weight from inverted pyramid
    raw_weight = EMOTION_WEIGHTS.get(emotion_clean, 0.0)

    # Calculate asymptotic dampening factor D
    if s_current > RESISTANCE_THRESHOLD:
        dampening_factor = 1.0 - (s_current / 100.0)
    else:
        dampening_factor = 1.0

    # Apply dampening multiplier to incoming emotion raw weight
    dampened_raw_score = raw_weight * dampening_factor

    # Exponential Moving Average (EMA) update calculation
    # S_new = (alpha * S_effective_raw) + ((1 - alpha) * S_current)
    s_new = (ALPHA * dampened_raw_score) + ((1.0 - ALPHA) * s_current)
    s_new = max(0.0, min(100.0, round(s_new, 2)))

    # Check if escalation threshold (65) breached
    escalation_triggered = s_new >= ESCALATION_THRESHOLD

    return ScoreResponse(
        emotion=payload.emotion,
        confidence=confidence,
        emotion_weight=raw_weight,
        previous_score=round(s_current, 2),
        dampening_factor=round(dampening_factor, 4),
        dampened_raw_score=round(dampened_raw_score, 2),
        score=s_new,
        escalation_triggered=escalation_triggered,
    )
