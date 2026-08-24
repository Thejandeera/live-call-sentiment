# System Architecture & Technical Design Specification

This document provides a comprehensive architectural and engineering specification of the **Live Call Sentiment Analysis & Real-Time Monitoring System**. It details the decoupled microservices architecture, inter-service communication protocols, data flows, scoring state transitions, package ecosystem, and deployment strategies.

---

## 1. High-Level Architectural Overview

The Live Call Sentiment platform is designed around a **decoupled, asynchronous microservices architecture** optimized for high-throughput, low-latency live conversational intelligence in customer contact centers.

```mermaid
graph TB
    subgraph Client_Layer["Client & Ingestion Layer"]
        Frontend["Web Dashboard / Next.js Client<br/>(Live Monitor & Admin UI)"]
        AudioPipeline["Live Audio / Telephony Stream<br/>(ASR / Transcription Engine)"]
    end

    subgraph Gateway_Layer["Gateway & Orchestration Layer"]
        APIGateway["FastAPI API Gateway<br/>(Port 8000)<br/>- Async HTTP Connection Pool<br/>- CORS Management<br/>- Request Orchestration"]
    end

    subgraph Microservices_Layer["Specialized NLP & AI Microservices"]
        PhraseService["Phrase & Keyword Service<br/>(Port 8002)<br/>- spaCy PhraseMatcher<br/>- Zero-Redirect Google GViz Sync"]
        SentimentService["Sentiment & Emotion Service<br/>(Port 8003)<br/>- RoBERTa Transformer Engine<br/>- 28 GoEmotions Taxonomy"]
        ScoreService["Live Sentiment Scoring Engine<br/>(Port 8004)<br/>- Confidence-Scaled EMA<br/>- Continuous Logistic Saturation<br/>- Dual-Horizon Health Tracking"]
    end

    subgraph External_Storage["External Configuration & Persistence"]
        GoogleSheets["Google Spreadsheet<br/>(Admin Monitored Keywords & Weights)"]
        BrowserStorage["Client Session Storage<br/>(Turn History & Chart Trajectories)"]
    end

    %% Flow Connections
    Frontend -->|"POST /api/v1/process-message"| APIGateway
    AudioPipeline -->|"POST /api/v1/process-text"| APIGateway
    APIGateway -->|"POST /extract-keywords"| PhraseService
    APIGateway -->|"POST /analyze-sentiment"| SentimentService
    APIGateway -->|"POST /calculate-score"| ScoreService
    PhraseService -.->|"Fetch CSV via GViz API"| GoogleSheets
    Frontend -.->|"Local State Sync"| BrowserStorage

    classDef gateway fill:#1e3a8a,stroke:#3b82f6,stroke-width:2px,color:#ffffff;
    classDef service fill:#065f46,stroke:#10b981,stroke-width:2px,color:#ffffff;
    classDef client fill:#374151,stroke:#9ca3af,stroke-width:2px,color:#ffffff;
    classDef external fill:#7c2d12,stroke:#f97316,stroke-width:2px,color:#ffffff;

    class APIGateway gateway;
    class PhraseService,SentimentService,ScoreService service;
    class Frontend,AudioPipeline client;
    class GoogleSheets,BrowserStorage external;
```

---

## 2. Microservice Topology & Component Responsibilities

```mermaid
flowchart LR
    subgraph S1["1. API Gateway (Port 8000)"]
        direction TB
        G1["Ingest Transcript Payload"] --> G2["Connection Pool (HTTPX AsyncClient)"]
        G2 --> G3["Concurrent Microservice Dispatch"]
        G3 --> G4["Aggregate Results & Latency Measurement"]
    end

    subgraph S2["2. Phrase Service (Port 8002)"]
        direction TB
        P1["spaCy en_core_web_sm Pipeline"] --> P2["Google Sheets CSV GViz Ingestion"]
        P2 --> P3["In-Memory PhraseMatcher (LOWER)"]
        P3 --> P4["Return Detected Keyword Matches"]
    end

    subgraph S3["3. Sentiment Service (Port 8003)"]
        direction TB
        T1["RoBERTa GoEmotions Pipeline"] --> T2["torch.inference_mode (Zero Grad)"]
        T2 --> T3["28-Emotion Multi-Class Classification"]
        T3 --> T4["Categorize: Positive / Negative / Neutral"]
    end

    subgraph S4["4. Score Service (Port 8004)"]
        direction TB
        C1["Confidence-Scaled Step Size (alpha)"] --> C2["Continuous Logistic Saturation D(S)"]
        C2 --> C3["Mild Negative Non-Relief & Crisis Clamping"]
        C3 --> C4["Dual-Horizon Session Health (S_health)"]
    end

    S1 <-->|Async REST| S2
    S1 <-->|Async REST| S3
    S1 <-->|Async REST| S4
```

