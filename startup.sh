#!/usr/bin/env bash
python -m uvicorn prof_ai.main:app --app-dir src --host 0.0.0.0 --port "${PORT:-8000}"
