import json
import time
import uuid

from fastapi import APIRouter, Response, HTTPException, Depends
from fastapi.responses import StreamingResponse
from api_models import ChatCompletionRequest, ChatCompletionResponse, ChatCompletionResponseChoice, ResponseMessage, UsageInfo
from rag_chain import X4RAGChain
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

router = APIRouter()
rag_pipeline = X4RAGChain()

@router.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    if not request.messages:
        raise HTTPException(status_code=400, detail="Messages list is empty.")

    user_query = request.messages[-1].content
    chat_history = []
    for msg in request.messages[:-1]:
        if msg.role == "user": chat_history.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant": chat_history.append(AIMessage(content=msg.content))
        elif msg.role == "system": chat_history.append(SystemMessage(content=msg.content))

    if request.stream:
        async def event_stream():
            stream_id = f"chatcmpl-{uuid.uuid4()}"
            async for chunk in rag_pipeline.stream_query(user_query, chat_history):
                if answer_chunk := chunk.get("answer"):
                    response_chunk = {
                        "id": stream_id, "object": "chat.completion.chunk", "created": int(time.time()),
                        "model": request.model, "choices": [{"index": 0, "delta": {"content": answer_chunk}, "finish_reason": None}]
                    }
                    yield f"data: {json.dumps(response_chunk)}\n\n"
            final_chunk = {"id": stream_id, "object": "chat.completion.chunk", "created": int(time.time()), "model": request.model, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
            yield f"data: {json.dumps(final_chunk)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")
    else:
        full_response_content = ""
        async for chunk in rag_pipeline.stream_query(user_query, chat_history):
            if answer_chunk := chunk.get("answer"):
                full_response_content += answer_chunk
        response = ChatCompletionResponse(id=f"chatcmpl-{uuid.uuid4()}", created=int(time.time()), model=request.model, choices=[ChatCompletionResponseChoice(index=0, message=ResponseMessage(role="assistant", content=full_response_content), finish_reason="stop")], usage=UsageInfo())
        return response


