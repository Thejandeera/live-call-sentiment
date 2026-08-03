import spacy
import sys
import subprocess
import requests
from spacy.matcher import PhraseMatcher
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Keyword Detection Service")

APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbwwudCW1hW9TbEV3btIXJl9rYi3GYU2E1jQ55mAXj9LAniuG8i0SLPMmrRrgWgsdHAQWA/exec"

class TextPayload(BaseModel):
    transcript: str = ""
    text: str = ""

nlp = None

@app.on_event("startup")
def load_spacy():
    global nlp
    try:
        print("[Phrase Service] Loading en_core_web_sm...")
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        print("[Phrase Service] Model not found. Downloading...")
        subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
        nlp = spacy.load("en_core_web_sm")
    print("[Phrase Service] Ready.")

@app.post("/extract-phrases")
@app.post("/extract-keywords")
async def extract_keywords(payload: TextPayload):
    text_content = payload.text if payload.text else payload.transcript
    if not text_content:
        return {"matches": [], "keywords": []}

    try:
        remote_data = requests.get(APPS_SCRIPT_URL).json()
    except Exception:
        remote_data = []

    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    keyword_db = {}
    
    for item in remote_data:
        kw = item.get("keyword", "")
        if kw:
            keyword_db[kw.lower()] = item.get("sentiment", "neutral")
            matcher.add(kw, [nlp.make_doc(kw)])

    doc = nlp(text_content)
    matches = matcher(doc)
    
    detected_keywords = []
    seen = set()
    
    for match_id, start, end in matches:
        matched_span = doc[start:end]
        kw_text = matched_span.text.lower()
        
        if kw_text not in seen:
            sentiment = keyword_db.get(kw_text, "neutral")
            detected_keywords.append({
                "keyword": matched_span.text,
                "sentiment": sentiment
            })
            seen.add(kw_text)
            
    return {
        "matches": detected_keywords,
        "keywords": detected_keywords
    }
