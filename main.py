# main.py

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from logging_config import setup_logging
from api_routes import router as api_router

# --- Logging Configuration ---
setup_logging()
# --- End Logging Configuration ---

# --- FastAPI Application ---
app = FastAPI(
    title="X4 RAG API",
    description="An OpenAI-compatible API that uses a local RAG pipeline for X4 Foundations.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
