# main.py

import uvicorn
import json
import time
import uuid
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict

from rag_chain import X4RAGChain

# --- Pydantic Models for OpenAI Compatibility ---
# We'll add more specific models for the non-streaming response

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    stream: Optional[bool] = False

# --- Models for Non-Streaming Response ---
class ResponseMessage(BaseModel):
    role: Literal["assistant"]
    content: str

class ChatCompletionResponseChoice(BaseModel):
    index: int
    message: ResponseMessage
    finish_reason: str

class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionResponseChoice]
    usage: UsageInfo


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

rag_pipeline = X4RAGChain()

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    user_query = ""
    if request.messages:
        last_message = request.messages[-1]
        if last_message.role == "user":
            user_query = last_message.content

    if not user_query:
        return Response(status_code=400, content="No user query found in messages.")

    # --- DUAL MODE: Handle streaming and non-streaming requests ---

    if request.stream:
        # --- Streaming Logic (existing code) ---
        async def event_stream():
            stream_id = f"chatcmpl-{uuid.uuid4()}"
            async for chunk in rag_pipeline.stream_query(user_query):
                if chunk:
                    response_chunk = {
                        "id": stream_id, "object": "chat.completion.chunk", "created": int(time.time()),
                        "model": request.model, "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}]
                    }
                    yield f"data: {json.dumps(response_chunk)}\n\n"
            final_chunk = {
                "id": stream_id, "object": "chat.completion.chunk", "created": int(time.time()),
                "model": request.model, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
            }
            yield f"data: {json.dumps(final_chunk)}\n\n"
            yield "data: [DONE]\n\n"
        
        from fastapi.responses import StreamingResponse
        return StreamingResponse(event_stream(), media_type="text/event-stream")

    else:
        # --- Non-Streaming Logic (for the "Test" button) ---
        full_response_content = ""
        async for chunk in rag_pipeline.stream_query(user_query):
            full_response_content += chunk
        
        response = ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4()}",
            created=int(time.time()),
            model=request.model,
            choices=[
                ChatCompletionResponseChoice(
                    index=0,
                    message=ResponseMessage(role="assistant", content=full_response_content),
                    finish_reason="stop"
                )
            ],
            usage=UsageInfo() # We can use dummy values for usage
        )
        return response

# --- Main Entry Point ---
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)

