#!/bin/bash

if [ ! -d "venv" ]; then
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements-base.txt
    python -m spacy download en_core_web_sm
else
    source venv/bin/activate
fi

trap 'kill $(jobs -p)' EXIT

(cd api-gateway && uvicorn main:app --port 8000 --reload) &
(cd service-phrase && uvicorn main:app --port 8002 --reload) &
(cd service-sentiment && uvicorn main:app --port 8003 --reload) &
(cd service-score && uvicorn main:app --port 8004 --reload) &

wait -n