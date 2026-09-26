import os
import sys
import time
from pathlib import Path
from typing import List, Optional


os.environ["PYTHONUNBUFFERED"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

import torch
import requests
from fastapi import FastAPI, Request
from pydantic import BaseModel
import transformers
from transformers import pipeline, logging as hf_logging
from huggingface_hub import HfApi, hf_hub_url
from dotenv import load_dotenv
from audit_logger import AuditLoggingMiddleware

hf_logging.set_verbosity_error()
transformers.utils.logging.disable_progress_bar()

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
LOCAL_MODEL_DIR = Path(os.getenv("LOCAL_MODEL_DIR", "/app/models/roberta"))

class TextPayload(BaseModel):
    isolated_sentence: Optional[str] = None
    text: Optional[str] = None

class BatchItem(BaseModel):
    isolated_sentence: Optional[str] = None
    text: Optional[str] = None

class BatchPayload(BaseModel):
    items: List[BatchItem]

roberta_model = None

ESSENTIAL_FILES = [
    "config.json",
    "model.safetensors",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "vocab.json",
    "merges.txt"
]

def download_model_with_progress(repo_id: str, dest_dir: Path):
    """
    Downloads essential repository files with real-time single-line progress updates
    once every second. Supports resuming interrupted downloads via HTTP Range requests.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN")
    base_headers = {"User-Agent": "sentiment-service"}
    if hf_token:
        base_headers["Authorization"] = f"Bearer {hf_token}"

    try:
        api = HfApi(token=hf_token)
        info = api.model_info(repo_id, files_metadata=True)

        sibling_map = {s.rfilename: s for s in info.siblings}

        target_files = []
        for filename in ESSENTIAL_FILES:
            if filename == "model.safetensors" and filename not in sibling_map:
                if "pytorch_model.bin" in sibling_map:
                    target_files.append(("pytorch_model.bin", sibling_map["pytorch_model.bin"].size or 0))
            elif filename in sibling_map:
                target_files.append((filename, sibling_map[filename].size or 0))

        if not target_files:
            return

        total_bytes = sum(size for _, size in target_files)
        already_present_bytes = 0
        files_to_fetch = []

        for filename, expected_size in target_files:
            local_file = dest_dir / filename
            if local_file.exists() and (expected_size == 0 or local_file.stat().st_size == expected_size):
                already_present_bytes += expected_size
            else:
                files_to_fetch.append((filename, expected_size))

        if not files_to_fetch:
            print(f"[Sentiment Service] All model files already cached in '{dest_dir}'.")
            return

        print(f"[Sentiment Service] Downloading RoBERTa model '{repo_id}' ({total_bytes / (1024 * 1024):.1f} MB)...")
        sys.stdout.write("[Sentiment Service] Connecting to Hugging Face CDN...\n")
        sys.stdout.flush()

        cumulative_bytes = already_present_bytes
        start_time = time.time()
        last_update_time = 0.0

        for filename, file_size in files_to_fetch:
            download_url = hf_hub_url(repo_id=repo_id, filename=filename)
            dest_file = dest_dir / filename
            part_file = dest_dir / f"{filename}.part"

            headers = dict(base_headers)
            mode = "wb"
            initial_part_size = 0

            if part_file.exists():
                initial_part_size = part_file.stat().st_size
                if initial_part_size > 0 and (file_size == 0 or initial_part_size < file_size):
                    headers["Range"] = f"bytes={initial_part_size}-"
                    mode = "ab"
                    cumulative_bytes += initial_part_size

            with requests.get(download_url, headers=headers, stream=True, allow_redirects=True, timeout=60) as r:
                if "Range" in headers and r.status_code != 206:
                    mode = "wb"
                    cumulative_bytes -= initial_part_size
                    initial_part_size = 0

                r.raise_for_status()

                with open(part_file, mode) as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        f.write(chunk)
                        cumulative_bytes += len(chunk)

                        now = time.time()
                        if now - last_update_time >= 1.0 or cumulative_bytes >= total_bytes:
                            elapsed = max(now - start_time, 0.001)
                            downloaded_session = cumulative_bytes - already_present_bytes
                            speed_bps = downloaded_session / elapsed
                            speed_mbps = speed_bps / (1024 * 1024)
                            pct = (cumulative_bytes / total_bytes * 100) if total_bytes > 0 else 0.0
                            remaining_bytes = max(total_bytes - cumulative_bytes, 0)
                            eta = int(remaining_bytes / speed_bps) if speed_bps > 0 else 0

                            status_line = (
                                f"\033[A\r\033[K[Downloading {filename}] {pct:5.1f}% "
                                f"({cumulative_bytes / (1024 * 1024):.1f}/{total_bytes / (1024 * 1024):.1f} MB) | "
                                f"Speed: {speed_mbps:.2f} MB/s | ETA: {eta}s\n"
                            )
                            sys.stdout.write(status_line)
                            sys.stdout.flush()
                            last_update_time = now

            if part_file.exists():
                part_file.replace(dest_file)

        sys.stdout.write(f"\033[A\r\033[K[Sentiment Service] RoBERTa model files downloaded and verified ({total_bytes / (1024 * 1024):.1f} MB).\n")
        sys.stdout.flush()

    except Exception as e:
        sys.stdout.write(f"\n[Sentiment Service] Warning: Custom streaming download error: {e}. Falling back to standard pipeline loader...\n")
        sys.stdout.flush()

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
            print(f"[Sentiment Service] Preparing RoBERTa model '{MODEL_NAME}' in '{LOCAL_MODEL_DIR}'...")
            download_model_with_progress(MODEL_NAME, LOCAL_MODEL_DIR)

            has_weights = (LOCAL_MODEL_DIR / "model.safetensors").exists() or (LOCAL_MODEL_DIR / "pytorch_model.bin").exists()
            has_config = (LOCAL_MODEL_DIR / "config.json").exists()

            if has_weights and has_config:
                print(f"[Sentiment Service] Loading pipeline from local path '{LOCAL_MODEL_DIR}'...")
                roberta_model = pipeline("text-classification", model=str(LOCAL_MODEL_DIR), top_k=1)
            else:
                print(f"[Sentiment Service] Loading pipeline from repo '{MODEL_NAME}'...")
                roberta_model = pipeline("text-classification", model=MODEL_NAME, top_k=1)

            print("[Sentiment Service] RoBERTa model ready.")
        except Exception as e:
            print(f"CRITICAL ERROR: Failed to load model '{MODEL_NAME}': {e}. Terminating service...")
            os._exit(1)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy" if roberta_model is not None else "initializing",
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
        raw_result = roberta_model(sentence.strip(), truncation=True, max_length=128)[0]

    # top_k=1 returns a list per item — unwrap to get the top prediction dict
    result = raw_result[0] if isinstance(raw_result, list) else raw_result
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
        # top_k=1 returns a list per item — unwrap to get the top prediction dict
        top = result[0] if isinstance(result, list) else result
        emotion = top["label"]
        confidence = round(float(top["score"]), 4)
        category = categorize_emotion(emotion, confidence)

        output.append({
            "emotion": emotion,
            "sentiment_category": category,
            "confidence": confidence
        })

    return {"results": output}