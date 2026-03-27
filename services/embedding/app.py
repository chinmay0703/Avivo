# embedding service - handles chunking docs, generating embeddings and storing them in sqlite

import os, sys, json, hashlib, glob
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import aiosqlite
from sentence_transformers import SentenceTransformer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config

app = FastAPI(title="Embedding Service")

DB_PATH = config.DB_PATH
CHUNK_SIZE = config.CHUNK_SIZE
CHUNK_OVERLAP = config.CHUNK_OVERLAP
TOP_K = config.TOP_K
KNOWLEDGE_BASE_PATH = config.KNOWLEDGE_BASE_PATH

# load the model at startup - all-MiniLM-L6-v2 gives 384 dim vectors
print("loading embedding model...")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
EMBEDDING_DIM = 384
print("model loaded")


class QueryRequest(BaseModel):
    query: str
    top_k: int = TOP_K

class IngestRequest(BaseModel):
    file_path: str | None = None

class ChunkResult(BaseModel):
    text: str
    source: str
    score: float


def chunk_text(text, source):
    # split text into overlapping chunks
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end]
        if chunk.strip():
            chunks.append({"text": chunk.strip(), "source": source})
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def get_embedding(text):
    embedding = embedding_model.encode(text, convert_to_numpy=True)
    return embedding.tolist()

def get_embeddings_batch(texts):
    # batch is faster than doing one by one
    embeddings = embedding_model.encode(texts, convert_to_numpy=True, batch_size=32)
    return embeddings.tolist()

def compute_hash(text):
    return hashlib.md5(text.encode()).hexdigest()

def cosine_similarity(a, b):
    a_np, b_np = np.array(a), np.array(b)
    return float(np.dot(a_np, b_np) / (np.linalg.norm(a_np) * np.linalg.norm(b_np) + 1e-10))


async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                source TEXT NOT NULL,
                text_hash TEXT UNIQUE NOT NULL,
                embedding BLOB NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS query_cache (
                query_hash TEXT PRIMARY KEY,
                result TEXT NOT NULL
            )
        """)
        await db.commit()


@app.on_event("startup")
async def startup():
    await init_db()
    await ingest_knowledge_base()


async def ingest_knowledge_base():
    # read all md/txt files from knowledge_base folder
    files = []
    for pattern in ["*.md", "*.txt"]:
        files.extend(glob.glob(os.path.join(KNOWLEDGE_BASE_PATH, pattern)))

    if not files:
        print(f"no docs found in {KNOWLEDGE_BASE_PATH}")
        return

    for fp in files:
        await ingest_file(fp)
    print(f"ingested {len(files)} docs")


async def ingest_file(file_path):
    with open(file_path, "r") as f:
        text = f.read()

    source = os.path.basename(file_path)
    chunks = chunk_text(text, source)

    # figure out which chunks are new (skip already embedded ones)
    new_chunks = []
    async with aiosqlite.connect(DB_PATH) as db:
        for chunk in chunks:
            text_hash = compute_hash(chunk["text"])
            existing = await db.execute("SELECT id FROM embeddings WHERE text_hash = ?", (text_hash,))
            if not await existing.fetchone():
                new_chunks.append((chunk, text_hash))

    if not new_chunks:
        return

    # batch embed everything at once
    texts_to_embed = [c[0]["text"] for c in new_chunks]
    embeddings = get_embeddings_batch(texts_to_embed)

    async with aiosqlite.connect(DB_PATH) as db:
        for (chunk, text_hash), embedding in zip(new_chunks, embeddings):
            blob = np.array(embedding, dtype=np.float32).tobytes()
            await db.execute(
                "INSERT OR IGNORE INTO embeddings (text, source, text_hash, embedding) VALUES (?, ?, ?, ?)",
                (chunk["text"], chunk["source"], text_hash, blob),
            )
        await db.commit()


@app.post("/embed")
async def embed_text(request: QueryRequest):
    embedding = get_embedding(request.query)
    return {"embedding": embedding}


@app.post("/search", response_model=list[ChunkResult])
async def search(request: QueryRequest):
    # check cache first
    query_hash = compute_hash(request.query)
    async with aiosqlite.connect(DB_PATH) as db:
        cached = await db.execute("SELECT result FROM query_cache WHERE query_hash = ?", (query_hash,))
        row = await cached.fetchone()
        if row:
            return json.loads(row[0])

    query_embedding = get_embedding(request.query)

    # compare against all stored embeddings
    results = []
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT text, source, embedding FROM embeddings")
        rows = await cursor.fetchall()
        for text, source, embedding_blob in rows:
            stored = np.frombuffer(embedding_blob, dtype=np.float32).tolist()
            score = cosine_similarity(query_embedding, stored)
            results.append({"text": text, "source": source, "score": score})

    results.sort(key=lambda x: x["score"], reverse=True)
    top_results = results[:request.top_k]

    # save to cache
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO query_cache (query_hash, result) VALUES (?, ?)",
            (query_hash, json.dumps(top_results)),
        )
        await db.commit()

    return top_results


@app.post("/ingest")
async def ingest(request: IngestRequest):
    if request.file_path:
        if not os.path.exists(request.file_path):
            raise HTTPException(status_code=404, detail="File not found")
        await ingest_file(request.file_path)
        return {"status": "ok", "message": f"Ingested {request.file_path}"}
    else:
        await ingest_knowledge_base()
        return {"status": "ok", "message": "Ingested all docs"}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "embedding"}
