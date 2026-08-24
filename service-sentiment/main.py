import os
import torch
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import pipeline
from dotenv import load_dotenv


env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

app = FastAPI(title="Sentiment & Emotion Service")

MODEL_NAME = os.getenv("SENTIMENT_MODEL_NAME", os.getenv("MODEL_NAME", "SamLowe/roberta-base-go_emotions"))

class TextPayload(BaseModel):
    isolated_sentence: Optional[str] = None
    text: Optional[str] = None

class BatchItem(BaseModel):
    isolated_sentence: Optional[str] = None
    text: Optional[str] = None

class BatchPayload(BaseModel):
    items: List[BatchItem]

roberta_model = None

def categorize_emotion(emotion: str, score: float) -> str:
    positive_emotions = {
        "admiration", "amusement", "approval", "caring", "desire",
        "excitement", "gratitude", "joy", "love", "optimism", "pride", "relief"
    }
    negative_emotions = {
        "anger", "annoyance", "confusion", "curiosity", "disappointment", "disapproval", "disgust",
        "embarrassment", "fear", "grief", "nervousness", "realization", "remorse", "sadness"
    }
    if emotion in positive_emotions:
        return "positive" if score >= 0.20 else "neutral"
    elif emotion in negative_emotions:
        return "negative" if score >= 0.20 else "neutral"
    else:
        return "neutral"

@app.on_event("startup")
def load_model():
    global roberta_model
    if roberta_model is None:
        print(f"[Sentiment Service] Loading RoBERTa model '{MODEL_NAME}'...")
        roberta_model = pipeline("text-classification", model=MODEL_NAME)
        print("[Sentiment Service] RoBERTa model ready.")

@app.get("/")
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "service-sentiment",
        "model_name": MODEL_NAME,
        "model_loaded": roberta_model is not None
    }

@app.post("/analyze-sentiment")
async def analyze_sentiment(payload: TextPayload):
    global roberta_model
    if roberta_model is None:
        load_model()

    sentence = payload.isolated_sentence if payload.isolated_sentence is not None and payload.isolated_sentence.strip() else payload.text
    if not sentence or not sentence.strip():
        return {"emotion": "neutral", "sentiment_category": "neutral", "confidence": 0.0}
        
    with torch.inference_mode():
        result = roberta_model(sentence.strip(), truncation=True, max_length=128)[0]
    
    emotion = result["label"]
    confidence = round(float(result["score"]), 4)
    category = categorize_emotion(emotion, confidence)
    
    return {
        "emotion": emotion,
        "sentiment_category": category,
        "confidence": confidence
    }

@app.post("/analyze-sentiment-batch")
async def analyze_sentiment_batch(payload: BatchPayload):
    global roberta_model
    if roberta_model is None:
        load_model()

    if not payload.items:
        return {"results": []}

    sentences = [
        (item.isolated_sentence if item.isolated_sentence is not None and item.isolated_sentence.strip() else item.text or "").strip()
        for item in payload.items
    ]
    
    valid_sentences = [s if s else "." for s in sentences]
    
    with torch.inference_mode():
        batch_results = roberta_model(valid_sentences, truncation=True, max_length=128, batch_size=32)

    output = []
    for item, result in zip(payload.items, batch_results):
        emotion = result["label"]
        confidence = round(float(result["score"]), 4)
        category = categorize_emotion(emotion, confidence)

        output.append({
            "emotion": emotion,
            "sentiment_category": category,
            "confidence": confidence
        })

    return {"results": output}
