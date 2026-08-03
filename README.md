# Live Call Sentiment System

A decoupled AI architecture designed for real-time live call monitoring, sentiment tracking, and supervisor alertness management.

## 🏗 Architecture Overview

The system consists of a Next.js frontend and three independent FastAPI Python microservices:

- **Frontend (Next.js):** Provides a Live Call Sentiment Monitor UI (`/live`) and a Supervisor Configuration Dashboard (`/admin`).
- **API Gateway (Port 8000):** Central orchestrator routing requests to the NLP and sentiment microservices.
- **Phrase Extraction Service (Port 8002):** spaCy `PhraseMatcher` microservice isolating exact sentence boundaries around admin-configured keywords.
- **Sentiment Service (Port 8003):** Fine-tuned RoBERTa model (`SamLowe/roberta-base-go_emotions`) calculating emotion and confidence scores.

## 📂 Project Structure

```text
live-call-sentiment/
├── api-gateway/            # FastAPI Gateway (Port 8000)
├── service-phrase/         # spaCy Keyphrase Detection (Port 8002)
├── service-sentiment/      # RoBERTa Emotion Classifier (Port 8003)
├── frontend/               # Next.js Frontend UI
├── start_services.bat      # Windows batch startup script
└── README.md
```

## ⚙️ Environment Setup & Installation

### 1. Backend Setup

From the project root folder:

```powershell
# Create and activate Python virtual environment (Windows)
python -m venv venv
.\venv\Scripts\activate

# Install dependencies for all microservices
pip install -r api-gateway/requirements.txt
pip install -r service-phrase/requirements.txt
pip install -r service-sentiment/requirements.txt
```

### 2. Frontend Setup

Navigate to the `frontend/` folder:

```bash
cd frontend
npm install
npm run dev
```

### 3. Launch Microservices

Run the batch script from the project root directory:

```dos
.\start_services.bat
```

This launches:
- **API Gateway** on `http://localhost:8000`
- **Phrase Service** on `http://localhost:8002`
- **Sentiment Service** on `http://localhost:8003`
- **Frontend** on `http://localhost:3000/live`

## 📊 Features

1. **Rolling Sentiment Score**: Evaluates the cumulative RoBERTa sentiment score using a sliding window of the last 6 sentences.
2. **Session Storage Persistence**: Saves full conversation history and rolling windows in browser `sessionStorage`.
3. **Supervisor Admin Dashboard**: Dynamically syncs monitored keywords and categories with Google Sheets.