### 2.1 API Gateway (`api-gateway/main.py`)
- **Role**: Central ingress proxy and orchestrator.
- **Port**: `8000` (configurable via `API_GATEWAY_PORT`).
- **Connection Management**: Instantiates a persistent `httpx.AsyncClient` with connection pooling (`max_keepalive_connections=20`, `max_connections=100`, `timeout=30.0s`) on application startup, eliminating TCP handshake overhead for subsequent calls.
- **CORS Support**: Enforces secure cross-origin resource sharing configured via `CORS_ORIGINS` (defaults to `http://localhost:3000`).
- **Resilience**: Independent error containment per microservice call. If `service-phrase` fails, sentiment and scoring continue uninterrupted; if `service-sentiment` fails, graceful neutral defaults are returned.

### 2.2 Phrase Extraction Service (`service-phrase/main.py`)
- **Role**: High-speed keyword identification and exact sentence phrase matching.
- **Port**: `8002` (configurable via `PHRASE_SERVICE_PORT`).
- **Engine**: spaCy (`en_core_web_sm`) using `PhraseMatcher(nlp.vocab, attr="LOWER")`.
- **Dynamic Config Ingestion**: Fetches keyword configuration live from Google Sheets using the Google Visualization API CSV endpoint (`/gviz/tq?tqx=out:csv`). This completely eliminates OAuth redirects and external domain blocking while providing real-time sync with supervisor edits.

### 2.3 Sentiment & Emotion Classification Service (`service-sentiment/main.py`)
- **Role**: Transformer-based deep learning emotion classification.
- **Port**: `8003` (configurable via `SENTIMENT_SERVICE_PORT`).
- **Model**: `SamLowe/roberta-base-go_emotions` (fine-tuned RoBERTa on Reddit GoEmotions dataset spanning 28 fine-grained emotions).
- **Execution Mode**: PyTorch `torch.inference_mode()` with token truncation (`max_length=128`) and batching support (`batch_size=32`), minimizing VRAM/RAM overhead and eliminating computational graph construction.
- **Categorization**: Maps 28 emotions to tri-state sentiment polarity (`positive`, `negative`, `neutral`) using a $0.20$ minimum confidence threshold.

### 2.4 Live Sentiment Scoring Engine (`service-score/main.py`)
- **Role**: Standardized Dual-Horizon stateful mathematical scoring engine.
- **Port**: `8004` (configurable via `SCORE_SERVICE_PORT`).
- **Mathematical Foundations**:
  - **Confidence-Scaled Step Size ($\alpha_{\text{effective}}$)**: Prevents low-confidence noise from causing score reversal paradoxes.
  - **Continuous Logistic Saturation ($D(S)$)**: Smooth non-linear resistance as scores traverse towards $\pm 100.0$.
  - **Mild Negative Non-Relief Rule**: Prevents milder negative emotions during severe crisis from triggering false recovery.
  - **Crisis Neutral Clamping**: Preserves crisis context during informational neutral utterances.
  - **Dual-Horizon Call Health Aggregator ($S_{\text{health}}$)**: Weighted fusion of cumulative session average ($70\%$) and instantaneous live score ($30\%$).

---

## 3. End-to-End Request & Data Flow

The following sequence diagram traces the complete lifecycle of a single caller or agent conversational turn processed by the platform:

