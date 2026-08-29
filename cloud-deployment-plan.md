# AWS Cloud Deployment Plan

A concise, step-by-step production deployment guide for the **Live Call Sentiment Analysis & Monitoring Platform** using **Amazon ECR**, **AWS ECS Fargate**, **AWS Secrets Manager**, and **AWS Systems Manager (SSM) Parameter Store**.

---

## 1. Cloud Architecture Summary

```
                      [ Client Requests / Frontend / ASR ]
                                      │
                                      ▼
                      ┌──────────────────────────────┐
                      │    AWS Application LB /      │
                      │         API Gateway          │ (Port 8000)
                      └──────────────┬───────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│  service-phrase  │       │ service-sentiment│       │  service-score   │
│   (Port 8002)    │       │   (Port 8003)    │       │   (Port 8004)    │
└────────┬─────────┘       └──────────────────┘       └──────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│   Amazon RDS / PostgreSQL DB    │
│       (`callIntelligence`)      │
└─────────────────────────────────┘
```

- **Container Registry**: Amazon ECR (images pushed per microservice).
- **Compute**: AWS ECS Fargate (serverless containers).
- **Environment & Secrets**: Injected at runtime via **AWS Secrets Manager** and **SSM Parameter Store** (zero hardcoded secrets or `.env` files inside Docker images).
- **Audit Logging**: Streamed directly via `stdout` to **Amazon CloudWatch Logs**.

---

## 2. Set Environment Variables & Authenticate Docker to ECR

```bash
# 1. Export AWS configuration
export AWS_REGION="us-east-1"
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
export CLUSTER_NAME="sentiment-cluster"

# 2. Login Docker to Amazon ECR
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}
```

---

## 3. Create ECR Repositories

Create an ECR repository for each microservice (one-time setup):

```bash
for repo in api-gateway service-phrase service-sentiment service-score; do
  aws ecr create-repository --repository-name $repo --region ${AWS_REGION}
done
```

---

## 4. Build, Tag, and Push Docker Images to ECR

Build each service cleanly from its own folder and push to ECR:

```bash
# Build and push all 4 microservices
for svc in api-gateway service-phrase service-sentiment service-score; do
  docker build -t ${ECR_REGISTRY}/${svc}:latest ./${svc}
  docker push ${ECR_REGISTRY}/${svc}:latest
done
```

---

## 5. Configure AWS Environment Manager (Secrets & SSM)

### A. Store Sensitive Database Password in AWS Secrets Manager
```bash
aws secretsmanager create-secret \
  --name "prod/sentiment/db_password" \
  --description "PostgreSQL password for callIntelligence database" \
  --secret-string "YourStrongProductionRDSMasterPassword" \
  --region ${AWS_REGION}
```

### B. Store Service Configurations in SSM Parameter Store
*(Replace `your-rds-endpoint.amazonaws.com` with your actual cloud RDS host)*:

```bash
# Database parameters
aws ssm put-parameter --name "/sentiment/POSTGRES_HOST" --type String --value "your-rds-endpoint.amazonaws.com" --overwrite
aws ssm put-parameter --name "/sentiment/POSTGRES_PORT" --type String --value "5432" --overwrite
aws ssm put-parameter --name "/sentiment/POSTGRES_DB" --type String --value "callIntelligence" --overwrite
aws ssm put-parameter --name "/sentiment/POSTGRES_USER" --type String --value "postgres" --overwrite
aws ssm put-parameter --name "/sentiment/POSTGRES_TABLE" --type String --value "call_admin_keywords" --overwrite
aws ssm put-parameter --name "/sentiment/SPACY_MODEL" --type String --value "en_core_web_sm" --overwrite

# Downstream URLs (using Cloud Map internal DNS or ALB)
aws ssm put-parameter --name "/sentiment/PHRASE_SERVICE_URL" --type String --value "http://service-phrase.sentiment.local:8002/extract-keywords" --overwrite
aws ssm put-parameter --name "/sentiment/SENTIMENT_SERVICE_URL" --type String --value "http://service-sentiment.sentiment.local:8003/analyze-sentiment" --overwrite
aws ssm put-parameter --name "/sentiment/SCORE_SERVICE_URL" --type String --value "http://service-score.sentiment.local:8004/calculate-score" --overwrite

# Application settings
aws ssm put-parameter --name "/sentiment/CORS_ORIGINS" --type String --value "https://yourfrontend.com" --overwrite
aws ssm put-parameter --name "/sentiment/ESCALATION_THRESHOLD" --type String --value "-65.0" --overwrite
```

---

## 6. Register ECS Task Definitions

Create the CloudWatch log group first:
```bash
aws logs create-log-group --log-group-name "/ecs/live-call-sentiment" --region ${AWS_REGION}
```

Each Task Definition dynamically injects parameters from Secrets Manager & SSM into the container runtime.

