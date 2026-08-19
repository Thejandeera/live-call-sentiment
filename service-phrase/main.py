import csv
import io
import re
import spacy
import sys
import subprocess
import requests
from spacy.matcher import PhraseMatcher
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Keyword Detection Service")

# Live Google Spreadsheet / Apps Script URL
APPS_SCRIPT_URL = "https://docs.google.com/spreadsheets/d/1yeeIb2uFRsXWJWFXDlKSA8c0oc_FuLwapMF5OH7Sf3k/edit"

class TextPayload(BaseModel):
    transcript: str = ""
    text: str = ""

nlp = None


def fetch_live_keywords(url: str):
    """Fetches live keyword rows directly from Google without hitting blocked googleusercontent domains."""
    if "docs.google.com/spreadsheets" in url:
        match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
        if match:
            sheet_id = match.group(1)
            # Direct docs.google.com gviz endpoint (zero redirects to googleusercontent.com)
            csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv"
            res = requests.get(csv_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            reader = csv.reader(io.StringIO(res.text))
            rows = list(reader)
            result = []
            if len(rows) > 1:
                for row in rows[1:]:
                    if row and row[0].strip():
                        result.append({
                            "keyword": row[0].strip().lower(),
                            "sentiment": row[1].strip().lower() if len(row) > 1 else "neutral",
                            "weight": int(row[2]) if (len(row) > 2 and row[2].isdigit()) else 0
                        })
            return result
    else:
        res = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        return res.json()


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
        remote_data = fetch_live_keywords(APPS_SCRIPT_URL)
    except Exception as e:
        print(f"[Phrase Service] Error fetching live keywords from Google: {e}")
        remote_data = []

    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    
    if isinstance(remote_data, list):
        for item in remote_data:
            kw = item.get("keyword", "").strip() if isinstance(item, dict) else ""
            if kw:
                matcher.add(kw, [nlp.make_doc(kw)])

    doc = nlp(text_content)
    matches = matcher(doc)
    
    detected_keywords = []
    seen = set()
    
    for match_id, start, end in matches:
        matched_span = doc[start:end]
        kw_text = matched_span.text.lower()
        
        if kw_text not in seen:
            detected_keywords.append({
                "keyword": matched_span.text
            })
            seen.add(kw_text)
            
    return {
        "matches": detected_keywords,
        "keywords": detected_keywords
    }


@app.get("/admin-keywords")
@app.get("/get-admin-keywords")
async def get_admin_keywords():
    try:
        remote_data = fetch_live_keywords(APPS_SCRIPT_URL)
        return {"status": "success", "keywords": remote_data}
    except Exception as e:
        return {"status": "error", "message": str(e), "keywords": []}



