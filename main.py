# main.py

import uvicorn
import json
import time
import uuid
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any

from rag_chain import X4RAGChain # Import our RAG logic

# --- Pydantic Models for OpenAI Compatibility ---

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    stream: Optional[bool] = False

# --- FastAPI Application ---

app = FastAPI(
    title="X4 RAG API",
    description="An OpenAI-compatible API that uses a local RAG pipeline for X4 Foundations.",
    version="1.0.0",
)

# --- Initialize RAG Chain ---
# This creates a single, reusable instance of our RAG chain.
# It loads the models and vector store only once when the server starts.
rag_pipeline = X4RAGChain()


# --- API Endpoint ---

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """
    Handles chat completion requests, compatible with the OpenAI API.
    It uses the pre-initialized RAG pipeline to generate a response.
    """
    # Extract the last user message from the request
    user_query = ""
    if request.messages:
        last_message = request.messages[-1]
        if last_message.role == "user":
            user_query = last_message.content

    if not user_query:
        # Handle cases where there's no user query
        async def empty_stream():
            yield ""
        return StreamingResponse(empty_stream(), media_type="text/event-stream")

    # This async generator function wraps the RAG chain's output
    # into the OpenAI SSE format.
    async def event_stream():
        stream_id = f"chatcmpl-{uuid.uuid4()}"
        
        async for chunk in rag_pipeline.stream_query(user_query):
            if chunk:
                response_chunk = {
                    "id": stream_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": request.model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": chunk},
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(response_chunk)}\n\n"
        
        # After the stream is finished, send the final chunk with finish_reason
        final_chunk = {
            "id": stream_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": request.model,
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop"
            }]
        }
        yield f"data: {json.dumps(final_chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

# --- Main Entry Point ---

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)

