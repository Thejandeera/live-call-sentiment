# Live Call Sentiment Analysis & Real-Time Monitoring System

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.95%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17%2B-336791.svg)](https://www.postgresql.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0%2B-EE4C2C.svg)](https://pytorch.org/)
[![Transformers](https://img.shields.io/badge/Transformers-4.30%2B-orange.svg)](https://huggingface.co/transformers/)
[![spaCy](https://img.shields.io/badge/spaCy-3.5%2B-09A3D5.svg)](https://spacy.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A high-throughput, decoupled AI microservices platform designed for real-time live call monitoring, sentiment escalation detection, dynamic PostgreSQL keyword management, and contact center conversational intelligence.

---

## Table of Contents

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

This system solves these issues through a **Standardized Confidence-Scaled Dual-Horizon Scoring Engine** paired with deep-learning NLP microservices and persistent **PostgreSQL** (`callIntelligence` database, `call_admin_keywords` table) keyword phrase tracking.

---

## 2. System Architecture Summary

The platform is structured into four independent, decoupled microservices:

```text
live-call-sentiment/
├── api-gateway/            # Central orchestrator, connection pool & proxy (Port 8000)
├── service-phrase/         # spaCy keyword extraction & PostgreSQL sync (Port 8002)
├── service-sentiment/      # RoBERTa 28-emotion classification engine (Port 8003)
├── service-score/          # Dual-Horizon mathematical scoring engine (Port 8004)
├── .env.example            # Environment configuration template
├── .env                    # Local runtime environment
├── architecture.md         # Full system architecture specification
├── deployment_plan.md      # Local Docker deployment guide
├── cloud-deployment-plan.md# AWS Cloud deployment guide (ECR + ECS Fargate)
├── requests.http           # REST API test suite
├── start_services.bat      # Windows batch startup script
└── README.md               # Primary project documentation
```

For full diagrams, state machines, and component topologies, see [`architecture.md`](./architecture.md). For local containerization, see [`deployment_plan.md`](./deployment_plan.md). For AWS production deployment, see [`cloud-deployment-plan.md`](./cloud-deployment-plan.md).

---

## 3. Scoring Engine Logic & Mathematical Formulas

The sentiment scoring engine (`service-score`) calculates a real-time sentiment score `S` in the range `[-100.0, +100.0]` across every conversational turn.

### 3.1 Emotion Severity Weight Matrix 

Every detected emotion maps to a standardized severity weight:

| Category | Emotion Label | Raw Weight | Notes / Behavior |
| :--- | :--- | :--- | :--- |
| **High Positive** | `gratitude` | `+100.0` | Complete resolution / appreciation |
| | `relief` | `+95.0` | Anxiety resolved |
| | `approval` | `+85.0` | Customer agrees with proposal |
| | `optimism`, `caring`, `joy` | `+80.0` to `+70.0` | Positive customer tone |
| | `admiration`, `excitement` | `+65.0` to `+60.0` | High engagement |
| **Mild Positive** | `amusement`, `pride`, `love`, `desire` | `+45.0` to `+25.0` | Pleasant interaction |
| **Neutral / Inquiry** | `surprise` | `0.0` | Neutral baseline for support inquiries |
| | `curiosity` | `-10.0` | Re-weighted to mild friction for support calls |
| | `neutral` | `0.0` | Informational baseline |
| **Mild Negative** | `realization`, `confusion` | `-15.0` to `-25.0` | Information mismatch |
| | `embarrassment`, `nervousness` | `-35.0` to `-45.0` | Customer unease |
| | `remorse`, `fear` | `-55.0` to `-65.0` | Escalation impending |
| **Severe Negative** | `annoyance`, `disapproval` | `-70.0` to `-75.0` | Friction building |
| | `disappointment`, `sadness` | `-80.0` to `-85.0` | Customer distress |
| | `grief`, `disgust` | `-90.0` to `-95.0` | Severe hostility |
| | `anger` | `-100.0` | Maximum hostility / churn risk |

---

### 3.2 Confidence-Scaled Step Size

To eliminate the **Score Reversal Paradox**, confidence (`C` in `[0.0, 1.0]`) scales the step size (`alpha`), while the target destination remains fixed at `W_destination`:

```python
confidence_weight = max(0.40, confidence)
alpha_effective = BASE_ALPHA * dampening_factor * confidence_weight  # where BASE_ALPHA = 0.30
S_new = (alpha_effective * W_destination) + ((1.0 - alpha_effective) * S_current)
```

---

### 3.3 Continuous Logistic Saturation Resistance (`D(S)`)

Replaces rigid step thresholds with a smooth continuous friction function:

```python
dampening_factor = 1.0 / (1.0 + (abs(S_current) / SATURATION_SCALE) ** 2)
```

- **Negative Escalation Scale**: `SATURATION_SCALE = 100.0` (allows deep natural progression into `-65.0` to `-95.0`).
- **Positive Climbing Scale**: `POSITIVE_SATURATION_SCALE = 150.0` (smooth climbing into `+80.0` to `+100.0`).

---

### 3.4 Mild Negative Non-Relief Rule

When a call is already in severe crisis (`S_current <= -65.0`), a milder negative emotion (e.g. `fear` -65, `annoyance` -70, `curiosity` -10) must **never** pull the score upward:

```python
if S_current <= -65.0 and W_destination < 0 and W_destination > S_current:
    alpha_effective = 0.01
```

---

### 3.5 Crisis Neutral Clamping & Neutral Inertia

- **Standard Neutral Inertia**: Neutral statements decay by only 3% to 4% per turn (`alpha_neutral = 0.04`).
- **Crisis Neutral Clamping**: If `S_current <= -65.0`, factual/neutral statements (e.g., providing an address or ID) decay by only 0.5% (`alpha = 0.005`), preserving crisis context.

---

### 3.6 Sustained Crisis Duration Momentum

When severe friction (`S <= -65.0` and `W <= -50.0`) persists across multiple turns (`turn_count > 10`), an incremental duration penalty compounds the score:

```python
if S_current <= -65.0 and W_destination <= -50.0 and turn_count > 10:
    duration_penalty = min(0.60, (turn_count / 100.0) * 0.60)
    S_new = S_new - duration_penalty
```

---

### 3.7 Fast Recovery for Genuine Resolution

When transitioning from negative to positive (`S_current < 0` and `W_destination > 0`), dampening is bypassed (`dampening_factor = 1.0`) for 12 genuine resolution emotions:
`gratitude`, `relief`, `approval`, `joy`, `optimism`, `caring`, `admiration`, `excitement`, `amusement`, `pride`, `love`, `desire`.

---

### 3.8 Dual-Horizon Call Health Aggregation (`S_health`)

The system maintains two distinct score perspectives:
1. **Instantaneous Live Score (`S_live`)**: Immediate turn-by-turn state.
2. **Cumulative Session Average (`S_session_avg`)**: Running mean of all turn scores.
3. **Session Call Health Score (`S_health`)**:
   ```python
   S_health = (0.70 * S_session_avg) + (0.30 * S_live)
   ```

- **Escalation Alert**: Fired whenever `S_live <= -65.0` OR `S_health <= -65.0`.

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
- **`psycopg2-binary>=2.9.9`**: Production PostgreSQL database adapter supporting connection pooling and parameterized queries.
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

All configurable URLs, ports, CORS origins, PostgreSQL database credentials, and thresholds are managed via `.env`. A complete template is provided in [`.env.example`](./.env.example):

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
| **`POSTGRES_HOST`** | `localhost` | PostgreSQL server hostname / IP. |
| **`POSTGRES_PORT`** | `5432` | PostgreSQL port. |
| **`POSTGRES_DB`** | `callIntelligence` | PostgreSQL database name. |
| **`POSTGRES_USER`** | `postgres` | PostgreSQL username. |
| **`POSTGRES_PASSWORD`** | `postgres` | PostgreSQL password. |
| **`POSTGRES_TABLE`** | `call_admin_keywords` | Table storing monitored phrases. |
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
- PostgreSQL 14+ (e.g., PostgreSQL 17 with `callIntelligence` database)
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

# 4. Copy environment configuration and configure your PostgreSQL password
copy .env.example .env
```

### 6.3 Launch All Microservices Locally

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

### 6.4 Docker Deployment (Without Docker Compose)

Containers are configured with **zero hardcoded environment variables**. All configurations are injected dynamically at runtime via `--env-file .env` (locally) or AWS Secrets Manager / Parameter Store (production).

#### 1. Create Docker Network & Build Images
```bash
# Create shared bridge network for container DNS resolution
docker network create sentiment-network

# Build microservice images
docker build -t api-gateway ./api-gateway
docker build -t service-phrase ./service-phrase
docker build -t service-sentiment ./service-sentiment
docker build -t service-score ./service-score
```

#### 2. Start PostgreSQL Container
```bash
docker run -d \
  --name sentiment_postgres \
  --network sentiment-network \
  -p 5432:5432 \
  -e POSTGRES_DB=callIntelligence \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -v pgdata:/var/lib/postgresql/data \
  postgres:17-alpine
```

#### 3. Run Microservices (with Host Log Sync `-v`)
```bash
# 1. Phrase Service (Port 8002)
docker run -d --name service_phrase --network sentiment-network -p 8002:8002 \
  --env-file .env -e LOG_DIR=/app/logs -e POSTGRES_HOST=sentiment_postgres -e POSTGRES_PORT=5432 -e POSTGRES_PASSWORD=postgres \
  -v "${PWD}/logs:/app/logs" service-phrase

# 2. Sentiment Service (Port 8003)
docker run -d --name service_sentiment --network sentiment-network -p 8003:8003 \
  --env-file .env -e LOG_DIR=/app/logs \
  -v "${PWD}/logs:/app/logs" service-sentiment

# 3. Score Service (Port 8004)
docker run -d --name service_score --network sentiment-network -p 8004:8004 \
  --env-file .env -e LOG_DIR=/app/logs \
  -v "${PWD}/logs:/app/logs" service-score

# 4. API Gateway (Port 8000)
docker run -d --name api_gateway --network sentiment-network -p 8000:8000 \
  --env-file .env -e LOG_DIR=/app/logs \
  -e PHRASE_SERVICE_URL=http://service_phrase:8002/extract-keywords \
  -e SENTIMENT_SERVICE_URL=http://service_sentiment:8003/analyze-sentiment \
  -e SCORE_SERVICE_URL=http://service_score:8004/calculate-score \
  -v "${PWD}/logs:/app/logs" api-gateway
```

> [!NOTE]
> The `-v "${PWD}/logs:/app/logs"` bind mount and `-e LOG_DIR=/app/logs` flag ensure audit logs written inside containers sync directly to your local `logs/` folder in real-time. For full AWS production deployment with AWS Secrets Manager, see [`deployment_plan.md`](./deployment_plan.md).

---

## 7. API Reference & Data Contracts

### 7.1 Primary Ingress: `POST /api/v1/process-text`
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

### 7.2 Keyword Management Endpoints (PostgreSQL)

#### Add Keyword(s): `POST /api/v1/add-keyword`
- **Request (Single Keyword with Category)**:
  ```json
  {
    "keyword": "cancel account",
    "category": "churn"
  }
  ```
- **Request (Single Keyword without Category - Defaults to `null`)**:
  ```json
  {
    "keyword": "escalate to manager"
  }
  ```
- **Request (Batch Keywords with Specific Categories)**:
  ```json
  {
    "keywords": [
      { "keyword": "talk to supervisor", "category": "escalation" },
      { "keyword": "demand refund", "category": "billing" },
      { "keyword": "terrible service" }
    ]
  }
  ```
- **Response (201 Created)**:
  ```json
  {
    "status": "success",
    "message": "Successfully processed 3 keyword(s). 3 new or updated keyword(s) stored.",
    "added_count": 3,
    "processed_keywords": [
      { "keyword": "talk to supervisor", "category": "escalation" },
      { "keyword": "demand refund", "category": "billing" },
      { "keyword": "terrible service", "category": null }
    ]
  }
  ```

#### Get All Keywords: `GET /api/v1/admin-keywords`
- **Response (200 OK)**:
  ```json
  {
    "status": "success",
    "count": 3,
    "keywords": [
      { "keyword": "cancel account", "category": "churn" },
      { "keyword": "demand refund", "category": "billing" },
      { "keyword": "talk to supervisor", "category": "escalation" }
    ]
  }
  ```

#### Delete Keyword: `DELETE /api/v1/delete-keyword/{keyword}`
- **Response (200 OK)**:
  ```json
  {
    "status": "success",
    "message": "Keyword 'cancel account' successfully removed.",
    "keyword": "cancel account"
  }
  ```

#### Database Migration
For existing deployments, run the migration script located in [`migrations/001_add_category_to_call_admin_keywords.sql`](./migrations/001_add_category_to_call_admin_keywords.sql):
```bash
psql -U postgres -d callIntelligence -f migrations/001_add_category_to_call_admin_keywords.sql
```

---

### 7.3 Microservice Endpoints Overview

| Service | Endpoint | Method | Purpose |
| :--- | :--- | :--- | :--- |
| **API Gateway** | `/health` | `GET` | Service mesh health & config status |
| | `/api/v1/process-text` | `POST` | Orchestrated end-to-end processing |
| | `/api/v1/add-keyword` | `POST` | Add monitored keywords to PostgreSQL |
| | `/api/v1/admin-keywords` | `GET` | Retrieve all keywords from PostgreSQL |
| | `/api/v1/delete-keyword/{keyword}` | `DELETE`| Remove a keyword from PostgreSQL |
| **Phrase Service** | `/health` | `GET` | Health check & PostgreSQL connection status |
| | `/add-keyword` | `POST` | Add keywords to PostgreSQL |
| | `/admin-keywords` | `GET` | Retrieve keywords from PostgreSQL |
| | `/delete-keyword/{keyword}` | `DELETE`| Delete keyword from PostgreSQL |
| | `/extract-keywords` | `POST` | Match text against PostgreSQL keywords |
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

# Add Keyword to PostgreSQL
curl -X POST http://localhost:8000/api/v1/add-keyword \
  -H "Content-Type: application/json" \
  -d "{\"keyword\": \"cancel subscription\"}"

# Retrieve All Keywords
curl http://localhost:8000/api/v1/admin-keywords

# Process Test Turn with Keyword Detection
curl -X POST http://localhost:8000/api/v1/process-text \
  -H "Content-Type: application/json" \
  -d "{\"text\": \"I want to cancel my subscription right now!\", \"speaker\": \"caller\", \"previous_score\": 0.0}"
```

---

## 9. Architecture Deep-Dive Reference

For the comprehensive technical design specification including:
- High-level topology diagram
- Microservice component breakdown
- End-to-end data flow sequence
- Scoring engine state machine & trajectory lifecycle
- Fault tolerance & resilience fallback matrix
- Production containerization & scaling architecture

Read [`architecture.md`](./architecture.md)
