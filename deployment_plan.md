# Deployment Plan

A simple, step-by-step guide to deploying the **Live Call Sentiment Analysis & Monitoring Platform** using Docker Compose.

---

## 1. Services Overview

| Service | Port | Description | Recommended Resources |
| :--- | :--- | :--- | :--- |
| **api-gateway** | `8000` | Ingress orchestrator & connection pooling | 1 vCPU, 512 MB RAM |
| **service-phrase** | `8002` | spaCy keyword detection & PostgreSQL sync | 1 vCPU, 1 GB RAM |
| **service-sentiment** | `8003` | RoBERTa 28-emotion classification engine | 2 vCPU, 2-4 GB RAM |
| **service-score** | `8004` | Dual-Horizon mathematical scoring engine | 1 vCPU, 512 MB RAM |
| **PostgreSQL** | `5432` | Relational database (`callIntelligence`) | Standard container / instance |

---

## 2. Docker Compose Deployment (Recommended)

### Step 1: Configure Environment Variables
Copy the template configuration and set your database credentials:
```bash
cp .env.example .env
```
Ensure `POSTGRES_DB=callIntelligence`, `POSTGRES_TABLE=call_admin_keywords`, and your `POSTGRES_PASSWORD` are configured in `.env`.

### Step 2: Build and Start Services
Build all container images and launch the multi-service stack in detached mode:
```bash
docker compose up -d --build
```

### Step 3: Check Logs and Status
Inspect live container logs and running status:
```bash
docker compose ps
docker compose logs -f
```

### Step 4: Stop or Restart Services
To stop the services:
```bash
docker compose down
```

---

## 3. Health Check & Validation

Verify deployment health across all microservices:

```bash
# Check API Gateway & Downstream Mesh Status
curl http://localhost:8000/health

# Check Phrase Service & PostgreSQL Connection
curl http://localhost:8002/health

# Check Sentiment Service & Transformer Model Status
curl http://localhost:8003/health

# Check Live Score Service Status
curl http://localhost:8004/health
```
