# Local Docker Deployment Plan

```bash
docker network create sentiment-network
```

```bash
docker build -f Dockerfile.base -t sentiment-base:latest --no-cache .
```

```bash
docker build -t api-gateway ./api-gateway
docker build -t service-phrase ./service-phrase
docker build -t service-sentiment ./service-sentiment
docker build -t service-score ./service-score
```

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

```bash
docker run -d \
  --name api_gateway \
  --network sentiment-network \
  -p 8000:8000 \
  --env-file .env \
  -v "${PWD}/logs:/app/logs" \
  api-gateway
```

```bash
docker ps
```

```bash
docker logs -f api_gateway
docker logs -f service_phrase
```

```bash
docker stop api_gateway service_phrase service_sentiment service_score
docker rm api_gateway service_phrase service_sentiment service_score
```

```bash
docker network rm sentiment-network
```

```bash
curl http://localhost:8000/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
```

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