import os
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI
from pydantic import BaseModel, Field
from dotenv import load_dotenv


env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

app = FastAPI(title="Live Sentiment Score Service")

EMOTION_WEIGHTS = {
    "gratitude": 100.0,
    "relief": 95.0,
    "approval": 85.0,
    "optimism": 80.0,
    "caring": 75.0,
    "joy": 70.0,
    "admiration": 65.0,
    "excitement": 60.0,
    "surprise": 0.0,     
    "amusement": 45.0,
    "curiosity": -10.0,   
    "pride": 40.0,
    "love": 35.0,
    "desire": 25.0,
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
SATURATION_SCALE = 100.0          
POSITIVE_SATURATION_SCALE = 150.0  
ESCALATION_THRESHOLD = float(os.getenv("ESCALATION_THRESHOLD", "-65.0"))


FAST_RECOVERY_EMOTIONS = {
    "gratitude", "relief", "approval", "joy", "optimism", "caring", "admiration",
    "excitement", "amusement", "pride", "love", "desire"
}


class ScoreRequest(BaseModel):
    emotion: str
    confidence: Optional[float] = 1.0
    previous_score: Optional[float] = 0.0
    session_avg_score: Optional[float] = None
    turn_count: Optional[int] = 1
    speaker: Optional[str] = "caller"
    peak_negativity: Optional[float] = None
    recent_scores: Optional[List[float]] = None


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


@app.get("/")
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "service-score",
        "base_alpha": BASE_ALPHA,
        "neutral_alpha": NEUTRAL_ALPHA,
        "saturation_scale": SATURATION_SCALE,
        "escalation_threshold": ESCALATION_THRESHOLD
    }


@app.post("/calculate-score", response_model=ScoreResponse)
async def calculate_score(payload: ScoreRequest):
    turn_count = max(1, payload.turn_count if payload.turn_count is not None else 1)
    emotion_clean = payload.emotion.strip().lower() if payload.emotion else "neutral"
    confidence = payload.confidence if (payload.confidence is not None and payload.confidence >= 0.0) else 1.0
    s_current = payload.previous_score if payload.previous_score is not None else 0.0
    s_current = max(-100.0, min(100.0, float(s_current)))

    w_destination = EMOTION_WEIGHTS.get(emotion_clean, 0.0)
    w_effective = w_destination * confidence

  
    confidence_weight = max(0.40, confidence)

    dampening_factor = 1.0

    if emotion_clean == "neutral" or w_destination == 0.0:
        
        if s_current <= ESCALATION_THRESHOLD:
            effective_alpha = 0.005
        else:
            effective_alpha = NEUTRAL_ALPHA * confidence_weight
        dampening_factor = round(effective_alpha / BASE_ALPHA, 4)
    else:
        is_recovery = (s_current < 0 and w_destination > 0) or (s_current > 0 and w_destination < 0)
        
        if is_recovery:
           
            if emotion_clean in FAST_RECOVERY_EMOTIONS or s_current >= 0:
                dampening_factor = 1.0
            else:
                abs_score = abs(s_current)
                dampening_factor = 1.0 / (1.0 + (abs_score / SATURATION_SCALE) ** 2)
        else:
            abs_score = abs(s_current)
            if w_destination > 0:
                dampening_factor = 1.0 / (1.0 + (abs_score / POSITIVE_SATURATION_SCALE) ** 2)
            else:
                dampening_factor = 1.0 / (1.0 + (abs_score / SATURATION_SCALE) ** 2)

        
        if s_current <= ESCALATION_THRESHOLD and w_destination < 0 and w_destination > s_current:
            effective_alpha = 0.01
        else:
            effective_alpha = BASE_ALPHA * dampening_factor * confidence_weight

  
    s_new = (effective_alpha * w_destination) + ((1.0 - effective_alpha) * s_current)

    
    if s_current <= ESCALATION_THRESHOLD and w_destination <= -50.0 and turn_count > 10:
        duration_penalty = -min(0.60, (turn_count / 100.0) * 0.60)
        s_new += duration_penalty

    s_new = max(-100.0, min(100.0, round(s_new, 2)))

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
        emotion_weight=w_destination,
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
