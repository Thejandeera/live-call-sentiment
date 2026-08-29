# Local Docker Deployment Plan

A step-by-step guide to building, running, and testing the **Live Call Sentiment Analysis & Monitoring Platform** using standalone Docker containers with local environment configuration (`.env`) and host log synchronization.

For AWS production deployment (ECR, ECS Fargate, AWS Secrets Manager, SSM Parameter Store), see [`cloud-deployment-plan.md`](./cloud-deployment-plan.md).

---

## 1. Services Overview

| Service | Port | Description | Recommended Resources |
| :--- | :--- | :--- | :--- |
| **api-gateway** | `8000` | Ingress orchestrator & downstream proxy | 1 vCPU, 512 MB RAM |
| **service-phrase** | `8002` | spaCy keyword detection & PostgreSQL sync | 1 vCPU, 1 GB RAM |
| **service-sentiment** | `8003` | RoBERTa 28-emotion classification engine | 2 vCPU, 2-4 GB RAM |
| **service-score** | `8004` | Dual-Horizon mathematical scoring engine | 1 vCPU, 512 MB RAM |
| **PostgreSQL** | `5432` | Relational database (`callIntelligence`) | Local Docker container or cloud DB |

---

## 2. Environment Variables & Logging Strategy

- **Zero Hardcoded Secrets/Envs**: Dockerfiles never contain hardcoded `ENV` directives. All configurations are supplied at runtime.
- **Environment Variables**: Injected into containers via Docker `--env-file .env` (or `-e KEY=VALUE`).
- **Host Audit Logging Sync**: By default, Docker container filesystems are isolated. Using a bind mount (`-v "${PWD}/logs:/app/logs"`) and setting `-e LOG_DIR=/app/logs` maps the container's log directory directly to the host machine's `logs/` directory so you can inspect audit logs in real-time in your IDE.

---

## 3. Local Docker Deployment (Without Docker Compose)

### Step 1: Create a Shared Docker Bridge Network
To allow containers to discover each other via container names:
```bash
docker network create sentiment-network
```

### Step 2: Build All Docker Images
Each Dockerfile uses its own folder as build context:
```bash
docker build -t api-gateway ./api-gateway
docker build -t service-phrase ./service-phrase
docker build -t service-sentiment ./service-sentiment
docker build -t service-score ./service-score
```

### Step 3: Start PostgreSQL (If running database locally in Docker)
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

### Step 4: Run Microservices with Host Log Sync (`-v`)
Pass your local `.env` file via `--env-file .env`, and mount the host `logs` directory (`-v "${PWD}/logs:/app/logs"`) with `-e LOG_DIR=/app/logs` so that container audit logs are written directly to your host machine in real time:

```bash
# 1. Run Phrase Extraction Service (Port 8002)
docker run -d \
  --name service_phrase \
  --network sentiment-network \
  -p 8002:8002 \
  --env-file .env \
  -e LOG_DIR=/app/logs \
  -e POSTGRES_HOST=sentiment_postgres \
  -e POSTGRES_PORT=5432 \
  -e POSTGRES_PASSWORD=postgres \
  -v "${PWD}/logs:/app/logs" \
  service-phrase

# 2. Run Sentiment & Emotion Service (Port 8003)
docker run -d \
  --name service_sentiment \
  --network sentiment-network \
  -p 8003:8003 \
  --env-file .env \
  -e LOG_DIR=/app/logs \
  -v "${PWD}/logs:/app/logs" \
  service-sentiment

# 3. Run Live Sentiment Score Service (Port 8004)
docker run -d \
  --name service_score \
  --network sentiment-network \
  -p 8004:8004 \
  --env-file .env \
  -e LOG_DIR=/app/logs \
  -v "${PWD}/logs:/app/logs" \
  service-score

# 4. Run API Gateway (Port 8000)
docker run -d \
  --name api_gateway \
  --network sentiment-network \
  -p 8000:8000 \
  --env-file .env \
  -e LOG_DIR=/app/logs \
  -e PHRASE_SERVICE_URL=http://service_phrase:8002/extract-keywords \
  -e SENTIMENT_SERVICE_URL=http://service_sentiment:8003/analyze-sentiment \
  -e SCORE_SERVICE_URL=http://service_score:8004/calculate-score \
  -v "${PWD}/logs:/app/logs" \
  api-gateway
```

---

## 4. Inspection & Management Commands

```bash
# Check status of running containers
docker ps

# Stream logs of a container
docker logs -f api_gateway
docker logs -f service_phrase

# Stop and remove all containers
docker stop api_gateway service_phrase service_sentiment service_score sentiment_postgres
docker rm api_gateway service_phrase service_sentiment service_score sentiment_postgres

# Remove network
docker network rm sentiment-network
```

---

## 5. Health Check & Verification

Verify each service is healthy and communicating:

```bash
# 1. Health checks
curl http://localhost:8000/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health

# 2. Add Keyword to PostgreSQL
curl -X POST http://localhost:8000/api/v1/add-keyword \
  -H "Content-Type: application/json" \
  -d '{"keyword": "cancel subscription"}'

# 3. Process Live Call Turn
curl -X POST http://localhost:8000/api/v1/process-text \
  -H "Content-Type: application/json" \
  -d '{"text": "I want to cancel my subscription right now!", "speaker": "caller", "previous_score": 0.0}'
```

---

## 6. AWS Cloud Deployment

For deploying to AWS (Amazon ECR, AWS ECS Fargate, AWS Secrets Manager, SSM Parameter Store, and CloudWatch), refer to the dedicated cloud deployment guide:

👉 **[`cloud-deployment-plan.md`](./cloud-deployment-plan.md)**

It covers:
- Image registry setup with Amazon ECR
- Injecting credentials via AWS Secrets Manager & SSM Parameter Store
- Fargate Task Definitions & Service deployment
- Zero-downtime rolling updates
- CloudWatch live audit logging
