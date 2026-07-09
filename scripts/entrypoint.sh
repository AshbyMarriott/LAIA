#!/bin/bash
set -euo pipefail

echo "Running database migrations..."
alembic upgrade head

echo "Starting LAIA API..."
exec uvicorn laia.main:app --host 0.0.0.0 --port 8000
