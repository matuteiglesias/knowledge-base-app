#!/usr/bin/env bash
# start backend and frontend in separate jobs
cd backend && uvicorn app.main:app --reload --port 9001 & 
cd ../frontend && npm run dev