```mermaid
sequenceDiagram
    autonumber
    actor Caller as Caller / Telephony Stream
    participant Client as Frontend / Next.js Client
    participant GW as API Gateway (:8000)
    participant Phrase as Phrase Service (:8002)
    participant Sheet as Google Sheets GViz
    participant Sentiment as Sentiment Service (:8003)
    participant Score as Score Service (:8004)

    Caller->>Client: Utterance: "I am furious, cancel my account!"
    Client->>GW: POST /api/v1/process-message<br/>{text, speaker, previous_score, turn_count, session_avg_score}

    par Step 1: Detect Monitored Keywords
        GW->>Phrase: POST /extract-keywords {text}
        opt Cache Miss / Fetch Live
            Phrase->>Sheet: GET /gviz/tq?tqx=out:csv
            Sheet-->>Phrase: CSV Keywords Matrix
        end
        Phrase-->>GW: {matches: ["cancel account"]}
    and Step 2: Classify Emotion & Confidence
        GW->>Sentiment: POST /analyze-sentiment {text}
        Note over Sentiment: RoBERTa Transformer Inference<br/>Output: "anger", conf: 0.94
        Sentiment-->>GW: {emotion: "anger", sentiment_category: "negative", confidence: 0.94}
    end

    GW->>Score: POST /calculate-score<br/>{emotion: "anger", confidence: 0.94, previous_score: -50.0, turn_count: 5}
    Note over Score: Apply Confidence-Scaled Alpha<br/>Apply Logistic Dampening D(S)<br/>Calculate S_live & S_health
    Score-->>GW: {score: -72.4, call_health_score: -66.1, trend: "Escalating", escalation_triggered: true}

    GW-->>Client: 200 OK<br/>{status: "success", processing_time_ms: 22.4, detected_issues: [...]}
    Client->>Client: Update SVG Sentiment Line Chart & Trigger Supervisor Alert
```

---

## 4. Scoring Engine State Machine & Trajectory Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Baseline: Session Start (S = 0.0)

    state "Normal Interaction (-30.0 < S < +30.0)" as Baseline
    state "Escalating Friction (-65.0 < S <= -30.0)" as MildFriction
    state "Escalation Alert Triggered (S <= -65.0)" as EscalationZone
    state "Severe Catastrophic Crisis (S <= -85.0)" as SevereCrisis
    state "De-Escalation & Fast Recovery" as FastRecovery

    Baseline --> MildFriction: Negative Utterance (annoyance, disappointment)
    MildFriction --> EscalationZone: Consecutive Hostile Utterances (anger, disgust)
    EscalationZone --> SevereCrisis: Sustained Negative Momentum (t > 10 turns)

    SevereCrisis --> EscalationZone: Mild Negative Utterance (Clamped alpha = 0.01)
    SevereCrisis --> FastRecovery: Genuine Resolution Emotion (relief, gratitude, D = 1.0)
    EscalationZone --> FastRecovery: Positive Emotion (approval, joy, D = 1.0)
    MildFriction --> FastRecovery: Positive Utterance
    FastRecovery --> Baseline: Score climbs past -30.0 to 0.0+

    Baseline --> [*]: Session Ended
    EscalationZone --> [*]: Supervisor Intervenes / Call Ends
    SevereCrisis --> [*]: Call Terminated
