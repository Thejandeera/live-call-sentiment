from typing import Optional, List
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Live Sentiment Score Service")

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

BASE_ALPHA = 0.3
NEUTRAL_ALPHA = 0.04
SATURATION_SCALE = 75.0
ESCALATION_THRESHOLD = -65.0


class ScoreRequest(BaseModel):
    emotion: str
    confidence: Optional[float] = 1.0
    previous_score: Optional[float] = 0.0
    session_avg_score: Optional[float] = None
    turn_count: Optional[int] = 1
    speaker: Optional[str] = "caller"
    peak_negativity: Optional[float] = None
    recent_scores: Optional[List[float]] = None
    negative_threshold_1: Optional[float] = None
    negative_threshold_1_dampening_factor: Optional[float] = None
    negative_threshold_2: Optional[float] = None
    negative_threshold_2_dampening_factor: Optional[float] = None


class ScoreResponse(BaseModel):
    emotion: str
    confidence: float
    emotion_weight: float
    effective_emotion_weight: float
    previous_score: float
    dampening_factor: float
    dampened_raw_score: float
    score: float
    call_health_score: float
    sentiment_trend: str
    peak_negativity: float
    turn_count: int
    session_avg_score: float
    escalation_triggered: bool


@app.post("/calculate-score", response_model=ScoreResponse)
async def calculate_score(payload: ScoreRequest):
    emotion_clean = payload.emotion.strip().lower() if payload.emotion else "neutral"
    confidence = payload.confidence if (payload.confidence is not None and payload.confidence >= 0.0) else 1.0
    s_current = payload.previous_score if payload.previous_score is not None else 0.0
    s_current = max(-100.0, min(100.0, float(s_current)))

    raw_weight = EMOTION_WEIGHTS.get(emotion_clean, 0.0)
    w_effective = raw_weight * confidence

    dampening_factor = 1.0

    if emotion_clean == "neutral" or raw_weight == 0.0:
        effective_alpha = NEUTRAL_ALPHA
        dampening_factor = round(NEUTRAL_ALPHA / BASE_ALPHA, 4)
    else:
        same_direction = (s_current > 0 and w_effective > 0) or (s_current < 0 and w_effective < 0)
        
        if same_direction:
            abs_score = abs(s_current)
            if payload.negative_threshold_1 is not None or payload.negative_threshold_2 is not None:
                neg_thresh_1 = payload.negative_threshold_1 if payload.negative_threshold_1 is not None else 50.0
                neg_damp_1 = payload.negative_threshold_1_dampening_factor if payload.negative_threshold_1_dampening_factor is not None else 0.5
                neg_thresh_2 = payload.negative_threshold_2 if payload.negative_threshold_2 is not None else 80.0
                neg_damp_2 = payload.negative_threshold_2_dampening_factor if payload.negative_threshold_2_dampening_factor is not None else 0.2
                if abs_score >= neg_thresh_2:
                    dampening_factor = neg_damp_2
                elif abs_score >= neg_thresh_1:
                    dampening_factor = neg_damp_1
                else:
                    dampening_factor = 1.0
            else:
                dampening_factor = 1.0 / (1.0 + (abs_score / SATURATION_SCALE) ** 2)
        else:
            dampening_factor = 1.0

        effective_alpha = BASE_ALPHA * dampening_factor

    s_new = (effective_alpha * w_effective) + ((1.0 - effective_alpha) * s_current)
    s_new = max(-100.0, min(100.0, round(s_new, 2)))

    turn_count = max(1, payload.turn_count if payload.turn_count is not None else 1)
    prev_session_avg = payload.session_avg_score if payload.session_avg_score is not None else s_current
    
    new_session_avg = round(((prev_session_avg * (turn_count - 1)) + s_new) / turn_count, 2)
    call_health_score = max(-100.0, min(100.0, round(0.70 * new_session_avg + 0.30 * s_new, 2)))

    prev_peak_neg = payload.peak_negativity if payload.peak_negativity is not None else s_current
    peak_negativity = round(min(prev_peak_neg, s_new), 2)

    recent_scores = (payload.recent_scores or []) + [s_new]
    recent_scores = recent_scores[-5:]
    if len(recent_scores) >= 2:
        delta = recent_scores[-1] - recent_scores[0]
        if delta > 5.0:
            sentiment_trend = "Strong Recovery"
        elif delta < -5.0:
            sentiment_trend = "Escalating"
        else:
            sentiment_trend = "Stable"
    else:
        sentiment_trend = "Stable"

    escalation_triggered = s_new <= ESCALATION_THRESHOLD or call_health_score <= ESCALATION_THRESHOLD
    dampened_raw_score = w_effective * dampening_factor

    return ScoreResponse(
        emotion=payload.emotion,
        confidence=confidence,
        emotion_weight=raw_weight,
        effective_emotion_weight=round(w_effective, 2),
        previous_score=round(s_current, 2),
        dampening_factor=round(dampening_factor, 4),
        dampened_raw_score=round(dampened_raw_score, 2),
        score=s_new,
        call_health_score=call_health_score,
        sentiment_trend=sentiment_trend,
        peak_negativity=peak_negativity,
        turn_count=turn_count,
        session_avg_score=new_session_avg,
        escalation_triggered=escalation_triggered,
    )

