@echo off
echo ===================================================
echo Starting Live Call Sentiment Microservices...
echo ===================================================

REM Start API Gateway (Port 8000)
start "API Gateway" cmd /k "call venv\Scripts\activate && cd api-gateway && uvicorn main:app --port 8000"

REM Start Phrase Extraction Service (Port 8002)
start "Phrase Service" cmd /k "call venv\Scripts\activate && cd service-phrase && uvicorn main:app --port 8002"

REM Start Sentiment Analysis Service (Port 8003)
start "Sentiment Service" cmd /k "call venv\Scripts\activate && cd service-sentiment && uvicorn main:app --port 8003"

REM Start Sentiment Score Calculation Service (Port 8004)
start "Sentiment Score Service" cmd /k "call venv\Scripts\activate && cd service-score && uvicorn main:app --port 8004"

echo All 4 microservices are launching in separate windows!
echo You can close this window now.
pause

