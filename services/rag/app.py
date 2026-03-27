# rag service - takes user query, gets relevant chunks from embedding service,
# then sends them to openai to get a proper answer

import os, sys
import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config

app = FastAPI(title="RAG Service")

openai_client = OpenAI(api_key=config.OPENAI_API_KEY)
EMBEDDING_SERVICE_URL = config.EMBEDDING_SERVICE_URL
LLM_MODEL = "gpt-4o-mini"


class AskRequest(BaseModel):
    query: str
    top_k: int = config.TOP_K
    history: list[dict] | None = None

class AskResponse(BaseModel):
    answer: str
    sources: list[dict]


@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest):
    # get relevant chunks from embedding service
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{EMBEDDING_SERVICE_URL}/search",
            json={"query": request.query, "top_k": request.top_k},
        )
        resp.raise_for_status()
        chunks = resp.json()

    # build context string from chunks
    context_parts = []
    sources = []
    for chunk in chunks:
        context_parts.append(f"[Source: {chunk['source']}]\n{chunk['text']}")
        sources.append({
            "source": chunk["source"],
            "score": chunk["score"],
            "snippet": chunk["text"][:200]
        })

    context = "\n\n---\n\n".join(context_parts)

    # build the prompt
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant that answers questions based on the provided context. "
                       "Only use info from the context. If it doesnt have enough info, say so. Keep it short.",
        }
    ]

    # add last 3 messages from history if we have any
    if request.history:
        for entry in request.history[-3:]:
            messages.append({"role": entry.get("role", "user"), "content": entry.get("content", "")})

    messages.append({
        "role": "user",
        "content": f"Context:\n{context}\n\nQuestion: {request.query}",
    })

    # call openai
    completion = openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=0.3,
        max_tokens=500,
    )

    answer = completion.choices[0].message.content
    return AskResponse(answer=answer, sources=sources)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "rag"}
