from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Live Sentiment Score Service (EMA with Non-Linear Dampening)")

# Contextual Severity Emotion Weights:
# Good (Positive) Emotions: (+) Weights from +5.0 to +100.0
# Bad (Negative) Emotions: (-) Weights from -15.0 to -100.0
EMOTION_WEIGHTS = {
    # Good (Positive) Emotions Hierarchy (+)
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

    # Bad (Negative) Emotions Hierarchy (-)
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

    # Neutral Emotion
    "neutral": 0.0,
}

ALPHA = 0.15  # Smoothing factor for Exponential Moving Average
RESISTANCE_THRESHOLD = 40.0  # Resistance threshold magnitude for non-linear dampening
ESCALATION_THRESHOLD = -65.0  # Critical threshold breach for manager intervention (negative scale)


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

    # Ensure s_current stays within valid signed bounds [-100.0, +100.0]
    s_current = max(-100.0, min(100.0, float(s_current)))

    # Get predefined contextual severity weight from hierarchy (+ for positive, - for negative)
    raw_weight = EMOTION_WEIGHTS.get(emotion_clean, 0.0)

    # Calculate asymptotic dampening factor D based on magnitude |S_current|
    abs_score = abs(s_current)
    if abs_score > RESISTANCE_THRESHOLD:
        dampening_factor = 1.0 - (abs_score / 100.0)
    else:
        dampening_factor = 1.0

    # Apply dampening multiplier to incoming emotion raw weight
    dampened_raw_score = raw_weight * dampening_factor

    # Exponential Moving Average (EMA) update calculation
    # S_new = (alpha * S_effective_raw) + ((1 - alpha) * S_current)
    s_new = (ALPHA * dampened_raw_score) + ((1.0 - ALPHA) * s_current)
    s_new = max(-100.0, min(100.0, round(s_new, 2)))

    # Check if negative escalation threshold (-65.0) is breached
    escalation_triggered = s_new <= ESCALATION_THRESHOLD

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

