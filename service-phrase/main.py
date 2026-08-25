import os
import sys
import subprocess
from pathlib import Path
from typing import List, Optional, Union
from contextlib import contextmanager
from datetime import datetime, timezone
import spacy
from spacy.matcher import PhraseMatcher
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
import psycopg2
from psycopg2 import pool
from psycopg2.extras import DictCursor
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

app = FastAPI(title="Keyword & Phrase Detection Service (PostgreSQL)")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "callIntelligence")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_TABLE = os.getenv("POSTGRES_TABLE", "call_admin_keywords")
POSTGRES_URI = os.getenv("POSTGRES_URI")
SPACY_MODEL = os.getenv("SPACY_MODEL", "en_core_web_sm")

in_memory_keywords = set()

class KeywordPayload(BaseModel):
    keyword: Optional[str] = None
    keywords: Optional[List[str]] = None

class TextPayload(BaseModel):
    transcript: Optional[str] = ""
    text: Optional[str] = ""

nlp = None
db_pool: Optional[pool.ThreadedConnectionPool] = None


def get_connection_params():
    if POSTGRES_URI:
        return {"dsn": POSTGRES_URI}
    return {
        "host": POSTGRES_HOST,
        "port": POSTGRES_PORT,
        "dbname": POSTGRES_DB,
        "user": POSTGRES_USER,
        "password": POSTGRES_PASSWORD
    }


def init_db_pool():
    global db_pool
    if db_pool is not None:
        return db_pool

    try:
        params = get_connection_params()
        db_pool = pool.ThreadedConnectionPool(minconn=1, maxconn=20, **params)
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                create_table_sql = f"""
                CREATE TABLE IF NOT EXISTS {POSTGRES_TABLE} (
                    id SERIAL PRIMARY KEY,
                    keyword VARCHAR(255) UNIQUE NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
                """
                cur.execute(create_table_sql)
            conn.commit()
        return db_pool
    except Exception as e:
        print(f"[Phrase Service] Warning: Unable to connect to PostgreSQL database '{POSTGRES_DB}' ({e}). Operating in in-memory fallback mode.")
        db_pool = None
        return None


@contextmanager
def get_db_connection():
    global db_pool
    if db_pool is None:
        init_db_pool()
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Database connection pool unavailable.")
    
    conn = db_pool.getconn()
    try:
        yield conn
    finally:
        db_pool.putconn(conn)


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

    pool_instance = init_db_pool()
    if pool_instance is not None:
        print(f"[Phrase Service] Connected to PostgreSQL database '{POSTGRES_DB}', table '{POSTGRES_TABLE}'.")
    else:
        print("[Phrase Service] PostgreSQL not fully configured or offline. Ready with fallback.")


@app.on_event("shutdown")
def shutdown_event():
    global db_pool
    if db_pool:
        db_pool.closeall()
        print("[Phrase Service] PostgreSQL connection pool closed.")


def fetch_stored_keywords() -> List[str]:
    """Retrieves all active keywords from PostgreSQL or in-memory fallback."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT keyword FROM {POSTGRES_TABLE} ORDER BY keyword ASC;")
                rows = cur.fetchall()
                return [row[0] for row in rows if row and row[0]]
    except Exception as e:
        print(f"[Phrase Service] Fallback retrieving keywords: {e}")
        return list(in_memory_keywords)


@app.get("/health")
async def health_check():
    db_connected = False
    db_count = 0
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {POSTGRES_TABLE};")
                row = cur.fetchone()
                db_count = row[0] if row else 0
                db_connected = True
    except Exception:
        db_connected = False

    return {
        "status": "healthy",
        "service": "service-phrase",
        "spacy_model": SPACY_MODEL,
        "database": {
            "type": "postgresql",
            "connected": db_connected,
            "database_name": POSTGRES_DB,
            "table_name": POSTGRES_TABLE,
            "total_keywords": db_count if db_connected else len(in_memory_keywords)
        }
    }


@app.post("/add-keyword", status_code=status.HTTP_201_CREATED)
async def add_keywords(payload: KeywordPayload):
    """Saves new monitored keyword(s) into PostgreSQL call_admin_keywords."""
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
    added_count = 0

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for word in words_to_add:
                    insert_sql = f"""
                    INSERT INTO {POSTGRES_TABLE} (keyword)
                    VALUES (%s)
                    ON CONFLICT (keyword) DO NOTHING
                    RETURNING id;
                    """
                    cur.execute(insert_sql, (word,))
                    res = cur.fetchone()
                    if res is not None:
                        added_count += 1
            conn.commit()
    except Exception as e:
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


@app.get("/admin-keywords")
async def get_keywords():
    """Returns all monitored keywords from PostgreSQL."""
    keywords = fetch_stored_keywords()
    formatted = [{"keyword": kw} for kw in sorted(keywords)]
    return {
        "status": "success",
        "count": len(formatted),
        "keywords": formatted
    }


@app.delete("/delete-keyword/{keyword}")
async def delete_keyword(keyword: str):
    """Deletes a monitored keyword from PostgreSQL."""
    clean_kw = keyword.strip().lower()
    if not clean_kw:
        raise HTTPException(status_code=400, detail="Invalid keyword provided.")

    deleted = False
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                delete_sql = f"DELETE FROM {POSTGRES_TABLE} WHERE LOWER(keyword) = %s;"
                cur.execute(delete_sql, (clean_kw,))
                deleted = cur.rowcount > 0
            conn.commit()
    except Exception as e:
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


@app.post("/extract-keywords")
async def extract_keywords(payload: TextPayload):
    """Analyzes text and isolates matches against keywords stored in PostgreSQL."""
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