### 1. Phrase Extraction Service (`service-phrase`)
```bash
cat <<EOF > phrase-task.json
{
  "family": "service-phrase",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "service-phrase",
      "image": "${ECR_REGISTRY}/service-phrase:latest",
      "essential": true,
      "portMappings": [{ "containerPort": 8002, "protocol": "tcp" }],
      "secrets": [
        { "name": "POSTGRES_PASSWORD", "valueFrom": "arn:aws:secretsmanager:${AWS_REGION}:${AWS_ACCOUNT_ID}:secret:prod/sentiment/db_password" },
        { "name": "POSTGRES_HOST", "valueFrom": "arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/sentiment/POSTGRES_HOST" },
        { "name": "POSTGRES_PORT", "valueFrom": "arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/sentiment/POSTGRES_PORT" },
        { "name": "POSTGRES_DB", "valueFrom": "arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/sentiment/POSTGRES_DB" },
        { "name": "POSTGRES_USER", "valueFrom": "arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/sentiment/POSTGRES_USER" },
        { "name": "POSTGRES_TABLE", "valueFrom": "arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/sentiment/POSTGRES_TABLE" }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/live-call-sentiment",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "phrase"
        }
      }
    }
  ]
}
EOF
aws ecs register-task-definition --cli-input-json file://phrase-task.json
```

### 2. Sentiment Service (`service-sentiment`)
```bash
cat <<EOF > sentiment-task.json
{
  "family": "service-sentiment",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "4096",
  "executionRoleArn": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "service-sentiment",
      "image": "${ECR_REGISTRY}/service-sentiment:latest",
      "essential": true,
      "portMappings": [{ "containerPort": 8003, "protocol": "tcp" }],
      "environment": [
        { "name": "SENTIMENT_MODEL_NAME", "value": "SamLowe/roberta-base-go_emotions" }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/live-call-sentiment",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "sentiment"
        }
      }
    }
  ]
}
EOF
aws ecs register-task-definition --cli-input-json file://sentiment-task.json
```

### 3. Score Service (`service-score`)
```bash
cat <<EOF > score-task.json
{
  "family": "service-score",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "service-score",
      "image": "${ECR_REGISTRY}/service-score:latest",
      "essential": true,
      "portMappings": [{ "containerPort": 8004, "protocol": "tcp" }],
      "secrets": [
        { "name": "ESCALATION_THRESHOLD", "valueFrom": "arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/sentiment/ESCALATION_THRESHOLD" }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/live-call-sentiment",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "score"
        }
      }
    }
  ]
}
EOF
aws ecs register-task-definition --cli-input-json file://score-task.json
```

### 4. API Gateway (`api-gateway`)
```bash
cat <<EOF > gateway-task.json
{
  "family": "api-gateway",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "api-gateway",
      "image": "${ECR_REGISTRY}/api-gateway:latest",
      "essential": true,
      "portMappings": [{ "containerPort": 8000, "protocol": "tcp" }],
      "secrets": [
        { "name": "CORS_ORIGINS", "valueFrom": "arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/sentiment/CORS_ORIGINS" },
        { "name": "PHRASE_SERVICE_URL", "valueFrom": "arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/sentiment/PHRASE_SERVICE_URL" },
        { "name": "SENTIMENT_SERVICE_URL", "valueFrom": "arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/sentiment/SENTIMENT_SERVICE_URL" },
        { "name": "SCORE_SERVICE_URL", "valueFrom": "arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/sentiment/SCORE_SERVICE_URL" }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/live-call-sentiment",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "gateway"
        }
      }
    }
  ]
}
EOF
aws ecs register-task-definition --cli-input-json file://gateway-task.json
```

---

## 7. Deploy to ECS Cluster (Fargate)

```bash
# 1. Create Cluster
aws ecs create-cluster --cluster-name ${CLUSTER_NAME} --region ${AWS_REGION}

# 2. Deploy Services
SUBNETS="subnet-xxxxxx1,subnet-xxxxxx2"
SEC_GROUP="sg-xxxxxx"

for svc in service-phrase service-sentiment service-score api-gateway; do
  aws ecs create-service \
    --cluster ${CLUSTER_NAME} \
    --service-name $svc \
    --task-definition $svc \
    --desired-count 1 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[${SUBNETS}],securityGroups=[${SEC_GROUP}],assignPublicIp=ENABLED}"
done
```

---

## 8. Zero-Downtime Rolling Update

Whenever code is updated:
```bash
# 1. Rebuild and push updated image
docker build -t ${ECR_REGISTRY}/api-gateway:latest ./api-gateway
docker push ${ECR_REGISTRY}/api-gateway:latest

# 2. Trigger instant rolling deployment
aws ecs update-service --cluster ${CLUSTER_NAME} --service api-gateway --force-new-deployment
```

---

## 9. Testing & Live Verification

Replace `<API_GATEWAY_URL>` with your Load Balancer DNS or public IP:

```bash
# 1. Health Checks
curl http://<API_GATEWAY_URL>:8000/health

# 2. Add Monitored Keyword to Cloud DB
curl -X POST http://<API_GATEWAY_URL>:8000/api/v1/add-keyword \
  -H "Content-Type: application/json" \
  -d '{"keyword": "cancel subscription"}'

# 3. Process Live Call Sentence
curl -X POST http://<API_GATEWAY_URL>:8000/api/v1/process-text \
  -H "Content-Type: application/json" \
  -d '{"text": "I want to cancel my subscription right now!", "speaker": "caller", "previous_score": 0.0}'
```

---

## 10. Live Production Audit Logs (CloudWatch)

Stream and tail live audit logs directly from the cloud:

```bash
aws logs tail "/ecs/live-call-sentiment" --follow --filter-pattern "AUDIT"
```
