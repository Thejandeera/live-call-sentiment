# Live Call Sentiment Analysis & Real-Time Monitoring System

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.95%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![MongoDB Atlas](https://img.shields.io/badge/MongoDB-Atlas-47A248.svg)](https://www.mongodb.com/atlas)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0%2B-EE4C2C.svg)](https://pytorch.org/)
[![Transformers](https://img.shields.io/badge/Transformers-4.30%2B-orange.svg)](https://huggingface.co/transformers/)
[![spaCy](https://img.shields.io/badge/spaCy-3.5%2B-09A3D5.svg)](https://spacy.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A high-throughput, decoupled AI microservices platform designed for real-time live call monitoring, sentiment escalation detection, dynamic MongoDB keyword management, and contact center conversational intelligence.

---

## 📖 Table of Contents

- [1. Overview & Core Value Proposition](#1-overview--core-value-proposition)
- [2. System Architecture Summary](#2-system-architecture-summary)
- [3. Scoring Engine Logic & Mathematical Formulas](#3-scoring-engine-logic--mathematical-formulas)
- [4. Package Ecosystem Across Microservices](#4-package-ecosystem-across-microservices)
- [5. Environment Variables & Configuration (`.env`)](#5-environment-variables--configuration-env)
- [6. Installation & Quickstart Guide](#6-installation--quickstart-guide)
- [7. API Reference & Data Contracts](#7-api-reference--data-contracts)
- [8. Testing & Verification](#8-testing--verification)
- [9. Architecture Deep-Dive Reference](#9-architecture-deep-dive-reference)

---

## 1. Overview & Core Value Proposition

In customer support and telecommunications, identifying angry or frustrated callers in real time allows supervisors to proactively intervene, de-escalate crises, and reduce customer churn. 

Traditional Exponential Moving Average (EMA) and basic lexicon-based systems suffer from critical defects:
1. **Recency Bias**: A caller furious for 40 turns who politely says *"Okay, thank you, bye"* at turn 41 resets the score, hiding customer friction from supervisor audits.
2. **Score Reversal Paradox**: Low-confidence negative predictions pull already negative scores upward.
3. **Neutral Decay Collapse**: 60–70% of call center sentences are neutral facts (e.g., account numbers). Standard EMA decays the negative score back to zero in 2 turns.
4. **Rhetorical Question False Positives**: Panicked questions (*"Are you out of your mind?!"*) get misclassified as positive curiosity.

This system solves these issues through a **Standardized Confidence-Scaled Dual-Horizon Scoring Engine** paired with deep-learning NLP microservices and persistent **MongoDB Atlas** keyword phrase tracking.

---

## 2. System Architecture Summary

The platform is structured into four independent, decoupled microservices:

```text
live-call-sentiment/
├── api-gateway/            # Central orchestrator, connection pool & proxy (Port 8000)
├── service-phrase/         # spaCy keyword extraction & MongoDB Atlas sync (Port 8002)
├── service-sentiment/      # RoBERTa 28-emotion classification engine (Port 8003)
├── service-score/          # Dual-Horizon mathematical scoring engine (Port 8004)
├── .env.example            # Environment configuration template
├── .env                    # Local runtime environment
├── architecture.md         # Full system architecture & Mermaid diagrams
├── requests.http           # REST API test suite
├── start_services.bat      # Windows batch startup script
└── README.md               # Primary project documentation
```

For full sequence diagrams, state machines, and component topologies, see [`architecture.md`](./architecture.md).

---

## 3. Scoring Engine Logic & Mathematical Formulas

The sentiment scoring engine (`service-score`) calculates a real-time sentiment score $S \in [-100.0, +100.0]$ across every conversational turn.

### 3.1 Emotion Severity Weight Matrix ($W_{\text{destination}}$)

Every detected emotion maps to a standardized severity weight:

| Category | Emotion Label | Raw Weight ($W_{\text{raw}}$) | Notes / Behavior |
| :--- | :--- | :--- | :--- |
| **High Positive** | `gratitude` | $+100.0$ | Complete resolution / appreciation |
| | `relief` | $+95.0$ | Anxiety resolved |
| | `approval` | $+85.0$ | Customer agrees with proposal |
| | `optimism`, `caring`, `joy` | $+80.0 \dots +70.0$ | Positive customer tone |
| | `admiration`, `excitement` | $+65.0 \dots +60.0$ | High engagement |
| **Mild Positive** | `amusement`, `pride`, `love`, `desire` | $+45.0 \dots +25.0$ | Pleasant interaction |
| **Neutral / Inquiry** | `surprise` | $0.0$ | Neutral baseline for support inquiries |
| | `curiosity` | $-10.0$ | Re-weighted to mild friction for support calls |
| | `neutral` | $0.0$ | Informational baseline |
| **Mild Negative** | `realization`, `confusion` | $-15.0 \dots -25.0$ | Information mismatch |
| | `embarrassment`, `nervousness` | $-35.0 \dots -45.0$ | Customer unease |
| | `remorse`, `fear` | $-55.0 \dots -65.0$ | Escalation impending |
| **Severe Negative** | `annoyance`, `disapproval` | $-70.0 \dots -75.0$ | Friction building |
| | `disappointment`, `sadness` | $-80.0 \dots -85.0$ | Customer distress |
| | `grief`, `disgust` | $-90.0 \dots -95.0$ | Severe hostility |
| | `anger` | $-100.0$ | Maximum hostility / churn risk |

---

### 3.2 Confidence-Scaled Step Size ($\alpha_{\text{effective}}$)

To eliminate the **Score Reversal Paradox**, confidence ($C \in [0.0, 1.0]$) scales the *step size* ($\alpha$), while the target destination remains fixed at $W_{\text{destination}}$:

$$\text{confidence\_weight} = \max(0.40, C)$$

$$\alpha_{\text{effective}} = \text{BASE\_ALPHA} \times D(S) \times \text{confidence\_weight} \quad (\text{where } \text{BASE\_ALPHA} = 0.30)$$

$$S_{\text{new}} = (\alpha_{\text{effective}} \times W_{\text{destination}}) + ((1.0 - \alpha_{\text{effective}}) \times S_{\text{current}})$$

---

### 3.3 Continuous Logistic Saturation Resistance ($D(S)$)

Replaces rigid step thresholds with a smooth continuous friction function:

$$D(S) = \frac{1}{1 + \left(\frac{|S_{\text{current}}|}{\text{SATURATION\_SCALE}}\right)^2}$$

- **Negative Escalation Scale**: $\text{SATURATION\_SCALE} = 100.0$ (allows deep natural progression into $-65.0 \to -95.0$).
- **Positive Climbing Scale**: $\text{POSITIVE\_SATURATION\_SCALE} = 150.0$ (smooth climbing into $+80.0 \to +100.0$).

---

### 3.4 Mild Negative Non-Relief Rule

When a call is already in severe crisis ($S_{\text{current}} \le -65.0$), a milder negative emotion (e.g. `fear` $-65$, `annoyance` $-70$, `curiosity` $-10$) must **never** pull the score upward:

$$\text{If } S_{\text{current}} \le -65.0 \text{ and } W_{\text{destination}} < 0 \text{ and } W_{\text{destination}} > S_{\text{current}} \implies \alpha_{\text{effective}} = 0.01$$

---

### 3.5 Crisis Neutral Clamping & Neutral Inertia

- **Standard Neutral Inertia**: Neutral statements decay by only $3\text{--}4\%$ per turn ($\alpha_{\text{neutral}} = 0.04$).
- **Crisis Neutral Clamping**: If $S_{\text{current}} \le -65.0$, factual/neutral statements (e.g., providing an address or ID) decay by only $0.5\%$ ($\alpha = 0.005$), preserving crisis context.

---

### 3.6 Sustained Crisis Duration Momentum

When severe friction ($S \le -65.0$ and $W \le -50.0$) persists across multiple turns ($t > 10$), an incremental duration penalty compounds the score:

$$S_{\text{new}} \leftarrow S_{\text{new}} - \min\left(0.60, \frac{t}{100} \times 0.60\right)$$

---

### 3.7 Fast Recovery for Genuine Resolution

When transitioning from negative to positive ($S_{\text{current}} < 0 \land W_{\text{destination}} > 0$), dampening is bypassed ($D = 1.0$) for 12 genuine resolution emotions (`gratitude`, `relief`, `approval`, `joy`, `optimism`, `caring`, `admiration`, `excitement`, `amusement`, `pride`, `love`, `desire`).

---

### 3.8 Dual-Horizon Call Health Aggregation ($S_{\text{health}}$)

The system maintains two distinct score perspectives:
1. **Instantaneous Live Score ($S_{\text{live}}$)**: Immediate turn-by-turn state.
2. **Cumulative Session Average ($\overline{S}_{\text{session}}$)**: Running mean of all turn scores.
3. **Session Call Health Score ($S_{\text{health}}$)**:
   $$S_{\text{health}} = 0.70 \times \overline{S}_{\text{session}} + 0.30 \times S_{\text{live}}$$

- **Escalation Alert**: Fired whenever $S_{\text{live}} \le -65.0$ OR $S_{\text{health}} \le -65.0$.

---

## 4. Package Ecosystem Across Microservices

Every dependency in this repository has been selected for high performance, reliability, and low overhead:

### 4.1 API Gateway (`api-gateway/requirements.txt`)
- **`fastapi>=0.95.0`**: High-speed asynchronous REST API framework with native OpenAPI/Swagger docs.
- **`uvicorn>=0.21.0`**: Production-grade ASGI server implementation.
- **`httpx>=0.24.0`**: Next-generation async HTTP client with connection pooling and HTTP/2 support.
- **`pydantic>=1.10.0`**: Runtime payload schema validation and serialization.
- **`python-dotenv>=1.0.0`**: Automatic `.env` loading across runtime environments.

### 4.2 Phrase Extraction Service (`service-phrase/requirements.txt`)
- **`spacy>=3.5.0`**: Industrial NLP library with `PhraseMatcher` for instant multi-token keyword isolation.
- **`pymongo>=4.6.0`**: Official MongoDB Python driver for Atlas SRV connection and performant CRUD queries.
- **`dnspython>=2.4.0`**: DNS SRV protocol resolution required for MongoDB Atlas cluster connection strings.
- **`pydantic>=1.10.0`**: Request/response contracts.
- **`python-dotenv>=1.0.0`**: Dynamic database and service configuration.

### 4.3 Sentiment Service (`service-sentiment/requirements.txt`)
- **`torch>=2.0.0`**: PyTorch backend with optimized `torch.inference_mode()` tensor execution.
- **`transformers>=4.30.0`**: Hugging Face pipeline for `SamLowe/roberta-base-go_emotions`.
- **`pydantic>=1.10.0`**: Batch payload structuring.
- **`python-dotenv>=1.0.0`**: Dynamic model identification.

### 4.4 Score Service (`service-score/requirements.txt`)
- **`fastapi>=0.95.0`**: Sub-millisecond mathematical calculation endpoint.
- **`uvicorn>=0.21.0`**: ASGI server.
- **`pydantic>=1.10.0`**: Scoring request and response data contracts.
- **`python-dotenv>=1.0.0`**: Configuration management.

---

## 5. Environment Variables & Configuration (`.env`)

All configurable URLs, ports, CORS origins, database connection strings, and thresholds are managed via `.env`. A complete template is provided in [`.env.example`](./.env.example):

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| **`API_GATEWAY_HOST`** | `0.0.0.0` | Gateway host bind address. |
| **`API_GATEWAY_PORT`** | `8000` | Gateway port. |
| **`CORS_ORIGINS`** | `http://localhost:3000,http://127.0.0.1:3000` | Allowed CORS origins (comma-separated). |
| **`PHRASE_SERVICE_URL`** | `http://localhost:8002/extract-keywords` | URL to Phrase Service endpoint. |
| **`SENTIMENT_SERVICE_URL`**| `http://localhost:8003/analyze-sentiment` | URL to Sentiment Service endpoint. |
| **`SCORE_SERVICE_URL`** | `http://localhost:8004/calculate-score` | URL to Score Service endpoint. |
| **`PHRASE_SERVICE_HOST`**| `0.0.0.0` | Phrase service host bind address. |
| **`PHRASE_SERVICE_PORT`**| `8002` | Phrase service port. |
| **`MONGODB_URI`** | `mongodb+srv://thejaninfo_db_user:...` | MongoDB Atlas SRV connection string. |
| **`MONGODB_DB_NAME`** | `live_call_sentiment` | MongoDB database name. |
| **`MONGODB_COLLECTION_NAME`**| `keywords` | MongoDB collection storing monitored phrases. |
| **`SPACY_MODEL`** | `en_core_web_sm` | spaCy model used for phrase matching. |
| **`SENTIMENT_SERVICE_HOST`**| `0.0.0.0` | Sentiment service host bind address. |
| **`SENTIMENT_SERVICE_PORT`**| `8003` | Sentiment service port. |
| **`SENTIMENT_MODEL_NAME`**| `SamLowe/roberta-base-go_emotions` | Hugging Face emotion classifier repository. |
| **`SCORE_SERVICE_HOST`** | `0.0.0.0` | Score service host bind address. |
| **`SCORE_SERVICE_PORT`** | `8004` | Score service port. |
| **`ESCALATION_THRESHOLD`**| `-65.0` | Alert threshold triggering supervisor escalation. |

---

## 6. Installation & Quickstart Guide

### 6.1 Prerequisites
- Python 3.10, 3.11, 3.12, 3.13, or 3.14
- MongoDB Atlas cluster or local MongoDB instance (`mongodb://localhost:27017`)
- Git

### 6.2 Setup Python Environment

From the repository root:

```powershell
# 1. Create and activate Python virtual environment (Windows PowerShell)
python -m venv venv
.\venv\Scripts\activate

# 2. Install dependencies for all 4 microservices
pip install -r api-gateway/requirements.txt
pip install -r service-phrase/requirements.txt
pip install -r service-sentiment/requirements.txt
pip install -r service-score/requirements.txt

# 3. Download spaCy English language model
python -m spacy download en_core_web_sm

# 4. Copy environment configuration and configure your MongoDB password
copy .env.example .env
```

### 6.3 Launch All Microservices

Run the provided Windows startup script:

```cmd
.\start_services.bat
```

Or start each microservice manually in separate terminal tabs:

```bash
# Terminal 1: API Gateway (Port 8000)
cd api-gateway && uvicorn main:app --port 8000 --reload

# Terminal 2: Phrase Extraction Service (Port 8002)
cd service-phrase && uvicorn main:app --port 8002 --reload

# Terminal 3: Sentiment & Emotion Service (Port 8003)
cd service-sentiment && uvicorn main:app --port 8003 --reload

# Terminal 4: Live Sentiment Score Service (Port 8004)
cd service-score && uvicorn main:app --port 8004 --reload
```

---

## 7. API Reference & Data Contracts

### 7.1 Primary Ingress: `POST /api/v1/process-message`
- **Host**: `http://localhost:8000`
- **Description**: Main ingress called by client UI or ASR audio pipeline for each conversational turn.

#### Request JSON:
```json
{
  "text": "I am extremely unhappy and I want to cancel my account immediately.",
  "speaker": "caller",
  "previous_score": -45.0,
  "turn_count": 5,
  "session_avg_score": -40.0,
  "peak_negativity": -50.0
}
```

#### Response JSON:
```json
{
  "status": "success",
  "processing_time_ms": 18.42,
  "detected_issues": [
    {
      "isolated_sentence": "I am extremely unhappy and I want to cancel my account immediately.",
      "detected_keywords": [
        {
          "keyword": "cancel account"
        }
      ],
      "emotion": "anger",
      "confidence": 0.9241,
      "sentiment_category": "negative",
      "final_score": -64.82,
      "score": -64.82,
      "live_score": -64.82
    }
  ]
}
```

---

### 7.2 Keyword Management Endpoints (MongoDB)

#### Add Keyword(s): `POST /api/v1/keywords`
- **Request (Single Keyword)**:
  ```json
  {
    "keyword": "cancel account"
  }
  ```
- **Request (Batch Keywords)**:
  ```json
  {
    "keywords": [
      "talk to supervisor",
      "demand refund",
      "terrible service"
    ]
  }
  ```
- **Response (201 Created)**:
  ```json
  {
    "status": "success",
    "message": "Successfully processed 3 keyword(s). 3 new keyword(s) stored.",
    "added_count": 3,
    "processed_keywords": ["talk to supervisor", "demand refund", "terrible service"]
  }
  ```

#### Get All Keywords: `GET /api/v1/keywords`
- **Response (200 OK)**:
  ```json
  {
    "status": "success",
    "count": 3,
    "keywords": [
      { "keyword": "cancel account" },
      { "keyword": "demand refund" },
      { "keyword": "talk to supervisor" }
    ]
  }
  ```

#### Delete Keyword: `DELETE /api/v1/keywords/{keyword}`
- **Response (200 OK)**:
  ```json
  {
    "status": "success",
    "message": "Keyword 'cancel account' successfully removed.",
    "keyword": "cancel account"
  }
  ```

---

### 7.3 Microservice Endpoints Overview

| Service | Endpoint | Method | Purpose |
| :--- | :--- | :--- | :--- |
| **API Gateway** | `/health` | `GET` | Service mesh health & config status |
| | `/api/v1/process-message` | `POST` | Orchestrated end-to-end processing |
| | `/api/v1/keywords` | `POST` | Add monitored keywords to MongoDB |
| | `/api/v1/keywords` | `GET` | Retrieve all keywords from MongoDB |
| | `/api/v1/keywords/{keyword}` | `DELETE`| Remove a keyword from MongoDB |
| **Phrase Service** | `/health` | `GET` | Health check & MongoDB connection status |
| | `/keywords` | `POST` | Add keywords to MongoDB |
| | `/keywords` | `GET` | Retrieve keywords from MongoDB |
| | `/keywords/{keyword}` | `DELETE`| Delete keyword from MongoDB |
| | `/extract-keywords` | `POST` | Match text against MongoDB keywords |
| **Sentiment Service** | `/health` | `GET` | Model load status |
| | `/analyze-sentiment` | `POST` | Single sentence emotion classification |
| | `/analyze-sentiment-batch` | `POST` | Multi-sentence batch classification |
| **Score Service** | `/health` | `GET` | Math engine parameters |
| | `/calculate-score` | `POST` | Standardized Dual-Horizon score calculation |

---

## 8. Testing & Verification

A complete set of test requests is pre-configured in [`requests.http`](./requests.http). You can execute these tests directly in VS Code / Antigravity using the REST Client extension or with `curl`:

```bash
# Test API Gateway Health
curl http://localhost:8000/health

# Add Keyword to MongoDB
curl -X POST http://localhost:8000/api/v1/keywords \
  -H "Content-Type: application/json" \
  -d "{\"keyword\": \"cancel subscription\"}"

# Retrieve All Keywords
curl http://localhost:8000/api/v1/keywords

# Process Test Turn with Keyword Detection
curl -X POST http://localhost:8000/api/v1/process-message \
  -H "Content-Type: application/json" \
  -d "{\"text\": \"I want to cancel my subscription right now!\", \"speaker\": \"caller\", \"previous_score\": 0.0}"
```

---

## 9. Architecture Deep-Dive Reference

For the comprehensive technical design specification including:
- High-level topology diagram (`graph TB`)
- End-to-end sequence diagram (`sequenceDiagram`)
- State machine lifecycle diagram (`stateDiagram-v2`)
- Fault tolerance & resilience fallback matrix
- Production containerization & scaling architecture

👉 **Read [`architecture.md`](./architecture.md)**
