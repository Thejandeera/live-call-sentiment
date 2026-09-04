# Local Docker Deployment Plan

This guide outlines the steps to build, configure, run, and verify the **Live Call Sentiment Analysis & Monitoring Platform** locally using Docker.

---

## 1. Prerequisites & Directory Setup

Ensure Docker is running and create the necessary host directories for audit logs and persistent model caching:

```bash
# Create host directories for logs and persistent model cache
mkdir -p logs model_cache

# Create Docker bridge network
docker network create sentiment-network
```



> The `model_cache` folder persists the RoBERTa model weights on your host machine (`./model_cache/roberta`). The 478 MB model will be downloaded only once, all subsequent container launches will load locally in under 2 seconds.

---

## 2. Environment Configuration

Copy the example environment file if you haven't already:

```bash
cp .env.example .env
```

Ensure the PostgreSQL credentials and service URLs match your environment in `.env`.

---

## 3. Build Base Docker Image

Build the shared base image containing Python 3.11, PyTorch CPU, spaCy (`en_core_web_sm`), Hugging Face Transformers, and FastAPI:

```bash
docker build -f Dockerfile.base -t r1-sentiment-base:v3 --no-cache .
```

---

## 4. Build Microservice Images

Build each service image using the local base image:

```bash
docker build -t r1-service-phrase:v3 ./service-phrase
docker build -t r1-service-sentiment:v3 ./service-sentiment
docker build -t r1-service-score:v3 ./service-score
docker build -t r1-api-gateway:v3 ./api-gateway
```

---

## 5. Run Downstream Microservices

### A. Phrase Extraction Service (Port 8002)
```bash
docker run -d \
  --name service_phrase \
  --network sentiment-network \
  -p 8002:8002 \
  --env-file .env \
  -v "${PWD}/logs:/app/logs" \
  r1-service-phrase:v3
```

### B. Sentiment & Emotion Service (Port 8003)
> IMPORTANT
> - `-t` allocates a pseudo-TTY so the real-time download progress updates cleanly in-place on a single line.
> - `-v "${PWD}/model_cache:/app/models"` mounts the model cache so the weights are persisted on the host.

```bash
docker run -d -t \
  --name service_sentiment \
  --network sentiment-network \
  -p 8003:8003 \
  --env-file .env \
  -v "${PWD}/logs:/app/logs" \
  -v "${PWD}/model_cache:/app/models" \
  r1-service-sentiment:v3
```

### C. Live Sentiment Score Service (Port 8004)
```bash
docker run -d \
  --name service_score \
  --network sentiment-network \
  -p 8004:8004 \
  --env-file .env \
  -v "${PWD}/logs:/app/logs" \
  r1-service-score:v3
```

---

## 6. Run API Gateway (Port 8000)

```bash
docker run -d \
  --name api-gateway \
  --network sentiment-network \
  -p 8000:8000 \
  --env-file .env \
  -v "${PWD}/logs:/app/logs" \
  r1-api-gateway:v3
```

---

## 7. Monitor Model Download & Container Logs

### Real-Time Model Download Progress
Watch the model download in real time. It displays on a single line updating every second with percentage, downloaded MB, transfer speed, and ETA:

```bash
docker logs -f service_sentiment
```

**Sample Output:**
```text
[Sentiment Service] Preparing RoBERTa model 'SamLowe/roberta-base-go_emotions' in '/app/models/roberta'...
[Sentiment Service] Downloading RoBERTa model 'SamLowe/roberta-base-go_emotions' (478.8 MB)...
[Sentiment Service] Connecting to Hugging Face CDN...
[Downloading model.safetensors]  45.2% (216.0/478.8 MB) | Speed: 4.80 MB/s | ETA: 54s
```

### Other Service Logs
```bash
docker logs -f api-gateway
docker logs -f service_phrase
docker logs -f service_score
```

---

## 8. Health Check Verification

```bash
curl http://localhost:8000/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
```

---

## 9. Fault Tolerance & API Testing

The API Gateway includes built-in fault tolerance and graceful degradation:
- If a downstream service is offline or initializing, the gateway **will not hang or fail with a 500 error**.
- Individual service status (`online`, `unavailable`, `degraded`) is reported under `services_status`.
- Keyword extraction, sentiment classification, and score calculation run in parallel with 3-second timeouts.

### Add a Keyword
```bash
curl -X POST http://localhost:8000/api/v1/add-keyword \
  -H "Content-Type: application/json" \
  -d '{"keyword": "bad"}'
```

### Process Text (Caller Turn)
```bash
curl -X POST http://localhost:8000/api/v1/process-text \
  -H "Content-Type: application/json" \
  -d '{"text": "its very bad, I am very disappointed", "speaker": "caller", "previous_score": -50}'
```

**Sample Response:**
```json
{
  "status": "success",
  "processing_time_ms": 32.81,
  "services_status": {
    "phrase_service": "online",
    "sentiment_service": "online",
    "score_service": "online"
  },
  "detected_issues": [
    {
      "isolated_sentence": "its very bad, I am very disappointed",
      "detected_keywords": [
        { "keyword": "bad", "category": null }
      ],
      "emotion": "disappointment",
      "confidence": 0.8421,
      "sentiment_category": "negative",
      "live_score": -62.5
    }
  ]
}
```

---

## 10. Teardown / Cleanup

Stop and remove all running containers:

```bash
docker stop api-gateway service_phrase service_sentiment service_score
docker rm api-gateway service_phrase service_sentiment service_score
```

Remove the Docker network (optional):

```bash
docker network rm sentiment-network
```