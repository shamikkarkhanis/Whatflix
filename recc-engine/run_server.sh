#!/bin/bash
echo "Starting Recc Engine on 0.0.0.0:8000..."
echo "Use 'uv sync' first if dependencies are not installed."
uv run uvicorn app:app --host 0.0.0.0 --port 8000 --reload
