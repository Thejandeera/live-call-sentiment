import torch
from typing import List, Optional
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import pipeline

app = FastAPI(title="Sentiment & Emotion Service")

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
        "anger", "annoyance", "disappointment", "disapproval", "disgust",
        "embarrassment", "fear", "grief", "nervousness", "remorse", "sadness"
    }
    if emotion in positive_emotions:
        return "positive" if score >= 0.50 else "neutral"
    elif emotion in negative_emotions:
        return "negative" if score >= 0.20 else "neutral"
    else:
        return "positive" if emotion == "surprise" and score >= 0.75 else "neutral"

@app.on_event("startup")
def load_model():
    global roberta_model
    print("[Sentiment Service] Loading RoBERTa emotion classification model...")
    roberta_model = pipeline("text-classification", model="SamLowe/roberta-base-go_emotions")
    print("[Sentiment Service] RoBERTa model ready.")

@app.post("/analyze-sentiment")
async def analyze_sentiment(payload: TextPayload):
    sentence = payload.isolated_sentence if payload.isolated_sentence else payload.text
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
    if not payload.items:
        return {"results": []}

    sentences = [
        (item.isolated_sentence if item.isolated_sentence else item.text or "").strip()
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