```

---

## 5. Package Ecosystem & Technology Stack

Each microservice leverages a targeted, lightweight set of packages selected for stability, asynchronous performance, and minimal memory footprint:

| Component | Package | Version Constraint | Architectural Purpose & Rationale |
| :--- | :--- | :--- | :--- |
| **API Gateway** | `fastapi` | `>=0.95.0` | High-performance asynchronous REST API framework with native OpenAPI documentation and Pydantic validation. |
| | `uvicorn` | `>=0.21.0` | Lightning-fast ASGI web server implementation based on `uvloop` and `httptools`. |
| | `httpx` | `>=0.24.0` | Next-generation async HTTP client supporting HTTP/1.1 and HTTP/2 connection pooling. |
| | `pydantic` | `>=1.10.0` | Data parsing, type enforcement, and payload validation. |
| | `python-dotenv` | `>=1.0.0` | Environment variable parsing and `.env` file management across runtime contexts. |
| **Phrase Service** | `spacy` | `>=3.5.0` | Industrial-strength NLP library providing exact, efficient multi-token `PhraseMatcher`. |
| | `requests` | `>=2.28.0` | Synchronous HTTP library for simple Google Sheets GViz CSV ingestion. |
| | `pydantic` | `>=1.10.0` | Request and response schema validation. |
| | `python-dotenv` | `>=1.0.0` | Dynamic configuration of Google Sheets URL and model names. |
| **Sentiment Service**| `torch` | `>=2.0.0` | Deep learning backend providing optimized tensor math and GPU/CPU inference kernels. |
| | `transformers` | `>=4.30.0` | Hugging Face pipeline abstraction for loading pre-trained RoBERTa architectures. |
| | `pydantic` | `>=1.10.0` | Batch payload structuring and response serialization. |
| | `python-dotenv` | `>=1.0.0` | Configurable model repository identifier (`SENTIMENT_MODEL_NAME`). |
| **Score Service** | `fastapi` | `>=0.95.0` | High-speed scoring endpoint serving sub-millisecond mathematical calculations. |
| | `pydantic` | `>=1.10.0` | Mathematical request and response contract enforcement. |
| | `python-dotenv` | `>=1.0.0` | Dynamic parametrization of dampening constants and thresholds. |

---

## 6. Fault Tolerance, Resilience & Fallback Matrix

```mermaid
flowchart TD
    Req["Incoming Utterance to API Gateway"] --> Dispatch["Dispatch Sub-Requests"]

    Dispatch --> P_Call["Call service-phrase"]
    Dispatch --> S_Call["Call service-sentiment"]
    
    P_Call -->|200 OK| P_Res["Keywords Found"]
    P_Call -->|Timeout / Error| P_Fail["Fallback: matches = [] (Non-blocking)"]

    S_Call -->|200 OK| S_Res["Emotion & Confidence"]
    S_Call -->|Timeout / Error| S_Fail["Fallback: emotion='neutral', conf=0.0"]

    P_Res & P_Fail --> Aggregate["Assemble Score Payload"]
    S_Res & S_Fail --> Aggregate

    Aggregate --> C_Call["Call service-score"]
    C_Call -->|200 OK| C_Res["Computed S_live & S_health"]
    C_Call -->|Timeout / Error| C_Fail["Fallback: Maintain previous_score"]

    C_Res & C_Fail --> Final["Return Unified Gateway JSON (200 OK)"]
```

---

## 7. Production Deployment & Containerization Architecture

### 7.1 Container Mesh Topology

```mermaid
graph TD
    subgraph Host["Docker / Kubernetes Host"]
        subgraph ReverseProxy["Ingress Layer"]
            Nginx["Nginx / Traefik Reverse Proxy<br/>(Port 80/443 SSL Termination)"]
        end

        subgraph ServiceMesh["Internal Bridge Network"]
            GW_C["api-gateway Container<br/>(Port 8000)"]
            PH_C["service-phrase Container<br/>(Port 8002)"]
            ST_C["service-sentiment Container<br/>(Port 8003, CPU/CUDA)"]
            SC_C["service-score Container<br/>(Port 8004)"]
        end
    end

    Internet(("Public Internet / Client")) -->|HTTPS| Nginx
    Nginx -->|Proxy Pass| GW_C
    GW_C --> PH_C
    GW_C --> ST_C
    GW_C --> SC_C
```

### 7.2 Scaling Recommendations
1. **API Gateway**: Stateless and I/O bound. Scale horizontally with multiple workers (`uvicorn main:app --workers 4`).
2. **Phrase Service**: CPU bound during startup; in-memory lookup during runtime. Memory footprint $\approx 150\text{MB}$.
3. **Sentiment Service**: Compute/RAM bound. When running on CPU, allocate $\ge 2\text{GB}$ RAM per instance; for high-concurrency environments ($>100\text{ req/sec}$), deploy on an NVIDIA T4/A10 GPU with TensorRT or ONNX Runtime acceleration.
4. **Score Service**: Pure mathematical operations ($\approx 0.5\text{ms}$ latency). A single instance easily handles $>2,000\text{ req/sec}$.
