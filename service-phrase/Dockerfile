FROM r1-sentiment-base:v2
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY . .
EXPOSE 8002
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
