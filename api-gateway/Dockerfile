FROM r1-sentiment-base:v3
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
