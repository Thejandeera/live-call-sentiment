# Deployment Plan

A step-by-step guide to building, running, and testing the **Live Call Sentiment Analysis & Monitoring Platform** using standalone Docker containers and AWS Environment Manager (Parameter Store / Secrets Manager / ECS).

---

## 1. Services Overview

| Service | Port | Description | Recommended Resources |
| :--- | :--- | :--- | :--- |
| **api-gateway** | `8000` | Ingress orchestrator & downstream proxy | 1 vCPU, 512 MB RAM |
| **service-phrase** | `8002` | spaCy keyword detection & PostgreSQL sync | 1 vCPU, 1 GB RAM |
| **service-sentiment** | `8003` | RoBERTa 28-emotion classification engine | 2 vCPU, 2-4 GB RAM |
| **service-score** | `8004` | Dual-Horizon mathematical scoring engine | 1 vCPU, 512 MB RAM |
| **PostgreSQL** | `5432` | Relational database (`callIntelligence`) | AWS RDS / Docker container |

---

## 2. Environment Variables Strategy

Environment variables are **never hardcoded inside Dockerfiles**. They are supplied dynamically at runtime:
- **Local Testing**: Injected via Docker `--env-file .env` or `-e KEY=VALUE`.
- **AWS Production**: Injected via **AWS Systems Manager Parameter Store**, **AWS Secrets Manager**, or ECS Task Definition `environment` / `secrets` blocks.

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

### Step 4: Run Microservices
Pass your local `.env` file via `--env-file .env`, overriding internal network endpoints where necessary:

```bash
# 1. Run Phrase Extraction Service (Port 8002)
docker run -d \
  --name service_phrase \
  --network sentiment-network \
  -p 8002:8002 \
  --env-file .env \
  -e POSTGRES_HOST=sentiment_postgres \
  -e POSTGRES_PORT=5432 \
  service-phrase

# 2. Run Sentiment & Emotion Service (Port 8003)
docker run -d \
  --name service_sentiment \
  --network sentiment-network \
  -p 8003:8003 \
  --env-file .env \
  service-sentiment

# 3. Run Live Sentiment Score Service (Port 8004)
docker run -d \
  --name service_score \
  --network sentiment-network \
  -p 8004:8004 \
  --env-file .env \
  service-score

# 4. Run API Gateway (Port 8000)
docker run -d \
  --name api_gateway \
  --network sentiment-network \
  -p 8000:8000 \
  --env-file .env \
  -e PHRASE_SERVICE_URL=http://service_phrase:8002/extract-keywords \
  -e SENTIMENT_SERVICE_URL=http://service_sentiment:8003/analyze-sentiment \
  -e SCORE_SERVICE_URL=http://service_score:8004/calculate-score \
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

## 6. AWS Environment Manager / ECS Deployment

When deploying to AWS (e.g., ECS Fargate):
1. **Secrets**: Store database passwords and API tokens in **AWS Secrets Manager**.
2. **Parameters**: Store service discovery URLs and thresholds in **AWS Systems Manager Parameter Store**.
3. **Task Definition**: Inject variables into the container environment using `secrets` and `environment` blocks:
   ```json
   {
     "name": "service-phrase",
     "image": "<aws_account_id>.dkr.ecr.<region>.amazonaws.com/service-phrase:latest",
     "environment": [
       { "name": "POSTGRES_HOST", "value": "mydb.xyz.rds.amazonaws.com" },
       { "name": "POSTGRES_DB", "value": "callIntelligence" },
       { "name": "SPACY_MODEL", "value": "en_core_web_sm" }
     ],
     "secrets": [
       { "name": "POSTGRES_PASSWORD", "valueFrom": "arn:aws:secretsmanager:<region>:<account>:secret:db-password" }
     ]
   }
   ```
