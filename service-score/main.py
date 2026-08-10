from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Live Sentiment Score Service (EMA with Non-Linear Dampening)")

EMOTION_WEIGHTS = {
    "gratitude": 100.0,
    "relief": 95.0,
    "approval": 85.0,
    "optimism": 80.0,
    "caring": 75.0,
    "joy": 70.0,
    "admiration": 65.0,
    "excitement": 55.0,
    "surprise": 45.0,
    "amusement": 35.0,
    "curiosity": 25.0,
    "pride": 15.0,
    "love": 10.0,
    "desire": 5.0,
    "anger": -100.0,
    "disgust": -95.0,
    "grief": -90.0,
    "sadness": -85.0,
    "disappointment": -80.0,
    "disapproval": -75.0,
    "annoyance": -70.0,
    "fear": -65.0,
    "remorse": -55.0,
    "nervousness": -45.0,
    "embarrassment": -35.0,
    "confusion": -25.0,
    "realization": -15.0,
    "neutral": 0.0,
}

ALPHA = 0.3
RESISTANCE_THRESHOLD_1 = 50.0
RESISTANCE_THRESHOLD_2 = 80.0
ESCALATION_THRESHOLD = -65.0


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

    s_current = max(-100.0, min(100.0, float(s_current)))

    raw_weight = EMOTION_WEIGHTS.get(emotion_clean, 0.0)

    same_direction = (s_current > 0 and raw_weight > 0) or (s_current < 0 and raw_weight < 0)
    abs_score = abs(s_current)

    if same_direction:
        if abs_score >= RESISTANCE_THRESHOLD_2:
            dampening_factor = 0.2
        elif abs_score >= RESISTANCE_THRESHOLD_1:
            dampening_factor = 0.5
        else:
            dampening_factor = 1.0
    else:
        dampening_factor = 1.0

    effective_alpha = ALPHA * dampening_factor

    s_new = (effective_alpha * raw_weight) + ((1.0 - effective_alpha) * s_current)
    s_new = max(-100.0, min(100.0, round(s_new, 2)))

    escalation_triggered = s_new <= ESCALATION_THRESHOLD

    dampened_raw_score = raw_weight * dampening_factor

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
