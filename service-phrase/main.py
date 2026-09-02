import os
import sys
import subprocess
from pathlib import Path
from typing import List, Optional, Union
from contextlib import contextmanager
from datetime import datetime, timezone
import spacy
from spacy.matcher import PhraseMatcher
from fastapi import FastAPI, HTTPException, status, Request
from pydantic import BaseModel
import psycopg2
from psycopg2 import pool
from psycopg2.extras import DictCursor
from dotenv import load_dotenv
from audit_logger import AuditLoggingMiddleware

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

from fastapi.responses import JSONResponse

class CriticalError(Exception):
    pass

app = FastAPI(title="Keyword & Phrase Detection Service (PostgreSQL)")

@app.exception_handler(CriticalError)
async def critical_error_handler(request: Request, exc: CriticalError):
    print(f"CRITICAL ERROR: {exc}. Terminating service...")
    os._exit(1)

app.add_middleware(AuditLoggingMiddleware, service_name="service-phrase")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "callIntelligence")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_TABLE = os.getenv("POSTGRES_TABLE", "call_admin_keywords")
POSTGRES_URI = os.getenv("POSTGRES_URI")
SPACY_MODEL = os.getenv("SPACY_MODEL", "en_core_web_sm")

in_memory_keywords = {}

class KeywordItem(BaseModel):
    keyword: str
    category: Optional[str] = None

class KeywordPayload(BaseModel):
    keyword: Optional[str] = None
    category: Optional[str] = None
    keywords: Optional[List[Union[str, KeywordItem]]] = None

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
                    category VARCHAR(255) DEFAULT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
                """
                cur.execute(create_table_sql)
                cur.execute(f"ALTER TABLE {POSTGRES_TABLE} ADD COLUMN IF NOT EXISTS category VARCHAR(255) DEFAULT NULL;")
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{POSTGRES_TABLE}_category ON {POSTGRES_TABLE} (category);")
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


def fetch_stored_keywords() -> List[dict]:
    """Retrieves all active keywords from PostgreSQL or in-memory fallback."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT keyword, category FROM {POSTGRES_TABLE} ORDER BY keyword ASC;")
                rows = cur.fetchall()
                return [{"keyword": row[0], "category": row[1]} for row in rows if row and row[0]]
    except Exception as e:
        print(f"[Phrase Service] Fallback retrieving keywords: {e}")
        return [{"keyword": kw, "category": cat} for kw, cat in sorted(in_memory_keywords.items())]


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
    items_to_process: List[dict] = []

   
    if payload.keyword and payload.keyword.strip():
        kw_clean = payload.keyword.strip().lower()
        cat_clean = payload.category.strip() if (payload.category and payload.category.strip()) else None
        items_to_process.append({"keyword": kw_clean, "category": cat_clean})

    
    if payload.keywords:
        for item in payload.keywords:
            if isinstance(item, str):
                if item.strip():
                    cat_clean = payload.category.strip() if (payload.category and payload.category.strip()) else None
                    items_to_process.append({"keyword": item.strip().lower(), "category": cat_clean})
            elif isinstance(item, KeywordItem) or (isinstance(item, dict) and "keyword" in item):
                item_dict = item.dict() if hasattr(item, "dict") else item
                kw = item_dict.get("keyword")
                if kw and kw.strip():
                    raw_cat = item_dict.get("category")
                    cat_clean = raw_cat.strip() if (raw_cat and isinstance(raw_cat, str) and raw_cat.strip()) else (payload.category.strip() if (payload.category and payload.category.strip()) else None)
                    items_to_process.append({"keyword": kw.strip().lower(), "category": cat_clean})

    if not items_to_process:
        raise HTTPException(status_code=400, detail="No valid keyword provided. Supply 'keyword' or 'keywords'.")

 
    deduped: dict = {}
    for item in items_to_process:
        kw = item["keyword"]
        cat = item["category"]
        if kw not in deduped or cat is not None:
            deduped[kw] = cat

    added_count = 0

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for kw, cat in deduped.items():
                    insert_sql = f"""
                    INSERT INTO {POSTGRES_TABLE} (keyword, category)
                    VALUES (%s, %s)
                    ON CONFLICT (keyword) DO UPDATE
                    SET category = COALESCE(EXCLUDED.category, {POSTGRES_TABLE}.category)
                    RETURNING id;
                    """
                    cur.execute(insert_sql, (kw, cat))
                    res = cur.fetchone()
                    if res is not None:
                        added_count += 1
            conn.commit()
    except Exception as e:
        for kw, cat in deduped.items():
            if kw not in in_memory_keywords:
                in_memory_keywords[kw] = cat
                added_count += 1
            elif cat is not None:
                in_memory_keywords[kw] = cat

    processed_keywords = [{"keyword": kw, "category": cat} for kw, cat in deduped.items()]

    return {
        "status": "success",
        "message": f"Successfully processed {len(deduped)} keyword(s). {added_count} new or updated keyword(s) stored.",
        "added_count": added_count,
        "processed_keywords": processed_keywords
    }


@app.get("/admin-keywords")
async def get_keywords():
    """Returns all monitored keywords from PostgreSQL."""
    keywords = fetch_stored_keywords()
    return {
        "status": "success",
        "count": len(keywords),
        "keywords": keywords
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
            del in_memory_keywords[clean_kw]
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

    global nlp
    if nlp is None:
        try:
            nlp = spacy.load(SPACY_MODEL)
        except Exception:
            return {"matches": [], "keywords": []}

    keyword_category_map = {item["keyword"].lower(): item.get("category") for item in stored_keywords if item.get("keyword")}
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    for kw in keyword_category_map:
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
                "keyword": matched_span.text,
                "category": keyword_category_map.get(kw_text)
            })
            seen.add(kw_text)

    return {
        "matches": detected_keywords,
        "keywords": detected_keywords
    }
