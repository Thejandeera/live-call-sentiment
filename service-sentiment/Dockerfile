FROM r1-sentiment-base:v3
ENV PYTHONUNBUFFERED=1
WORKDIR /app
RUN mkdir -p /app/models
COPY . .
EXPOSE 8003
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
