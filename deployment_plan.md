# Local Docker Deployment Plan

## 1. Create Docker Network
```bash
docker network create sentiment-network
```

## 2. Build Base Image
```bash
docker build -f Dockerfile.base -t thejandeerasan/sentiment-base:latest -t sentiment-base:latest --no-cache .
```

## 3. Build Microservice Images
```bash
docker build -t api-gateway ./api-gateway
docker build -t service-phrase ./service-phrase
docker build -t service-sentiment ./service-sentiment
docker build -t service-score ./service-score
```

## 4. Run Downstream Microservices
```bash
docker run -d \
  --name service_phrase \
  --network sentiment-network \
  -p 8002:8002 \
  --env-file .env \
  -v "${PWD}/logs:/app/logs" \
  service-phrase
```

```bash
docker run -d \
  --name service_sentiment \
  --network sentiment-network \
  -p 8003:8003 \
  --env-file .env \
  -v "${PWD}/logs:/app/logs" \
  service-sentiment
```

```bash
docker run -d \
  --name service_score \
  --network sentiment-network \
  -p 8004:8004 \
  --env-file .env \
  -v "${PWD}/logs:/app/logs" \
  service-score
```

## 5. Run API Gateway
```bash
docker run -d \
  --name api_gateway \
  --network sentiment-network \
  -p 8000:8000 \
  --env-file .env \
  -v "${PWD}/logs:/app/logs" \
  api-gateway
```

## 6. Verify Running Containers
```bash
docker ps
```

## 7. Check Logs (Optional)
```bash
docker logs -f api_gateway
docker logs -f service_phrase
docker logs -f service_sentiment
docker logs -f service_score
```

## 8. Health Check Verification
```bash
curl http://localhost:8000/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
```

## 9. Test API Functionality
```bash
curl -X POST http://localhost:8000/api/v1/add-keyword \
  -H "Content-Type: application/json" \
  -d '{"keyword": "cancel subscription"}'
```

```bash
curl -X POST http://localhost:8000/api/v1/process-text \
  -H "Content-Type: application/json" \
  -d '{"text": "I want to cancel my subscription right now!", "speaker": "caller", "previous_score": 0.0}'
```

## 10. Teardown / Cleanup
```bash
docker stop api_gateway service_phrase service_sentiment service_score
docker rm api_gateway service_phrase service_sentiment service_score
```

```bash
docker network rm sentiment-network
```