import os
import sys
import subprocess
from pathlib import Path
from typing import List, Optional, Union
from datetime import datetime, timezone
import spacy
from spacy.matcher import PhraseMatcher
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError
from dotenv import load_dotenv


env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

app = FastAPI(title="Keyword & Phrase Detection Service (MongoDB)")


MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME")
MONGODB_COLLECTION_NAME = os.getenv("MONGODB_COLLECTION_NAME")
SPACY_MODEL = os.getenv("SPACY_MODEL", "en_core_web_sm")


in_memory_keywords = set()


class KeywordPayload(BaseModel):
    keyword: Optional[str] = None
    keywords: Optional[List[str]] = None

class TextPayload(BaseModel):
    transcript: Optional[str] = ""
    text: Optional[str] = ""

nlp = None
mongo_client: Optional[MongoClient] = None
keywords_collection = None


def get_mongo_collection():
    global mongo_client, keywords_collection
    if keywords_collection is not None:
        return keywords_collection
    
    if not MONGODB_URI or "<db_password>" in MONGODB_URI:
        return None

    try:
        if mongo_client is None:
            mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        db = mongo_client[MONGODB_DB_NAME]
        coll = db[MONGODB_COLLECTION_NAME]
      
        coll.create_index([("keyword", ASCENDING)], unique=True)
        keywords_collection = coll
        return keywords_collection
    except Exception as e:
        print(f"[Phrase Service] Warning: Unable to connect to MongoDB ({e}). Operating in in-memory fallback mode.")
        return None


@app.on_event("startup")
def startup_event():
    global nlp
    
    try:
        print(f"[Phrase Service] Loading {SPACY_MODEL}...")
        nlp = spacy.load(SPACY_MODEL)
    except OSError:
        print(f"[Phrase Service] Model '{SPACY_MODEL}' not found. Downloading...")
        subprocess.run([sys.executable, "-m", "spacy", "download", SPACY_MODEL])
        nlp = spacy.load(SPACY_MODEL)
    print(f"[Phrase Service] {SPACY_MODEL} ready.")

    
    coll = get_mongo_collection()
    if coll is not None:
        print(f"[Phrase Service] Connected to MongoDB database '{MONGODB_DB_NAME}', collection '{MONGODB_COLLECTION_NAME}'.")
    else:
        print("[Phrase Service] MongoDB URI not fully configured or pending credentials. Ready with fallback.")


@app.on_event("shutdown")
def shutdown_event():
    global mongo_client
    if mongo_client:
        mongo_client.close()


def fetch_stored_keywords() -> List[str]:
    """Retrieves all active keywords from MongoDB or in-memory fallback."""
    coll = get_mongo_collection()
    if coll is not None:
        try:
            cursor = coll.find({}, {"keyword": 1, "_id": 0})
            return [doc["keyword"] for doc in cursor if "keyword" in doc and doc["keyword"]]
        except Exception as e:
            print(f"[Phrase Service] Error querying MongoDB keywords: {e}")
            return list(in_memory_keywords)
    else:
        return list(in_memory_keywords)


@app.get("/")
@app.get("/health")
async def health_check():
    coll = get_mongo_collection()
    db_connected = False
    db_count = 0
    if coll is not None:
        try:
            db_count = coll.count_documents({})
            db_connected = True
        except Exception:
            db_connected = False

    return {
        "status": "healthy",
        "service": "service-phrase",
        "spacy_model": SPACY_MODEL,
        "database": {
            "type": "mongodb",
            "connected": db_connected,
            "database_name": MONGODB_DB_NAME,
            "collection": MONGODB_COLLECTION_NAME,
            "total_keywords": db_count if db_connected else len(in_memory_keywords)
        }
    }


@app.post("/keywords", status_code=status.HTTP_201_CREATED)
@app.post("/add-keyword", status_code=status.HTTP_201_CREATED)
async def add_keywords(payload: KeywordPayload):
    """Saves new monitored keyword(s) into MongoDB."""
    words_to_add = []
    if payload.keyword and payload.keyword.strip():
        words_to_add.append(payload.keyword.strip().lower())
    if payload.keywords:
        for kw in payload.keywords:
            if kw and kw.strip():
                words_to_add.append(kw.strip().lower())

    if not words_to_add:
        raise HTTPException(status_code=400, detail="No valid keyword provided. Supply 'keyword' or 'keywords'.")

  
    words_to_add = list(set(words_to_add))
    
    coll = get_mongo_collection()
    added_count = 0
    
    if coll is not None:
        try:
            for word in words_to_add:
                result = coll.update_one(
                    {"keyword": word},
                    {"$setOnInsert": {
                        "keyword": word,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }},
                    upsert=True
                )
                if result.upserted_id is not None:
                    added_count += 1
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"MongoDB insertion error: {str(e)}")
    else:
        for word in words_to_add:
            if word not in in_memory_keywords:
                in_memory_keywords.add(word)
                added_count += 1

    return {
        "status": "success",
        "message": f"Successfully processed {len(words_to_add)} keyword(s). {added_count} new keyword(s) stored.",
        "added_count": added_count,
        "processed_keywords": words_to_add
    }


@app.get("/keywords")
@app.get("/admin-keywords")
@app.get("/get-admin-keywords")
async def get_keywords():
    """Returns all monitored keywords from MongoDB."""
    keywords = fetch_stored_keywords()
    formatted = [{"keyword": kw} for kw in sorted(keywords)]
    return {
        "status": "success",
        "count": len(formatted),
        "keywords": formatted
    }


@app.delete("/keywords/{keyword}")
@app.delete("/delete-keyword/{keyword}")
async def delete_keyword(keyword: str):
    """Deletes a monitored keyword from MongoDB."""
    clean_kw = keyword.strip().lower()
    if not clean_kw:
        raise HTTPException(status_code=400, detail="Invalid keyword provided.")

    coll = get_mongo_collection()
    deleted = False
    if coll is not None:
        try:
            result = coll.delete_one({"keyword": clean_kw})
            deleted = result.deleted_count > 0
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"MongoDB deletion error: {str(e)}")
    else:
        if clean_kw in in_memory_keywords:
            in_memory_keywords.remove(clean_kw)
            deleted = True

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Keyword '{clean_kw}' not found.")

    return {
        "status": "success",
        "message": f"Keyword '{clean_kw}' successfully removed.",
        "keyword": clean_kw
    }


@app.post("/extract-phrases")
@app.post("/extract-keywords")
async def extract_keywords(payload: TextPayload):
    """Analyzes text and isolates matches against keywords stored in MongoDB."""
    text_content = payload.text if payload.text else payload.transcript
    if not text_content or not text_content.strip():
        return {"matches": [], "keywords": []}

    stored_keywords = fetch_stored_keywords()
    if not stored_keywords:
        return {"matches": [], "keywords": []}

    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    for kw in stored_keywords:
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
