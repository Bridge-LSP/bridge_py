#!/bin/bash

echo "🔍 Testing Bridge Backend for Flutter"
echo ""

echo "Testing /health..."
curl -X GET "http://127.0.0.1:8000/health" \
  -H "Accept: application/json" \
  --max-time 10 \
  --silent \
  --show-error \
  --write-out "\nResponse Code: %{http_code}\n\n"

echo "Testing /autocorrector/session/create..."
curl -X POST "http://127.0.0.1:8000/autocorrector/session/create" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"session_id": "flutter_test_123"}' \
  --max-time 10 \
  --silent \
  --show-error \
  --write-out "\nResponse Code: %{http_code}\n\n"

echo "Done!"