import os
import sys

# Suppress verbose huggingface/transformers multi-line and per-file progress bars
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

import torch
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, Request
from pydantic import BaseModel
import transformers
from transformers import pipeline, logging as hf_logging
from tqdm import tqdm
import huggingface_hub
from huggingface_hub import HfApi, hf_hub_download, try_to_load_from_cache
from dotenv import load_dotenv
from audit_logger import AuditLoggingMiddleware

hf_logging.set_verbosity_error()
transformers.utils.logging.disable_progress_bar()
huggingface_hub.utils.disable_progress_bars()

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

class CriticalError(Exception):
    pass

app = FastAPI(title="Sentiment & Emotion Service")

@app.exception_handler(CriticalError)
async def critical_error_handler(request: Request, exc: CriticalError):
    print(f"CRITICAL ERROR: {exc}. Terminating service...")
    os._exit(1)

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

roberta_model = None

def download_model_with_progress(repo_id: str):
    """
    Downloads required repository files using 1 single real-time progress bar,
    suppressing byte-by-byte line spam and per-file progress outputs.
    """
    try:
        api = HfApi()
        info = api.model_info(repo_id, files_metadata=True)
        
        files_to_download = []
        total_bytes = 0
        
        for sibling in info.siblings:
            filename = sibling.rfilename
            if filename.startswith(".") or filename.endswith(".gitattributes"):
                continue
            cached_path = try_to_load_from_cache(repo_id, filename)
            file_size = sibling.size or 0
            if cached_path is None or not os.path.exists(cached_path):
                files_to_download.append((filename, file_size))
                total_bytes += file_size

        if not files_to_download:
            return

        print(f"[Sentiment Service] Downloading RoBERTa model '{repo_id}' ({total_bytes / (1024 * 1024):.1f} MB)...")
        
        with tqdm(
            total=total_bytes,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            desc=f"Downloading {repo_id.split('/')[-1]}",
            ncols=85,
            file=sys.stdout,
            leave=True,
            mininterval=0.2
        ) as pbar:
            for filename, file_size in files_to_download:
                hf_hub_download(
                    repo_id=repo_id,
                    filename=filename,
                )
                if file_size > 0:
                    pbar.update(file_size)
            if pbar.n < total_bytes:
                pbar.update(total_bytes - pbar.n)
    except Exception:
        # Fallback to default pipeline loader if metadata query fails
        pass

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
        try:
            print(f"[Sentiment Service] Loading RoBERTa model '{MODEL_NAME}'...")
            download_model_with_progress(MODEL_NAME)
            roberta_model = pipeline("text-classification", model=MODEL_NAME)
            print("[Sentiment Service] RoBERTa model ready.")
        except Exception as e:
            print(f"CRITICAL ERROR: Failed to load model '{MODEL_NAME}': {e}. Terminating service...")
            os._exit(1)

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