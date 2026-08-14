import time
import asyncio
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

app = FastAPI(title="Live Call Sentiment API Gateway")

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MessagePayload(BaseModel):
    text: str
    speaker: Optional[str] = "caller"
    previous_score: Optional[float] = 0.0
    negative_threshold_1: Optional[float] = None
    negative_threshold_1_dampening_factor: Optional[float] = None
    negative_threshold_2: Optional[float] = None
    negative_threshold_2_dampening_factor: Optional[float] = None

PHRASE_SERVICE_URL = "http://localhost:8002/extract-keywords"
SENTIMENT_SERVICE_URL = "http://localhost:8003/analyze-sentiment"
SCORE_SERVICE_URL = "http://localhost:8004/calculate-score"

http_client: httpx.AsyncClient = None

@app.on_event("startup")
async def startup_event():
    global http_client
    http_client = httpx.AsyncClient(timeout=30.0, limits=httpx.Limits(max_keepalive_connections=20, max_connections=100))

@app.on_event("shutdown")
async def shutdown_event():
    global http_client
    if http_client:
        await http_client.aclose()

@app.post("/api/v1/process-text")
async def process_message(payload: MessagePayload):
    try:
        start_time = time.perf_counter()
        client = http_client if http_client is not None else httpx.AsyncClient(timeout=30.0)
        
        text = payload.text.strip()
        speaker = payload.speaker if payload.speaker in ["agent", "caller"] else "caller"
        previous_score = payload.previous_score if payload.previous_score is not None else 0.0

        if not text:
            return {
                "status": "success",
                "processing_time_ms": 0,
                "detected_issues": []
            }

        detected_keywords = []
        try:
            phrase_res = await client.post(PHRASE_SERVICE_URL, json={"text": text})
            if phrase_res.status_code == 200:
                detected_keywords = phrase_res.json().get("keywords", phrase_res.json().get("matches", []))
        except Exception as e:
            print(f"Warning: Keyword detection service error: {e}")

        emotion = "neutral"
        sentiment_category = "neutral"
        confidence = 0.0
        try:
            sentiment_res = await client.post(SENTIMENT_SERVICE_URL, json={"text": text})
            if sentiment_res.status_code == 200:
                s_data = sentiment_res.json()
                emotion = s_data.get("emotion", "neutral")
                sentiment_category = s_data.get("sentiment_category", "neutral")
                confidence = float(s_data.get("confidence", 0.0))
        except Exception as e:
            print(f"Warning: Sentiment analysis service error: {e}")

        score_details = {
            "emotion": emotion,
            "confidence": confidence,
            "emotion_weight": 0.0,
            "previous_score": previous_score,
            "dampening_factor": 1.0,
            "dampened_raw_score": 0.0,
            "score": previous_score,
            "escalation_triggered": previous_score <= -65.0
        }

        score_req_payload = {
            "emotion": emotion,
            "confidence": confidence,
            "previous_score": previous_score
        }
        if payload.negative_threshold_1 is not None:
            score_req_payload["negative_threshold_1"] = payload.negative_threshold_1
        if payload.negative_threshold_1_dampening_factor is not None:
            score_req_payload["negative_threshold_1_dampening_factor"] = payload.negative_threshold_1_dampening_factor
        if payload.negative_threshold_2 is not None:
            score_req_payload["negative_threshold_2"] = payload.negative_threshold_2
        if payload.negative_threshold_2_dampening_factor is not None:
            score_req_payload["negative_threshold_2_dampening_factor"] = payload.negative_threshold_2_dampening_factor

        try:
            score_res = await client.post(
                SCORE_SERVICE_URL,
                json=score_req_payload
            )
            if score_res.status_code == 200:
                score_details = score_res.json()
        except Exception as e:
            print(f"Warning: Score calculation service error: {e}")

        end_time = time.perf_counter()
        processing_time_ms = round((end_time - start_time) * 1000, 2)

        return {
            "status": "success",
            "processing_time_ms": processing_time_ms,
            "detected_issues": [{
                "isolated_sentence": text,
                "detected_keywords": detected_keywords,
                "emotion": emotion,
                "sentiment_category": sentiment_category,
                "live_score": score_details.get("score", previous_score)
            }]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Gateway Error: {str(e)}")
