import os
import json
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI
from pydantic import BaseModel
import onnxruntime as ort
from transformers import AutoTokenizer
import numpy as np
from dotenv import load_dotenv
from audit_logger import AuditLoggingMiddleware

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

app = FastAPI(title="Sentiment & Emotion Service")
app.add_middleware(AuditLoggingMiddleware, service_name="service-sentiment")

MODEL_NAME = os.getenv("SENTIMENT_MODEL_NAME", os.getenv("MODEL_NAME", "SamLowe/roberta-base-go_emotions"))

class TextPayload(BaseModel):
    isolated_sentence: Optional[str] = None
    text: Optional[str] = None

class BatchItem(BaseModel):
    isolated_sentence: Optional[str] = None
    text: Optional[str] = None

class BatchPayload(BaseModel):
    items: List[BatchItem]

ort_session = None
tokenizer = None
id2label = {}

def sigmoid(x):
    return 1 / (1 + np.exp(-x))

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
    global ort_session, tokenizer, id2label
    if ort_session is None:
        print(f"[Sentiment Service] Loading Pure ONNX model '{MODEL_NAME}'...")
        model_path = Path(__file__).resolve().parent / "onnx_model"
        
        load_path = str(model_path) if model_path.exists() and (model_path / "model.onnx").exists() else MODEL_NAME
        
        tokenizer = AutoTokenizer.from_pretrained(load_path)
        ort_session = ort.InferenceSession(str(model_path / "model.onnx"), providers=["CPUExecutionProvider"])
        
        with open(model_path / "config.json", "r") as f:
            config = json.load(f)
            id2label = config.get("id2label", {})
            
        print("[Sentiment Service] Pure ONNX RoBERTa model ready.")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "service-sentiment",
        "model_name": MODEL_NAME,
        "model_loaded": ort_session is not None
    }

@app.post("/analyze-sentiment")
async def analyze_sentiment(payload: TextPayload):
    global ort_session
    if ort_session is None:
        load_model()

    sentence = payload.isolated_sentence if payload.isolated_sentence is not None and payload.isolated_sentence.strip() else payload.text
    if not sentence or not sentence.strip():
        return {"emotion": "neutral", "sentiment_category": "neutral", "confidence": 0.0}
        
    inputs = tokenizer(sentence.strip(), return_tensors="np", truncation=True, max_length=128)
    ort_inputs = {
        "input_ids": inputs["input_ids"],
        "attention_mask": inputs["attention_mask"]
    }
    
    outputs = ort_session.run(None, ort_inputs)
    logits = outputs[0][0]
    
    probs = sigmoid(logits)
    best_idx = np.argmax(probs)
    
    emotion = id2label.get(str(best_idx), "neutral")
    confidence = round(float(probs[best_idx]), 4)
    category = categorize_emotion(emotion, confidence)
    
    return {
        "emotion": emotion,
        "sentiment_category": category,
        "confidence": confidence
    }

@app.post("/analyze-sentiment-batch")
async def analyze_sentiment_batch(payload: BatchPayload):
    global ort_session
    if ort_session is None:
        load_model()

    if not payload.items:
        return {"results": []}

    sentences = [
        (item.isolated_sentence if item.isolated_sentence is not None and item.isolated_sentence.strip() else item.text or "").strip()
        for item in payload.items
    ]
    valid_sentences = [s if s else "." for s in sentences]
    
    inputs = tokenizer(valid_sentences, return_tensors="np", truncation=True, max_length=128, padding=True)
    ort_inputs = {
        "input_ids": inputs["input_ids"],
        "attention_mask": inputs["attention_mask"]
    }
    
    outputs = ort_session.run(None, ort_inputs)
    logits_batch = outputs[0]
    
    output = []
    for item, logits in zip(payload.items, logits_batch):
        probs = sigmoid(logits)
        best_idx = np.argmax(probs)
        
        emotion = id2label.get(str(best_idx), "neutral")
        confidence = round(float(probs[best_idx]), 4)
        category = categorize_emotion(emotion, confidence)

        output.append({
            "emotion": emotion,
            "sentiment_category": category,
            "confidence": confidence
        })

    return {"results": output}