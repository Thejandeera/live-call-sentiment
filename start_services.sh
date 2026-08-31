#!/bin/bash

source venv/bin/activate

trap 'kill $(jobs -p)' EXIT

(cd api-gateway && uvicorn main:app --port 8000 --reload) &
(cd service-phrase && uvicorn main:app --port 8002 --reload) &
(cd service-sentiment && uvicorn main:app --port 8003 --reload) &
(cd service-score && uvicorn main:app --port 8004 --reload) &

wait