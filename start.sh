#!/bin/bash

# Start the Backend (FastAPI) in the background
# We bind to 0.0.0.0:8000 so the frontend can reach it internally
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 &

# Wait for the backend to start (optional, but good practice)
sleep 5

# Start the Frontend (Streamlit)
# server.port 7860 is REQUIRED by Hugging Face Spaces
streamlit run streamlit_app.py
