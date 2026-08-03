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

PHRASE_SERVICE_URL = "http://localhost:8002/extract-keywords"
SENTIMENT_SERVICE_URL = "http://localhost:8003/analyze-sentiment"

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

@app.post("/api/v1/process-message")
async def process_message(payload: MessagePayload):
    try:
        start_time = time.perf_counter()
        client = http_client if http_client is not None else httpx.AsyncClient(timeout=30.0)
        
        text = payload.text.strip()
        speaker = payload.speaker if payload.speaker in ["agent", "caller"] else "caller"
        if not text:
            return {"status": "success", "detected_issues": [], "processing_time_ms": 0}

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

        end_time = time.perf_counter()
        processing_time_ms = round((end_time - start_time) * 1000, 2)

        return {
            "status": "success",
            "processing_time_ms": processing_time_ms,
            "detected_issues": [{
                "isolated_sentence": text,
                "speaker": speaker,
                "phrase": detected_keywords[0]["keyword"] if detected_keywords else "N/A",
                "detected_keywords": detected_keywords,
                "emotion": emotion,
                "sentiment_category": sentiment_category,
                "confidence": confidence
            }]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Gateway Error: {str(e)}")
