# main.py
import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api_routes import router as api_router
from  logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

logger.debug("Logger in main.py is configured.")

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
    cert_file = "ssl-cert.pem"
    key_file = "ssl-cert-key.pem"
    logger.info("Starting the server with SSL.")
    uvicorn.run(app, host="0.0.0.0", 
                port=8001, 
                log_config=None,
                ssl_keyfile=key_file,
                ssl_certfile=cert_file)
