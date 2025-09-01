# main.py

import uvicorn
import json
import time
import uuid
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Literal

from rag_chain import X4RAGChain
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

# --- Pydantic Models for OpenAI Compatibility ---

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
    if not request.messages:
        return Response(status_code=400, content="Messages list is empty.")

    # --- History Formatting ---
    # The last message is the new user query. All preceding messages are history.
    user_query = request.messages[-1].content
    
    chat_history = []
    # Convert all messages before the last one into LangChain message objects.
    # This history will include any user-defined character prompts.
    for msg in request.messages[:-1]:
        if msg.role == "user":
            chat_history.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            chat_history.append(AIMessage(content=msg.content))
        elif msg.role == "system":
            # Pass system messages along as part of the history, allowing for potential client-side rule additions.
            chat_history.append(SystemMessage(content=msg.content))

    # --- DUAL MODE: Handle streaming and non-streaming requests ---
    if request.stream:
        # --- Streaming Logic ---
        async def event_stream():
            stream_id = f"chatcmpl-{uuid.uuid4()}"
            async for chunk in rag_pipeline.stream_query(user_query, chat_history):
                if answer_chunk := chunk.get("answer"):
                    response_chunk = {
                        "id": stream_id, "object": "chat.completion.chunk", "created": int(time.time()),
                        "model": request.model, "choices": [{"index": 0, "delta": {"content": answer_chunk}, "finish_reason": None}]
                    }
                    yield f"data: {json.dumps(response_chunk)}\n\n"

            # Send the final chunk
            final_chunk = {
                "id": stream_id, "object": "chat.completion.chunk", "created": int(time.time()),
                "model": request.model, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
            }
            yield f"data: {json.dumps(final_chunk)}\n\n"
            yield "data: [DONE]\n\n"

        from fastapi.responses import StreamingResponse
        return StreamingResponse(event_stream(), media_type="text/event-stream")

    else:
        # --- Non-Streaming Logic ---
        full_response_content = ""
        async for chunk in rag_pipeline.stream_query(user_query, chat_history):
            if answer_chunk := chunk.get("answer"):
                full_response_content += answer_chunk

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
            usage=UsageInfo()
        )
        return response

# --- Main Entry Point ---
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
